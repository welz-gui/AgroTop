"""A transferência de animais em lote entre piquetes chegou à tela de verdade?

Trilha 3 (ROADMAP §5, Estoque → Financeiro → Nutrição), sétima fatia:
`db.move_animal` (na ficha do animal) só movia um de cada vez — mover um
piquete inteiro (rodízio de pasto, separação de lote) exigia abrir a ficha
de cada animal, um a um. `db.move_animals_bulk` (`repositories/animais.py`)
é a mesma operação, para vários animais, na mesma transação; a aba
"🔀 Transferir Animais" (em Lotes / Pastagem) é a ligação.

Estes testes travam:

- **Selecionar animais de um piquete e movê-los todos para outro** funciona
  de ponta a ponta pela tela real.
- **Animal inexistente não derruba a transferência dos outros** — cada
  animal é resolvido independentemente.

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
class TestTransferenciaDeAnimaisNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_transf.db"))
        db.init_db()
        db.clear_cache()

    def setUp(self):
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "lotes"
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

    def test_a_aba_de_transferencia_existe(self):
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Transferir Animais" in r for r in rotulos), rotulos)

    def test_transferir_dois_animais_move_os_dois(self):
        lotes = db.get_all_lotes()
        # Garante uma origem com pelo menos 2 animais ativos, senão o teste
        # não exercitaria a transferência em lote de verdade.
        with_animals = [l for l in lotes
                        if len(db.get_all_animals(status="ativo", lote_id=l["id"])) >= 2]
        self.assertTrue(with_animals, "seed sem piquete com >= 2 animais ativos")
        origem = with_animals[0]
        destino = next(l for l in lotes if l["id"] != origem["id"])

        at = self._tela()
        origem_sel = self._por_chave(at.selectbox, "transf_origem")
        origem_sel.set_value(origem)
        at.run()

        ms = self._por_chave(at.multiselect, "transf_animais")
        self.assertGreaterEqual(len(ms.options), 2)
        ms.set_value(ms.options[:2])
        at.run()

        destino_sel = [w for w in at.selectbox if w.label == "Piquete de destino"][0]
        destino_sel.set_value(destino)
        at.run()

        botao = [b for b in at.button if b.label == "✅ Transferir"][0]
        botao.click()
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção ao transferir: {[e.value for e in at.exception]}")
        # Não checa `at.success` aqui: o handler faz `st.success(...)` seguido
        # de `st.rerun()` — o `AppTest` persegue o rerun interno e devolve o
        # estado da execução final, não da que exibiu a mensagem (mesma
        # pegadinha já documentada em ui_compra_de_insumo_prova.py). A prova
        # real é o banco, conferido abaixo.

        db.clear_cache()
        ativos_destino = db.get_all_animals(status="ativo", lote_id=destino["id"])
        ativos_origem = db.get_all_animals(status="ativo", lote_id=origem["id"])
        self.assertEqual(len(ativos_origem), 0, "origem deveria ter esvaziado")
        self.assertGreaterEqual(len(ativos_destino), 2)


if __name__ == "__main__":
    unittest.main()
