"""Ficha do animal: corrigir ou cancelar uma aplicação de medicamento.

Critérios:
1. A aplicação vigente oferece "corrigir ou cancelar"; o motivo é obrigatório.
2. Corrigir grava a certa, ligada à original, e a original aparece como cancelada.
3. Cancelar deixa a linha riscada, com o motivo, e tira a carência do animal.

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
class TestCorrecaoNaFicha(unittest.TestCase):
    def setUp(self):
        import streamlit as st
        st.cache_data.clear()
        self._dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self._dir, "ui_correcao_tratamento.db"))
        db.init_db()
        db.clear_cache()
        self.animal_id = db.get_all_animals()[0]["id"]
        db.add_medication(db.MedicationData(
            animal_id=self.animal_id, medication_name="Produto CORR UI", dose=50.0, unit="ml",
            application_route="Subcutânea (SC)", withdrawal_days=30, med_date=date.today().isoformat(),
            applied_by="op", lote_produto="L1"))
        db.clear_cache()
        self.mid = [m for m in db.get_medication_history(self.animal_id)
                    if m["medication_name"] == "Produto CORR UI"][0]["id"]

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

    def _clicar(self, at, rotulo):
        # A ficha do seed tem várias aplicações, cada uma com o seu formulário: acha o botão
        # pelo formulário da aplicação deste teste.
        botao = [b for b in at.button
                 if rotulo in (b.label or "") and b.proto.form_id.endswith(f"corr_form_{self.mid}")]
        self.assertEqual(len(botao), 1, f"botão '{rotulo}': {len(botao)}")
        botao[0].click()
        at.run()
        self.assertEqual(list(at.exception), [], [e.value for e in at.exception])

    def _linha(self, mid):
        with db._conn() as con:
            return dict(con.execute("SELECT * FROM medications WHERE id=?", (mid,)).fetchone())

    def test_formulario_de_correcao_existe_para_a_aplicacao_vigente(self):
        at = self._tela()
        self._por_chave(at.text_input, f"corr_motivo_{self.mid}")
        self._por_chave(at.number_input, f"corr_dose_{self.mid}")

    def test_sem_motivo_mostra_erro_e_nao_grava(self):
        at = self._tela()
        self._clicar(at, "Cancelar aplicação")
        self.assertTrue(any("motivo" in e.value.lower() for e in at.error), [e.value for e in at.error])
        self.assertIsNone(self._linha(self.mid)["cancelada_em"])

    def test_corrigir_grava_a_certa_ligada_a_original(self):
        at = self._tela()
        self._por_chave(at.text_input, f"corr_motivo_{self.mid}").set_value("dose com zero a mais")
        self._por_chave(at.number_input, f"corr_dose_{self.mid}").set_value(5.0)
        self._clicar(at, "Salvar correção")

        original = self._linha(self.mid)
        self.assertTrue(original["cancelada_em"])
        self.assertEqual(original["motivo_cancelamento"], "dose com zero a mais")
        self.assertEqual(original["cancelada_por"], "admin")
        nova = [m for m in db.get_medication_history(self.animal_id) if m["corrige_id"] == self.mid]
        self.assertEqual(len(nova), 1)
        self.assertEqual(nova[0]["dose"], 5.0)
        self.assertEqual(nova[0]["applied_by"], "op", "quem aplicou continua sendo quem aplicou")

    def test_cancelar_grava_o_motivo_e_marca_a_linha(self):
        at = self._tela()
        self._por_chave(at.text_input, f"corr_motivo_{self.mid}").set_value("animal errado")
        self._clicar(at, "Cancelar aplicação")

        linha = self._linha(self.mid)
        self.assertEqual(linha["motivo_cancelamento"], "animal errado")
        db.clear_cache()
        # O animal do seed tem outras aplicações: o que importa é a carência de 30 dias sair.
        fim = db.get_withdrawal_end(self.animal_id)
        self.assertTrue(fim is None or fim < date.today() + timedelta(days=30), fim)

        depois = self._tela()      # a ficha mostra a cancelada, riscada, e sem novo formulário
        textos = " ".join(m.value for m in depois.markdown)
        self.assertIn("Cancelada", textos)
        self.assertIn("animal errado", textos)
        self.assertEqual([w for w in depois.text_input if (w.key or "") == f"corr_motivo_{self.mid}"], [])


if __name__ == "__main__":
    unittest.main()
