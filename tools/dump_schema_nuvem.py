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
    colunas, constraints, índices, **funções e triggers** — mas NÃO políticas de
    RLS, grants, sequences órfãs ou extensões.

    ⚠️ Funções e triggers passaram a ser capturados em 2026-08-03. Antes disso o
    baseline recriava `animal_events` e `audit_logs` **sem os gatilhos
    append-only** — quem restaurasse a partir dele teria as duas graváveis e
    apagáveis, perdendo a garantia que a etapa B2 existe para dar. O
    `testar_baseline.py` dizia "OK" porque comparava apenas colunas. Quando houver `pg_dump` ou o Supabase
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


Q_FUNCOES = """
SELECT p.proname AS nome,
       pg_get_functiondef(p.oid) AS definicao
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = 'public' AND p.prokind = 'f'
 ORDER BY p.proname;
"""

Q_TRIGGERS = """
SELECT c.relname AS tabela, t.tgname AS nome,
       pg_get_triggerdef(t.oid) AS definicao
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND NOT t.tgisinternal
 ORDER BY c.relname, t.tgname;
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


def _colunas_da_constraint(definicao: str) -> str:
    """Lista de colunas de um PRIMARY KEY/UNIQUE, normalizada para comparação.

    `pg_get_constraintdef` devolve "PRIMARY KEY (uuid)" e "UNIQUE (uuid)"; o que
    interessa é só o miolo entre parênteses.
    """
    ini, fim = definicao.find("("), definicao.rfind(")")
    if ini < 0 or fim <= ini:
        return ""
    return ",".join(parte.strip() for parte in definicao[ini + 1:fim].split(","))


def _redundante_com_a_pk(con: dict, definicao_pk: str | None) -> bool:
    """UNIQUE sobre exatamente as mesmas colunas da PRIMARY KEY.

    ⚠️ Declarada INLINE, junto da PK no mesmo `CREATE TABLE`, o PostgreSQL
    **descarta essa constraint em silêncio** — sem erro, sem aviso. Foi o que
    fez a migration 0027 falhar no replay em 2026-08-29: o baseline declarava
    `animals_uuid_key UNIQUE (uuid)` ao lado de `animals_pkey PRIMARY KEY
    (uuid)`, a constraint nunca nascia, e o `DROP CONSTRAINT` da 0027 então
    reclamava que ela não existia. Medido em PG16 no CI (2026-08-31).

    Por `ALTER TABLE ADD CONSTRAINT` separado o Postgres cria normalmente — que
    é como produção chegou a ter as duas (a 0005 promoveu `idx_animals_uuid` a
    UNIQUE muito antes de a 0017 tornar `uuid` a PK). Por isso estas saem do
    `CREATE TABLE` e viram ALTER: é o que faz o replay reproduzir produção.
    """
    if definicao_pk is None or con["tipo"] != "u":
        return False
    return _colunas_da_constraint(con["definicao"]) == _colunas_da_constraint(definicao_pk)


def escrever_baseline(colunas, constraints, indices, data,
                      funcoes=None, triggers=None):
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
        fh.write("-- NÃO cobre: políticas de RLS, grants, extensões.\n")
        fh.write("-- Para um dump completo, prefira `supabase db dump` ou `pg_dump`.\n")
        fh.write("--\n-- SEM QUALIFICAÇÃO DE SCHEMA de propósito: os nomes são resolvidos\n")
        fh.write("-- pelo search_path, para que o mesmo arquivo sirva a qualquer tenant\n")
        fh.write("-- (ver docs/adr/0001-multi-fazenda-schema-por-tenant.md). Aplicar com:\n")
        fh.write("--     CREATE SCHEMA fazenda_2;  SET search_path TO fazenda_2;\n")
        fh.write("--     \\i supabase/migrations/0000_baseline_producao.sql\n")
        fh.write("-- Validar com: python tools/testar_baseline.py\n\n")

        fks = []
        unicas_redundantes = []
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
            definicao_pk = next((c["definicao"] for c in cons_por_tabela.get(tabela, [])
                                 if c["tipo"] == "p"), None)
            for con in cons_por_tabela.get(tabela, []):
                if con["tipo"] == "f":
                    fks.append((tabela, con))
                elif _redundante_com_a_pk(con, definicao_pk):
                    unicas_redundantes.append((tabela, con))
                else:
                    partes.append(f"    CONSTRAINT {con['nome']} {con['definicao']}")
            fh.write(",\n".join(partes))
            fh.write("\n);\n\n")

        if unicas_redundantes:
            fh.write("-- UNIQUE sobre as mesmas colunas da PRIMARY KEY. Fora do\n")
            fh.write("-- CREATE TABLE de propósito: declarada inline, o PostgreSQL\n")
            fh.write("-- descarta em silêncio, e o replay deixa de reproduzir a\n")
            fh.write("-- produção (ver _redundante_com_a_pk neste arquivo).\n")
            for tabela, con in unicas_redundantes:
                fh.write(f"ALTER TABLE {tabela} "
                         f"ADD CONSTRAINT {con['nome']} {con['definicao']};\n")
            fh.write("\n")

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

        # Funções antes dos triggers: o trigger referencia a função.
        #
        # A qualificação `public.` é removida das duas, pelo mesmo motivo dos
        # índices: quem resolve o nome é o search_path. Sem isso, aplicar o
        # baseline num schema novo criaria a função dentro de `public` — efeito
        # colateral no schema de produção — e o trigger não a encontraria no
        # schema onde está sendo criado.
        if funcoes:
            fh.write("-- Funções\n")
            for f in funcoes:
                definicao = f["definicao"].replace("FUNCTION public.", "FUNCTION ", 1)
                fh.write(f"{definicao};\n\n")

        if triggers:
            fh.write("-- Triggers\n")
            fh.write("-- Sem eles, `animal_events` e `audit_logs` deixam de ser\n")
            fh.write("-- append-only (PNIB §6.3 e §14.1).\n")
            for t in triggers:
                definicao = t["definicao"].replace(" ON public.", " ON ")
                fh.write(f"DROP TRIGGER IF EXISTS {t['nome']} ON {t['tabela']};\n")
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
        funcoes = _linhas(con, Q_FUNCOES)
        triggers = _linhas(con, Q_TRIGGERS)
    finally:
        con.close()

    n = escrever_snapshot(colunas, hoje)
    tabelas = len({c["tabela"] for c in colunas})
    print(f"[ok] {os.path.relpath(SNAPSHOT, RAIZ)}: {n} colunas / {tabelas} tabelas")

    if args.baseline:
        t = escrever_baseline(colunas, constraints, indices, hoje,
                              funcoes, triggers)
        print(f"[ok] {os.path.relpath(BASELINE, RAIZ)}: {t} tabelas, "
              f"{len(constraints)} constraints, {len(indices)} índices, "
              f"{len(funcoes)} funções, {len(triggers)} triggers")

    print("\nConfira o diff antes de commitar: git diff docs/ supabase/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
