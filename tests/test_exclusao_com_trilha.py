"""Excluir custo fixo e protocolo deixa a linha apagada na trilha de auditoria (plano, Fase 1).

Eram as duas últimas exclusões de registro de negócio sem rastro. Id inexistente continua sendo
um no-op e não gera trilha.
"""

import database as db
from repositories import eventos
from tests.test_regras_negocio import BaseRegras


class TestExclusaoComTrilha(BaseRegras):
    def _custo(self):
        db.add_fixed_cost(db.FixedCostData(
            category="Salários", description="Gerente", amount=1500.5, cost_date="2026-10-01",
            recurring=1))
        return db.get_fixed_costs()[0]["id"]

    def _protocolo(self):
        db.add_protocol(db.ProtocolData(
            name="Aftosa", sex_target="ambos", age_min=0, age_max=36, dose_value=2.0,
            dose_ref_kg=1.0, dose_unit="ml", insumo_id=None, frequency="semestral",
            withdrawal_days=0))
        return db.get_protocols(active_only=False)[0]["id"]

    def test_custo_fixo_apagado_fica_na_trilha_com_a_linha_e_o_autor(self):
        cid = self._custo()

        db.delete_fixed_cost(cid, usuario="Maria")

        self.assertEqual(db.get_fixed_costs(), [])
        (t,) = eventos.trilha(entidade="fixed_costs", entidade_id=str(cid))
        self.assertEqual((t["acao"], t["usuario"]), ("excluir_custo_fixo", "Maria"))
        antes = t["registro_anterior"]
        self.assertEqual((antes["description"], antes["amount"], antes["category"]),
                         ("Gerente", 1500.5, "Salários"))

    def test_protocolo_apagado_fica_na_trilha_com_a_linha_e_o_autor(self):
        pid = self._protocolo()

        db.delete_protocol(pid, usuario="Maria")

        self.assertEqual(db.get_protocols(active_only=False), [])
        (t,) = eventos.trilha(entidade="health_protocols", entidade_id=str(pid))
        self.assertEqual((t["acao"], t["usuario"]), ("excluir_protocolo", "Maria"))
        self.assertEqual(t["registro_anterior"]["name"], "Aftosa")

    def test_id_inexistente_nao_faz_nada_nem_gera_trilha(self):
        db.delete_fixed_cost(999, usuario="Maria")
        db.delete_protocol(999, usuario="Maria")

        self.assertEqual(eventos.trilha(entidade="fixed_costs"), [])
        self.assertEqual(eventos.trilha(entidade="health_protocols"), [])

    def test_o_usuario_e_opcional_e_a_exclusao_continua_auditada(self):
        cid = self._custo()

        db.delete_fixed_cost(cid)

        (t,) = eventos.trilha(entidade="fixed_costs", entidade_id=str(cid))
        self.assertIsNone(t["usuario"])
