"""Cancelar e corrigir aplicação pela API (plano de rastreabilidade, Fase 2).

O registro original nunca some: cancelar marca com motivo e autor, corrigir cancela e grava a
certa, ligada à original. Motivo é obrigatório; aplicação de outro animal é 404; repetir o
cancelamento é 409 com código; a mesma Idempotency-Key devolve a resposta guardada.
"""

import sqlite3

import database as db
from repositories.sanidade import get_medication_history, get_medications
from tests.test_backend_api import BackendApiTestCase


class TestCorrecaoDeTratamentoApi(BackendApiTestCase):
    def _headers(self, chave=None):
        h = {"Authorization": f"Bearer {self._get_access_token()}"}
        if chave:
            h["Idempotency-Key"] = chave
        return h

    def _corpo(self, **kw):
        base = {"medicamento": "Ivermectina CORR", "dose": 5.0, "unidade": "ml", "via": "Subcutânea",
                "carencia_dias": 21, "data": "2026-10-01"}
        base.update(kw)
        return base

    def _aplicar(self, animal_id, **kw):
        r = self.client.post(f"/animais/{animal_id}/medicamentos", headers=self._headers(),
                             json=self._corpo(**kw))
        self.assertEqual(r.status_code, 201, r.text)
        db.clear_cache()
        return [m for m in get_medication_history(animal_id) if m["medication_name"] == "Ivermectina CORR"][0]

    def _animais(self):
        ids = [a["id"] for a in db.get_all_animals()]
        return ids[0], ids[1]

    def test_listagem_expoe_o_id_da_aplicacao(self):
        a, _ = self._animais()
        m = self._aplicar(a)
        r = self.client.get(f"/animais/{a}/medicamentos", headers=self._headers())
        self.assertIn(m["id"], [x["id"] for x in r.json()["aplicacoes"]])

    def test_cancelar_exige_motivo(self):
        a, _ = self._animais()
        m = self._aplicar(a)
        r = self.client.post(f"/animais/{a}/medicamentos/{m['id']}/cancelar", headers=self._headers(),
                             json={"motivo": "   "})
        self.assertEqual(r.status_code, 422)
        db.clear_cache()
        self.assertIn(m["id"], [x["id"] for x in get_medications(a)])

    def test_cancelar_tira_da_listagem_e_guarda_o_historico(self):
        a, _ = self._animais()
        m = self._aplicar(a)
        r = self.client.post(f"/animais/{a}/medicamentos/{m['id']}/cancelar", headers=self._headers(),
                             json={"motivo": "animal errado"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(r.json()["aplicacao_id"])
        lista = self.client.get(f"/animais/{a}/medicamentos", headers=self._headers()).json()
        self.assertNotIn(m["id"], [x["id"] for x in lista["aplicacoes"]])
        hist = [x for x in get_medication_history(a) if x["id"] == m["id"]][0]
        self.assertEqual(hist["motivo_cancelamento"], "animal errado")
        self.assertTrue(hist["cancelada_por"])

    def test_cancelar_de_novo_devolve_409_com_codigo(self):
        a, _ = self._animais()
        m = self._aplicar(a)
        url = f"/animais/{a}/medicamentos/{m['id']}/cancelar"
        self.client.post(url, headers=self._headers(), json={"motivo": "erro"})
        r = self.client.post(url, headers=self._headers(), json={"motivo": "erro"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["codigo"], "aplicacao_ja_cancelada")

    def test_aplicacao_de_outro_animal_ou_inexistente_e_404_e_nao_cancela(self):
        a, b = self._animais()
        m = self._aplicar(a)
        r = self.client.post(f"/animais/{b}/medicamentos/{m['id']}/cancelar", headers=self._headers(),
                             json={"motivo": "erro"})
        self.assertEqual(r.status_code, 404)
        r = self.client.post(f"/animais/{a}/medicamentos/99999/cancelar", headers=self._headers(),
                             json={"motivo": "erro"})
        self.assertEqual(r.status_code, 404)
        db.clear_cache()
        self.assertIn(m["id"], [x["id"] for x in get_medications(a)])

    def test_corrigir_cria_a_nova_e_devolve_o_id(self):
        a, _ = self._animais()
        m = self._aplicar(a, dose=50.0)
        r = self.client.post(f"/animais/{a}/medicamentos/{m['id']}/corrigir", headers=self._headers(),
                             json={**self._corpo(dose=5.0, lote="L9"), "motivo": "dose com zero a mais"})
        self.assertEqual(r.status_code, 200, r.text)
        nova = r.json()["aplicacao_id"]
        self.assertIsNotNone(nova)
        db.clear_cache()
        vigentes = {x["id"]: x for x in get_medications(a)}
        self.assertNotIn(m["id"], vigentes)
        self.assertEqual(vigentes[nova]["dose"], 5.0)
        self.assertEqual(vigentes[nova]["lote_produto"], "L9")
        self.assertEqual(vigentes[nova]["corrige_id"], m["id"])

    def test_corrigir_produto_vencido_e_422_e_a_original_continua_vigente(self):
        a, _ = self._animais()
        m = self._aplicar(a)
        r = self.client.post(f"/animais/{a}/medicamentos/{m['id']}/corrigir", headers=self._headers(),
                             json={**self._corpo(validade="2020-01-01"), "motivo": "erro"})
        self.assertEqual(r.status_code, 422)
        db.clear_cache()
        self.assertIn(m["id"], [x["id"] for x in get_medications(a)])

    def test_mesma_chave_devolve_a_resposta_guardada_sem_corrigir_duas_vezes(self):
        a, _ = self._animais()
        m = self._aplicar(a)
        url = f"/animais/{a}/medicamentos/{m['id']}/corrigir"
        corpo = {**self._corpo(dose=4.0), "motivo": "erro"}
        r1 = self.client.post(url, headers=self._headers("corr-1"), json=corpo)
        r2 = self.client.post(url, headers=self._headers("corr-1"), json=corpo)
        self.assertEqual((r1.status_code, r2.status_code), (200, 200))
        self.assertEqual(r1.json(), r2.json())
        db.clear_cache()
        self.assertEqual(len([x for x in get_medication_history(a) if x["medication_name"] == "Ivermectina CORR"]), 2)

    def test_correcao_deixa_trilha_de_auditoria_com_origem_app(self):
        a, _ = self._animais()
        m = self._aplicar(a)
        self.client.post(f"/animais/{a}/medicamentos/{m['id']}/cancelar", headers=self._headers(),
                         json={"motivo": "erro"})
        with sqlite3.connect(db.DB_PATH) as con:
            con.row_factory = sqlite3.Row
            linha = con.execute(
                "SELECT usuario, origem, motivo FROM audit_logs WHERE acao='cancelar_aplicacao' "
                "AND entidade_id=?", (str(m["id"]),)).fetchone()
        self.assertEqual((linha["origem"], linha["motivo"]), ("app", "erro"))
        self.assertTrue(linha["usuario"])
