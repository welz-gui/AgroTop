"""Testes de integridade da paleta de cores e auditoria de tokens (Spec 0007-v2)."""

import unittest
from pathlib import Path
from tools import auditar_cores
from ui import tema

# Os 20 hex literais (21 tokens) originais congelados conforme o relatório da Spec 0024.
# Garantem que nenhuma substituição ou refatoração alterou a aparência visual original.
VALORES_ORIGINAIS_ESCURO = {
    "fundo":            "#0f172a",
    "fundo_alt":        "#0a1628",
    "superficie":       "#1e293b",
    "borda":            "#334155",
    "borda_suave":      "#475569",
    "texto":            "#f1f5f9",
    "texto_secundario": "#94a3b8",
    "texto_terciario":  "#64748b",
    "primaria":         "#4ade80",
    "sucesso":          "#4ade80",
    "sucesso_escuro":   "#166534",
    "sucesso_fundo":    "#14532d",
    "atencao":          "#fbbf24",
    "atencao_escuro":   "#854d0e",
    "atencao_fundo":    "#422006",
    "perigo":           "#f87171",
    "perigo_escuro":    "#7f1d1d",
    "perigo_fundo":     "#450a0a",
    "info":             "#22d3ee",
    "info_fundo":       "#1e3a5f",
    "destaque":         "#a78bfa",
}

# Lista de exceções permitidas de hex literais em app.py.
# Conforme a Spec 0007-v2 (seção 3), o bloco CSS estático do topo de app.py (linhas 46-104)
# é mantido como a única exceção permitida (33 ocorrências de hex literais no CSS estático),
# todas perfeitamente mapeadas para os tokens equivalentes em ui/tema.py.
LIMITE_EXCECOES_CSS = 33


class TestCores(unittest.TestCase):
    def test_nenhum_hex_literal_sobrou_em_app_py(self):
        """1. Mede a contagem de hex literais restantes em app.py (via auditar_cores.extrair_hex)
        e garante que não sobrou nenhum hex literal em código Python fora da exceção do bloco CSS estático.
        """
        raiz = Path(__file__).resolve().parents[1]
        codigo_app = (raiz / "app.py").read_text(encoding="utf-8")
        hexes = auditar_cores.extrair_hex(codigo_app)
        resultado = auditar_cores.mapear(hexes, tema.TEMAS)

        self.assertLessEqual(
            len(hexes),
            LIMITE_EXCECOES_CSS,
            f"Sobraram {len(hexes)} hexadecimais literais em app.py, excedendo o limite permitido do CSS estático ({LIMITE_EXCECOES_CSS}).",
        )
        self.assertEqual(
            resultado["resumo"]["sem_token"],
            0,
            f"Existem cores hexadecimais em app.py sem token associado: {resultado['sem_token']}",
        )

    def test_todo_token_existe_nos_dois_temas(self):
        """2. Todos os tokens devem existir tanto no tema escuro quanto no tema claro."""
        chaves_escuro = set(tema.ESCURO.keys())
        chaves_claro = set(tema.CLARO.keys())

        self.assertEqual(
            chaves_escuro,
            chaves_claro,
            "Discrepância entre os tokens declarados em ESCURO e CLARO em ui/tema.py",
        )

    def test_valores_dos_tokens_nao_mudaram(self):
        """3. Congela os 20 valores hexadecimais originais do tema escuro."""
        for token, valor_esperado in VALORES_ORIGINAIS_ESCURO.items():
            self.assertIn(
                token,
                tema.ESCURO,
                f"O token original '{token}' foi removido do tema ESCURO.",
            )
            self.assertEqual(
                tema.ESCURO[token].lower(),
                valor_esperado.lower(),
                f"O valor do token '{token}' mudou de '{valor_esperado}' para '{tema.ESCURO[token]}'.",
            )
