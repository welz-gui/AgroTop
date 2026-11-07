"""A aplicação guarda o piquete em que o animal estava NA DATA dela (plano, comparação com outros
sistemas): o do dia, e não o do momento do registro, para valer em aplicação offline ou retroativa.
"""

import sqlite3

import database as db
from repositories.sanidade import MedicationData, get_medication_history, corrigir_medicamento
from tests.test_backend_api import BackendApiTestCase
from tests.test_regras_negocio import BaseRegras, _dias_atras


def _med(animal, dias_atras, nome="Ivermectina"):
    return MedicationData(animal_id=animal, medication_name=nome, dose=1.0, unit="ml",
                          application_route="Subcutânea", withdrawal_days=0,
                          med_date=_dias_atras(dias_atras), applied_by="t")


class TestPiqueteNaAplicacao(BaseRegras):
    def _movimentou(self, aid, de, para, dias_atras, cancelada=False):
        self._sql(
            "INSERT INTO animal_movements (animal_uuid,from_lote_id,to_lote_id,movement_date,cancelada_em) "
            "VALUES(?,?,?,?,?)",
            (self._uuid(aid), de, para, _dias_atras(dias_atras), "2026-01-01" if cancelada else None))

    def _lote_da_aplicacao(self, aid):
        con = sqlite3.connect(db.DB_PATH)
        try:
            return [r[0] for r in con.execute(
                "SELECT lote_id FROM medications WHERE animal_uuid=? ORDER BY id", (self._uuid(aid),))]
        finally:
            con.close()

    def test_sem_movimentacao_vale_o_piquete_de_hoje(self):
        a = self.animal("P1", lote="P01")

        db.add_medication(_med(a, 3))

        self.assertEqual(self._lote_da_aplicacao(a), ["P01"])

    def test_aplicacao_anterior_a_uma_movimentacao_leva_o_piquete_de_origem(self):
        a = self.animal("P2", lote="P02")           # hoje está no P02
        self._movimentou(a, "P01", "P02", 10)        # foi do P01 para o P02 há 10 dias

        db.add_medication(_med(a, 20))               # antes da mudança
        db.add_medication(_med(a, 5))                # depois dela

        self.assertEqual(self._lote_da_aplicacao(a), ["P01", "P02"])

    def test_no_dia_da_movimentacao_conta_o_piquete_de_destino(self):
        a = self.animal("P3", lote="P02")
        self._movimentou(a, "P01", "P02", 10)

        db.add_medication(_med(a, 10))

        self.assertEqual(self._lote_da_aplicacao(a), ["P02"])

    def test_varias_movimentacoes_usam_a_primeira_depois_da_data(self):
        a = self.animal("P4", lote="P03")
        self._movimentou(a, "P01", "P02", 30)
        self._movimentou(a, "P02", "P03", 10)

        for dias in (40, 20, 5):
            db.add_medication(_med(a, dias))

        self.assertEqual(self._lote_da_aplicacao(a), ["P01", "P02", "P03"])

    def test_movimentacao_cancelada_e_ignorada(self):
        a = self.animal("P5", lote="P02")
        self._movimentou(a, "P01", "P02", 10, cancelada=True)

        db.add_medication(_med(a, 20))

        self.assertEqual(self._lote_da_aplicacao(a), ["P02"])

    def test_animal_sem_piquete_fica_sem_piquete(self):
        a = self.animal("P6", lote=None)

        db.add_medication(_med(a, 3))

        self.assertEqual(self._lote_da_aplicacao(a), [None])

    def test_correcao_refaz_o_piquete_pela_data_corrigida(self):
        a = self.animal("P7", lote="P02")
        self._movimentou(a, "P01", "P02", 10)
        db.add_medication(_med(a, 5))                # nasce no P02
        original = get_medication_history(a)[0]["id"]

        corrigir_medicamento(original, _med(a, 20), "data errada", "t")

        vigentes = [m for m in get_medication_history(a) if not m["cancelada_em"]]
        self.assertEqual([m["lote_id"] for m in vigentes], ["P01"])
        self.assertEqual(self._lote_da_aplicacao(a), ["P02", "P01"], "a original continua com o dela")


class TestPiqueteNaApi(BackendApiTestCase):
    def test_lista_de_medicamentos_traz_o_piquete_com_o_nome(self):
        animal = next(a for a in db.get_all_animals() if a.get("lote_id"))
        h = {"Authorization": f"Bearer {self._get_access_token()}"}
        corpo = {"medicamento": "Produto do teste do piquete", "dose": 1.0, "unidade": "ml", "via": "Subcutânea",
                 "carencia_dias": 0, "data": _dias_atras(1)}

        r = self.client.post(f"/animais/{animal['id']}/medicamentos", headers=h, json=corpo)
        self.assertEqual(r.status_code, 201, r.text)
        db.clear_cache()

        aplicacoes = self.client.get(f"/animais/{animal['id']}/medicamentos", headers=h).json()["aplicacoes"]
        (ap,) = [a for a in aplicacoes if a["medicamento"] == "Produto do teste do piquete"]
        self.assertEqual(ap["piquete_id"], str(animal["lote_id"]))
        nome = next(l["name"] for l in db.get_all_lotes() if str(l["id"]) == str(animal["lote_id"]))
        self.assertEqual(ap["piquete"], nome)
