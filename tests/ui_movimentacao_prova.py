"""A tela de movimentação obedece ao §8? (Fase B na interface)

A pré-validação é `services/movimentacao.py` e já está testada. Estes testes
travam as **decisões de interface** do §8, que não cabem no service:

- **Bloqueio não tem "liberar assim mesmo".** O §8.3 lista bloqueios e alertas;
  se a tela oferecer o botão nos dois casos, a distinção some na prática.
- **Alerta pede justificativa em texto, não uma caixa de seleção** (§8.4). O que
  fica no evento e na auditoria é o que a pessoa escreveu.
- **Rascunho não é validado.** É onde se monta o lote; validar aqui obrigaria a
  ter GTA antes de saber quais animais vão.
- **O seletor só oferece animais da origem.** Animal de outra propriedade é
  bloqueio garantido — oferecê-lo é armadilha.
- **Chegada parcial é divergência, não erro.** Desmarcar quem não chegou conclui
  a movimentação com ressalva registrada.

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
class TestTelaMovimentacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_mov.db"))
        db.init_db()
        db.clear_cache()

        # A tela exige duas propriedades — movimentar entre propriedades com
        # uma só não existe. O seed cria uma; a segunda é daqui.
        cls.origem = db.propriedades.padrao()
        assert cls.origem, "seed não criou propriedade"
        cls.destino_id = db.propriedades.criar_propriedade(
            cls.origem["produtor_id"], "Fazenda Destino")
        db.clear_cache()

        cls.animais = [a for a in db.get_all_animals(status="ativo")
                       if a.get("property_id") == cls.origem["id"]][:3]
        assert len(cls.animais) >= 2, "seed sem animais na propriedade padrão"

    def setUp(self):
        """Cada teste começa no mesmo mundo.

        Duas coisas vazam entre testes e as duas são reais: a fila de abertas é
        global, e **confirmar chegada muda a propriedade do animal** — é o
        efeito da movimentação, não um detalhe. Sem restaurar, o teste seguinte
        monta um lote com animais que já não são da origem, cai no bloqueio
        `animal_de_outra_propriedade` e falha por um motivo que não é o dele.
        """
        with db._conn() as con:
            con.execute("DELETE FROM movimentacao_animais")
            con.execute("DELETE FROM movimentacoes")
            con.execute("UPDATE animals SET property_id=?", (self.origem["id"],))
        db.clear_cache()

    def _rascunho(self, **campos):
        campos.setdefault("propriedade_origem_id", self.origem["id"])
        campos.setdefault("propriedade_destino_id", self.destino_id)
        campos.setdefault("animais", [a["uuid"] for a in self.animais[:2]])
        campos.setdefault("data_prevista", date.today().isoformat())
        r = db.movimentacoes.criar(campos.pop("tipo", "venda"),
                                   usuario="setup", **campos)
        self.assertTrue(r["ok"], r)
        db.clear_cache()
        return r["id"]

    def _selecionar_origem(self, at):
        """A tela ordena as propriedades por nome, e a primeira não é a origem
        deste cenário. Escolher explicitamente evita o teste medir a tela de
        uma propriedade sem animais."""
        caixa = self._por_chave(at.selectbox, "movn_origem")
        caixa.set_value([o for o in caixa.options
                         if o.startswith(self.origem["nome"])][0])
        at.run()
        return at

    def _tela(self, **estado):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "movimentacao"
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

    def _sem_chave(self, widgets, chave):
        return [w for w in widgets if (w.key or "") == chave] == []

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_pagina_existe(self):
        at = self._tela()
        self.assertIn("🚚 Movimentação entre Propriedades",
                      " ".join(m.value for m in at.markdown))

    def test_sem_gta_e_alerta_e_pede_justificativa_escrita(self):
        """§8.4: o que fica registrado é o texto de quem avaliou."""
        self._rascunho(gta_numero="")
        at = self._tela()

        self.assertTrue(list(at.warning), "falta de GTA não foi avisada")
        self.assertTrue(self._por_chave(at.button, "mov_liberar").disabled,
                        "liberou com alerta e sem justificativa (§8.4)")

        self._por_chave(at.text_input, "mov_just").set_value("GTA emitida na barreira")
        at.run()
        self.assertFalse(self._por_chave(at.button, "mov_liberar").disabled,
                         "justificativa escrita não liberou a saída")

    def test_pedido_de_justificativa_segue_a_regra(self):
        """A tela pede justificativa exatamente quando a regra manda — nem mais,
        nem menos.

        Usa `pre_validar` como oráculo em vez de fixar quais alertas existem.
        Fixar seria frágil por um motivo que o próprio §6.3 impõe:
        `animal_events` é append-only, os testes anteriores deixam eventos
        pendentes de sincronização, e **não há como limpá-los** — o que muda o
        conjunto de alertas conforme a ordem de execução. O que importa aqui não
        é qual alerta apareceu, é a tela concordar com a regra.
        """
        mid = self._rascunho(
            gta_numero="GTA-123",
            data_prevista=(date.today() + timedelta(days=2)).isoformat())
        v = db.movimentacoes.pre_validar(mid)

        at = self._tela()
        pediu = not self._sem_chave(at.text_input, "mov_just")
        self.assertEqual(
            pediu, v["exige_confirmacao"],
            f"tela pediu justificativa={pediu}, regra diz "
            f"{v['exige_confirmacao']} (problemas: "
            f"{[(p['codigo'], p['gravidade']) for p in v['problemas']]})")

        if not pediu:
            self.assertFalse(self._por_chave(at.button, "mov_liberar").disabled,
                             "travou a liberação sem haver alerta")

    def test_bloqueio_nao_oferece_liberar(self):
        """§8.3: bloqueio impede. Um botão desabilitado ainda sugere que existe
        um caminho; aqui não existe."""
        self._rascunho(gta_numero="GTA-9", animais=[])
        at = self._tela()

        self.assertTrue(list(at.error), "bloqueio não foi mostrado")
        self.assertTrue(self._sem_chave(at.button, "mov_liberar"),
                        "tela ofereceu liberar apesar do bloqueio")

    def test_seletor_de_animais_so_traz_os_da_origem(self):
        """Animal de outra propriedade é bloqueio garantido na pré-validação."""
        # Move um animal para o destino, para haver o que NÃO oferecer.
        with db._conn() as con:
            con.execute("UPDATE animals SET property_id=? WHERE uuid=?",
                        (self.destino_id, self.animais[0]["uuid"]))
        db.clear_cache()

        at = self._selecionar_origem(self._tela())
        opcoes = self._por_chave(at.multiselect, "movn_animais").options
        self.assertTrue(opcoes, "nenhum animal oferecido para a origem")
        self.assertFalse(
            any(o.startswith(self.animais[0]["id"]) for o in opcoes),
            f"animal {self.animais[0]['id']} de outra propriedade foi oferecido")

    def test_destino_nunca_repete_a_origem(self):
        """Origem igual ao destino é bloqueio — não pode nem ser escolhido."""
        at = self._tela()
        origem = self._por_chave(at.selectbox, "movn_origem").value
        self.assertNotIn(origem,
                         self._por_chave(at.selectbox, "movn_destino").options)

    def test_rascunho_exige_animais_e_nao_exige_gta(self):
        """Rascunho é onde se monta: sem animal não há o que criar, mas a guia
        costuma sair depois do lote montado."""
        at = self._selecionar_origem(self._tela())
        self.assertTrue(self._por_chave(at.button, "movn_salvar").disabled,
                        "criou rascunho sem animal")

        caixa = self._por_chave(at.multiselect, "movn_animais")
        caixa.set_value([caixa.options[0]])
        at.run()
        self.assertFalse(self._por_chave(at.button, "movn_salvar").disabled,
                         "exigiu GTA para criar rascunho")

    def test_chegada_parcial_registra_divergencia(self):
        """§8.2: quem embarcou e não chegou fica marcado, e a movimentação
        conclui com ressalva em vez de silêncio."""
        mid = self._rascunho(gta_numero="GTA-77")
        r = db.movimentacoes.liberar(mid, usuario="op1")
        self.assertTrue(r["ok"], r)
        db.clear_cache()

        at = self._tela()
        ausente = self.animais[0]["uuid"]
        self._por_chave(at.checkbox, f"mov_rec_{ausente}").set_value(False)
        at.run()

        self.assertTrue(list(at.warning), "chegada parcial não foi avisada")
        self._por_chave(at.button, "mov_confirmar").click()
        at.run()

        mov = db.movimentacoes.get(mid)
        self.assertEqual(mov["status"], "divergente", mov)
        faltante = [a for a in mov["animais"] if a["animal_uuid"] == ausente][0]
        self.assertEqual(faltante["divergencia"], "nao_recebido")


if __name__ == "__main__":
    unittest.main()
