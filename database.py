"""
AgroTop — Camada de acesso ao banco de dados.
Funciona com SQLite (local) ou PostgreSQL/Supabase (nuvem), conforme a
variável de ambiente/segredo DATABASE_URL. Schema completo: animais,
pesagens, medicamentos, lotes, movimentações, insumos, custos, nutrição.
"""

import os
import sqlite3
import hashlib
import random
from datetime import datetime, date, timedelta
from contextlib import contextmanager
from typing import Optional

DB_PATH       = "agrotop.db"
CARCASS_YIELD = 0.52    # rendimento de carcaça padrão (52 %)
KG_PER_ARROBA = 15.0    # kg por arroba
UA_WEIGHT     = 450.0   # kg por Unidade Animal padrão

# ─── Seleção de backend (SQLite local x Postgres/Supabase nuvem) ─────────────

def _database_url() -> str:
    """Lê a URL do Postgres de env var ou dos segredos do Streamlit."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("DATABASE_URL", "")  # type: ignore
        except Exception:
            url = ""
    return url or ""

DATABASE_URL = _database_url()
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2
    import psycopg2.extras
    IntegrityError = psycopg2.IntegrityError
else:
    IntegrityError = sqlite3.IntegrityError


def _translate(sql: str) -> str:
    """Adapta SQL escrito para SQLite ao dialeto Postgres."""
    if not USE_PG:
        return sql
    sql = sql.replace("?", "%s")
    sql = sql.replace("MAX(0,", "GREATEST(0,")
    return sql


class _PGConn:
    """Adaptador para que o código escrito para sqlite3 (con.execute(...).fetchone())
    funcione igual com psycopg2. Usa DictCursor (suporta row[0] e row['col'])."""
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        cur = self.raw.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(_translate(sql), params)
        return cur

    def executescript(self, sql):
        cur = self.raw.cursor()
        cur.execute(sql)
        cur.close()

    def commit(self):   self.raw.commit()
    def rollback(self): self.raw.rollback()
    def close(self):    self.raw.close()

# ─── Conexão ──────────────────────────────────────────────────────────────────

@contextmanager
def _conn():
    if USE_PG:
        con = _PGConn(psycopg2.connect(DATABASE_URL))
    else:
        con = sqlite3.connect(DB_PATH, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

# ─── Cache (reduz consultas repetidas; essencial na nuvem) ───────────────────
# Estratégia: carregamento em lote. A 1ª chamada busca TODOS os registros de
# uma vez; as demais são leituras em memória. clear_cache() é chamado após
# qualquer gravação, para o usuário ver a alteração imediatamente.
try:
    import streamlit as _st

    def _cache(fn):
        return _st.cache_data(ttl=120, show_spinner=False)(fn)

    def clear_cache() -> None:
        try:
            _st.cache_data.clear()
        except Exception:
            pass
except Exception:
    def _cache(fn):
        return fn

    def clear_cache() -> None:
        pass


def _writes(fn):
    """Decorador para funções de gravação: limpa o cache após executar,
    garantindo que a próxima leitura reflita a alteração imediatamente."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        clear_cache()
        return result
    return wrapper


@_cache
def _weighings_by_animal() -> dict:
    """Todas as pesagens agrupadas por animal (mais recente primeiro). 1 consulta."""
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM weighings ORDER BY weigh_date DESC, id DESC"
        ).fetchall()
    out: dict = {}
    for r in rows:
        out.setdefault(r["animal_id"], []).append(dict(r))
    return out


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


@_cache
def _costs_by_animal() -> dict:
    """Soma de custos por animal. 1 consulta."""
    with _conn() as con:
        rows = con.execute(
            "SELECT animal_id, COALESCE(SUM(amount),0) AS total FROM animal_costs GROUP BY animal_id"
        ).fetchall()
    return {r["animal_id"]: round(float(r["total"]), 2) for r in rows}

# ─── Inicialização ────────────────────────────────────────────────────────────

