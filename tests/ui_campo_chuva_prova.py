"""Registro rápido de chuva chegou ao Modo Campo?

Antes desta tela, só o admin registrava chuva (`page_clima`, fora de
`OPERATOR_PAGES`) — o operador, que é quem está no campo olhando o
pluviômetro, não tinha como. `_campo_chuva()` espelha o padrão já usado por
`_campo_trato()`: poucos campos, uma confirmação, disponível pros dois papéis.

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
class TestChuvaDoDia(unittest.TestCase):
    def setUp(self):
        import streamlit as st
        st.cache_data.clear()
        self._dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self._dir, "ui_campo_chuva.db"))
        db.init_db()
        db.clear_cache()

    def _tela(self, role="operator"):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "op1",
                                    "name": "Op1", "role": role}
        at.session_state["page"] = "campo"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def _por_chave(self, widgets, chave):
        achados = [w for w in widgets if (w.key or "") == chave]
        self.assertEqual(len(achados), 1,
                         f"esperava 1 widget com chave '{chave}', achei {len(achados)}")
        return achados[0]

    # ── testes ───────────────────────────────────────────────────────────────

    def test_aba_existe_e_operador_tem_acesso(self):
        """Operador é o público principal: ele está no campo, admin está na sede."""
        at = self._tela(role="operator")
        self.assertIn("🌧️ Chuva do Dia", [t.label for t in at.tabs])
        self._por_chave(at.number_input, "campo_chuva_mm")
        self._por_chave(at.selectbox, "campo_chuva_lote")

    def test_admin_tambem_acessa(self):
        at = self._tela(role="admin")
        self.assertIn("🌧️ Chuva do Dia", [t.label for t in at.tabs])

    def test_registro_grava_e_aparece_no_resumo_do_dia(self):
        at = self._tela(role="operator")
        # step=1.0 no widget: usar valor alinhado ao passo evita ambiguidade
        # de arredondamento no set_value do AppTest.
        self._por_chave(at.number_input, "campo_chuva_mm").set_value(15.0)
        at.run()
        botao = [b for b in at.button if "Registrar chuva de hoje" in (b.label or "")][0]
        botao.click()
        at.run()
        # Não checa `at.success` aqui: o handler faz `st.success(...)` seguido
        # de `st.rerun()` — o `AppTest` persegue o rerun interno e devolve o
        # estado pós-rerun, onde a mensagem de sucesso já não existe (mesmo
        # padrão documentado em ui_compra_de_insumo_prova/ui_transferencia_
        # animais_prova). O que prova o registro é o efeito no banco abaixo.
        self.assertEqual(list(at.exception), [])

        hoje = date.today().isoformat()
        leituras = db.get_rain(hoje, hoje)
        self.assertEqual(len(leituras), 1)
        self.assertEqual(leituras[0]["rain_mm"], 15.0)
        self.assertEqual(leituras[0]["operator"], "Op1")

        # Reabrindo a aba, o resumo do que já foi lido hoje aparece.
        at2 = self._tela(role="operator")
        self.assertTrue(any("Já registrado hoje" in i.value for i in at2.info),
                        "resumo de leitura já feita não apareceu")

    def test_zero_mm_e_registro_valido(self):
        """Registrar 0mm é dado — 'conferi e não choveu' —, não erro."""
        at = self._tela(role="operator")
        botao = [b for b in at.button if "Registrar chuva de hoje" in (b.label or "")][0]
        botao.click()
        at.run()
        self.assertEqual(list(at.exception), [])
        hoje = date.today().isoformat()
        self.assertEqual(len(db.get_rain(hoje, hoje)), 1)


if __name__ == "__main__":
    unittest.main()
