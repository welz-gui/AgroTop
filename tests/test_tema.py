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


def contraste_wcag(primeiro, segundo):
    def luminancia(valor):
        rgb = [int(valor[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        canais = [
            ((canal + 0.055) / 1.055) ** 2.4
            if canal > 0.03928
            else canal / 12.92
            for canal in rgb
        ]
        return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]

    claro, escuro = sorted(
        (luminancia(primeiro), luminancia(segundo)), reverse=True
    )
    return (claro + 0.05) / (escuro + 0.05)


class TestParidadeDeTemas(unittest.TestCase):
    def test_badges_de_status_mantem_contraste_wcag_aa(self):
        contraste_verde = contraste_wcag(
            tema.cores()["sucesso"], tema.cores()["sucesso_fundo"]
        )
        contraste_vermelho = contraste_wcag(
            tema.cores()["perigo"], tema.cores()["perigo_fundo"]
        )

        self.assertGreaterEqual(contraste_verde, 4.5)
        self.assertGreaterEqual(contraste_vermelho, 4.5)
        self.assertAlmostEqual(contraste_verde, 5.23, places=2)
        self.assertAlmostEqual(contraste_vermelho, 5.84, places=2)

    def test_bloco_css_do_app_nao_tem_hex_literal(self):
        caminho = os.path.join(RAIZ, "app.py")
        with open(caminho, encoding="utf-8") as arquivo:
            codigo = arquivo.read()
        bloco = codigo.split("# ─── CSS", 1)[1].split("</style>", 1)[0]

        self.assertEqual(re.findall(r"#[0-9a-fA-F]{6}", bloco), [])

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
