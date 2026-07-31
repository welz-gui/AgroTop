"""Guardas da paleta (DESIGN.md, ROADMAP.md R20).

O tema é escolha do usuário, então cada token precisa existir nos DOIS temas —
um token faltando quebraria aquele tema em silêncio, e só apareceria para o
usuário que tivesse escolhido justamente ele.
"""

import os
import re
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from ui import tema  # noqa: E402

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class TestParidadeDeTemas(unittest.TestCase):
    def test_mesmos_tokens_nos_dois_temas(self):
        so_escuro = sorted(set(tema.ESCURO) - set(tema.CLARO))
        so_claro = sorted(set(tema.CLARO) - set(tema.ESCURO))
        self.assertEqual(so_escuro, [], f"tokens ausentes no tema claro: {so_escuro}")
        self.assertEqual(so_claro, [], f"tokens ausentes no tema escuro: {so_claro}")

    def test_todos_os_valores_sao_hex(self):
        for nome_tema, paleta in tema.TEMAS.items():
            for token, valor in paleta.items():
                with self.subTest(tema=nome_tema, token=token):
                    self.assertRegex(valor, HEX,
                                     f"{nome_tema}.{token} não é hex de 6 dígitos")

    def test_tema_padrao_preserva_o_visual_atual(self):
        """O padrão tem de continuar sendo o escuro que está em produção.

        Se isto falhar, a introdução da troca de tema mudou a aparência de quem
        não escolheu nada — exatamente o que a etapa A2b promete não fazer.
        """
        self.assertEqual(tema.TEMA_PADRAO, "escuro")
        padrao = tema.cores()
        self.assertEqual(padrao["fundo"], "#0f172a")        # config.toml backgroundColor
        self.assertEqual(padrao["superficie"], "#1e293b")   # secondaryBackgroundColor
        self.assertEqual(padrao["texto"], "#f1f5f9")        # textColor
        self.assertEqual(padrao["primaria"], "#4ade80")     # primaryColor

    def test_tema_desconhecido_cai_no_padrao(self):
        self.assertEqual(tema.cores("inexistente"), tema.cores())
        self.assertEqual(tema.cores(None), tema.cores())

    def test_css_declara_todos_os_tokens(self):
        css = tema.css_variaveis()
        for token in tema.ESCURO:
            self.assertIn(f"--{token}:", css, f"token {token} ausente no :root")

    def test_plotly_acompanha_o_tema(self):
        self.assertEqual(tema.plotly_layout("escuro")["template"], "plotly_dark")
        self.assertEqual(tema.plotly_layout("claro")["template"], "plotly_white")
        self.assertEqual(tema.plotly_layout(height=300)["height"], 300)


class TestModuloDeTemaEhPortavel(unittest.TestCase):
    def test_nao_importa_streamlit(self):
        """A paleta precisa servir também a relatórios e à futura API (R9)."""
        with open(os.path.join(RAIZ, "ui", "tema.py"), encoding="utf-8") as fh:
            for n, linha in enumerate(fh, 1):
                self.assertFalse(
                    linha.startswith(("import streamlit", "from streamlit")),
                    f"ui/tema.py importa streamlit na linha {n}")


if __name__ == "__main__":
    unittest.main()
