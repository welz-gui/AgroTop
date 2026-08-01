"""Medicamentos, protocolos sanitários e carência.

Camada de dados (ROADMAP.md R1/R9): aqui mora o SQL, e só aqui.
Sem regra de negócio — cálculo e decisão ficam em `services/`.
Sem Streamlit no topo do módulo.
"""

from datetime import date, datetime, timedelta
from typing import Optional

from .animais import get_all_animals
from .animais import uuid_de
from .conexao import _cache, _conn, _writes


@_cache
def _medications_by_animal() -> dict:
    """Todos os medicamentos agrupados por animal (mais recente primeiro). 1 consulta."""
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM medications ORDER BY med_date DESC, id DESC"
        ).fetchall()
    out: dict = {}
    for r in rows:
        out.setdefault(r["animal_id"], []).append(dict(r))
    return out


def get_medications(animal_id: str) -> list[dict]:
    return list(_medications_by_animal().get(animal_id, []))


@_writes
def add_medication(animal_id, medication_name, dose, unit, application_route,
                   withdrawal_days, med_date, applied_by="",
                   insumo_id=None, notes="", protocol_id=None) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO medications
               (animal_id,animal_uuid,medication_name,dose,unit,application_route,
                withdrawal_days,med_date,applied_by,insumo_id,notes,protocol_id)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (animal_id, uuid_de(con, animal_id), medication_name, dose, unit,
             application_route,
             withdrawal_days, med_date, applied_by, insumo_id or None, notes,
             protocol_id or None),
        )
        # Baixa automática no estoque
        if insumo_id and dose > 0:
            con.execute(
                "UPDATE insumos SET current_stock = MAX(0, current_stock - ?) WHERE id=?",
                (dose, insumo_id),
            )
            con.execute(
                """INSERT INTO insumo_transactions
                   (insumo_id,type,quantity,reason,animal_id,transaction_date,operator)
                   VALUES(?,?,?,?,?,?,?)""",
                (insumo_id, "saida", dose, "uso_animal", animal_id, med_date, applied_by),
            )
        # Atualiza status do animal se há carência
        if withdrawal_days and withdrawal_days > 0:
            con.execute(
                "UPDATE animals SET status='carencia' WHERE id=? AND status='ativo'",
                (animal_id,),
            )


def get_withdrawal_end(animal_id: str) -> Optional[date]:
    """Retorna a maior data de fim de carência ativa do animal, ou None."""
    rows = _medications_by_animal().get(animal_id, [])
    latest = None
    for r in rows:
        if not r["withdrawal_days"]:
            continue
        try:
            end = datetime.strptime(r["med_date"], "%Y-%m-%d").date() + timedelta(days=r["withdrawal_days"])
            if end > date.today() and (latest is None or end > latest):
                latest = end
        except ValueError:
            pass
    return latest


def get_protocols(active_only: bool = True) -> list[dict]:
    sql = ("SELECT p.*, i.name AS insumo_name, i.current_stock, i.unit AS insumo_unit "
           "FROM health_protocols p LEFT JOIN insumos i ON i.id=p.insumo_id WHERE 1=1")
    if active_only:
        sql += " AND p.active=1"
    sql += " ORDER BY p.name"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql).fetchall()]


@_writes
def add_protocol(name, sex_target, age_min, age_max, dose_value, dose_ref_kg,
                 dose_unit, insumo_id, frequency, withdrawal_days,
                 route="Subcutânea", notes="") -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO health_protocols
               (name,sex_target,age_min,age_max,dose_value,dose_ref_kg,dose_unit,
                insumo_id,frequency,withdrawal_days,route,notes)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (name, sex_target, int(age_min), int(age_max), dose_value, dose_ref_kg,
             dose_unit, insumo_id or None, frequency, int(withdrawal_days), route, notes),
        )


@_writes
def set_protocol_active(pid: int, active: int) -> None:
    with _conn() as con:
        con.execute("UPDATE health_protocols SET active=? WHERE id=?", (int(active), pid))


@_writes
def delete_protocol(pid: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM health_protocols WHERE id=?", (pid,))


def _protocol_pending(protocol: dict, animal: dict, ref_date: date) -> bool:
    """True se o animal ainda precisa da aplicação no ciclo atual."""
    freq = protocol.get("frequency", "anual")
    aplicadas = [m for m in get_medications(animal["id"])
                 if m.get("protocol_id") == protocol["id"]]
    if not aplicadas:
        return True
    if freq == "unica":
        return False
    try:
        ultima = datetime.strptime(aplicadas[0]["med_date"], "%Y-%m-%d").date()
    except (ValueError, TypeError, KeyError):
        return True
    return (ref_date - ultima).days >= _FREQ_DAYS.get(freq, 365)


def get_protocol_plan(protocol: dict, ref_date: Optional[date] = None) -> dict:
    """Elegíveis, pendentes, doses necessárias e projeção de estoque."""
    ref = ref_date or date.today()
    animals = get_all_animals()
    elegiveis, pendentes = [], []
    idade_desconhecida = 0
    for a in animals:
        if get_age_months(a.get("birth_date")) is None:
            stt = protocol.get("sex_target", "ambos")
            if stt == "ambos" or a["sex"] == stt:
                idade_desconhecida += 1
            continue
        if not _protocol_eligible(protocol, a):
            continue
        elegiveis.append(a)
        if _protocol_pending(protocol, a, ref):
            pendentes.append(a)
    doses = round(sum(_dose_for_animal(protocol, a) for a in pendentes), 2)
    stock = float(protocol.get("current_stock") or 0)
    return {
        "n_eligible": len(elegiveis),
        "n_pending":  len(pendentes),
        "pending":    pendentes,
        "doses_needed": doses,
        "stock":      round(stock, 2),
        "shortfall":  round(max(0.0, doses - stock), 2),
        "idade_desconhecida": idade_desconhecida,
    }


@_writes
def apply_protocol_campaign(protocol_id: int, med_date: str, operator: str = "") -> dict:
    """Aplica o protocolo a todos os animais pendentes (registra + baixa estoque)."""
    prot = next((p for p in get_protocols(active_only=False) if p["id"] == protocol_id), None)
    if not prot:
        return {"n": 0, "doses": 0}
    try:
        ref = datetime.strptime(med_date, "%Y-%m-%d").date()
    except ValueError:
        ref = date.today()
    plan = get_protocol_plan(prot, ref)
    n = 0
    for a in plan["pending"]:
        dose = _dose_for_animal(prot, a)
        add_medication(a["id"], prot["name"], dose, prot["dose_unit"],
                       prot.get("route", "Subcutânea"), prot.get("withdrawal_days", 0),
                       med_date, applied_by=operator, insumo_id=prot.get("insumo_id"),
                       notes="Campanha sanitária", protocol_id=prot["id"])
        n += 1
    return {"n": n, "doses": plan["doses_needed"]}


def _dose_for_animal(protocol: dict, animal: dict) -> float:
    """Dose para um animal: fixa, ou proporcional ao peso (dose_ref_kg > 0)."""
    ref = protocol.get("dose_ref_kg") or 0
    if ref > 0:
        return round(animal["current_weight"] / ref * protocol["dose_value"], 2)
    return round(protocol["dose_value"], 2)
