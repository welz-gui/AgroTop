"""Animais, movimentações entre lotes e o seed de demonstração.

Camada de dados (ROADMAP.md R1/R9): aqui mora o SQL, e só aqui.
Sem regra de negócio — cálculo e decisão ficam em `services/`.
Sem Streamlit no topo do módulo.
"""

import random
from datetime import date, timedelta
from typing import Optional

from .conexao import _cache, _conn, _writes


@_cache
def get_all_animals(status: Optional[str] = "ativo",
                    lote_id: Optional[str] = None,
                    breed: Optional[str] = None) -> list[dict]:
    sql  = "SELECT a.*, f.name as fornecedor_name FROM animals a LEFT JOIN fornecedores f ON f.id=a.fornecedor_id WHERE 1=1"
    args: list = []
    if status:
        sql += " AND a.status=?"; args.append(status)
    if lote_id:
        sql += " AND a.lote_id=?"; args.append(lote_id)
    if breed:
        sql += " AND a.breed=?"; args.append(breed)
    sql += " ORDER BY a.id"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def get_animal(animal_id: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            """SELECT a.*, f.name as fornecedor_name, l.name as lote_name
               FROM animals a
               LEFT JOIN fornecedores f ON f.id=a.fornecedor_id
               LEFT JOIN lotes l ON l.id=a.lote_id
               WHERE a.id=?""",
            (animal_id,),
        ).fetchone()
    return dict(row) if row else None


@_writes
def add_animal(animal_id, breed, sex, birth_date, entry_date,
               entry_weight, target_weight, purchase_price,
               lote_id, fornecedor_id, notes="",
               birth_estimated=0, age_source="propriedade",
               nf_number="", gta_number="", weight_method="pesado",
               purchase_mode="cabeca") -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO animals
               (id,breed,sex,birth_date,birth_estimated,age_source,nf_number,
                gta_number,entry_date,entry_weight,current_weight,target_weight,
                purchase_price,purchase_mode,lote_id,fornecedor_id,notes)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (animal_id, breed, sex, birth_date or None,
             int(birth_estimated), age_source,
             nf_number or None, gta_number or None, entry_date,
             entry_weight, entry_weight, target_weight, purchase_price,
             purchase_mode, lote_id or None, fornecedor_id or None, notes),
        )
        con.execute(
            "INSERT INTO weighings (animal_id,weight,weigh_date,lote_id,operator,method) VALUES(?,?,?,?,?,?)",
            (animal_id, entry_weight, entry_date, lote_id or None, "Cadastro", weight_method),
        )
        # Registra custo de compra apenas para animais adquiridos
        if age_source != "propriedade" and purchase_price and purchase_price > 0:
            con.execute(
                "INSERT INTO animal_costs (animal_id,cost_type,description,amount,cost_date) VALUES(?,?,?,?,?)",
                (animal_id, "compra", "Valor de compra", purchase_price, entry_date),
            )
        if lote_id:
            con.execute(
                "INSERT INTO animal_movements (animal_id,from_lote_id,to_lote_id,movement_date,reason,operator) VALUES(?,?,?,?,?,?)",
                (animal_id, None, lote_id, entry_date, "entrada", "Cadastro"),
            )


@_writes
def move_animal(animal_id, to_lote_id, movement_date, reason="manejo", operator="", notes="") -> None:
    with _conn() as con:
        row = con.execute("SELECT lote_id FROM animals WHERE id=?", (animal_id,)).fetchone()
        from_lote = row["lote_id"] if row else None
        con.execute(
            "UPDATE animals SET lote_id=? WHERE id=?", (to_lote_id, animal_id)
        )
        con.execute(
            """INSERT INTO animal_movements
               (animal_id,from_lote_id,to_lote_id,movement_date,reason,operator,notes)
               VALUES(?,?,?,?,?,?,?)""",
            (animal_id, from_lote, to_lote_id, movement_date, reason, operator, notes),
        )
        con.execute(
            "UPDATE lotes SET last_entry_date=? WHERE id=?", (movement_date, to_lote_id)
        )
        if from_lote:
            con.execute(
                "UPDATE lotes SET last_exit_date=? WHERE id=?", (movement_date, from_lote)
            )


