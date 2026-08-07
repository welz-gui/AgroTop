"""Pesagens e GMD recente.

`_weighings_by_animal` é bulk loader cacheado (ROADMAP R11): 1 consulta traz tudo,
o resto é leitura em memória. Não consultar por animal em laço.

Camada de dados (ROADMAP.md R1/R9): aqui mora o SQL, e só aqui.
Sem regra de negócio — cálculo e decisão ficam em `services/`.
Sem Streamlit no topo do módulo.
"""

from datetime import datetime
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
        d0 = datetime.strptime(ws[0]["weigh_date"], "%Y-%m-%d").date()
        d1 = datetime.strptime(ws[1]["weigh_date"], "%Y-%m-%d").date()
        days = abs((d0 - d1).days)
        return round((ws[0]["weight"] - ws[1]["weight"]) / days, 3) if days else None
    except (ValueError, KeyError):
        return None


def calculate_gmd_batch(animal_ids: list[str]) -> dict[str, Optional[float]]:
    """Calcula o GMD recente em lote, usando os dados cacheados em memória.
    Retorna um dicionário mapeando animal_id para o valor de GMD (float ou None)."""
    import pandas as pd

    ws_all = _weighings_by_animal()
    gmd_records = []

    for aid in animal_ids:
        ws = ws_all.get(aid, [])
        if len(ws) >= 2:
            try:
                gmd_records.append({
                    'id': aid,
                    'w0': ws[0]['weight'],
                    'w1': ws[1]['weight'],
                    'd0': ws[0]['weigh_date'],
                    'd1': ws[1]['weigh_date']
                })
            except KeyError:
                pass

    if not gmd_records:
        return {aid: None for aid in animal_ids}

    df = pd.DataFrame(gmd_records)
    df['d0'] = pd.to_datetime(df['d0'])
    df['d1'] = pd.to_datetime(df['d1'])
    df['days'] = (df['d0'] - df['d1']).dt.days.abs()

    mask = df['days'] > 0
    df.loc[mask, 'GMD'] = ((df.loc[mask, 'w0'] - df.loc[mask, 'w1']) / df.loc[mask, 'days']).round(3)

    gmd_dict = df.set_index('id')['GMD'].where(pd.notna(df.set_index('id')['GMD']), None).to_dict()

    # Preencher com None para animais que não têm pesagens suficientes
    return {aid: gmd_dict.get(aid) for aid in animal_ids}


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
