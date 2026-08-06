"""O perímetro do piquete obedece à mesma disciplina da tela de propriedades?

`lotes.poligono` existe desde a migration 0015, que destravou
`services/lotacao.py::sobrepostos()` (specs 0028/0043) — a função existia desde a
etapa B, testada, e nunca teve como ser chamada de verdade: não havia onde o
piquete guardar o próprio desenho.

Estes testes travam as duas decisões que a tela precisa repetir do padrão já
estabelecido em Propriedades:

- **A área é calculada do desenho, nunca digitada** — mesma razão de sempre:
  área digitada e perímetro desenhado divergem com o tempo.
- **Sobreposição entre piquetes é avisada, não bloqueada.** Um piquete
  redesenhado sem apagar o anterior é situação real, não erro fatal — quem
  decide o que fazer é o pecuarista, olhando o mapa.

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

# Dois quadrados que se sobrepõem de verdade — mesma vizinhança de coordenadas
# usada nos testes de propriedades, para o overlap não depender de sorte de zona
# UTM (ver o defeito original da spec 0028, corrigido na PR #94).
QUADRADO_A = json.dumps({"type": "Polygon", "coordinates": [[
    [-51.2300, -30.0300], [-51.2280, -30.0300],
    [-51.2280, -30.0320], [-51.2300, -30.0320]]]})
QUADRADO_B = json.dumps({"type": "Polygon", "coordinates": [[
    [-51.2295, -30.0305], [-51.2275, -30.0305],
    [-51.2275, -30.0325], [-51.2295, -30.0325]]]})
QUADRADO_LONGE = json.dumps({"type": "Polygon", "coordinates": [[
    [-49.0000, -30.0300], [-48.9980, -30.0300],
    [-48.9980, -30.0320], [-49.0000, -30.0320]]]})


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestPerimetroDoLote(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_perimetro.db"))
        db.init_db()
        db.clear_cache()
        cls.lotes = db.get_all_lotes()
        assert len(cls.lotes) >= 2, "seed sem pelo menos 2 lotes"

    def setUp(self):
        for l in self.lotes:
            db.set_lote_poligono(l["id"], None)
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

    def test_a_aba_de_perimetro_existe_por_lote(self):
        at = self._tela()
        rotulos = [ex.label for ex in at.expander]
        self.assertTrue(any("Perímetro" in r for r in rotulos),
                        f"nenhum expander de perímetro encontrado: {rotulos}")

    def test_area_e_calculada_e_nao_digitada(self):
        lid = self.lotes[0]["id"]
        at = self._tela()
        self._por_chave(at.text_area, f"lote_poligono_{lid}").set_value(
            "-51.2300, -30.0300\n-51.2280, -30.0300\n-51.2280, -30.0320")
        at.run()

        campos = [(w.key or "") for w in at.number_input]
        for k in campos:
            self.assertNotIn("area", k.lower(),
                             f"tela ofereceu área digitável em '{k}'")
        rotulos = [m.label for m in at.metric]
        self.assertIn("Área do desenho", rotulos)

    def test_poligono_invalido_nao_salva(self):
        lid = self.lotes[0]["id"]
        at = self._tela()
        self._por_chave(at.text_area, f"lote_poligono_{lid}").set_value(
            "-51.23\n-30.03")  # linha sem par lon,lat
        at.run()

        self.assertTrue(list(at.error), "linha mal formada não foi recusada")
        self.assertTrue(
            self._por_chave(at.button, f"lote_poligono_salvar_{lid}").disabled,
            "tela deixou salvar um perímetro inválido")

    def test_salvar_grava_geojson_recuperavel(self):
        lid = self.lotes[0]["id"]
        at = self._tela()
        self._por_chave(at.text_area, f"lote_poligono_{lid}").set_value(
            "-51.2300, -30.0300\n-51.2280, -30.0300\n-51.2280, -30.0320")
        at.run()
        self._por_chave(at.button, f"lote_poligono_salvar_{lid}").click()
        at.run()

        db.clear_cache()
        salvo = db.get_lote(lid)["poligono"]
        g = json.loads(salvo)
        self.assertEqual(g["type"], "Polygon")
        self.assertEqual(len(g["coordinates"][0]), 3)

    def test_sobreposicao_avisa_sem_bloquear_a_pagina(self):
        """Piquete redesenhado sem apagar o anterior é situação real — a
        página continua funcionando, só avisa."""
        a, b = self.lotes[0]["id"], self.lotes[1]["id"]
        db.set_lote_poligono(a, QUADRADO_A)
        db.set_lote_poligono(b, QUADRADO_B)
        db.clear_cache()

        at = self._tela()
        self.assertEqual(list(at.exception), [])
        texto = " ".join(w.value for w in at.warning)
        self.assertIn("sobreposto", texto.lower())
        self.assertIn(a, texto)
        self.assertIn(b, texto)

    def test_piquetes_distantes_nao_disparam_aviso(self):
        """Mesmo defeito que a spec 0028 corrigiu: zona UTM diferente não pode
        virar falsa sobreposição."""
        a, b = self.lotes[0]["id"], self.lotes[1]["id"]
        db.set_lote_poligono(a, QUADRADO_A)
        db.set_lote_poligono(b, QUADRADO_LONGE)
        db.clear_cache()

        at = self._tela()
        self.assertEqual(list(at.warning), [],
                         "piquetes distantes foram acusados de sobreposição")

    def test_sem_nenhum_poligono_nao_ha_aviso(self):
        at = self._tela()
        self.assertEqual(list(at.warning), [])


if __name__ == "__main__":
    unittest.main()
