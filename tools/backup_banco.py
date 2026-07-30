#!/usr/bin/env python
"""Backup completo do banco do AgroTop para uma pasta local.

POR QUE EXISTE
    O projeto está no plano free do Supabase, que **não oferece point-in-time
    recovery**. Sem uma cópia local, um erro de migration ou uma exclusão acidental
    não têm volta. Ver ROADMAP.md R26.

O QUE GERA
    backups/agrotop_AAAAMMDD_HHMMSS.zip contendo:
      manifesto.json     data, backend, versão do schema, contagem por tabela
      dados/<tabela>.jsonl   uma linha JSON por registro

    Campos binários (as fotos dos animais, em bytea) são gravados em base64, então
    o backup é COMPLETO — diferente do backup em Excel do app, que omite fotos
    de propósito.

CONSISTÊNCIA
    Tudo é lido numa única transação REPEATABLE READ / somente leitura. Assim o
    retrato é coerente mesmo que alguém esteja usando o sistema durante o backup.

USO
    python tools/backup_banco.py                 # backup + rotação (mantém 30)
    python tools/backup_banco.py --manter 90
    python tools/backup_banco.py --destino D:/backups_agrotop
    python tools/backup_banco.py --verificar backups/agrotop_20260730_120000.zip

    Para restaurar: tools/restaurar_banco.py

⚠️ O arquivo gerado contém TODOS os dados, inclusive os hashes de senha dos
   usuários. A pasta `backups/` está no .gitignore — mantenha assim, e guarde uma
   cópia fora desta máquina.
"""

import argparse
import base64
import json
import os
import sys
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

DESTINO_PADRAO = os.path.join(RAIZ, "backups")


def _serializar(valor):
    """Converte tipos do banco para algo que o JSON aceite, sem perder informação."""
    if isinstance(valor, (bytes, bytearray, memoryview)):
        return {"__bytes_b64__": base64.b64encode(bytes(valor)).decode("ascii")}
    if isinstance(valor, Decimal):
        return {"__decimal__": str(valor)}
    if isinstance(valor, (datetime, date)):
        return {"__datetime__": valor.isoformat()}
    raise TypeError(f"tipo não suportado no backup: {type(valor).__name__}")


def _tabelas(cur, usa_pg: bool) -> list[str]:
    if usa_pg:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "ORDER BY tablename")
    else:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name")
    return [r[0] for r in cur.fetchall()]


def fazer_backup(destino: str, manter: int) -> str:
    import database as db

    os.makedirs(destino, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = os.path.join(destino, f"agrotop_{carimbo}.zip")

    if db.USE_PG:
        import psycopg2
        con = psycopg2.connect(db.DATABASE_URL)
        con.set_session(isolation_level="REPEATABLE READ", readonly=True)
        backend = "postgres"
    else:
        import sqlite3
        con = sqlite3.connect(db.DB_PATH)
        backend = f"sqlite ({os.path.basename(db.DB_PATH)})"

    contagem: dict[str, int] = {}
    try:
        cur = con.cursor()
        tabelas = _tabelas(cur, db.USE_PG)
        if not tabelas:
            raise RuntimeError("nenhuma tabela encontrada — banco vazio ou errado?")

        with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
            for tabela in tabelas:
                cur.execute(f'SELECT * FROM "{tabela}"')
                colunas = [d[0] for d in cur.description]
                linhas = []
                for registro in cur.fetchall():
                    obj = dict(zip(colunas, registro))
                    linhas.append(json.dumps(obj, default=_serializar,
                                             ensure_ascii=False))
                contagem[tabela] = len(linhas)
                z.writestr(f"dados/{tabela}.jsonl", "\n".join(linhas))
                print(f"  {tabela:24} {len(linhas):>7} registros")

            manifesto = {
                "gerado_em": datetime.now(timezone.utc).isoformat(),
                "backend": backend,
                "tabelas": contagem,
                "total_registros": sum(contagem.values()),
                "formato": 1,
                "observacao": ("Contém dados sensíveis, inclusive hashes de senha. "
                               "Restaurar com tools/restaurar_banco.py."),
            }
            z.writestr("manifesto.json",
                       json.dumps(manifesto, indent=2, ensure_ascii=False))
    finally:
        con.close()

    tam = os.path.getsize(caminho) / 1024 / 1024
    print(f"\n[ok] {os.path.relpath(caminho, RAIZ)} "
          f"({tam:.1f} MB, {sum(contagem.values())} registros em {len(contagem)} tabelas)")

    _rotacionar(destino, manter)
    return caminho


def _rotacionar(destino: str, manter: int) -> None:
    if manter <= 0:
        return
    arquivos = sorted(f for f in os.listdir(destino)
                      if f.startswith("agrotop_") and f.endswith(".zip"))
    excedente = arquivos[:-manter] if len(arquivos) > manter else []
    for f in excedente:
        os.remove(os.path.join(destino, f))
    if excedente:
        print(f"[ok] rotação: {len(excedente)} backup(s) antigo(s) removido(s), "
              f"mantendo os {manter} mais recentes")


def verificar(caminho: str) -> bool:
    """Confere se o arquivo abre, tem manifesto e bate com as contagens gravadas."""
    print(f"verificando {os.path.relpath(caminho, RAIZ)}")
    try:
        with zipfile.ZipFile(caminho) as z:
            ruim = z.testzip()
            if ruim:
                print(f"  FALHOU: arquivo corrompido em {ruim}", file=sys.stderr)
                return False
            manifesto = json.loads(z.read("manifesto.json"))
            divergencias = []
            for tabela, esperado in manifesto["tabelas"].items():
                bruto = z.read(f"dados/{tabela}.jsonl").decode("utf-8")
                obtido = len([l for l in bruto.split("\n") if l.strip()])
                if obtido != esperado:
                    divergencias.append(f"{tabela}: manifesto {esperado} × arquivo {obtido}")
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as e:
        print(f"  FALHOU: {type(e).__name__}: {e}", file=sys.stderr)
        return False

    if divergencias:
        print("  FALHOU — contagens divergentes:", file=sys.stderr)
        for d in divergencias:
            print("   -", d, file=sys.stderr)
        return False

    print(f"  [ok] gerado em {manifesto['gerado_em']} · backend {manifesto['backend']}")
    print(f"  [ok] {manifesto['total_registros']} registros em "
          f"{len(manifesto['tabelas'])} tabelas — íntegro")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--destino", default=DESTINO_PADRAO,
                    help="pasta de destino (padrão: backups/)")
    ap.add_argument("--manter", type=int, default=30,
                    help="quantos backups manter; 0 desliga a rotação (padrão: 30)")
    ap.add_argument("--verificar", metavar="ARQUIVO",
                    help="apenas verificar a integridade de um backup existente")
    args = ap.parse_args()

    if args.verificar:
        return 0 if verificar(args.verificar) else 1

    caminho = fazer_backup(args.destino, args.manter)
    # Um backup que não foi verificado não conta como backup.
    return 0 if verificar(caminho) else 1


if __name__ == "__main__":
    raise SystemExit(main())
