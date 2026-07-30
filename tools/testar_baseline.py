#!/usr/bin/env python
"""Valida que o baseline recria o schema do zero — o requisito da estratégia
de uma fazenda por schema (docs/adr/0001-multi-fazenda-schema-por-tenant.md).

O QUE FAZ
    1. Cria um schema temporário e descartável no Postgres.
    2. Aplica supabase/migrations/0000_baseline_producao.sql dentro dele.
    3. Compara o resultado com docs/schema-nuvem.txt (o retrato de produção).
    4. Apaga o schema temporário, inclusive em caso de erro.

    É exatamente o que aconteceria ao provisionar uma fazenda nova.

SEGURANÇA
    - O schema temporário tem nome único com timestamp e prefixo `_baseline_test_`.
    - O DROP é blindado: recusa qualquer nome que não comece com esse prefixo,
      de modo que `public` nunca pode ser alvo.
    - Nenhum dado de produção é lido, escrito ou movido. Só DDL, em schema isolado.

USO
    python tools/testar_baseline.py          # cria, valida e apaga
    python tools/testar_baseline.py --manter # não apaga (para inspeção manual)
"""

import argparse
import os
import sys
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

BASELINE = os.path.join(RAIZ, "supabase", "migrations", "0000_baseline_producao.sql")
SNAPSHOT = os.path.join(RAIZ, "docs", "schema-nuvem.txt")
PREFIXO = "_baseline_test_"


def _drop_seguro(cur, schema: str) -> None:
    """Apaga o schema temporário. Recusa qualquer alvo fora do prefixo."""
    if not schema.startswith(PREFIXO):
        raise RuntimeError(
            f"DROP recusado: '{schema}' não começa com '{PREFIXO}'. "
            "Este script só apaga schemas temporários que ele mesmo criou.")
    cur.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--manter", action="store_true",
                    help="não apagar o schema temporário no final")
    args = ap.parse_args()

    import database as db

    if not db.USE_PG:
        print("ERRO: DATABASE_URL não configurada.", file=sys.stderr)
        return 1
    for caminho in (BASELINE, SNAPSHOT):
        if not os.path.exists(caminho):
            print(f"ERRO: {caminho} não encontrado.", file=sys.stderr)
            return 1

    sql = open(BASELINE, encoding="utf-8").read()
    esperado = {l.strip() for l in open(SNAPSHOT, encoding="utf-8")
                if l.strip() and not l.startswith("#")}

    schema = PREFIXO + datetime.now().strftime("%Y%m%d%H%M%S")
    import psycopg2

    con = psycopg2.connect(db.DATABASE_URL)
    con.autocommit = True
    falhou = False
    try:
        cur = con.cursor()
        print(f"[1/4] criando schema temporário {schema}")
        cur.execute(f'CREATE SCHEMA "{schema}"')

        print("[2/4] aplicando o baseline dentro dele")
        # search_path aponta para o schema novo: o baseline não qualifica nomes.
        cur.execute(f'SET search_path TO "{schema}"')
        cur.execute(sql)

        print("[3/4] comparando com o retrato de produção")
        cur.execute("""
            SELECT c.relname || '.' || a.attname
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
              JOIN pg_attribute a ON a.attrelid = c.oid
             WHERE n.nspname = %s AND c.relkind = 'r'
               AND a.attnum > 0 AND NOT a.attisdropped
        """, (schema,))
        obtido = {r[0] for r in cur.fetchall()}

        faltando = sorted(esperado - obtido)
        sobrando = sorted(obtido - esperado)
        tabelas = len({c.split(".")[0] for c in obtido})
        print(f"      recriado: {len(obtido)} colunas / {tabelas} tabelas")
        print(f"      esperado: {len(esperado)} colunas / "
              f"{len({c.split('.')[0] for c in esperado})} tabelas")

        if faltando:
            falhou = True
            print(f"\n  FALHOU — não foram recriadas ({len(faltando)}):")
            for c in faltando:
                print("   -", c)
        if sobrando:
            falhou = True
            print(f"\n  FALHOU — criadas a mais ({len(sobrando)}):")
            for c in sobrando:
                print("   +", c)
        if not falhou:
            print("\n  OK: o baseline recria o schema de produção integralmente.")
    except Exception as e:
        falhou = True
        print(f"\n  FALHOU ao aplicar o baseline: {type(e).__name__}: {e}",
              file=sys.stderr)
    finally:
        cur = con.cursor()
        if args.manter:
            print(f"[4/4] schema {schema} MANTIDO para inspeção — apague-o depois.")
        else:
            print(f"[4/4] apagando {schema}")
            _drop_seguro(cur, schema)
        con.close()

    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
