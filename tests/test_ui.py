"""Executa as provas de interface num subprocesso isolado.

Os testes reais estão em `tests/ui_*_prova.py`. Eles **não podem** rodar dentro
desta suíte: o `AppTest` do Streamlit levanta um runtime próprio e esbarra no
módulo de cache já carregado pelos outros testes —
`PicklingError: it's not the same object as ...CachedResult`. Passam sozinhos e
quebram em conjunto, que é o pior tipo de teste.

Subprocesso resolve pela raiz: processo novo, uma cópia só de cada módulo. O
custo é ~15 s, e o que se compra é a única prova automatizada de que as funções
puras de `services/` chegaram de fato à tela — nenhum teste de unidade pega uma
função entregue e nunca chamada.
"""

import os
import subprocess
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROVAS = [
    "tests.ui_estados_prova",       # máquina de estados na tela de admin
    "tests.ui_integracoes_prova",   # identificadores, consistência e recomendações
    "tests.ui_nascimento_prova",    # §7.2: bloqueio impede, alerta pede confirmação
    "tests.ui_brincos_prova",       # §5: estado definitivo, divergência, troca
    "tests.ui_movimentacao_prova",  # §8: bloqueio, justificativa escrita, divergência
    "tests.ui_pendencias_prova",    # §7.3: prazo futuro não é irregularidade
    "tests.ui_propriedades_prova",  # §3: titular imutável, área calculada
    "tests.ui_regras_prova",        # §11: versão em vez de edição, simular antes
    "tests.ui_eventos_prova",       # §6/§10: corrigir em vez de editar, fila de sincronização
    "tests.ui_perimetro_lote_prova", # perímetro do piquete, sobrepostos() ligado (migration 0015)
]


class TestProvasDeInterface(unittest.TestCase):
    def test_as_telas_obedecem_aos_services(self):
        ambiente = dict(os.environ,
                        AGROTOP_FORCE_SQLITE="1",
                        PYTHONIOENCODING="utf-8")
        r = subprocess.run(
            [sys.executable, "-m", "unittest", *PROVAS],
            cwd=RAIZ, env=ambiente, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=900,
        )
        self.assertEqual(
            r.returncode, 0,
            "a prova de interface falhou — saída do subprocesso:\n"
            f"{r.stdout[-4000:]}\n{r.stderr[-4000:]}")


if __name__ == "__main__":
    unittest.main()
