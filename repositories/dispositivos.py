"""Estoque de dispositivos de identificação (ADR 0004 · etapa B7 · PNIB §5).

O brinco é um **bem antes de ser identidade**: é comprado em lote, fica em
estoque, pode ser perdido ou inutilizado. Nada disso cabia em
`animal_identifiers`, que registra o vínculo **já feito** — por isso a tabela é
outra, e as duas convivem: `dispositivos` é o objeto físico, `animal_identifiers`
é a relação com o animal.

A máquina de doze estados (§5.2) é `services/estados_dispositivo.py`, pura.
A conferência visual × eletrônico (§5.3) também. Aqui é a ligação.

Camada de dados (ROADMAP R1/R9): aqui mora o SQL, e só aqui.
"""

import uuid as _uuid
from datetime import date
from typing import Optional

from services.dispositivos import expandir_faixa
from services.estados_dispositivo import conferir_codigos, transicao_permitida

from . import eventos, identificadores
from .conexao import _cache, _conn, _writes

TIPOS = ("brinco_visual", "boton", "conjunto", "outro")

# Estados que ainda contam como estoque utilizável.
EM_ESTOQUE = ("recebido", "disponivel", "reservado")


def _novo_id() -> str:
    return str(_uuid.uuid4())


@_writes
def importar_lote(inicio: str, fim: str, *, lote: str,
                  tipo: str = "brinco_visual",
                  fabricante: str = "", fornecedor: str = "",
                  modelo: str = "", tecnologia: str = "",
                  data_aquisicao: str = "",
                  proprietario_id: Optional[str] = None,
                  propriedade_destino_id: Optional[str] = None,
                  usuario: str = "") -> dict:
    """Importa uma faixa de dispositivos (§5.3: importação de lotes).

    A faixa é expandida por `services/dispositivos.py`, que já valida prefixo e
    ordem. **Números já existentes são pulados, não sobrescritos** — reimportar
    o mesmo arquivo não pode duplicar nem apagar histórico de aplicação.
    """
    if tipo not in TIPOS:
        return {"ok": False, "erro": f"Tipo desconhecido: '{tipo}'."}
    try:
        numeros = expandir_faixa(inicio, fim)
    except ValueError as e:
        return {"ok": False, "erro": str(e)}

    criados = pulados = 0
    with _conn() as con:
        existentes = {r["codigo_visual"] for r in con.execute(
            "SELECT codigo_visual FROM dispositivos "
            "WHERE status NOT IN ('inutilizado','devolvido','cancelado')").fetchall()}
        for n in numeros:
            if n in existentes:
                pulados += 1
                continue
            con.execute(
                """INSERT INTO dispositivos
                   (id,codigo_visual,tipo,tecnologia,fabricante,fornecedor,
                    modelo,lote,data_aquisicao,proprietario_id,
                    propriedade_destino_id,status)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,'disponivel')""",
                (_novo_id(), n, tipo, tecnologia or None, fabricante or None,
                 fornecedor or None, modelo or None, lote,
                 data_aquisicao or None, proprietario_id,
                 propriedade_destino_id))
            criados += 1

    eventos.auditar("importacao_de_lote_de_dispositivos", usuario=usuario,
                    entidade="dispositivos", entidade_id=lote,
                    registro_posterior={"faixa": f"{inicio}..{fim}",
                                        "criados": criados, "pulados": pulados})
    return {"ok": True, "criados": criados, "pulados": pulados,
            "total_na_faixa": len(numeros)}


@_writes
def mudar_status(dispositivo_id: str, novo: str, *, motivo: str = "",
                 usuario: str = "", tem_autorizacao: bool = False) -> dict:
    """Muda o estado passando pela máquina do §5.2.

    Único funil de mudança de estado — a regra vale para todos os chamadores.
    """
    with _conn() as con:
        row = con.execute(
            "SELECT status, codigo_visual FROM dispositivos WHERE id=?",
            (dispositivo_id,)).fetchone()
    if row is None:
        return {"ok": False, "erro": "Dispositivo não encontrado."}

    atual = row["status"]
    v = transicao_permitida(atual, novo, tem_autorizacao=tem_autorizacao)
    if not v["permitida"]:
        return {"ok": False, "de": atual, "para": novo, **v}
    if v["exige_motivo"] and not motivo.strip():
        return {"ok": False, "de": atual, "para": novo, **v,
                "motivo": f"Mudar para '{novo}' exige motivo registrado."}

    with _conn() as con:
        campos = ["status=?"]
        args: list = [novo]
        if novo == "inutilizado":
            campos.append("motivo_inutilizacao=?"); args.append(motivo.strip())
        if novo in ("devolvido", "inutilizado"):
            campos.append("data_baixa=?"); args.append(date.today().isoformat())
        args.append(dispositivo_id)
        con.execute(f"UPDATE dispositivos SET {', '.join(campos)} WHERE id=?", args)

    eventos.auditar("mudanca_status_dispositivo", usuario=usuario,
                    entidade="dispositivos", entidade_id=dispositivo_id,
                    registro_anterior={"status": atual},
                    registro_posterior={"status": novo},
                    motivo=motivo.strip(),
                    autorizacao=usuario if v["exige_autorizacao"] else "")
    return {"ok": True, "de": atual, "para": novo, **v}


