"""Prova estrutural da integração com o tema nativo do Streamlit (spec 0102)."""

import ast
import os
import unittest


RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestTemaNativoNoApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RAIZ, "app.py"), encoding="utf-8") as arquivo:
            cls.codigo = arquivo.read()
        cls.arvore = ast.parse(cls.codigo)

    def test_resolve_tema_uma_vez_e_trata_none(self):
        self.assertIn(
            "tema_ativo = st.context.theme.type or TEMA_PADRAO", self.codigo
        )
        self.assertIn("c = cores(tema_ativo)", self.codigo)
        self.assertIn("css_variaveis(tema_ativo)", self.codigo)

    def test_layout_plotly_recebe_tema_ativo(self):
        chamadas = [
            no
            for no in ast.walk(self.arvore)
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Name)
            and no.func.id == "plotly_layout"
        ]
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(len(chamadas[0].args), 1)
        self.assertIsInstance(chamadas[0].args[0], ast.Name)
        self.assertEqual(chamadas[0].args[0].id, "tema_ativo")

    def test_meta_tag_reusa_paleta_ativa(self):
        self.assertIn("tema = c", self.codigo)
        self.assertNotIn('cores("escuro")', self.codigo)

    def test_historico_nao_reverte_para_tema_padrao(self):
        self.assertNotIn("c = cores()", self.codigo)


if __name__ == "__main__":
    unittest.main()
