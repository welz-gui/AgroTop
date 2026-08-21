"""O custo por lote de venda chegou à tela de verdade?

ROADMAP §5, Trilha 3 — o item que fechava a trilha: custo por kg e por
arroba já existiam por animal ("Custos por Animal") e por piquete
(Nutrição, `_nutricao_custo_por_piquete`). Faltava por LOTE DE VENDA — o
agrupamento que `register_sale` já grava em `sales.lot_ref` sempre que a
venda sai com mais de um animal, ou no modo de precificação "lote".

`services.rentabilidade.por_lote_de_venda` é pura e testada isoladamente em
`tests/test_rentabilidade.py`; estes testes travam o que a integração à aba
"💵 Registrar Venda" precisa garantir de verdade:

- **A seção existe e não quebra** com ou sem venda registrada.
- **Uma venda de vários animais vira UM lote** na tela (`lot_ref` comum),
  não uma linha por animal — é a soma que o ROADMAP pedia.
- **Venda avulsa de um único animal ainda aparece**, como lote de 1 cabeça.

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
class TestCustoPorLoteDeVendaNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_lote_venda.db"))
        db.init_db()
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

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_secao_existe_sem_nenhuma_venda(self):
        at = self._tela()
        texto = " ".join(m.value for m in at.markdown)
        self.assertIn("Custo por Lote de Venda", texto)

    def test_venda_de_varios_animais_vira_um_lote_so(self):
        entrada = (date.today() - timedelta(days=120)).isoformat()
        hoje = date.today().isoformat()
        db.add_animal("LOTEV1", "Nelore", "M", None, entrada,
                      300.0, 450.0, 1000.0, None, None)
        db.add_animal("LOTEV2", "Nelore", "M", None, entrada,
                      310.0, 460.0, 1000.0, None, None)
        db.add_animal_cost("LOTEV1", "operacional", "trato", 200.0, hoje)
        db.add_animal_cost("LOTEV2", "operacional", "trato", 200.0, hoje)
        db.clear_cache()
        db.register_sale(["LOTEV1", "LOTEV2"], hoje, "abate", "lote", 5000.0)
        db.clear_cache()

        from services.rentabilidade import por_lote_de_venda
        vendas = db.get_sales()
        lotes = por_lote_de_venda(vendas)
        lote = next((lv for lv in lotes if lv["animais"] >= 2), None)
        self.assertIsNotNone(lote, f"nenhum lote com 2+ animais em {lotes}")
        self.assertIsNotNone(lote["lot_ref"], "venda de 2 animais deveria gerar lot_ref")
        self.assertEqual(lote["peso_total_kg"], 300.0 + 310.0)  # entry_weight = current_weight na criação
        self.assertGreater(lote["custo_por_kg"], 0)
        self.assertGreater(lote["custo_por_arroba"], 0)

        at = self._tela()  # não pode levantar exceção com a venda já no banco
        texto = " ".join(m.value for m in at.markdown)
        self.assertIn("Custo por Lote de Venda", texto)

    def test_venda_avulsa_vira_lote_de_uma_cabeca(self):
        entrada = (date.today() - timedelta(days=90)).isoformat()
        hoje = date.today().isoformat()
        db.add_animal("LOTEV3", "Angus", "F", None, entrada,
                      280.0, 420.0, 900.0, None, None)
        db.clear_cache()
        db.register_sale(["LOTEV3"], hoje, "abate", "cabeca", 3000.0)
        db.clear_cache()

        from services.rentabilidade import por_lote_de_venda
        vendas = db.get_sales()
        venda_avulsa = next(v for v in vendas if v["animal_id"] == "LOTEV3")
        lotes = por_lote_de_venda(vendas)
        lote = next(lv for lv in lotes
                    if lv["animais"] == 1 and lv["lot_ref"] == venda_avulsa["lot_ref"])
        self.assertIsNone(lote["lot_ref"], "venda de um único animal não deveria ter lot_ref")


if __name__ == "__main__":
    unittest.main()
