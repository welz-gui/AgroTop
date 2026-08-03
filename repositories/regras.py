"""Regras regulatórias configuráveis (ADR 0004 · etapa B5 · PNIB §11).

O §11 abre com a exigência que define esta etapa: **"as regras não devem ficar
fixadas no código-fonte"**. Aqui elas são linhas de tabela; a avaliação é
`services/regras_regulatorias.py`, pura.

**Regra alterada não se sobrescreve: cria versão nova.** Uma movimentação
julgada em 2027 precisa poder ser reexaminada pela regra que valia então — se a
linha for editada no lugar, o histórico regulatório passa a mentir. É a mesma
lógica de `animal_events` ser append-only.

Camada de dados (ROADMAP R1/R9): aqui mora o SQL, e só aqui.
"""

import json
import uuid as _uuid
from datetime import date
from typing import Optional

from services.regras_regulatorias import (ESFERAS, NIVEIS, avaliar,
                                          exige_confirmacao, pode_prosseguir,
                                          simular)

from . import eventos
from .conexao import _cache, _conn, _writes


def _novo_id() -> str:
    return str(_uuid.uuid4())


def _linha(r) -> dict:
    d = dict(r)
    if isinstance(d.get("condicao"), str):
        try:
            d["condicao"] = json.loads(d["condicao"])
        except (ValueError, TypeError):
            d["condicao"] = None
    return d


@_cache
def listar(*, apenas_ativas: bool = True,
           evento: Optional[str] = None) -> list[dict]:
    """Regras cadastradas.

    `apenas_ativas` filtra por **aprovação**, não por vigência: rascunho sem
    responsável não entra. A vigência é aplicada depois, por data, em
    `services/regras_regulatorias.vigente_em` — é o que permite reexaminar um
    fato de 2024 com a norma de 2024.
    """
    sql = "SELECT * FROM regras_regulatorias WHERE 1=1"
    args: list = []
    if apenas_ativas:
        sql += " AND ativa=1"
    if evento:
        sql += " AND (evento_aplicacao=? OR evento_aplicacao IS NULL)"
        args.append(evento)
    sql += " ORDER BY esfera, nome, versao DESC"
    with _conn() as con:
        return [_linha(r) for r in con.execute(sql, args).fetchall()]


def get(regra_id: str) -> Optional[dict]:
    with _conn() as con:
        r = con.execute("SELECT * FROM regras_regulatorias WHERE id=?",
                        (regra_id,)).fetchone()
    return _linha(r) if r else None


@_writes
def criar(nome: str, *, nivel: str = "informativo", esfera: str = "federal",
          descricao: str = "", fundamento: str = "", mensagem: str = "",
          uf: Optional[str] = None, especie: Optional[str] = None,
          categoria: Optional[str] = None, sexo: Optional[str] = None,
          idade_min_meses: Optional[int] = None,
          idade_max_meses: Optional[int] = None,
          finalidade: Optional[str] = None,
          evento_aplicacao: Optional[str] = None,
          data_inicial: Optional[str] = None,
          data_final: Optional[str] = None,
          condicao=None, excecoes: str = "",
          documentacao_exigida: str = "",
          aprovado_por: str = "", usuario: str = "") -> dict:
    """Cria uma regra. **Nasce inativa se não tiver `aprovado_por`.**

    Regra de bloqueio ativada sem aprovação registrada é decisão regulatória
    sem responsável — e o §11.1 pede o responsável pela aprovação justamente
    para que exista a quem perguntar depois.
    """
    if nivel not in NIVEIS:
        return {"ok": False, "erro": f"Nível inválido: '{nivel}'."}
    if esfera not in ESFERAS:
        return {"ok": False, "erro": f"Esfera inválida: '{esfera}'."}

    rid = _novo_id()
    ativa = 1 if aprovado_por.strip() else 0
    with _conn() as con:
        con.execute(
            """INSERT INTO regras_regulatorias
               (id,nome,descricao,fundamento,esfera,uf,especie,categoria,sexo,
                idade_min_meses,idade_max_meses,finalidade,evento_aplicacao,
                data_inicial,data_final,nivel,condicao,mensagem,excecoes,
                documentacao_exigida,versao,aprovado_por,ultima_revisao,ativa)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?)""",
            (rid, nome, descricao or None, fundamento or None, esfera, uf,
             especie, categoria, sexo, idade_min_meses, idade_max_meses,
             finalidade, evento_aplicacao, data_inicial, data_final, nivel,
             json.dumps(condicao, ensure_ascii=False) if condicao else None,
             mensagem or None, excecoes or None, documentacao_exigida or None,
             aprovado_por or None, date.today().isoformat(), ativa))

    eventos.auditar("criacao_de_regra_regulatoria", usuario=usuario,
                    entidade="regras_regulatorias", entidade_id=rid,
                    registro_posterior={"nome": nome, "nivel": nivel,
                                        "ativa": bool(ativa)},
                    autorizacao=aprovado_por)
    return {"ok": True, "id": rid, "ativa": bool(ativa)}