def init_db() -> None:
    with _conn() as con:
        if not USE_PG:
            con.executescript("""
            -- Usuários
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                name          TEXT    NOT NULL,
                role          TEXT    NOT NULL DEFAULT 'operator'
            );

            -- Fornecedores / Origem
            CREATE TABLE IF NOT EXISTS fornecedores (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                city       TEXT,
                state      TEXT DEFAULT 'MT',
                contact    TEXT,
                notes      TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            -- Lotes / Piquetes
            CREATE TABLE IF NOT EXISTS lotes (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                area_ha         REAL DEFAULT 0,
                capacity_ua     REAL DEFAULT 0,
                status          TEXT DEFAULT 'ativo',
                last_entry_date TEXT,
                last_exit_date  TEXT,
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now','localtime'))
            );

            -- Animais
            CREATE TABLE IF NOT EXISTS animals (
                id               TEXT PRIMARY KEY,
                breed            TEXT NOT NULL,
                sex              TEXT NOT NULL DEFAULT 'M',
                birth_date       TEXT,
                birth_estimated  INTEGER DEFAULT 0,
                age_source       TEXT DEFAULT 'propriedade',
                nf_number        TEXT,
                gta_number       TEXT,
                entry_date       TEXT NOT NULL,
                entry_weight     REAL NOT NULL,
                current_weight   REAL NOT NULL,
                target_weight    REAL DEFAULT 500,
                status           TEXT NOT NULL DEFAULT 'ativo',
                lote_id          TEXT,
                fornecedor_id    INTEGER,
                purchase_price   REAL DEFAULT 0,
                carcass_yield    REAL DEFAULT 0.52,
                notes            TEXT,
                created_at       TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (lote_id)       REFERENCES lotes(id),
                FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id)
            );

            -- Pesagens
            CREATE TABLE IF NOT EXISTS weighings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_id   TEXT NOT NULL,
                weight      REAL NOT NULL,
                weigh_date  TEXT NOT NULL,
                lote_id     TEXT,
                operator    TEXT,
                method      TEXT DEFAULT 'pesado',
                notes       TEXT,
                created_at  TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (animal_id) REFERENCES animals(id)
            );

            -- Insumos (estoque)
            CREATE TABLE IF NOT EXISTS insumos (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                category      TEXT NOT NULL DEFAULT 'medicamento',
                unit          TEXT NOT NULL DEFAULT 'ml',
                current_stock REAL NOT NULL DEFAULT 0,
                min_stock     REAL NOT NULL DEFAULT 0,
                cost_per_unit REAL DEFAULT 0,
                supplier      TEXT,
                notes         TEXT,
                created_at    TEXT DEFAULT (datetime('now','localtime'))
            );

            -- Medicamentos / Vacinas aplicados
            CREATE TABLE IF NOT EXISTS medications (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_id         TEXT NOT NULL,
                medication_name   TEXT NOT NULL,
                dose              REAL DEFAULT 0,
                unit              TEXT DEFAULT 'ml',
                application_route TEXT DEFAULT 'Subcutânea',
                withdrawal_days   INTEGER DEFAULT 0,
                med_date          TEXT NOT NULL,
                applied_by        TEXT,
                insumo_id         INTEGER,
                notes             TEXT,
                created_at        TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (animal_id) REFERENCES animals(id),
                FOREIGN KEY (insumo_id) REFERENCES insumos(id)
            );

            -- Movimentações entre lotes
            CREATE TABLE IF NOT EXISTS animal_movements (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_id     TEXT NOT NULL,
                from_lote_id  TEXT,
                to_lote_id    TEXT NOT NULL,
                movement_date TEXT NOT NULL,
                reason        TEXT DEFAULT 'manejo',
                operator      TEXT,
                notes         TEXT,
                created_at    TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (animal_id) REFERENCES animals(id)
            );

            -- Transações de estoque de insumos
            CREATE TABLE IF NOT EXISTS insumo_transactions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                insumo_id        INTEGER NOT NULL,
                type             TEXT NOT NULL,
                quantity         REAL NOT NULL,
                reason           TEXT,
                animal_id        TEXT,
                transaction_date TEXT NOT NULL,
                operator         TEXT,
                notes            TEXT,
                created_at       TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (insumo_id) REFERENCES insumos(id)
            );

            -- Custos por animal
            CREATE TABLE IF NOT EXISTS animal_costs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_id   TEXT NOT NULL,
                cost_type   TEXT NOT NULL DEFAULT 'operacional',
                description TEXT,
                amount      REAL NOT NULL,
                cost_date   TEXT NOT NULL,
                notes       TEXT,
                created_at  TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (animal_id) REFERENCES animals(id)
            );

            -- Custos fixos (nível da fazenda: aluguel, salários, impostos, taxas)
            CREATE TABLE IF NOT EXISTS fixed_costs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category    TEXT NOT NULL DEFAULT 'outro',
                description TEXT,
                amount      REAL NOT NULL,
                cost_date   TEXT NOT NULL,
                recurring   INTEGER DEFAULT 0,
                notes       TEXT,
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            );

            -- Programação de trato/ração/mineral por piquete
            CREATE TABLE IF NOT EXISTS feeding_plans (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                lote_id      TEXT NOT NULL,
                product_name TEXT NOT NULL,
                insumo_id    INTEGER,
                quantity     REAL NOT NULL DEFAULT 0,
                unit         TEXT NOT NULL DEFAULT 'kg',
                frequency    TEXT NOT NULL DEFAULT 'diario',
                active       INTEGER DEFAULT 1,
                notes        TEXT,
                created_at   TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (lote_id)   REFERENCES lotes(id),
                FOREIGN KEY (insumo_id) REFERENCES insumos(id)
            );

            -- Checagens de execução do trato (operador confirma)
            CREATE TABLE IF NOT EXISTS feeding_checks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id         INTEGER,
                lote_id         TEXT NOT NULL,
                check_date      TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'feito',
                actual_quantity REAL,
                operator        TEXT,
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (plan_id) REFERENCES feeding_plans(id),
                FOREIGN KEY (lote_id) REFERENCES lotes(id)
            );

            -- Preços esperados por categoria (idade x sexo) — apenas por kg
            CREATE TABLE IF NOT EXISTS category_prices (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                age_band       TEXT NOT NULL,
                sex            TEXT NOT NULL,
                price_per_kg   REAL DEFAULT 0,
                price_per_head REAL DEFAULT 0,
                updated_at     TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE (age_band, sex)
            );

            -- Vendas (1 linha por animal; lote agrupado por lot_ref)
            CREATE TABLE IF NOT EXISTS sales (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_id    TEXT NOT NULL,
                sale_date    TEXT NOT NULL,
                sale_type    TEXT NOT NULL DEFAULT 'abate',
                pricing_mode TEXT NOT NULL DEFAULT 'kg',
                weight_kg    REAL,
                price_per_kg REAL,
                total_value  REAL NOT NULL DEFAULT 0,
                buyer        TEXT,
                lot_ref      TEXT,
                cost_at_sale REAL DEFAULT 0,
                profit       REAL DEFAULT 0,
                operator     TEXT,
                notes        TEXT,
                created_at   TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (animal_id) REFERENCES animals(id)
            );
        """)
        _migrate(con)
        _seed_users(con)
        _seed_fornecedores(con)
        _seed_lotes(con)
        _seed_animals(con)
        _seed_insumos(con)


def _migrate(con) -> None:
    """Adiciona colunas novas a bancos SQLite criados por versões anteriores.
    No Postgres o schema já vem completo pela migração."""
    if USE_PG:
        return
    cols = {r["name"] for r in con.execute("PRAGMA table_info(animals)").fetchall()}
    if "birth_estimated" not in cols:
        con.execute("ALTER TABLE animals ADD COLUMN birth_estimated INTEGER DEFAULT 0")
    if "age_source" not in cols:
        con.execute("ALTER TABLE animals ADD COLUMN age_source TEXT DEFAULT 'propriedade'")
    if "nf_number" not in cols:
        con.execute("ALTER TABLE animals ADD COLUMN nf_number TEXT")
    if "gta_number" not in cols:
        con.execute("ALTER TABLE animals ADD COLUMN gta_number TEXT")
    if "purchase_mode" not in cols:
        con.execute("ALTER TABLE animals ADD COLUMN purchase_mode TEXT DEFAULT 'cabeca'")
    if "purchase_lot_ref" not in cols:
        con.execute("ALTER TABLE animals ADD COLUMN purchase_lot_ref TEXT")
    wcols = {r["name"] for r in con.execute("PRAGMA table_info(weighings)").fetchall()}
    if "method" not in wcols:
        con.execute("ALTER TABLE weighings ADD COLUMN method TEXT DEFAULT 'pesado'")

# ─── Seeds ────────────────────────────────────────────────────────────────────

def _seed_users(con):
    for u, p, n, r in [
        ("admin", "admin123", "Administrador",  "admin"),
        ("op1",   "op1234",   "Operador Campo", "operator"),
    ]:
        existe = con.execute("SELECT 1 FROM users WHERE username=?", (u,)).fetchone()
        if existe:
            continue
        con.execute(
            "INSERT INTO users (username,password_hash,name,role) VALUES(?,?,?,?)",
            (u, _hash(p), n, r),
        )