@_writes
def aplicar(dispositivo_id: str, animal_uuid: str, *,
            aplicador: str = "", data: str = "",
            tipo_identificador: str = "manejo",
            eletronico_lido: str = "",
            motivo_substituicao: str = "") -> dict:
    """Aplica o dispositivo num animal (§5.3).

    Faz **duas coisas que precisam andar juntas**: baixa o dispositivo do
    estoque e cria o identificador do animal. Separá-las deixaria brinco
    aplicado sem vínculo, ou vínculo sem brinco baixado.

    `eletronico_lido` permite conferir visual × eletrônico na hora da aplicação.
    Divergência é **registrada, não bloqueia** — pode ser erro de leitura, e
    recusar trava o trabalho no curral.
    """
    data = data or date.today().isoformat()
    with _conn() as con:
        d = con.execute(
            "SELECT * FROM dispositivos WHERE id=?", (dispositivo_id,)).fetchone()
        if d is None:
            return {"ok": False, "erro": "Dispositivo não encontrado."}
        existe = con.execute(
            "SELECT 1 FROM animals WHERE uuid=?", (animal_uuid,)).fetchone()
        if existe is None:
            return {"ok": False, "erro": "Animal não encontrado."}

    v = transicao_permitida(d["status"], "aplicado")
    if not v["permitida"]:
        return {"ok": False, "erro": v["motivo"], **v}

    divergencia = None
    if eletronico_lido:
        conf = conferir_codigos(d["codigo_visual"], eletronico_lido)
        if not conf["confere"]:
            divergencia = conf["divergencia"]

    # O animal já tem um identificador vigente deste tipo? Então isto é TROCA
    # de brinco, não primeira aplicação — e o §4.2.3 exige encerrar o anterior
    # com motivo, em vez de deixar dois ativos. Sem esta checagem, o animal
    # ficaria com dois brincos de manejo válidos e ninguém saberia qual vale.
    vigente = identificadores.get_ativo(animal_uuid, tipo_identificador)
    if vigente and vigente["valor"] != d["codigo_visual"]:
        if not motivo_substituicao.strip():
            return {"ok": False, "exige_motivo_substituicao": True,
                    "erro": f"Animal já tem {tipo_identificador} "
                            f"'{vigente['valor']}'. Trocar exige motivo (§4.2.3)."}
        r = identificadores.substituir(animal_uuid, tipo_identificador,
                                       d["codigo_visual"],
                                       motivo_substituicao.strip(),
                                       aplicado_por=aplicador)
    else:
        r = identificadores.aplicar(animal_uuid, tipo_identificador,
                                    d["codigo_visual"], aplicado_por=aplicador,
                                    aplicado_em=data)
    if not r.get("ok"):
        return {"ok": False, "erro": r.get("erro")}

    with _conn() as con:
        con.execute(
            "UPDATE dispositivos SET status='aplicado', animal_uuid=?, "
            "data_aplicacao=?, aplicador=?, divergencia=? WHERE id=?",
            (animal_uuid, data, aplicador or None, divergencia, dispositivo_id))
        eventos.registrar_em(
            con, animal_uuid, "aplicacao_dispositivo", ocorrido_em=data,
            usuario_registro=aplicador,
            observacoes=f"{d['tipo']} {d['codigo_visual']}"
                        + (f" — DIVERGÊNCIA: {divergencia}" if divergencia else ""))

    return {"ok": True, "divergencia": divergencia,
            "alerta": bool(divergencia)}


def get(dispositivo_id: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM dispositivos WHERE id=?", (dispositivo_id,)).fetchone()
    return dict(row) if row else None


def por_codigo(codigo_visual: str) -> Optional[dict]:
    """Localiza pelo código visual — é como o operador busca no curral."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM dispositivos WHERE codigo_visual=? "
            "AND status NOT IN ('inutilizado','devolvido','cancelado')",
            (codigo_visual,)).fetchone()
    return dict(row) if row else None


@_cache
def inventario() -> dict:
    """Inventário por estado e por lote (§5.3).

    Responde o que o pecuarista pergunta antes de comprar mais: quantos ainda
    tenho, e quantos já se perderam.
    """
    with _conn() as con:
        por_status = {r["status"]: r["c"] for r in con.execute(
            "SELECT status, count(*) c FROM dispositivos GROUP BY status").fetchall()}
        por_lote = [dict(r) for r in con.execute(
            "SELECT lote, count(*) AS total, "
            "SUM(CASE WHEN status IN ('recebido','disponivel','reservado') "
            "         THEN 1 ELSE 0 END) AS em_estoque "
            "FROM dispositivos WHERE lote IS NOT NULL "
            "GROUP BY lote ORDER BY lote").fetchall()]
        divergentes = [dict(r) for r in con.execute(
            "SELECT id, codigo_visual, divergencia FROM dispositivos "
            "WHERE divergencia IS NOT NULL").fetchall()]

    return {
        "por_status": por_status,
        "por_lote": por_lote,
        "em_estoque": sum(por_status.get(s, 0) for s in EM_ESTOQUE),
        "aplicados": por_status.get("aplicado", 0),
        "perdidos_ou_danificados": (por_status.get("perdido", 0)
                                    + por_status.get("danificado", 0)),
        "divergencias": divergentes,
    }


def disponiveis(limite: int = 20) -> list[dict]:
    """Próximos dispositivos prontos para aplicar, em ordem de código."""
    with _conn() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM dispositivos WHERE status='disponivel' "
            "ORDER BY codigo_visual LIMIT ?", (limite,)).fetchall()]
