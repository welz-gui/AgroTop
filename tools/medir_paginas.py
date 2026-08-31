#!/usr/bin/env python
"""Mede conexões, queries e tempo por página do app web — o baseline de desempenho.

O QUE FAZ
    1. Instrumenta a abertura de conexões no backend (`sqlite3.connect`) e a
       execução de queries, ANTES de importar o app.
    2. Roda cada página pelo `AppTest` do Streamlit, num SQLite temporário.
    3. Mede duas vezes por página: cache de dados frio e cache quente.
    4. Projeta o tempo em produção com o custo por operação medido contra o
       Postgres (ver `--handshake` e `--query`).

POR QUE CONTAGEM E NÃO MILISSEGUNDOS
    O `AppTest` materializa a árvore inteira de elementos, então o tempo local
    dele não é o tempo que o usuário sente. As CONTAGENS, essas, são exatas —
    e é a contagem de conexões que domina o custo em produção, porque cada
    handshake com o Postgres custa ~7x o preço de uma query.

SEGURANÇA
    - Roda com `AGROTOP_FORCE_SQLITE=1` em diretório temporário. Nunca toca
      produção.
    - Desliga chamadas HTTP externas (a previsão do tempo), que poluiriam a
      medição com latência de terceiros.

USO
    python tools/medir_paginas.py
    python tools/medir_paginas.py --paginas financeiro,dashboard
    python tools/medir_paginas.py --handshake 177.2 --query 24.4

    Os padrões de --handshake e --query vieram de medição contra o pooler de
    produção (sa-east-1) em 2026-08-27. Refaça com `--medir-rede` se a região,
    o provedor ou a máquina mudarem.
"""

import argparse
import os
import sqlite3
import statistics
import sys
import tempfile
import time
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

# Custos medidos contra o pooler de produção (sa-east-1, porta 6543).
#
# Com o pool em `repositories/conexao.py`, o handshake é pago UMA vez por
# processo, não uma vez por `_conn()`. O que cada `with _conn()` custa é a
# query mais o `commit()` que ele dispara ao sair — 73,4 ms medidos, dos quais
# 49 ms são o commit (`tools/medir_conexoes.py` e a medição de 2026-08-29).
HANDSHAKE_MS = 177.2       # uma vez, na primeira conexão do processo
USO_MS = 73.4              # por `with _conn()`: query + commit
QUERY_MS = 24.4            # a query sozinha, em conexão já aberta

PAGINAS_PADRAO = [
    "dashboard", "rebanho", "lotes", "financeiro", "estoque", "campo",
    "sanitario", "nutricao", "relatorios", "alertas", "desempenho",
    "brincos", "propriedades", "cadastrar",
]

CONTA = {"conexoes": 0, "queries": 0}


# ─── Instrumentação: precisa vir ANTES de qualquer import do app ─────────────
def _instrumentar():
    """Conta aberturas reais de conexão e queries no backend.

    Envolve `sqlite3.connect`, não `_conn()`, de propósito: o que interessa é
    quantas conexões o backend REALMENTE abre. Com pool, `_conn()` continua
    sendo chamado o mesmo tanto de vezes e é a abertura que cai — a diferença
    entre as duas contagens é justamente o ganho.
    """
    real_connect = sqlite3.connect

    class _Proxy:
        def __init__(self, raw):
            object.__setattr__(self, "_raw", raw)

        def execute(self, sql, *a, **k):
            if not sql.lstrip()[:6].upper().startswith(
                    ("PRAGMA", "CREATE", "ALTER", "DROP")):
                CONTA["queries"] += 1
            return self._raw.execute(sql, *a, **k)

        def __getattr__(self, nome):
            return getattr(self._raw, nome)

        def __setattr__(self, nome, valor):
            setattr(self._raw, nome, valor)

    def _connect_contado(*a, **k):
        CONTA["conexoes"] += 1
        return _Proxy(real_connect(*a, **k))

    sqlite3.connect = _connect_contado

    # Previsão do tempo é rede de terceiro: mediria o Open-Meteo, não o AgroTop.
    urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(
        OSError("rede externa desligada durante a medição"))


def _zerar():
    CONTA.update(conexoes=0, queries=0)


# ─── Medição de rede contra produção (opcional) ──────────────────────────────
def medir_rede():
    """Mede handshake e query contra o Postgres de produção. SOMENTE LEITURA."""
    from repositories.conexao import _database_url

    url = _database_url()
    if not url:
        sys.exit("sem DATABASE_URL — configure o segredo antes de usar --medir-rede")
    import psycopg2

    print(f"host: {url.split('@')[-1].split('/')[0]}")   # sem credenciais

    frios = []
    for _ in range(10):
        t0 = time.perf_counter()
        con = psycopg2.connect(url)
        cur = con.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        con.close()
        frios.append((time.perf_counter() - t0) * 1000)

    con = psycopg2.connect(url)
    quentes = []
    for _ in range(20):
        t0 = time.perf_counter()
        cur = con.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        quentes.append((time.perf_counter() - t0) * 1000)
    con.close()

    mf, mq = statistics.median(frios), statistics.median(quentes)
    print(f"conexão nova + SELECT 1 (n=10): mediana {mf:7.1f} ms")
    print(f"query em conexão aberta (n=20): mediana {mq:7.1f} ms")
    print(f"handshake por conexão:          ~{mf - mq:.1f} ms")
    return mf - mq, mq