def _seed_fornecedores(con):
    if con.execute("SELECT COUNT(*) FROM fornecedores").fetchone()[0]:
        return
    for name, city, state in [
        ("Fazenda Santa Fé",   "Cuiabá",       "MT"),
        ("Agro Pantanal Ltda", "Corumbá",      "MS"),
        ("Rancho Verde",       "Uberlândia",   "MG"),
        ("Estância Boa Vista", "Campo Grande", "MS"),
    ]:
        con.execute(
            "INSERT INTO fornecedores (name,city,state) VALUES(?,?,?)",
            (name, city, state),
        )


def _seed_lotes(con):
    if con.execute("SELECT COUNT(*) FROM lotes").fetchone()[0]:
        return
    for lid, name, area, cap, status in [
        ("P01", "Piquete Central",   15.0, 25.0, "ativo"),
        ("P02", "Piquete Norte",     12.0, 20.0, "ativo"),
        ("P03", "Piquete Sul",       18.0, 30.0, "ativo"),
        ("P04", "Piquete Leste",     10.0, 15.0, "descanso"),
        ("CRL", "Curral Principal",   0.5,  0.0, "ativo"),
    ]:
        con.execute(
            "INSERT INTO lotes (id,name,area_ha,capacity_ua,status) VALUES(?,?,?,?,?)",
            (lid, name, area, cap, status),
        )


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


def _seed_insumos(con):
    if con.execute("SELECT COUNT(*) FROM insumos").fetchone()[0]:
        return
    items = [
        ("Ivermectina 1%",   "medicamento", "ml",    800.0, 100.0, 0.15),
        ("Vacina FMD",       "vacina",      "dose",  150.0,  30.0, 3.50),
        ("Closantel 10%",    "medicamento", "ml",    400.0,  80.0, 0.28),
        ("Vitamina ADE",     "medicamento", "ml",    500.0,  80.0, 0.09),
        ("Oxitetraciclina",  "medicamento", "ml",     80.0,  50.0, 0.45),
        ("Sal Mineral",      "mineral",     "kg",   1200.0, 200.0, 4.80),
        ("Ração Engorda",    "racao",       "kg",   4500.0, 800.0, 1.25),
        ("Vermífugo Oral",   "medicamento", "ml",     45.0,  60.0, 0.35),
        ("Silagem de Milho", "trato",       "ton",    85.0,  15.0, 320.00),
        ("Massa de Soja",    "trato",       "ton",    12.0,   5.0, 1150.00),
        ("Bagaço de Laranja","trato",       "ton",    30.0,   8.0, 180.00),
    ]
    for name, cat, unit, stock, min_s, cpu in items:
        con.execute(
            """INSERT INTO insumos (name,category,unit,current_stock,min_stock,cost_per_unit)
               VALUES(?,?,?,?,?,?)""",
            (name, cat, unit, stock, min_s, cpu),
        )

# ─── Utilidades ───────────────────────────────────────────────────────────────

def _hash(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


# Rótulos das faixas etárias (registro por idade)
AGE_BANDS = ["Até 12 meses", "13 a 24 meses", "25 a 36 meses", "+ de 36 meses"]

# Formas de definição da idade
AGE_SOURCES = {
    "propriedade": "Nascido na propriedade (data exata)",
    "estimado":    "Nascimento estimado (mês aproximado)",
    "operador":    "Idade definida pelo operador",
    "nf_gta":      "Idade da NF / GTA",
}


def _months_between(d_start: date, d_end: date) -> int:
    """Diferença em meses cheios entre duas datas."""
    months = (d_end.year - d_start.year) * 12 + (d_end.month - d_start.month)
    if d_end.day < d_start.day:
        months -= 1
    return max(months, 0)


def birth_date_from_age(age_months: int, ref_date: Optional[date] = None) -> str:
    """Calcula a data de nascimento retroativa a partir de uma idade em meses.
    Usada quando o operador ou a NF/GTA informam a idade em vez da data."""
    ref = ref_date or date.today()
    total = ref.year * 12 + (ref.month - 1) - int(age_months)
    year, month = divmod(total, 12)
    month += 1
    # dia 15 como referência média do mês (nascimento estimado)
    day = min(15, 28)
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return date(year, month, 1).isoformat()


def get_age_months(birth_date_str: Optional[str]) -> Optional[int]:
    """Idade atual em meses (avança automaticamente com o tempo)."""
    if not birth_date_str:
        return None
    try:
        birth = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        return _months_between(birth, date.today())
    except ValueError:
        return None


def get_age_category(birth_date_str: Optional[str], sex: Optional[str] = None) -> str:
    """Categoria por faixa etária. O parâmetro sex é mantido por compatibilidade."""
    months = get_age_months(birth_date_str)
    if months is None:
        return "Sem idade"
    if months <= 12: return AGE_BANDS[0]
    if months <= 24: return AGE_BANDS[1]
    if months <= 36: return AGE_BANDS[2]
    return AGE_BANDS[3]


def get_age_display(animal: dict) -> str:
    """Texto de idade para exibição, indicando se é estimada."""
    months = get_age_months(animal.get("birth_date"))
    if months is None:
        return "—"
    est = " (est.)" if animal.get("birth_estimated") else ""
    years, rem = divmod(months, 12)
    if years and rem:
        base = f"{years}a {rem}m"
    elif years:
        base = f"{years} ano{'s' if years > 1 else ''}"
    else:
        base = f"{months} mes{'es' if months != 1 else ''}"
    return f"{base}{est}"


def kg_to_arrobas(weight_kg: float, yield_: float = CARCASS_YIELD) -> float:
    return round(weight_kg * yield_ / KG_PER_ARROBA, 2)


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

# ─── Autenticação ─────────────────────────────────────────────────────────────

def verify_login(username: str, password: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
    if row and row["password_hash"] == _hash(password):
        return dict(row)
    return None

# ─── Sessões persistentes (login lembrado) ───────────────────────────────────

def create_session(user_id: int, days: int = 7) -> str:
    """Cria um token de sessão e retorna-o. Usado para manter o login ao recarregar."""
    import secrets
    token = secrets.token_urlsafe(24)
    expires = (datetime.now() + timedelta(days=days)).isoformat()
    with _conn() as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER, expires_at TEXT)"
        )
        if USE_PG:
            con.execute(
                "INSERT INTO sessions (token,user_id,expires_at) VALUES(?,?,?) "
                "ON CONFLICT (token) DO UPDATE SET user_id=EXCLUDED.user_id, expires_at=EXCLUDED.expires_at",
                (token, user_id, expires),
            )
        else:
            con.execute(
                "INSERT OR REPLACE INTO sessions (token,user_id,expires_at) VALUES(?,?,?)",
                (token, user_id, expires),
            )
    return token


