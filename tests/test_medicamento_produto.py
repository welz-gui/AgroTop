"""Tratamento grava princípio ativo, lote e validade do produto aplicado.

Um tratamento só é defensável se disser o que foi aplicado, de qual lote e até
quando valia. Os campos são opcionais; validade anterior à aplicação é recusada e,
nesse caso, nada é gravado (nem a aplicação, nem a baixa de estoque, nem o evento).
"""

import unittest
from datetime import timedelta

import database as db
from repositories import eventos
from repositories.sanidade import MedicationData, add_medication, get_medications
from tests.test_regras_negocio import BaseRegras, HOJE


def _hoje():
    return HOJE.isoformat()


def _dias(n):
    return (HOJE + timedelta(days=n)).isoformat()


class TestProdutoAplicado(BaseRegras):
    def setUp(self):
        super().setUp()
        self.animal("A1")
        db.add_new_insumo(db.InsumoCreate("Ivermectina 1%", "medicamento", "ml", 100.0, 10.0, 0.5,
                                          principio_ativo="  ivermectina "))
        with db._conn() as con:
            self.insumo = dict(con.execute("SELECT * FROM insumos WHERE name='Ivermectina 1%'").fetchone())

    def _aplicar(self, **kw):
        base = dict(animal_id="A1", medication_name="Ivermectina 1%", dose=5.0, unit="ml",
                    application_route="Subcutânea", withdrawal_days=0, med_date=_hoje(), applied_by="t")
        base.update(kw)
        add_medication(MedicationData(**base))
        db.clear_cache()
        return get_medications("A1")[0]

    def test_grava_principio_ativo_lote_e_validade(self):
        m = self._aplicar(principio_ativo="ivermectina", lote_produto="L2410A", validade_produto=_dias(180))
        self.assertEqual((m["principio_ativo"], m["lote_produto"], m["validade_produto"]),
                         ("ivermectina", "L2410A", _dias(180)))

    def test_sem_os_campos_continua_valendo_e_fica_nulo(self):
        m = self._aplicar()
        self.assertEqual((m["principio_ativo"], m["lote_produto"], m["validade_produto"]), (None, None, None))

    def test_principio_ativo_vazio_usa_o_do_cadastro_do_insumo(self):
        m = self._aplicar(insumo_id=self.insumo["id"])
        self.assertEqual(m["principio_ativo"], "ivermectina")

    def test_principio_ativo_informado_prevalece_sobre_o_do_insumo(self):
        m = self._aplicar(insumo_id=self.insumo["id"], principio_ativo="abamectina")
        self.assertEqual(m["principio_ativo"], "abamectina")

    def test_insumo_sem_principio_ativo_deixa_a_aplicacao_sem(self):
        db.add_new_insumo(db.InsumoCreate("Vacina X", "vacina", "dose", 10.0, 1.0, 1.0))
        with db._conn() as con:
            vid = con.execute("SELECT id FROM insumos WHERE name='Vacina X'").fetchone()["id"]
        m = self._aplicar(medication_name="Vacina X", insumo_id=vid)
        self.assertIsNone(m["principio_ativo"])

    def test_produto_vencido_e_recusado_e_nada_e_gravado(self):
        with self.assertRaises(db.TratamentoInvalido):
            add_medication(MedicationData(
                animal_id="A1", medication_name="Ivermectina 1%", dose=5.0, unit="ml",
                application_route="Subcutânea", withdrawal_days=10, med_date=_hoje(), applied_by="t",
                insumo_id=self.insumo["id"], lote_produto="L1", validade_produto=_dias(-1)))
        db.clear_cache()
        self.assertEqual(get_medications("A1"), [])
        with db._conn() as con:
            estoque = con.execute("SELECT current_stock FROM insumos WHERE id=?", (self.insumo["id"],)).fetchone()[0]
            transacoes = con.execute("SELECT COUNT(*) FROM insumo_transactions WHERE reason='uso_animal'").fetchone()[0]
            status = con.execute("SELECT status FROM animals WHERE id='A1'").fetchone()[0]
        self.assertEqual(estoque, 100.0, "a baixa de estoque não pode ter acontecido")
        self.assertEqual(transacoes, 0)
        self.assertEqual(status, "ativo", "a carência não pode ter mudado o status")

    def test_validade_no_dia_da_aplicacao_e_aceita(self):
        m = self._aplicar(validade_produto=_hoje())
        self.assertEqual(m["validade_produto"], _hoje())

    def test_validade_e_comparada_com_a_data_da_aplicacao_e_nao_com_hoje(self):
        """Pesagem/aplicação retroativa (fila offline): vale a validade na data em que ocorreu."""
        antiga = _dias(-30)
        m = self._aplicar(med_date=antiga, validade_produto=_dias(-10))
        self.assertEqual(m["validade_produto"], _dias(-10))

    def test_validade_com_formato_invalido_e_recusada(self):
        with self.assertRaises(db.TratamentoInvalido):
            self._aplicar(validade_produto="31/12/2030")

    def test_o_evento_sanitario_carrega_principio_lote_e_validade(self):
        self._aplicar(principio_ativo="ivermectina", lote_produto="L2410A", validade_produto=_dias(180), withdrawal_days=21)
        with db._conn() as con:
            uuid = con.execute("SELECT uuid FROM animals WHERE id='A1'").fetchone()["uuid"]
        obs = [e["observacoes"] for e in eventos.do_animal(uuid, tipo="manejo_sanitario")][0]
        self.assertIn("principio ativo ivermectina", obs)
        self.assertIn("lote L2410A", obs)
        self.assertIn(f"validade {_dias(180)}", obs)
        self.assertIn("carencia 21d", obs)

    def test_cadastro_de_insumo_normaliza_o_principio_ativo(self):
        self.assertEqual(self.insumo["principio_ativo"], "ivermectina")


