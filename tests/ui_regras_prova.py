"""A tela de regras obedece ao §11? (Fase B na interface)

`repositories/regras.py` e `services/regras_regulatorias.py` já estão testados.
O que estes testes travam são as três decisões de interface que o §11 impõe:

- **Não existe "editar" regra** (§11.2). Editar no lugar reescreveria o passado:
  uma movimentação julgada em 2027 passaria a ser explicada por um texto que
  não existia então. A tela só oferece **nova versão**.
- **Nova versão exige responsável pela aprovação** (§11.1). Decisão regulatória
  sem responsável é decisão de ninguém.
- **A simulação vem antes de salvar** (§11.3). Ativar bloqueio sem saber o
  alcance é descobri-lo no dia em que o caminhão está no curral.

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
class TestTelaRegras(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_regras.db"))
        db.init_db()
        db.clear_cache()

        # Uma aprovada e um rascunho: os dois estados que a tela precisa
        # distinguir, e que o §11.1 separa.
        r = db.regras.criar("Regra aprovada de teste", nivel="alerta",
                            aprovado_por="Fiscal", usuario="setup")
        assert r["ok"] and r["ativa"], r
        cls.aprovada = r["id"]
        r2 = db.regras.criar("Rascunho sem responsável", nivel="bloqueio",
                             usuario="setup")
        assert r2["ok"] and not r2["ativa"], r2
        cls.rascunho = r2["id"]
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "regras"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def _por_chave(self, widgets, chave):
        achados = [w for w in widgets if (w.key or "") == chave]
        self.assertEqual(len(achados), 1,
                         f"esperava 1 widget com chave '{chave}', achei {len(achados)}")
        return achados[0]

    def _escolher(self, at, regra_id):
        nome = db.regras.get(regra_id)["nome"]
        caixa = self._por_chave(at.selectbox, "reg_sel")
        caixa.set_value([o for o in caixa.options if o.startswith(nome)][0])
        at.run()
        return at

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_pagina_existe(self):
        at = self._tela()
        self.assertIn("📜 Regras Regulatórias",
                      " ".join(m.value for m in at.markdown))

    def test_operador_nao_entra(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 2, "username": "op1",
                                    "name": "Operador", "role": "operador"}
        at.session_state["page"] = "regras"
        at.run()
        self.assertEqual(list(at.exception), [])
        self.assertNotIn("📜 Regras Regulatórias",
                         " ".join(m.value for m in at.markdown),
                         "operador alcançou a administração de regras")

    def test_nao_existe_editar_no_lugar(self):
        """§11.2: só nova versão. Um botão 'salvar alterações' aqui destruiria
        o histórico que explica o que já foi julgado."""
        at = self._escolher(self._tela(), self.aprovada)
        rotulos = " ".join(b.label.lower() for b in at.button)
        self.assertNotIn("salvar alterações", rotulos)
        self.assertIn("nova versão", rotulos,
                      f"a tela não ofereceu versionamento: {rotulos!r}")

    def test_nova_versao_exige_responsavel(self):
        """§11.1: decisão regulatória sem responsável é decisão de ninguém."""
        at = self._escolher(self._tela(), self.aprovada)
        self.assertTrue(self._por_chave(at.button, "reg_versao").disabled,
                        "versionou sem responsável pela aprovação")

        self._por_chave(at.text_input, "reg_aprovador").set_value("Fiscal 2")
        at.run()
        self.assertFalse(self._por_chave(at.button, "reg_versao").disabled)

    def test_rascunho_e_mostrado_como_rascunho(self):
        """Regra sem responsável nasce inativa. Se a tela não disser isso, o
        usuário acredita que cadastrou uma regra que vale."""
        at = self._escolher(self._tela(), self.rascunho)
        texto = " ".join(w.value for w in at.warning)
        self.assertIn("ascunho", texto,
                      f"a tela não avisou que a regra está inativa: {texto!r}")

    def test_simulacao_aparece_antes_de_cadastrar(self):
        """§11.3: o alcance precisa estar na tela antes do botão, não depois
        de salvar."""
        at = self._tela()
        rotulos = [m.label for m in at.metric]
        self.assertIn("Animais atingidos", rotulos,
                      f"nenhuma simulação na tela: {rotulos}")
        self.assertIn("Alcance", rotulos)

    def test_simulacao_reage_ao_escopo(self):
        """Escopo que não bate com ninguém precisa mostrar zero — número que
        não muda com o formulário é número decorativo."""
        at = self._tela()
        self._por_chave(at.selectbox, "regn_sexo").set_value("M")
        self._por_chave(at.number_input, "regn_idade_min").set_value(240)
        at.run()

        atingidos = [m for m in at.metric if m.label == "Animais atingidos"]
        self.assertTrue(atingidos)
        self.assertEqual(atingidos[-1].value, "0",
                         "escopo impossível ainda atingiu animais")

    def test_criar_sem_responsavel_nasce_inativa(self):
        at = self._tela()
        self._por_chave(at.text_input, "regn_nome").set_value("Nascida rascunho")
        at.run()
        self._por_chave(at.button, "regn_salvar").click()
        at.run()

        nova = [r for r in db.regras.listar(apenas_ativas=False)
                if r["nome"] == "Nascida rascunho"]
        self.assertEqual(len(nova), 1, "regra não foi criada")
        self.assertFalse(nova[0]["ativa"],
                         "regra sem responsável nasceu ativa (§11.1)")


if __name__ == "__main__":
    unittest.main()
