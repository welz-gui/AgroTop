"""O fluxo de caixa realizado e projetado chegou à tela de verdade?

Trilha 3 (ROADMAP §5, Estoque → Financeiro → Nutrição), quarta fatia:
`services/caixa.py::fluxo_de_caixa` e `em_aberto` (spec 0021) existiam desde
a etapa anterior e nunca tiveram consumidor — não tinham como: as duas
funções precisam de `vencimento`/`pagamento` reais para separar "em aberto"
de "já liquidado", e `services.lancamentos.normalizar` sempre preencheu os
três campos (`competencia`/`vencimento`/`pagamento`) com a mesma data, porque
nenhuma fonte carregava um vencimento de verdade até `contas_pagar`/
`contas_receber` existirem (as duas fatias anteriores desta trilha).

A peça central desta integração — e o que estes testes travam — é **não
contar o mesmo evento duas vezes**: uma compra com nota fiscal e parcelas
aparece em `insumo_transactions` (competência) E em `contas_pagar`
(cronograma de caixa); uma venda a prazo aparece em `sales` (competência) E
em `contas_receber` (cronograma). `app.py::_fin_lancamentos_caixa` precisa
excluir da fonte de competência o que já tem parcela, usando as colunas
novas `insumo_transactions.compra_id` e `sales.a_prazo` (migration 0020).

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
class TestFluxoDeCaixaNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_fluxo.db"))
        db.init_db()
        db.clear_cache()
        cls.insumo = db.get_all_insumos()[0]

    def setUp(self):
        with db._conn() as con:
            con.execute("DELETE FROM contas_pagar")
            con.execute("DELETE FROM contas_receber")
            con.execute("DELETE FROM insumo_transactions WHERE compra_id IS NOT NULL")
            con.execute("DELETE FROM compra_itens")
            con.execute("DELETE FROM compras")
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

    def _metricas(self, at):
        return {m.label: m.value for m in at.metric}

    def _reais(self, texto: str) -> float:
        """'R$ 1,234.56' -> 1234.56; 'R$ -50.00' -> -50.0."""
        return float(texto.replace("R$", "").replace(",", "").strip())

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_aba_de_fluxo_de_caixa_existe(self):
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Fluxo de Caixa" in r for r in rotulos), rotulos)

    def test_compra_com_nota_e_venda_a_prazo_nao_contam_duas_vezes(self):
        """O cenário central: compra a prazo (2 parcelas) + venda à vista +
        venda a prazo (2 parcelas). O DELTA de realizado/projetado precisa
        bater com a SOMA DAS PARCELAS, nunca com parcela + lançamento de
        origem somados juntos (isso seria o dobro) — por isso mede-se a
        diferença antes/depois, não o valor absoluto (a base já tem seed)."""
        antes = self._metricas(self._tela())
        realizado_antes = self._reais(antes["Realizado no período"])
        projetado_antes = self._reais(antes["Projetado no período"])

        hoje = date.today()
        r_compra = db.compras.registrar(
            data_emissao=hoje.isoformat(), data_recebimento=hoje.isoformat(),
            itens=[{"insumo_id": self.insumo["id"], "quantidade": 10.0,
                    "custo_unitario": 5.0}],
            primeiro_vencimento=(hoje + timedelta(days=15)).isoformat(),
            num_parcelas=2)
        self.assertTrue(r_compra["ok"])

        animais = db.get_all_animals(status="ativo")
        db.register_sale([animais[0]["id"]], hoje.isoformat(), "abate", "cabeca", 3000.0)
        r_venda_prazo = db.register_sale(
            [animais[1]["id"]], hoje.isoformat(), "abate", "cabeca", 4000.0,
            a_prazo=True, num_parcelas=2,
            primeiro_vencimento=(hoje + timedelta(days=20)).isoformat())
        self.assertEqual(r_venda_prazo["parcelas_a_receber"], 2)

        db.clear_cache()

        depois = self._metricas(self._tela())
        realizado_depois = self._reais(depois["Realizado no período"])
        projetado_depois = self._reais(depois["Projetado no período"])

        # Janela padrão (início do mês até hoje+60d) cobre as duas parcelas
        # de cada lado. Nada foi pago/recebido ainda: projetado sobe 4000
        # (venda a prazo) − 50 (compra a prazo) = 3950. Se a compra/venda de
        # origem tivesse vazado para a competência, a diferença seria maior.
        self.assertEqual(round(projetado_depois - projetado_antes, 2), 3950.0)
        # Realizado sobe só a venda à vista (3000) — nada pago de compra ainda.
        self.assertEqual(round(realizado_depois - realizado_antes, 2), 3000.0)

    def test_marcar_parcela_como_paga_move_de_projetado_para_realizado(self):
        antes = self._metricas(self._tela())
        realizado_antes = self._reais(antes["Realizado no período"])
        projetado_antes = self._reais(antes["Projetado no período"])

        hoje = date.today()
        r = db.compras.registrar(
            data_emissao=hoje.isoformat(), data_recebimento=hoje.isoformat(),
            itens=[{"insumo_id": self.insumo["id"], "quantidade": 10.0,
                    "custo_unitario": 5.0}],
            primeiro_vencimento=(hoje + timedelta(days=15)).isoformat(),
            num_parcelas=1)
        self.assertTrue(r["ok"])

        db.clear_cache()
        conta = db.compras.listar_contas_pagar("aberto")[0]
        self.assertEqual(conta["valor"], 50.0)

        m1 = self._metricas(self._tela())
        self.assertEqual(round(self._reais(m1["Projetado no período"]) - projetado_antes, 2), -50.0)
        self.assertEqual(round(self._reais(m1["Realizado no período"]) - realizado_antes, 2), 0.0)

        db.compras.marcar_pago(conta["id"], hoje.isoformat(), "pix")
        db.clear_cache()

        m2 = self._metricas(self._tela())
        self.assertEqual(round(self._reais(m2["Realizado no período"]) - realizado_antes, 2), -50.0)
        self.assertEqual(round(self._reais(m2["Projetado no período"]) - projetado_antes, 2), 0.0)

    def test_conta_vencida_aparece_destacada_em_aberto(self):
        hoje = date.today()
        ontem = (hoje - timedelta(days=1)).isoformat()
        r = db.compras.registrar(
            data_emissao=ontem, data_recebimento=ontem,
            itens=[{"insumo_id": self.insumo["id"], "quantidade": 1.0,
                    "custo_unitario": 10.0}],
            primeiro_vencimento=ontem, num_parcelas=1)
        self.assertTrue(r["ok"])
        db.clear_cache()

        at = self._tela()
        self.assertTrue(list(at.warning), "conta vencida não gerou aviso")


if __name__ == "__main__":
    unittest.main()
