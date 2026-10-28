"""Calendário sanitário, aba "Brucelose (SDA)": registrar a vacinação e confirmar o registro oficial.

Critérios:
1. Registrar exige o médico-veterinário e grava o ato com as fêmeas escolhidas.
2. O ato nasce "pendente no SDA"; confirmar exige a referência do atestado.
3. Cancelar exige motivo e tira o ato da lista.

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
class TestBruceloseNaTela(unittest.TestCase):
    def setUp(self):
        import streamlit as st
        st.cache_data.clear()
        self._dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self._dir, "ui_brucelose.db"))
        db.init_db()
        db.clear_cache()
        self.prop = db.propriedades.listar()[0]["id"]
        self.femeas = [a["id"] for a in db.get_all_animals()
                       if a.get("sex") == "F" and a.get("property_id") == self.prop][:2]
        self.assertEqual(len(self.femeas), 2, "o seed deveria ter ao menos duas fêmeas na propriedade padrão")

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin", "name": "Admin", "role": "admin"}
        at.session_state["page"] = "sanitario"
        at.run()
        self.assertEqual(list(at.exception), [], [e.value for e in at.exception])
        return at

    def _por_chave(self, widgets, chave):
        achados = [w for w in widgets if (w.key or "") == chave]
        self.assertEqual(len(achados), 1, f"esperava 1 widget '{chave}', achei {len(achados)}")
        return achados[0]

    def _clicar(self, at, rotulo, formulario=None):
        botao = [b for b in at.button if rotulo in (b.label or "")
                 and (formulario is None or b.proto.form_id.endswith(formulario))]
        self.assertEqual(len(botao), 1, f"botão '{rotulo}' em {formulario}: {len(botao)}")
        botao[0].click()
        at.run()
        self.assertEqual(list(at.exception), [], [e.value for e in at.exception])

    def _registrar_pela_tela(self, at, veterinario="Dra. Ana"):
        self._por_chave(at.multiselect, "bru_animais").set_value(self.femeas)
        self._por_chave(at.text_input, "bru_vet").set_value(veterinario)
        self._clicar(at, "Registrar vacinação", "bru_novo")

    def _atos(self):
        return db.vacinacao_brucelose.listar(incluir_canceladas=True)

    def test_sem_veterinario_mostra_erro_e_nao_grava(self):
        at = self._tela()
        self._registrar_pela_tela(at, veterinario=" ")
        self.assertTrue(any("veterinário" in e.value for e in at.error), [e.value for e in at.error])
        self.assertEqual(self._atos(), [])

    def test_registrar_grava_o_ato_pendente_com_as_femeas(self):
        at = self._tela()
        self._registrar_pela_tela(at)

        atos = self._atos()
        self.assertEqual(len(atos), 1)
        self.assertEqual((atos[0]["status_oficial"], atos[0]["n_animais"], atos[0]["veterinario_nome"]),
                         ("pendente_sda", 2, "Dra. Ana"))
        self.assertEqual(sorted(a["brinco"] for a in db.vacinacao_brucelose.animais_da_vacinacao(atos[0]["id"])),
                         sorted(self.femeas))
        depois = self._tela()
        self.assertTrue(any("Pendente" in e.label or "Atrasada" in e.label or "Perto do prazo" in e.label
                            for e in depois.expander), [e.label for e in depois.expander])

    def test_confirmar_exige_a_referencia_do_atestado(self):
        at = self._tela()
        self._registrar_pela_tela(at)
        vid = self._atos()[0]["id"]

        depois = self._tela()
        self._clicar(depois, "Confirmar: registrada no SDA", f"bru_conf_{vid}")
        self.assertTrue(any("referência" in e.value for e in depois.error), [e.value for e in depois.error])
        self.assertEqual(self._atos()[0]["status_oficial"], "pendente_sda")

        depois = self._tela()
        self._por_chave(depois.text_input, f"bru_ref_{vid}").set_value("SDA-2027/00123")
        self._clicar(depois, "Confirmar: registrada no SDA", f"bru_conf_{vid}")
        ato = self._atos()[0]
        self.assertEqual((ato["status_oficial"], ato["referencia_atestado"], ato["confirmado_por"]),
                         ("registrado_sda", "SDA-2027/00123", "Admin"))

    def test_cancelar_exige_motivo_e_tira_o_ato_da_lista(self):
        at = self._tela()
        self._registrar_pela_tela(at)
        vid = self._atos()[0]["id"]

        depois = self._tela()
        self._clicar(depois, "Cancelar vacinação", f"bru_canc_{vid}")
        self.assertTrue(any("motivo" in e.value.lower() for e in depois.error), [e.value for e in depois.error])
        self.assertIsNone(self._atos()[0]["cancelada_em"])

        depois = self._tela()
        self._por_chave(depois.text_input, f"bru_mot_{vid}").set_value("vacas erradas")
        self._clicar(depois, "Cancelar vacinação", f"bru_canc_{vid}")
        self.assertEqual(self._atos()[0]["motivo_cancelamento"], "vacas erradas")
        self.assertEqual(db.vacinacao_brucelose.listar(), [])


if __name__ == "__main__":
    unittest.main()
