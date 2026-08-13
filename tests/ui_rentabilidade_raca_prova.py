"""A rentabilidade por raça chegou à tela de verdade?

`services/rentabilidade.py::ranking_por_raca` existia pura, testada, e nunca
foi chamada. A spec 0042 escreveu `services/rentabilidade_adaptador.py
::montar_ciclos`, a ponte entre `sales`/`animals`/custo acumulado e o que
`ranking_por_raca` espera; ligar isso é a aba "🐄 Por Raça" de
`page_financeiro`.

Estes testes travam o que a integração teve que resolver — nada disso é
objeto da spec 0042 (que recebe as três fontes já prontas por parâmetro), é
trabalho do mantenedor (R31):

- **Venda muda o status do animal para `vendido`** (`register_sale`) — a
  aba não pode depender do rebanho **ativo** (`get_all_animals()` sem
  argumento filtra por `status="ativo"`), senão o único animal do banco
  sumiria da análise no instante em que fosse vendido. É por isso que a
  aba fica fora do guard "sem animais ativos" que as outras abas de
  Financeiro usam.
- **Margem negativa continua negativa** — o defeito histórico do clamping
  (ROADMAP, spec 0017) não pode voltar por um caminho novo.

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
class TestRentabilidadePorRacaNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_rentabilidade.db"))
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

    def test_a_aba_por_raca_existe(self):
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Por Raça" in r for r in rotulos),
                        f"nenhuma aba de rentabilidade por raça encontrada: {rotulos}")

    def test_venda_de_todo_o_rebanho_ainda_mostra_a_aba(self):
        """O cenário que motivou tirar esta aba do guard "sem animais ativos":
        vender todo o rebanho ativo não pode fazer a aba sumir nem quebrar.

        Ordem alfabética garante que este é o último teste da classe — vender
        tudo aqui não afeta pré-condição de nenhum outro método."""
        hoje = date.today().isoformat()
        ativos = db.get_all_animals(status="ativo")
        if ativos:
            db.register_sale([a["id"] for a in ativos], hoje, "abate",
                             "cabeca", 1000.0)
            db.clear_cache()

        self.assertEqual(db.get_all_animals(status="ativo"), [],
                         "pré-condição do teste: nenhum animal ativo deveria sobrar")

        at = self._tela()  # não pode levantar exceção nem sumir a aba
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Por Raça" in r for r in rotulos))

    def test_ciclo_de_venda_aparece_no_ranking_por_raca(self):
        """Independente das outras — cria seu próprio animal e venda, para não
        depender da ordem alfabética de execução dos métodos da classe."""
        entrada = (date.today() - timedelta(days=120)).isoformat()
        hoje = date.today().isoformat()
        db.add_animal("RACA3", "Brangus", "M", None, entrada,
                      320.0, 480.0, 1000.0, None, None)
        db.clear_cache()
        db.register_sale(["RACA3"], hoje, "abate", "cabeca", 3500.0)
        db.clear_cache()

        from services.rentabilidade_adaptador import montar_ciclos
        from services.rentabilidade import ranking_por_raca

        vendas = db.get_sales()
        animais_por_uuid = {a["uuid"]: a for a in db.get_all_animals(status=None)
                            if a.get("uuid")}
        custos_por_id = db._costs_by_animal()
        custo_total_por_uuid = {uuid: custos_por_id.get(a["id"], 0.0)
                                for uuid, a in animais_por_uuid.items()}

        ciclos = montar_ciclos(vendas, animais_por_uuid, custo_total_por_uuid)
        ranking = ranking_por_raca(ciclos)

        brangus = next((r for r in ranking if r["raca"] == "Brangus"), None)
        self.assertIsNotNone(ranking, "nenhum ranking produzido")
        self.assertIsNotNone(brangus, f"Brangus não apareceu no ranking: {ranking}")
        self.assertEqual(brangus["animais"], 1)

    def test_margem_negativa_nao_e_zerada(self):
        """O defeito histórico (spec 0017): custo maior que receita precisa
        virar margem NEGATIVA, não 0.0 por clamping."""
        entrada = (date.today() - timedelta(days=90)).isoformat()
        hoje = date.today().isoformat()
        db.add_animal("RACA2", "Angus", "F", None, entrada,
                      300.0, 450.0, 1000.0, None, None)
        db.add_animal_cost("RACA2", "operacional", "trato caro", 5000.0, hoje)
        db.clear_cache()
        db.register_sale(["RACA2"], hoje, "abate", "cabeca", 100.0)
        db.clear_cache()

        from services.rentabilidade_adaptador import montar_ciclos
        from services.rentabilidade import ranking_por_raca

        vendas = db.get_sales()
        animais_por_uuid = {a["uuid"]: a for a in db.get_all_animals(status=None)
                            if a.get("uuid")}
        custos_por_id = db._costs_by_animal()
        custo_total_por_uuid = {uuid: custos_por_id.get(a["id"], 0.0)
                                for uuid, a in animais_por_uuid.items()}
        ciclos = montar_ciclos(vendas, animais_por_uuid, custo_total_por_uuid)
        ranking = ranking_por_raca(ciclos)

        angus = next(r for r in ranking if r["raca"] == "Angus")
        self.assertLess(angus["margem"], 0, "margem negativa foi zerada")


if __name__ == "__main__":
    unittest.main()
