#!/usr/bin/env python
"""Extrai o schema real do Postgres de produção para dentro do repositório.

POR QUE ISSO EXISTE
    O schema do AgroTop já esteve definido em vários lugares ao mesmo tempo
    (DDL do init_db, migrations aplicadas só na nuvem, CREATE TABLE dentro de
    funções), e a divergência entre eles causou bugs reais. Ver
    docs/adr/0001-multi-fazenda-schema-por-tenant.md.

    Além disso, a estratégia de uma fazenda por schema depende de conseguir
    recriar o schema do zero de forma repetível — o que exige o DDL versionado
    em git, não apenas aplicado no servidor.

O QUE GERA
    docs/schema-nuvem.txt
        Retrato simples (uma linha por "tabela.coluna"). Serve para o teste
        tests/test_schema.py comparar o DDL local com a produção e para a
        divergência aparecer em diff de git.

    supabase/migrations/0000_baseline_producao.sql   (com --baseline)
        DDL reconstruído do catálogo: CREATE TABLE com tipos, defaults e
        nullability, mais constraints e índices. Ponto de partida para recriar
        o schema num tenant novo.

COMO USAR
    # precisa de DATABASE_URL (env var) ou .streamlit/secrets.toml
    python tools/dump_schema_nuvem.py
    python tools/dump_schema_nuvem.py --baseline

AVISO SOBRE FIDELIDADE
    O baseline é reconstruído do catálogo, não é um `pg_dump`. Cobre tabelas,
    colunas, constraints e índices — mas NÃO triggers, funções, políticas de RLS,
    grants, sequences órfãs ou extensões. Quando houver `pg_dump` ou o Supabase
    CLI disponível, prefira:
        supabase db dump -f supabase/migrations/0000_baseline_producao.sql
    Este script é o caminho alternativo para quando nenhum dos dois existe.
"""

import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

SNAPSHOT = os.path.join(RAIZ, "docs", "schema-nuvem.txt")
BASELINE = os.path.join(RAIZ, "supabase", "migrations", "0000_baseline_producao.sql")

Q_COLUNAS = """
SELECT c.relname AS tabela,
       a.attname AS coluna,
       format_type(a.atttypid, a.atttypmod) AS tipo,
       a.attnotnull AS obrigatorio,
       pg_get_expr(d.adbin, d.adrelid) AS padrao
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_attribute a ON a.attrelid = c.oid
  LEFT JOIN pg_attrdef d ON d.adrelid = c.oid AND d.adnum = a.attnum
 WHERE n.nspname = 'public' AND c.relkind = 'r'
   AND a.attnum > 0 AND NOT a.attisdropped
 ORDER BY c.relname, a.attnum;
"""

Q_CONSTRAINTS = """
SELECT c.relname AS tabela, con.conname AS nome,
       pg_get_constraintdef(con.oid) AS definicao, con.contype AS tipo
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public'
 ORDER BY c.relname, (con.contype <> 'p'), con.conname;
"""

Q_INDICES = """
SELECT tablename AS tabela, indexname AS nome, indexdef AS definicao
  FROM pg_indexes
 WHERE schemaname = 'public'
   AND indexname NOT IN (SELECT conname FROM pg_constraint)
 ORDER BY tablename, indexname;
"""


def _linhas(con, sql):
    cur = con.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    out = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()
    return out


