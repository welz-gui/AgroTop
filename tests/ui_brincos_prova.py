"""A tela de brincos obedece ao §5? (Fase B na interface)

A máquina de doze estados é `services/estados_dispositivo.py` e já está testada.
Estes testes travam as **decisões de interface** que o §5 impõe, e que não cabem
no service:

- **Estado definitivo não oferece saída.** Se a tela mostrar um destino para um
  brinco inutilizado, o operador tenta e leva erro — e pior, passa a acreditar
  que dá para reaproveitar o número.
- **`bloqueado_orgao` não é "sem opções": é bloqueio de terceiro.** A tela
  precisa dizer *quem* libera, senão o operador procura o botão que não existe.
- **Divergência visual × eletrônico avisa, não impede** (§5.3). Recusar travaria
  o trabalho no curral por um erro de leitura.
- **Troca de brinco exige motivo** (§4.2.3), perguntado antes de salvar.

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
class TestTelaBrincos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_brincos.db"))
        db.init_db()
        db.clear_cache()
        r = db.dispositivos.importar_lote("TAG0001", "TAG0010", lote="NF-TESTE",
                                          usuario="setup")
        assert r["ok"], r
        db.clear_cache()

    def _tela(self, **estado):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "brincos"
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

    def _botao(self, at, chave):
        return self._por_chave(at.button, chave)

    def _buscar(self, at, codigo):
        self._por_chave(at.text_input, "brc_busca").set_value(codigo)
        at.run()
        return at

    def _um_disponivel(self):
        return db.dispositivos.disponiveis(limite=1)[0]

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_pagina_existe_e_conta_o_estoque(self):
        at = self._tela()
        self.assertIn("🏷️ Brincos e Dispositivos",
                      " ".join(m.value for m in at.markdown))
        # Comparado com o inventário do momento, não com um número fixo: os
        # outros testes mudam estado de dispositivo, e um literal aqui passaria
        # ou falharia conforme a ordem em que o unittest os executa.
        esperado = str(db.dispositivos.inventario()["em_estoque"])
        valores = [m.value for m in at.metric]
        self.assertIn(esperado, valores,
                      f"estoque exibido não bateu com o inventário: {valores}")

    def test_operador_alcanca_a_pagina(self):
        """Aplicar brinco é trabalho de curral. Se o operador não entra, a tela
        existe para quem não usa."""
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 2, "username": "op1",
                                    "name": "Operador", "role": "operador"}
        at.session_state["page"] = "brincos"
        at.run()
        self.assertEqual(list(at.exception), [])
        self.assertIn("🏷️ Brincos e Dispositivos",
                      " ".join(m.value for m in at.markdown),
                      "operador foi redirecionado para fora da página de brincos")

    def test_estado_definitivo_nao_oferece_saida(self):
        """`inutilizado` é ato definitivo. Oferecer destino seria mentir."""
        d = self._um_disponivel()
        r = db.dispositivos.mudar_status(d["id"], "inutilizado",
                                         motivo="teste de refugo", usuario="op1")
        self.assertTrue(r["ok"], r)
        db.clear_cache()

        at = self._buscar(self._tela(), d["codigo_visual"])
        # Some da busca por código: o número não volta ao estoque.
        self.assertEqual([w for w in at.selectbox if (w.key or "") == "brc_novo"], [],
                         "tela ofereceu mudança de situação para um inutilizado")

    def test_bloqueio_do_orgao_diz_quem_libera(self):
        d = self._um_disponivel()
        r = db.dispositivos.mudar_status(d["id"], "bloqueado_orgao",
                                         motivo="ofício 123", usuario="op1")
        self.assertTrue(r["ok"], r)
        db.clear_cache()

        at = self._buscar(self._tela(), d["codigo_visual"])
        # Sair de bloqueado_orgao exige autorização, então não há destino livre.
        self.assertEqual([w for w in at.selectbox if (w.key or "") == "brc_novo"], [],
                         "tela ofereceu desbloqueio sem autorização do órgão")
        texto = " ".join(e.value for e in at.error)
        self.assertIn("órgão", texto,
                      f"tela não explicou quem libera; mostrou: {texto!r}")

    def test_mudanca_que_exige_motivo_trava_o_botao(self):
        """§5.2: sem motivo ninguém reconstrói por que um brinco pago virou refugo."""
        d = self._um_disponivel()
        at = self._buscar(self._tela(), d["codigo_visual"])

        caixa = self._por_chave(at.selectbox, "brc_novo")
        # `options` traz os rótulos já formatados — é o que o operador lê —,
        # mas a seleção usa o valor cru, que é o que chega ao repositório.
        self.assertIn("Perdido", caixa.options)
        caixa.set_value("perdido")
        at.run()

        self.assertTrue(self._botao(at, "brc_salvar").disabled,
                        "botão liberado sem motivo para uma perda")

        self._por_chave(at.text_input, "brc_motivo").set_value("caiu no pasto")
        at.run()
        self.assertFalse(self._botao(at, "brc_salvar").disabled,
                         "motivo preenchido não liberou o registro")

    def test_divergencia_avisa_mas_nao_impede(self):
        """§5.3: divergência de leitura é registrada, não bloqueia o curral.

        Escolhe a função `oficial` de propósito: todo animal do rebanho já tem
        um identificador de `manejo` (o próprio brinco de cadastro), e aplicar
        outro seria **troca**, que exige motivo pelo §4.2.3. O botão ficaria
        travado por esse motivo e o teste mediria a coisa errada.
        """
        at = self._tela()
        self._por_chave(at.selectbox, "brap_tipo").set_value("oficial")
        self._por_chave(at.text_input, "brap_lido").set_value("OUTRO999")
        at.run()

        self.assertTrue(list(at.warning), "divergência não foi avisada")
        self.assertFalse(self._botao(at, "brap_salvar").disabled,
                         "divergência bloqueou a aplicação — o §5.3 diz que não deve")

    def test_troca_de_brinco_exige_motivo(self):
        """§4.2.3: o identificador anterior é encerrado, não apagado — com motivo.

        Não precisa preparar nada: todo animal do rebanho já tem identificador
        de `manejo` desde o cadastro, então aplicar um dispositivo com essa
        função **é** troca. Foi o próprio repositório que recusou a preparação
        original deste teste, o que confirma a regra.
        """
        animal = db.get_all_animals(status="ativo")[0]
        d = self._um_disponivel()

        at = self._tela()
        caixa_d = self._por_chave(at.selectbox, "brap_disp")
        caixa_d.set_value([o for o in caixa_d.options
                           if o.startswith(d["codigo_visual"])][0])
        caixa_a = self._por_chave(at.selectbox, "brap_animal")
        caixa_a.set_value([o for o in caixa_a.options
                           if o.startswith(animal["id"])][0])
        at.run()

        self.assertTrue(self._botao(at, "brap_salvar").disabled,
                        "troca de brinco liberada sem motivo (§4.2.3)")
        self._por_chave(at.text_input, "brap_motivo").set_value("brinco ilegível")
        at.run()
        self.assertFalse(self._botao(at, "brap_salvar").disabled,
                         "motivo da substituição não liberou a aplicação")

    def test_importacao_exige_faixa_e_lote(self):
        at = self._tela()
        self.assertTrue(self._botao(at, "brimp_salvar").disabled,
                        "importação liberada sem faixa nem lote")

        for chave, valor in (("brimp_ini", "NOVO001"), ("brimp_fim", "NOVO003"),
                             ("brimp_lote", "NF-9")):
            self._por_chave(at.text_input, chave).set_value(valor)
        at.run()
        self.assertFalse(self._botao(at, "brimp_salvar").disabled)


if __name__ == "__main__":
    unittest.main()
