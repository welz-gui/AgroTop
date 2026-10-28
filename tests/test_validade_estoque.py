"""Lote e validade por entrada de estoque (plano de rastreabilidade, Fase 2).

O alerta "medicamento vencendo" precisa saber de quais entradas é feito o saldo de hoje. O
sistema não guarda o que sobrou de cada lote, então a divisão é uma estimativa com regra
explícita (PEPS; lote informado na aplicação sai do lote): estes testes fixam essa regra.
"""

import unittest
from datetime import timedelta

import database as db
from repositories import compras
from repositories.sanidade import MedicationData, add_medication
from services.recomendacoes import avaliar
from services.validade_estoque import (
    LoteInvalido, lotes_do_insumo, normalizar_lote_entrada, situacao,
)
from tests.test_regras_negocio import BaseRegras, HOJE


def _dia(n):
    return (HOJE + timedelta(days=n)).isoformat()


def _e(id_, data, qtd, lote=None, validade=None):
    return {"id": id_, "data": data, "quantidade": qtd, "lote": lote, "validade": validade}


class TestNormalizarLoteEntrada(unittest.TestCase):
    def test_sem_lote_e_sem_validade_e_valido(self):
        self.assertEqual(normalizar_lote_entrada("", "", _dia(0)),
                         {"lote_produto": "", "validade_produto": ""})

    def test_normaliza_espacos_e_aceita_validade_do_proprio_dia(self):
        r = normalizar_lote_entrada("  L2410   A ", _dia(0), _dia(0))
        self.assertEqual(r, {"lote_produto": "L2410 A", "validade_produto": _dia(0)})

    def test_produto_que_chegou_vencido_e_recusado(self):
        with self.assertRaisesRegex(LoteInvalido, "já chegou vencido"):
            normalizar_lote_entrada("L1", _dia(-1), _dia(0))

    def test_validade_em_formato_invalido(self):
        for ruim in ("01/02/2027", "2027-13-01", "amanhã"):
            with self.assertRaises(LoteInvalido):
                normalizar_lote_entrada("", ruim, _dia(0))

    def test_lote_longo_demais(self):
        with self.assertRaises(LoteInvalido):
            normalizar_lote_entrada("x" * 61, "", _dia(0))


class TestSituacao(unittest.TestCase):
    def test_classifica_pela_validade(self):
        h = HOJE
        self.assertEqual(situacao(None, h), "sem_validade")
        self.assertEqual(situacao(_dia(-1), h), "vencido")
        self.assertEqual(situacao(_dia(0), h), "vencendo", "vence no dia: ainda vale, mas é urgente")
        self.assertEqual(situacao(_dia(30), h), "vencendo")
        self.assertEqual(situacao(_dia(31), h), "ok")
        self.assertEqual(situacao(_dia(10), h, dias=5), "ok")


class TestLotesDoInsumo(unittest.TestCase):
    def test_sem_consumo_todas_as_entradas_restam(self):
        r = lotes_do_insumo([_e(1, "2026-01-01", 100, "A"), _e(2, "2026-02-01", 50, "B")],
                            saldo=150, saidas_liquidas=0, consumo_por_lote={})
        self.assertEqual([(x["lote"], x["restante"]) for x in r], [("A", 100), ("B", 50)])

    def test_consumo_sem_lote_sai_da_entrada_mais_antiga_peps(self):
        r = lotes_do_insumo([_e(1, "2026-01-01", 100, "A"), _e(2, "2026-02-01", 50, "B")],
                            saldo=90, saidas_liquidas=60, consumo_por_lote={})
        self.assertEqual([(x["lote"], x["restante"]) for x in r], [("A", 40), ("B", 50)])

    def test_consumo_alem_da_primeira_entrada_passa_para_a_seguinte(self):
        r = lotes_do_insumo([_e(1, "2026-01-01", 100, "A"), _e(2, "2026-02-01", 50, "B")],
                            saldo=30, saidas_liquidas=120, consumo_por_lote={})
        self.assertEqual([(x["lote"], x["restante"]) for x in r], [("B", 30)])

    def test_lote_informado_na_aplicacao_sai_desse_lote_mesmo_sendo_o_mais_novo(self):
        # 70 do lote B foram aplicados com o lote anotado; o resto do consumo (10) é PEPS.
        r = lotes_do_insumo([_e(1, "2026-01-01", 100, "A"), _e(2, "2026-02-01", 100, "B")],
                            saldo=120, saidas_liquidas=80, consumo_por_lote={"B": 70})
        self.assertEqual([(x["lote"], x["restante"]) for x in r], [("A", 90), ("B", 30)])

    def test_saldo_anterior_ao_controle_de_lotes_e_consumido_primeiro(self):
        # 40 já existiam sem entrada registrada; entrou 100 do lote A; saíram 30 (sem lote).
        r = lotes_do_insumo([_e(1, "2026-01-01", 100, "A")], saldo=110, saidas_liquidas=30,
                            consumo_por_lote={})
        self.assertEqual([(x["lote"], x["restante"]) for x in r], [(None, 10), ("A", 100)])
        self.assertIsNone(r[0]["entrada_id"])
        self.assertIsNone(r[0]["validade"])

    def test_a_soma_do_que_resta_fecha_com_o_saldo(self):
        entradas = [_e(1, "2026-01-01", 100, "A", "2026-06-01"), _e(2, "2026-02-01", 60, "B"),
                    _e(3, "2026-03-01", 40, "C", "2027-01-01")]
        for saidas, explicito in ((0, {}), (75, {}), (75, {"C": 30}), (180, {"B": 20}), (200, {})):
            saldo = 20 + 200 - saidas          # 20 de saldo anterior + 200 de entradas
            r = lotes_do_insumo(entradas, saldo, saidas, explicito)
            self.assertAlmostEqual(sum(x["restante"] for x in r), max(0.0, saldo), places=6,
                                   msg=f"saidas={saidas} explicito={explicito}")

    def test_lote_informado_que_nao_existe_nas_entradas_cai_no_peps(self):
        r = lotes_do_insumo([_e(1, "2026-01-01", 100, "A")], saldo=70, saidas_liquidas=30,
                            consumo_por_lote={"LOTE-FANTASMA": 30})
        self.assertEqual([(x["lote"], x["restante"]) for x in r], [("A", 70)])

    def test_estorno_deixa_a_saida_liquida_menor(self):
        # 30 aplicados e 30 estornados: saída líquida zero, nada foi consumido.
        r = lotes_do_insumo([_e(1, "2026-01-01", 100, "A")], saldo=100, saidas_liquidas=0,
                            consumo_por_lote={})
        self.assertEqual([(x["lote"], x["restante"]) for x in r], [("A", 100)])


