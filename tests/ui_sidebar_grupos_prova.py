"""Prova estrutural da navegação agrupada da sidebar (Spec 0103).

O app é executado por ``tests.test_ui`` em subprocesso. Esta prova lê a
constante de navegação sem importar o Streamlit, garantindo que o contrato de
rotas não dependa do estado de um banco ou de uma sessão de usuário.
"""

import ast
import os
import unittest


RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSidebarAgrupada(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RAIZ, "app.py"), encoding="utf-8") as arquivo:
            cls.codigo = arquivo.read()
        cls.arvore = ast.parse(cls.codigo)

    def _valor_da_constante(self, nome):
        for no in self.arvore.body:
            if isinstance(no, ast.Assign) and any(
                isinstance(alvo, ast.Name) and alvo.id == nome for alvo in no.targets
            ):
                return ast.literal_eval(no.value)
        self.fail(f"constante {nome} não encontrada")

    def test_admin_tem_os_20_destinos_em_um_unico_grupo(self):
        grupos = self._valor_da_constante("SIDEBAR_GROUPS")
        esperados = {
            "Visão geral": ("dashboard", "desempenho", "alertas"),
            "Operação": ("campo", "rebanho", "cadastrar", "lotes", "nutricao", "sanitario", "clima"),
            "Gestão": ("financeiro", "estoque", "relatorios"),
            "Rastreabilidade": ("brincos", "movimentacao", "propriedades", "regras", "sincronizacao"),
            "Apoio e administração": ("assistente", "admin"),
        }
        self.assertEqual(tuple(nome for nome, _ in grupos), tuple(esperados))
        chaves = []
        for nome, paginas in grupos:
            atuais = tuple(pagina[2] for pagina in paginas)
            self.assertEqual(atuais, esperados[nome])
            chaves.extend(atuais)
        self.assertEqual(len(chaves), 20)
        self.assertEqual(len(set(chaves)), 20)

    def test_operador_filtra_somente_seus_quatro_destinos(self):
        operador = self._valor_da_constante("OPERATOR_PAGES")
        self.assertEqual(operador, {"campo", "cadastrar", "estoque", "brincos"})
        self.assertIn('page for page in group_pages if page[2] in OPERATOR_PAGES', self.codigo)
        self.assertIn('if user["role"] == "admin" else', self.codigo)

    def test_cabecalhos_sao_estaticos_e_badges_continuam_dinamicos(self):
        self.assertIn('st.markdown(f"**{group_label}**")', self.codigo)
        self.assertNotIn("st.expander(group_label", self.codigo)
        self.assertIn('"estoque": f" 🔴{len(low_stk)}" if low_stk else ""', self.codigo)
        self.assertIn('"alertas": f" 🔴{n_alerts}" if n_alerts else ""', self.codigo)


if __name__ == "__main__":
    unittest.main()
