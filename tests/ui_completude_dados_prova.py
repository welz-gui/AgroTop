"""O indicador de completude de dados chegou à tela de verdade?

`services/completude.py::avaliar_mes` existia pura, testada, e nunca foi
chamada — o ROADMAP (Trilha 4) já pedia isso cedo: "mostra, mês a mês, se a
base está ficando treinável". A spec 0035 escreveu
`services/completude_adaptador.py` (`normalizar_pesagens`, `janela_do_mes`),
a ponte entre `weighings`/`feeding_checks`/`pluviometria` e o que
`avaliar_mes` espera; ligar isso é a seção "📋 Completude dos Dados" no
Dashboard.

Estes testes travam o que a integração monta — nada disso é objeto da spec
0035 (que recebe as listas já prontas por parâmetro), é trabalho do
mantenedor (R31): construir o intervalo de datas do mês (`inicio`/`fim`)
corretamente para `db.get_feeding_checks`/`db.get_rain`, sem cortar o
último dia do mês por um off-by-one.

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
class TestCompletudeDeDadosNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_completude.db"))
        db.init_db()
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "dashboard"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_secao_de_completude_existe(self):
        at = self._tela()
        rotulos = [ex.label for ex in at.expander]
        self.assertTrue(any("Completude" in r for r in rotulos),
                        f"nenhum expander de completude encontrado: {rotulos}")

    def test_tela_nao_quebra_e_mostra_alerta_ou_confirmacao(self):
        """Banco recém-criado não tem checagem de trato nem leitura de chuva
        no mês corrente — a seção precisa avisar disso, não estourar."""
        at = self._tela()
        self.assertTrue(list(at.warning) or list(at.success),
                        "nem alerta nem confirmação de completude apareceram")

    def test_intervalo_do_mes_cobre_o_ultimo_dia_sem_off_by_one(self):
        """A parte que é trabalho do mantenedor, não da spec 0035: construir
        inicio/fim do mês para db.get_rain(). Um off-by-one no fim cortaria
        leituras do último dia do mês silenciosamente."""
        from services.completude_adaptador import janela_do_mes

        hoje = date.today()
        ultimo_dia_do_mes = (
            date(hoje.year + (1 if hoje.month == 12 else 0),
                1 if hoje.month == 12 else hoje.month + 1, 1)
            - timedelta(days=1)
        )
        db.add_rain(ultimo_dia_do_mes.isoformat(), 5.0)
        db.clear_cache()

        inicio = date(hoje.year, hoje.month, 1)
        prox_mes = date(hoje.year + (1 if hoje.month == 12 else 0),
                        1 if hoje.month == 12 else hoje.month + 1, 1)
        fim = prox_mes - timedelta(days=1)
        self.assertEqual(fim, ultimo_dia_do_mes,
                         "cálculo de fim do mês não bate com o último dia real")

        chuvas = db.get_rain(start_date=inicio.isoformat(), end_date=fim.isoformat())
        self.assertTrue(
            any(ch["read_date"] == ultimo_dia_do_mes.isoformat() for ch in chuvas),
            "leitura do último dia do mês não veio na consulta — off-by-one no fim")

        janela = janela_do_mes(hoje.year, hoje.month, checagens_de_trato=[],
                               leituras_de_chuva=chuvas)
        self.assertGreaterEqual(janela["semanas_com_chuva"], 1)

    def test_cadeia_completa_com_dados_reais_do_banco(self):
        """A mesma cadeia que o Dashboard usa: banco real → adaptador →
        avaliar_mes(), sem estourar e com o formato que a tela espera."""
        from services.completude_adaptador import normalizar_pesagens, janela_do_mes
        from services.completude import avaliar_mes

        hoje = date.today()
        animais_ativos = len(db.get_all_animals(status="ativo"))
        pesagens = normalizar_pesagens(db.get_all_weighings())

        inicio = date(hoje.year, hoje.month, 1)
        prox_mes = date(hoje.year + (1 if hoje.month == 12 else 0),
                        1 if hoje.month == 12 else hoje.month + 1, 1)
        fim = prox_mes - timedelta(days=1)
        checagens = db.get_feeding_checks(
            start_date=inicio.isoformat(), end_date=fim.isoformat())
        chuvas = db.get_rain(
            start_date=inicio.isoformat(), end_date=fim.isoformat())

        janela = janela_do_mes(hoje.year, hoje.month, checagens_de_trato=checagens,
                               leituras_de_chuva=chuvas)
        r = avaliar_mes(hoje.year, hoje.month, animais_ativos, pesagens, **janela)

        self.assertIn("alertas", r)
        for chave in ("animais_com_pesagem_em_dia", "intervalos_uteis_gmd",
                      "contexto_da_pesagem", "execucao_nutricional",
                      "cobertura_ambiental"):
            self.assertIn(chave, r)
            self.assertGreaterEqual(r[chave], 0.0)
            self.assertLessEqual(r[chave], 1.0)


if __name__ == "__main__":
    unittest.main()
