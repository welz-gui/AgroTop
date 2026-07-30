#!/usr/bin/env python
"""Restaura um backup do AgroTop — o outro lado de tools/backup_banco.py.

**Um backup que nunca foi restaurado não é backup.** Este script existe para que a
recuperação seja um procedimento testado, não uma esperança.

COMO FUNCIONA
    1. Cria um schema no Postgres (por padrão, um schema de conferência descartável).
    2. Aplica supabase/migrations/0000_baseline_producao.sql para montar as tabelas.
       As chaves estrangeiras ficam para o fim — é por isso que o baseline as emite
       como ALTER separados: permite inserir os dados sem brigar com a ordem das FKs.
    3. Carrega os dados do backup.
    4. Confere as contagens contra o manifesto.

SEGURANÇA
    Por padrão restaura num schema **de conferência** (`restauracao_<carimbo>`), nunca
    por cima dos dados vivos. Assim você inspeciona antes de decidir qualquer coisa.
    Sobrescrever o schema `public` exige a flag explícita `--sobrescrever-public`, e
    ainda pede confirmação digitada.

USO
    python tools/restaurar_banco.py backups/agrotop_20260730_120000.zip
    python tools/restaurar_banco.py <arquivo> --schema conferencia_jan
    python tools/restaurar_banco.py <arquivo> --apagar-depois   # teste de recuperação

DEPOIS DE CONFERIR
    Para promover a restauração a dados vivos, o caminho seguro é renomear schemas
    (operação atômica), não copiar linha a linha:
        ALTER SCHEMA public RENAME TO public_antigo;
        ALTER SCHEMA <schema_restaurado> RENAME TO public;
    Guarde o `public_antigo` até ter certeza.
"""

import argparse
import base64
import json
import os
import sys
import zipfile
from datetime import datetime
from decimal import Decimal

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

BASELINE = os.path.join(RAIZ, "supabase", "migrations", "0000_baseline_producao.sql")
MARCA_FK = "-- Chaves estrangeiras"


def _desserializar(obj):
    if "__bytes_b64__" in obj:
        return base64.b64decode(obj["__bytes_b64__"])
    if "__decimal__" in obj:
        return Decimal(obj["__decimal__"])
    if "__datetime__" in obj:
        return datetime.fromisoformat(obj["__datetime__"])
    return obj


def _partir_baseline(sql: str) -> tuple[str, str]:
    """Separa a criação das tabelas da aplicação das FKs."""
    if MARCA_FK not in sql:
        return sql, ""
    i = sql.index(MARCA_FK)
    return sql[:i], sql[i:]


def restaurar(arquivo: str, schema: str, apagar_depois: bool,
              sobrescrever_public: bool) -> int:
    import database as db

    if not db.USE_PG:
        print("ERRO: este script restaura em Postgres. DATABASE_URL não configurada.",
              file=sys.stderr)
        return 1
    if not os.path.exists(BASELINE):
        print(f"ERRO: baseline não encontrado em {BASELINE}", file=sys.stderr)
        return 1

    if schema == "public" and not sobrescrever_public:
        print("ERRO: restaurar em `public` sobrescreveria os dados vivos.\n"
              "Use um schema de conferência (padrão) ou passe --sobrescrever-public.",
              file=sys.stderr)
        return 1
    if schema == "public":
        print("!! Você está prestes a restaurar POR CIMA DOS DADOS VIVOS em `public`.")
        if input("   Digite EU CONFIRMO para prosseguir: ").strip() != "EU CONFIRMO":
            print("cancelado.")
            return 1

    with zipfile.ZipFile(arquivo) as z:
        manifesto = json.loads(z.read("manifesto.json"))
        dados = {t: z.read(f"dados/{t}.jsonl").decode("utf-8")
                 for t in manifesto["tabelas"]}

    print(f"backup de {manifesto['gerado_em']} · {manifesto['total_registros']} "
          f"registros em {len(manifesto['tabelas'])} tabelas")

    tabelas_sql, fks_sql = _partir_baseline(open(BASELINE, encoding="utf-8").read())

    import psycopg2
    con = psycopg2.connect(db.DATABASE_URL)
    con.autocommit = False
    inseridos: dict[str, int] = {}
    try:
        cur = con.cursor()
        print(f"[1/4] criando schema {schema}")
        cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        cur.execute(f'SET search_path TO "{schema}"')

        print("[2/4] montando as tabelas a partir do baseline")
        cur.execute(tabelas_sql)

        print("[3/4] carregando os dados")
        for tabela, bruto in dados.items():
            linhas = [json.loads(l, object_hook=_desserializar)
                      for l in bruto.split("\n") if l.strip()]
            if not linhas:
                inseridos[tabela] = 0
                continue
            colunas = list(linhas[0].keys())
            marcadores = ",".join(["%s"] * len(colunas))
            alvo = ",".join(f'"{c}"' for c in colunas)
            cur.executemany(
                f'INSERT INTO "{tabela}" ({alvo}) VALUES ({marcadores})',
                [tuple(l.get(c) for c in colunas) for l in linhas])
            inseridos[tabela] = len(linhas)
            print(f"  {tabela:24} {len(linhas):>7} registros")

        if fks_sql.strip():
            cur.execute(fks_sql)
        con.commit()

        print("[4/4] conferindo contra o manifesto")
        divergencias = [f"{t}: manifesto {n} × restaurado {inseridos.get(t, 0)}"
                        for t, n in manifesto["tabelas"].items()
                        if inseridos.get(t, 0) != n]
        if divergencias:
            print("  FALHOU — contagens divergentes:", file=sys.stderr)
            for d in divergencias:
                print("   -", d, file=sys.stderr)
            return 1
        print(f"  [ok] {sum(inseridos.values())} registros restaurados e conferidos")
        print(f"\nSchema `{schema}` pronto para inspeção.")
        return 0

    except Exception as e:
        con.rollback()
        print(f"\nFALHOU: {type(e).__name__}: {e}", file=sys.stderr)
        print("Nada foi commitado — a transação inteira foi desfeita.", file=sys.stderr)
        return 1
    finally:
        if apagar_depois:
            try:
                con.autocommit = True
                if not schema.startswith("public"):
                    con.cursor().execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                    print(f"[limpeza] schema {schema} removido (--apagar-depois)")
            except Exception as e:      # noqa: BLE001
                print(f"[aviso] não consegui remover {schema}: {e}", file=sys.stderr)
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("arquivo", help="backup .zip a restaurar")
    ap.add_argument("--schema", default=None,
                    help="schema de destino (padrão: restauracao_<carimbo>)")
    ap.add_argument("--apagar-depois", action="store_true",
                    help="remover o schema ao final — use para TESTAR a recuperação")
    ap.add_argument("--sobrescrever-public", action="store_true",
                    help="permite --schema public (dados vivos); pede confirmação")
    args = ap.parse_args()

    if not os.path.exists(args.arquivo):
        print(f"ERRO: {args.arquivo} não encontrado", file=sys.stderr)
        return 1

    schema = args.schema or f"restauracao_{datetime.now():%Y%m%d_%H%M%S}"
    return restaurar(args.arquivo, schema, args.apagar_depois,
                     args.sobrescrever_public)


if __name__ == "__main__":
    raise SystemExit(main())
