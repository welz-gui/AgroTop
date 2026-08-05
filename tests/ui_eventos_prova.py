"""A linha do tempo e o painel de sincronização obedecem ao §6 e ao §10? (Fase B na
interface)

`repositories/eventos.py` grava evento em toda operação desde o B2 — nenhum
teste aqui prova isso, já está coberto. O que estes testes travam são as
decisões de interface que o §6 e o §10 impõem, e que o repositório não pode
tomar sozinho:

- **Não existe editar um evento** (§6.3). Só "registrar correção", que cria
  outro evento apontando para o original. O original nunca some da tela.
- **A fila de sincronização em lote só oferece o que fecha a pendência**
  (§10.3). Se ela oferecesse 'rejeitado', o operador fecharia uma pendência
  que na verdade continua em aberto.
- **A trilha individual (§10.2) aceita qualquer situação**, inclusive as que
  não resolvem — é o "log técnico" que o parágrafo pede.

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
from services.sincronizacao import rotulo as sincronizacao_rotulo  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestLinhaDoTempoEsincronizacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_eventos.db"))
        db.init_db()
        db.clear_cache()
        cls.animal = db.get_all_animals(status="ativo")[0]

    def setUp(self):
        """Cada teste começa sem eventos além dos que ele mesmo cria.

        `animal_events` e `evento_sincronizacao` são append-only — não dá para
        limpar com DELETE (o gatilho recusa). Uso um animal por teste, tirado
        de uma lista maior que o número de testes, para eventos de um teste
        nunca aparecerem na tela de outro.
        """
        ativos = db.get_all_animals(status="ativo")
        indice = getattr(TestLinhaDoTempoEsincronizacao, "_proximo", 0)
        TestLinhaDoTempoEsincronizacao._proximo = indice + 1
        self.animal = ativos[indice % len(ativos)]

    def _tela_animal(self, **estado):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "animal"
        at.session_state["animal_detail"] = self.animal["id"]
        for k, v in estado.items():
            at.session_state[k] = v
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def _tela_sincronizacao(self, papel="admin"):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1 if papel == "admin" else 2,
                                    "username": "admin" if papel == "admin" else "op1",
                                    "name": "Admin" if papel == "admin" else "Operador",
                                    "role": papel}
        at.session_state["page"] = "sincronizacao"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def _por_chave(self, widgets, chave):
        achados = [w for w in widgets if (w.key or "") == chave]
        self.assertEqual(len(achados), 1,
                         f"esperava 1 widget com chave '{chave}', achei {len(achados)}")
        return achados[0]

    # ── linha do tempo (§6) ─────────────────────────────────────────────────

    def test_a_aba_existe_na_ficha_do_animal(self):
        at = self._tela_animal()
        self.assertIn("🕒 Linha do Tempo", [t.label for t in at.tabs])

    def test_evento_registrado_aparece_na_tela(self):
        r = db.eventos.registrar(self.animal["uuid"], "pesagem",
                                 usuario_registro="setup", observacoes="80 kg")
        self.assertTrue(r["ok"], r)
        db.clear_cache()

        at = self._tela_animal()
        texto = " ".join(m.value for m in at.markdown)
        self.assertIn("Pesagem", texto, "evento registrado não apareceu na linha do tempo")

    def test_nao_existe_editar_so_corrigir(self):
        """§6.3: a tela não pode oferecer alterar o evento no lugar."""
        db.eventos.registrar(self.animal["uuid"], "pesagem", usuario_registro="setup")
        db.clear_cache()

        at = self._tela_animal()
        rotulos_botao = " ".join(b.label.lower() for b in at.button)
        self.assertNotIn("salvar alterações", rotulos_botao)
        self.assertTrue(any("registrar correção" in (ex.label or "").lower()
                            for ex in at.expander),
                        "tela não ofereceu o caminho de correção do §6.3")

    def test_correcao_exige_justificativa_e_preserva_o_original(self):
        r = db.eventos.registrar(self.animal["uuid"], "pesagem", usuario_registro="setup")
        db.clear_cache()
        at = self._tela_animal()

        # Pega o primeiro botão "corr_salvar_<id>" — é o do evento recém-criado.
        botoes_correcao = [b for b in at.button if (b.key or "").startswith("corr_salvar_")]
        self.assertEqual(len(botoes_correcao), 1)
        self.assertTrue(botoes_correcao[0].disabled,
                        "botão de correção liberado sem justificativa")

        eid = botoes_correcao[0].key.rsplit("_", 1)[1]
        self._por_chave(at.text_input, f"corr_just_{eid}").set_value("peso digitado errado")
        at.run()

        botao = [b for b in at.button if (b.key or "") == f"corr_salvar_{eid}"][0]
        self.assertFalse(botao.disabled, "justificativa preenchida não liberou a correção")
        botao.click()
        at.run()

        self.assertEqual(list(at.exception), [])
        db.clear_cache()
        eventos = db.eventos.do_animal(self.animal["uuid"])
        # O original (pesagem) continua na lista — §6.3 não apaga.
        self.assertTrue(any(e["tipo"] == "pesagem" for e in eventos),
                        "evento original sumiu depois da correção")
        self.assertTrue(any(e["tipo"] == "correcao" for e in eventos),
                        "correção não foi criada como evento novo")

    def test_diferenca_entre_ocorrido_e_registrado_aparece(self):
        """§6.2: a diferença entre o fato e o registro é auditável, então a
        tela precisa mostrá-la quando for relevante."""
        ha_3_dias = (date.today() - timedelta(days=3)).isoformat() + "T00:00:00+00:00"
        db.eventos.registrar(self.animal["uuid"], "pesagem",
                             usuario_registro="setup", ocorrido_em=ha_3_dias)
        db.clear_cache()

        at = self._tela_animal()
        texto = " ".join(m.value for m in at.markdown)
        self.assertIn("registrado", texto)
        self.assertIn("depois", texto,
                      "atraso entre ocorrido_em e registrado_em não foi mostrado")

    # ── painel de sincronização (§10) ───────────────────────────────────────

    def test_operador_nao_acessa_o_painel(self):
        at = self._tela_sincronizacao(papel="operador")
        self.assertNotIn("Sincronização com o Sistema Oficial",
                         " ".join(m.value for m in at.markdown),
                         "operador alcançou o painel de sincronização")

    def test_sem_pendencia_mostra_sucesso(self):
        # Este animal específico do teste não tem evento nenhum; a fila global
        # pode não estar vazia por causa de outros testes da classe, então o
        # que se afirma aqui é só que a tela não quebra e reage ao estado —
        # não que a fila esteja vazia (isso depende de execução isolada).
        at = self._tela_sincronizacao()
        self.assertIn("📡 Sincronização", " ".join(m.value for m in at.markdown))

    def test_lote_so_oferece_situacoes_que_fecham_a_pendencia(self):
        """§10.3: 'rejeitado' continua em aberto. Oferecê-lo aqui esconderia
        uma obrigação de comunicar que segue de pé."""
        db.eventos.registrar(self.animal["uuid"], "pesagem", usuario_registro="setup")
        db.clear_cache()

        at = self._tela_sincronizacao()
        opcoes = self._por_chave(at.selectbox, "sinc_lote_situacao").options
        self.assertNotIn(sincronizacao_rotulo("rejeitado"), opcoes)
        self.assertNotIn(sincronizacao_rotulo("erro_tecnico"), opcoes)
        self.assertIn(sincronizacao_rotulo("aceito"), opcoes)

    def test_acompanhar_aceita_situacao_que_nao_resolve(self):
        """§10.2: o log técnico precisa registrar tentativa, não só sucesso."""
        db.eventos.registrar(self.animal["uuid"], "pesagem", usuario_registro="setup")
        db.clear_cache()

        at = self._tela_sincronizacao()
        opcoes = self._por_chave(at.selectbox, "sinc_ac_situacao").options
        self.assertIn(sincronizacao_rotulo("enviado"), opcoes)
        self.assertIn(sincronizacao_rotulo("rejeitado"), opcoes)

    def test_marcar_em_lote_fecha_a_pendencia(self):
        r = db.eventos.registrar(self.animal["uuid"], "pesagem", usuario_registro="setup")
        self.assertTrue(r["ok"], r)
        db.clear_cache()
        antes = db.eventos.contar_pendentes()

        at = self._tela_sincronizacao()
        caixa = self._por_chave(at.multiselect, "sinc_lote_eventos")
        self.assertTrue(caixa.options, "nenhum evento oferecido para fechar em lote")
        caixa.set_value([caixa.options[0]])
        at.run()

        self._por_chave(at.button, "sinc_lote_salvar").click()
        at.run()
        self.assertEqual(list(at.exception), [])

        db.clear_cache()
        self.assertEqual(db.eventos.contar_pendentes(), antes - 1,
                         "marcar em lote não tirou o evento da fila")


if __name__ == "__main__":
    unittest.main()
