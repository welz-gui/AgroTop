"""Executa a prova de interface num subprocesso isolado.

O teste real está em `tests/ui_estados_prova.py`. Ele não pode rodar dentro
desta suíte porque o `AppTest` do Streamlit levanta um runtime próprio e
esbarra no módulo de cache já carregado — `PicklingError: it's not the same
object as ...CachedResult`. Passa sozinho e quebra em conjunto.

Subprocesso resolve pela raiz: processo novo, uma cópia só de cada módulo. O
custo é ~8 s, e o que se compra é a única prova automatizada de que a tela
obedece à máquina de estados.
"""

import os
import subprocess
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestProvaDeInterface(unittest.TestCase):
    def test_tela_de_status_obedece_a_maquina_de_estados(self):
        ambiente = dict(os.environ,
                        AGROTOP_FORCE_SQLITE="1",
                        PYTHONIOENCODING="utf-8")
        r = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.ui_estados_prova"],
            cwd=RAIZ, env=ambiente, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600,
        )
        self.assertEqual(
            r.returncode, 0,
            "a prova de interface falhou — saída do subprocesso:\n"
            f"{r.stdout[-3000:]}\n{r.stderr[-3000:]}")


if __name__ == "__main__":
    unittest.main()
