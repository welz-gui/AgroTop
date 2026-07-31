"""Testes da máquina de estados regulatória do animal."""

import inspect
import unittest

from services.estados_animal import estados, estados_finais, transicao_permitida


class TestEstadosAnimal(unittest.TestCase):
    def test_assinatura_do_contrato(self):
        self.assertEqual(
            str(inspect.signature(transicao_permitida)),
            "(estado_atual: str, estado_novo: str, *, tem_autorizacao: bool = False) -> dict",
        )

    def test_estados_na_ordem_da_interface(self):
        self.assertEqual(
            estados(),
            [
                "ativo",
                "carencia",
                "vendido",
                "morto",
                "rascunho",
                "ativo_sem_identificacao_oficial",
                "identificado_oficialmente",
                "identificacao_pendente_sincronizacao",
                "identificacao_rejeitada",
                "movimentacao_programada",
                "em_transito",
                "transferido",
                "abatido",
                "desaparecido",
                "furtado",
                "baixado_por_ajuste",
                "cadastro_bloqueado",
            ],
        )

    def test_estados_finais(self):
        self.assertEqual(
            estados_finais(),
            {"vendido", "morto", "transferido", "abatido", "baixado_por_ajuste"},
        )

    def test_morto_para_ativo_sem_autorizacao(self):
        resultado = transicao_permitida("morto", "ativo")

        self.assertFalse(resultado["permitida"])
        self.assertTrue(resultado["exige_autorizacao"])
        self.assertTrue(resultado["exige_justificativa"])
        self.assertEqual(
            resultado["motivo"],
            "Animal morto só volta a ativo com autorização de administrador e "
            "justificativa registrada.",
        )

    def test_morto_para_ativo_com_autorizacao(self):
        resultado = transicao_permitida("morto", "ativo", tem_autorizacao=True)

        self.assertTrue(resultado["permitida"])
        self.assertTrue(resultado["exige_autorizacao"])
        self.assertTrue(resultado["exige_justificativa"])
        self.assertNotEqual(resultado["motivo"], "")

    def test_abate_e_venda_para_ativo_exigem_autorizacao(self):
        for estado in ("abatido", "vendido"):
            with self.subTest(estado=estado, autorizado=False):
                resultado = transicao_permitida(estado, "ativo")
                self.assertFalse(resultado["permitida"])
                self.assertTrue(resultado["exige_autorizacao"])
                self.assertTrue(resultado["exige_justificativa"])
            with self.subTest(estado=estado, autorizado=True):
                resultado = transicao_permitida(
                    estado, "ativo", tem_autorizacao=True
                )
                self.assertTrue(resultado["permitida"])
                self.assertTrue(resultado["exige_autorizacao"])
                self.assertTrue(resultado["exige_justificativa"])

    def test_sentido_inverso_para_estados_finais_e_livre(self):
        for estado in ("morto", "abatido", "vendido"):
            with self.subTest(estado=estado, autorizado=False):
                resultado = transicao_permitida("ativo", estado)
                self.assertEqual(
                    resultado,
                    {
                        "permitida": True,
                        "exige_autorizacao": False,
                        "exige_justificativa": False,
                        "motivo": "",
                    },
                )
            with self.subTest(estado=estado, autorizado=True):
                resultado = transicao_permitida(
                    "ativo", estado, tem_autorizacao=True
                )
                self.assertTrue(resultado["permitida"])
                self.assertFalse(resultado["exige_autorizacao"])

    def test_ativo_e_carencia_nos_dois_sentidos(self):
        for origem, destino in (("ativo", "carencia"), ("carencia", "ativo")):
            for autorizado in (False, True):
                with self.subTest(
                    origem=origem, destino=destino, autorizado=autorizado
                ):
                    resultado = transicao_permitida(
                        origem, destino, tem_autorizacao=autorizado
                    )
                    self.assertTrue(resultado["permitida"])
                    self.assertFalse(resultado["exige_autorizacao"])
                    self.assertFalse(resultado["exige_justificativa"])
                    self.assertEqual(resultado["motivo"], "")

    def test_rascunho_para_ativo_e_livre(self):
        resultado = transicao_permitida("rascunho", "ativo")

        self.assertTrue(resultado["permitida"])
        self.assertFalse(resultado["exige_autorizacao"])

    def test_qualquer_estado_nao_volta_a_rascunho(self):
        for origem in ("ativo", "carencia", "morto"):
            for autorizado in (False, True):
                with self.subTest(origem=origem, autorizado=autorizado):
                    resultado = transicao_permitida(
                        origem, "rascunho", tem_autorizacao=autorizado
                    )
                    self.assertFalse(resultado["permitida"])
                    self.assertFalse(resultado["exige_autorizacao"])
                    self.assertFalse(resultado["exige_justificativa"])
                    self.assertIn("estado inicial", resultado["motivo"])

    def test_estado_igual_e_permitido_sem_efeito(self):
        for estado in ("ativo", "rascunho", "morto"):
            with self.subTest(estado=estado):
                self.assertEqual(
                    transicao_permitida(estado, estado),
                    {
                        "permitida": True,
                        "exige_autorizacao": False,
                        "exige_justificativa": False,
                        "motivo": "",
                    },
                )

    def test_estado_atual_invalido(self):
        resultado = transicao_permitida("inexistente", "ativo")

        self.assertFalse(resultado["permitida"])
        self.assertIn("Estado atual inválido", resultado["motivo"])

    def test_estado_novo_invalido(self):
        resultado = transicao_permitida("ativo", "inexistente")

        self.assertFalse(resultado["permitida"])
        self.assertIn("Estado novo inválido", resultado["motivo"])

    def test_toda_saida_de_estado_final_e_sensivel(self):
        for origem in estados_finais():
            with self.subTest(origem=origem, autorizado=False):
                resultado = transicao_permitida(origem, "carencia")
                self.assertFalse(resultado["permitida"])
                self.assertTrue(resultado["exige_autorizacao"])
                self.assertTrue(resultado["exige_justificativa"])
            with self.subTest(origem=origem, autorizado=True):
                resultado = transicao_permitida(
                    origem, "carencia", tem_autorizacao=True
                )
                self.assertTrue(resultado["permitida"])
                self.assertTrue(resultado["exige_autorizacao"])
                self.assertTrue(resultado["exige_justificativa"])


if __name__ == "__main__":
    unittest.main()
