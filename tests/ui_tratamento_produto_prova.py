"""Formulário de medicamento do Modo Campo: princípio ativo, lote e validade.

Critérios:
1. Preenchendo os três campos e salvando, a aplicação grava os valores.
2. Validade anterior à data da aplicação mostra erro e não grava nada.

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
class TestProdutoNoFormulario(unittest.TestCase):
    def setUp(self):
        import streamlit as st
        st.cache_data.clear()
        self._dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self._dir, "ui_tratamento_produto.db"))
        db.init_db()
        db.clear_cache()
        self.animal_id = db.get_all_animals()[0]["id"]
        with db._conn() as con:
            self._antes = con.execute("SELECT COUNT(*) FROM medications").fetchone()[0]

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin", "name": "Admin", "role": "admin"}
        at.session_state["page"] = "campo"        # o formulário vive no Modo Campo
        at.session_state["campo_id"] = self.animal_id
        at.run()
        self.assertEqual(list(at.exception), [], [e.value for e in at.exception])
        return at

    def _por_chave(self, widgets, chave):
        achados = [w for w in widgets if (w.key or "") == chave]
        self.assertEqual(len(achados), 1, f"esperava 1 widget '{chave}', achei {len(achados)}")
        return achados[0]

    def _salvar(self, at):
        botao = [b for b in at.button if "Salvar Medicamento" in (b.label or "")]
        self.assertEqual(len(botao), 1)
        botao[0].click()
        at.run()

    def _ultima_aplicacao(self):
        with db._conn() as con:
            n = con.execute("SELECT COUNT(*) FROM medications").fetchone()[0]
            r = con.execute("SELECT * FROM medications ORDER BY id DESC LIMIT 1").fetchone()
        return n, (dict(r) if r else None)

    def test_campos_existem_no_formulario(self):
        at = self._tela()
        self._por_chave(at.text_input, "med_principio_ativo")
        self._por_chave(at.text_input, "med_lote_produto")
        self._por_chave(at.date_input, "med_validade_produto")

    def test_salvar_grava_principio_lote_e_validade(self):
        at = self._tela()
        self._por_chave(at.text_input, "med_principio_ativo").set_value("ivermectina")
        self._por_chave(at.text_input, "med_lote_produto").set_value("L2410A")
        validade = date.today() + timedelta(days=120)
        self._por_chave(at.date_input, "med_validade_produto").set_value(validade)

        self._salvar(at)

        n, m = self._ultima_aplicacao()
        self.assertEqual(n, self._antes + 1)
        self.assertEqual((m["principio_ativo"], m["lote_produto"], m["validade_produto"]),
                         ("ivermectina", "L2410A", validade.isoformat()))

    def test_produto_vencido_mostra_erro_e_nao_grava(self):
        at = self._tela()
        self._por_chave(at.text_input, "med_lote_produto").set_value("L-VELHO")
        self._por_chave(at.date_input, "med_validade_produto").set_value(date.today() - timedelta(days=1))

        self._salvar(at)

        self.assertTrue(any("vencido" in e.value for e in at.error), [e.value for e in at.error])
        n, _ = self._ultima_aplicacao()
        self.assertEqual(n, self._antes)


if __name__ == "__main__":
    unittest.main()
