"""Testes unitários para services.gta_adaptador (Spec 0038)."""

import unittest
from services.gta_adaptador import montar_contexto
from services.gta import validar


class TestGtaAdaptador(unittest.TestCase):

    def test_criterio_1_dados_completos_rodam_todas_as_checagens(self):
        """Critério 1: dados_do_documento completo produz gta completo e validação correta."""
        movimentacao = {
            "gta_numero": "GTA-12345",
            "propriedade_origem_nome": "Fazenda Sol",
            "propriedade_destino_nome": "Frigorífico Boi Gordo",
            "finalidade": "abate",
            "animais_uuids": ["uuid-1", "uuid-2"],
        }
        dados_doc = {
            "emissao": "2026-08-01",
            "validade": "2026-08-05",  # Vencida se hoje for 2026-08-06
            "quantidade_declarada": 2,
        }
        gta, contexto = montar_contexto(
            movimentacao,
            dados_doc,
            animais_no_embarque_uuids=["uuid-1", "uuid-2"],
            animais_em_carencia_uuids=[],
            hoje="2026-08-06",
        )

        self.assertEqual(gta["numero"], "GTA-12345")
        self.assertEqual(gta["emissao"], "2026-08-01")
        self.assertEqual(gta["validade"], "2026-08-05")
        self.assertEqual(gta["quantidade"], 2)

        problemas = validar(gta, contexto)
        codigos = [p["codigo"] for p in problemas]
        self.assertIn("gta_vencida", codigos)

    def test_criterio_2_dados_none_nao_disparam_checagens_dependentes(self):
        """Critério 2: dados_do_documento com Nones produz gta sem campos e não dispara checagens desnecessárias."""
        movimentacao = {
            "gta_numero": "GTA-12345",
            "propriedade_origem_nome": "Fazenda Sol",
            "propriedade_destino_nome": "Fazenda Lua",
            "finalidade": "recria",
            "animais_uuids": ["uuid-1"],
        }
        dados_doc = {
            "emissao": None,
            "validade": None,
            "quantidade_declarada": None,
        }
        gta, contexto = montar_contexto(
            movimentacao,
            dados_doc,
            animais_no_embarque_uuids=["uuid-1"],
            animais_em_carencia_uuids=[],
            hoje="2026-08-06",
        )

        self.assertNotIn("emissao", gta)
        self.assertNotIn("validade", gta)
        self.assertNotIn("quantidade", gta)

        problemas = validar(gta, contexto)
        codigos = [p["codigo"] for p in problemas]
        self.assertNotIn("gta_vencida", codigos)
        self.assertNotIn("gta_futura", codigos)
        self.assertNotIn("validade_maior_que_o_permitido", codigos)
        self.assertNotIn("quantidade_divergente", codigos)

    def test_criterio_3_divergencia_de_embarque_gera_problema(self):
        """Critério 3: animais_no_embarque_uuids divergente gera problema de embarque/GTA."""
        movimentacao = {
            "gta_numero": "GTA-12345",
            "animais_uuids": ["uuid-1", "uuid-2"],
        }
        dados_doc = {}
        gta, contexto = montar_contexto(
            movimentacao,
            dados_doc,
            animais_no_embarque_uuids=["uuid-1", "uuid-3"],
            animais_em_carencia_uuids=[],
            hoje="2026-08-06",
        )

        problemas = validar(gta, contexto)
        codigos = [p["codigo"] for p in problemas]
        self.assertTrue(
            "animal_no_embarque_fora_da_gta" in codigos
            or "animal_da_gta_ausente" in codigos
        )

    def test_criterio_4_uf_origem_e_destino_ausentes(self):
        """Critério 4: uf_origem e uf_destino nunca aparecem no gta retornado."""
        movimentacao = {
            "gta_numero": "GTA-999",
            "propriedade_origem_nome": "Fazenda MS",
            "propriedade_destino_nome": "Fazenda SP",
        }
        gta, _ = montar_contexto(movimentacao, {}, [], [], "2026-08-06")
        self.assertNotIn("uf_origem", gta)
        self.assertNotIn("uf_destino", gta)

    def test_criterio_5_listas_vazias_nao_estouram(self):
        """Critério 5: Lista de UUIDs vazia em qualquer um dos parâmetros não estoura."""
        gta, contexto = montar_contexto({}, {}, [], [], "2026-08-06")
        self.assertEqual(gta["animais"], [])
        self.assertEqual(contexto["animais_no_embarque"], [])
        self.assertEqual(contexto["animais_em_carencia"], [])
        problemas = validar(gta, contexto)
        self.assertIsInstance(problemas, list)


if __name__ == "__main__":
    unittest.main()
