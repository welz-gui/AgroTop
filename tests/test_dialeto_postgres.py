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
            from repositories.animais import get_animal

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            animal_id = "PG" + uuid.uuid4().hex[:10]
            db.add_animal(db.AnimalData(
                animal_id, "Nelore", "M", None, "2026-08-01",
                300.0, 500.0, 0.0, None, None,
            ))
            db.add_weighing(animal_id, 345.0, "2026-08-02", operator="CI")

            animal = get_animal(animal_id)
            assert animal is not None
            assert animal["current_weight"] == 345.0
            pesagens = db.get_weighings(animal_id)
            assert any(p["weight"] == 345.0 for p in pesagens)
            """
        )

    def test_executemany_grava_em_lote(self):
        """`_PGConn` precisa expor `executemany`, não só `execute`.

        Vários pontos do código (importação de dispositivos/pesagens,
        backfill de uuid/identificadores, confirmação de chegada) trocaram
        um loop de `execute` por um único `executemany` para ganho de
        performance. SQLite tem `executemany` nativo, então esse caminho
        nunca quebrava em CI — só no Postgres real, onde `_PGConn` só
        proxeava `execute`. Achado ao revisar PRs automatizadas do Jules
        (2026-09-01): `AttributeError: '_PGConn' object has no attribute
        'executemany'`.
        """
        self._executar(
            """
            import uuid

            import database as db
            from repositories.animais import get_animal

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            animal_id = "EM" + uuid.uuid4().hex[:10]
            db.add_animal(db.AnimalData(
                animal_id, "Nelore", "M", None, "2026-08-01",
                300.0, 500.0, 0.0, None, None,
            ))
            animal_uuid = get_animal(animal_id)["uuid"]

            with db._conn() as con:
                con.executemany(
                    "INSERT INTO weighings (animal_uuid,weigh_date,weight) "
                    "VALUES(?,?,?)",
                    [(animal_uuid, "2026-08-03", 350.0),
                     (animal_uuid, "2026-08-10", 360.0)],
                )

            pesagens = db.get_weighings(animal_id)
            pesos = {p["weight"] for p in pesagens}
            assert 350.0 in pesos and 360.0 in pesos, pesagens
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
            db.add_animal(db.AnimalData(
                animal_id, "Nelore", "F", None, "2026-08-01",
                280.0, 480.0, 0.0, None, None,
            ))
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

    def test_fila_de_sincronizacao_drena(self):
        """ADR 0005 — o mesmo cenário do SQLite, no dialeto que vai para produção.

        Interessa aqui o que só o Postgres exercita: `bigserial`, `timestamptz`
        voltando como `datetime` (normalizado pelo repositório) e a subconsulta
        `MAX(id)` por par (evento, sistema).
        """
        self._executar(
            """
            import uuid

            import database as db
            from repositories.animais import get_animal
            from repositories import eventos

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            animal_id = "SY" + uuid.uuid4().hex[:10]
            db.add_animal(db.AnimalData(
                animal_id, "Nelore", "F", None, "2026-08-01",
                280.0, 480.0, 0.0, None, None,
            ))
            animal_uuid = get_animal(animal_id)["uuid"]
            evento_id = eventos.do_animal(animal_uuid)[0]["id"]

            antes = eventos.contar_pendentes()
            assert antes > 0, "nenhum evento na fila para exercitar o cenário"

            eventos.registrar_situacao(evento_id, "enviado", usuario="CI")
            eventos.registrar_situacao(evento_id, "rejeitado", usuario="CI")
            assert eventos.contar_pendentes() == antes, "rejeitado saiu da fila"

            r = eventos.marcar_sincronizado(
                [evento_id], protocolo="CI-1", usuario="CI")
            assert r["ok"], r
            assert eventos.contar_pendentes() == antes - 1, "a fila não drenou"

            atual = eventos.situacao_atual(evento_id)["oficial"]
            assert atual["situacao"] == "aceito", atual
            assert atual["protocolo"] == "CI-1", atual
            assert isinstance(atual["registrado_em"], str), (
                "timestamptz não foi normalizado para texto ISO")
            assert len(eventos.historico_de_sincronizacao(evento_id)) == 3
            """
        )

    def test_evento_sincronizacao_recusa_update_e_delete(self):
        """A tabela nova é append-only como as outras duas (ADR 0005)."""
        self._executar(
            """
            import uuid

            import psycopg2

            import database as db
            from repositories.animais import get_animal
            from repositories import eventos

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            animal_id = "SZ" + uuid.uuid4().hex[:10]
            db.add_animal(db.AnimalData(
                animal_id, "Nelore", "M", None, "2026-08-01",
                300.0, 500.0, 0.0, None, None,
            ))
            animal_uuid = get_animal(animal_id)["uuid"]
            evento_id = eventos.do_animal(animal_uuid)[0]["id"]
            eventos.registrar_situacao(evento_id, "enviado", usuario="CI")

            with db._conn() as con:
                linha = con.execute(
                    "SELECT id FROM evento_sincronizacao WHERE evento_id=?",
                    (evento_id,),
                ).fetchone()
            assert linha is not None

            for sql in (
                "UPDATE evento_sincronizacao SET situacao='aceito' WHERE id=?",
                "DELETE FROM evento_sincronizacao WHERE id=?",
            ):
                try:
                    with db._conn() as con:
                        con.execute(sql, (linha["id"],))
                except psycopg2.Error:
                    pass
                else:
                    raise AssertionError(f"gatilho append-only aceitou: {sql}")

            # E o evento em si continua intocável, inclusive na coluna legada.
            try:
                with db._conn() as con:
                    con.execute(
                        "UPDATE animal_events SET status_sincronizacao='sincronizado' "
                        "WHERE id=?",
                        (evento_id,),
                    )
            except psycopg2.Error:
                pass
            else:
                raise AssertionError(
                    "UPDATE de status_sincronizacao foi aceito — a exceção "
                    "recusada pelo ADR 0005 entrou por alguma porta")
            """
        )


if __name__ == "__main__":
    unittest.main()
