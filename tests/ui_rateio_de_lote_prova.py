"""O rateio de custo de lote chegou à tela de verdade?

`services/rateio.py::ratear` existia pura e testada desde a spec 0019 — mas
sem consumidor, e a lacuna que a motivou continuava aberta: não existia
nenhum jeito de lançar um custo para "o lote inteiro" (trato coletivo,
medicamento aplicado a todos, frete). Só dava pra lançar custo por um
animal de cada vez (Ficha do Animal). A spec 0041 escreveu
`services/rateio_adaptador.py::com_dias_no_lote`, a ponte para o critério
`peso_dia`; ligar isso é a aba "➗ Rateio de Lote" de `page_financeiro`.

Estes testes travam o que a integração monta — nada disso é objeto das
specs 0019/0041 (que recebem os animais já prontos por parâmetro), é
trabalho do mantenedor (R31): resolver de onde vem `entrada_no_lote`
(nenhuma coluna guarda isso pronto) — a movimentação mais recente do
animal para o piquete, ou `entry_date` se ele nunca se moveu — e gravar o
resultado como `animal_costs` de verdade, um por animal.

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
class TestRateioDeLoteNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_rateio.db"))
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

    def test_a_aba_de_rateio_existe(self):
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Rateio de Lote" in r for r in rotulos),
                        f"nenhuma aba de rateio encontrada: {rotulos}")

    def test_rateio_por_peso_fecha_o_centavo_e_grava(self):
        """R$ 100 entre 3 animais de pesos diferentes: a soma dos custos
        gravados precisa fechar exatamente com o valor total — o "teste do
        centavo" da spec 0019, agora com a escrita de verdade em
        animal_costs, não só a função pura."""
        lote = db.get_all_lotes()[0]
        entrada = (date.today() - timedelta(days=90)).isoformat()
        db.add_animal("RAT1", "Nelore", "M", None, entrada, 300.0, 500.0, 0.0,
                      lote["id"], None)
        db.add_animal("RAT2", "Nelore", "M", None, entrada, 300.0, 500.0, 0.0,
                      lote["id"], None)
        db.add_animal("RAT3", "Nelore", "M", None, entrada, 300.0, 500.0, 0.0,
                      lote["id"], None)
        db.clear_cache()
        # pesos desiguais, de propósito — é o que faz "peso" divergir de "igual"
        db.add_weighing("RAT1", 200.0, date.today().isoformat())
        db.add_weighing("RAT2", 300.0, date.today().isoformat())
        db.add_weighing("RAT3", 400.0, date.today().isoformat())
        db.clear_cache()

        from services.rateio import ratear
        animais = [{"id": "RAT1", "peso": 200.0}, {"id": "RAT2", "peso": 300.0},
                  {"id": "RAT3", "peso": 400.0}]
        preview = ratear(100.0, animais, "peso")
        soma = sum(p["valor"] for p in preview)
        self.assertEqual(soma, 100.0, "rateio não fechou o centavo")

        antes = {p["animal_id"]: db.get_total_cost(p["animal_id"]) for p in preview}
        for p in preview:
            db.add_animal_cost(p["animal_id"], "veterinário", "prova rateio",
                               p["valor"], date.today().isoformat())
        db.clear_cache()
        depois_soma = sum(db.get_total_cost(p["animal_id"]) for p in preview)
        antes_soma = sum(antes.values())
        self.assertAlmostEqual(depois_soma - antes_soma, 100.0, places=2)

    def test_entrada_no_lote_usa_movimentacao_quando_existe(self):
        """Peça nova (R31): entrada_no_lote não vem pronta de lugar nenhum —
        precisa vir da movimentação mais recente, não sempre de entry_date."""
        lotes = db.get_all_lotes()
        origem, destino = lotes[0], lotes[1] if len(lotes) > 1 else lotes[0]
        if origem["id"] == destino["id"]:
            db.add_lote("RATDEST", "Piquete destino de prova", 5.0, 10.0)
            db.clear_cache()
            destino = db.get_all_lotes()[-1]

        entrada_rebanho = (date.today() - timedelta(days=200)).isoformat()
        db.add_animal("RATMOV", "Nelore", "M", None, entrada_rebanho,
                      300.0, 500.0, 0.0, origem["id"], None)
        db.clear_cache()
        data_movimento = (date.today() - timedelta(days=15)).isoformat()
        db.move_animal("RATMOV", destino["id"], data_movimento)
        db.clear_cache()

        movs = db.get_movements("RATMOV", limit=1)
        self.assertTrue(movs, "movimentação não foi registrada")
        entrada_no_lote = movs[0]["movement_date"]
        # tem que ser a data da movimentação, não a de entrada no rebanho
        self.assertEqual(entrada_no_lote, data_movimento)
        self.assertNotEqual(entrada_no_lote, entrada_rebanho)

        from services.rateio_adaptador import com_dias_no_lote
        resultado = com_dias_no_lote(
            [{"id": "RATMOV", "peso": 400.0, "entrada_no_lote": entrada_no_lote}],
            date.today().isoformat())
        self.assertEqual(resultado[0]["dias_no_lote"], 15)

    def test_piquete_sem_animais_nao_quebra(self):
        db.add_lote("RATVAZIO", "Piquete vazio de prova rateio", 5.0, 10.0)
        db.clear_cache()
        at = self._tela()  # não pode estourar
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Rateio de Lote" in r for r in rotulos))


if __name__ == "__main__":
    unittest.main()
