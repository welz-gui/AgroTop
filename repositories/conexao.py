"""Camada de conexão: escolha do backend, pool, adaptação de dialeto e cache.

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
import threading
from contextlib import contextmanager

FORCE_SQLITE_ENV = "AGROTOP_FORCE_SQLITE"

DB_PATH = "agrotop.db"

# Teto de conexões simultâneas do pool. Dez cobre com folga um processo
# Streamlit servindo o rebanho atual; se o pool esgotar, `_emprestar()` cai
# para conexão direta em vez de recusar (ver lá).
MAX_CONEXOES = int(os.environ.get("AGROTOP_MAX_CONEXOES") or 10)


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
    fechar_pool()          # as ociosas apontam para o banco ANTIGO
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


# Só estes começam uma leitura pura. Qualquer outra coisa — INSERT, UPDATE,
# DELETE, DDL, SET, COPY, CTE — conta como escrita. É conservador de propósito:
# classificar escrita como leitura custaria consistência, o contrário custa
# 49 ms. O levantamento de 2026-08-29 achou 109 SELECT e nenhum `WITH` na
# camada de dados, então a regra simples cobre tudo que existe hoje.
_VERBOS_DE_LEITURA = ("SELECT", "EXPLAIN", "SHOW")


class _PGConn:
    """Adaptador para que o código escrito para sqlite3 (con.execute(...).fetchone())
    funcione igual com psycopg2. Usa DictCursor (suporta row[0] e row['col']).

    ⚠️ Nasce em `autocommit`, e só abre transação quando aparece o primeiro
    comando de escrita. É isso que permite a um `with _conn()` puramente de
    leitura sair sem COMMIT — medição de 2026-08-29: o COMMIT custava 49,4 ms
    contra 24,0 ms da própria query, e a maioria dos usos por rerun é leitura.

    A atomicidade da escrita não muda: assim que o primeiro INSERT/UPDATE
    aparece, a conexão volta ao modo transacional e TODOS os comandos seguintes
    — inclusive as leituras — ficam dentro da mesma transação, que faz commit
    ou rollback junto. O que fica de fora são as leituras anteriores à primeira
    escrita, e essas não dependem de nada que ainda não aconteceu. Não há
    `SELECT ... FOR UPDATE` nem isolamento acima de READ COMMITTED no código do
    app (`tools/backup_banco.py` usa conexão própria), então não há trava nem
    snapshot para preservar.
    """
    def __init__(self, raw):
        self.raw = raw
        self.escreveu = False
        try:
            raw.autocommit = True
        except Exception:
            # Não deu para entrar em autocommit: segue no modo antigo, que é
            # o seguro. Perde-se o ganho, não a correção.
            self.escreveu = True

    def _abre_transacao_se_escrita(self, sql: str) -> None:
        if self.escreveu:
            return
        if sql.lstrip()[:7].upper().startswith(_VERBOS_DE_LEITURA):
            return
        self.raw.autocommit = False      # local: só vale do próximo comando em diante
        self.escreveu = True

    def execute(self, sql, params=()):
        self._abre_transacao_se_escrita(sql)
        cur = self.raw.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(_translate(sql), params)
        return cur

    def executescript(self, sql):
        self._abre_transacao_se_escrita("")      # script é sempre escrita
        cur = self.raw.cursor()
        cur.execute(sql)
        cur.close()

    def commit(self):
        if self.escreveu:                        # leitura pura não abriu nada
            self.raw.commit()

    def rollback(self):
        if self.escreveu:
            self.raw.rollback()

    def close(self):    self.raw.close()


# ─── Pool de conexões ────────────────────────────────────────────────────────
# Medição de 2026-08-27: abrir conexão nova no pooler de produção custa ~177 ms
# de handshake, contra ~24 ms de uma query em conexão já aberta. Como `_conn()`
# era chamado dezenas de vezes por rerun do Streamlit, o handshake dominava o
# tempo de página (financeiro: 29 conexões, ~5,1 s só de handshake).
#
# ⚠️ Cada `with _conn()` recebe uma conexão SÓ SUA, emprestada do pool e
# devolvida no fim. É isso que preserva a semântica atual: `_conn()` é dono da
# transação (commit ao sair, rollback em erro). Compartilhar UMA conexão entre
# sessões faria o rollback de uma abortar a transação em voo de outra — o
# Streamlit atende cada sessão numa thread do mesmo processo.
#
# ⚠️ SÓ o Postgres é agrupado. Abrir SQLite é abrir um arquivo local (~0,02 ms),
# então não há handshake para economizar — e conexão ociosa apertando o arquivo
# faz o Windows recusar `os.remove()` nos testes que gerenciam o próprio banco
# (`test_schema.py`, `test_backend_api.py`). Custo real zero, atrito garantido.
_pool_pg = None
_trava = threading.Lock()


def fechar_pool() -> None:
    """Descarta o pool. Chamado ao trocar de banco (testes)."""
    global _pool_pg
    with _trava:
        if _pool_pg is not None:
            try:
                _pool_pg.closeall()
            except Exception:
                pass
            _pool_pg = None


def _abrir_sqlite():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def _emprestar():
    """Devolve uma conexão do pool, abrindo uma nova só quando não há ociosa."""
    global _pool_pg
    if USE_PG:
        if _pool_pg is None:
            with _trava:
                if _pool_pg is None:
                    from psycopg2 import pool as _pgpool
                    _pool_pg = _pgpool.ThreadedConnectionPool(
                        1, MAX_CONEXOES, DATABASE_URL)
        try:
            return _PGConn(_pool_pg.getconn())
        except Exception:
            # Pool esgotado: cai para o comportamento anterior (conexão direta).
            # Lento, mas nunca recusa — o pool não pode ser um modo novo de falha.
            return _PGConn(psycopg2.connect(DATABASE_URL))
    return _abrir_sqlite()


def _devolver(con, quebrada: bool) -> None:
    # Decide pelo TIPO, não por `USE_PG`: se o alvo do banco mudar enquanto uma
    # conexão está emprestada, a global já não descreve o objeto em mãos — e
    # devolver um `_PGConn` para a lista de ociosas do SQLite corromperia o pool.
    if isinstance(con, _PGConn):
        try:
            _pool_pg.putconn(con.raw, close=quebrada)
        except Exception:
            # Conexão avulsa (pool esgotado) ou pool já descartado: fecha e pronto.
            try:
                con.close()
            except Exception:
                pass
        return
    con.close()          # SQLite não é agrupado: abrir arquivo local é barato


@contextmanager
def _conn():
    con = _emprestar()
    quebrada = False
    try:
        yield con
        con.commit()
    except Exception:
        try:
            con.rollback()
        except Exception:
            # O rollback falhou: a conexão não serve mais para ninguém.
            quebrada = True
        raise
    finally:
        _devolver(con, quebrada)

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
