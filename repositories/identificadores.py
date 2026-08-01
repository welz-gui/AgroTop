"""Identificadores do animal (ADR 0004 · PNIB §4.1 e §4.2).

O brinco deixa de ser a identidade do animal e passa a ser **um identificador
entre vários**, com vigência própria. Trocar brinco vira encerrar um registro e
abrir outro — sem apagar o anterior, como o §4.2.3 exige.

Camada de dados (ROADMAP R1/R9): aqui mora o SQL, e só aqui. A validação de
formato é regra de negócio e vive em `services/identificadores.py`.
"""

from datetime import date
from typing import Optional

from .conexao import _cache, _conn, _writes

# Tipos previstos no §4.1. `oficial_pnib` fica no vocabulário desde já, mesmo
# sem formato publicado — a coluna aceita, a validação é configurável.
TIPOS = ("manejo", "oficial_pnib", "visual", "rfid", "sisbov", "privado")


@_cache
def _por_animal() -> dict:
    """Todos os identificadores agrupados por animal. 1 consulta (R11)."""
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM animal_identifiers ORDER BY animal_uuid, tipo, id"
        ).fetchall()
    out: dict = {}
    for r in rows:
        out.setdefault(r["animal_uuid"], []).append(dict(r))
    return out


def get_identificadores(animal_uuid: str, *, apenas_ativos: bool = False) -> list[dict]:
    """Identificadores de um animal, inclusive os históricos.

    `apenas_ativos=True` devolve só os vigentes — é o que a interface mostra.
    O histórico completo é o que sustenta a rastreabilidade (§4.2.10).
    """
    itens = _por_animal().get(animal_uuid, [])
    return [i for i in itens if i["status"] == "ativo"] if apenas_ativos else list(itens)


def get_ativo(animal_uuid: str, tipo: str) -> Optional[dict]:
    """O identificador vigente de um tipo, se houver."""
    for i in _por_animal().get(animal_uuid, []):
        if i["tipo"] == tipo and i["status"] == "ativo":
            return i
    return None


def buscar_por_valor(tipo: str, valor: str) -> Optional[dict]:
    """Localiza o identificador ATIVO com esse valor — para detectar duplicidade.

    Só considera vigentes: o mesmo valor pode aparecer no histórico de outro
    animal (brinco reaproveitado após baixa), e isso não é conflito.
    """
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM animal_identifiers "
            "WHERE tipo=? AND valor=? AND status='ativo'", (tipo, valor)
        ).fetchone()
    return dict(row) if row else None


@_writes
def aplicar(animal_uuid: str, tipo: str, valor: str,
            aplicado_por: str = "", aplicado_em: Optional[str] = None) -> dict:
    """Vincula um identificador ao animal.

    Recusa se o valor já estiver ativo em OUTRO animal (§4.2.1 e §4.2.2) —
    devolver erro é melhor que deixar o índice único estourar, porque aqui dá
    para dizer em qual animal o valor está.
    """
    existente = buscar_por_valor(tipo, valor)
    if existente and existente["animal_uuid"] != animal_uuid:
        return {"ok": False,
                "erro": f"{tipo} '{valor}' já está ativo em outro animal",
                "animal_uuid": existente["animal_uuid"]}
    if existente:
        return {"ok": True, "id": existente["id"], "ja_existia": True}

    with _conn() as con:
        con.execute(
            "INSERT INTO animal_identifiers "
            "(animal_uuid,tipo,valor,status,aplicado_em,aplicado_por) "
            "VALUES(?,?,?,'ativo',?,?)",
            (animal_uuid, tipo, valor, aplicado_em or date.today().isoformat(),
             aplicado_por or None),
        )
    return {"ok": True, "ja_existia": False}


@_writes
def remover(animal_uuid: str, tipo: str, motivo: str,
            removido_em: Optional[str] = None) -> bool:
    """Encerra a vigência de um identificador — **não apaga** (§4.2.3).

    É o que permite reconstruir qual brinco o animal usava em cada data.
    """
    with _conn() as con:
        cur = con.execute(
            "UPDATE animal_identifiers SET status='removido', removido_em=?, "
            "motivo_remocao=? WHERE animal_uuid=? AND tipo=? AND status='ativo'",
            (removido_em or date.today().isoformat(), motivo, animal_uuid, tipo),
        )
    return (getattr(cur, "rowcount", 0) or 0) > 0


@_writes
def substituir(animal_uuid: str, tipo: str, valor_novo: str, motivo: str,
               aplicado_por: str = "") -> dict:
    """Troca de brinco: encerra o atual e aplica o novo, preservando o histórico.

    É a operação do §4.2.3 — e a razão de a identidade do animal ter deixado de
    ser o brinco. Antes do ADR 0004 isto exigiria trocar a chave primária.
    """
    remover(animal_uuid, tipo, motivo)
    return aplicar(animal_uuid, tipo, valor_novo, aplicado_por=aplicado_por)
