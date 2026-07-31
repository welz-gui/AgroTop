"""Camada de conexão: escolha do backend, adaptação de dialeto e cache.

É a base da árvore de dependências: `repositories/` e `database.py` importam daqui,
e este módulo não importa nenhum dos dois.

⚠️ ROADMAP.md R1 — `_conn()` é o ÚNICO ponto de acesso ao banco em toda a aplicação.
Nunca chame `psycopg2.connect` nem `sqlite3.connect` fora daqui. É essa concentração
que torna viável rotear por tenant no futuro (ADR 0001) e trocar de provedor (ADR 0002).
Scripts de manutenção em `tools/` são a única exceção — eles precisam de controle
explícito de transação.
"""

import os
import sqlite3
from contextlib import contextmanager

FORCE_SQLITE_ENV = "AGROTOP_FORCE_SQLITE"

DB_PATH = "agrotop.db"


def _database_url() -> str:
    """Lê a URL do Postgres de env var ou dos segredos do Streamlit.

    `AGROTOP_FORCE_SQLITE=1` ignora as duas fontes e devolve string vazia,
    forçando o backend SQLite. Serve para testes: com `.streamlit/secrets.toml`
    presente, o padrão seria conectar em PRODUÇÃO — e um teste que chame
    `init_db()` gravaria lá. Ver `tests/__init__.py`.
    """
    if os.environ.get(FORCE_SQLITE_ENV, "").strip().lower() in ("1", "true", "yes"):
        return ""
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


def configurar_sqlite(caminho: str) -> None:
    """Aponta a conexão para um arquivo SQLite específico (uso em TESTES).

    Existe porque `_conn()` lê as configurações deste módulo. Antes do refactor os
    testes mutavam `database.DB_PATH` e `database.USE_PG` diretamente; com a camada
    separada, essa mutação deixaria de ter efeito e os testes gravariam no banco
    errado **em silêncio** — por isso a configuração é explícita.
    """
    global DB_PATH, DATABASE_URL, USE_PG, IntegrityError
    DB_PATH = caminho
    DATABASE_URL = ""
    USE_PG = False
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
#
# O import de streamlit é preguiçoso e com fallback (ROADMAP.md R9): sem o
# framework, o cache vira no-op e a camada de dados continua utilizável pela API,
# pelo app mobile e por jobs agendados.
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
