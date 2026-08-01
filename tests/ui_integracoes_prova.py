"""As três funções puras que faltavam chegaram mesmo à interface?

`identificadores`, `validacao_regulatoria` e `recomendacoes` ficaram prontas e
ligadas a nada por dias. Estes testes travam a **ligação** — que a tela chama a
função, e que o resultado dela aparece.

⚠️ **Não começa com `test_` de propósito** — ver `tests/ui_estados_prova.py`
para o motivo (conflito do runtime do `AppTest` com a suíte grande). Quem
executa isto é `tests/test_ui.py`, num subprocesso.
"""

import os
import sqlite3
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
class BaseTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_int.db"))
        db.init_db()
        db.clear_cache()

    def _tela(self, pagina, **estado):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = pagina
        for k, v in estado.items():
            at.session_state[k] = v
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção em '{pagina}': "
                         f"{[e.value for e in at.exception]}")
        return at

    def _ativo(self):
        return db.get_all_animals(status="ativo")[0]

    def _por_chave(self, widgets, chave):
        """Localiza widget pela `key`, não pelo rótulo.

        A ficha do animal tem **dois** selectbox rotulados "Tipo" — o de
        identificador e o de tipo de custo. Buscar por rótulo pega o errado e o
        erro aparece longe daqui, como `ValueError` dentro do próprio AppTest.
        """
        achados = [w for w in widgets if (w.key or "").startswith(chave)]
        self.assertEqual(len(achados), 1,
                         f"esperava 1 widget com chave '{chave}', achei {len(achados)}")
        return achados[0]

    def _sql(self, sql, args=()):
        con = sqlite3.connect(db.DB_PATH)
        try:
            con.execute(sql, args)
            con.commit()
        finally:
            con.close()
        db.clear_cache()


class TestRecomendacoes(BaseTela):
    def test_pagina_de_alertas_tem_a_secao(self):
        at = self._tela("alertas")
        self.assertIn("🧭 Recomendações", [s.value for s in at.subheader])

    def test_estoque_curto_vira_recomendacao_na_tela(self):
        """Prova a corrente inteira: plano de trato → consumo diário → regra → tela.

        Sem isto, `_consumo_diario_por_insumo` poderia devolver zero para tudo e
        a seção apareceria sempre vazia, sem ninguém notar.
        """
        insumo = db.get_all_insumos()[0]
        lote = db.get_all_lotes()[0]
        # Consumo alto o bastante para o saldo não cobrir 15 dias.
        diario = max(float(insumo["current_stock"]) / 5.0, 1.0)
        db.add_feeding_plan(lote["id"], "Trato de teste", diario,
                            insumo["unit"], "diario", insumo_id=insumo["id"])
        db.clear_cache()

        at = self._tela("alertas")
        textos = " ".join(m.value or "" for m in at.markdown)
        self.assertIn(insumo["name"], textos,
                      "a recomendação de estoque não chegou à tela")


class TestIdentificadores(BaseTela):
    def test_ficha_tem_a_aba(self):
        at = self._tela("animal", animal_detail=self._ativo()["id"])
        self.assertIn("🏷️ Identificadores", [t.label for t in at.tabs])

    def _preencher(self, at, valor):
        self._por_chave(at.selectbox, "id_tipo_").set_value("rfid")
        self._por_chave(at.text_input, "id_valor_").set_value(valor)
        at.run()
        return self._por_chave(at.button, "id_aplicar_")

    def test_formato_invalido_trava_o_botao(self):
        """`rfid` exige 15 dígitos — a validação é `services/identificadores.py`."""
        at = self._tela("animal", animal_detail=self._ativo()["id"])
        botao = self._preencher(at, "123")
        self.assertTrue(botao.disabled, "botão liberado com rfid de 3 dígitos")
        self.assertTrue(list(at.error), "nenhum erro de formato foi mostrado")

    def test_formato_valido_libera_o_botao(self):
        at = self._tela("animal", animal_detail=self._ativo()["id"])
        botao = self._preencher(at, "123456789012345")
        self.assertFalse(botao.disabled,
                         "botão travado com rfid de 15 dígitos, que é válido")


class TestConsistencia(BaseTela):
    def test_nascimento_no_futuro_aparece_na_ficha(self):
        a = self._ativo()
        self._sql("UPDATE animals SET birth_date='2030-01-01' WHERE id=?", (a["id"],))
        at = self._tela("animal", animal_detail=a["id"])
        textos = " ".join((e.label or "") for e in at.expander)
        self.assertIn("inconsistência", textos.casefold(),
                      "a checagem do §17.3 não apareceu para nascimento futuro")

    def test_animal_consistente_nao_mostra_aviso(self):
        a = self._ativo()
        self._sql("UPDATE animals SET birth_date='2023-01-01', birth_estimated=0 "
                  "WHERE id=?", (a["id"],))
        at = self._tela("animal", animal_detail=a["id"])
        textos = " ".join((e.label or "") for e in at.expander)
        self.assertNotIn("inconsistência", textos.casefold(),
                         "avisou inconsistência num animal consistente")


if __name__ == "__main__":
    unittest.main()
