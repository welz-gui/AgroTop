"""A previsão de ruptura de estoque chegou à tela de verdade?

`services/previsao_estoque.py::prever` existia desde a spec 0018, pura, testada,
e nunca foi chamada — o alerta de estoque continuava binário (abaixo do mínimo
ou não), avisando só quando já era tarde. A spec 0039 escreveu o adaptador
(`services/previsao_estoque_adaptador.py`) que traduz `insumos` + `feeding_plans`
para o formato que `prever()` espera; ligar os dois à aba "📈 Previsão de Ruptura"
de `page_estoque()` é o que fecha o ciclo.

Estes testes travam duas coisas:

- **O defeito da PR #101 não pode voltar por este caminho.** `_consumo_diario_por_insumo`
  calculava a mesma conta inline, com um bug real: frequência desconhecida
  (`"quinzenal"`) caía num `.get(freq, 1.0)` e virava consumo diário inventado.
  Ligar o adaptador aqui precisa ter fechado esse defeito também neste consumidor,
  não só no novo (spec 0039 v2, PR #105).
- **Insumo sem plano de trato ativo é "sem dados", não crítico por acaso** — ausência
  de consumo conhecido é informação, não erro.

⚠️ **Não começa com `test_` de propósito** — ver `tests/ui_estados_prova.py`.
Quem executa isto é `tests/test_ui.py`, num subprocesso.
"""

import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestPrevisaoDeEstoqueNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_previsao_estoque.db"))
        db.init_db()
        db.clear_cache()
        cls.lote_id = db.get_all_lotes()[0]["id"]

    def _insumo(self, nome, unit="kg", saldo=100.0, minimo=20.0):
        db.add_new_insumo(db.InsumoCreate(nome, "trato", unit, saldo, minimo, 2.0))
        db.clear_cache()
        return next(i for i in db.get_all_insumos() if i["name"] == nome)

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "estoque"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_aba_de_previsao_existe(self):
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Previsão" in r for r in rotulos),
                        f"nenhuma aba de previsão encontrada: {rotulos}")

    def test_insumo_com_consumo_diario_mostra_dias_restantes(self):
        ins = self._insumo("Sal Mineral Prova", saldo=20.0, minimo=5.0)
        db.add_feeding_plan(self.lote_id, "Sal", 2.0, "kg", "diario",
                            insumo_id=ins["id"])
        db.clear_cache()

        at = self._tela()
        texto = " ".join(df.value.to_string() for df in at.dataframe)
        self.assertIn("Sal Mineral Prova", texto)
        # 20 kg de saldo ÷ 2 kg/dia = 10 dias — não pode aparecer "—"
        self.assertIn("10,0", texto)

    def test_frequencia_desconhecida_nao_infla_consumo(self):
        """O defeito da PR #101: 'quinzenal' não pode virar 1x/dia.

        Um insumo com plano quinzenal de 14 kg tratado como diário devolveria
        14 kg/dia — saldo de 100 kg sumiria em ~7 dias. Tratado corretamente
        (plano ignorado, consumo 0), o insumo entra como 'sem dados'.
        """
        ins = self._insumo("Nucleo Proteico Prova", saldo=100.0, minimo=10.0)
        db.add_feeding_plan(self.lote_id, "Nucleo", 14.0, "kg", "quinzenal",
                            insumo_id=ins["id"])
        db.clear_cache()

        at = self._tela()
        texto = " ".join(df.value.to_string() for df in at.dataframe)
        self.assertIn("Nucleo Proteico Prova", texto)
        self.assertIn("Sem dados", texto,
                      "plano quinzenal inflou o consumo em vez de ser ignorado")

    def test_insumo_sem_plano_ativo_e_sem_dados_nao_critico_por_acaso(self):
        self._insumo("Insumo Sem Plano Prova", saldo=50.0, minimo=10.0)
        at = self._tela()
        texto = " ".join(df.value.to_string() for df in at.dataframe)
        self.assertIn("Insumo Sem Plano Prova", texto)
        self.assertIn("Sem dados", texto)


if __name__ == "__main__":
    unittest.main()
