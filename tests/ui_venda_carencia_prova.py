"""A lista de venda respeita a carência?

`register_sale` recusa abate de animal em carência (tests/test_venda_carencia.py),
mas a tela ainda oferecia esses animais na seleção: o usuário só descobria ao
confirmar. Agora, no tipo "abate", a lista os deixa de fora e diz quais são e até
quando; no tipo "criação" nada muda, porque a carência impede o abate.

⚠️ **Não começa com `test_` de propósito** — ver `tests/ui_estados_prova.py`.
Quem executa isto é `tests/test_ui.py`, num subprocesso.
"""

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None

DIAS_DE_CARENCIA = 30


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestListaDeVendaComCarencia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_venda_carencia.db"))
        db.init_db()
        # O seed já tem animais ativos com carência vigente; aqui o cenário é
        # controlado: um animal em carência e os demais livres.
        with db._conn() as con:
            con.execute("UPDATE medications SET withdrawal_days=0")
            con.execute("UPDATE animals SET status='ativo'")
        db.clear_cache()
        ativos = db.get_all_animals(status="ativo")
        cls.preso, cls.livre = ativos[0]["id"], ativos[1]["id"]
        with db._conn() as con:
            uuid = con.execute("SELECT uuid FROM animals WHERE id=?",
                               (cls.preso,)).fetchone()["uuid"]
            con.execute("INSERT INTO medications (animal_uuid,medication_name,med_date,"
                        "withdrawal_days) VALUES(?,?,?,?)",
                        (uuid, "Ivermectina", date.today().isoformat(), DIAS_DE_CARENCIA))
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "financeiro"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def _opcoes(self, at):
        multi = [w for w in at.multiselect if w.label == "Animais a vender"]
        self.assertEqual(len(multi), 1, "esperava 1 seleção 'Animais a vender'")
        return multi[0].options

    def _tem(self, opcoes, brinco):
        return any(o.startswith(f"{brinco} ·") for o in opcoes)

    def _aviso(self, at):
        return [i.value for i in at.info if "Em carência hoje" in i.value]

    def _tipo(self, at, tipo):
        radio = [w for w in at.radio if (w.key or "") == "venda_tipo"][0]
        radio.set_value(tipo)
        at.run()
        self.assertEqual(list(at.exception), [])
        return at

    def test_abate_deixa_o_animal_em_carencia_fora_da_lista(self):
        at = self._tela()                      # "abate" é o tipo padrão
        opcoes = self._opcoes(at)

        self.assertFalse(self._tem(opcoes, self.preso), "animal em carência na lista de abate")
        self.assertTrue(self._tem(opcoes, self.livre), "animal livre sumiu da lista")

    def test_o_aviso_diz_quem_e_ate_quando(self):
        at = self._tela()
        fim = (date.today() + timedelta(days=DIAS_DE_CARENCIA)).strftime("%d/%m/%Y")

        avisos = self._aviso(at)

        self.assertEqual(len(avisos), 1, avisos)
        self.assertIn(self.preso, avisos[0])
        self.assertIn(fim, avisos[0])

    def test_venda_para_criacao_lista_todos_e_nao_avisa(self):
        at = self._tipo(self._tela(), "criacao")
        opcoes = self._opcoes(at)

        self.assertTrue(self._tem(opcoes, self.preso))
        self.assertTrue(self._tem(opcoes, self.livre))
        self.assertEqual(self._aviso(at), [])

    def test_voltar_para_abate_tira_o_animal_de_novo(self):
        at = self._tipo(self._tela(), "criacao")
        at = self._tipo(at, "abate")

        self.assertFalse(self._tem(self._opcoes(at), self.preso))


if __name__ == "__main__":
    unittest.main()
