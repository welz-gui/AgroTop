"""A tela de nascimento obedece ao §7.2? (Fase B na interface)

A regra é `services/genealogia.py` e já está testada. Estes testes travam a
**decisão de interface** que o §7.2 impõe:

> o sistema deve "emitir alerta, **sem substituir a avaliação técnica**"

Ou seja: **bloqueio impede; alerta pede confirmação e libera.** Confundir os dois
é o erro que trava o pecuarista sem prova, ou deixa passar o que não devia.

⚠️ **Não começa com `test_` de propósito** — ver `tests/ui_estados_prova.py`.
Quem executa isto é `tests/test_ui.py`, num subprocesso.
"""

import os
import sqlite3
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


def _dias_atras(n):
    return (date.today() - timedelta(days=n)).isoformat()


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestTelaNascimento(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_nasc.db"))
        db.init_db()
        db.clear_cache()

    @classmethod
    def _mae_apta(cls):
        """Uma fêmea com idade suficiente para parir.

        O seed gera animais de 400 a 900 dias, então parte das fêmeas tem menos
        de 18 meses e é **corretamente bloqueada** pelo §7. Escolher qualquer uma
        faria o teste medir o bloqueio em vez do fluxo.

        Também precisa estar **sem parto recente**: o banco é compartilhado pela
        classe (`setUpClass`), e o teste do alerta registra um parto. Sem este
        filtro, os testes passariam ou falhariam conforme a ordem alfabética em
        que o unittest os executa — que é o pior tipo de teste.
        """
        hoje = date.today()
        for a in db.get_all_animals(status="ativo"):
            if a.get("sex") != "F" or not a.get("birth_date"):
                continue
            if (hoje - date.fromisoformat(a["birth_date"])).days < 18 * 31:
                continue
            from repositories import nascimentos
            if nascimentos.partos_da_mae(a["uuid"]):
                continue
            return a
        raise AssertionError("seed sem fêmea apta e sem parto registrado")

    def _selecionar_mae(self, at, animal):
        caixa = self._por_chave(at.selectbox, "nasc_mae")
        alvo = [o for o in caixa.options if o.startswith(animal["id"])][0]
        caixa.set_value(alvo)
        at.run()
        return at

    def _tela(self, **estado):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "cadastrar"
        for k, v in estado.items():
            at.session_state[k] = v
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def _por_chave(self, widgets, chave):
        achados = [w for w in widgets if (w.key or "") == chave]
        self.assertEqual(len(achados), 1,
                         f"esperava 1 widget com chave '{chave}', achei {len(achados)}")
        return achados[0]

    def _botao(self, at):
        alvos = [b for b in at.button if (b.key or "") == "nasc_salvar"]
        self.assertEqual(len(alvos), 1, "botão de registrar nascimento não encontrado")
        return alvos[0]

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_aba_existe_e_lista_so_femeas(self):
        at = self._tela()
        self.assertIn("🐮 Nascimento na fazenda", [t.label for t in at.tabs])

        opcoes = self._por_chave(at.selectbox, "nasc_mae").options
        machos = [a["id"] for a in db.get_all_animals(status="ativo")
                  if a.get("sex") == "M"]
        for m in machos:
            self.assertFalse(any(o.startswith(m) for o in opcoes),
                             f"macho {m} apareceu como mãe")

    def test_botao_travado_sem_brinco(self):
        """Sem brinco não há cria — o botão não pode estar clicável."""
        at = self._selecionar_mae(self._tela(), self._mae_apta())
        self.assertTrue(self._botao(at).disabled,
                        "botão liberado sem brinco informado")

    def test_botao_libera_com_brinco(self):
        at = self._selecionar_mae(self._tela(), self._mae_apta())
        self._por_chave(at.text_input, "nasc_id_0").set_value("CRIA1")
        at.run()
        self.assertFalse(self._botao(at).disabled)

    def test_dois_brincos_iguais_travam_o_botao(self):
        """Ninhada com brincos repetidos é erro de digitação, não gêmeos."""
        at = self._selecionar_mae(self._tela(), self._mae_apta())
        self._por_chave(at.number_input, "nasc_n").set_value(2)
        at.run()
        self._por_chave(at.text_input, "nasc_id_0").set_value("IGUAL")
        self._por_chave(at.text_input, "nasc_id_1").set_value("IGUAL")
        at.run()
        self.assertTrue(self._botao(at).disabled)
        self.assertTrue(list(at.error), "nenhum erro mostrado para brinco repetido")

    def test_numero_de_crias_gera_campos_distintos(self):
        """§7.2: gêmeos precisam de animais distintos, logo brincos distintos."""
        at = self._selecionar_mae(self._tela(), self._mae_apta())
        self._por_chave(at.number_input, "nasc_n").set_value(3)
        at.run()
        for i in range(3):
            self._por_chave(at.text_input, f"nasc_id_{i}")

    def test_mae_jovem_demais_bloqueia_e_esconde_o_formulario(self):
        """Bloqueio não é alerta: a tela para antes dos campos da cria.

        O seed tem fêmeas com menos de 18 meses, e o §7 as recusa. Mostrar os
        campos e recusar só no fim faria o usuário preencher para nada.
        """
        hoje = date.today()
        jovem = next(a for a in db.get_all_animals(status="ativo")
                     if a.get("sex") == "F" and a.get("birth_date")
                     and (hoje - date.fromisoformat(a["birth_date"])).days < 18 * 30)
        at = self._selecionar_mae(self._tela(), jovem)

        self.assertTrue(list(at.error), "bloqueio não foi mostrado")
        self.assertEqual([w for w in at.text_input if (w.key or "") == "nasc_id_0"], [],
                         "campos da cria apareceram apesar do bloqueio")

    def test_alerta_exige_confirmacao_e_nao_impede(self):
        """O caso central do §7.2: alerta pede confirmação, não bloqueia.

        Dois partos com intervalo curto disparam `intervalo_entre_partos_curto`,
        que é ALERTA — biologicamente improvável não é impossível.
        """
        mae = self._mae_apta()
        r = db.nascimentos.registrar(
            mae["uuid"], _dias_atras(60),
            [{"id": "PREV1", "sexo": "M", "raca": "Nelore"}],
            responsavel="op1", ignorar_alertas=True)
        self.assertTrue(r["ok"], r)
        db.clear_cache()

        at = self._selecionar_mae(self._tela(), mae)

        confirma = [c for c in at.checkbox if (c.key or "") == "nasc_conf"]
        self.assertTrue(confirma, "alerta não ofereceu confirmação — virou bloqueio?")
        self.assertTrue(list(at.warning), "alerta não foi mostrado ao usuário")

        self._por_chave(at.text_input, "nasc_id_0").set_value("CRIA9")
        at.run()
        self.assertTrue(self._botao(at).disabled,
                        "botão liberado com alerta pendente de confirmação")

        self._por_chave(at.checkbox, "nasc_conf").set_value(True)
        at.run()
        self.assertFalse(self._botao(at).disabled,
                         "confirmação não liberou o registro")


if __name__ == "__main__":
    unittest.main()
