"""
AgroTop — Migração de dados do SQLite local para o Postgres/Supabase (nuvem).

Uso (uma única vez, após configurar o DATABASE_URL):

    Windows PowerShell:
        $env:DATABASE_URL="postgresql://postgres.xxxx:SENHA@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
        python migrar_para_nuvem.py

O script copia todas as tabelas do arquivo agrotop.db para o banco na nuvem,
preservando acentos (UTF-8), e ajusta os contadores de ID automáticos.
É seguro rodar: se a nuvem já tiver dados, ele avisa antes de sobrescrever.
"""

import os
import sys
import sqlite3

TABLES = [
    "users", "fornecedores", "lotes", "insumos", "animals", "weighings",
    "medications", "animal_movements", "insumo_transactions", "animal_costs",
    "fixed_costs", "feeding_plans", "feeding_checks",
]
# Tabelas com id automático (BIGSERIAL) — o contador precisa ser reajustado
SERIAL_TABLES = [
    "users", "fornecedores", "insumos", "weighings", "medications",
    "animal_movements", "insumo_transactions", "animal_costs", "fixed_costs",
    "feeding_plans", "feeding_checks",
]


def main():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("[ERRO] Defina a variavel DATABASE_URL antes de rodar. Veja o topo deste arquivo.")
        sys.exit(1)

    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("[ERRO] Instale o driver:  python -m pip install psycopg2-binary")
        sys.exit(1)

    if not os.path.exists("agrotop.db"):
        print("[ERRO] agrotop.db nao encontrado nesta pasta.")
        sys.exit(1)

    lite = sqlite3.connect("agrotop.db")
    lite.row_factory = sqlite3.Row
    pg = psycopg2.connect(url)
    pgc = pg.cursor()

    # Verifica se a nuvem já tem animais
    pgc.execute("SELECT COUNT(*) FROM animals")
    if pgc.fetchone()[0] > 0:
        resp = input("[AVISO] A nuvem ja possui dados. Apagar tudo e reimportar? (digite SIM): ")
        if resp.strip().upper() != "SIM":
            print("Cancelado. Nada foi alterado.")
            return
    # Sempre limpa antes de importar, para permitir reexecucao sem conflitos
    for t in reversed(TABLES):
        pgc.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
    pg.commit()
    print("[OK] Tabelas da nuvem limpas.")

    total = 0
    for t in TABLES:
        try:
            rows = lite.execute(f"SELECT * FROM {t}").fetchall()
        except sqlite3.OperationalError:
            continue
        if not rows:
            continue
        cols = [c for c in rows[0].keys() if c != "created_at"]
        collist = ",".join(cols)
        placeholders = ",".join(["%s"] * len(cols))
        sql = f"INSERT INTO {t} ({collist}) VALUES ({placeholders})"
        data = [tuple(r[c] for c in cols) for r in rows]
        psycopg2.extras.execute_batch(pgc, sql, data)
        pg.commit()
        print(f"[OK] {t}: {len(rows)} registro(s)")
        total += len(rows)

    # Reajusta os contadores de ID automáticos
    for t in SERIAL_TABLES:
        try:
            pgc.execute(
                f"SELECT setval(pg_get_serial_sequence('{t}','id'), "
                f"COALESCE((SELECT MAX(id) FROM {t}), 1), true)"
            )
        except Exception:
            pg.rollback()
    pg.commit()

    print(f"\n[SUCESSO] Migracao concluida: {total} registros copiados para a nuvem.")
    lite.close()
    pg.close()


if __name__ == "__main__":
    main()
