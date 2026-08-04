import ast
import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
MAPA_PATH = os.path.join(
    PROJECT_ROOT, "docs", "regulatorio", "mapa-de-conformidade.md"
)
REQUISITOS_PATH = os.path.join(
    PROJECT_ROOT, "docs", "regulatorio", "requisitos_sistema_pnib_rs.md"
)


class TestMapaConformidade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MAPA_PATH, "r", encoding="utf-8") as f:
            cls.mapa_content = f.read()

        with open(REQUISITOS_PATH, "r", encoding="utf-8") as f:
            cls.requisitos_content = f.read()

    def test_todo_arquivo_citado_existe(self):
        """Verifica se todos os arquivos ou diretórios citados no mapa de conformidade existem no disco."""
        caminhos = re.findall(
            r"`([a-zA-Z0-9_\-/\.]+\.[a-zA-Z0-9]+|[a-zA-Z0-9_\-/]+/)`",
            self.mapa_content,
        )
        self.assertTrue(caminhos, "Nenhum caminho de arquivo encontrado no mapa.")

        for rel_path in set(caminhos):
            if rel_path.startswith("http") or rel_path.startswith("N/A"):
                continue

            abs_path = os.path.join(PROJECT_ROOT, rel_path)
            self.assertTrue(
                os.path.exists(abs_path),
                f"O arquivo/diretório citado no mapa não existe no disco: '{rel_path}' (absoluto: {abs_path})",
            )

    def test_todo_simbolo_citado_existe(self):
        """Verifica via AST se todas as funções, classes e variáveis citadas no mapa existem nos arquivos Python correspondentes."""
        padrao = re.compile(r"`([a-zA-Z0-9_\-/]+\.py)`\s*\(([^)]+)\)")
        matches = padrao.findall(self.mapa_content)
        self.assertTrue(matches, "Nenhum símbolo citado encontrado no mapa.")

        for rel_path, simbolos_raw in matches:
            abs_path = os.path.join(PROJECT_ROOT, rel_path)
            self.assertTrue(
                os.path.exists(abs_path),
                f"Arquivo Python citado não existe: '{rel_path}'",
            )

            with open(abs_path, "r", encoding="utf-8") as f:
                code_ast = ast.parse(f.read(), filename=abs_path)

            simbolos_definidos = set()
            for node in ast.walk(code_ast):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    simbolos_definidos.add(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            simbolos_definidos.add(target.id)

            simbolos_citados = [
                s.strip(" `\"'") for s in simbolos_raw.split(",")
            ]
            for simbolo in simbolos_citados:
                simbolo_limpo = simbolo.split()[-1].strip(" `\"'")
                self.assertIn(
                    simbolo_limpo,
                    simbolos_definidos,
                    f"Símbolo '{simbolo_limpo}' citado no mapa não existe no AST do arquivo '{rel_path}'",
                )

    def test_toda_secao_do_pnib_aparece_no_mapa(self):
        """Verifica se todas as seções numeradas (ex: ## 1., ## 2., ..., ## 26.) do documento PNIB aparecem no mapa."""
        secoes_requisitos = re.findall(
            r"^##\s+(\d+)\.\s+", self.requisitos_content, re.MULTILINE
        )
        self.assertTrue(
            secoes_requisitos,
            "Nenhuma seção numerada encontrada no documento de requisitos.",
        )

        lines_mapa = self.mapa_content.splitlines()
        secoes_no_mapa = set()
        for line in lines_mapa:
            if line.startswith("| §"):
                match = re.search(r"\|\s*§(\d+)\s*\|", line)
                if match:
                    secoes_no_mapa.add(match.group(1))

        for sec in secoes_requisitos:
            self.assertIn(
                sec,
                secoes_no_mapa,
                f"A seção §{sec} do documento de requisitos do PNIB não aparece na tabela do mapa de conformidade.",
            )

    def test_parcial_sempre_diz_o_que_falta(self):
        """Verifica se todas as linhas marcadas como '🟡 parcial' especificam o que falta."""
        lines = self.mapa_content.splitlines()
        for line in lines:
            if "| 🟡 parcial |" in line:
                self.assertIn(
                    "Falta:",
                    line,
                    f"Linha marcada como '🟡 parcial' não especifica o que falta: '{line}'",
                )

    def test_resumo_bate_com_tabela(self):
        """Verifica se a contagem do resumo executivo bate exatamente com o número de linhas da tabela para cada situação."""
        status_map = {
            "✅ atendido": len(re.findall(r"\|\s*✅ atendido\s*\|", self.mapa_content)),
            "🟡 parcial": len(re.findall(r"\|\s*🟡 parcial\s*\|", self.mapa_content)),
            "❌ não atendido": len(re.findall(r"\|\s*❌ não atendido\s*\|", self.mapa_content)),
            "⏳ fora de prazo": len(re.findall(r"\|\s*⏳ fora de prazo\s*\|", self.mapa_content)),
            "➖ não se aplica": len(re.findall(r"\|\s*➖ não se aplica\s*\|", self.mapa_content)),
        }

        for status_label, count_tabela in status_map.items():
            match_resumo = re.search(
                rf"- \*\*`{re.escape(status_label)}`\*\*:\s*(\d+)",
                self.mapa_content,
            )
            self.assertIsNotNone(
                match_resumo,
                f"Contagem do status '{status_label}' não encontrada no resumo executivo.",
            )
            count_resumo = int(match_resumo.group(1))
            self.assertEqual(
                count_resumo,
                count_tabela,
                f"Divergência de contagem para '{status_label}': resumo={count_resumo}, tabela={count_tabela}",
            )


if __name__ == "__main__":
    unittest.main()
