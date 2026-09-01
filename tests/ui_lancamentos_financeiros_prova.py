"""A normalização de lançamentos financeiros chegou à tela de verdade?

`services/caixa.py` (`resultado_por_competencia`, `fluxo_de_caixa`, `em_aberto`)
existia pura, testada, e nunca foi chamada — o dinheiro do AgroTop estava
espalhado em quatro tabelas com formatos diferentes, e nada falava a língua
que `caixa.py` entende. A spec 0034 escreveu `services/lancamentos.py::normalizar`,
a ponte; ligar isso à aba "📅 Competência" de `page_financeiro` é o que fecha
o ciclo.

Estes testes travam o que a integração descobriu e teve que resolver — nada
disso é objeto da spec 0034 (que recebe as quatro listas já prontas por
parâmetro), é trabalho do mantenedor (R31):

- **Compra de insumo não é `type='compra'` no schema real** — é
  `type='entrada'` + `reason='compra'` (`type='compra'` nunca existiu de
  fato; é o que `add_insumo_entry` sempre gravou). `db.get_insumo_compras`
  faz essa tradução; se ela quebrar, toda compra de insumo desaparece do
  resultado em silêncio — o pior tipo de bug financeiro.
- **O "teste do centavo" da spec 0031 continua valendo ponta a ponta**:
  `receitas - despesas == resultado`, com dados que vieram do banco de
  verdade, não só de fixture no teste da função pura.

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
class TestLancamentosFinanceirosNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_lancamentos.db"))
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

    def test_a_aba_de_competencia_existe(self):
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Competência" in r for r in rotulos),
                        f"nenhuma aba de competência encontrada: {rotulos}")

    def test_venda_do_mes_entra_como_receita(self):
        hoje = date.today().isoformat()
        aid = db.get_all_animals(status="ativo")[0]["id"]
        db.register_sale([aid], hoje, "criacao", "cabeca", 3000.0)
        db.clear_cache()

        # O helper que monta a lista única (`_fin_lancamentos`) vive em
        # app.py; aqui exercitamos a mesma cadeia — banco real → normalizar()
        # → resultado_por_competencia() — sem importar app.py inteiro.
        from services.lancamentos import normalizar
        from services.caixa import resultado_por_competencia

        vendas = db.get_sales(hoje, hoje)
        self.assertTrue(any(v["total_value"] == 3000.0 for v in vendas))

        lanc = normalizar(vendas=vendas)
        hj = date.today()
        r = resultado_por_competencia(lanc, hj.year, hj.month)
        self.assertGreaterEqual(r["receitas"], 3000.0)

    def test_compra_de_insumo_type_entrada_reason_compra_nao_some(self):
        """O defeito que a integração evitou: se `get_insumo_compras` filtrasse
        por `type='compra'` (como a spec 0034 supunha), NENHUMA compra real
        apareceria — é sempre `type='entrada'` + `reason='compra'`."""
        db.add_new_insumo(db.InsumoCreate("Sal Prova Financeiro", "trato", "kg", 0.0, 10.0, 4.0))
        db.clear_cache()
        insumo = next(i for i in db.get_all_insumos()
                      if i["name"] == "Sal Prova Financeiro")
        db.add_insumo_entry(insumo["id"], 50.0, 4.0, "op-prova")
        db.clear_cache()

        hoje = date.today().isoformat()
        compras = db.get_insumo_compras(hoje, hoje)
        self.assertTrue(any(c["insumo_nome"] == "Sal Prova Financeiro"
                            for c in compras),
                        "compra de insumo não apareceu — a tradução "
                        "type='entrada'+reason='compra' quebrou")

    def test_do_centavo_com_dados_reais_do_banco(self):
        """receitas - despesas == resultado, com lançamentos que vieram do
        banco de verdade — o mesmo caminho que a aba usa."""
        hoje = date.today().isoformat()
        aid = db.get_all_animals(status="ativo")[0]["id"]
        db.register_sale([aid], hoje, "criacao", "cabeca", 1500.0)
        db.add_fixed_cost("Aluguel de pastagem", "prova", 400.0, hoje)
        db.clear_cache()

        from services.lancamentos import normalizar
        from services.caixa import resultado_por_competencia

        lanc = normalizar(
            vendas=db.get_sales(hoje, hoje),
            custos_fixos=db.get_fixed_costs(hoje, hoje),
            custos_animal=db.get_all_animal_costs(hoje, hoje),
        )
        hj = date.today()
        r = resultado_por_competencia(lanc, hj.year, hj.month)
        self.assertAlmostEqual(r["receitas"] - r["despesas"], r["resultado"], places=2)


if __name__ == "__main__":
    unittest.main()
