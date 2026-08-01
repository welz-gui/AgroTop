"""Teste ponta a ponta da API usando usuário e animais reais do SQLite local."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ["AGROTOP_FORCE_SQLITE"] = "1"
os.environ["AGROTOP_ADMIN_PASSWORD"] = "senha-da-poc"
os.environ["AGROTOP_OP_PASSWORD"] = "senha-da-poc"
os.environ["AGROTOP_API_SECRET"] = "segredo-local-de-teste-com-mais-de-32-caracteres"

from fastapi.testclient import TestClient

import database
from poc.api.main import app
from repositories.conexao import configurar_sqlite


class ApiFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        configurar_sqlite(str(Path(cls._tmp.name) / "poc.db"))
        database.init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_login_lista_ficha_e_gmd(self):
        login = self.client.post(
            "/auth/login", json={"username": "admin", "password": "senha-da-poc"}
        )
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        lista = self.client.get("/animais", headers=headers)
        self.assertEqual(lista.status_code, 200, lista.text)
        self.assertGreater(len(lista.json()), 0)

        animal_id = lista.json()[0]["id"]
        ficha = self.client.get(f"/animais/{animal_id}", headers=headers)
        self.assertEqual(ficha.status_code, 200, ficha.text)
        self.assertEqual(ficha.json()["id"], animal_id)
        self.assertIn("gmd_recent_kg_day", ficha.json())
        self.assertIn("gmd_total_kg_day", ficha.json())

    def test_endpoint_protegido_rejeita_sem_token(self):
        response = self.client.get("/animais")
        self.assertEqual(response.status_code, 401)

    def test_login_invalido_nao_emite_token(self):
        response = self.client.post(
            "/auth/login", json={"username": "admin", "password": "errada"}
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
