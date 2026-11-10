"""Corrigir ou cancelar uma venda, pela tela de vendas (Financeiro).

Critérios:
1. O motivo é obrigatório; sem ele nada é gravado.
2. Cancelar deixa a linha, com o motivo e o autor, e devolve o animal ao rebanho.
3. Corrigir grava a venda certa, ligada à original.
4. Venda a prazo só se cancela (as parcelas em aberto são canceladas junto).
5. Corrigir pode trocar os animais da venda: o que sai volta ao rebanho com o estorno na trilha,
   o que entra fica vendido; sem nenhum animal, recusa e nada muda.

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
from repositories import eventos  # noqa: E402
from repositories.animais import get_animal  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None

HOJE = date.today().isoformat()


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestRevisaoDeVenda(unittest.TestCase):
    def setUp(self):
        import streamlit as st
        st.cache_data.clear()
        self._dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self._dir, "ui_revisao_venda.db"))
        db.init_db()
        with db._conn() as con:      # cenário controlado: ninguém em carência
            con.execute("UPDATE medications SET withdrawal_days=0")
            con.execute("UPDATE animals SET status='ativo'")
        db.clear_cache()
        self.animal_id = db.get_all_animals(status="ativo")[0]["id"]

    def _vender(self, **extra):
        db.register_sale(db.SaleParams(
            animal_ids=[self.animal_id], sale_date=HOJE, sale_type="criacao", pricing_mode="kg",
            value=10.0, buyer="Comprador UI", operator="op", **extra))
        db.clear_cache()
        return [v for v in db.get_sales() if v["animal_id"] == self.animal_id][0]

    def _vender_varios(self, ids):
        db.register_sale(db.SaleParams(
            animal_ids=ids, sale_date=HOJE, sale_type="criacao", pricing_mode="kg",
            value=10.0, buyer="Comprador UI", operator="op"))
        db.clear_cache()
        return [v for v in db.get_sales() if v["animal_id"] == ids[0]][0]

    def _seletor_de_animais(self, at):
        """O seletor da venda do lote e a chave `k` dos demais widgets: `k` é o id da PRIMEIRA linha
        do grupo, que não é necessariamente a do primeiro animal."""
        achados = [w for w in at.multiselect if (w.key or "").startswith("rv_a_")]
        self.assertEqual(len(achados), 1)
        return achados[0], achados[0].key[len("rv_a_"):]

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin", "name": "Admin", "role": "admin"}
        at.session_state["page"] = "financeiro"
        at.run()
        self.assertEqual(list(at.exception), [], [e.value for e in at.exception])
        return at

    def _por_chave(self, widgets, chave):
        achados = [w for w in widgets if (w.key or "") == chave]
        self.assertEqual(len(achados), 1, f"esperava 1 widget '{chave}', achei {len(achados)}")
        return achados[0]

    def _clicar(self, at, rotulo, formulario):
        botao = [b for b in at.button
                 if rotulo in (b.label or "") and b.proto.form_id.endswith(formulario)]
        self.assertEqual(len(botao), 1, f"botão '{rotulo}' em '{formulario}': {len(botao)}")
        botao[0].click()
        at.run()
        self.assertEqual(list(at.exception), [], [e.value for e in at.exception])

    def _linha(self, sid):
        with db._conn() as con:
            return dict(con.execute("SELECT * FROM sales WHERE id=?", (sid,)).fetchone())

    def test_sem_motivo_nao_cancela(self):
        v = self._vender()
        at = self._tela()
        self._clicar(at, "Cancelar venda", f"f_rev_venda_{v['id']}")
        self.assertTrue(any("motivo" in e.value.lower() for e in at.error), [e.value for e in at.error])
        self.assertIsNone(self._linha(v["id"])["cancelada_em"])
        self.assertEqual(get_animal(self.animal_id)["status"], "vendido")

    def test_cancelar_grava_o_motivo_e_devolve_o_animal(self):
        v = self._vender()
        at = self._tela()
        self._por_chave(at.text_input, f"rv_m_{v['id']}").set_value("animal errado")
        self._clicar(at, "Cancelar venda", f"f_rev_venda_{v['id']}")

        linha = self._linha(v["id"])
        self.assertEqual((linha["motivo_cancelamento"], linha["cancelada_por"]), ("animal errado", "admin"))
        db.clear_cache()
        self.assertEqual(get_animal(self.animal_id)["status"], "ativo")

        depois = self._tela()      # a venda cancelada sai da lista de correção e aparece em "canceladas"
        self.assertEqual([w for w in depois.text_input if (w.key or "") == f"rv_m_{v['id']}"], [])
        self.assertTrue(any("Vendas canceladas" in (e.label or "") for e in depois.expander))

    def test_corrigir_grava_a_venda_certa_ligada_a_original(self):
        v = self._vender()
        at = self._tela()
        self._por_chave(at.text_input, f"rv_m_{v['id']}").set_value("preço errado")
        self._por_chave(at.number_input, f"rv_v_{v['id']}").set_value(12.0)
        self._clicar(at, "Salvar correção", f"f_rev_venda_{v['id']}")

        self.assertTrue(self._linha(v["id"])["cancelada_em"])
        db.clear_cache()
        (nova,) = [s for s in db.get_sales() if s["animal_id"] == self.animal_id]
        self.assertEqual(nova["corrige_id"], v["id"])
        self.assertEqual(nova["price_per_kg"], 12.0)
        self.assertEqual(nova["total_value"], round(nova["weight_kg"] * 12.0, 2))
        self.assertEqual(get_animal(self.animal_id)["status"], "vendido")

    def test_venda_a_prazo_so_cancela_e_cancela_as_parcelas(self):
        v = self._vender(a_prazo=True, num_parcelas=2,
                         primeiro_vencimento=(date.today() + timedelta(days=30)).isoformat())
        at = self._tela()
        corrigir = [b for b in at.button if "Salvar correção" in (b.label or "")
                    and b.proto.form_id.endswith(f"f_rev_venda_{v['id']}")]
        self.assertEqual([b.proto.disabled for b in corrigir], [True], "a prazo não oferece corrigir")

        self.assertTrue(self._por_chave(at.multiselect, f"rv_a_{v['id']}").proto.disabled,
                        "a prazo também não oferece trocar os animais")

        self._por_chave(at.text_input, f"rv_m_{v['id']}").set_value("venda desfeita")
        self._clicar(at, "Cancelar venda", f"f_rev_venda_{v['id']}")

        self.assertTrue(self._linha(v["id"])["cancelada_em"])
        parcelas = [c for c in db.listar_contas_receber() if c["lot_ref"] == v["lot_ref"]]
        self.assertEqual([c["status"] for c in parcelas], ["cancelado", "cancelado"])

    def test_corrigir_troca_um_animal_por_outro(self):
        a1, a2, a3 = [a["id"] for a in db.get_all_animals(status="ativo")[:3]]
        v = self._vender_varios([a1, a2])
        at = self._tela()
        seletor, k = self._seletor_de_animais(at)
        self.assertEqual(sorted(seletor.value), sorted([a1, a2]), "abre com os animais da venda")
        self.assertIn(a3, seletor.options and [o.split(" · ")[0] for o in seletor.options],
                      "oferece os ativos como candidatos")
        seletor.unselect(a2)
        seletor.select(a3)
        self._por_chave(at.text_input, f"rv_m_{k}").set_value("foi o terceiro, não o segundo")
        self._clicar(at, "Salvar correção", f"f_rev_venda_{k}")

        db.clear_cache()
        vigentes = [s for s in db.get_sales() if s["lot_ref"] == v["lot_ref"]]
        self.assertEqual(sorted(s["animal_id"] for s in vigentes), sorted([a1, a3]))
        self.assertEqual((get_animal(a1)["status"], get_animal(a2)["status"], get_animal(a3)["status"]),
                         ("vendido", "ativo", "vendido"))
        estornos = [e for e in eventos.do_animal(get_animal(a2)["uuid"]) if e["tipo"] == "estorno"]
        self.assertEqual([e["justificativa"] for e in estornos], ["foi o terceiro, não o segundo"])

    def test_corrigir_sem_nenhum_animal_recusa_e_nada_muda(self):
        a1, a2 = [a["id"] for a in db.get_all_animals(status="ativo")[:2]]
        v = self._vender_varios([a1, a2])
        at = self._tela()
        seletor, k = self._seletor_de_animais(at)
        seletor.unselect(a1)
        seletor.unselect(a2)
        self._por_chave(at.text_input, f"rv_m_{k}").set_value("engano")
        self._clicar(at, "Salvar correção", f"f_rev_venda_{k}")

        self.assertTrue(any("ao menos um animal" in e.value for e in at.error), [e.value for e in at.error])
        self.assertIsNone(self._linha(v["id"])["cancelada_em"])
        db.clear_cache()
        self.assertEqual((get_animal(a1)["status"], get_animal(a2)["status"]), ("vendido", "vendido"))


if __name__ == "__main__":
    unittest.main()
