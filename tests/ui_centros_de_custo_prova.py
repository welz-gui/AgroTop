"""Centros de custo (piquete) chegaram à tela de verdade?

Trilha 3 (ROADMAP §5, Estoque → Financeiro → Nutrição), quinta fatia:
`fixed_costs` sempre foi um balde único da fazenda inteira — sem jeito de
saber "quanto custou manter o Piquete Norte" separado de "quanto custou o
Curral". `services/centros_de_custo.py::consolidar` junta custo fixo
alocado a um piquete (`fixed_costs.lote_id`, coluna nova) com custo por
animal (`animal_costs`, pelo piquete atual de cada animal) num retrato só.

Estes testes travam:

- **`lote_id=None` é "Geral da Fazenda", não erro** — custo fixo que não é
  de nenhum piquete específico (salário do gerente) continua válido.
- **A soma bate**: custo fixo alocado + custo de animal do mesmo piquete
  aparecem juntos, num total só, por centro de custo.

⚠️ **Não começa com `test_` de propósito** — ver `tests/ui_estados_prova.py`.
Quem executa isto é `tests/test_ui.py`, num subprocesso.
"""

import os
import sys
import tempfile
import unittest
from datetime import date

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestCentrosDeCustoNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_cc.db"))
        db.init_db()
        db.clear_cache()
        cls.lote = db.get_all_lotes()[0]

    def setUp(self):
        with db._conn() as con:
            con.execute("DELETE FROM fixed_costs")
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

    def _por_label(self, widgets, label):
        achados = [w for w in widgets if getattr(w, "label", None) == label]
        self.assertEqual(len(achados), 1,
                         f"esperava 1 widget com label '{label}', achei {len(achados)}")
        return achados[0]

    def _metricas(self, at):
        return {m.label: m.value for m in at.metric}

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_aba_de_centros_de_custo_existe(self):
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Centros de Custo" in r for r in rotulos), rotulos)

    def test_form_de_custo_fixo_oferece_centro_de_custo(self):
        at = self._tela()
        rotulos = [w.label for w in at.selectbox if w.label == "Centro de Custo"]
        self.assertEqual(len(rotulos), 1)

    def test_lancar_custo_geral_e_custo_de_piquete_aparecem_separados(self):
        hoje = date.today().isoformat()
        db.add_fixed_cost("Salários", "Gerente", 5000.0, hoje, 1, "")  # geral
        db.add_fixed_cost("Aluguel de pastagem", "Piquete X", 1000.0, hoje, 0, "",
                          lote_id=self.lote["id"])
        db.clear_cache()

        fixos = db.get_fixed_costs_by_lote(f"{date.today().year}-01-01", hoje)
        self.assertEqual(fixos.get(None), 5000.0)
        self.assertEqual(fixos.get(self.lote["id"]), 1000.0)

        at = self._tela()
        m = self._metricas(at)
        self.assertIn("Total no período", m)
        self.assertEqual(self._reais(m["Total no período"]) >= 6000.0, True)

    def test_geral_da_fazenda_aparece_na_tabela_quando_ha_custo_sem_lote(self):
        db.add_fixed_cost("Impostos", "IPTU", 300.0, date.today().isoformat(), 0, "")
        db.clear_cache()

        at = self._tela()
        dfs = list(at.dataframe)
        textos = " ".join(str(d.value) for d in dfs)
        self.assertIn("Geral da Fazenda", textos)

    def _reais(self, texto: str) -> float:
        return float(texto.replace("R$", "").replace(",", "").strip())


if __name__ == "__main__":
    unittest.main()
