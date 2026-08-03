"""Integração real do caminho PostgreSQL usando apenas o banco efêmero do CI."""

import os
import subprocess
import sys
import textwrap
import unittest


RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTGRES_NO_CI = os.environ.get("AGROTOP_TEST_POSTGRES") == "1"


@unittest.skipUnless(POSTGRES_NO_CI, "PostgreSQL efêmero não solicitado")
class TestDialetoPostgres(unittest.TestCase):
    def _executar(self, codigo: str) -> None:
        """Executa o cenário num processo que realmente importa USE_PG=True."""
        env = dict(os.environ)
        env.pop("AGROTOP_FORCE_SQLITE", None)
        self.assertTrue(env.get("DATABASE_URL"), "DATABASE_URL de teste ausente")

        processo = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(codigo)],
            cwd=RAIZ,
            env=env,
            capture_output=True,
            text=True,
        )
        saida = f"{processo.stdout}\n{processo.stderr}"
        url = env.get("DATABASE_URL", "")
        if url:
            saida = saida.replace(url, "<DATABASE_URL omitida>")
        self.assertEqual(
            processo.returncode,
            0,
            f"Cenário PostgreSQL falhou (credencial omitida):\n{saida}",
        )

    def test_init_db_completa(self):
        self._executar(
            """
            import database as db

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            """
        )

    def test_ciclo_de_escrita_e_leitura(self):
        self._executar(
            """
            import uuid

            import database as db

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            animal_id = "PG" + uuid.uuid4().hex[:10]
            db.add_animal(
                animal_id, "Nelore", "M", None, "2026-08-01",
                300.0, 500.0, 0.0, None, None,
            )
            db.add_weighing(animal_id, 345.0, "2026-08-02", operator="CI")

            animal = db.get_animal(animal_id)
            assert animal is not None
            assert animal["current_weight"] == 345.0
            pesagens = db.get_weighings(animal_id)
            assert any(p["weight"] == 345.0 for p in pesagens)
            """
        )

    def test_animal_events_recusa_update_e_delete(self):
        self._executar(
            """
            import uuid

            import psycopg2

            import database as db

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            animal_id = "EV" + uuid.uuid4().hex[:10]
            db.add_animal(
                animal_id, "Nelore", "F", None, "2026-08-01",
                280.0, 480.0, 0.0, None, None,
            )
            with db._conn() as con:
                evento = con.execute(
                    "SELECT e.id FROM animal_events e "
                    "JOIN animals a ON a.uuid=e.animal_uuid "
                    "WHERE a.id=? ORDER BY e.id LIMIT 1",
                    (animal_id,),
                ).fetchone()
            assert evento is not None

            for sql in (
                "UPDATE animal_events SET tipo='venda' WHERE id=?",
                "DELETE FROM animal_events WHERE id=?",
            ):
                try:
                    with db._conn() as con:
                        con.execute(sql, (evento["id"],))
                except psycopg2.Error:
                    pass
                else:
                    raise AssertionError(f"gatilho append-only aceitou: {sql}")
            """
        )


if __name__ == "__main__":
    unittest.main()
