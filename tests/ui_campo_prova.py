"""Prova de UI do Modo Campo (page_campo)."""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import date

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestModoCampo(unittest.TestCase):
    def setUp(self):
        import streamlit as st
        st.cache_data.clear()
        self._dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self._dir, "ui_campo.db"))
        db.init_db()
        db.clear_cache()

    def tearDown(self):
        shutil.rmtree(self._dir, ignore_errors=True)

    def _app(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {
            "id": 1,
            "username": "op1",
            "name": "Op1",
            "role": "operator"
        }
        at.session_state["page"] = "campo"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def test_page_campo_renderiza_abas_corretamente(self):
        at = self._app()
        # Verifica se as abas estão presentes
        tab_labels = [tab.label for tab in at.tabs]
        self.assertTrue(any("Trato do Dia" in label for label in tab_labels))
        self.assertIn("🌧️ Chuva do Dia", tab_labels)
        self.assertIn("🐄 Manejo do Animal", tab_labels)
        self.assertIn("📥 Importar CSV", tab_labels)

        # Verifica o título da página
        self.assertTrue(any("Modo Campo" in md.value for md in at.markdown))

    def test_badge_de_tratos_pendentes(self):
        hoje = date.today().isoformat()
        # Adiciona um lote e um trato pendente para verificar se o badge aparece
        db.add_lote(db.LoteData(lote_id="Lote 1", name="Lote 1", area_ha=10, capacity_ua=10))
        # Adiciona animais no lote 1
        db.add_animal(db.AnimalData(animal_id="BR1234", breed="Nelore", sex="M", birth_date=None, entry_date=hoje, entry_weight=100.0, target_weight=200.0, purchase_price=None, lote_id="Lote 1", fornecedor_id=None))

        # Simula a adição de um plano alimentar ativo no lote 1
        db.add_feeding_plan(db.FeedingPlanCreate(lote_id="Lote 1", product_name="Silagem", quantity=10.0, unit="kg", frequency="Diário"))
        at = self._app()
        tab_labels = [tab.label for tab in at.tabs]
        self.assertTrue(any("🔴" in label for label in tab_labels))
        self.assertTrue(any("Trato do Dia" in label for label in tab_labels))


if __name__ == "__main__":
    unittest.main()
