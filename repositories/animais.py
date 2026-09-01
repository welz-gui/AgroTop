"""Animais, movimentações entre lotes e o seed de demonstração.

Camada de dados (ROADMAP.md R1/R9): aqui mora o SQL, e só aqui.
Sem regra de negócio — cálculo e decisão ficam em `services/`.
Sem Streamlit no topo do módulo.
"""

import random
import uuid as _uuid
from datetime import date, timedelta
from typing import Optional

from . import eventos
from .conexao import _cache, _conn, _writes


def uuid_de(con, animal_id: str) -> str | None:
    """UUID interno a partir do número do brinco (ADR 0004, etapa B1.4).

    Usado nas escritas das tabelas filhas enquanto `animal_id` ainda é o que
    chega da interface. Some na etapa 6, quando as funções passarem a receber o
    uuid direto.
    """
    if not animal_id:
        return None
    row = con.execute("SELECT uuid FROM animals WHERE id=?", (animal_id,)).fetchone()
    return row["uuid"] if row else None


def novo_uuid() -> str:
    """Identificador interno imutável de um animal (ADR 0004, §4.1 do PNIB).

    Gerado em Python, e não pelo banco, porque o `gen_random_uuid()` do Postgres
    não existe no SQLite — e a compatibilidade dupla é requisito do projeto.
    """
    return str(_uuid.uuid4())


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
               purchase_mode="cabeca", property_id=None) -> None:
    _uuid_novo = novo_uuid()
    with _conn() as con:
        # ADR 0004 · B4: o animal nasce numa propriedade (§3.4). Sem escolha
        # explícita, herda a do piquete; sem piquete, a propriedade padrão.
        # É o que permite a B4.3 exigir a coluna depois.
        if property_id is None and lote_id:
            r = con.execute(
                "SELECT property_id FROM lotes WHERE id=?", (lote_id,)).fetchone()
            property_id = r["property_id"] if r else None
        if property_id is None:
            r = con.execute(
                "SELECT id FROM properties ORDER BY created_at LIMIT 1").fetchone()
            property_id = r["id"] if r else None

        con.execute(
            """INSERT INTO animals
               (id,uuid,breed,sex,birth_date,birth_estimated,age_source,nf_number,
                gta_number,entry_date,entry_weight,current_weight,target_weight,
                purchase_price,purchase_mode,lote_id,property_id,fornecedor_id,notes)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (animal_id, _uuid_novo, breed, sex, birth_date or None,
             int(birth_estimated), age_source,
             nf_number or None, gta_number or None, entry_date,
             entry_weight, entry_weight, target_weight, purchase_price,
             purchase_mode, lote_id or None, property_id,
             fornecedor_id or None, notes),
        )
        con.execute(
            "INSERT INTO weighings (animal_uuid,weight,weigh_date,lote_id,operator,method) VALUES(?,?,?,?,?,?)",
            (_uuid_novo, entry_weight, entry_date, lote_id or None,
             "Cadastro", weight_method),
        )
        # Registra custo de compra apenas para animais adquiridos
        if age_source != "propriedade" and purchase_price and purchase_price > 0:
            con.execute(
                "INSERT INTO animal_costs (animal_uuid,cost_type,description,amount,cost_date) VALUES(?,?,?,?,?)",
                (_uuid_novo, "compra", "Valor de compra", purchase_price,
                 entry_date),
            )
        if lote_id:
            con.execute(
                "INSERT INTO animal_movements (animal_uuid,from_lote_id,to_lote_id,movement_date,reason,operator) VALUES(?,?,?,?,?,?)",
                (_uuid_novo, None, lote_id, entry_date, "entrada", "Cadastro"),
            )
        eventos.registrar_em(con, _uuid_novo, "cadastro_inicial",
                             ocorrido_em=entry_date,
                             observacoes=f"{breed}, {entry_weight} kg")
        eventos.registrar_em(con, _uuid_novo, "identificacao_interna",
                             ocorrido_em=entry_date,
                             observacoes=f"brinco {animal_id}")


def _mover_animal_em(con, animal_id, to_lote_id, movement_date, reason, operator, notes) -> None:
    """O que `move_animal` faz, mas recebendo a conexão de fora — para
    `move_animals_bulk` mover várias cabeças na mesma transação, em vez de
    uma conexão por animal (R8: mesma regra, um lugar só)."""
    row = con.execute("SELECT lote_id, uuid FROM animals WHERE id=?", (animal_id,)).fetchone()
    if row is None:
        raise ValueError(f"Animal {animal_id} não encontrado.")
    from_lote = row["lote_id"]
    # Mudar de piquete pode mudar de propriedade — a B6 vai tratar isso como
    # evento regulatório de trânsito. Por ora o animal acompanha o piquete.
    destino = con.execute(
        "SELECT property_id FROM lotes WHERE id=?", (to_lote_id,)).fetchone()
    con.execute(
        "UPDATE animals SET lote_id=?, property_id=COALESCE(?, property_id) "
        "WHERE id=?",
        (to_lote_id, destino["property_id"] if destino else None, animal_id)
    )
    con.execute(
        """INSERT INTO animal_movements
           (animal_uuid,from_lote_id,to_lote_id,movement_date,reason,
            operator,notes)
           VALUES(?,?,?,?,?,?,?)""",
        (row["uuid"], from_lote, to_lote_id,
         movement_date, reason, operator, notes),
    )
    eventos.registrar_em(
        con, row["uuid"], "mudanca_lote", ocorrido_em=movement_date,
        usuario_registro=operator, local_interno=to_lote_id,
        observacoes=f"{from_lote or '—'} → {to_lote_id} ({reason})")
    con.execute(
        "UPDATE lotes SET last_entry_date=? WHERE id=?", (movement_date, to_lote_id)
    )
    if from_lote:
        con.execute(
            "UPDATE lotes SET last_exit_date=? WHERE id=?", (movement_date, from_lote)
        )


@_writes
def move_animal(animal_id, to_lote_id, movement_date, reason="manejo", operator="", notes="") -> None:
    with _conn() as con:
        _mover_animal_em(con, animal_id, to_lote_id, movement_date, reason, operator, notes)


@_writes
def move_animals_bulk(animal_ids: list, to_lote_id, movement_date, reason="manejo",
                      operator="", notes="") -> dict:
    """Transfere várias cabeças para o mesmo piquete de destino, na mesma
    transação — a versão em lote de `move_animal` (transferência entre
    piquetes, ROADMAP §5, Trilha 3). Sem isso, mover um piquete inteiro
    exigia abrir a ficha de cada animal, um de cada vez.

    Animal que já está no piquete de destino é pulado (não é erro: apenas
    não gera um evento de mudança de piquete que não mudou nada).
    """
    movidos, ja_no_destino, erros = [], [], []
    animal_states = {}
    with _conn() as con:
        chunk_size = 900
        for i in range(0, len(animal_ids), chunk_size):
            chunk = animal_ids[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            rows = con.execute(f"SELECT id, lote_id FROM animals WHERE id IN ({placeholders})", chunk).fetchall()
            for row in rows:
                animal_states[row["id"]] = row["lote_id"]

        for animal_id in animal_ids:
            if animal_id not in animal_states:
                erros.append(animal_id)
                continue
            if animal_states[animal_id] == to_lote_id:
                ja_no_destino.append(animal_id)
                continue
            _mover_animal_em(con, animal_id, to_lote_id, movement_date, reason,
                            operator, notes)
            movidos.append(animal_id)
    return {"movidos": movidos, "ja_no_destino": ja_no_destino, "erros": erros}


def get_movements(animal_id: str, limit: Optional[int] = None) -> list[dict]:
    with _conn() as con:
        sql = """SELECT m.*, l1.name as from_name, l2.name as to_name
               FROM animal_movements m
               LEFT JOIN lotes l1 ON l1.id=m.from_lote_id
               LEFT JOIN lotes l2 ON l2.id=m.to_lote_id
               JOIN animals a ON a.uuid=m.animal_uuid
               WHERE a.id=? ORDER BY m.movement_date DESC"""
        args = [animal_id]
        if limit is not None:
            sql += " LIMIT ?"
            args.append(limit)

        rows = con.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def get_last_movements_bulk(animal_ids: list[str]) -> dict[str, str]:
    if not animal_ids:
        return {}

    last_movements = {}
    with _conn() as con:
        # SQLite limit is typically 999 parameters. Batch by 900.
        for i in range(0, len(animal_ids), 900):
            batch = animal_ids[i:i+900]
            placeholders = ",".join("?" for _ in batch)
            sql = f"""
                SELECT a.id as animal_id, MAX(m.movement_date) as last_movement_date
                FROM animals a
                LEFT JOIN animal_movements m ON a.uuid = m.animal_uuid
                WHERE a.id IN ({placeholders})
                GROUP BY a.id
            """
            rows = con.execute(sql, batch).fetchall()
            for r in rows:
                if r["last_movement_date"]:
                    last_movements[r["animal_id"]] = r["last_movement_date"]
    return last_movements


def _seed_animals(con, property_id: str = None):
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

        # O uuid é gerado AQUI, e não deixado para o backfill: depois da etapa
        # B1.6 as filhas só têm `animal_uuid`, então uma linha semeada sem uuid
        # ficaria órfã sem nada de onde reconstruí-la.
        a_uuid = novo_uuid()
        con.execute(
            """INSERT INTO animals
               (id,uuid,breed,sex,birth_date,birth_estimated,age_source,entry_date,
                entry_weight,current_weight,target_weight,status,lote_id,
                fornecedor_id,purchase_price,property_id)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (aid, a_uuid, breed, sex, birth_date, est, src, entry_date, e_weight,
             c_weight, target_w, status, lote_id, forn_id, price, property_id),
        )

        # Pesagens: entrada, meio, recente
        for step, days_back in [(0.0, days_in), (0.5, days_in//2), (1.0, 0)]:
            w_date   = (today - timedelta(days=int(days_in * (1 - step)))).isoformat()
            w_weight = round(e_weight + (c_weight - e_weight) * step, 1)
            con.execute(
                "INSERT INTO weighings (animal_uuid,weight,weigh_date,lote_id,operator) VALUES(?,?,?,?,?)",
                (a_uuid, w_weight, w_date, lote_id, "Sistema"),
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
                   (animal_uuid,medication_name,dose,unit,application_route,
                    withdrawal_days,med_date,applied_by)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (a_uuid, mn, dose, mu, "Subcutânea", wd, md, "Sistema"),
            )

        # Custo de compra
        con.execute(
            "INSERT INTO animal_costs (animal_uuid,cost_type,description,amount,cost_date) VALUES(?,?,?,?,?)",
            (a_uuid, "compra", "Valor de compra", price, entry_date),
        )
        # Custo operacional
        op_cost = round(days_in * 0.85, 2)
        con.execute(
            "INSERT INTO animal_costs (animal_uuid,cost_type,description,amount,cost_date) VALUES(?,?,?,?,?)",
            (a_uuid, "operacional", "Custeio diário (pasto/água/mão de obra)", op_cost, today.isoformat()),
        )

        # Movimentação inicial para o lote
        con.execute(
            """INSERT INTO animal_movements
               (animal_uuid,from_lote_id,to_lote_id,movement_date,reason,operator)
               VALUES(?,?,?,?,?,?)""",
            (a_uuid, None, lote_id, entry_date, "entrada", "Sistema"),
        )
