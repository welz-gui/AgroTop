"""Garante que a camada de dados não fique acoplada ao Streamlit.

Motivo: `database.py` guarda as regras de negócio (GMD, custos, terminação, auth).
Se ele passar a exigir Streamlit, essas regras deixam de ser reutilizáveis por uma
API (FastAPI), por um job agendado, pelo app mobile ou por qualquer outro frontend
— e trocar de framework de UI passaria a exigir reescrever regra de negócio.

Ver docs/adr/0002-fronteira-de-portabilidade.md

O teste roda em SUBPROCESSO de propósito: bloquear `streamlit` em `sys.meta_path`
dentro do processo de teste contaminaria os outros testes.
"""

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Executado num interpretador separado, com qualquer import de streamlit bloqueado.
SCRIPT = r"""
import sys, os
sys.path.insert(0, os.environ["AGROTOP_ROOT"])
from importlib.abc import MetaPathFinder


class BloqueiaStreamlit(MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "streamlit" or name.startswith("streamlit."):
            raise ImportError("streamlit indisponivel (simulado pelo teste)")
        return None


sys.meta_path.insert(0, BloqueiaStreamlit())

import database as db

# Regras de negócio puras precisam funcionar sem o framework de UI.
sim = db.simular_terminacao(380, 500, 300, db.TERMINACAO_DEFAULTS)
assert sim and sim[0]["lucro"] is not None, "simular_terminacao falhou"
assert db.kg_to_arrobas(450) == 15.6, "kg_to_arrobas divergente"

h = db._hash("senha-de-teste")
assert db._verify_password("senha-de-teste", h), "hash/verify de senha falhou"
assert not db._verify_password("errada", h), "verify aceitou senha errada"

# O cache do Streamlit deve degradar para no-op, não estourar.
db.clear_cache()

print("PORTABILIDADE_OK")
"""


class TestCamadaDadosSemStreamlit(unittest.TestCase):
    def test_database_importa_e_funciona_sem_streamlit(self):
        env = {**os.environ, "AGROTOP_ROOT": ROOT}
        # Sem DATABASE_URL o módulo cai no SQLite e não tenta acessar a nuvem.
        env.pop("DATABASE_URL", None)
        proc = subprocess.run([sys.executable, "-c", SCRIPT], capture_output=True,
                              text=True, env=env, cwd=ROOT)
        self.assertIn("PORTABILIDADE_OK", proc.stdout,
                      "database.py deixou de funcionar sem o Streamlit.\n"
                      f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")

    def test_streamlit_nao_e_importado_no_topo_do_modulo(self):
        """O import precisa ser preguiçoso (dentro de função/try), nunca no topo."""
        with open(os.path.join(ROOT, "database.py"), encoding="utf-8") as fh:
            linhas = fh.readlines()

        infratores = []
        for n, linha in enumerate(linhas, 1):
            if linha.startswith(("import streamlit", "from streamlit")):
                infratores.append(f"linha {n}: {linha.strip()}")

        self.assertEqual(infratores, [],
                         "streamlit importado no nível do módulo em database.py — "
                         "use import preguiçoso com fallback (ver o padrão em _cache). "
                         + "; ".join(infratores))


if __name__ == "__main__":
    unittest.main()
