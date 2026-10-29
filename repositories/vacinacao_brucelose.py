"""Vacinação contra brucelose: o ato de vacinar e o estado do registro oficial (SDA/RS).

Camada de dados (ROADMAP R1/R9): aqui mora o SQL. A regra pura (prazo, situação do prazo,
veterinário, aviso de idade) vem de `services/vacinacao_brucelose.py`.

O AgroTop **não registra nada no SDA** (o módulo não tem API para terceiros). Este módulo
guarda o ato e a ficha que o veterinário usa para lançar no SDA; o estado do registro oficial
só muda por confirmação humana, com a referência do atestado.

Cada animal vacinado também ganha uma aplicação (`medications`) e um evento
`vacinacao_brucelose`, na mesma transação do ato, então carência, estoque, lote/validade e a
revisão por cancelar/corrigir valem como para qualquer tratamento.
"""

import uuid as _uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from services.tratamento import normalizar_produto
from services.vacinacao_brucelose import (
    DadoInvalido, EXCECAO, PENDENTE, REGISTRADO, aviso_de_idade, normalizar_veterinario,
    prazo_sda, situacao_do_prazo,
)
from services.zootecnia import get_age_months

from . import eventos
from .conexao import _conn, _writes
from .revisao import motivo_obrigatorio
from .sanidade import MedicationData, _cancelar_em, _inserir_aplicacao

LIMITE_REFERENCIA = 120
LIMITE_JUSTIFICATIVA = 500


class VacinacaoInvalida(ValueError):
    """Vacinação recusada (dado inválido, animal fora da regra, estado que não permite a ação).
    Nada é gravado."""


@dataclass
class NovaVacinacao:
    property_id: str
    vacinado_em: str
    animal_ids: list
    produto: str
    veterinario_nome: str
    veterinario_crmv: str = ""
    veterinario_uf: str = ""
    lote_produto: str = ""
    validade_produto: str = ""
    dose: float = 2.0
    unidade: str = "ml"
    via: str = "Subcutânea"
    insumo_id: Optional[int] = None
    operator: str = ""
    notes: str = ""


def _texto(valor, limite: int, rotulo: str, obrigatorio: bool = False) -> str:
    t = " ".join(str(valor or "").split())
    if obrigatorio and not t:
        raise VacinacaoInvalida(f"Informe {rotulo}.")
    if len(t) > limite:
        raise VacinacaoInvalida(f"{rotulo[0].upper() + rotulo[1:]} muito longo (máximo {limite} caracteres).")
    return t


def _identificadores(con, uuids: list) -> dict:
    """`{animal_uuid: {"oficial": ..., "genealogico": ...}}` com o que estava ativo hoje."""
    if not uuids:
        return {}
    marcas = ",".join("?" for _ in uuids)
    rows = con.execute(
        f"""SELECT animal_uuid, tipo, valor FROM animal_identifiers
            WHERE status='ativo' AND tipo IN ('oficial_pnib','sisbov','registro_genealogico')
              AND animal_uuid IN ({marcas}) ORDER BY id""", uuids).fetchall()
    out: dict = {}
    for r in rows:
        d = out.setdefault(r["animal_uuid"], {"oficial": None, "genealogico": None})
        if r["tipo"] == "registro_genealogico":
            d["genealogico"] = r["valor"]
        elif r["tipo"] == "oficial_pnib" or d["oficial"] is None:
            d["oficial"] = r["valor"]
    return out