@_writes
def nova_versao(regra_id: str, *, aprovado_por: str, usuario: str,
                **campos) -> dict:
    """Altera uma regra **criando outra versão** e encerrando a anterior.

    Editar no lugar reescreveria o passado: uma movimentação julgada em 2027
    passaria a ser explicada por um texto que não existia então. Aqui a versão
    antiga fica com `data_final` de ontem e a nova começa hoje.
    """
    if not aprovado_por.strip():
        return {"ok": False, "erro": "Nova versão exige responsável pela aprovação."}

    atual = get(regra_id)
    if atual is None:
        return {"ok": False, "erro": "Regra não encontrada."}

    hoje = date.today()
    ontem = date.fromordinal(hoje.toordinal() - 1).isoformat()
    novo = {k: v for k, v in atual.items()
            if k not in ("id", "versao", "created_at", "ativa", "ultima_revisao")}
    novo.update(campos)
    novo["data_inicial"] = hoje.isoformat()
    novo["data_final"] = None

    rid = _novo_id()
    with _conn() as con:
        # Só `data_final` — a versão antiga NÃO é marcada inativa.
        # `ativa` significa "aprovada"; a vigência é dada pelas datas. Marcar
        # inativa faria o `listar` esconder a regra e o passado ficaria sem
        # norma para julgá-lo, que é exatamente o que o versionamento existe
        # para evitar. Foi o teste do reexame de 2024 que pegou isto.
        con.execute(
            "UPDATE regras_regulatorias SET data_final=? WHERE id=?",
            (ontem, regra_id))
        con.execute(
            """INSERT INTO regras_regulatorias
               (id,nome,descricao,fundamento,esfera,uf,especie,categoria,sexo,
                idade_min_meses,idade_max_meses,finalidade,evento_aplicacao,
                data_inicial,data_final,nivel,condicao,mensagem,excecoes,
                documentacao_exigida,versao,aprovado_por,ultima_revisao,ativa)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (rid, novo.get("nome"), novo.get("descricao"), novo.get("fundamento"),
             novo.get("esfera"), novo.get("uf"), novo.get("especie"),
             novo.get("categoria"), novo.get("sexo"),
             novo.get("idade_min_meses"), novo.get("idade_max_meses"),
             novo.get("finalidade"), novo.get("evento_aplicacao"),
             novo["data_inicial"], novo["data_final"], novo.get("nivel"),
             json.dumps(novo.get("condicao"), ensure_ascii=False)
             if novo.get("condicao") else None,
             novo.get("mensagem"), novo.get("excecoes"),
             novo.get("documentacao_exigida"),
             (atual.get("versao") or 1) + 1, aprovado_por,
             hoje.isoformat()))

    eventos.auditar("nova_versao_de_regra", usuario=usuario,
                    entidade="regras_regulatorias", entidade_id=rid,
                    registro_anterior={"id": regra_id,
                                       "versao": atual.get("versao")},
                    registro_posterior={"versao": (atual.get("versao") or 1) + 1},
                    autorizacao=aprovado_por)
    return {"ok": True, "id": rid, "versao": (atual.get("versao") or 1) + 1}


def aplicar_a(contexto: dict, *, evento: Optional[str] = None,
              referencia: Optional[str] = None) -> dict:
    """Avalia as regras vigentes contra um contexto.

    `referencia` é a data pela qual julgar. **Omitir usa hoje**, o que só é
    correto para decisão presente — para reexaminar o passado, passe a data do
    fato, senão a norma de hoje julga o que aconteceu antes dela existir.
    """
    disparadas = avaliar(listar(evento=evento), contexto, referencia)
    return {"disparadas": disparadas,
            "pode_prosseguir": pode_prosseguir(disparadas),
            "exige_confirmacao": exige_confirmacao(disparadas)}


def simular_regra(regra_id: str, casos: list[dict],
                  referencia: Optional[str] = None) -> dict:
    """§11.3: mede o alcance de uma regra **antes de ativá-la**.

    Ativar bloqueio sem simular é descobrir o alcance no dia em que o caminhão
    está no curral.
    """
    r = get(regra_id)
    if r is None:
        return {"ok": False, "erro": "Regra não encontrada."}
    return {"ok": True, **simular(r, casos, referencia)}
