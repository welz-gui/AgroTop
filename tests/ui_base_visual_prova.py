"""Prova estática da base visual web (spec 0100).

O CSS é uma folha comum aos dois temas: as cores vêm de ``css_variaveis`` e
os seletores desta prova só referenciam tokens semânticos. Assim a mesma
captura de estrutura pode ser comparada emitindo as variáveis de ``escuro`` e
``claro`` sem duplicar a folha de estilo.

⚠️ Não começa com ``test_`` de propósito — executado por ``tests/test_ui.py``.
"""

import os
import re
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from ui.tema import css_variaveis  # noqa: E402


class TestBaseVisual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RAIZ, "app.py"), encoding="utf-8") as arquivo:
            codigo = arquivo.read()
        cls.css = codigo.split("# ─── CSS", 1)[1].split("</style>", 1)[0]
        cls.paletas = {nome: css_variaveis(nome) for nome in ("escuro", "claro")}

    def test_hierarquia_tipografica_e_utilitarios_estao_declarados(self):
        self.assertIn(".page-title{font-size:1.875rem", self.css)
        self.assertIn('div[data-testid="stMetricValue"]{font-size:2rem!important}', self.css)
        self.assertIn(
            ".texto-apoio{font-size:.8125rem;color:var(--texto_secundario)}",
            self.css,
        )
        self.assertIn(
            ".titulo-secao{font-size:1.1875rem;font-weight:700;color:var(--texto)}",
            self.css,
        )

    def test_raio_e_espacamento_seguem_a_escala(self):
        for seletor in (".stButton>button", "div[data-testid=\"stMetric\"]",
                        ".card", ".card-green", ".card-yellow", ".card-red",
                        ".keypad-display"):
            regra = re.search(rf"{re.escape(seletor)}\{{([^}}]+)\}}", self.css)
            self.assertIsNotNone(regra, seletor)
            self.assertIn("border-radius:12px", regra.group(1), seletor)

        self.assertIn("padding:1rem", self.css)
        self.assertIn("margin-bottom:1rem", self.css)
        self.assertIn("padding:4px 8px", self.css)  # badges compactos, escala 4/8
        self.assertNotIn("padding:1.2rem", self.css)
        self.assertNotIn("margin-bottom:1.4rem", self.css)

    def test_a_folha_funciona_com_as_duas_paletas(self):
        for nome, variaveis in self.paletas.items():
            self.assertIn("--fundo:", variaveis, nome)
            self.assertIn("--texto:", variaveis, nome)
            self.assertIn("var(--primaria)", self.css, nome)
            self.assertIn("var(--texto_secundario)", self.css, nome)

    def test_css_nao_injeta_acao_primaria_customizada(self):
        regra = re.search(r"\.stButton>button\{([^}]+)\}", self.css)
        self.assertIsNotNone(regra)
        self.assertNotIn("background", regra.group(1))

    def test_cores_e_inicializada_uma_so_vez(self):
        self.assertEqual(self.css.split("</style>", 1)[0].count("c = cores("), 0)
        with open(os.path.join(RAIZ, "app.py"), encoding="utf-8") as arquivo:
            codigo = arquivo.read()
        self.assertEqual(codigo.count("c = cores("), 1)


if __name__ == "__main__":
    unittest.main()
