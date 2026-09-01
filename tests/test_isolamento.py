"""Verifica que a suíte não consegue tocar o banco de produção.

Ver `tests/__init__.py` para o contexto. Estes testes falham se a proteção for
removida ou deixar de funcionar.
"""

import os
import subprocess
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402
from repositories.conexao import FORCE_SQLITE_ENV


class TestIsolamentoDeProducao(unittest.TestCase):
    def test_suite_roda_em_sqlite(self):
        """Durante os testes, o backend tem de ser SQLite — nunca Postgres.

        As mensagens NÃO incluem `DATABASE_URL`: ela contém a senha do banco, e
        logs de teste vazam para o CI e para o terminal.
        """
        self.assertFalse(
            db.USE_PG,
            "a suíte está apontando para o Postgres de PRODUÇÃO. Rode com "
            "`python -m unittest discover -s tests -t .` para que tests/__init__.py "
            "seja importado e defina AGROTOP_FORCE_SQLITE=1 antes do import de "
            "database.")
        self.assertEqual(
            len(db.DATABASE_URL), 0,
            "DATABASE_URL deveria estar vazia durante os testes "
            f"(tem {len(db.DATABASE_URL)} caracteres — valor omitido de propósito).")

    def test_variavel_de_isolamento_esta_ativa(self):
        """A proteção vem de tests/__init__.py, não de acaso do ambiente."""
        self.assertEqual(os.environ.get(FORCE_SQLITE_ENV), "1",
                         "AGROTOP_FORCE_SQLITE não está definida — "
                         "tests/__init__.py não foi importado?")

    def test_flag_vence_uma_database_url_presente(self):
        """O ponto central: a flag precisa ignorar uma DATABASE_URL existente.

        Roda em subprocesso com DATABASE_URL apontando para um endereço inválido.
        Sem a flag, `USE_PG` seria True; com ela, o módulo cai no SQLite. Verifica
        o mecanismo em si, e não apenas o ambiente atual (que pode não ter segredos).
        """
        script = (
            "import os, sys; sys.path.insert(0, os.environ['AGROTOP_RAIZ']);"
            "import database as db;"
            "print('USE_PG=', db.USE_PG, 'URL=', repr(db.DATABASE_URL))"
        )

        env_sem = {**os.environ, "AGROTOP_RAIZ": RAIZ,
                   "DATABASE_URL": "postgresql://x:y@localhost:1/naoexiste"}
        env_sem.pop("AGROTOP_FORCE_SQLITE", None)
        sem_flag = subprocess.run([sys.executable, "-c", script], capture_output=True,
                                  text=True, env=env_sem, cwd=RAIZ)
        self.assertIn("USE_PG= True", sem_flag.stdout,
                      f"sem a flag, deveria usar Postgres.\n{sem_flag.stdout}\n"
                      f"{sem_flag.stderr}")

        env_com = {**env_sem, "AGROTOP_FORCE_SQLITE": "1"}
        com_flag = subprocess.run([sys.executable, "-c", script], capture_output=True,
                                  text=True, env=env_com, cwd=RAIZ)
        self.assertIn("USE_PG= False", com_flag.stdout,
                      "AGROTOP_FORCE_SQLITE=1 não sobrepôs a DATABASE_URL — o "
                      f"isolamento dos testes está furado.\n{com_flag.stdout}\n"
                      f"{com_flag.stderr}")


if __name__ == "__main__":
    unittest.main()
