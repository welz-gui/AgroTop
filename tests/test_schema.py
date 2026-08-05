"""Guardas de integridade do schema — fonte única de verdade.

Contexto (ver docs/adr/0001-multi-fazenda-schema-por-tenant.md): o schema já foi
definido em quatro mecanismos diferentes ao mesmo tempo, e a divergência entre eles
causou bugs reais:

  - `protocol_id` / `lote_id` existiam apenas como ALTER em `_migrate()` e faltavam
    no CREATE TABLE → `init_db()` quebrava em banco novo (corrigido em 75dce18).
  - `sessions` era criada sob demanda dentro de três funções → banco novo ficava sem
    a tabela até o primeiro login (corrigido em 599162a).

Estes testes rodam offline, sem credenciais, e falham se a classe de bug voltar.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from importlib.abc import MetaPathFinder

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class _BloqueiaStreamlit(MetaPathFinder):
    """Impede que `st.secrets` aponte o teste para o banco de produção."""

    def find_spec(self, name, path=None, target=None):
        if name == "streamlit" or name.startswith("streamlit."):
            raise ImportError("streamlit bloqueado no teste de schema")
        return None


def _schema_sqlite_novo():
    """Cria um SQLite do zero via init_db() e devolve (módulo, caminho, colunas)."""
    sys.meta_path.insert(0, _BloqueiaStreamlit())
    # O estado de import é global: o que este teste tira de `sys.modules` some
    # para TODA a suíte. Guardar antes é o que permite devolver depois.
    salvos = {k: v for k, v in sys.modules.items() if k.startswith("streamlit")}
    salvos["database"] = sys.modules.get("database")
    try:
        for m in [k for k in list(sys.modules) if k.startswith("streamlit")]:
            del sys.modules[m]
        os.environ.pop("DATABASE_URL", None)
        for m in ("database",):
            sys.modules.pop(m, None)
        import database as db

        assert not db.USE_PG, "o teste precisa rodar em SQLite, não em produção"
        caminho = os.path.join(tempfile.mkdtemp(), "schema_guard.db")
        db.configurar_sqlite(caminho)
        db.init_db()
        return db, caminho, _colunas(caminho)
    finally:
        sys.meta_path[:] = [f for f in sys.meta_path
                            if not isinstance(f, _BloqueiaStreamlit)]
        # Devolve `database` e `streamlit` como estavam. Sem isto, todo módulo
        # de teste que rode DEPOIS deste continua apontando para o `database`
        # antigo enquanto o `streamlit` do processo é outro — e o cache passa a
        # tentar picklar `sqlite3.Row`, quebrando testes que nada têm a ver com
        # schema. Ficou latente porque nenhum módulo existente vinha depois de
        # `test_schema` na ordem alfabética; o primeiro a vir quebrou.
        for m in [k for k in list(sys.modules) if k.startswith("streamlit")]:
            del sys.modules[m]
        for nome, modulo in salvos.items():
            if modulo is not None:
                sys.modules[nome] = modulo
            else:
                sys.modules.pop(nome, None)


def _colunas(caminho):
    con = sqlite3.connect(caminho)
    try:
        return {
            f"{t}.{r[1]}"
            for (t,) in con.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            for r in con.execute(f"PRAGMA table_info({t})")
        }
    finally:
        con.close()


class TestDDLCompleto(unittest.TestCase):
    def test_ddl_completo_sem_depender_do_migrate(self):
        """O CREATE TABLE precisa ser completo por si só.

        `init_db()` chama `_migrate()` no final, então não basta comparar o schema
        depois dele: é preciso neutralizar o `_migrate` durante a criação e só então
        verificar se ele ainda teria algo a adicionar. Se tiver, o CREATE TABLE está
        incompleto e o schema depende de dois mecanismos — foi essa divergência que
        quebrou o `init_db()` em banco novo (75dce18).

        `_migrate()` deve existir apenas para bancos SQLite antigos, nunca para
        completar o schema de uma instalação nova.
        """
        db, caminho, _ = _schema_sqlite_novo()

        # Recria o banco com o _migrate neutralizado: sobra só o DDL puro.
        os.remove(caminho)
        real_migrate = db._migrate
        db._migrate = lambda con: None
        try:
            db.init_db()
            so_ddl = _colunas(caminho)
        finally:
            db._migrate = real_migrate

        # Agora aplica o _migrate de verdade e vê se ele tinha algo a fazer.
        with db._conn() as con:
            db._migrate(con)
        com_migrate = _colunas(caminho)

        faltando = com_migrate - so_ddl
        self.assertEqual(
            faltando, set(),
            "estas colunas existem apenas como ALTER em _migrate() e faltam no "
            "CREATE TABLE do init_db(): " + ", ".join(sorted(faltando)))

    def test_init_db_e_idempotente(self):
        """Rodar init_db() duas vezes não pode falhar nem alterar o schema."""
        db, caminho, antes = _schema_sqlite_novo()
        db.init_db()  # segunda vez
        self.assertEqual(_colunas(caminho), antes,
                         "init_db() não é idempotente — o schema mudou na 2ª execução")


class TestFonteUnicaDeVerdade(unittest.TestCase):
    def test_create_table_apenas_no_ddl_canonico(self):
        """`CREATE TABLE` só pode aparecer dentro do executescript de init_db().

        Criar tabela sob demanda dentro de funções (como `sessions` fazia) deixa
        bancos novos incompletos e espalha a definição do schema.
        """
        with open(os.path.join(ROOT, "database.py"), encoding="utf-8") as fh:
            linhas = fh.readlines()

        # Faixa de linhas do executescript dentro de init_db().
        ini = fim = None
        for n, linha in enumerate(linhas, 1):
            if linha.lstrip().startswith("def init_db"):
                ini = n
            elif ini and fim is None and linha.lstrip().startswith("_migrate("):
                fim = n
        self.assertIsNotNone(ini, "init_db() não encontrado em database.py")
        self.assertIsNotNone(fim, "fim do DDL de init_db() não identificado")

        def _e_comentario(linha: str) -> bool:
            """Comentário Python (#) ou SQL (--) — documentação, não instrução.

            Sem isto, o teste acusa qualquer comentário que *mencione* CREATE
            TABLE, o que aconteceu ao documentar a migração da chave surrogate.
            """
            t = linha.strip()
            return t.startswith("#") or t.startswith("--")

        fora = [f"linha {n}: {l.strip()[:70]}"
                for n, l in enumerate(linhas, 1)
                if "CREATE TABLE" in l.upper()
                and not _e_comentario(l)
                and not (ini <= n <= fim)]

        self.assertEqual(
            fora, [],
            "CREATE TABLE fora do DDL canônico de init_db(). Mova a definição para "
            "lá — ver o caso de `sessions`. Ocorrências: " + "; ".join(fora))

    def test_schema_local_nao_divergiu_da_producao(self):
        """O DDL local deve ser subconjunto do snapshot de produção.

        `docs/schema-nuvem.txt` é o retrato do Postgres de produção. Uma coluna que
        exista só no local significa que a migration correspondente não foi aplicada
        na nuvem — e o app quebraria em produção.
        """
        snapshot = os.path.join(ROOT, "docs", "schema-nuvem.txt")
        if not os.path.exists(snapshot):
            self.skipTest("docs/schema-nuvem.txt ausente")

        with open(snapshot, encoding="utf-8") as fh:
            nuvem = {l.strip() for l in fh
                     if l.strip() and not l.startswith("#")}

        _, _, local = _schema_sqlite_novo()

        so_local = sorted(local - nuvem)
        self.assertEqual(
            so_local, [],
            "colunas existem no DDL local mas NÃO em produção — falta aplicar a "
            "migration no Supabase e regenerar docs/schema-nuvem.txt "
            "(tools/dump_schema_nuvem.py): " + ", ".join(so_local))


if __name__ == "__main__":
    unittest.main()
