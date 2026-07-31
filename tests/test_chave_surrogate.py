"""Guardas da chave surrogate de `animals` (ADR 0004, etapa B1).

O PNIB §4.1 exige identificador interno **imutável e separado do brinco**: trocar
o brinco não pode trocar a identidade do animal. Hoje `animals.id` ainda é o
brinco e ainda é a PK — a migração acontece por etapas, e estes testes travam o
que já foi conquistado em cada uma.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402
from repositories.animais import novo_uuid  # noqa: E402


class BaseSurrogate(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "surrogate.db"))
        db.init_db()
        db.clear_cache()

    def _linhas(self, sql, args=()):
        con = sqlite3.connect(db.DB_PATH)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args).fetchall()]
        finally:
            con.close()


class TestUuidGerado(BaseSurrogate):
    def test_todo_animal_tem_uuid(self):
        """Nenhum animal pode ficar sem identificador interno — nem os de seed."""
        sem = self._linhas("SELECT id FROM animals WHERE uuid IS NULL OR uuid=''")
        self.assertEqual(sem, [], f"animais sem uuid: {[a['id'] for a in sem]}")

    def test_uuid_e_unico(self):
        linhas = self._linhas("SELECT uuid FROM animals")
        valores = [l["uuid"] for l in linhas]
        self.assertEqual(len(valores), len(set(valores)), "há uuid repetido")

    def test_animal_novo_nasce_com_uuid(self):
        db.add_animal("SURR1", "Nelore", "M", None, "2026-01-01",
                      300.0, 500.0, 0.0, None, None)
        a = self._linhas("SELECT uuid FROM animals WHERE id=?", ("SURR1",))[0]
        self.assertTrue(a["uuid"], "add_animal não gerou uuid")

    def test_backfill_e_idempotente(self):
        """Rodar de novo não pode reescrever uuid já atribuído.

        Se reescrevesse, o identificador deixaria de ser imutável — que é
        exatamente o que o §4.1 exige dele.
        """
        antes = {l["id"]: l["uuid"] for l in self._linhas("SELECT id, uuid FROM animals")}
        with db._conn() as con:
            alterados = db._backfill_uuids(con)
        depois = {l["id"]: l["uuid"] for l in self._linhas("SELECT id, uuid FROM animals")}
        self.assertEqual(alterados, 0, "backfill mexeu em quem já tinha uuid")
        self.assertEqual(antes, depois)

    def test_backfill_preenche_quem_esta_sem(self):
        con = sqlite3.connect(db.DB_PATH)
        con.execute("UPDATE animals SET uuid=NULL WHERE id=(SELECT MIN(id) FROM animals)")
        con.commit(); con.close()

        with db._conn() as c:
            alterados = db._backfill_uuids(c)
        self.assertEqual(alterados, 1)
        self.assertEqual(
            self._linhas("SELECT id FROM animals WHERE uuid IS NULL"), [])


class TestFormatoDoUuid(unittest.TestCase):
    def test_novo_uuid_gera_valores_distintos(self):
        valores = {novo_uuid() for _ in range(200)}
        self.assertEqual(len(valores), 200)

    def test_formato_uuid4(self):
        v = novo_uuid()
        self.assertEqual(len(v), 36)
        self.assertEqual([len(p) for p in v.split("-")], [8, 4, 4, 4, 12])


if __name__ == "__main__":
    unittest.main()
