"""Estoque: lote e validade na entrada, e o aviso de produto vencido ou perto de vencer.

Critérios:
1. Registrando uma entrada com lote e validade, os dois ficam gravados na entrada.
2. Produto que já chega vencido mostra erro e não entra no estoque.
3. A tela avisa dos lotes vencidos ou perto de vencer e lista os lotes em estoque.

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


def _dia(n):
    return (date.today() + timedelta(days=n)).isoformat()


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestLoteNaEntradaDeEstoque(unittest.TestCase):
    def setUp(self):
        import streamlit as st
        st.cache_data.clear()
        self._dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self._dir, "ui_validade_estoque.db"))
        db.init_db()
        db.clear_cache()
        # O formulário vem com o primeiro insumo da lista (ordem da página).
        self.insumo = db.get_all_insumos()[0]
        self._antes = len(self._entradas())

    def _entradas(self):
        with db._conn() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM insumo_transactions WHERE insumo_id=? AND type='entrada' ORDER BY id",
                (self.insumo["id"],)).fetchall()]

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin", "name": "Admin", "role": "admin"}
        at.session_state["page"] = "estoque"
        at.run()
        self.assertEqual(list(at.exception), [], [e.value for e in at.exception])
        return at

    def _por_chave(self, widgets, chave):
        achados = [w for w in widgets if (w.key or "") == chave]
        self.assertEqual(len(achados), 1, f"esperava 1 widget '{chave}', achei {len(achados)}")
        return achados[0]

    def _registrar(self, at):
        botao = [b for b in at.button if "Registrar Entrada" in (b.label or "")]
        self.assertEqual(len(botao), 1)
        botao[0].click()
        at.run()
        self.assertEqual(list(at.exception), [], [e.value for e in at.exception])

    def test_campos_existem_no_formulario(self):
        at = self._tela()
        self._por_chave(at.text_input, "entrada_lote")
        self._por_chave(at.date_input, "entrada_validade")

    def test_entrada_com_lote_e_validade_grava_os_dois(self):
        at = self._tela()
        self._por_chave(at.text_input, "entrada_lote").set_value("L2410A")
        self._por_chave(at.date_input, "entrada_validade").set_value(date.today() + timedelta(days=120))
        self._registrar(at)

        entradas = self._entradas()
        self.assertEqual(len(entradas), self._antes + 1)
        self.assertEqual((entradas[-1]["lote_produto"], entradas[-1]["validade_produto"]),
                         ("L2410A", _dia(120)))

    def test_produto_vencido_mostra_erro_e_nao_entra(self):
        at = self._tela()
        self._por_chave(at.text_input, "entrada_lote").set_value("L-VELHO")
        self._por_chave(at.date_input, "entrada_validade").set_value(date.today() - timedelta(days=1))
        self._registrar(at)

        self.assertTrue(any("vencido" in e.value for e in at.error), [e.value for e in at.error])
        self.assertEqual(len(self._entradas()), self._antes)

    def test_aviso_de_lote_perto_de_vencer_e_tabela_de_lotes(self):
        db.add_insumo_entry(self.insumo["id"], 25.0, 1.0, "ana", "PERTO-23", _dia(7))
        db.clear_cache()

        at = self._tela()

        avisos = " ".join(e.value for e in at.error)
        self.assertIn("perto de vencer", avisos)
        self.assertIn("PERTO-23", avisos)
        tabelas = [df.value for df in at.dataframe]
        self.assertTrue(any("Lote" in t.columns and "PERTO-23" in set(t["Lote"]) for t in tabelas),
                        "a tabela de lotes em estoque deveria listar o lote da entrada")


if __name__ == "__main__":
    unittest.main()