class TestCampanhaComProduto(BaseRegras):
    def setUp(self):
        super().setUp()
        self.animal("C1", nascimento=(HOJE - timedelta(days=400)).isoformat())
        self.animal("C2", nascimento=(HOJE - timedelta(days=400)).isoformat())
        db.add_new_insumo(db.InsumoCreate("Aftosa", "vacina", "dose", 50.0, 5.0, 2.0, principio_ativo="vírus inativado"))
        with db._conn() as con:
            iid = con.execute("SELECT id FROM insumos WHERE name='Aftosa'").fetchone()["id"]
        db.add_protocol(db.ProtocolData(
            name="Aftosa", sex_target="ambos", age_min=0, age_max=999, dose_value=2.0, dose_ref_kg=0.0,
            dose_unit="dose", insumo_id=iid, frequency="unica", withdrawal_days=0))
        self.protocolo = db.get_protocols(active_only=False)[0]

    def test_campanha_grava_lote_e_validade_em_todos_e_usa_o_principio_do_insumo(self):
        r = db.apply_protocol_campaign(self.protocolo["id"], _hoje(), "t",
                                       lote_produto="F-77", validade_produto=_dias(90))
        db.clear_cache()
        self.assertEqual(r["n"], 2)
        for aid in ("C1", "C2"):
            m = get_medications(aid)[0]
            self.assertEqual((m["lote_produto"], m["validade_produto"], m["principio_ativo"]),
                             ("F-77", _dias(90), "vírus inativado"))

    def test_campanha_com_produto_vencido_nao_aplica_em_ninguem(self):
        with self.assertRaises(db.TratamentoInvalido):
            db.apply_protocol_campaign(self.protocolo["id"], _hoje(), "t",
                                       lote_produto="F-77", validade_produto=_dias(-1))
        db.clear_cache()
        self.assertEqual(get_medications("C1"), [])
        self.assertEqual(get_medications("C2"), [])


if __name__ == "__main__":
    unittest.main()
