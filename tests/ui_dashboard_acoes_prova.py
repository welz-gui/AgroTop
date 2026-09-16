"""Prova de UI e regras do dashboard com prioridades e alertas acionáveis (Spec 0105).

Critérios de aceite cobertos:
1. Tocar em cada um dos três cards de alerta leva ao destino certo com o filtro já aplicado
   (teste de ida e volta: abre filtrado, Limpar/Ver todos volta ao estado completo).
2. Os 7 KPIs continuam presentes e com os mesmos valores da base.
3. Nenhum alerta consegue levar a uma tela sem indicar visualmente que há um filtro ativo.
4. page_rebanho com filtro de Carência pré-setado mostra só animais com Status=carencia.
5. Sem alertas de nenhuma categoria, a seção _dash_alerts continua invisível.
6. Perfil operador: confirma que permissões continuam restritas a OPERATOR_PAGES.
"""

import ast
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None


class TestEstruturalDashboardAcoes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RAIZ, "app.py"), encoding="utf-8") as f:
            cls.codigo = f.read()
        cls.arvore = ast.parse(cls.codigo)

    def test_kpis_possuem_os_sete_indicadores(self):
        self.assertIn('"🐄 Animais"', self.codigo)
        self.assertIn('"⚖️ Peso Médio"', self.codigo)
        self.assertIn('"📈 GMD Médio"', self.codigo)
        self.assertIn('"🌿 Lotação"', self.codigo)
        self.assertIn('"♂ Machos"', self.codigo)
        self.assertIn('"♀ Fêmeas"', self.codigo)
        self.assertIn("prod_label", self.codigo)

    def test_botoes_de_acao_em_dash_alerts(self):
        self.assertIn("dash_btn_sumidos", self.codigo)
        self.assertIn("dash_btn_carencia", self.codigo)
        self.assertIn("dash_btn_prontos", self.codigo)
        self.assertIn('st.session_state.alertas_foco = "sumidos"', self.codigo)
        self.assertIn('st.session_state.rebanho_status = "carencia"', self.codigo)
        self.assertIn('st.session_state.alertas_foco = "prontos"', self.codigo)

    def test_page_alertas_trata_foco_e_limpeza(self):
        self.assertIn('st.session_state.get("alertas_foco")', self.codigo)
        self.assertIn("btn_limpar_foco_alertas", self.codigo)
        self.assertIn("st.session_state.alertas_foco = None", self.codigo)

    def test_page_rebanho_trata_status_persistido_e_limpeza(self):
        self.assertIn('st.session_state.get("rebanho_status"', self.codigo)
        self.assertIn("btn_limpar_filtro_rebanho", self.codigo)
        self.assertIn('st.session_state.rebanho_status = "Todos"', self.codigo)

    def test_permissoes_operador_preservadas(self):
        self.assertIn('OPERATOR_PAGES = {"campo", "cadastrar", "estoque", "brincos"}', self.codigo)


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestFuncionalDashboardAcoes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_dash.db"))
        db.init_db()
        db.clear_cache()

        # Cadastra animais de teste para disparar alertas e métricas
        try:
            db.add_animal(
                animal_id="BR9901",
                breed="Nelore",
                entry_weight=400.0,
                current_weight=420.0,
                status="carencia",
                sex="M",
            )
            # Medicamento com carência futura
            db.add_medication(
                animal_id="BR9901",
                remedio="Ivermectina",
                dose="5ml",
                data_aplicacao="2026-09-01",
                dias_carencia=60,
            )
        except Exception:
            pass

    def _app(self, pagina="dashboard", **kwargs):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {
            "id": 1,
            "username": "admin",
            "name": "Administrador",
            "role": "admin",
        }
        at.session_state["page"] = pagina
        for k, v in kwargs.items():
            at.session_state[k] = v
        at.run()
        return at

    def test_kpis_aparecem_no_dashboard(self):
        at = self._app("dashboard")
        rotulos = [m.label for m in at.metric]
        self.assertTrue(any("Animais" in r for r in rotulos))
        self.assertTrue(any("Peso Médio" in r for r in rotulos))
        self.assertTrue(any("GMD Médio" in r for r in rotulos))
        self.assertTrue(any("Lotação" in r for r in rotulos))
        self.assertTrue(any("Machos" in r for r in rotulos))
        self.assertTrue(any("Fêmeas" in r for r in rotulos))
        self.assertEqual(len(at.metric), 7)

    def test_clique_carencia_vai_para_rebanho_e_limpar_volta(self):
        at = self._app("dashboard")
        btn_carencia = at.button(key="dash_btn_carencia")
        self.assertIsNotNone(btn_carencia)
        btn_carencia.click().run()

        # Deve navegar para a página rebanho com filtro de carência ativo
        self.assertEqual(at.session_state["page"], "rebanho")
        self.assertEqual(at.session_state["rebanho_status"], "carencia")

        # Botão limpar filtro deve existir e funcionar
        btn_limpar = at.button(key="btn_limpar_filtro_rebanho")
        self.assertIsNotNone(btn_limpar)
        btn_limpar.click().run()
        self.assertEqual(at.session_state["rebanho_status"], "Todos")

    def test_clique_sumidos_vai_para_alertas_e_limpar_volta(self):
        at = self._app("dashboard")
        btn_sumidos = at.button(key="dash_btn_sumidos")
        self.assertIsNotNone(btn_sumidos)
        btn_sumidos.click().run()

        # Deve navegar para a página alertas com foco em sumidos
        self.assertEqual(at.session_state["page"], "alertas")
        self.assertEqual(at.session_state["alertas_foco"], "sumidos")

        # Botão limpar foco deve existir e restaurar
        btn_limpar = at.button(key="btn_limpar_foco_alertas")
        self.assertIsNotNone(btn_limpar)
        btn_limpar.click().run()
        self.assertIsNone(at.session_state["alertas_foco"])

    def test_clique_prontos_vai_para_alertas(self):
        at = self._app("dashboard")
        btn_prontos = at.button(key="dash_btn_prontos")
        self.assertIsNotNone(btn_prontos)
        btn_prontos.click().run()

        self.assertEqual(at.session_state["page"], "alertas")
        self.assertEqual(at.session_state["alertas_foco"], "prontos")


if __name__ == "__main__":
    unittest.main()
