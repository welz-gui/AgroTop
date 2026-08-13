"""O escore de conformidade PNIB chegou à tela de verdade?

`services/conformidade.py::avaliar` existia pura, testada, e nunca foi
chamada. A spec 0036 escreveu `services/conformidade_adaptador.py
::montar_rebanho`, a ponte entre `animals`/`animal_identifiers`/
`dispositivos`/fila de sincronização/`movimentacoes` e o que `avaliar`
espera; ligar isso é a seção "🛡️ Conformidade PNIB" no Dashboard.

Estes testes travam o que a integração monta — nada disso é objeto da spec
0036 (que recebe as cinco fontes já prontas por parâmetro), é trabalho do
mantenedor (R31):

- **`repositories/dispositivos.py::com_divergencia` é peça nova**: nenhuma
  função existente devolvia `{animal_uuid, divergencia}` de todo
  dispositivo aplicado — só agregados por status (`inventario()`) sem o
  uuid, ou por código único (`por_codigo()`). Sem ela, toda divergência
  visual×eletrônico desapareceria da dimensão "Sem divergência de
  dispositivo".
- **A regra "antes de 2033" não pode virar pendência crítica por engano**:
  isso já é comportamento de `services/conformidade.py` (testado em
  `tests/test_conformidade.py`), mas só se prova de verdade quando a data
  de referência real (`date.today()`) é passada — não uma fixture.

⚠️ **Não começa com `test_` de propósito** — ver `tests/ui_estados_prova.py`.
Quem executa isto é `tests/test_ui.py`, num subprocesso.
"""

import os
import sys
import tempfile
import unittest
from datetime import date

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestConformidadeNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_conformidade.db"))
        db.init_db()
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "dashboard"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def _cadeia(self):
        """Reproduz exatamente o que `_dash_conformidade()` monta."""
        from services.conformidade_adaptador import montar_rebanho
        from services.conformidade import avaliar

        animais = db.get_all_animals(status=None)
        identificadores_ativos = [
            item for itens in db.identificadores._por_animal().values()
            for item in itens if item.get("status") == "ativo"
        ]
        dispositivos = db.dispositivos.com_divergencia()
        eventos_pendentes = db.eventos.contar_pendentes()
        movimentacoes_abertas = db.movimentacoes.abertas()
        referencia = date.today().isoformat()

        rebanho = montar_rebanho(
            animais=animais, identificadores_ativos=identificadores_ativos,
            dispositivos=dispositivos, eventos_pendentes=eventos_pendentes,
            movimentacoes_abertas=movimentacoes_abertas, referencia=referencia)
        return avaliar(rebanho, referencia)

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_secao_de_conformidade_existe(self):
        at = self._tela()
        rotulos = [ex.label for ex in at.expander]
        self.assertTrue(any("Conformidade PNIB" in r for r in rotulos),
                        f"nenhum expander de conformidade encontrado: {rotulos}")

    def test_tela_nao_quebra_e_mostra_escore(self):
        at = self._tela()
        rotulo = next(ex.label for ex in at.expander if "Conformidade PNIB" in ex.label)
        self.assertRegex(rotulo, r"\d+[.,]\d/100",
                         f"escore não apareceu no rótulo: {rotulo}")

    def test_antes_de_2033_falta_de_id_oficial_nao_e_pendencia_critica(self):
        """A data de referência real (hoje, 2026) precisa chegar certa no
        adaptador — se caísse em None ou numa data errada, a regra do prazo
        (services/conformidade.py, já testada em unidade) não teria como
        agir, e a ausência de identificação oficial (esperada até 2033)
        viraria pendência crítica por engano."""
        resultado = self._cadeia()
        self.assertEqual(resultado["prazo_relevante"], "2033-01-01")
        mensagens_criticas = " ".join(resultado["pendencias_criticas"])
        self.assertNotIn("identificação oficial", mensagens_criticas)

    def test_divergencia_de_dispositivo_aparece_na_dimensao_certa(self):
        """Prova a peça nova (com_divergencia): sem ela, a dimensão nunca
        veria uma divergência real."""
        aid = db.get_all_animals(status="ativo")[0]["id"]
        animal = db.get_animal(aid)
        db.dispositivos.importar_lote("DVCONF001", "DVCONF001", lote="prova-conformidade")
        db.clear_cache()
        d = db.dispositivos.por_codigo("DVCONF001")
        # tipo_identificador="rfid": o animal seedado já tem um "manejo"
        # vigente (o próprio brinco), e aplicar outro ali exigiria
        # motivo_substituicao (§4.2.3) — rfid evita essa colisão de propósito.
        r = db.dispositivos.aplicar(d["id"], animal["uuid"],
                                    tipo_identificador="rfid",
                                    eletronico_lido="000000000000000")
        self.assertTrue(r.get("ok"), r)
        self.assertTrue(r["divergencia"], "aplicação não gerou divergência de teste")
        db.clear_cache()

        divergentes = db.dispositivos.com_divergencia()
        self.assertTrue(
            any(dv["animal_uuid"] == animal["uuid"] for dv in divergentes),
            "divergência criada não apareceu em com_divergencia()")

        resultado = self._cadeia()
        dimensao = next(d for d in resultado["dimensoes"]
                        if d["nome"] == "Sem divergência de dispositivo")
        self.assertGreaterEqual(dimensao["faltam"], 1)


if __name__ == "__main__":
    unittest.main()
