import os
import sys
import tempfile
import unittest
import uuid

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestPageAnimal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_animal.db"))
        db.init_db()
        db.clear_cache()
        animal_uuid = str(uuid.uuid4())
        # Use existing properties/animals from seed or insert with minimum required fields
        with db._conn() as con:
            # check if properties is already seeded
            prop = con.execute("SELECT id FROM properties LIMIT 1").fetchone()
            if not prop:
                con.execute("INSERT INTO properties (id, titular_name) VALUES (1, 'Teste')")
                prop_id = 1
            else:
                prop_id = prop["id"]

            con.execute("INSERT INTO animals (uuid, id, breed, entry_weight, current_weight, entry_date, status, property_id) VALUES (?, 'A001', 'Nelore', 200, 300, '2023-01-01', 'ativo', ?)", (animal_uuid, prop_id))
            con.execute("INSERT INTO weighings (animal_uuid, weight, weigh_date) VALUES (?, 300, '2023-06-01')", (animal_uuid,))
        db.clear_cache()

    def _tela(self, **estado):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {
            "id": 1,
            "username": "admin",
            "name": "Admin",
            "role": "admin",
        }
        at.session_state["page"] = "animal"
        for k, v in estado.items():
            at.session_state[k] = v
        at.run()
        self.assertEqual(list(at.exception), [])
        return at

    def test_nenhum_animal_selecionado(self):
        at = self._tela(animal_detail=None)
        # Should show a warning
        self.assertTrue(any("Nenhum animal selecionado" in w.value for w in at.warning))

    def test_animal_nao_encontrado(self):
        at = self._tela(animal_detail="NaoExiste999")
        # Should show an error
        self.assertTrue(any("não encontrado" in e.value for e in at.error))

    def test_animal_valido_carrega_detalhes(self):
        at = self._tela(animal_detail="A001")

        # Verify basic UI elements present on animal page
        # It should render animal id
        self.assertTrue(any("A001" in m.value for m in at.markdown))
        # Should have a back button
        botoes = [b for b in at.button if "Voltar" in (b.label or "")]
        self.assertTrue(len(botoes) > 0)

        # Click back button should change page
        botoes[0].click()
        at.run()
        self.assertEqual(at.session_state["page"], "rebanho")


if __name__ == "__main__":
    unittest.main()
