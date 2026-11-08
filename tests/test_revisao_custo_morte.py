"""Revisão de custo (de animal e fixo) e de óbito (plano de rastreabilidade, Fase 2).

Mesmo desenho do tratamento, da pesagem e da movimentação: o registro errado não é apagado nem
editado; é cancelado ou substituído por outro que aponta para ele, com motivo e autor. A linha
cancelada permanece e sai de tudo que soma ou conta (custo por animal, custo fixo, DRE, mortalidade).
"""

import sqlite3
from datetime import timedelta

import database as db
from repositories import eventos
from repositories.animais import get_animal
from repositories.revisao import RegistroJaCancelado, RegistroNaoEncontrado, RevisaoNaoPermitida
from tests.test_regras_negocio import BaseRegras, HOJE


def _dia(n):
    return (HOJE - timedelta(days=n)).isoformat()


class TestRevisaoCustoDeAnimal(BaseRegras):
    def setUp(self):
        super().setUp()
        self.animal("A1")
        self.animal("A2")
        db.add_animal_cost(db.AnimalCostData("A1", "operacional", "Vermífugo", 100.0, _dia(5)))
        db.add_animal_cost(db.AnimalCostData("A1", "compra", "Compra", 900.0, _dia(60)))
        db.clear_cache()
        self.custo = [c for c in db.get_animal_costs("A1") if c["description"] == "Vermífugo"][0]["id"]

    def _total(self):
        db.clear_cache()
        return db.get_total_cost("A1")

    def test_cancelar_tira_o_custo_de_todas_as_somas_e_mantem_a_linha(self):
        db.cancelar_custo_animal(self.custo, "valor lançado errado", "Maria", animal_id="A1")

        self.assertEqual(self._total(), 900.0)
        self.assertEqual([c["description"] for c in db.get_animal_costs("A1")], ["Compra"])
        self.assertEqual([c["description"] for c in db.get_all_animal_costs()], ["Compra"])
        todos = db.get_animal_costs("A1", incluir_canceladas=True)
        cancelado = [c for c in todos if c["id"] == self.custo][0]
        self.assertEqual((cancelado["cancelada_por"], cancelado["motivo_cancelamento"]),
                         ("Maria", "valor lançado errado"))
        self.assertEqual(db.get_financial_summary()["saidas_total"], 900.0)

    def test_cancelar_deixa_a_trilha_com_a_linha_original(self):
        db.cancelar_custo_animal(self.custo, "duplicado", "Maria")

        (t,) = eventos.trilha(entidade="animal_costs", entidade_id=str(self.custo))
        self.assertEqual((t["acao"], t["usuario"], t["motivo"]), ("cancelar_custo_animal", "Maria", "duplicado"))
        self.assertEqual(t["registro_anterior"]["amount"], 100.0)

    def test_sem_motivo_nada_muda(self):
        with self.assertRaises(RevisaoNaoPermitida):
            db.cancelar_custo_animal(self.custo, "   ", "Maria")
        self.assertEqual(self._total(), 1000.0)
        self.assertEqual(eventos.trilha(entidade="animal_costs"), [])

    def test_nao_se_cancela_duas_vezes(self):
        db.cancelar_custo_animal(self.custo, "engano", "Maria")
        with self.assertRaises(RegistroJaCancelado):
            db.cancelar_custo_animal(self.custo, "de novo", "Maria")

    def test_custo_de_outro_animal_ou_inexistente_nao_existe_para_ele(self):
        with self.assertRaises(RegistroNaoEncontrado):
            db.cancelar_custo_animal(self.custo, "engano", "Maria", animal_id="A2")
        with self.assertRaises(RegistroNaoEncontrado):
            db.cancelar_custo_animal(999, "engano", "Maria")
        self.assertEqual(self._total(), 1000.0)

    def test_corrigir_cancela_o_original_e_grava_o_certo_ligado_a_ele(self):
        r = db.corrigir_custo_animal(
            self.custo, db.AnimalCostData("A1", "operacional", "Vermífugo", 10.0, _dia(5)),
            "vírgula no lugar errado", "Maria")

        self.assertEqual(self._total(), 910.0)
        todos = db.get_animal_costs("A1", incluir_canceladas=True)
        nova = [c for c in todos if c["id"] == r["nova"]][0]
        self.assertEqual((nova["amount"], nova["corrige_id"], nova["cancelada_em"]), (10.0, self.custo, None))
        self.assertTrue([c for c in todos if c["id"] == self.custo][0]["cancelada_em"])
        t = eventos.trilha(entidade="animal_costs", entidade_id=str(self.custo))[0]
        self.assertEqual((t["acao"], t["registro_posterior"]["valor"]), ("corrigir_custo_animal", 10.0))

    def test_corrigir_nao_muda_de_animal(self):
        with self.assertRaises(RegistroNaoEncontrado):
            db.corrigir_custo_animal(
                self.custo, db.AnimalCostData("A2", "operacional", "x", 1.0, _dia(1)), "engano", "Maria")
        self.assertEqual(self._total(), 1000.0)

    def test_custo_cancelado_nao_entra_no_custo_por_piquete(self):
        self._sql("UPDATE animals SET lote_id='P01' WHERE id='A1'")
        antes = db.get_animal_costs_by_lote().get("P01", 0)
        db.cancelar_custo_animal(self.custo, "engano", "Maria")
        db.clear_cache()
        self.assertEqual(antes - db.get_animal_costs_by_lote().get("P01", 0), 100.0)


