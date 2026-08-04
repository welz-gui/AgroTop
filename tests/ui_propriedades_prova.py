"""A tela de propriedades obedece ao §3? (Fase B na interface)

`repositories/propriedades.py` e `services/geometria.py` já estão testados. O
que estes testes travam são as decisões de interface:

- **O titular não é editável.** Trocar `produtor_id` é transferência de
  titularidade, que é evento do §8 com GTA e data. Oferecê-lo como campo de
  cadastro faria uma mudança regulatória parecer correção de digitação — e o
  repositório recusaria em silêncio, porque `atualizar()` ignora o campo.
- **A área é calculada, nunca digitada.** Área digitada e perímetro desenhado
  divergem com o tempo, e aí ninguém sabe qual dos dois vale.
- **Polígono inválido não é salvo.** `services/geometria.validar` sabe recusar;
  a tela precisa impedir antes de gravar, senão o GeoJSON entra torto.
- **Encerrar exige data.** Saber que o vínculo terminou sem saber quando não
  conta história nenhuma.

⚠️ **Não começa com `test_` de propósito** — ver `tests/ui_estados_prova.py`.
Quem executa isto é `tests/test_ui.py`, num subprocesso.
"""

import json
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

# Um quadrado pequeno perto de Porto Alegre. Área conhecida o bastante para o
# teste conferir a ordem de grandeza sem reimplementar a projeção.
QUADRADO = "-51.2300, -30.0300\n-51.2280, -30.0300\n-51.2280, -30.0320\n-51.2300, -30.0320"
# Gravata: os lados se cruzam. `geometria.validar` recusa.
CRUZADO = "-51.2300, -30.0300\n-51.2280, -30.0320\n-51.2280, -30.0300\n-51.2300, -30.0320"


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestTelaPropriedades(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_prop.db"))
        db.init_db()
        db.clear_cache()
        cls.prop = db.propriedades.padrao()
        assert cls.prop, "seed não criou propriedade"

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "propriedades"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def _por_chave(self, widgets, chave):
        achados = [w for w in widgets if (w.key or "") == chave]
        self.assertEqual(len(achados), 1,
                         f"esperava 1 widget com chave '{chave}', achei {len(achados)}")
        return achados[0]

    def _com_poligono(self, at, texto):
        self._por_chave(at.text_area, "prop_poligono").set_value(texto)
        at.run()
        return at

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_pagina_existe(self):
        at = self._tela()
        self.assertIn("🏞️ Propriedades",
                      " ".join(m.value for m in at.markdown))

    def test_operador_nao_entra(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 2, "username": "op1",
                                    "name": "Operador", "role": "operador"}
        at.session_state["page"] = "propriedades"
        at.run()
        self.assertEqual(list(at.exception), [])
        self.assertNotIn("🏞️ Propriedades",
                         " ".join(m.value for m in at.markdown),
                         "operador alcançou o cadastro de propriedades")

    def test_titular_nao_e_campo_editavel(self):
        """§8: mudar titular é transferência, não edição de cadastro.

        `atualizar()` já ignora `produtor_id`. Se a tela oferecesse o campo, o
        usuário mudaria, veria 'salvo' e nada teria mudado — o pior dos dois
        mundos.
        """
        at = self._tela()
        # Só os campos de EDIÇÃO (`prop_`). Na aba de criação (`propn_`) o
        # titular é escolhido de propósito — é lá que ele se define, e uma vez só.
        edicao = [(w.key or "") for w in at.selectbox] + \
                 [(w.key or "") for w in at.text_input]
        for k in edicao:
            if not k.startswith("prop_"):
                continue
            self.assertNotIn("produtor", k,
                             f"a tela de edição ofereceu o campo '{k}'")

        criacao = [(w.key or "") for w in at.selectbox]
        self.assertIn("propn_produtor", criacao,
                      "a criação precisa escolher o titular — é lá que ele se define")

    def test_area_e_calculada_e_nao_digitada(self):
        """Área digitada e perímetro desenhado divergem com o tempo."""
        at = self._com_poligono(self._tela(), QUADRADO)

        campos = [(w.key or "") for w in at.number_input] + \
                 [(w.key or "") for w in at.text_input]
        for k in campos:
            self.assertFalse("area" in k or "área" in k,
                             f"a tela ofereceu área digitável em '{k}'")

        rotulos = [m.label for m in at.metric]
        self.assertIn("Área", rotulos, f"área não foi calculada: {rotulos}")

    def test_poligono_invalido_nao_salva(self):
        """Gravata é polígono auto-interceptante — `geometria.validar` recusa."""
        at = self._com_poligono(self._tela(), CRUZADO)
        self.assertTrue(list(at.error), "polígono cruzado não foi recusado")
        self.assertTrue(self._por_chave(at.button, "prop_salvar").disabled,
                        "tela deixou salvar um polígono inválido")

    def test_coordenada_mal_formada_nao_salva(self):
        at = self._com_poligono(self._tela(), "-51.23\n-30.03")
        self.assertTrue(list(at.error), "linha sem par não foi recusada")
        self.assertTrue(self._por_chave(at.button, "prop_salvar").disabled)

    def test_encerrar_exige_data(self):
        at = self._tela()
        self._por_chave(at.selectbox, "prop_situacao").set_value("encerrada")
        at.run()

        self.assertTrue(self._por_chave(at.button, "prop_salvar").disabled,
                        "encerrou a propriedade sem data de encerramento")
        self._por_chave(at.text_input, "prop_encerramento").set_value("2026-08-04")
        at.run()
        self.assertFalse(self._por_chave(at.button, "prop_salvar").disabled)

    def test_salvar_grava_geojson_e_centro(self):
        """O que a tela mostra precisa ser o que ela grava."""
        at = self._com_poligono(self._tela(), QUADRADO)
        self._por_chave(at.button, "prop_salvar").click()
        at.run()

        p = db.propriedades.get(self.prop["id"])
        g = json.loads(p["poligono"])
        self.assertEqual(g["type"], "Polygon")
        self.assertEqual(len(g["coordinates"][0]), 4)
        self.assertIsNotNone(p["latitude"], "centroide não foi gravado")
        self.assertAlmostEqual(p["latitude"], -30.031, places=2)


if __name__ == "__main__":
    unittest.main()
