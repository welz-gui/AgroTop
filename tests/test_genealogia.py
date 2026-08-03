import unittest
from services.genealogia import validar_vinculo


class TestValidacaoGenealogia(unittest.TestCase):
    def setUp(self):
        self.cria_valida = {
            "id": "CRIA01",
            "sexo": "M",
            "nascimento": "2026-05-10",
            "propriedade_id": 1,
        }
        self.mae_valida = {
            "id": "MAE01",
            "sexo": "F",
            "nascimento": "2024-01-01",  # 28 meses no parto -> OK
            "propriedade_id": 1,
        }

    def test_sem_mae_vinculada(self):
        res = validar_vinculo(self.cria_valida, None)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["codigo"], "sem_mae_vinculada")
        self.assertEqual(res[0]["gravidade"], "informativo")

        res_ok = validar_vinculo(self.cria_valida, self.mae_valida)
        self.assertEqual(res_ok, [])

    def test_mae_macho(self):
        mae_macho = dict(self.mae_valida, sexo="M")
        res = validar_vinculo(self.cria_valida, mae_macho)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["codigo"], "mae_macho")
        self.assertEqual(res[0]["gravidade"], "bloqueio")

        self.assertEqual(validar_vinculo(self.cria_valida, self.mae_valida), [])

    def test_mae_mais_nova_que_cria(self):
        mae_nova = dict(
            self.mae_valida, nascimento="2026-06-01"
        )  # Nascida depois da cria
        res = validar_vinculo(self.cria_valida, mae_nova)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["codigo"], "mae_mais_nova_que_cria")
        self.assertEqual(res[0]["gravidade"], "bloqueio")

    def test_mae_jovem_demais_fronteiras(self):
        # Vaca de 24 meses parindo passa (nasc mãe 2024-05-10, cria 2026-05-10)
        mae_24m = dict(self.mae_valida, nascimento="2024-05-10")
        res_24m = validar_vinculo(self.cria_valida, mae_24m)
        self.assertEqual(res_24m, [])

        # Vaca de 12 meses parindo é bloqueada (nasc mãe 2025-05-10, cria 2026-05-10)
        mae_12m = dict(self.mae_valida, nascimento="2025-05-10")
        res_12m = validar_vinculo(self.cria_valida, mae_12m)
        self.assertEqual(len(res_12m), 1)
        self.assertEqual(res_12m[0]["codigo"], "mae_jovem_demais")
        self.assertEqual(res_12m[0]["gravidade"], "bloqueio")
        self.assertIn("12 meses", res_12m[0]["mensagem"])

    def test_parto_apos_morte_da_mae(self):
        mae_morta = dict(
            self.mae_valida, morte="2026-01-01"
        )  # Morreu antes do parto
        res = validar_vinculo(self.cria_valida, mae_morta)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["codigo"], "parto_apos_morte_da_mae")
        self.assertEqual(res[0]["gravidade"], "bloqueio")

        mae_morta_depois = dict(
            self.mae_valida, morte="2026-07-01"
        )  # Morreu depois -> OK
        self.assertEqual(
            validar_vinculo(self.cria_valida, mae_morta_depois), []
        )

    def test_intervalo_entre_partos_curto(self):
        # Parto anterior há 150 dias (< 270) -> alerta
        ctx_curto = {"partos_anteriores": ["2025-12-10"]}
        res = validar_vinculo(self.cria_valida, self.mae_valida, ctx_curto)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["codigo"], "intervalo_entre_partos_curto")
        self.assertEqual(res[0]["gravidade"], "alerta")

        # Parto anterior há 365 dias (>= 270) -> OK
        ctx_ok = {"partos_anteriores": ["2025-05-10"]}
        self.assertEqual(
            validar_vinculo(self.cria_valida, self.mae_valida, ctx_ok), []
        )

    def test_mae_em_outra_propriedade(self):
        mae_outra = dict(
            self.mae_valida, propriedade_id=2
        )  # Cria em 1, mãe em 2
        res = validar_vinculo(self.cria_valida, mae_outra)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["codigo"], "mae_em_outra_propriedade")
        self.assertEqual(res[0]["gravidade"], "alerta")

        self.assertEqual(validar_vinculo(self.cria_valida, self.mae_valida), [])

    def test_contexto_vazio_nao_estoura(self):
        res_vazio = validar_vinculo(self.cria_valida, self.mae_valida, None)
        self.assertEqual(res_vazio, [])

        res_vazio_dict = validar_vinculo(self.cria_valida, self.mae_valida, {})
        self.assertEqual(res_vazio_dict, [])


if __name__ == "__main__":
    unittest.main()
