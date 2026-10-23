"""Correção de tratamento por revisão (plano de rastreabilidade, Fase 2).

Aplicação registrada errada não é apagada nem editada: cancela-se ou corrige-se criando
outra que aponta para ela, com motivo e autor. A linha cancelada permanece no histórico e
sai de tudo que olha a situação vigente (carência, alertas, venda).
"""

import unittest
from datetime import timedelta

import database as db
from repositories import eventos
from repositories.animais import get_animal
from repositories.sanidade import (
    AplicacaoJaCancelada, AplicacaoNaoEncontrada, MedicationData,
    add_medication, cancelar_medicamento, corrigir_medicamento,
    get_medication_history, get_medications, get_withdrawal_end,
)
from services.tratamento import TratamentoInvalido
from tests.test_regras_negocio import BaseRegras, HOJE


def _hoje():
    return HOJE.isoformat()


class TestCorrecaoDeTratamento(BaseRegras):
    def setUp(self):
        super().setUp()
        self.animal("A1")
        with db._conn() as con:
            self.uuid = con.execute("SELECT uuid FROM animals WHERE id='A1'").fetchone()["uuid"]
        db.add_new_insumo(db.InsumoCreate("Ivermectina 1%", "medicamento", "ml", 100.0, 10.0, 0.5))
        with db._conn() as con:
            self.insumo = con.execute("SELECT id FROM insumos WHERE name='Ivermectina 1%'").fetchone()["id"]

    def _dados(self, **kw):
        base = dict(animal_id="A1", medication_name="Ivermectina 1%", dose=5.0, unit="ml",
                    application_route="Subcutânea", withdrawal_days=28, med_date=_hoje(),
                    applied_by="op", insumo_id=self.insumo, lote_produto="L1")
        base.update(kw)
        return MedicationData(**base)

    def _aplicar(self, **kw):
        add_medication(self._dados(**kw))
        db.clear_cache()
        return get_medication_history("A1")[0]

    def _estoque(self):
        with db._conn() as con:
            return con.execute("SELECT current_stock FROM insumos WHERE id=?", (self.insumo,)).fetchone()[0]

    def _status(self):
        db.clear_cache()
        return get_animal("A1")["status"]

    def _eventos(self):
        return sorted(eventos.do_animal(self.uuid), key=lambda e: e["id"])

    # ── a aplicação nova ganha o vínculo com o evento ────────────────────────
    def test_aplicacao_guarda_o_id_do_evento(self):
        m = self._aplicar()
        ev = [e for e in self._eventos() if e["tipo"] == "manejo_sanitario"]
        self.assertEqual(m["evento_id"], ev[0]["id"])
        self.assertIsNone(m["cancelada_em"])
        self.assertIsNone(m["corrige_id"])

    # ── cancelar ─────────────────────────────────────────────────────────────
    def test_cancelar_mantem_a_linha_e_a_tira_da_situacao_vigente(self):
        m = self._aplicar()
        self.assertIsNotNone(get_withdrawal_end("A1"))

        r = cancelar_medicamento(m["id"], "  lançada no animal errado ", "ana")

        self.assertEqual(r["cancelada"], m["id"])
        db.clear_cache()
        self.assertEqual(get_medications("A1"), [])
        self.assertIsNone(get_withdrawal_end("A1"))
        hist = get_medication_history("A1")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["cancelada_por"], "ana")
        self.assertEqual(hist[0]["motivo_cancelamento"], "lançada no animal errado")
        self.assertTrue(hist[0]["cancelada_em"])

    def test_cancelar_exige_motivo_e_nao_grava_nada(self):
        m = self._aplicar()
        antes = len(self._eventos())
        for vazio in ("", "   ", None):
            with self.assertRaises(TratamentoInvalido):
                cancelar_medicamento(m["id"], vazio, "ana")
        db.clear_cache()
        self.assertEqual(len(get_medications("A1")), 1)
        self.assertEqual(len(self._eventos()), antes)

    def test_cancelar_duas_vezes_recusa_a_segunda(self):
        m = self._aplicar()
        cancelar_medicamento(m["id"], "erro", "ana")
        with self.assertRaises(AplicacaoJaCancelada):
            cancelar_medicamento(m["id"], "erro de novo", "ana")

    def test_cancelar_aplicacao_inexistente(self):
        with self.assertRaises(AplicacaoNaoEncontrada):
            cancelar_medicamento(99999, "erro", "ana")

    def test_cancelar_grava_evento_estorno_apontando_para_o_original(self):
        m = self._aplicar()
        cancelar_medicamento(m["id"], "dose errada", "ana")
        evs = self._eventos()
        original, estorno = evs[0], evs[-1]
        self.assertEqual(original["tipo"], "manejo_sanitario")
        self.assertEqual(estorno["tipo"], "estorno")
        self.assertEqual(estorno["evento_anterior_id"], original["id"])
        self.assertEqual(estorno["versao"], 2)
        self.assertEqual(estorno["justificativa"], "dose errada")
        self.assertEqual(estorno["usuario_registro"], "ana")

    def test_cancelar_audita_com_o_registro_anterior(self):
        m = self._aplicar()
        cancelar_medicamento(m["id"], "dose errada", "ana")
        t = [x for x in eventos.trilha(entidade="medications", entidade_id=str(m["id"]))
             if x["acao"] == "cancelar_aplicacao"]
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0]["usuario"], "ana")
        self.assertEqual(t[0]["motivo"], "dose errada")
        self.assertEqual(t[0]["registro_anterior"]["medication_name"], "Ivermectina 1%")

    def test_cancelar_devolve_o_estoque_e_zera_o_custo_liquido(self):
        m = self._aplicar()
        self.assertEqual(self._estoque(), 95.0)
        cancelar_medicamento(m["id"], "erro", "ana")
        self.assertEqual(self._estoque(), 100.0)
        with db._conn() as con:
            liquido = con.execute(
                "SELECT SUM(quantity) FROM insumo_transactions WHERE insumo_id=? AND type='saida' "
                "AND reason='uso_animal'", (self.insumo,)).fetchone()[0]
        self.assertEqual(liquido, 0.0, "a saída e o estorno se anulam nas somas por motivo")

    def test_cancelar_a_unica_carencia_devolve_o_animal_a_ativo(self):
        m = self._aplicar()
        self.assertEqual(self._status(), "carencia")
        cancelar_medicamento(m["id"], "erro", "ana")
        self.assertEqual(self._status(), "ativo")

    def test_cancelar_uma_de_duas_carencias_mantem_a_outra_e_o_status(self):
        self._aplicar(withdrawal_days=10)
        longa = self._aplicar(withdrawal_days=40)
        cancelar_medicamento(longa["id"], "erro", "ana")
        db.clear_cache()
        fim = get_withdrawal_end("A1")
        self.assertEqual(fim, HOJE + timedelta(days=10))
        self.assertEqual(self._status(), "carencia")

    def test_cancelar_aplicacao_antiga_sem_evento_nao_quebra(self):
        m = self._aplicar()
        with db._conn() as con:
            con.execute("UPDATE medications SET evento_id=NULL WHERE id=?", (m["id"],))
        cancelar_medicamento(m["id"], "erro", "ana")
        estorno = self._eventos()[-1]
        self.assertEqual(estorno["tipo"], "estorno")
        self.assertIsNone(estorno["evento_anterior_id"])
        self.assertEqual(estorno["versao"], 2)

    # ── corrigir ─────────────────────────────────────────────────────────────
    def test_corrigir_cria_a_certa_ligada_a_original(self):
        m = self._aplicar(dose=50.0)
        r = corrigir_medicamento(
            m["id"], self._dados(dose=5.0, lote_produto="L2"), "dose digitada com zero a mais", "ana")

        self.assertEqual(r["cancelada"], m["id"])
        db.clear_cache()
        vigentes = get_medications("A1")
        self.assertEqual([x["id"] for x in vigentes], [r["nova"]])
        self.assertEqual(vigentes[0]["dose"], 5.0)
        self.assertEqual(vigentes[0]["corrige_id"], m["id"])
        self.assertEqual(vigentes[0]["lote_produto"], "L2")
        self.assertEqual(len(get_medication_history("A1")), 2)

    def test_corrigir_encadeia_o_evento_novo_ao_original(self):
        m = self._aplicar()
        r = corrigir_medicamento(m["id"], self._dados(dose=4.0), "dose errada", "ana")
        evs = [e for e in self._eventos() if e["tipo"] == "manejo_sanitario"]
        self.assertEqual(len(evs), 2)
        self.assertEqual(evs[1]["evento_anterior_id"], evs[0]["id"])
        self.assertEqual(evs[1]["versao"], 2)
        self.assertEqual(evs[1]["justificativa"], "dose errada")
        nova = [x for x in get_medication_history("A1") if x["id"] == r["nova"]][0]
        self.assertEqual(nova["evento_id"], evs[1]["id"])

    def test_corrigir_acerta_o_estoque_e_a_carencia(self):
        m = self._aplicar(dose=50.0, withdrawal_days=40)
        self.assertEqual(self._estoque(), 50.0)
        corrigir_medicamento(m["id"], self._dados(dose=5.0, withdrawal_days=14), "erro", "ana")
        self.assertEqual(self._estoque(), 95.0)
        db.clear_cache()
        self.assertEqual(get_withdrawal_end("A1"), HOJE + timedelta(days=14))
        self.assertEqual(self._status(), "carencia")

    def test_corrigir_para_sem_carencia_devolve_o_animal_a_ativo(self):
        m = self._aplicar(withdrawal_days=28)
        corrigir_medicamento(m["id"], self._dados(withdrawal_days=0), "não tinha carência", "ana")
        self.assertEqual(self._status(), "ativo")

    def test_corrigir_produto_vencido_recusa_e_nao_cancela_a_original(self):
        m = self._aplicar()
        antes = len(self._eventos())
        vencido = (HOJE - timedelta(days=1)).isoformat()
        with self.assertRaises(TratamentoInvalido):
            corrigir_medicamento(m["id"], self._dados(validade_produto=vencido), "erro", "ana")
        db.clear_cache()
        self.assertEqual([x["id"] for x in get_medications("A1")], [m["id"]])
        self.assertEqual(self._estoque(), 95.0)
        self.assertEqual(len(self._eventos()), antes)

    def test_corrigir_nao_troca_o_animal(self):
        self.animal("A2")
        m = self._aplicar()
        with self.assertRaises(AplicacaoNaoEncontrada):
            corrigir_medicamento(m["id"], self._dados(animal_id="A2"), "animal errado", "ana")
        db.clear_cache()
        self.assertEqual(len(get_medications("A1")), 1)
        self.assertEqual(get_medications("A2"), [])

    def test_corrigir_exige_motivo(self):
        m = self._aplicar()
        with self.assertRaises(TratamentoInvalido):
            corrigir_medicamento(m["id"], self._dados(), "  ", "ana")

    def test_corrigir_a_ja_corrigida_recusa(self):
        m = self._aplicar()
        corrigir_medicamento(m["id"], self._dados(dose=4.0), "erro", "ana")
        with self.assertRaises(AplicacaoJaCancelada):
            corrigir_medicamento(m["id"], self._dados(dose=3.0), "erro", "ana")

    def test_corrigir_a_correcao_forma_cadeia(self):
        m = self._aplicar()
        r1 = corrigir_medicamento(m["id"], self._dados(dose=4.0), "erro 1", "ana")
        r2 = corrigir_medicamento(r1["nova"], self._dados(dose=3.0), "erro 2", "ana")
        evs = [e for e in self._eventos() if e["tipo"] == "manejo_sanitario"]
        self.assertEqual([e["versao"] for e in evs], [1, 2, 3])
        self.assertEqual(evs[2]["evento_anterior_id"], evs[1]["id"])
        db.clear_cache()
        self.assertEqual([x["id"] for x in get_medications("A1")], [r2["nova"]])

    # ── os leitores que não passam por get_medications ───────────────────────
    def test_venda_para_abate_deixa_de_ser_bloqueada_apos_cancelar(self):
        from repositories.financeiro import VendaBloqueadaPorCarencia, _recusar_abate_em_carencia
        m = self._aplicar()
        with db._conn() as con:
            with self.assertRaises(VendaBloqueadaPorCarencia):
                _recusar_abate_em_carencia(con, ("A1",), _hoje())
        cancelar_medicamento(m["id"], "erro", "ana")
        with db._conn() as con:
            _recusar_abate_em_carencia(con, ("A1",), _hoje())      # não levanta


if __name__ == "__main__":
    unittest.main()
