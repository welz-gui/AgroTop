"""A DRE gerencial chegou à tela de verdade?

Trilha 3 (ROADMAP §5, Estoque → Financeiro → Nutrição), terceira fatia:
`services/dre.py::montar_dre` — nunca chamado até aqui — reorganiza o mesmo
resumo do período que a aba "📒 Resultado" já usa
(`repositories.financeiro.get_financial_summary`), mas trocando custo de
**compra no período** (caixa) por custo do animal **casado com a venda**
(`cost_at_sale`, competência). Nenhuma consulta nova, nenhuma tabela nova —
é só a forma certa de somar números que já existiam.

Estes testes travam a diferença que separa a DRE do "Resultado (Caixa)":
comprar um lote de animais no período e não vendê-lo não pode aparecer como
despesa da DRE — o valor virou rebanho (patrimônio), não custo do período.

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
class TestDREGerencialNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_dre.db"))
        db.init_db()
        db.clear_cache()

    def setUp(self):
        with db._conn() as con:
            con.execute("DELETE FROM sales")
            con.execute("UPDATE animals SET status='ativo'")
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

    def test_a_aba_de_dre_existe(self):
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("DRE Gerencial" in r for r in rotulos), rotulos)

    def test_dre_sem_vendas_nao_quebra_a_tela(self):
        self._tela()  # já falha em _tela() se houver exceção

    def test_cpv_usa_o_custo_casado_com_a_venda_nao_a_compra_do_periodo(self):
        """A peça central desta integração: comprar animais no período (caixa)
        não pode contaminar o CPV da DRE (competência)."""
        animais_ativos = db.get_all_animals(status="ativo")
        vendido = animais_ativos[0]
        custo_do_vendido = db.get_total_cost(vendido["id"])
        self.assertGreater(custo_do_vendido, 0, "seed sem custo lançado no animal")

        hoje = date.today().isoformat()
        r = db.register_sale([vendido["id"]], hoje, "abate", "cabeca", 5000.0)
        db.clear_cache()

        fin = db.get_financial_summary(f"{date.today().year}-01-01", hoje)
        # Outros animais ativos garantem que compra_animais > 0 no período,
        # sem que isso vaze para o CPV da DRE.
        self.assertGreater(fin["compra_animais"], 0,
                           "seed sem custo de compra nos outros animais")

        from services.dre import montar_dre
        dre = montar_dre(fin)
        self.assertEqual(dre["cpv"], round(custo_do_vendido, 2))
        self.assertEqual(dre["lucro_bruto"], r["lucro"])
        self.assertNotEqual(dre["cpv"], fin["compra_animais"])

    def test_tela_mostra_a_receita_bruta_apos_uma_venda(self):
        vendido = db.get_all_animals(status="ativo")[0]
        db.register_sale([vendido["id"]], date.today().isoformat(), "abate",
                         "cabeca", 5000.0)
        db.clear_cache()

        at = self._tela()
        textos = " ".join(str(m.value) for m in at.markdown)
        self.assertIn("Receita Bruta", textos)
        self.assertIn("Resultado Líquido", textos)
        self.assertTrue(
            any(m.label == "Margem Líquida" for m in at.metric),
            "métrica de margem líquida não renderizada")


if __name__ == "__main__":
    unittest.main()