class TestRevisaoCustoFixo(BaseRegras):
    def setUp(self):
        super().setUp()
        con = sqlite3.connect(db.DB_PATH)
        try:
            prop = con.execute("SELECT id FROM properties LIMIT 1").fetchone()[0]
        finally:
            con.close()
        self._sql("INSERT INTO lotes (id,name,property_id) VALUES('P01','Piquete 1',?)", (prop,))
        db.add_fixed_cost(db.FixedCostData("Salários", "Gerente", 1500.0, _dia(3), 1))
        db.add_fixed_cost(db.FixedCostData("Impostos", "ITR", 400.0, _dia(3), 0, lote_id="P01"))
        self.salario = [c for c in db.get_fixed_costs() if c["category"] == "Salários"][0]["id"]

    def test_cancelar_tira_das_somas_e_mantem_a_linha(self):
        db.cancelar_custo_fixo(self.salario, "lançado duas vezes", "Maria")

        self.assertEqual(db.get_total_fixed_costs(), 400.0)
        self.assertEqual([c["category"] for c in db.get_fixed_costs()], ["Impostos"])
        self.assertEqual({c["category"]: c["total"] for c in db.get_fixed_costs_by_category()},
                         {"Impostos": 400.0})
        self.assertEqual(db.get_fixed_costs_by_lote().get(None, 0), 0)
        todos = db.get_fixed_costs(incluir_canceladas=True)
        self.assertEqual(len(todos), 2)
        self.assertEqual([c["motivo_cancelamento"] for c in todos if c["id"] == self.salario],
                         ["lançado duas vezes"])
        self.assertEqual(db.get_financial_summary()["saidas_total"], 400.0)

    def test_cancelar_deixa_a_trilha_e_exige_motivo(self):
        with self.assertRaises(RevisaoNaoPermitida):
            db.cancelar_custo_fixo(self.salario, "", "Maria")
        self.assertEqual(db.get_total_fixed_costs(), 1900.0)

        db.cancelar_custo_fixo(self.salario, "engano", "Maria")

        (t,) = eventos.trilha(entidade="fixed_costs", entidade_id=str(self.salario))
        self.assertEqual((t["acao"], t["usuario"]), ("cancelar_custo_fixo", "Maria"))
        self.assertEqual(t["registro_anterior"]["description"], "Gerente")

    def test_nao_se_cancela_duas_vezes_nem_o_que_nao_existe(self):
        db.cancelar_custo_fixo(self.salario, "engano", "Maria")
        with self.assertRaises(RegistroJaCancelado):
            db.cancelar_custo_fixo(self.salario, "de novo", "Maria")
        with self.assertRaises(RegistroNaoEncontrado):
            db.cancelar_custo_fixo(999, "engano", "Maria")

    def test_corrigir_grava_o_certo_ligado_ao_original(self):
        r = db.corrigir_custo_fixo(
            self.salario, db.FixedCostData("Salários", "Gerente", 1800.0, _dia(3), 1), "reajuste", "Maria")

        self.assertEqual(db.get_total_fixed_costs(), 2200.0)
        nova = [c for c in db.get_fixed_costs(incluir_canceladas=True) if c["id"] == r["nova"]][0]
        self.assertEqual((nova["amount"], nova["corrige_id"], nova["recurring"]), (1800.0, self.salario, 1))