def get_movements(animal_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT m.*, l1.name as from_name, l2.name as to_name
               FROM animal_movements m
               LEFT JOIN lotes l1 ON l1.id=m.from_lote_id
               LEFT JOIN lotes l2 ON l2.id=m.to_lote_id
               WHERE m.animal_id=? ORDER BY m.movement_date DESC""",
            (animal_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _seed_animals(con):
    if con.execute("SELECT COUNT(*) FROM animals").fetchone()[0]:
        return

    random.seed(7)
    today  = date.today()
    breeds = ["Nelore", "Angus", "Brahman", "Senepol", "Brangus", "Canchim"]
    lotes  = ["P01", "P01", "P01", "P02", "P02", "P03", "P03", "P03", "CRL"]

    for i in range(1, 15):
        aid          = f"BR{i:04d}"
        breed        = random.choice(breeds)
        sex          = random.choice(["M", "F"])
        days_in      = random.randint(60, 220)
        days_old     = random.randint(400, 900)
        birth_date   = (today - timedelta(days=days_old)).isoformat()
        entry_date   = (today - timedelta(days=days_in)).isoformat()
        e_weight     = round(random.uniform(220, 320), 1)
        c_weight     = round(e_weight + random.uniform(30, 110), 1)
        target_w     = round(random.uniform(480, 520), 1)
        lote_id      = random.choice(lotes)
        forn_id      = random.randint(1, 4)
        price        = round(e_weight * 0.52 / 15 * random.uniform(280, 320), 2)
        status       = "ativo"
        # Variedade de origens de idade para demonstração
        src, est = random.choice([
            ("propriedade", 0), ("propriedade", 0),
            ("nf_gta", 1), ("operador", 1), ("estimado", 1),
        ])
        # make 1 animal vendido and 1 morto for demo
        if i == 13: status = "vendido"
        if i == 14: status = "morto"

        con.execute(
            """INSERT INTO animals
               (id,breed,sex,birth_date,birth_estimated,age_source,entry_date,
                entry_weight,current_weight,target_weight,status,lote_id,
                fornecedor_id,purchase_price)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (aid, breed, sex, birth_date, est, src, entry_date, e_weight, c_weight,
             target_w, status, lote_id, forn_id, price),
        )

        # Pesagens: entrada, meio, recente
        for step, days_back in [(0.0, days_in), (0.5, days_in//2), (1.0, 0)]:
            w_date   = (today - timedelta(days=int(days_in * (1 - step)))).isoformat()
            w_weight = round(e_weight + (c_weight - e_weight) * step, 1)
            con.execute(
                "INSERT INTO weighings (animal_id,weight,weigh_date,lote_id,operator) VALUES(?,?,?,?,?)",
                (aid, w_weight, w_date, lote_id, "Sistema"),
            )

        # Medicamentos (1-2 por animal)
        meds_pool = [
            ("Ivermectina 1%",  "ml",  10, 21),
            ("Vacina FMD",      "dose", 2,  0),
            ("Closantel 10%",   "ml",  10, 28),
            ("Vitamina ADE",    "ml",  10,  0),
            ("Oxitetraciclina", "ml",  20, 14),
        ]
        for _ in range(random.randint(1, 2)):
            mn, mu, dose, wd = random.choice(meds_pool)
            md = (today - timedelta(days=random.randint(0, 60))).isoformat()
            con.execute(
                """INSERT INTO medications
                   (animal_id,medication_name,dose,unit,application_route,
                    withdrawal_days,med_date,applied_by)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (aid, mn, dose, mu, "Subcutânea", wd, md, "Sistema"),
            )

        # Custo de compra
        con.execute(
            "INSERT INTO animal_costs (animal_id,cost_type,description,amount,cost_date) VALUES(?,?,?,?,?)",
            (aid, "compra", "Valor de compra", price, entry_date),
        )
        # Custo operacional
        op_cost = round(days_in * 0.85, 2)
        con.execute(
            "INSERT INTO animal_costs (animal_id,cost_type,description,amount,cost_date) VALUES(?,?,?,?,?)",
            (aid, "operacional", "Custeio diário (pasto/água/mão de obra)", op_cost, today.isoformat()),
        )

        # Movimentação inicial para o lote
        con.execute(
            """INSERT INTO animal_movements
               (animal_id,from_lote_id,to_lote_id,movement_date,reason,operator)
               VALUES(?,?,?,?,?,?)""",
            (aid, None, lote_id, entry_date, "entrada", "Sistema"),
        )
