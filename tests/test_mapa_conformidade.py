import ast
import os
import re
import unittest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAPA_PATH = os.path.join(
    PROJECT_ROOT, "docs", "regulatorio", "mapa-de-conformidade.md"
)
REQUISITOS_PATH = os.path.join(
    PROJECT_ROOT, "docs", "regulatorio", "requisitos_sistema_pnib_rs.md"
)


class TestMapaConformidade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MAPA_PATH, encoding="utf-8") as mapa:
            cls.mapa_content = mapa.read()
        with open(REQUISITOS_PATH, encoding="utf-8") as requisitos:
            cls.requisitos_content = requisitos.read()

    def _linhas_tabela(self):
        return [
            linha
            for linha in self.mapa_content.splitlines()
            if re.match(r"^\| §\d+\s*\|", linha)
        ]

    def test_todo_arquivo_citado_existe(self):
        caminhos = set(
            re.findall(r"`([^`]+)`", self.mapa_content)
        )
        arquivos = {
            caminho
            for caminho in caminhos
            if re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", caminho)
            and ("." in caminho or caminho.endswith("/"))
        }
        self.assertTrue(arquivos)
        for rel_path in arquivos:
            self.assertTrue(
                os.path.exists(os.path.join(PROJECT_ROOT, rel_path)),
                f"Caminho citado não existe: {rel_path}",
            )

    def test_todo_simbolo_citado_existe(self):
        padrao = re.compile(r"`([A-Za-z0-9_/-]+\.py)`\s*\(([^)]+)\)")
        matches = padrao.findall(self.mapa_content)
        self.assertTrue(matches)

        for rel_path, simbolos_raw in matches:
            abs_path = os.path.join(PROJECT_ROOT, rel_path)
            with open(abs_path, encoding="utf-8") as modulo:
                arvore = ast.parse(modulo.read(), filename=abs_path)
            definidos = {
                node.name
                for node in ast.walk(arvore)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }
            for simbolo in simbolos_raw.split(","):
                nome = simbolo.strip().strip("`'\"")
                self.assertIn(
                    nome,
                    definidos,
                    f"Símbolo {nome!r} não existe em {rel_path}",
                )

    def test_toda_secao_do_pnib_aparece_no_mapa(self):
        secoes_requisitos = re.findall(
            r"^##\s+(\d+)\.\s+", self.requisitos_content, re.MULTILINE
        )
        secoes_mapa = {
            numero
            for linha in self._linhas_tabela()
            if (numero := re.match(r"^\| §(\d+)\s*\|", linha))
        }
        secoes_mapa = {match.group(1) for match in secoes_mapa}
        self.assertEqual(set(secoes_requisitos), secoes_mapa)

    def test_parcial_sempre_diz_o_que_falta(self):
        for linha in self._linhas_tabela():
            if "| 🟡 parcial |" in linha:
                self.assertRegex(linha, r"Falta:")

    def test_resumo_bate_com_tabela(self):
        situacoes = (
            "✅ atendido",
            "🟡 parcial",
            "❌ não atendido",
            "⏳ fora de prazo",
            "➖ não se aplica",
        )
        for situacao in situacoes:
            tabela = sum(f"| {situacao} |" in linha for linha in self._linhas_tabela())
            resumo = re.search(
                rf"- \*\*`{re.escape(situacao)}`\*\*:\s*(\d+)",
                self.mapa_content,
            )
            self.assertIsNotNone(resumo, situacao)
            self.assertEqual(int(resumo.group(1)), tabela, situacao)

    def test_exigencias_visiveis_atendidas_citam_app(self):
        for secao in ("3", "4", "5", "7", "8", "14", "15", "17"):
            linha = next(
                (linha for linha in self._linhas_tabela() if linha.startswith(f"| §{secao} |")),
                None,
            )
            self.assertIsNotNone(linha, secao)
            self.assertIn("| ✅ atendido |", linha)
            self.assertIn("`app.py`", linha)

    def test_nenhum_link_e_caminho_absoluto(self):
        self.assertNotRegex(self.mapa_content, r"(?i)file://")
        self.assertNotRegex(self.mapa_content, r"(?i)[A-Za-z]:[\\/]")
        self.assertNotRegex(self.mapa_content, r"(?i)/d:/")


if __name__ == "__main__":
    unittest.main()