def get_session_user(token: str) -> Optional[dict]:
    """Retorna o usuário associado a um token de sessão válido (não expirado)."""
    if not token:
        return None
    with _conn() as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER, expires_at TEXT)"
        )
        row = con.execute(
            "SELECT user_id, expires_at FROM sessions WHERE token=?", (token,)
        ).fetchone()
        if not row:
            return None
        try:
            if datetime.fromisoformat(row["expires_at"]) < datetime.now():
                con.execute("DELETE FROM sessions WHERE token=?", (token,))
                return None
        except (ValueError, TypeError):
            return None
        u = con.execute(
            "SELECT id, username, name, role FROM users WHERE id=?", (row["user_id"],)
        ).fetchone()
    return dict(u) if u else None


def delete_session(token: str) -> None:
    if not token:
        return
    with _conn() as con:
        con.execute("CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER, expires_at TEXT)")
        con.execute("DELETE FROM sessions WHERE token=?", (token,))

# ─── Gestão de Usuários ──────────────────────────────────────────────────────

def get_all_users() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, username, name, role FROM users ORDER BY role, username"
        ).fetchall()
    return [dict(r) for r in rows]


def get_user(user_id: int) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT id, username, name, role FROM users WHERE id=?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def username_exists(username: str, exclude_id: Optional[int] = None) -> bool:
    with _conn() as con:
        if exclude_id is not None:
            row = con.execute(
                "SELECT 1 FROM users WHERE username=? AND id<>?", (username, exclude_id)
            ).fetchone()
        else:
            row = con.execute(
                "SELECT 1 FROM users WHERE username=?", (username,)
            ).fetchone()
    return row is not None


@_writes
def add_user(username: str, password: str, name: str, role: str = "operator") -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO users (username,password_hash,name,role) VALUES(?,?,?,?)",
            (username, _hash(password), name, role),
        )


@_writes
def update_user(user_id: int, name: str, role: str,
                new_password: Optional[str] = None) -> None:
    """Atualiza nome e papel; se new_password for informado, redefine a senha."""
    with _conn() as con:
        if new_password:
            con.execute(
                "UPDATE users SET name=?, role=?, password_hash=? WHERE id=?",
                (name, role, _hash(new_password), user_id),
            )
        else:
            con.execute(
                "UPDATE users SET name=?, role=? WHERE id=?",
                (name, role, user_id),
            )


