import unittest
from services.validacao_regulatoria import validar_animal


class TestValidacaoRegulatoria(unittest.TestCase):
    def setUp(self):
        self.hoje = "2026-05-10"
        self.animal_integro = {
            "id": "BR0001",
            "sexo": "F",
            "nascimento": "2024-01-01",
            "propriedade_id": "FAZ001",
            "mae_id": "MAE001",
        }
        self.contexto_integro = {
            "hoje": self.hoje,
            "mae": {
                "id": "MAE001",
                "sexo": "F",
                "nascimento": "2020-01-01",
            },
            "identificadores": [
                {"tipo": "brinco_visual", "valor": "0001", "ativo": True},
                {"tipo": "rfid", "valor": "900123", "ativo": True},
            ],
            "eventos": [
                {
                    "tipo": "nascimento",
                    "data": "2024-01-01",
                    "propriedade_id": "FAZ001",
                },
                {
                    "tipo": "movimentacao",
                    "data": "2025-01-01",
                    "propriedade_id": "FAZ002",
                },
            ],
        }

    def test_animal_integro(self):
        problemas = validar_animal(self.animal_integro, self.contexto_integro)
        self.assertEqual(problemas, [])

    def test_contexto_vazio(self):
        prob1 = validar_animal(self.animal_integro, None)
        self.assertIsInstance(prob1, list)
        prob2 = validar_animal(self.animal_integro, {})
        self.assertIsInstance(prob2, list)

    def test_morte_antes_nascimento(self):
        animal = dict(self.animal_integro, morte="2023-12-31")
        problemas = validar_animal(animal, self.contexto_integro)
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("morte_antes_nascimento", codigos)

        animal_ok = dict(self.animal_integro, morte="2025-06-01")
        codigos_ok = [
            p["codigo"]
            for p in validar_animal(animal_ok, self.contexto_integro)
        ]
        self.assertNotIn("morte_antes_nascimento", codigos_ok)

    def test_movimentacao_apos_morte(self):
        animal = dict(self.animal_integro, morte="2024-06-01")
        contexto = dict(
            self.contexto_integro,
            eventos=[{"tipo": "movimentacao", "data": "2024-07-01"}],
        )
        problemas = validar_animal(animal, contexto)
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("movimentacao_apos_morte", codigos)

    def test_mae_mais_nova_que_cria(self):
        contexto = dict(
            self.contexto_integro,
            mae={"id": "MAE001", "sexo": "F", "nascimento": "2024-06-01"},
        )
        problemas = validar_animal(self.animal_integro, contexto)
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("mae_mais_nova_que_cria", codigos)

    def test_sexo_incompativel_com_parto(self):
        contexto = dict(
            self.contexto_integro,
            mae={"id": "MAE001", "sexo": "M", "nascimento": "2020-01-01"},
        )
        problemas = validar_animal(self.animal_integro, contexto)
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("sexo_incompativel_com_parto", codigos)

    def test_data_futura(self):
        animal = dict(self.animal_integro, nascimento="2026-12-01")
        problemas = validar_animal(animal, self.contexto_integro)
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("data_futura", codigos)

    def test_identificador_duplicado(self):
        contexto = dict(
            self.contexto_integro,
            identificadores=[
                {"tipo": "brinco_visual", "valor": "0001", "ativo": True},
                {"tipo": "brinco_visual", "valor": "0002", "ativo": True},
            ],
        )
        problemas = validar_animal(self.animal_integro, contexto)
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("identificador_duplicado", codigos)

        contexto_inativo = dict(
            self.contexto_integro,
            identificadores=[
                {"tipo": "brinco_visual", "valor": "0001", "ativo": True},
                {"tipo": "brinco_visual", "valor": "0002", "ativo": False},
            ],
        )
        codigos_inativo = [
            p["codigo"]
            for p in validar_animal(self.animal_integro, contexto_inativo)
        ]
        self.assertNotIn("identificador_duplicado", codigos_inativo)

    def test_eventos_fora_de_ordem(self):
        contexto = dict(
            self.contexto_integro,
            eventos=[
                {"tipo": "movimentacao", "data": "2025-05-01"},
                {"tipo": "movimentacao", "data": "2024-05-01"},
            ],
        )
        problemas = validar_animal(self.animal_integro, contexto)
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("eventos_fora_de_ordem", codigos)

    def test_animal_sem_origem(self):
        animal = {
            "id": "BR0001",
            "sexo": "F",
            "nascimento": "2024-01-01",
            "mae_id": "M1",
        }
        problemas = validar_animal(animal, {})
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("animal_sem_origem", codigos)

    def test_nascimento_sem_mae(self):
        animal = {
            "id": "BR0001",
            "sexo": "F",
            "nascimento": "2024-01-01",
            "propriedade_id": "FAZ1",
        }
        problemas = validar_animal(animal, {})
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("nascimento_sem_mae", codigos)

    def test_mae_jovem_demais_fronteiras_e_customizacao(self):
        animal = dict(self.animal_integro, nascimento="2024-06-01")
        contexto = dict(
            self.contexto_integro,
            mae={"id": "MAE1", "sexo": "F", "nascimento": "2023-01-01"},
        )
        prob_padrao = validar_animal(animal, contexto)
        self.assertIn("mae_jovem_demais", [p["codigo"] for p in prob_padrao])

        prob_custom = validar_animal(
            animal, contexto, idade_minima_mae_meses=15
        )
        self.assertNotIn(
            "mae_jovem_demais", [p["codigo"] for p in prob_custom]
        )

    def test_nascimento_estimado(self):
        animal = dict(self.animal_integro, nascimento_estimado=True)
        problemas = validar_animal(animal, self.contexto_integro)
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("nascimento_estimado", codigos)

    def test_varios_problemas_simultaneos(self):
        animal = {
            "id": "BR0001",
            "nascimento": "2024-01-01",
            "morte": "2023-01-01",
            "nascimento_estimado": True,
        }
        contexto = {
            "mae": {"id": "M1", "sexo": "M"},
        }
        problemas = validar_animal(animal, contexto)
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("morte_antes_nascimento", codigos)
        self.assertIn("sexo_incompativel_com_parto", codigos)
        self.assertIn("nascimento_estimado", codigos)


if __name__ == "__main__":
    unittest.main()
