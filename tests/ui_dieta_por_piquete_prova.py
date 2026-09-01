"""O custo de dieta por piquete chegou à tela de verdade?

`services/dieta.py::custo_por_cabeca_dia` existia pura, testada, e nunca foi
chamada. A spec 0037 escreveu `services/dieta_adaptador.py
::ingredientes_por_cabeca`, a ponte entre `feeding_plans` (por piquete) e o
que `custo_por_cabeca_dia` espera (por cabeça); ligar isso é a aba
"💰 Custo por Piquete" de `page_nutricao`.

Estes testes travam o que a integração monta — nada disso é objeto da spec
0037 (que recebe `planos_do_piquete`/`insumos_por_id`/`cabecas_no_piquete`
já prontos por parâmetro), é trabalho do mantenedor (R31): buscar os planos
ativos de cada piquete, contar cabeças ativas nele, resolver os insumos
vinculados e converter unidade quando precisa (`db.convert_quantity`).

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
class TestDietaPorPiqueteNaTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_dieta.db"))
        db.init_db()
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                    "name": "Admin", "role": "admin"}
        at.session_state["page"] = "nutricao"
        at.run()
        self.assertEqual(list(at.exception), [],
                         f"app levantou exceção: {[e.value for e in at.exception]}")
        return at

    # ── testes ───────────────────────────────────────────────────────────────

    def test_a_aba_de_custo_por_piquete_existe(self):
        at = self._tela()
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Custo por Piquete" in r for r in rotulos),
                        f"nenhuma aba de custo por piquete encontrada: {rotulos}")

    def test_tela_nao_quebra_sem_plano_nenhum(self):
        """Banco recém-criado não tem feeding_plans — a aba precisa avisar
        isso, não estourar (nt4 roda incondicionalmente)."""
        self._tela()  # já falha em setUp/_tela se houver exceção

    def test_cadeia_completa_com_dados_reais_do_banco(self):
        """Reproduz a mesma cadeia que `_nutricao_custo_por_piquete` monta:
        insumo → plano de trato → animal no piquete → custo por cabeça."""
        from services.dieta_adaptador import ingredientes_por_cabeca
        from services.dieta import custo_por_cabeca_dia

        lote = db.get_all_lotes()[0]
        db.add_new_insumo(db.InsumoCreate("Ração Prova Dieta", "racao", "kg", 500.0, 50.0, 2.0))
        db.clear_cache()
        insumo = next(i for i in db.get_all_insumos()
                      if i["name"] == "Ração Prova Dieta")
        db.add_feeding_plan(lote["id"], "Ração Prova Dieta", 40.0, "kg", "diario",
                            insumo_id=insumo["id"])
        db.clear_cache()
        entrada = (date.today() - timedelta(days=60)).isoformat()
        db.add_animal("DIETA1", "Nelore", "M", None, entrada,
                      300.0, 500.0, 1000.0, lote["id"], None)
        db.clear_cache()

        insumos_por_id = {i["id"]: i for i in db.get_all_insumos()}
        planos = db.get_feeding_plans(lote_id=lote["id"], active_only=True)
        cabecas = len(db.get_all_animals(status="ativo", lote_id=lote["id"]))
        self.assertGreaterEqual(cabecas, 1)

        ingredientes = ingredientes_por_cabeca(
            planos, insumos_por_id, cabecas, converter_quantidade=db.convert_quantity)
        self.assertTrue(ingredientes, "nenhum ingrediente resolvido — plano/insumo não bateu")

        resultado = custo_por_cabeca_dia(ingredientes)
        # 40 kg/dia de ração a R$2/kg, dividido pelas cabeças do piquete
        esperado_por_cabeca = 40.0 * 2.0 / cabecas
        self.assertAlmostEqual(resultado["custo_dia"], round(esperado_por_cabeca, 2), places=2)
        self.assertTrue(resultado["participacao"])

    def test_piquete_sem_animais_nao_quebra(self):
        """Plano ativo num piquete vazio — a aba precisa avisar, não dividir
        por zero nem estourar."""
        lotes = db.get_all_lotes()
        vazio = next((l for l in lotes
                     if not db.get_all_animals(status="ativo", lote_id=l["id"])), None)
        if vazio is None:
            db.add_lote("PVAZIO", "Piquete vazio de prova", 5.0, 10.0)
            db.clear_cache()
            vazio = db.get_all_lotes()[-1]

        db.add_feeding_plan(vazio["id"], "Sal mineral", 5.0, "kg", "diario")
        db.clear_cache()

        at = self._tela()  # não pode estourar
        rotulos = [t.label for t in at.tabs]
        self.assertTrue(any("Custo por Piquete" in r for r in rotulos))


if __name__ == "__main__":
    unittest.main()
