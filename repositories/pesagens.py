"""Pesagens e GMD recente.

`_weighings_by_animal` é bulk loader cacheado (ROADMAP R11): 1 consulta traz tudo,
o resto é leitura em memória. Não consultar por animal em laço.

Camada de dados (ROADMAP.md R1/R9): aqui mora o SQL, e só aqui.
Sem regra de negócio — cálculo e decisão ficam em `services/`.
Sem Streamlit no topo do módulo.
"""

from datetime import date
from typing import Optional

from . import eventos
from .conexao import _cache, _conn, _writes


@_cache
def _weighings_by_animal() -> dict:
    """Todas as pesagens agrupadas por animal (mais recente primeiro). 1 consulta.

    A ligação é por `animal_uuid` (ADR 0004, etapa B1.6), mas o dicionário
    continua indexado pelo **brinco**: é o que a interface usa e o que os
    chamadores esperam. O `JOIN` faz essa tradução numa consulta só.
    """
    with _conn() as con:
        rows = con.execute(
            """SELECT w.*, a.id AS animal_id
               FROM weighings w JOIN animals a ON a.uuid=w.animal_uuid
               ORDER BY w.weigh_date DESC, w.id DESC"""
        ).fetchall()
    out: dict = {}
    for r in rows:
        out.setdefault(r["animal_id"], []).append(dict(r))
    return out


def get_weighings(animal_id: str) -> list[dict]:
    return list(_weighings_by_animal().get(animal_id, []))


def get_weighings_batch(animal_ids: set[str]) -> dict[str, list[dict]]:
    """Busca pesagens apenas para os animais especificados numa única consulta."""
    if not animal_ids:
        return {}

    out: dict[str, list[dict]] = {}

    # Processa em lotes de 900 para evitar o limite de variáveis do SQLite
    animal_ids_list = list(animal_ids)
    batch_size = 900

    with _conn() as con:
        for i in range(0, len(animal_ids_list), batch_size):
            chunk = animal_ids_list[i:i + batch_size]
            placeholders = ",".join("?" * len(chunk))
            rows = con.execute(
                f"""SELECT w.*, a.id AS animal_id
                   FROM weighings w JOIN animals a ON a.uuid=w.animal_uuid
                   WHERE a.id IN ({placeholders})
                   ORDER BY w.weigh_date DESC, w.id DESC""", tuple(chunk)
            ).fetchall()

            for r in rows:
                out.setdefault(r["animal_id"], []).append(dict(r))

    return out


@_writes
def add_weighing(animal_id, weight, weigh_date, operator="", notes="",
                 method="pesado") -> None:
    with _conn() as con:
        # Busca lote e uuid na mesma consulta (ADR 0004 etapa B1.4).
        a = con.execute(
            "SELECT lote_id, uuid FROM animals WHERE id=?", (animal_id,)
        ).fetchone()
        if a is None:
            raise ValueError(f"Animal {animal_id} não encontrado.")
        con.execute(
            "INSERT INTO weighings (animal_uuid,weight,weigh_date,lote_id,operator,method,notes) VALUES(?,?,?,?,?,?,?)",
            (a["uuid"], weight, weigh_date, a["lote_id"], operator, method, notes),
        )
        con.execute("UPDATE animals SET current_weight=? WHERE id=?", (weight, animal_id))
        # Evento na MESMA transação da pesagem (§6): ou entram os dois, ou nenhum.
        eventos.registrar_em(
            con, a["uuid"], "pesagem", ocorrido_em=weigh_date,
            usuario_registro=operator, observacoes=f"{weight} kg ({method})")


def get_all_weighings() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT w.*, a.id AS animal_id, a.breed
               FROM weighings w JOIN animals a ON a.uuid=w.animal_uuid
               WHERE a.status='ativo' ORDER BY w.weigh_date""",
        ).fetchall()
    return [dict(r) for r in rows]


def calculate_gmd(animal_id: str) -> Optional[float]:
    """GMD recente: entre as duas últimas pesagens (como o animal está agora)."""
    ws = get_weighings(animal_id)
    if len(ws) < 2:
        return None
    try:
        d0 = date.fromisoformat(ws[0]["weigh_date"])
        d1 = date.fromisoformat(ws[1]["weigh_date"])
        days = abs((d0 - d1).days)
        return round((ws[0]["weight"] - ws[1]["weight"]) / days, 3) if days else None
    except (ValueError, KeyError):
        return None


def calculate_gmd_bulk(animal_ids: list[str]) -> dict[str, Optional[float]]:
    """
    GMD recente em massa. Retorna um dicionário {animal_id: GMD}.
    Evita chamadas repetitivas pegando o cache de uma vez e operando em memória.
    """
    all_ws = _weighings_by_animal()
    gmds = {}
    for aid in animal_ids:
        ws = all_ws.get(aid, [])
        if len(ws) < 2:
            gmds[aid] = None
            continue
        try:
            d0 = date.fromisoformat(ws[0]["weigh_date"])
            d1 = date.fromisoformat(ws[1]["weigh_date"])
            days = abs((d0 - d1).days)
            gmds[aid] = round((ws[0]["weight"] - ws[1]["weight"]) / days, 3) if days else None
        except (ValueError, KeyError, TypeError):
            gmds[aid] = None
    return gmds


def get_last_estimate(animal_id: str) -> Optional[dict]:
    """Retorna a pesagem estimada (operador ou medição) mais recente ainda não
    confirmada por uma pesagem real posterior. Usada para comparação."""
    ws = get_weighings(animal_id)  # já vem ordenado do mais recente ao mais antigo
    for w in ws:
        if w.get("method") in ("estimado", "medicao"):
            return w
        # se a mais recente já é 'pesado', não há estimativa pendente antes dela
        return None
    return None
