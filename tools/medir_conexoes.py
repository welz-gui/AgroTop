#!/usr/bin/env python
"""Mede o custo de conexão do `_conn()` contra o Postgres real — com e sem pool.

O QUE FAZ
    Repete N ciclos de `with _conn(): SELECT 1` e reporta quantas conexões o
    driver realmente abriu e quanto tempo levou. Roda duas vezes: no caminho
    atual (com pool) e no caminho antigo (conexão nova a cada uso), para que a
    diferença seja medida, não projetada.

POR QUE N=29 POR PADRÃO
    É o número de `_conn()` que a página financeira faz num rerun com cache
    quente, medido por `tools/medir_paginas.py` em 2026-08-27. Ou seja: o
    resultado desta ferramenta é o tempo de banco daquela página.

SEGURANÇA
    - SOMENTE LEITURA: o único SQL executado é `SELECT 1`.
    - Não chama `init_db()` nem importa `database.py`, para não haver caminho
      algum de escrita em produção.
    - Nunca imprime a URL de conexão, só o host.

USO
    python tools/medir_conexoes.py
    python tools/medir_conexoes.py --ciclos 12      # o dashboard
"""

import argparse
import os
import statistics
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from repositories import conexao   # noqa: E402


class _ContaConexoes:
    """Conta aberturas reais no driver, sem alterar comportamento."""

    def __init__(self):
        self.n = 0
        self._real = None

    def __enter__(self):
        import psycopg2
        self._real = psycopg2.connect

        def contado(*a, **k):
            self.n += 1
            return self._real(*a, **k)

        psycopg2.connect = contado
        conexao.psycopg2.connect = contado
        return self

    def __exit__(self, *exc):
        import psycopg2
        psycopg2.connect = self._real
        conexao.psycopg2.connect = self._real
        return False


def _ciclo_com_pool(n):
    for _ in range(n):
        with conexao._conn() as con:
            con.execute("SELECT 1").fetchone()


def _ciclo_sem_pool(n):
    """O comportamento anterior ao pool: conexão nova, usada uma vez, fechada."""
    import psycopg2
    for _ in range(n):
        con = psycopg2.connect(conexao.DATABASE_URL)
        try:
            cur = con.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            con.commit()
        finally:
            con.close()


def medir(rotulo, funcao, ciclos, repeticoes):
    tempos = []
    aberturas = []
    for _ in range(repeticoes):
        conexao.fechar_pool()          # cada repetição começa do zero
        with _ContaConexoes() as conta:
            t0 = time.perf_counter()
            funcao(ciclos)
            tempos.append((time.perf_counter() - t0) * 1000)
        aberturas.append(conta.n)
    print(f"{rotulo:<16} {statistics.median(aberturas):>8.0f} "
          f"{statistics.median(tempos):>12.0f} ms")
    return statistics.median(aberturas), statistics.median(tempos)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ciclos", type=int, default=29,
                    help="quantos `with _conn()` por rodada (29 = financeiro)")
    ap.add_argument("--repeticoes", type=int, default=5)
    args = ap.parse_args()

    if os.environ.get(conexao.FORCE_SQLITE_ENV):
        sys.exit("AGROTOP_FORCE_SQLITE está ligado — esta medição precisa do Postgres")
    if not conexao.USE_PG:
        sys.exit("sem DATABASE_URL: esta ferramenta mede o Postgres real")

    host = conexao.DATABASE_URL.split("@")[-1].split("/")[0]   # sem credenciais
    print(f"host: {host}")
    print(f"{args.ciclos} usos de _conn() por rodada, mediana de "
          f"{args.repeticoes} rodadas\n")
    print(f"{'':16} {'conexões':>8} {'tempo':>15}")
    print("-" * 42)

    ab_sem, ms_sem = medir("sem pool", _ciclo_sem_pool, args.ciclos, args.repeticoes)
    ab_com, ms_com = medir("com pool", _ciclo_com_pool, args.ciclos, args.repeticoes)
    conexao.fechar_pool()

    print("-" * 42)
    if ms_sem:
        print(f"ganho: {ms_sem - ms_com:.0f} ms "
              f"({(1 - ms_com / ms_sem) * 100:.0f}% menos), "
              f"{ab_sem - ab_com:.0f} handshakes a menos")


if __name__ == "__main__":
    main()