class TestEntradaDeEstoque(BaseRegras):
    def setUp(self):
        super().setUp()
        db.add_new_insumo(db.InsumoCreate("Ivermectina 1%", "medicamento", "ml", 0.0, 10.0, 0.5))
        with db._conn() as con:
            self.insumo = con.execute("SELECT id FROM insumos WHERE name='Ivermectina 1%'").fetchone()["id"]
        self.animal("A1")

    def _entradas(self):
        with db._conn() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM insumo_transactions WHERE insumo_id=? AND type='entrada' ORDER BY id",
                (self.insumo,)).fetchall()]

    def _aplicar(self, dose, lote=""):
        add_medication(MedicationData(
            animal_id="A1", medication_name="Ivermectina 1%", dose=dose, unit="ml",
            application_route="Subcutânea", withdrawal_days=0, med_date=_dia(0), applied_by="op",
            insumo_id=self.insumo, lote_produto=lote))
        db.clear_cache()

    def _restantes(self):
        db.clear_cache()
        return [(x["lote"], x["restante"]) for x in db.lotes_em_estoque_por_insumo().get(self.insumo, [])]

    # ── captura ──────────────────────────────────────────────────────────────
    def test_entrada_guarda_lote_e_validade(self):
        db.add_insumo_entry(self.insumo, 100.0, 0.5, "ana", "L2410A", _dia(120))
        e = self._entradas()[0]
        self.assertEqual((e["lote_produto"], e["validade_produto"]), ("L2410A", _dia(120)))

    def test_entrada_sem_lote_nem_validade_fica_nula(self):
        db.add_insumo_entry(self.insumo, 100.0, 0.5, "ana")
        e = self._entradas()[0]
        self.assertEqual((e["lote_produto"], e["validade_produto"]), (None, None))

    def test_entrada_de_produto_vencido_e_recusada_e_nao_grava_nada(self):
        with self.assertRaises(LoteInvalido):
            db.add_insumo_entry(self.insumo, 100.0, 0.5, "ana", "L1", _dia(-1))
        self.assertEqual(self._entradas(), [])
        with db._conn() as con:
            self.assertEqual(con.execute("SELECT current_stock FROM insumos WHERE id=?",
                                         (self.insumo,)).fetchone()[0], 0.0)

    def test_compra_com_nota_guarda_lote_e_validade_por_item(self):
        r = compras.registrar(compras.NovaCompra(
            data_emissao=_dia(0), data_recebimento=_dia(0), primeiro_vencimento=_dia(30),
            itens=[{"insumo_id": self.insumo, "quantidade": 100.0, "custo_unitario": 0.5,
                    "lote": "NF-77", "validade": _dia(200)}]))
        self.assertTrue(r["ok"], r)
        e = self._entradas()[0]
        self.assertEqual((e["lote_produto"], e["validade_produto"]), ("NF-77", _dia(200)))

    def test_compra_de_produto_vencido_e_recusada_inteira(self):
        r = compras.registrar(compras.NovaCompra(
            data_emissao=_dia(0), data_recebimento=_dia(0), primeiro_vencimento=_dia(30),
            itens=[{"insumo_id": self.insumo, "quantidade": 100.0, "custo_unitario": 0.5,
                    "lote": "VELHO", "validade": _dia(-5)}]))
        self.assertFalse(r["ok"])
        self.assertIn("vencido", r["erro"])
        self.assertEqual(self._entradas(), [])

    # ── divisão do saldo por lote ────────────────────────────────────────────
    def test_lotes_em_estoque_apos_consumo_com_e_sem_lote_informado(self):
        db.add_insumo_entry(self.insumo, 100.0, 0.5, "ana", "A", _dia(10))
        db.add_insumo_entry(self.insumo, 100.0, 0.5, "ana", "B", _dia(200))
        self._aplicar(30.0, lote="B")       # do B, anotado
        self._aplicar(20.0)                 # sem lote: sai do A (PEPS)
        self.assertEqual(self._restantes(), [("A", 80.0), ("B", 70.0)])

    def test_aplicacao_cancelada_devolve_o_saldo_ao_lote(self):
        from repositories.sanidade import cancelar_medicamento, get_medication_history
        db.add_insumo_entry(self.insumo, 100.0, 0.5, "ana", "A", _dia(10))
        self._aplicar(40.0, lote="A")
        self.assertEqual(self._restantes(), [("A", 60.0)])
        mid = get_medication_history("A1")[0]["id"]
        cancelar_medicamento(mid, "erro", "ana")
        self.assertEqual(self._restantes(), [("A", 100.0)])

    def test_insumo_sem_saldo_nao_aparece(self):
        self.assertEqual(db.lotes_em_estoque_por_insumo(), {})

    # ── alerta ───────────────────────────────────────────────────────────────
    def test_alertas_de_validade_listam_vencidos_e_vencendo_do_mais_urgente_ao_menos(self):
        # Entrada vencida só chega por dado antigo: grava direto, como se tivesse vencido depois.
        db.add_insumo_entry(self.insumo, 50.0, 0.5, "ana", "ANTIGO", _dia(0))
        with db._conn() as con:
            con.execute("UPDATE insumo_transactions SET validade_produto=? WHERE lote_produto='ANTIGO'",
                        (_dia(-3),))
        db.add_insumo_entry(self.insumo, 50.0, 0.5, "ana", "PERTO", _dia(12))
        db.add_insumo_entry(self.insumo, 50.0, 0.5, "ana", "LONGE", _dia(300))
        db.clear_cache()

        a = db.alertas_de_validade()

        self.assertEqual([(x["lote"], x["situacao"], x["dias"]) for x in a],
                         [("ANTIGO", "vencido", -3), ("PERTO", "vencendo", 12)])
        self.assertEqual(a[0]["nome"], "Ivermectina 1%")
        self.assertEqual(a[0]["restante"], 50.0)

    def test_lote_ja_consumido_inteiro_nao_gera_alerta(self):
        db.add_insumo_entry(self.insumo, 50.0, 0.5, "ana", "PERTO", _dia(5))
        self._aplicar(50.0, lote="PERTO")
        self.assertEqual(db.alertas_de_validade(), [])

    def test_recomendacao_de_validade_entra_no_contexto_e_no_motor(self):
        db.add_insumo_entry(self.insumo, 50.0, 0.5, "ana", "PERTO", _dia(5))
        db.clear_cache()
        recs = [r for r in avaliar(db.contexto_recomendacoes()) if r["regra"] == "validade_estoque"]
        self.assertEqual(len(recs), 1)
        self.assertEqual((recs[0]["severidade"], recs[0]["dados"]["lote"], recs[0]["dados"]["dias"]),
                         ("media", "PERTO", 5))


