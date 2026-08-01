"""A interface reflete a máquina de estados? (ROADMAP: afirmação não é evidência)

Os testes de `test_integracao_estados_importacao.py` provam a REGRA. Estes provam
que a **tela obedece a ela** — que o aviso aparece, o campo de justificativa
aparece e o botão fica desabilitado até a justificativa ser escrita.

Nenhum teste de unidade pega isso: dá para a regra estar perfeita e a tela
gravar assim mesmo. Usa `streamlit.testing.v1.AppTest`, que executa `app.py`
sem navegador.

⚠️ **Não começa com `test_` de propósito.** O `AppTest` levanta um runtime do
Streamlit próprio, e rodando dentro da suíte grande ele encontra o módulo de
cache já carregado por outro caminho — o resultado é
`PicklingError: it's not the same object as ...CachedResult`. Passa sozinho e
quebra em conjunto, que é o pior tipo de teste.

Quem executa isto é `test_ui_estados.py`, num **subprocesso**. Rode direto com:

    AGROTOP_FORCE_SQLITE=1 python -m unittest tests.ui_estados_prova
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


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível nesta versão")
class TestTelaStatusAnimal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # O `@st.cache_data` de `repositories/conexao.py` guarda resultado de
        # execuções anteriores da suíte. O AppTest levanta um runtime próprio, e
        # a entrada velha não pertence a ele — dá erro de pickle. Limpar antes é
        # o que separa este teste dos que rodaram antes.
        import streamlit as st
        st.cache_data.clear()

        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui.db"))
        db.init_db()
        db.clear_cache()

        ativos = db.get_all_animals(status="ativo")
        assert ativos, "seed sem animais ativos"
        cls.ativo = ativos[0]["id"]

        vendidos = [a["id"] for a in db.get_all_animals(status=None)
                    if a["status"] == "vendido"]
        assert vendidos, "seed sem animal vendido — o caso sensível não existe"
        cls.vendido = vendidos[0]

    def _tela(self, animal, novo_status):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=120)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "admin"
        at.run()
        caixas = {s.label: s for s in at.selectbox}
        caixas["Animal"].set_value(animal)
        caixas["Novo Status"].set_value(novo_status)
        at.run()
        return at

    def _botao_atualizar(self, at):
        alvos = [b for b in at.button if "Atualizar" in (b.label or "")]
        self.assertEqual(len(alvos), 1, "botão de atualizar status não encontrado")
        return alvos[0]

    def _campo_justificativa(self, at):
        return [t for t in at.text_area if "Justificativa" in (t.label or "")]

    def test_transicao_livre_nao_pede_justificativa(self):
        at = self._tela(self.ativo, "vendido")
        self.assertEqual(self._campo_justificativa(at), [],
                         "transição cotidiana passou a exigir justificativa")
        self.assertFalse(self._botao_atualizar(at).disabled)

    def test_sair_de_estado_final_pede_justificativa_e_trava_o_botao(self):
        at = self._tela(self.vendido, "ativo")
        campos = self._campo_justificativa(at)
        self.assertEqual(len(campos), 1, "campo de justificativa não apareceu")
        self.assertTrue(
            any("justificativa" in w.value.casefold() for w in at.warning),
            f"nenhum aviso explicando a exigência: {[w.value for w in at.warning]}")
        self.assertTrue(self._botao_atualizar(at).disabled,
                        "botão habilitado sem justificativa — a trava não existe")

    def test_botao_libera_depois_da_justificativa(self):
        at = self._tela(self.vendido, "ativo")
        self._campo_justificativa(at)[0].set_value("venda cancelada pelo comprador")
        at.run()
        self.assertFalse(self._botao_atualizar(at).disabled,
                         "botão continuou travado mesmo com justificativa escrita")


if __name__ == "__main__":
    unittest.main()
