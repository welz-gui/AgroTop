"""A venda a prazo chegou à tela de verdade?

Trilha 3 (ROADMAP §5, Estoque → Financeiro → Nutrição), segunda fatia: até
aqui `register_sale` sempre tratava a venda como recebida na hora — a receita
ia para `sales.total_value` no dia da venda e nunca havia rastro de QUANDO o
dinheiro realmente chegaria. Venda a prazo (comum em pecuária — 30/60/90
dias) simplesmente não existia como conceito.

`services/compras.py::gerar_parcelas` é reaproveitado aqui (R8 — mesma conta
de parcelamento, venda ou compra) via `repositories/financeiro.py`. A aba
"💵 Registrar Venda" ganhou o checkbox "Venda a prazo?"; "📥 Contas a Receber"
(Financeiro) é onde se acompanha e se marca como recebida.

Estes testes travam:

- **Venda à vista continua sem gerar nada** — o padrão de sempre, preservado.
- **Venda a prazo grava as parcelas** — e a receita/lucro por venda continuam
  os mesmos de sempre (a competência não muda, só o rastro do recebimento).
- **A tela de Contas a Receber mostra e permite quitar** o que a venda gerou.

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
class TestContasAReceberNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_receber.db"))
        db.init_db()
        db.clear_cache()

    def setUp(self):
        with db._conn() as con:
            con.execute("DELETE FROM contas_receber")
            con.execute("DELETE FROM sales")
            con.execute("UPDATE animals SET status='ativo'")
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

    def _por_label(self, widgets, label):
        achados = [w for w in widgets if getattr(w, "label", None) == label]
        self.assertEqual(len(achados), 1,
                         f"esperava 1 widget com label '{label}', achei {len(achados)}")
        return achados[0]

    def _vender(self, at, *, animal_opcao=0, a_prazo=False, parcelas=1,
               comprador="Frigorífico Teste"):
        """Reproduz o fluxo real da aba Registrar Venda (modo 'cabeça')."""
        self._por_chave(at.radio, "venda_modo").set_value("cabeca")
        at.run()
        if a_prazo:
            self._por_chave(at.checkbox, "venda_a_prazo").set_value(True)
            at.run()
            self._por_chave(at.number_input, "venda_num_parcelas").set_value(parcelas)
            at.run()

        multi = [w for w in at.multiselect][0]
        multi.set_value([multi.options[animal_opcao]])
        at.run()

        self._por_label(at.number_input, "Valor por cabeça (R$)").set_value(5000.0)
        self._por_label(at.text_input, "Comprador").set_value(comprador)
        at.run()

        botao = [b for b in at.button if b.label == "✅ Confirmar Venda"][0]
        botao.click()
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção ao vender: {[e.value for e in at.exception]}")
        return at

    # ── testes ───────────────────────────────────────────────────────────────

    def test_checkbox_de_venda_a_prazo_existe(self):
        at = self._tela("financeiro")
        self.assertTrue(list(at.checkbox), "nenhum checkbox encontrado na tela")
        self._por_chave(at.checkbox, "venda_a_prazo")  # não levanta se existir

    def test_a_aba_de_contas_a_receber_existe(self):
        at = self._tela("financeiro")
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Contas a Receber" in r for r in rotulos), rotulos)

    def test_venda_a_vista_nao_gera_conta_a_receber(self):
        at = self._tela("financeiro")
        self._vender(at, a_prazo=False)

        db.clear_cache()
        self.assertEqual(db.listar_contas_receber(), [],
                         "venda à vista não pode gerar conta a receber")

    def test_venda_a_prazo_grava_as_parcelas(self):
        at = self._tela("financeiro")
        self._vender(at, a_prazo=True, parcelas=3, comprador="Frigorífico ABC")

        db.clear_cache()
        contas = db.listar_contas_receber()
        self.assertEqual(len(contas), 3)
        self.assertEqual(round(sum(c["valor"] for c in contas), 2), 5000.0)
        self.assertTrue(all(c["comprador"] == "Frigorífico ABC" for c in contas))
        self.assertTrue(all(c["status"] == "aberto" for c in contas))

    def test_tela_de_contas_a_receber_mostra_o_que_a_venda_gerou(self):
        at_v = self._tela("financeiro")
        self._vender(at_v, a_prazo=True, parcelas=1)

        at_r = self._tela("financeiro")
        metricas = {m.label: m.value for m in at_r.metric}
        self.assertIn("Em Aberto", metricas)
        self.assertEqual(metricas["Em Aberto"], "1")

    def test_marcar_como_recebida_fecha_a_conta(self):
        at_v = self._tela("financeiro")
        self._vender(at_v, a_prazo=True, parcelas=1)

        db.clear_cache()
        conta_id = db.listar_contas_receber("aberto")[0]["id"]

        at_r = self._tela("financeiro")
        self._por_chave(at_r.selectbox, "rec_conta_selecionada")
        at_r.run()
        self._por_chave(at_r.button, "rec_confirmar_btn").click()
        at_r.run()

        self.assertEqual(list(at_r.exception), [])
        db.clear_cache()
        conta = [c for c in db.listar_contas_receber() if c["id"] == conta_id][0]
        self.assertEqual(conta["status"], "recebido")
        self.assertIsNotNone(conta["data_recebimento"])


if __name__ == "__main__":
    unittest.main()
