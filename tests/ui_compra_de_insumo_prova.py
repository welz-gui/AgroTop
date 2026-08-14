"""A compra de insumo com nota fiscal chegou à tela de verdade?

Trilha 3 (ROADMAP §5, Estoque → Financeiro): "compra gera conta a pagar" era
o item ainda não feito do escopo — o sistema só tinha entrada avulsa de
estoque (`add_insumo_entry`, 1 insumo por lançamento, sem fornecedor,
documento ou parcelamento). `services/compras.py` (parcelamento e total da
nota) e `repositories/compras.py::registrar` (a operação atômica: estoque +
contas a pagar juntos) são a ligação — a aba "🛒 Compra com Nota Fiscal" em
Estoque, e "📋 Contas a Pagar" em Financeiro.

Estes testes travam:

- **A nota junta vários itens antes de registrar** — o carrinho vive em
  `session_state`, não em cada widget isolado.
- **Registrar grava estoque e contas a pagar juntos** — não só o service
  puro (isso `tests/test_compras.py` já cobre): a ponte de verdade contra o
  banco.
- **A tela de Contas a Pagar mostra e permite quitar** o que a compra gerou.

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
class TestCompraDeInsumoNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_compra.db"))
        db.init_db()
        db.clear_cache()
        cls.insumo = db.get_all_insumos()[0]

    def setUp(self):
        with db._conn() as con:
            con.execute("DELETE FROM contas_pagar")
            con.execute("DELETE FROM compra_itens")
            con.execute("DELETE FROM compras")
        db.clear_cache()

    def _tela(self, page):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = page
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def _por_chave(self, widgets, chave):
        achados = [w for w in widgets if (w.key or "") == chave]
        self.assertEqual(len(achados), 1,
                         f"esperava 1 widget com chave '{chave}', achei {len(achados)}")
        return achados[0]

    def _adicionar_item(self, at, quantidade, custo):
        self._por_chave(at.number_input, "compra_add_qtd").set_value(quantidade)
        self._por_chave(at.number_input, "compra_add_custo").set_value(custo)
        at.run()
        self._por_chave(at.button, "compra_add_btn").click()
        at.run()
        return at

    def _registrar(self, at, *, fornecedor="Agropecuária Teste", doc="NF-1",
                   parcelas=1):
        """Clica em Registrar e devolve o `at` já rodado de novo.

        Não checa `at.success` aqui: o handler faz `st.success(...)` seguido de
        `st.rerun()` — o `AppTest` persegue o rerun interno e devolve o estado
        da execução final, não da que exibiu a mensagem. A prova real de que
        registrou é o banco (é o que os testes conferem depois), não o toast.
        """
        self._por_chave(at.text_input, "compra_fornecedor").set_value(fornecedor)
        self._por_chave(at.text_input, "compra_doc_num").set_value(doc)
        self._por_chave(at.number_input, "compra_num_parcelas").set_value(parcelas)
        at.run()
        self._por_chave(at.button, "compra_registrar_btn").click()
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção ao registrar: {[e.value for e in at.exception]}")
        return at

    # ── testes ───────────────────────────────────────────────────────────────

    def test_as_abas_existem(self):
        at_estoque = self._tela("estoque")
        rotulos_e = [t.label for t in at_estoque.tabs]
        self.assertTrue(any("Compra com Nota Fiscal" in r for r in rotulos_e), rotulos_e)

        at_fin = self._tela("financeiro")
        rotulos_f = [t.label for t in at_fin.tabs]
        self.assertTrue(any("Contas a Pagar" in r for r in rotulos_f), rotulos_f)

    def test_botao_registrar_comeca_desabilitado_sem_item(self):
        at = self._tela("estoque")
        self.assertTrue(
            self._por_chave(at.button, "compra_registrar_btn").disabled,
            "deixou registrar uma compra sem nenhum item")

    def test_adicionar_item_preenche_o_carrinho(self):
        at = self._tela("estoque")
        self._adicionar_item(at, 20.0, 9.5)
        carrinho = at.session_state["compra_itens_atual"]
        self.assertEqual(len(carrinho), 1)
        self.assertEqual(carrinho[0]["insumo_id"], self.insumo["id"])
        self.assertEqual(carrinho[0]["quantidade"], 20.0)
        self.assertFalse(
            self._por_chave(at.button, "compra_registrar_btn").disabled)

    def test_registrar_grava_estoque_e_contas_a_pagar_juntos(self):
        # Estoque fresco, não o `self.insumo` de setUpClass: outros testes desta
        # classe também registram compra e mudam o saldo do mesmo insumo.
        estoque_antes = [i for i in db.get_all_insumos()
                         if i["id"] == self.insumo["id"]][0]["current_stock"]
        at = self._tela("estoque")
        self._adicionar_item(at, 20.0, 9.5)
        self._registrar(at, parcelas=2)

        self.assertEqual(at.session_state["compra_itens_atual"], [],
                         "carrinho não foi limpo após registrar")

        db.clear_cache()
        insumo_depois = [i for i in db.get_all_insumos()
                         if i["id"] == self.insumo["id"]][0]
        self.assertEqual(insumo_depois["current_stock"], estoque_antes + 20.0)

        contas = db.compras.listar_contas_pagar()
        self.assertEqual(len(contas), 2, "2 parcelas deveriam virar 2 contas a pagar")
        total = round(sum(c["valor"] for c in contas), 2)
        self.assertEqual(total, round(20.0 * 9.5, 2))
        self.assertTrue(all(c["status"] == "aberto" for c in contas))

    def test_tela_de_contas_a_pagar_mostra_o_que_a_compra_gerou(self):
        at_e = self._tela("estoque")
        self._adicionar_item(at_e, 10.0, 4.0)
        self._registrar(at_e, fornecedor="Fornecedor ABC", doc="NF-42", parcelas=1)

        at_f = self._tela("financeiro")
        metricas = {m.label: m.value for m in at_f.metric}
        self.assertIn("Em Aberto", metricas)
        self.assertEqual(metricas["Em Aberto"], "1")

    def test_marcar_como_paga_fecha_a_conta(self):
        at_e = self._tela("estoque")
        self._adicionar_item(at_e, 5.0, 2.0)
        self._registrar(at_e, parcelas=1)

        db.clear_cache()
        conta_id = db.compras.listar_contas_pagar("aberto")[0]["id"]

        at_f = self._tela("financeiro")
        self._por_chave(at_f.selectbox, "pag_conta_selecionada")
        at_f.run()
        self._por_chave(at_f.button, "pag_confirmar_btn").click()
        at_f.run()

        self.assertEqual(list(at_f.exception), [])
        db.clear_cache()
        conta = [c for c in db.compras.listar_contas_pagar() if c["id"] == conta_id][0]
        self.assertEqual(conta["status"], "pago")
        self.assertIsNotNone(conta["data_pagamento"])


if __name__ == "__main__":
    unittest.main()