def escrever_snapshot(colunas, data):
    os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
    with open(SNAPSHOT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Snapshot do schema de PRODUÇÃO (Supabase/Postgres, schema `public`)\n")
        fh.write(f"# Extraído em {data} por tools/dump_schema_nuvem.py\n#\n")
        fh.write("# Propósito: tornar a divergência entre nuvem e DDL local VISÍVEL em\n")
        fh.write("# diff de git, e servir de referência para tests/test_schema.py.\n")
        fh.write("# Não é uma migration — é um retrato. Regenerar após cada migration.\n#\n")
        fh.write('# formato: uma linha por coluna, "tabela.coluna", na ordem ordinal.\n\n')
        for c in colunas:
            fh.write(f"{c['tabela']}.{c['coluna']}\n")
    return len(colunas)


def escrever_baseline(colunas, constraints, indices, data):
    por_tabela = {}
    for c in colunas:
        por_tabela.setdefault(c["tabela"], []).append(c)

    cons_por_tabela = {}
    for c in constraints:
        cons_por_tabela.setdefault(c["tabela"], []).append(c)

    os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
    with open(BASELINE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("-- Baseline do schema de produção do AgroTop\n")
        fh.write(f"-- Gerado em {data} por tools/dump_schema_nuvem.py\n")
        fh.write("--\n-- GERADO AUTOMATICAMENTE a partir do catálogo do Postgres.\n")
        fh.write("-- NÃO cobre: triggers, funções, políticas de RLS, grants, extensões.\n")
        fh.write("-- Para um dump completo, prefira `supabase db dump` ou `pg_dump`.\n")
        fh.write("--\n-- SEM QUALIFICAÇÃO DE SCHEMA de propósito: os nomes são resolvidos\n")
        fh.write("-- pelo search_path, para que o mesmo arquivo sirva a qualquer tenant\n")
        fh.write("-- (ver docs/adr/0001-multi-fazenda-schema-por-tenant.md). Aplicar com:\n")
        fh.write("--     CREATE SCHEMA fazenda_2;  SET search_path TO fazenda_2;\n")
        fh.write("--     \\i supabase/migrations/0000_baseline_producao.sql\n")
        fh.write("-- Validar com: python tools/testar_baseline.py\n\n")

        fks = []
        for tabela in sorted(por_tabela):
            fh.write(f"CREATE TABLE IF NOT EXISTS {tabela} (\n")
            partes = []
            for c in por_tabela[tabela]:
                tipo, padrao = c["tipo"], c["padrao"]
                # `nextval(...)` depende de uma sequence que este arquivo não cria.
                # Traduz para serial/bigserial, que cria a sequence junto.
                if padrao and padrao.startswith("nextval("):
                    tipo = {"bigint": "bigserial", "integer": "serial",
                            "smallint": "smallserial"}.get(tipo, tipo)
                    padrao = None
                linha = f"    {c['coluna']} {tipo}"
                if padrao:
                    linha += f" DEFAULT {padrao}"
                # serial já implica NOT NULL
                if c["obrigatorio"] and not tipo.endswith("serial"):
                    linha += " NOT NULL"
                partes.append(linha)
            # PK/UNIQUE/CHECK ficam inline; FK sai para o fim do arquivo, porque
            # a ordem alfabética das tabelas não respeita a dependência entre elas.
            for con in cons_por_tabela.get(tabela, []):
                if con["tipo"] == "f":
                    fks.append((tabela, con))
                else:
                    partes.append(f"    CONSTRAINT {con['nome']} {con['definicao']}")
            fh.write(",\n".join(partes))
            fh.write("\n);\n\n")

        if fks:
            fh.write("-- Chaves estrangeiras aplicadas ao final: assim a ordem de\n")
            fh.write("-- criação das tabelas acima não importa.\n")
            for tabela, con in fks:
                fh.write(f"ALTER TABLE {tabela} "
                         f"ADD CONSTRAINT {con['nome']} {con['definicao']};\n")
            fh.write("\n")

        if indices:
            fh.write("-- Índices (fora das constraints)\n")
            for i in indices:
                definicao = i["definicao"].replace(
                    "CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1).replace(
                    "CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ", 1)
                # remove a qualificação de schema: quem resolve é o search_path
                definicao = definicao.replace(" ON public.", " ON ")
                fh.write(f"{definicao};\n")
            fh.write("\n")
    return len(por_tabela)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--baseline", action="store_true",
                    help="também gerar supabase/migrations/0000_baseline_producao.sql")
    args = ap.parse_args()

    import database as db

    if not db.USE_PG:
        print("ERRO: DATABASE_URL não configurada — este script lê o Postgres de "
              "produção.\nDefina a env var ou use .streamlit/secrets.toml.",
              file=sys.stderr)
        return 1

    import psycopg2
    from datetime import date

    hoje = date.today().isoformat()
    con = psycopg2.connect(db.DATABASE_URL)
    try:
        colunas = _linhas(con, Q_COLUNAS)
        constraints = _linhas(con, Q_CONSTRAINTS)
        indices = _linhas(con, Q_INDICES)
    finally:
        con.close()

    n = escrever_snapshot(colunas, hoje)
    tabelas = len({c["tabela"] for c in colunas})
    print(f"[ok] {os.path.relpath(SNAPSHOT, RAIZ)}: {n} colunas / {tabelas} tabelas")

    if args.baseline:
        t = escrever_baseline(colunas, constraints, indices, hoje)
        print(f"[ok] {os.path.relpath(BASELINE, RAIZ)}: {t} tabelas, "
              f"{len(constraints)} constraints, {len(indices)} índices")

    print("\nConfira o diff antes de commitar: git diff docs/ supabase/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
