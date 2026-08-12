"""A reconciliação de lote de brincos chegou à tela de verdade?

`services/reconciliacao_dispositivos.py::reconciliar` (spec 0033) existia
pura e testada, mas sem consumidor: a única importação em `page_brincos`
era por faixa numérica contígua (`db.dispositivos.importar_lote`), que não
serve para um arquivo de fornecedor com códigos arbitrários. Ligar isso
exigiu duas peças novas em `repositories/dispositivos.py` — que não são
objeto desta spec, são trabalho do mantenedor (R31):

- `codigos_em_estoque()` — {codigo_visual: status} de **todo** dispositivo,
  em qualquer situação (inclusive as três terminais), porque é isso que
  `reconciliar()` precisa para nunca duplicar um código.
- `importar_arquivo()` — grava só o que `reconciliar()` aprovou.

Estes testes travam o que a integração acrescentou:

- **Código já cadastrado, em qualquer situação, não vira um segundo registro**
  — nem quando já está `inutilizado` (o caso que `por_codigo` sozinho não
  pegaria, porque ele ignora os estados terminais de propósito).
- **Reimportar o mesmo arquivo é idempotente**: a segunda vez não duplica.

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

CSV_DUAS_NOVAS = "codigo_visual;tipo\nBRPROVA001;brinco_visual\nBRPROVA002;brinco_visual\n"


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestReconciliacaoDeBrincosNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_reconc_brincos.db"))
        db.init_db()
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "brincos"
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

    def test_a_aba_de_importar_arquivo_existe(self):
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Importar arquivo" in r for r in rotulos),
                        f"nenhuma aba de importar arquivo encontrada: {rotulos}")

    def test_codigo_ja_inutilizado_nao_duplica(self):
        """por_codigo() ignora estados terminais de propósito (não é para
        reaplicar um número descartado) — mas `codigos_em_estoque()`, que
        alimenta `reconciliar()`, não pode herdar essa cegueira: um código
        inutilizado que reaparece no arquivo do fornecedor é erro do
        fornecedor, não motivo para virar um segundo registro (§4.2.1)."""
        db.dispositivos.importar_lote("ZZ001", "ZZ001", lote="prova-antiga")
        db.clear_cache()
        d = db.dispositivos.por_codigo("ZZ001")
        r = db.dispositivos.mudar_status(d["id"], "inutilizado", motivo="teste")
        self.assertTrue(r.get("ok"), r)
        db.clear_cache()

        # por_codigo() de propósito não encontra mais — é a garantia que
        # existe hoje.
        self.assertIsNone(db.dispositivos.por_codigo("ZZ001"))

        # codigos_em_estoque() precisa enxergar mesmo assim, senão
        # reconciliar() deixaria "ZZ001" virar um segundo registro.
        codigos = db.dispositivos.codigos_em_estoque()
        self.assertEqual(codigos.get("ZZ001"), "inutilizado")

        from services.reconciliacao_dispositivos import reconciliar
        resultado = reconciliar([{"codigo_visual": "ZZ001"}], codigos)
        self.assertEqual(resultado["para_gravar"], [],
                         "código inutilizado foi oferecido para gravar de novo")
        self.assertEqual(resultado["ja_existentes"][0]["status_atual"], "inutilizado")

    def test_reconciliacao_nao_duplica_nem_na_segunda_importacao(self):
        codigos_antes = db.dispositivos.codigos_em_estoque()
        r = db.dispositivos.importar_arquivo(
            [{"codigo_visual": "BRPROVA001", "tipo": "brinco_visual"}],
            lote="prova-1")
        self.assertTrue(r["ok"])
        self.assertEqual(r["criados"], 1)
        db.clear_cache()

        codigos = db.dispositivos.codigos_em_estoque()
        self.assertIn("BRPROVA001", codigos)
        self.assertNotIn("BRPROVA001", codigos_antes)

        # reconciliar contra o estoque atual não deve oferecer o mesmo código
        from services.reconciliacao_dispositivos import reconciliar
        resultado = reconciliar(
            [{"codigo_visual": "BRPROVA001", "tipo": "brinco_visual"}], codigos)
        self.assertEqual(resultado["para_gravar"], [])
        self.assertEqual(len(resultado["ja_existentes"]), 1)


if __name__ == "__main__":
    unittest.main()