# ─── Medição por página ──────────────────────────────────────────────────────
def rodar(pagina, limpar_cache, raiz):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    if limpar_cache:
        st.cache_data.clear()
    # 600 s porque o dashboard frio paga o import do processo (~29 s) e, sob
    # carga, estourou o limite anterior de 300 s.
    teste = AppTest.from_file(os.path.join(raiz, "app.py"), default_timeout=600)
    teste.session_state["authenticated"] = True
    teste.session_state["user"] = {"id": 1, "username": "admin",
                                   "name": "Admin", "role": "admin"}
    teste.session_state["page"] = pagina
    _zerar()
    t0 = time.perf_counter()
    teste.run()
    ms = (time.perf_counter() - t0) * 1000
    return dict(CONTA), ms, [e.value for e in teste.exception]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paginas", default=",".join(PAGINAS_PADRAO),
                    help="lista separada por vírgula")
    ap.add_argument("--handshake", type=float, default=HANDSHAKE_MS,
                    help="custo de abrir a 1ª conexão do processo, em ms")
    ap.add_argument("--uso", type=float, default=USO_MS,
                    help="custo de um `with _conn()` (query + commit), em ms")
    ap.add_argument("--medir-rede", action="store_true",
                    help="mede handshake/query contra produção antes de projetar")
    args = ap.parse_args()

    os.environ["AGROTOP_FORCE_SQLITE"] = "1"
    os.chdir(RAIZ)
    _instrumentar()

    handshake, uso = args.handshake, args.uso
    if args.medir_rede:
        os.environ.pop("AGROTOP_FORCE_SQLITE")
        handshake, _ = medir_rede()
        os.environ["AGROTOP_FORCE_SQLITE"] = "1"
        print()

    import database as db

    db.configurar_sqlite(os.path.join(tempfile.mkdtemp(), "medicao.db"))
    db.init_db()
    db.clear_cache()

    # Custo fixo que toda interação paga, seja qual for a página. A chamada é
    # a mesma que `app.py` faz a cada rerun — de propósito: é isso que se quer
    # medir, e o número cai a zero quando a inicialização sai do ciclo.
    _zerar()
    t0 = time.perf_counter()
    db.init_db()
    print(f"init_db() em banco existente: {CONTA['conexoes']} conexão(ões), "
          f"{CONTA['queries']} queries, {(time.perf_counter() - t0) * 1000:.0f} ms\n")

    cab = (f"{'página':<14} {'conex':>6} {'queries':>8} {'projeção':>9}  "
           f"{'conex':>6} {'queries':>8} {'projeção':>9}")
    print(f"{'':14} {'-------- cache frio --------':^25}  "
          f"{'------- cache quente -------':^25}")
    print(cab)
    print("-" * len(cab))

    linhas = []
    for pagina in [p.strip() for p in args.paginas.split(",") if p.strip()]:
        try:
            frio, _, erro = rodar(pagina, True, RAIZ)
            if erro:
                print(f"{pagina:<14} EXCEÇÃO: {erro[0][:45]}")
                continue
            quente, _, _ = rodar(pagina, False, RAIZ)
        except Exception as exc:
            print(f"{pagina:<14} FALHOU: {type(exc).__name__}: {str(exc)[:45]}")
            continue

        # Um handshake por processo (o pool reusa), mais o custo de cada uso.
        proj = lambda c: (handshake + c["conexoes"] * uso) / 1000
        linhas.append((pagina, frio, quente))
        print(f"{pagina:<14} {frio['conexoes']:>6} {frio['queries']:>8} "
              f"{proj(frio):>8.2f}s  {quente['conexoes']:>6} "
              f"{quente['queries']:>8} {proj(quente):>8.2f}s")

    if linhas:
        print("-" * len(cab))
        med = lambda i, k: statistics.median([l[i][k] for l in linhas])
        pm = lambda i: (handshake + med(i, "conexoes") * uso) / 1000
        print(f"{'mediana':<14} {med(1, 'conexoes'):>6.0f} {med(1, 'queries'):>8.0f} "
              f"{pm(1):>8.2f}s  {med(2, 'conexoes'):>6.0f} {med(2, 'queries'):>8.0f} "
              f"{pm(2):>8.2f}s")


if __name__ == "__main__":
    main()
