"""Corrigir ou cancelar custo (de animal e fixo) e óbito, pelas telas.

Critérios:
1. O motivo é obrigatório; sem ele nada é gravado.
2. Cancelar deixa a linha, com o motivo e o autor, e a tira das somas.
3. Corrigir grava a certa, ligada à original.
4. Cancelar o óbito devolve o animal ao rebanho.

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
from repositories.animais import get_animal  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None

HOJE = date.today().isoformat()


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestRevisaoCustoObito(unittest.TestCase):
    def setUp(self):
        import streamlit as st
        st.cache_data.clear()
        self._dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self._dir, "ui_revisao_custo_obito.db"))
        db.init_db()
        db.clear_cache()
        self.animal_id = db.get_all_animals()[0]["id"]

    def _tela(self, pagina="animal"):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin", "name": "Admin", "role": "admin"}
        at.session_state["page"] = pagina
        at.session_state["animal_detail"] = self.animal_id
        at.session_state["campo_id"] = self.animal_id     # o óbito vive no Modo Campo
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

    def _linha(self, tabela, rid):
        with db._conn() as con:
            return dict(con.execute(f"SELECT * FROM {tabela} WHERE id=?", (rid,)).fetchone())

    # ── custo de animal ──────────────────────────────────────────────────────
    def _custo_animal(self):
        db.add_animal_cost(db.AnimalCostData(self.animal_id, "operacional", "Custo UI", 123.0, HOJE))
        db.clear_cache()
        return [c for c in db.get_animal_costs(self.animal_id) if c["description"] == "Custo UI"][0]["id"]

    def test_custo_de_animal_sem_motivo_nao_cancela(self):
        cid = self._custo_animal()
        at = self._tela()
        self._clicar(at, "Cancelar custo", f"f_rev_cost_{self.animal_id}_{cid}")
        self.assertTrue(any("motivo" in e.value.lower() for e in at.error), [e.value for e in at.error])
        self.assertIsNone(self._linha("animal_costs", cid)["cancelada_em"])

    def test_custo_de_animal_cancela_com_motivo_e_sai_da_soma(self):
        cid = self._custo_animal()
        antes = db.get_total_cost(self.animal_id)
        at = self._tela()
        self._por_chave(at.text_input, f"rc_m_{self.animal_id}_{cid}").set_value("valor lançado errado")
        self._clicar(at, "Cancelar custo", f"f_rev_cost_{self.animal_id}_{cid}")

        linha = self._linha("animal_costs", cid)
        self.assertEqual((linha["motivo_cancelamento"], linha["cancelada_por"]), ("valor lançado errado", "admin"))
        db.clear_cache()
        self.assertEqual(round(antes - db.get_total_cost(self.animal_id), 2), 123.0)

    def test_custo_de_animal_corrige_ligando_a_nova_a_original(self):
        cid = self._custo_animal()
        at = self._tela()
        self._por_chave(at.text_input, f"rc_m_{self.animal_id}_{cid}").set_value("vírgula no lugar errado")
        self._por_chave(at.number_input, f"rc_v_{self.animal_id}_{cid}").set_value(12.3)
        self._clicar(at, "Salvar correção", f"f_rev_cost_{self.animal_id}_{cid}")

        self.assertTrue(self._linha("animal_costs", cid)["cancelada_em"])
        nova = [c for c in db.get_animal_costs(self.animal_id) if c["corrige_id"] == cid]
        self.assertEqual([(c["amount"], c["description"]) for c in nova], [(12.3, "Custo UI")])

    # ── custo fixo ───────────────────────────────────────────────────────────
    def _custo_fixo(self):
        db.add_fixed_cost(db.FixedCostData(db.FIXED_COST_CATEGORIES[0], "Fixo UI", 777.0, HOJE, 0))
        return [c for c in db.get_fixed_costs() if c["description"] == "Fixo UI"][0]["id"]

    def test_custo_fixo_sem_motivo_nao_cancela(self):
        cid = self._custo_fixo()
        at = self._tela("financeiro")
        self._clicar(at, "Cancelar lançamento", f"f_rev_fix_{cid}")
        self.assertTrue(any("motivo" in e.value.lower() for e in at.error), [e.value for e in at.error])
        self.assertIsNone(self._linha("fixed_costs", cid)["cancelada_em"])

    def test_custo_fixo_cancela_com_motivo_e_sai_da_soma(self):
        cid = self._custo_fixo()
        antes = db.get_total_fixed_costs()
        at = self._tela("financeiro")
        self._por_chave(at.text_input, f"rf_m_{cid}").set_value("lançado duas vezes")
        self._clicar(at, "Cancelar lançamento", f"f_rev_fix_{cid}")

        linha = self._linha("fixed_costs", cid)
        self.assertEqual((linha["motivo_cancelamento"], linha["cancelada_por"]), ("lançado duas vezes", "admin"))
        self.assertEqual(round(antes - db.get_total_fixed_costs(), 2), 777.0)

    def test_custo_fixo_corrige_ligando_o_novo_ao_original(self):
        cid = self._custo_fixo()
        at = self._tela("financeiro")
        self._por_chave(at.text_input, f"rf_m_{cid}").set_value("reajuste")
        self._por_chave(at.number_input, f"rf_v_{cid}").set_value(800.0)
        self._clicar(at, "Salvar correção", f"f_rev_fix_{cid}")

        novo = [c for c in db.get_fixed_costs() if c["corrige_id"] == cid]
        self.assertEqual([(c["amount"], c["description"]) for c in novo], [(800.0, "Fixo UI")])

    # ── óbito ────────────────────────────────────────────────────────────────
    def _obito(self):
        db.register_death(self.animal_id, HOJE, db.DEATH_CAUSES[0], operator="op", notes="")
        db.clear_cache()
        return db.get_morte_vigente(self.animal_id)["id"]

    def test_obito_sem_motivo_nao_cancela(self):
        mid = self._obito()
        at = self._tela("campo")
        self._clicar(at, "Cancelar óbito", f"f_rev_obito_{mid}")
        self.assertTrue(any("motivo" in e.value.lower() for e in at.error), [e.value for e in at.error])
        self.assertIsNone(self._linha("deaths", mid)["cancelada_em"])

    def test_obito_cancelado_devolve_o_animal_ao_rebanho(self):
        mid = self._obito()
        # O animal do seed pode ter carência vigente: nesse caso volta como `carencia`, não `ativo`.
        esperado = "carencia" if db.get_withdrawal_end(self.animal_id) else "ativo"
        at = self._tela("campo")
        self._por_chave(at.text_input, f"ro_m_{mid}").set_value("animal estava vivo")
        self._clicar(at, "Cancelar óbito", f"f_rev_obito_{mid}")

        self.assertEqual(self._linha("deaths", mid)["motivo_cancelamento"], "animal estava vivo")
        db.clear_cache()
        self.assertEqual(get_animal(self.animal_id)["status"], esperado)
        self.assertIsNone(db.get_morte_vigente(self.animal_id))

    def test_obito_corrigido_troca_a_causa_e_o_animal_continua_morto(self):
        mid = self._obito()
        outra = db.DEATH_CAUSES[1]
        at = self._tela("campo")
        self._por_chave(at.text_input, f"ro_m_{mid}").set_value("causa errada")
        self._por_chave(at.selectbox, f"ro_c_{mid}").set_value(outra)
        self._clicar(at, "Salvar correção", f"f_rev_obito_{mid}")

        db.clear_cache()
        vigente = db.get_morte_vigente(self.animal_id)
        self.assertEqual((vigente["cause"], vigente["corrige_id"]), (outra, mid))
        self.assertEqual(get_animal(self.animal_id)["status"], "morto")


if __name__ == "__main__":
    unittest.main()
