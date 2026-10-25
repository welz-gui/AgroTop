"""Ficha do animal: corrigir ou cancelar uma pesagem e a última movimentação.

Critérios:
1. Pesagem: o motivo é obrigatório; corrigir grava a certa e o peso atual acompanha; cancelar
   devolve o peso da pesagem anterior; a cancelada aparece riscada, com o motivo.
2. Movimentação: cancelar devolve o animal ao piquete de origem; corrigir o leva ao destino certo.

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


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestRevisaoNaFicha(unittest.TestCase):
    def setUp(self):
        import streamlit as st
        st.cache_data.clear()
        self._dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self._dir, "ui_revisao.db"))
        db.init_db()
        db.clear_cache()
        animal = [a for a in db.get_all_animals() if a.get("lote_id")][0]
        self.animal_id = animal["id"]
        self.origem = animal["lote_id"]
        outros = [l["id"] for l in db.get_all_lotes() if l["id"] != self.origem]
        self.destino, self.certo = outros[0], outros[1]
        # Uma pesagem nova (a mais recente) e uma movimentação para o primeiro destino.
        self.peso_anterior = get_animal(self.animal_id)["current_weight"]
        db.add_weighing(db.WeighingCreate(self.animal_id, 555.0, date.today().isoformat(), "op"))
        db.move_animal(self.animal_id, db.MovementParams(self.destino, date.today().isoformat(), "manejo", "op"))
        db.clear_cache()
        self.pesagem_id = [w for w in db.get_weighing_history(self.animal_id) if w["weight"] == 555.0][0]["id"]
        self.mov_id = db.movimentacao_revisavel(self.animal_id)["id"]

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin", "name": "Admin", "role": "admin"}
        at.session_state["page"] = "animal"
        at.session_state["animal_detail"] = self.animal_id
        at.run()
        self.assertEqual(list(at.exception), [], [e.value for e in at.exception])
        return at

    def _por_chave(self, widgets, chave):
        achados = [w for w in widgets if (w.key or "") == chave]
        self.assertEqual(len(achados), 1, f"esperava 1 widget '{chave}', achei {len(achados)}")
        return achados[0]

    def _clicar(self, at, formulario, rotulo):
        botao = [b for b in at.button
                 if rotulo in (b.label or "") and b.proto.form_id.endswith(formulario)]
        self.assertEqual(len(botao), 1, f"botão '{rotulo}' em {formulario}: {len(botao)}")
        botao[0].click()
        at.run()
        self.assertEqual(list(at.exception), [], [e.value for e in at.exception])

    def _peso_atual(self):
        db.clear_cache()
        return get_animal(self.animal_id)["current_weight"]

    def _lote_atual(self):
        db.clear_cache()
        return get_animal(self.animal_id)["lote_id"]

    # ── pesagem ──────────────────────────────────────────────────────────────
    def test_pesagem_sem_motivo_mostra_erro_e_nao_grava(self):
        at = self._tela()
        self._clicar(at, f"rev_peso_form_{self.pesagem_id}", "Cancelar pesagem")
        self.assertTrue(any("motivo" in e.value.lower() for e in at.error), [e.value for e in at.error])
        self.assertEqual(self._peso_atual(), 555.0)

    def test_corrigir_pesagem_grava_a_certa_e_o_peso_atual_acompanha(self):
        at = self._tela()
        self._por_chave(at.text_input, f"rev_peso_motivo_{self.pesagem_id}").set_value("digitei 555")
        self._por_chave(at.number_input, f"rev_peso_peso_{self.pesagem_id}").set_value(455.0)
        self._clicar(at, f"rev_peso_form_{self.pesagem_id}", "Salvar correção")

        self.assertEqual(self._peso_atual(), 455.0)
        hist = db.get_weighing_history(self.animal_id)
        original = [w for w in hist if w["id"] == self.pesagem_id][0]
        self.assertEqual((original["motivo_cancelamento"], original["cancelada_por"]), ("digitei 555", "admin"))
        self.assertEqual([w["weight"] for w in hist if w["corrige_id"] == self.pesagem_id], [455.0])

    def test_cancelar_pesagem_devolve_o_peso_anterior_e_mostra_a_riscada(self):
        at = self._tela()
        self._por_chave(at.text_input, f"rev_peso_motivo_{self.pesagem_id}").set_value("pesei o animal errado")
        self._clicar(at, f"rev_peso_form_{self.pesagem_id}", "Cancelar pesagem")

        self.assertEqual(self._peso_atual(), self.peso_anterior)
        depois = self._tela()
        textos = " ".join(m.value for m in depois.markdown)
        self.assertIn("Cancelada", textos)
        self.assertIn("pesei o animal errado", textos)

    # ── movimentação ─────────────────────────────────────────────────────────
    def test_movimentacao_sem_motivo_mostra_erro_e_nao_grava(self):
        at = self._tela()
        self._clicar(at, f"rev_mov_form_{self.mov_id}", "Cancelar e devolver")
        self.assertTrue(any("motivo" in e.value.lower() for e in at.error), [e.value for e in at.error])
        self.assertEqual(self._lote_atual(), self.destino)

    def test_cancelar_movimentacao_devolve_o_animal_ao_piquete_de_origem(self):
        at = self._tela()
        self._por_chave(at.text_input, f"rev_mov_motivo_{self.mov_id}").set_value("piquete errado")
        self._clicar(at, f"rev_mov_form_{self.mov_id}", "Cancelar e devolver")

        self.assertEqual(self._lote_atual(), self.origem)
        depois = self._tela()
        textos = " ".join(m.value for m in depois.markdown)
        self.assertIn("Cancelada", textos)
        self.assertIn("piquete errado", textos)

    def test_corrigir_movimentacao_leva_o_animal_ao_destino_certo(self):
        at = self._tela()
        self._por_chave(at.text_input, f"rev_mov_motivo_{self.mov_id}").set_value("era outro piquete")
        self._por_chave(at.selectbox, f"rev_mov_destino_{self.mov_id}").select(self.certo)
        self._clicar(at, f"rev_mov_form_{self.mov_id}", "Salvar correção")

        self.assertEqual(self._lote_atual(), self.certo)
        vigentes = db.get_movements(self.animal_id)
        self.assertEqual((vigentes[0]["from_lote_id"], vigentes[0]["to_lote_id"]), (self.origem, self.certo))
        self.assertEqual(vigentes[0]["corrige_id"], self.mov_id)


if __name__ == "__main__":
    unittest.main()
