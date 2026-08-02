"""O código que roda na inicialização é válido nos DOIS bancos?

**Por que este arquivo existe.** Em 2026-08-02 a produção caiu com
`psycopg2.errors.SyntaxError`: `_backfill_animal_uuid` usava `PRAGMA table_info`,
que só existe no SQLite. A suíte inteira roda com `AGROTOP_FORCE_SQLITE=1` —
por design, para não tocar produção (R16/R18) — e por isso **nenhum dos 225
testes enxergava o caminho Postgres**. O defeito passou por CI verde, review e
merge.

Estes testes não conectam em Postgres: eles inspecionam o CÓDIGO à procura de
sintaxe de um dialeto só, em funções que rodam com `USE_PG=True`. É uma guarda
mais fraca que um banco de verdade, mas é a que cabe num CI sem Postgres — e
teria pego exatamente o defeito que derrubou a produção.
"""

import ast
import inspect
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402
from repositories import conexao  # noqa: E402

# Sintaxe que existe num banco e não no outro. O `_translate()` cobre só
# placeholder (`?` → `%s`) e `MAX(0,` → `GREATEST(0,`; o resto é por conta de quem escreve.
SO_SQLITE = ("PRAGMA ", "sqlite_master", "AUTOINCREMENT", "datetime('now'", "char(10)")
SO_POSTGRES = ("information_schema", "pg_index", "pg_attribute", "::regclass",
               "bigserial", "timestamptz", "jsonb", "chr(10)")


def _fontes_que_rodam_em_producao():
    """Funções de `database.py` que executam com `USE_PG=True`.

    `init_db` chama estas na inicialização, e é onde o app quebrou.
    """
    nomes = ["init_db", "_migrate", "_backfill_uuids", "_backfill_animal_uuid",
             "_backfill_identificadores", "_colunas"]
    for nome in nomes:
        fn = getattr(db, nome, None)
        if fn is not None:
            yield nome, inspect.getsource(fn)


def _tem_guarda_de_dialeto(fonte: str) -> bool:
    """A função se protege verificando `USE_PG` antes de usar sintaxe específica?"""
    return "USE_PG" in fonte


class TestSintaxeDeUmDialetoSo(unittest.TestCase):
    def test_funcoes_de_inicializacao_nao_usam_sintaxe_sqlite_sem_guarda(self):
        """Foi exatamente isto que derrubou a produção em 2026-08-02."""
        culpadas = []
        for nome, fonte in _fontes_que_rodam_em_producao():
            usadas = [t for t in SO_SQLITE if t in fonte]
            if usadas and not _tem_guarda_de_dialeto(fonte):
                culpadas.append(f"{nome}: usa {usadas} sem conferir USE_PG")
        self.assertEqual(culpadas, [], "\n".join(culpadas))

    def test_funcoes_de_inicializacao_nao_usam_sintaxe_postgres_sem_guarda(self):
        """O espelho: o SQLite também quebra com sintaxe que só o Postgres tem."""
        culpadas = []
        for nome, fonte in _fontes_que_rodam_em_producao():
            usadas = [t for t in SO_POSTGRES if t in fonte]
            if usadas and not _tem_guarda_de_dialeto(fonte):
                culpadas.append(f"{nome}: usa {usadas} sem conferir USE_PG")
        self.assertEqual(culpadas, [], "\n".join(culpadas))


class TestColunas(unittest.TestCase):
    """`_colunas` é o auxiliar criado para não repetir o erro."""

    def test_tem_os_dois_ramos(self):
        fonte = inspect.getsource(db._colunas)
        self.assertIn("USE_PG", fonte, "não confere o dialeto")
        self.assertIn("information_schema", fonte, "sem ramo Postgres")
        self.assertIn("PRAGMA", fonte, "sem ramo SQLite")

    def test_funciona_no_sqlite(self):
        with db._conn() as con:
            cols = db._colunas(con, "animals")
        self.assertIn("uuid", cols)
        self.assertIn("id", cols)
        self.assertNotIn("coluna_que_nao_existe", cols)

    def test_tabela_inexistente_devolve_vazio(self):
        """Não pode estourar: é usado para DECIDIR se a tabela tem a coluna."""
        with db._conn() as con:
            self.assertEqual(db._colunas(con, "tabela_inexistente"), set())


class TestTraducao(unittest.TestCase):
    """O que o `_translate()` cobre — e o que não cobre, que é a pegadinha."""

    def _como_postgres(self, sql):
        """Roda `_translate` no modo Postgres sem precisar de um Postgres.

        A tradução é decidida por `USE_PG`, que aqui está falso porque a suíte
        força SQLite. Trocar a bandeira só durante a chamada é o que permite
        testar o ramo que a produção usa.
        """
        original = conexao.USE_PG
        conexao.USE_PG = True
        try:
            return conexao._translate(sql)
        finally:
            conexao.USE_PG = original

    def test_converte_placeholder(self):
        self.assertIn("%s", self._como_postgres("SELECT * FROM t WHERE id=?"))

    def test_converte_max_zero(self):
        self.assertIn("GREATEST(0,", self._como_postgres("SET x = MAX(0, x - 1)"))

    def test_nao_converte_pragma(self):
        """Documenta o LIMITE: `_translate` não salva sintaxe de dialeto.

        Quem lê o código pode supor que a tradução resolve tudo. Ela cobre
        placeholder e uma função — nada além. Essa suposição custou uma queda
        de produção em 2026-08-02.
        """
        sql = "PRAGMA table_info(animals)"
        self.assertEqual(self._como_postgres(sql), sql,
                         "se um dia traduzir PRAGMA, atualize este teste e a guarda")

    def test_nao_traduz_nada_no_sqlite(self):
        sql = "SELECT * FROM t WHERE id=?"
        self.assertEqual(conexao._translate(sql), sql)


if __name__ == "__main__":
    unittest.main()
