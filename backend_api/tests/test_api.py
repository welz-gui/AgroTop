import unittest
import sys
import os

# Adiciona o diretório da API ao path do Python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from main import app

class TestFastAPIBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("version", data)

    def test_simular_terminacao_endpoint(self):
        payload = {
            "peso_atual": 380.0,
            "peso_meta": 540.0,
            "preco_arroba": 230.0,
            "custo_boi_magro": 0.0
        }
        headers = {"Authorization": "Bearer mock_dev_token"}
        response = self.client.post("/api/v1/simular-terminacao", json=payload, headers=headers)
        self.assertEqual(response.statusCode if hasattr(response, 'statusCode') else response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ganho_necessario_kg"], 160.0)
        self.assertGreater(len(data["cenarios"]), 0)
        self.assertIsNotNone(data["melhor_estratégia"])

    def test_dashboard_stats_endpoint(self):
        headers = {"Authorization": "Bearer mock_dev_token"}
        response = self.client.get("/api/v1/dashboard/stats", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_animais_ativos", data)
        self.assertGreaterThan = self.assertGreater(data["total_animais_ativos"], 0)

    def test_processar_imagem_endpoint(self):
        headers = {"Authorization": "Bearer mock_dev_token"}
        files = {"file": ("test_brinco.jpg", b"fake_image_bytes", "image/jpeg")}
        response = self.client.post("/api/v1/processar-imagem", files=files, headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("task_id", data)
        self.assertEqual(data["status"], "pending")

if __name__ == "__main__":
    unittest.main()