class TestRevisaoDeObito(BaseRegras):
    def setUp(self):
        super().setUp()
        self.animal("A1", peso=420.0)
        self.uuid = self._uuid("A1")
        db.add_animal_cost(db.AnimalCostData("A1", "compra", "Compra", 900.0, _dia(60)))
        db.clear_cache()
        db.register_death("A1", _dia(2), "Picada de cobra", operator="Joao", notes="piquete norte")
        db.clear_cache()
        self.morte = db.get_morte_vigente("A1")["id"]

    def _status(self):
        db.clear_cache()
        return get_animal("A1")["status"]

    def _eventos(self, tipo=None):
        return [e for e in sorted(eventos.do_animal(self.uuid), key=lambda e: e["id"])
                if tipo is None or e["tipo"] == tipo]

    def test_o_obito_guarda_o_id_do_evento(self):
        self.assertIsNotNone(db.get_morte_vigente("A1")["evento_id"])
        self.assertEqual(self._status(), "morto")

    def test_cancelar_devolve_o_animal_ao_rebanho_e_tira_da_mortalidade(self):
        self.assertEqual(db.get_mortality_stats()["n_deaths"], 1)

        r = db.cancelar_morte(self.morte, "animal estava vivo", "Maria", animal_id="A1")

        self.assertEqual((r["animal_id"], r["status"]), ("A1", "ativo"))
        self.assertEqual(self._status(), "ativo")
        self.assertEqual(db.get_deaths(), [])
        self.assertEqual(db.get_mortality_stats()["n_deaths"], 0)
        self.assertEqual(db.get_financial_summary()["perda_mortalidade"], 0)
        self.assertIsNone(db.get_morte_vigente("A1"))
        cancelada = db.get_deaths(incluir_canceladas=True)[0]
        self.assertEqual((cancelada["cancelada_por"], cancelada["motivo_cancelamento"]),
                         ("Maria", "animal estava vivo"))

    def test_cancelar_grava_o_estorno_ligado_ao_evento_original_e_a_trilha(self):
        original = self._eventos("morte")[0]

        db.cancelar_morte(self.morte, "animal estava vivo", "Maria")

        (estorno,) = self._eventos("estorno")
        self.assertEqual((estorno["evento_anterior_id"], estorno["versao"]), (original["id"], 2))
        (t,) = eventos.trilha(entidade="deaths", entidade_id=str(self.morte))
        self.assertEqual((t["acao"], t["usuario"]), ("cancelar_obito", "Maria"))
        self.assertEqual(t["registro_anterior"]["cause"], "Picada de cobra")

    def test_cancelar_com_carencia_vigente_volta_como_carencia(self):
        self._sql("INSERT INTO medications (animal_uuid,medication_name,med_date,withdrawal_days) "
                  "VALUES(?,?,?,?)", (self.uuid, "Ivermectina", _dia(1), 30))

        r = db.cancelar_morte(self.morte, "animal estava vivo", "Maria")

        self.assertEqual(r["status"], "carencia")
        self.assertEqual(self._status(), "carencia")

    def test_sem_motivo_duas_vezes_ou_inexistente_nada_muda(self):
        with self.assertRaises(RevisaoNaoPermitida):
            db.cancelar_morte(self.morte, " ", "Maria")
        with self.assertRaises(RegistroNaoEncontrado):
            db.cancelar_morte(999, "engano", "Maria")
        self.assertEqual(self._status(), "morto")

        db.cancelar_morte(self.morte, "engano", "Maria")
        with self.assertRaises(RegistroJaCancelado):
            db.cancelar_morte(self.morte, "de novo", "Maria")

    def test_corrigir_troca_data_e_causa_e_o_animal_continua_morto(self):
        original = self._eventos("morte")[0]

        r = db.corrigir_morte(self.morte, _dia(4), "Timpanismo", "causa errada", "Maria", notes="corrigido")

        self.assertEqual(self._status(), "morto")
        (vigente,) = db.get_deaths()
        self.assertEqual((vigente["id"], vigente["cause"], vigente["death_date"], vigente["corrige_id"]),
                         (r["nova"], "Timpanismo", _dia(4), self.morte))
        self.assertEqual(vigente["cost_at_death"], 900.0, "o custo no óbito é o do registro original")
        self.assertEqual(db.get_mortality_stats()["n_deaths"], 1)
        novo = [e for e in self._eventos("morte") if e["id"] != original["id"]][0]
        self.assertEqual((novo["evento_anterior_id"], novo["versao"]), (original["id"], 2))
        self.assertEqual(vigente["evento_id"], novo["id"])
        self.assertEqual(len(db.get_deaths(incluir_canceladas=True)), 2)

    def test_corrigir_sem_motivo_nada_muda(self):
        with self.assertRaises(RevisaoNaoPermitida):
            db.corrigir_morte(self.morte, _dia(4), "Timpanismo", "", "Maria")
        self.assertEqual(db.get_deaths()[0]["cause"], "Picada de cobra")