@_writes
def update_username(user_id: int, new_username: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET username=? WHERE id=?", (new_username, user_id))


@_writes
def delete_user(user_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM users WHERE id=?", (user_id,))


def count_admins() -> int:
    with _conn() as con:
        row = con.execute("SELECT COUNT(*) as n FROM users WHERE role='admin'").fetchone()
    return int(row["n"])

# ─── Animais ──────────────────────────────────────────────────────────────────

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
def update_animal_status(animal_id: str, status: str) -> None:
    with _conn() as con:
        con.execute("UPDATE animals SET status=? WHERE id=?", (status, animal_id))


@_writes
def update_animal_age(animal_id: str, birth_date: str,
                      birth_estimated: int, age_source: str) -> None:
    """Atualiza a definição de idade de um animal existente."""
    with _conn() as con:
        con.execute(
            "UPDATE animals SET birth_date=?, birth_estimated=?, age_source=? WHERE id=?",
            (birth_date or None, int(birth_estimated), age_source, animal_id),
        )

# ─── Pesagens ────────────────────────────────────────────────────────────────

def get_weighings(animal_id: str) -> list[dict]:
    return list(_weighings_by_animal().get(animal_id, []))


WEIGH_METHODS = {
    "pesado":   "Pesado na balança",
    "estimado": "Estimado pelo operador",
    "medicao":  "Estimado por medição (fita/fórmula)",
}


@_writes
def add_weighing(animal_id, weight, weigh_date, operator="", notes="",
                 method="pesado") -> None:
    with _conn() as con:
        lote = con.execute(
            "SELECT lote_id FROM animals WHERE id=?", (animal_id,)
        ).fetchone()
        lote_id = lote["lote_id"] if lote else None
        con.execute(
            "INSERT INTO weighings (animal_id,weight,weigh_date,lote_id,operator,method,notes) VALUES(?,?,?,?,?,?,?)",
            (animal_id, weight, weigh_date, lote_id, operator, method, notes),
        )
        con.execute("UPDATE animals SET current_weight=? WHERE id=?", (weight, animal_id))


def estimate_weight_by_measurement(girth_cm: float, length_cm: float) -> float:
    """Estima o peso vivo (kg) a partir do perímetro torácico e do comprimento
    corporal, usando a fórmula de Schaeffer convertida para o sistema métrico:
        Peso(lb) = (PT_pol² × Comp_pol) / 300
    Convertida para cm→kg resulta no fator ~1/10838."""
    if girth_cm <= 0 or length_cm <= 0:
        return 0.0
    return round((girth_cm ** 2) * length_cm / 10838.0, 1)


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


def calculate_gmd(animal_id: str) -> Optional[float]:
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

# ─── Medicamentos ─────────────────────────────────────────────────────────────

def get_medications(animal_id: str) -> list[dict]:
    return list(_medications_by_animal().get(animal_id, []))


@_writes
def add_medication(animal_id, medication_name, dose, unit, application_route,
                   withdrawal_days, med_date, applied_by="",
                   insumo_id=None, notes="") -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO medications
               (animal_id,medication_name,dose,unit,application_route,
                withdrawal_days,med_date,applied_by,insumo_id,notes)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (animal_id, medication_name, dose, unit, application_route,
             withdrawal_days, med_date, applied_by, insumo_id or None, notes),
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

# ─── Lotes / Piquetes ────────────────────────────────────────────────────────

@_cache
def get_all_lotes() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT l.*,
                      COUNT(a.id) as animal_count,
                      SUM(a.current_weight) / 450.0 as total_ua
               FROM lotes l
               LEFT JOIN animals a ON a.lote_id=l.id AND a.status='ativo'
               GROUP BY l.id ORDER BY l.id""",
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("total_ua") is not None:
            d["total_ua"] = round(float(d["total_ua"]), 2)
        out.append(d)
    return out


def get_lote(lote_id: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute("SELECT * FROM lotes WHERE id=?", (lote_id,)).fetchone()
    return dict(row) if row else None


@_writes
def add_lote(lote_id, name, area_ha, capacity_ua, notes="") -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO lotes (id,name,area_ha,capacity_ua,notes) VALUES(?,?,?,?,?)",
            (lote_id, name, area_ha, capacity_ua, notes),
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

# ─── Insumos / Estoque ───────────────────────────────────────────────────────

@_cache
def get_all_insumos() -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM insumos ORDER BY category, name").fetchall()
    return [dict(r) for r in rows]


def get_insumo(insumo_id: int) -> Optional[dict]:
    with _conn() as con:
        row = con.execute("SELECT * FROM insumos WHERE id=?", (insumo_id,)).fetchone()
    return dict(row) if row else None


@_writes
def add_insumo_entry(insumo_id: int, quantity: float, cost_per_unit: float,
                     operator: str = "") -> None:
    with _conn() as con:
        today_str = date.today().isoformat()
        con.execute(
            "UPDATE insumos SET current_stock=current_stock+?, cost_per_unit=? WHERE id=?",
            (quantity, cost_per_unit, insumo_id),
        )
        con.execute(
            """INSERT INTO insumo_transactions
               (insumo_id,type,quantity,reason,transaction_date,operator)
               VALUES(?,?,?,?,?,?)""",
            (insumo_id, "entrada", quantity, "compra", today_str, operator),
        )


@_writes
def add_new_insumo(name, category, unit, initial_stock, min_stock, cost_per_unit) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO insumos (name,category,unit,current_stock,min_stock,cost_per_unit) VALUES(?,?,?,?,?,?)",
            (name, category, unit, initial_stock, min_stock, cost_per_unit),
        )

# ─── Custos por Animal ───────────────────────────────────────────────────────

def get_animal_costs(animal_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM animal_costs WHERE animal_id=? ORDER BY cost_date DESC",
            (animal_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@_writes
def add_animal_cost(animal_id, cost_type, description, amount, cost_date, notes="") -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO animal_costs (animal_id,cost_type,description,amount,cost_date,notes) VALUES(?,?,?,?,?,?)",
            (animal_id, cost_type, description, amount, cost_date, notes),
        )


def get_total_cost(animal_id: str) -> float:
    return _costs_by_animal().get(animal_id, 0.0)

# ─── Custos Fixos (nível da fazenda) ─────────────────────────────────────────

FIXED_COST_CATEGORIES = [
    "Aluguel de pastagem",
    "Salários",
    "Bonificação de funcionários",
    "Impostos",
    "Taxas",
    "Energia / Combustível",
    "Manutenção",
    "Outro",
]


@_writes
def add_fixed_cost(category, description, amount, cost_date, recurring=0, notes="") -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO fixed_costs (category,description,amount,cost_date,recurring,notes)
               VALUES(?,?,?,?,?,?)""",
            (category, description, amount, cost_date, int(recurring), notes),
        )


def get_fixed_costs(start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> list[dict]:
    sql, args = "SELECT * FROM fixed_costs WHERE 1=1", []
    if start_date:
        sql += " AND cost_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND cost_date <= ?"; args.append(end_date)
    sql += " ORDER BY cost_date DESC, id DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def get_total_fixed_costs(start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> float:
    sql, args = "SELECT COALESCE(SUM(amount),0) as total FROM fixed_costs WHERE 1=1", []
    if start_date:
        sql += " AND cost_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND cost_date <= ?"; args.append(end_date)
    with _conn() as con:
        row = con.execute(sql, args).fetchone()
    return round(float(row["total"]), 2)


@_writes
def delete_fixed_cost(cost_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM fixed_costs WHERE id=?", (cost_id,))


def get_fixed_costs_by_category(start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> list[dict]:
    sql = "SELECT category, COALESCE(SUM(amount),0) as total FROM fixed_costs WHERE 1=1"
    args: list = []
    if start_date:
        sql += " AND cost_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND cost_date <= ?"; args.append(end_date)
    sql += " GROUP BY category ORDER BY total DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]

# ─── Programação de Trato / Ração / Mineral ──────────────────────────────────

FEEDING_FREQUENCIES = {"diario": "Diário", "semanal": "Semanal", "mensal": "Mensal"}
FEEDING_CHECK_STATUS = {"feito": "Feito", "parcial": "Parcial", "nao_feito": "Não feito"}

# Fatores de conversão para a unidade base de cada família (peso→kg, volume→litro)
_UNIT_FACTORS = {
    # peso (base: kg)
    "ton": ("peso", 1000.0), "t": ("peso", 1000.0),
    "kg": ("peso", 1.0),
    "g": ("peso", 0.001),
    # volume (base: litro)
    "litro": ("volume", 1.0), "l": ("volume", 1.0),
    "ml": ("volume", 0.001),
}


def convert_quantity(qty: float, from_unit: str, to_unit: str) -> Optional[float]:
    """Converte uma quantidade entre unidades compatíveis (kg↔ton↔g, litro↔ml).
    Retorna None se as unidades forem incompatíveis (ex.: kg → saco)."""
    if qty is None:
        return None
    fu, tu = (from_unit or "").lower().strip(), (to_unit or "").lower().strip()
    if fu == tu:
        return qty
    fi, ti = _UNIT_FACTORS.get(fu), _UNIT_FACTORS.get(tu)
    if not fi or not ti or fi[0] != ti[0]:
        return None  # incompatível ou desconhecida
    # qty * (fator_origem / fator_destino)
    return qty * fi[1] / ti[1]


@_writes
def add_feeding_plan(lote_id, product_name, quantity, unit, frequency,
                     insumo_id=None, notes="") -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO feeding_plans
               (lote_id,product_name,insumo_id,quantity,unit,frequency,notes)
               VALUES(?,?,?,?,?,?,?)""",
            (lote_id, product_name, insumo_id or None, quantity, unit, frequency, notes),
        )


@_cache
def get_feeding_plans(lote_id: Optional[str] = None,
                      active_only: bool = True) -> list[dict]:
    sql = ("SELECT p.*, l.name as lote_name, i.name as insumo_name "
           "FROM feeding_plans p "
           "LEFT JOIN lotes l ON l.id=p.lote_id "
           "LEFT JOIN insumos i ON i.id=p.insumo_id WHERE 1=1")
    args: list = []
    if active_only:
        sql += " AND p.active=1"
    if lote_id:
        sql += " AND p.lote_id=?"; args.append(lote_id)
    sql += " ORDER BY p.lote_id, p.product_name"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


@_writes
def set_feeding_plan_active(plan_id: int, active: int) -> None:
    with _conn() as con:
        con.execute("UPDATE feeding_plans SET active=? WHERE id=?", (int(active), plan_id))


@_writes
def delete_feeding_plan(plan_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM feeding_plans WHERE id=?", (plan_id,))


@_writes
def add_feeding_check(plan_id, lote_id, check_date, status,
                      actual_quantity=None, operator="", notes="",
                      deduct_stock=False, insumo_id=None,
                      quantity_unit="kg") -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO feeding_checks
               (plan_id,lote_id,check_date,status,actual_quantity,operator,notes)
               VALUES(?,?,?,?,?,?,?)""",
            (plan_id, lote_id, check_date, status, actual_quantity, operator, notes),
        )
        # Baixa opcional no estoque quando o trato é confirmado
        if deduct_stock and insumo_id and actual_quantity and status != "nao_feito":
            ins = con.execute(
                "SELECT unit FROM insumos WHERE id=?", (insumo_id,)
            ).fetchone()
            stock_unit = ins["unit"] if ins else quantity_unit
            # Converte a quantidade aplicada (unidade do plano) para a unidade do estoque
            deduct = convert_quantity(actual_quantity, quantity_unit, stock_unit)
            if deduct is None:
                deduct = actual_quantity   # unidades incompatíveis: baixa direta
            con.execute(
                "UPDATE insumos SET current_stock = MAX(0, current_stock - ?) WHERE id=?",
                (deduct, insumo_id),
            )
            con.execute(
                """INSERT INTO insumo_transactions
                   (insumo_id,type,quantity,reason,transaction_date,operator)
                   VALUES(?,?,?,?,?,?)""",
                (insumo_id, "saida", deduct, "trato_lote", check_date, operator),
            )


def get_feeding_checks(lote_id: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> list[dict]:
    sql = ("SELECT c.*, l.name as lote_name, p.product_name "
           "FROM feeding_checks c "
           "LEFT JOIN lotes l ON l.id=c.lote_id "
           "LEFT JOIN feeding_plans p ON p.id=c.plan_id WHERE 1=1")
    args: list = []
    if lote_id:
        sql += " AND c.lote_id=?"; args.append(lote_id)
    if start_date:
        sql += " AND c.check_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND c.check_date <= ?"; args.append(end_date)
    sql += " ORDER BY c.check_date DESC, c.id DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def get_plan_check_for_date(plan_id: int, check_date: str) -> Optional[dict]:
    """Retorna a checagem de um plano numa data específica, se existir."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM feeding_checks WHERE plan_id=? AND check_date=? ORDER BY id DESC LIMIT 1",
            (plan_id, check_date),
        ).fetchone()
    return dict(row) if row else None


def _period_key(freq: str, d: date) -> str:
    """Identificador do período atual conforme a frequência do plano."""
    if freq == "semanal":
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    if freq == "mensal":
        return f"{d.year}-{d.month:02d}"
    return d.isoformat()   # diário (ou padrão)


def get_pending_feedings(ref_date: Optional[date] = None) -> list[dict]:
    """Retorna os planos de nutrição ativos e, para cada um, se já foi confirmado
    no período atual (dia/semana/mês). Só há planos para piquetes cadastrados pelo
    admin — piquetes sem plano não entram na lista."""
    ref = ref_date or date.today()
    plans = get_feeding_plans(active_only=True)
    result = []
    with _conn() as con:
        for p in plans:
            last = con.execute(
                "SELECT check_date FROM feeding_checks WHERE plan_id=? ORDER BY check_date DESC, id DESC LIMIT 1",
                (p["id"],),
            ).fetchone()
            done = False
            last_date = None
            if last:
                last_date = last["check_date"]
                try:
                    ld = datetime.strptime(last_date, "%Y-%m-%d").date()
                    done = _period_key(p["frequency"], ld) == _period_key(p["frequency"], ref)
                except (ValueError, TypeError):
                    done = False
            result.append({**p, "done_this_period": done, "last_check": last_date})
    return result

# ─── Preços por Categoria (valor esperado por kg) ────────────────────────────

SALE_TYPES = {"abate": "Abate (frigorífico)", "criacao": "Criação (reprodução/recria)"}
PRICING_MODES = {"kg": "Por kg (peso × preço)",
                 "cabeca": "Por cabeça (valor fechado)",
                 "lote": "Por lote fechado (valor único do grupo)"}


def get_category_prices() -> dict:
    """Retorna {(age_band, sex): price_per_kg} para consulta rápida."""
    with _conn() as con:
        rows = con.execute("SELECT age_band, sex, price_per_kg FROM category_prices").fetchall()
    return {(r["age_band"], r["sex"]): r["price_per_kg"] for r in rows}


def get_category_prices_list() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM category_prices ORDER BY age_band, sex"
        ).fetchall()
    return [dict(r) for r in rows]


@_writes
def set_category_price(age_band: str, sex: str, price_per_kg: float) -> None:
    """Insere/atualiza o valor esperado por kg de uma categoria."""
    today = date.today().isoformat()
    with _conn() as con:
        if USE_PG:
            con.execute(
                "INSERT INTO category_prices (age_band,sex,price_per_kg,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT (age_band,sex) DO UPDATE SET price_per_kg=EXCLUDED.price_per_kg, updated_at=EXCLUDED.updated_at",
                (age_band, sex, price_per_kg, today),
            )
        else:
            con.execute(
                "INSERT OR REPLACE INTO category_prices (age_band,sex,price_per_kg,updated_at) VALUES(?,?,?,?)",
                (age_band, sex, price_per_kg, today),
            )


def get_expected_price_kg(age_band: str, sex: str) -> float:
    return get_category_prices().get((age_band, sex), 0.0)


def expected_sale_value(animal: dict) -> float:
    """Valor esperado de venda do animal = peso atual × preço/kg da categoria."""
    band = get_age_category(animal.get("birth_date"))
    price = get_expected_price_kg(band, animal["sex"])
    return round(animal["current_weight"] * price, 2)

# ─── Vendas ──────────────────────────────────────────────────────────────────

@_writes
def register_sale(animal_ids: list, sale_date: str, sale_type: str,
                  pricing_mode: str, value: float, buyer: str = "",
                  operator: str = "", notes: str = "") -> dict:
    """Registra a venda de um ou mais animais.
    - pricing_mode='kg':     `value` é o preço por kg (cada animal: peso × preço).
    - pricing_mode='cabeca': `value` é o valor por cabeça (igual para cada animal).
    - pricing_mode='lote':   `value` é o valor TOTAL do lote, rateado pelo peso.
    Retorna {'receita':..., 'custo':..., 'lucro':..., 'n':...}."""
    animais = [get_animal(a) for a in animal_ids]
    animais = [a for a in animais if a]
    if not animais:
        return {"receita": 0, "custo": 0, "lucro": 0, "n": 0}

    peso_total = sum(a["current_weight"] for a in animais) or 1
    lot_ref = f"V{sale_date.replace('-','')}-{int(datetime.now().timestamp())%100000}" \
              if (pricing_mode == "lote" or len(animais) > 1) else None

    tot_receita = tot_custo = 0.0
    with _conn() as con:
        for a in animais:
            if pricing_mode == "kg":
                ppk = value
                val = round(a["current_weight"] * value, 2)
            elif pricing_mode == "cabeca":
                ppk = None
                val = round(value, 2)
            else:  # lote: rateio proporcional ao peso
                ppk = None
                val = round(value * a["current_weight"] / peso_total, 2)

            custo = get_total_cost(a["id"])
            lucro = round(val - custo, 2)
            tot_receita += val
            tot_custo += custo

            con.execute(
                """INSERT INTO sales
                   (animal_id,sale_date,sale_type,pricing_mode,weight_kg,price_per_kg,
                    total_value,buyer,lot_ref,cost_at_sale,profit,operator,notes)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (a["id"], sale_date, sale_type, pricing_mode, a["current_weight"], ppk,
                 val, buyer or None, lot_ref, custo, lucro, operator, notes),
            )
            con.execute("UPDATE animals SET status='vendido' WHERE id=?", (a["id"],))
    return {"receita": round(tot_receita, 2), "custo": round(tot_custo, 2),
            "lucro": round(tot_receita - tot_custo, 2), "n": len(animais),
            "lot_ref": lot_ref}


def get_sales(start_date: Optional[str] = None,
              end_date: Optional[str] = None) -> list[dict]:
    sql = ("SELECT s.*, a.breed, a.sex FROM sales s "
           "LEFT JOIN animals a ON a.id=s.animal_id WHERE 1=1")
    args: list = []
    if start_date:
        sql += " AND s.sale_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND s.sale_date <= ?"; args.append(end_date)
    sql += " ORDER BY s.sale_date DESC, s.id DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]

# ─── Resumo Financeiro Consolidado ───────────────────────────────────────────

def _insumo_cost_by_reason(con, reasons: tuple, start=None, end=None) -> float:
    """Custo dos insumos consumidos (saída) por motivo, usando o custo unitário atual."""
    sql = ("SELECT COALESCE(SUM(t.quantity * i.cost_per_unit),0) AS total "
           "FROM insumo_transactions t JOIN insumos i ON i.id=t.insumo_id "
           "WHERE t.type='saida' AND t.reason IN (%s)" % ",".join("?"*len(reasons)))
    args = list(reasons)
    if start:
        sql += " AND t.transaction_date >= ?"; args.append(start)
    if end:
        sql += " AND t.transaction_date <= ?"; args.append(end)
    row = con.execute(sql, args).fetchone()
    return round(float(row["total"] or 0), 2)


def get_financial_summary(start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> dict:
    """Planilha financeira consolidada do período (todas as saídas e entradas)."""
    def _period(col):
        s, a = "", []
        if start_date: s += f" AND {col} >= ?"; a.append(start_date)
        if end_date:   s += f" AND {col} <= ?"; a.append(end_date)
        return s, a

    with _conn() as con:
        # Saídas
        ps, pa = _period("cost_date")
        compra = con.execute(
            "SELECT COALESCE(SUM(amount),0) t FROM animal_costs WHERE cost_type='compra'"+ps, pa
        ).fetchone()["t"]
        operacional = con.execute(
            "SELECT COALESCE(SUM(amount),0) t FROM animal_costs WHERE cost_type='operacional'"+ps, pa
        ).fetchone()["t"]
        fs, fa = _period("cost_date")
        fixos = con.execute(
            "SELECT COALESCE(SUM(amount),0) t FROM fixed_costs WHERE 1=1"+fs, fa
        ).fetchone()["t"]
        medicamentos = _insumo_cost_by_reason(con, ("uso_animal",), start_date, end_date)
        nutricao     = _insumo_cost_by_reason(con, ("trato_lote",), start_date, end_date)
        # Entradas
        ss, sa = _period("sale_date")
        rows_v = con.execute(
            "SELECT sale_type, COALESCE(SUM(total_value),0) receita, COALESCE(SUM(profit),0) lucro, COUNT(*) n "
            "FROM sales WHERE 1=1"+ss+" GROUP BY sale_type", sa
        ).fetchall()

    vendas = {r["sale_type"]: {"receita": round(float(r["receita"]),2),
                               "lucro": round(float(r["lucro"]),2),
                               "n": r["n"]} for r in rows_v}
    receita_total = round(sum(v["receita"] for v in vendas.values()), 2)
    saidas_total = round(float(compra)+float(operacional)+float(fixos)+medicamentos+nutricao, 2)
    return {
        "compra_animais": round(float(compra), 2),
        "operacional":    round(float(operacional), 2),
        "custos_fixos":   round(float(fixos), 2),
        "medicamentos":   medicamentos,
        "nutricao":       nutricao,
        "saidas_total":   saidas_total,
        "vendas":         vendas,
        "receita_total":  receita_total,
        "resultado":      round(receita_total - saidas_total, 2),
    }

# ─── Administração: edição direta de tabelas ─────────────────────────────────

ADMIN_TABLES = [
    "animals", "weighings", "medications", "insumos", "lotes",
    "fornecedores", "animal_costs", "fixed_costs", "insumo_transactions",
    "animal_movements", "feeding_plans", "feeding_checks",
    "category_prices", "sales", "users",
]


def admin_table_info(table: str) -> tuple[list[str], str]:
    """Retorna (colunas, coluna_pk) de uma tabela permitida."""
    if table not in ADMIN_TABLES:
        raise ValueError(f"Tabela não permitida: {table}")
    with _conn() as con:
        if USE_PG:
            cols = [r["name"] for r in con.execute(
                "SELECT column_name AS name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=? ORDER BY ordinal_position",
                (table,)).fetchall()]
            pkrows = con.execute(
                "SELECT a.attname AS name FROM pg_index i "
                "JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum = ANY(i.indkey) "
                "WHERE i.indrelid = (?::regclass) AND i.indisprimary", (table,)).fetchall()
            pk = pkrows[0]["name"] if pkrows else (cols[0] if cols else "id")
        else:
            info = con.execute(f"PRAGMA table_info({table})").fetchall()
            cols = [r["name"] for r in info]
            pk = next((r["name"] for r in info if r["pk"]), cols[0])
    return cols, pk


def admin_get_rows(table: str) -> list[dict]:
    if table not in ADMIN_TABLES:
        raise ValueError(f"Tabela não permitida: {table}")
    _, pk = admin_table_info(table)
    with _conn() as con:
        rows = con.execute(f"SELECT * FROM {table} ORDER BY {pk}").fetchall()
    return [dict(r) for r in rows]


@_writes
def admin_apply_changes(table: str, updates: list[dict],
                        inserts: list[dict], delete_pks: list) -> dict:
    """Aplica alterações vindas do editor. `updates` e `inserts` são dicts de
    coluna→valor (updates precisam conter a PK). Retorna contagem por operação."""
    if table not in ADMIN_TABLES:
        raise ValueError(f"Tabela não permitida: {table}")
    cols, pk = admin_table_info(table)
    valid = set(cols)
    n_upd = n_ins = n_del = 0
    with _conn() as con:
        # Exclusões
        for pkv in delete_pks:
            con.execute(f"DELETE FROM {table} WHERE {pk}=?", (pkv,))
            n_del += 1
        # Atualizações
        for row in updates:
            pkv = row.get(pk)
            fields = {k: v for k, v in row.items() if k in valid and k != pk}
            if not fields:
                continue
            sets = ", ".join(f"{k}=?" for k in fields)
            con.execute(f"UPDATE {table} SET {sets} WHERE {pk}=?",
                        (*fields.values(), pkv))
            n_upd += 1
        # Inserções
        for row in inserts:
            fields = {k: v for k, v in row.items()
                      if k in valid and v is not None and str(v) != ""}
            if not fields:
                continue
            placeholders = ", ".join("?" for _ in fields)
            con.execute(
                f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders})",
                tuple(fields.values()))
            n_ins += 1
    return {"updated": n_upd, "inserted": n_ins, "deleted": n_del}


# ─── Fornecedores ────────────────────────────────────────────────────────────

def get_all_fornecedores() -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM fornecedores ORDER BY name").fetchall()
    return [dict(r) for r in rows]


@_writes
def add_fornecedor(name, city, state, contact="", notes="") -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO fornecedores (name,city,state,contact,notes) VALUES(?,?,?,?,?)",
            (name, city, state, contact, notes),
        )


def get_fornecedor_performance() -> list[dict]:
    """GMD médio agrupado por fornecedor de origem."""
    animals = get_all_animals()
    rows = []
    forn_map: dict[str, list[float]] = {}
    for a in animals:
        gmd = calculate_gmd(a["id"])
        fname = a.get("fornecedor_name") or "Não informado"
        forn_map.setdefault(fname, [])
        if gmd is not None:
            forn_map[fname].append(gmd)
    for fname, gmds in forn_map.items():
        rows.append({
            "Fornecedor":   fname,
            "Animais":      len(gmds),
            "GMD Médio":    round(sum(gmds)/len(gmds), 3) if gmds else 0,
        })
    return sorted(rows, key=lambda x: -x["GMD Médio"])

# ─── Alertas ─────────────────────────────────────────────────────────────────

def get_alert_animals() -> dict:
    animals = get_all_animals()
    today   = date.today()
    sumidos, carencia_active, prontos = [], [], []

    for a in animals:
        # Sumidos: sem pesagem nos últimos 30 dias
        ws = get_weighings(a["id"])
        if ws:
            last_w = datetime.strptime(ws[0]["weigh_date"], "%Y-%m-%d").date()
            if (today - last_w).days > 30:
                sumidos.append({**a, "days_since_weighing": (today - last_w).days})

        # Em carência ativa
        end = get_withdrawal_end(a["id"])
        if end and end >= today:
            carencia_active.append({**a, "withdrawal_end": end.isoformat(),
                                    "days_remaining": (end - today).days})

        # Prontos para abate
        target = a.get("target_weight") or 500
        if a["current_weight"] >= target and not end:
            prontos.append({**a, "arrobas": kg_to_arrobas(a["current_weight"])})

    return {"sumidos": sumidos, "carencia": carencia_active, "prontos": prontos}


@_cache
def check_low_stock() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM insumos WHERE current_stock <= min_stock ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]

