"""O painel de pendências obedece ao §7.3? (Fase B na interface)

`repositories/nascimentos.pendencias()` já está testado. O que estes testes
travam é a **decisão de interface**, e ela é uma só, repetida em três formas:

> **Pendência com prazo futuro não pode se parecer com irregularidade.**

`sem_identificacao_oficial` lista o rebanho inteiro e só vira exigência em
**01/01/2033** (§4.1), com formato ainda não publicado (§23). Se ela contar
como alerta, o badge fica permanentemente alto e deixa de ser lido — o mesmo
erro que a dívida da fila de sincronização já produziu no §8.

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
class TestPainelPendencias(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_pend.db"))
        db.init_db()
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "alertas"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def _texto(self, at):
        return " ".join(
            [m.value for m in at.markdown] + [c.value for c in at.caption]
            + [e.label for e in at.expander])

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_aba_de_conformidade_existe(self):
        at = self._tela()
        self.assertIn("📋 Conformidade (§7.3)", [t.label for t in at.tabs])

    def test_toda_pendencia_com_animal_aparece_na_tela(self):
        """O painel não pode listar menos do que a consulta encontra: o que não
        aparece aqui só aparece na fiscalização."""
        pend = db.nascimentos.pendencias()
        com_animais = {k: v for k, v in pend.items() if v}
        self.assertTrue(com_animais,
                        "seed sem nenhuma pendência — este teste ficaria vazio")

        texto = self._texto(self._tela())
        for chave, ids in com_animais.items():
            self.assertIn(f"— {len(ids)}", texto,
                          f"pendência '{chave}' ({len(ids)}) não apareceu")

    def test_prazo_futuro_nao_e_marcado_como_irregularidade(self):
        """§4.1 só é exigível em 2033. Marcar como 🔴 hoje seria mentir sobre a
        situação da fazenda."""
        pend = db.nascimentos.pendencias()
        self.assertTrue(pend["sem_identificacao_oficial"],
                        "seed já teria identificação oficial — cenário ausente")

        rotulos = [e.label for e in self._tela().expander]
        oficial = [r for r in rotulos if "identificação oficial" in r]
        self.assertEqual(len(oficial), 1, rotulos)
        self.assertTrue(oficial[0].startswith("⏳"),
                        f"pendência de prazo futuro marcada como vigente: {oficial[0]!r}")

    def test_o_prazo_aparece_escrito(self):
        """O número sozinho engana. '12 sem identificação oficial' parece
        irregularidade até se ler que a exigência começa em 2033."""
        at = self._tela()
        self.assertIn("2033", self._texto(at),
                      "o painel não disse a partir de quando a exigência vale")

    def test_pendencia_de_prazo_futuro_fica_fora_do_contador(self):
        """O badge da barra lateral conta o que se faz hoje.

        Somar o rebanho inteiro nele deixaria o número permanentemente alto — e
        contador que nunca zera é contador que ninguém lê.
        """
        at = self._tela()
        pend = db.nascimentos.pendencias()
        rotulos = [b.label for b in at.button if (b.key or "") == "nav_alertas"]
        self.assertEqual(len(rotulos), 1, "botão de navegação de alertas não achado")

        badge = rotulos[0]
        n_oficial = len(pend["sem_identificacao_oficial"])
        self.assertNotIn(f"🔴{n_oficial}", badge,
                         f"o badge {badge!r} absorveu as pendências de 2033")


if __name__ == "__main__":
    unittest.main()
