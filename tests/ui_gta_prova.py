"""A conferência da GTA física chegou à tela de verdade?

`services/gta.py::validar` existia pura e testada — a última das onze
services órfãs do ROADMAP. A spec 0038 escreveu
`services/gta_adaptador.py::montar_contexto`, a ponte a partir de uma
movimentação real; ligar isso é o expander "📄 Conferir a GTA física (§8)"
na fila de movimentações "Em andamento".

A própria spec avisou: `movimentacoes` não guarda `emissao`/`validade`/
`quantidade_declarada` do papel — só o `gta_numero`. A decisão de onde
coletar isso ficou para o mantenedor (R31); a escolhida foi **não
persistir**: o operador digita o que está escrito no papel na hora de
conferir. Estes testes travam o que essa integração monta:

- **`animais_em_carencia_uuids` não vem pronto** — resolvido cruzando
  `get_withdrawal_end_batch` com "hoje", o mesmo padrão já usado em
  `page_desempenho`.
- **Datas ausentes não inventam checagem** — sem marcar a caixa "Tenho a
  data", `gta.validar()` não pode acusar "vencida" nem "futura" por um
  valor que o operador nunca informou.

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
class TestConferirGtaNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_gta.db"))
        db.init_db()
        db.clear_cache()

        # A tela exige duas propriedades — mesma pré-condição de
        # ui_movimentacao_prova.py.
        cls.origem = db.propriedades.padrao()
        cls.destino_id = db.propriedades.criar_propriedade(
            cls.origem["produtor_id"], "Fazenda Destino GTA")
        db.clear_cache()
        cls.animais = [a for a in db.get_all_animals(status="ativo")
                       if a.get("property_id") == cls.origem["id"]][:2]
        assert len(cls.animais) >= 2, "seed sem animais na propriedade padrão"

    def setUp(self):
        with db._conn() as con:
            con.execute("DELETE FROM movimentacao_animais")
            con.execute("DELETE FROM movimentacoes")
            con.execute("UPDATE animals SET property_id=?", (self.origem["id"],))
        db.clear_cache()

    def _rascunho(self, **campos):
        campos.setdefault("propriedade_origem_id", self.origem["id"])
        campos.setdefault("propriedade_destino_id", self.destino_id)
        campos.setdefault("animais", [a["uuid"] for a in self.animais])
        campos.setdefault("data_prevista", date.today().isoformat())
        r = db.movimentacoes.criar(campos.pop("tipo", "venda"),
                                   usuario="setup", **campos)
        self.assertTrue(r["ok"], r)
        db.clear_cache()
        return r["id"]

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "movimentacao"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    def _cadeia(self, mov, dados_do_documento, animais_no_embarque_uuids=None,
               animais_em_carencia_uuids=None, hoje=None):
        """Reproduz exatamente o que `_mov_conferir_gta` monta."""
        from services.gta_adaptador import montar_contexto
        from services.gta import validar

        props = db.propriedades.listar()
        rot = {p["id"]: p["nome"] for p in props}
        movimentacao_ctx = {
            "gta_numero": mov.get("gta_numero"),
            "propriedade_origem_nome": rot.get(mov.get("propriedade_origem_id")),
            "propriedade_destino_nome": rot.get(mov.get("propriedade_destino_id")),
            "finalidade": mov.get("finalidade"),
            "animais_uuids": [a["animal_uuid"] for a in mov["animais"]],
        }
        hoje = hoje or date.today().isoformat()
        embarque = (animais_no_embarque_uuids
                   if animais_no_embarque_uuids is not None
                   else movimentacao_ctx["animais_uuids"])
        carencia = animais_em_carencia_uuids or []
        gta, contexto = montar_contexto(movimentacao_ctx, dados_do_documento,
                                        embarque, carencia, hoje)
        return validar(gta, contexto)

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_secao_de_conferir_gta_existe(self):
        self._rascunho(gta_numero="GTA-0001")
        at = self._tela()
        rotulos = [ex.label for ex in at.expander]
        self.assertTrue(any("Conferir a GTA física" in r for r in rotulos),
                        f"nenhum expander de conferência de GTA encontrado: {rotulos}")

    def test_tela_nao_quebra_sem_nenhum_dado_do_documento(self):
        self._rascunho(gta_numero="")
        self._tela()  # já falha em setUp/_tela se houver exceção

    def test_gta_vencida_e_detectada(self):
        mid = self._rascunho(gta_numero="GTA-0002")
        mov = db.movimentacoes.get(mid)
        ontem = (date.today() - timedelta(days=1)).isoformat()
        problemas = self._cadeia(mov, {"emissao": None, "validade": ontem,
                                       "quantidade_declarada": None})
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("gta_vencida", codigos, f"não acusou vencida: {problemas}")

    def test_data_ausente_nao_inventa_checagem(self):
        """Sem marcar 'tenho a data', emissao/validade chegam None — e
        gta.validar() não pode acusar vencida/futura sobre dado que não
        existe."""
        mid = self._rascunho(gta_numero="GTA-0003")
        mov = db.movimentacoes.get(mid)
        problemas = self._cadeia(mov, {"emissao": None, "validade": None,
                                       "quantidade_declarada": None})
        codigos = [p["codigo"] for p in problemas]
        self.assertNotIn("gta_vencida", codigos)
        self.assertNotIn("gta_futura", codigos)
        self.assertNotIn("quantidade_divergente", codigos)

    def test_quantidade_divergente_e_detectada(self):
        mid = self._rascunho(gta_numero="GTA-0004")
        mov = db.movimentacoes.get(mid)
        errada = len(mov["animais"]) + 5
        problemas = self._cadeia(mov, {"emissao": None, "validade": None,
                                       "quantidade_declarada": errada})
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("quantidade_divergente", codigos, f"{problemas}")

    def test_carencia_resolvida_via_withdrawal_end_batch(self):
        """Peça nova (R31): animais_em_carencia_uuids não vem pronto — a
        integração cruza get_withdrawal_end_batch com hoje."""
        mid = self._rascunho(gta_numero="GTA-0005", finalidade="abate")
        mov = db.movimentacoes.get(mid)
        aid_carencia = mov["animais"][0]["brinco"]
        db.add_medication(aid_carencia, "Ivermectina", 5.0, "ml", "Subcutânea",
                          30, date.today().isoformat())
        db.clear_cache()

        wd_batch = db.get_withdrawal_end_batch(
            [a["brinco"] for a in mov["animais"] if a["brinco"]])
        hoje = date.today()
        em_carencia_uuids = [
            a["animal_uuid"] for a in mov["animais"]
            if a["brinco"] and wd_batch.get(a["brinco"])
            and wd_batch[a["brinco"]] > hoje
        ]
        self.assertTrue(em_carencia_uuids, "carência não foi resolvida")

        problemas = self._cadeia(
            mov, {"emissao": None, "validade": None, "quantidade_declarada": None},
            animais_em_carencia_uuids=em_carencia_uuids)
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("animal_em_carencia", codigos, f"{problemas}")


if __name__ == "__main__":
    unittest.main()