@_writes
def registrar(dados: NovaVacinacao) -> dict:
    """Registra o ato de vacinação e as aplicações, tudo na mesma transação.

    Regras: propriedade existente; ao menos um animal; só fêmeas (o módulo do SDA é de fêmeas
    bovinas e bubalinas); animais da própria propriedade e ainda no rebanho; data não futura;
    produto não vencido. Idade fora de 3 a 8 meses com B19 não bloqueia: vai em `avisos`.

    Levanta `VacinacaoInvalida` (ou `TratamentoInvalido`, para produto vencido); nada é gravado.
    """
    try:
        vet = normalizar_veterinario(dados.veterinario_nome, dados.veterinario_crmv, dados.veterinario_uf)
        prazo = prazo_sda(dados.vacinado_em)
        vacinado = datetime.strptime(dados.vacinado_em, "%Y-%m-%d").date()
    except DadoInvalido as exc:
        raise VacinacaoInvalida(str(exc)) from None
    if vacinado > date.today():
        raise VacinacaoInvalida("A data da vacinação não pode ser futura.")
    produto = _texto(dados.produto, 80, "o produto (vacina)", obrigatorio=True)
    notes = _texto(dados.notes, LIMITE_JUSTIFICATIVA, "observação")
    ids = list(dict.fromkeys(str(a) for a in (dados.animal_ids or [])))
    if not ids:
        raise VacinacaoInvalida("Escolha ao menos um animal.")
    if len(ids) > 500:
        raise VacinacaoInvalida("No máximo 500 animais por vacinação; divida em mais de um ato.")
    if float(dados.dose) <= 0:
        raise VacinacaoInvalida("A dose deve ser maior que zero.")
    # Produto vencido na data da vacinação não se aplica (mesma regra do tratamento).
    p = normalizar_produto("", dados.lote_produto, dados.validade_produto, dados.vacinado_em)

    avisos: list = []
    with _conn() as con:
        prop = con.execute("SELECT id, nome FROM properties WHERE id=?", (dados.property_id,)).fetchone()
        if prop is None:
            raise VacinacaoInvalida("Propriedade não encontrada.")
        marcas = ",".join("?" for _ in ids)
        animais = {r["id"]: dict(r) for r in con.execute(
            f"""SELECT id, uuid, sex, status, property_id, birth_date FROM animals
                WHERE id IN ({marcas})""", ids).fetchall()}
        faltando = [a for a in ids if a not in animais]
        if faltando:
            raise VacinacaoInvalida("Animal não encontrado: " + ", ".join(faltando) + ".")
        machos = [a for a in ids if animais[a]["sex"] != "F"]
        if machos:
            raise VacinacaoInvalida("A vacinação contra brucelose é de fêmeas. Machos na seleção: "
                                    + ", ".join(machos) + ".")
        fora = [a for a in ids if animais[a]["property_id"] != dados.property_id]
        if fora:
            raise VacinacaoInvalida("Animais de outra propriedade: " + ", ".join(fora) + ".")
        inativos = [a for a in ids if animais[a]["status"] not in ("ativo", "carencia")]
        if inativos:
            raise VacinacaoInvalida("Animais fora do rebanho (vendidos ou mortos): "
                                    + ", ".join(inativos) + ".")

        for a in ids:
            aviso = aviso_de_idade(produto, get_age_months(animais[a]["birth_date"]))
            if aviso:
                avisos.append(f"{a}: {aviso}")

        ident = _identificadores(con, [animais[a]["uuid"] for a in ids])
        vacinacao_id = str(_uuid.uuid4())
        con.execute(
            """INSERT INTO vacinacoes_brucelose
               (id,property_id,vacinado_em,produto,lote_produto,validade_produto,dose,unidade,via,
                insumo_id,veterinario_nome,veterinario_crmv,veterinario_uf,status_oficial,prazo_sda,
                registrado_por,notes)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vacinacao_id, dados.property_id, dados.vacinado_em, produto,
             p["lote_produto"] or None, p["validade_produto"] or None, float(dados.dose),
             dados.unidade, dados.via, dados.insumo_id or None, vet["veterinario_nome"],
             vet["veterinario_crmv"] or None, vet["veterinario_uf"] or None, PENDENTE, prazo,
             dados.operator or None, notes or None))
        for a in ids:
            medication_id = _inserir_aplicacao(
                con,
                MedicationData(
                    animal_id=a, medication_name=f"Vacina brucelose {produto}",
                    dose=float(dados.dose), unit=dados.unidade, application_route=dados.via,
                    withdrawal_days=0, med_date=dados.vacinado_em,
                    applied_by=dados.operator or vet["veterinario_nome"],
                    insumo_id=dados.insumo_id, notes=f"Vacinação contra brucelose ({vacinacao_id[:8]})",
                    principio_ativo="Brucella abortus", lote_produto=p["lote_produto"],
                    validade_produto=p["validade_produto"]),
                tipo_evento="vacinacao_brucelose")
            i = ident.get(animais[a]["uuid"], {})
            con.execute(
                """INSERT INTO vacinacao_brucelose_animais
                   (vacinacao_id,animal_uuid,brinco,identificador_oficial,registro_genealogico,medication_id)
                   VALUES(?,?,?,?,?,?)""",
                (vacinacao_id, animais[a]["uuid"], a, i.get("oficial"), i.get("genealogico"),
                 medication_id))
        eventos.auditar_em(
            con, "registrar_vacinacao_brucelose", usuario=dados.operator, entidade="vacinacoes_brucelose",
            entidade_id=vacinacao_id,
            registro_posterior={"propriedade": prop["nome"], "vacinado_em": dados.vacinado_em,
                                "produto": produto, "animais": len(ids), "prazo_sda": prazo,
                                "veterinario": vet["veterinario_nome"]})
    return {"ok": True, "id": vacinacao_id, "n": len(ids), "prazo_sda": prazo, "avisos": avisos}


def _carregar(con, vacinacao_id: str) -> dict:
    v = con.execute("SELECT * FROM vacinacoes_brucelose WHERE id=?", (vacinacao_id,)).fetchone()
    if v is None:
        raise VacinacaoInvalida("Vacinação não encontrada.")
    return dict(v)


@_writes
def confirmar_registro_sda(vacinacao_id: str, referencia: str, usuario: str) -> dict:
    """Marca como registrada no SDA. Só por confirmação humana, com a referência do atestado
    (número ou código emitido pelo SDA). O AgroTop nunca infere isto."""
    ref = _texto(referencia, LIMITE_REFERENCIA, "a referência do atestado emitido no SDA", obrigatorio=True)
    with _conn() as con:
        v = _carregar(con, vacinacao_id)
        if v["cancelada_em"]:
            raise VacinacaoInvalida("Esta vacinação foi cancelada.")
        if v["status_oficial"] != PENDENTE:
            raise VacinacaoInvalida(f"A vacinação já está '{v['status_oficial']}'.")
        con.execute(
            """UPDATE vacinacoes_brucelose SET status_oficial=?, referencia_atestado=?,
               confirmado_por=?, confirmado_em=? WHERE id=? AND status_oficial=?""",
            (REGISTRADO, ref, usuario or None, eventos._agora(), vacinacao_id, PENDENTE))
        eventos.auditar_em(
            con, "confirmar_registro_sda", usuario=usuario, entidade="vacinacoes_brucelose",
            entidade_id=vacinacao_id, registro_anterior={"status_oficial": v["status_oficial"]},
            registro_posterior={"status_oficial": REGISTRADO, "referencia_atestado": ref})
    return {"ok": True, "status_oficial": REGISTRADO}


@_writes
def registrar_excecao(vacinacao_id: str, justificativa: str, usuario: str) -> dict:
    """Fecha a pendência sem registro no SDA, com justificativa escrita (ex.: vacinação anterior
    à exigência, ou registro feito fora do prazo por motivo justificável)."""
    just = _texto(justificativa, LIMITE_JUSTIFICATIVA, "a justificativa da exceção", obrigatorio=True)
    with _conn() as con:
        v = _carregar(con, vacinacao_id)
        if v["cancelada_em"]:
            raise VacinacaoInvalida("Esta vacinação foi cancelada.")
        if v["status_oficial"] != PENDENTE:
            raise VacinacaoInvalida(f"A vacinação já está '{v['status_oficial']}'.")
        con.execute(
            """UPDATE vacinacoes_brucelose SET status_oficial=?, justificativa_excecao=?,
               confirmado_por=?, confirmado_em=? WHERE id=? AND status_oficial=?""",
            (EXCECAO, just, usuario or None, eventos._agora(), vacinacao_id, PENDENTE))
        eventos.auditar_em(
            con, "excecao_registro_sda", usuario=usuario, entidade="vacinacoes_brucelose",
            entidade_id=vacinacao_id, registro_anterior={"status_oficial": v["status_oficial"]},
            registro_posterior={"status_oficial": EXCECAO}, motivo=just)
    return {"ok": True, "status_oficial": EXCECAO}


@_writes
def cancelar(vacinacao_id: str, motivo: str, usuario: str) -> dict:
    """Cancela o ato inteiro (e cada aplicação, com estorno de estoque e evento), só enquanto
    o registro no SDA não foi confirmado: depois, o cancelamento é feito no próprio SDA."""
    motivo = motivo_obrigatorio(motivo)
    with _conn() as con:
        v = _carregar(con, vacinacao_id)
        if v["cancelada_em"]:
            raise VacinacaoInvalida("Esta vacinação já foi cancelada.")
        if v["status_oficial"] == REGISTRADO:
            raise VacinacaoInvalida(
                "Vacinação já registrada no SDA: o cancelamento precisa ser feito no SDA.")
        itens = con.execute(
            "SELECT medication_id FROM vacinacao_brucelose_animais WHERE vacinacao_id=?",
            (vacinacao_id,)).fetchall()
        for it in itens:
            if it["medication_id"]:
                try:
                    _cancelar_em(con, it["medication_id"], motivo, usuario, registrar_estorno=True)
                except ValueError:
                    # Aplicação já cancelada ou corrigida à mão: não impede cancelar o ato.
                    continue
        con.execute(
            """UPDATE vacinacoes_brucelose SET cancelada_em=?, cancelada_por=?, motivo_cancelamento=?
               WHERE id=? AND cancelada_em IS NULL""",
            (eventos._agora(), usuario or None, motivo, vacinacao_id))
        eventos.auditar_em(
            con, "cancelar_vacinacao_brucelose", usuario=usuario, entidade="vacinacoes_brucelose",
            entidade_id=vacinacao_id, registro_anterior={"status_oficial": v["status_oficial"]},
            motivo=motivo)
    return {"ok": True}


def listar(incluir_canceladas: bool = False) -> list[dict]:
    """Os atos de vacinação, do mais recente ao mais antigo, com a propriedade, o total de
    animais e a situação do prazo."""
    sql = """SELECT v.*, p.nome AS property_nome,
                    (SELECT COUNT(*) FROM vacinacao_brucelose_animais a WHERE a.vacinacao_id=v.id) AS n_animais
             FROM vacinacoes_brucelose v JOIN properties p ON p.id=v.property_id"""
    if not incluir_canceladas:
        sql += " WHERE v.cancelada_em IS NULL"
    sql += " ORDER BY v.vacinado_em DESC, v.created_at DESC"
    hoje = date.today()
    with _conn() as con:
        rows = [dict(r) for r in con.execute(sql).fetchall()]
    for r in rows:
        r["situacao_prazo"] = ("cancelada" if r["cancelada_em"]
                               else situacao_do_prazo(r["status_oficial"], r["prazo_sda"], hoje))
    return rows


def animais_da_vacinacao(vacinacao_id: str) -> list[dict]:
    """A ficha dos animais vacinados (brinco, identificador oficial, registro genealógico)."""
    with _conn() as con:
        rows = con.execute(
            """SELECT brinco, identificador_oficial, registro_genealogico, medication_id
               FROM vacinacao_brucelose_animais WHERE vacinacao_id=? ORDER BY brinco""",
            (vacinacao_id,)).fetchall()
    return [dict(r) for r in rows]


def pendencias_sda() -> list[dict]:
    """Vacinações com lançamento no SDA exigido e ainda não confirmado, com o prazo e quanto
    falta. Alimenta a recomendação de pendência."""
    hoje = date.today()
    out = []
    for v in listar():
        if v["status_oficial"] == PENDENTE and v["prazo_sda"]:
            out.append({
                "id": v["id"], "vacinado_em": v["vacinado_em"], "prazo": v["prazo_sda"],
                "produto": v["produto"], "n_animais": v["n_animais"],
                "propriedade": v["property_nome"],
                "dias": (date.fromisoformat(v["prazo_sda"]) - hoje).days,
            })
    return sorted(out, key=lambda p: p["prazo"])
