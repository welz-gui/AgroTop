"""A previsão do tempo por propriedade chegou à tela de verdade?

`services/clima_adaptador.py::localizacoes_para_previsao` existia desde a spec
0046, pura, testada, e nunca era chamada — `page_clima` sempre mostrava "a
mesma previsão vale para todos os piquetes da fazenda", mesmo com propriedades
em coordenadas diferentes (ADR 0004: um produtor pode ter mais de uma).

Não depende de rede: `_fetch_forecast` já falha graciosamente (devolve `None`
sem internet) — o que estes testes travam é a **estrutura** da tela (quando
abre aba por localização, quando não abre), não o conteúdo da previsão.

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
class TestPrevisaoPorPropriedade(unittest.TestCase):
    def setUp(self):
        # Por teste, não por classe: cada cenário cria propriedades em
        # coordenadas diferentes, e o número de abas depende exatamente do
        # que existe no banco — precisa nascer limpo a cada teste, não herdar
        # propriedade da execução anterior.
        import streamlit as st
        st.cache_data.clear()
        self._dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self._dir, "ui_clima.db"))
        db.init_db()
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "clima"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    # ── testes ───────────────────────────────────────────────────────────────

    def test_sem_localizacao_nenhuma_pede_para_definir(self):
        """Nem fazenda nem propriedade com coordenada: mensagem, não erro."""
        at = self._tela()
        self.assertTrue(list(at.info), "não pediu para definir localização")

    def test_uma_localizacao_resolvida_nao_abre_aba_por_propriedade(self):
        """Uma coordenada só (fallback da fazenda): sem aba extra — spec 0046
        é explícita que dividir isso em abas seria ruído, não informação."""
        db.set_setting("farm_lat", -15.6)
        db.set_setting("farm_lon", -56.1)
        db.clear_cache()
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        # só as 3 abas fixas de page_clima — nenhuma aba de propriedade.
        self.assertEqual(len(rotulos), 3, f"abas inesperadas: {rotulos}")

    def test_duas_propriedades_em_coordenadas_diferentes_abrem_uma_aba_cada(self):
        """ADR 0004: um produtor pode ter mais de uma propriedade, em lugares
        de verdade distantes — cada uma com sua própria previsão."""
        produtor_id = db.propriedades.padrao()["produtor_id"]
        db.propriedades.criar_propriedade(
            produtor_id, "Fazenda Norte", latitude=-12.0, longitude=-55.0)
        db.propriedades.criar_propriedade(
            produtor_id, "Fazenda Sul", latitude=-20.0, longitude=-52.0)
        db.clear_cache()
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertIn("Fazenda Norte", rotulos, f"abas: {rotulos}")
        self.assertIn("Fazenda Sul", rotulos, f"abas: {rotulos}")

    def test_duas_propriedades_na_mesma_coordenada_dividem_uma_aba(self):
        """Mesma coordenada, mesmo grupo — não duplica chamada nem aba
        (spec 0046: "agrupa propriedades que caem na mesma coordenada").

        Uma terceira propriedade em coordenada diferente é necessária para
        haver mais de uma localização — com só o par (Sede A, Sede B), a
        tela nem abriria aba nenhuma (cenário já coberto pelo teste
        `test_uma_localizacao_...`, spec 0046: uma localização só não gera
        ruído de aba)."""
        produtor_id = db.propriedades.padrao()["produtor_id"]
        db.propriedades.criar_propriedade(
            produtor_id, "Sede A", latitude=-14.0, longitude=-54.0)
        db.propriedades.criar_propriedade(
            produtor_id, "Sede B", latitude=-14.0, longitude=-54.0)
        db.propriedades.criar_propriedade(
            produtor_id, "Fazenda Distante", latitude=-22.0, longitude=-48.0)
        db.clear_cache()
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        agrupada = [r for r in rotulos if "Sede A" in r and "Sede B" in r]
        self.assertEqual(len(agrupada), 1,
                         f"mesma coordenada devia virar uma aba só: {rotulos}")
        self.assertIn("Fazenda Distante", rotulos, f"abas: {rotulos}")


if __name__ == "__main__":
    unittest.main()