class TestRegraDeValidade(unittest.TestCase):
    def _ctx(self, validade, restante=10.0, lote="L1"):
        return {"hoje": HOJE.isoformat(), "lotes_estoque": [
            {"insumo_id": 1, "nome": "Vacina", "unidade": "dose", "lote": lote,
             "validade": validade, "restante": restante}]}

    def _regra(self, ctx):
        return [r for r in avaliar(ctx) if r["regra"] == "validade_estoque"]

    def test_vencido_e_alta_vencendo_e_media_longe_nao_alerta(self):
        self.assertEqual(self._regra(self._ctx(_dia(-1)))[0]["severidade"], "alta")
        self.assertEqual(self._regra(self._ctx(_dia(30)))[0]["severidade"], "media")
        self.assertEqual(self._regra(self._ctx(_dia(31))), [])

    def test_sem_validade_ou_sem_saldo_nao_alerta(self):
        self.assertEqual(self._regra(self._ctx(None)), [])
        self.assertEqual(self._regra(self._ctx(_dia(1), restante=0.0)), [])

    def test_lote_sem_identificacao_e_dito_assim(self):
        r = self._regra(self._ctx(_dia(2), lote=None))[0]
        self.assertIn("sem identificação", r["motivo"])

    def test_contexto_sem_a_chave_nao_quebra(self):
        self.assertEqual(self._regra({"hoje": HOJE.isoformat()}), [])
        self.assertEqual(self._regra({"lotes_estoque": "x"}), [])


if __name__ == "__main__":
    unittest.main()