# ─── KPIs e Estatísticas ─────────────────────────────────────────────────────

def get_rebanho_stats() -> dict:
    animals = get_all_animals()
    lotes   = get_all_lotes()
    if not animals:
        return {}

    weights = [a["current_weight"] for a in animals]
    gains   = [a["current_weight"] - a["entry_weight"] for a in animals]
    gmds    = [g for g in (calculate_gmd(a["id"]) for a in animals) if g is not None]

    total_ua    = sum(w / UA_WEIGHT for w in weights)
    total_area  = sum(l["area_ha"] for l in lotes if l["area_ha"] and l["status"] == "ativo")
    lotacao     = round(total_ua / total_area, 2) if total_area else 0
    arrobas_prod = sum(kg_to_arrobas(g) for g in gains if g > 0)

    return {
        "total":         len(animals),
        "avg_weight":    round(sum(weights) / len(weights), 1),
        "avg_gmd":       round(sum(gmds) / len(gmds), 3) if gmds else 0,
        "total_kg":      round(sum(weights), 0),
        "males":         sum(1 for a in animals if a["sex"] == "M"),
        "females":       sum(1 for a in animals if a["sex"] == "F"),
        "total_ua":      round(total_ua, 1),
        "total_area":    total_area,
        "lotacao_ua_ha": lotacao,
        "arrobas_prod":  round(arrobas_prod, 1),
    }


def get_all_weighings() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT w.*, a.breed
               FROM weighings w JOIN animals a ON a.id=w.animal_id
               WHERE a.status='ativo' ORDER BY w.weigh_date""",
        ).fetchall()
    return [dict(r) for r in rows]


def refresh_carencia_status() -> None:
    """Atualiza automaticamente o status de animais cuja carência expirou."""
    today = date.today()
    animals = get_all_animals(status="carencia")
    for a in animals:
        end = get_withdrawal_end(a["id"])
        if end is None or end < today:
            update_animal_status(a["id"], "ativo")
