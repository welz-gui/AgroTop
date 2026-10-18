"""API: produto aplicado (princípio ativo, lote, validade) em POST/GET /animais/{id}/medicamentos."""

import unittest
from datetime import date, timedelta

import database as db
from database import _conn
from repositories.animais import get_all_animals
from tests.test_backend_api import BackendApiTestCase


def _dias(n):
    return (date.today() + timedelta(days=n)).isoformat()


class TestMedicamentoProdutoApi(BackendApiTestCase):
    def setUp(self):
        super().setUp()
        self.animal_id = get_all_animals()[0]["id"]
        self.url = f"/animais/{self.animal_id}/medicamentos"
        self.headers = {"Authorization": f"Bearer {self._get_access_token()}"}

    def _payload(self, **extra):
        base = {"medicamento": "Produto Teste D2", "dose": 5.0, "unidade": "ml", "via": "Subcutânea",
                "carencia_dias": 0, "data": date.today().isoformat()}
        base.update(extra)
        return base

    def _qtd(self):
        with _conn() as con:
            return con.execute("SELECT COUNT(*) FROM medications WHERE medication_name='Produto Teste D2'").fetchone()[0]

    def test_post_grava_e_get_devolve_principio_lote_e_validade(self):
        res = self.client.post(self.url, headers=self.headers, json=self._payload(
            principio_ativo="ivermectina", lote="L2410A", validade=_dias(120)))
        self.assertEqual(res.status_code, 201)

        aplicacao = next(a for a in self.client.get(self.url, headers=self.headers).json()["aplicacoes"]
                         if a["medicamento"] == "Produto Teste D2")
        self.assertEqual((aplicacao["principio_ativo"], aplicacao["lote"], aplicacao["validade"]),
                         ("ivermectina", "L2410A", _dias(120)))

    def test_payload_antigo_sem_os_campos_continua_funcionando(self):
        res = self.client.post(self.url, headers=self.headers, json=self._payload())
        self.assertEqual(res.status_code, 201)
        aplicacao = next(a for a in self.client.get(self.url, headers=self.headers).json()["aplicacoes"]
                         if a["medicamento"] == "Produto Teste D2")
        self.assertIsNone(aplicacao["principio_ativo"])
        self.assertIsNone(aplicacao["lote"])
        self.assertIsNone(aplicacao["validade"])

    def test_produto_vencido_devolve_422_e_nao_grava(self):
        res = self.client.post(self.url, headers=self.headers, json=self._payload(lote="L1", validade=_dias(-1)))
        self.assertEqual(res.status_code, 422)
        self.assertIn("vencido", res.json()["detail"])
        self.assertEqual(self._qtd(), 0)

    def test_validade_em_formato_invalido_devolve_422(self):
        res = self.client.post(self.url, headers=self.headers, json=self._payload(validade="31/12/2030"))
        self.assertEqual(res.status_code, 422)
        self.assertEqual(self._qtd(), 0)

    def test_animal_inexistente_continua_404_e_nao_vira_422(self):
        res = self.client.post("/animais/NAO-EXISTE/medicamentos", headers=self.headers,
                               json=self._payload(lote="L1", validade=_dias(30)))
        self.assertEqual(res.status_code, 404)

    def test_422_nao_fica_guardado_na_idempotencia_e_a_mesma_chave_pode_ser_corrigida(self):
        headers = {**self.headers, "Idempotency-Key": "med-vencido-1"}
        ruim = self.client.post(self.url, headers=headers, json=self._payload(lote="L1", validade=_dias(-1)))
        self.assertEqual(ruim.status_code, 422)

        # Operador corrige a validade e reenvia com a mesma chave: é um pedido novo, não o cache do erro.
        bom = self.client.post(self.url, headers=headers, json=self._payload(lote="L1", validade=_dias(60)))
        self.assertEqual(bom.status_code, 201)
        self.assertEqual(self._qtd(), 1)

    def test_mesma_chave_com_lote_diferente_e_recusada_pelo_hash_do_payload(self):
        headers = {**self.headers, "Idempotency-Key": "med-lote-1"}
        primeiro = self.client.post(self.url, headers=headers, json=self._payload(lote="L1", validade=_dias(60)))
        self.assertEqual(primeiro.status_code, 201)

        outro = self.client.post(self.url, headers=headers, json=self._payload(lote="L2", validade=_dias(60)))

        self.assertEqual(outro.status_code, 422)
        self.assertEqual(self._qtd(), 1)

    def test_principio_ativo_do_cadastro_do_insumo_nao_e_aplicado_pela_api_sem_insumo(self):
        """A API não liga insumo (insumo_id=None): sem princípio informado, fica vazio."""
        db.add_new_insumo(db.InsumoCreate("Produto Teste D2", "medicamento", "ml", 10.0, 1.0, 1.0,
                                          principio_ativo="ivermectina"))
        self.client.post(self.url, headers=self.headers, json=self._payload())
        aplicacao = next(a for a in self.client.get(self.url, headers=self.headers).json()["aplicacoes"]
                         if a["medicamento"] == "Produto Teste D2")
        self.assertIsNone(aplicacao["principio_ativo"])


if __name__ == "__main__":
    unittest.main()
