"""A correlação chuva×GMD chegou à tela — e a projeção de abate parou de
reimplementar a mesma conta com um bug de arredondamento?

`services/projecao.py` tinha três funções públicas, todas sem consumidor:
`projetar_abate`/`projetar_lote` (a tela de "Projeção de Abate" já existia,
mas `database.py::projecao_abate` reimplementava a mesma conta *duplicada*
— R8 — com `round()` em vez de `ceil()`) e `correlacao_chuva_gmd` (sem tela
nenhuma). A spec 0040 escreveu `services/projecao_adaptador.py
::series_mensais`, a ponte para esta última; a primeira não precisava de
adaptador — só de parar de reimplementar (2026-08-14).

Estes testes travam o que a integração corrigiu e montou:

- **O bug de arredondamento** (`tests/test_regras_negocio.py` já tem a
  versão de unidade; aqui é a versão de ponta a ponta, pela tela).
- **`situacao` diferencia "perdendo peso" de "sem dados"** — antes os dois
  casos eram visualmente idênticos ("— sem GMD"), escondendo um problema
  de saúde/pasto atrás da mesma cara de "faltou pesar".
- **A aba "🌧️ Chuva × GMD" existe e não quebra** sem dados suficientes.

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


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestProjecaoNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_projecao.db"))
        db.init_db()
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "desempenho"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_aba_de_chuva_gmd_existe(self):
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Chuva" in r for r in rotulos),
                        f"nenhuma aba de chuva × GMD encontrada: {rotulos}")

    def test_tela_nao_quebra_sem_dados_de_chuva(self):
        self._tela()  # já falha se houver exceção; banco novo não tem pluviometria

    def test_dias_fracionados_arredondam_para_cima_na_tela(self):
        """Ponta a ponta do bug corrigido: db.projecao_abate_bulk (o que a
        tela chama) não pode arredondar para baixo."""
        entrada = (date.today() - timedelta(days=60)).isoformat()
        db.add_animal(db.AnimalData("PROJ1", "Nelore", "M", None, entrada,
                      300.0, 500.0, 1000.0, None, None))
        db.clear_cache()
        db.add_weighing("PROJ1", 370.0, (date.today() - timedelta(days=11)).isoformat())
        db.add_weighing("PROJ1", 400.0, (date.today() - timedelta(days=1)).isoformat())
        db.clear_cache()

        r = db.projecao_abate(db.get_animal("PROJ1"))
        # falta 100 kg a 3 kg/dia = 33,33 dias -> ceil = 34, nunca 33
        self.assertEqual(r["falta"], 100.0)
        self.assertEqual(r["dias"], 34)

        bulk = db.projecao_abate_bulk([db.get_animal("PROJ1")])["PROJ1"]["projecao"]
        self.assertEqual(bulk["dias"], 34)

    def test_perdendo_peso_aparece_diferenciado_de_sem_dados(self):
        entrada = (date.today() - timedelta(days=60)).isoformat()
        db.add_animal(db.AnimalData("PROJ2", "Nelore", "F", None, entrada,
                      300.0, 500.0, 1000.0, None, None))
        db.clear_cache()
        db.add_weighing("PROJ2", 440.0, (date.today() - timedelta(days=11)).isoformat())
        db.add_weighing("PROJ2", 420.0, (date.today() - timedelta(days=1)).isoformat())
        db.clear_cache()

        r = db.projecao_abate(db.get_animal("PROJ2"))
        self.assertIsNone(r["dias"])
        self.assertEqual(r["situacao"], "perdendo_peso")

        at = self._tela()
        textos = " ".join(w.value for w in at.warning)
        self.assertIn("perdendo peso", textos.casefold(),
                      f"alerta de perda de peso não apareceu: {textos}")

    def test_correlacao_com_dados_reais_do_banco(self):
        """Reproduz a mesma cadeia que a aba usa: banco real → adaptador →
        correlacao_chuva_gmd()."""
        from services.projecao_adaptador import series_mensais
        from services.projecao import correlacao_chuva_gmd

        leituras = db.get_rain()
        pesagens = db.get_all_weighings()
        series = series_mensais(leituras, pesagens)
        resultado = correlacao_chuva_gmd(series)

        self.assertIn("n", resultado)
        self.assertIn("interpretacao", resultado)
        self.assertEqual(resultado["n"], len(series))


if __name__ == "__main__":
    unittest.main()
