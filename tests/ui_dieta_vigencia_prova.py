"""A dieta com vigência (histórico versionado) chegou à tela de verdade?

Trilha 3 (ROADMAP §5, Estoque → Financeiro → Nutrição), sexta fatia:
`feeding_plans` só tinha um interruptor `active` — mudar a quantidade de um
item de trato reescrevia o valor no lugar (ou, na prática, exigia apagar e
recriar), perdendo o que valeu antes. `db.nova_versao_feeding_plan` e
`db.encerrar_feeding_plan` seguem o mesmo princípio já usado em
`regras.nova_versao()`: editar no lugar reescreveria o custo já calculado
com a versão anterior (a aba "💰 Custo por Piquete" e o DRE dependem do
plano de trato para custo por cabeça/dia).

Estes testes travam:

- **"Nova versão" encerra a antiga, não apaga** — o histórico continua
  reconstruível.
- **"Encerrar" fecha a vigência, não exclui a linha.**
- **Pausar/reativar não é "mudança de dieta"** — continua sendo a mesma
  versão (não passa por este fluxo, é o interruptor de sempre).

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
class TestDietaComVigenciaNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_dieta_vig.db"))
        db.init_db()
        db.clear_cache()
        cls.lote = db.get_all_lotes()[0]

    def setUp(self):
        with db._conn() as con:
            con.execute("DELETE FROM feeding_plans")
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "nutricao"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def _por_chave(self, widgets, chave):
        achados = [w for w in widgets if (w.key or "") == chave]
        self.assertEqual(len(achados), 1,
                         f"esperava 1 widget com chave '{chave}', achei {len(achados)}")
        return achados[0]

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_aba_de_historico_da_dieta_existe(self):
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Histórico da Dieta" in r for r in rotulos), rotulos)

    def test_nova_versao_pela_tela_encerra_a_antiga(self):
        db.add_feeding_plan(self.lote["id"], "Silagem", 10.0, "kg", "diario")
        db.clear_cache()
        antiga = db.get_feeding_plans(lote_id=self.lote["id"], active_only=True)[0]

        at = self._tela()
        self._por_chave(at.number_input, f"nv_qtd_{antiga['id']}").set_value(25.0)
        at.run()
        botao = [b for b in at.button if b.label == "💾 Salvar nova versão"][0]
        botao.click()
        at.run()
        self.assertEqual(list(at.exception), [])

        db.clear_cache()
        historico = db.get_feeding_plan_historico(self.lote["id"])
        self.assertEqual(len(historico), 2)
        vigente = [h for h in historico if h["vigente_ate"] is None][0]
        encerrada = [h for h in historico if h["vigente_ate"] is not None][0]
        self.assertEqual(vigente["quantity"], 25.0)
        self.assertEqual(encerrada["id"], antiga["id"])
        self.assertEqual(encerrada["quantity"], 10.0)

    def test_encerrar_pela_tela_some_dos_planos_ativos_mas_fica_no_historico(self):
        db.add_feeding_plan(self.lote["id"], "Sal Mineral", 5.0, "kg", "diario")
        db.clear_cache()
        p = db.get_feeding_plans(lote_id=self.lote["id"], active_only=True)[0]

        at = self._tela()
        self._por_chave(at.button, f"enc_{p['id']}").click()
        at.run()
        self.assertEqual(list(at.exception), [])

        db.clear_cache()
        ativos = db.get_feeding_plans(lote_id=self.lote["id"], active_only=True)
        self.assertFalse(any(a["id"] == p["id"] for a in ativos))
        historico = db.get_feeding_plan_historico(self.lote["id"])
        self.assertTrue(any(h["id"] == p["id"] for h in historico),
                        "encerrar não pode apagar o registro do histórico")


if __name__ == "__main__":
    unittest.main()
