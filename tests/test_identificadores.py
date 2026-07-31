import unittest

from services.identificadores import REGRAS_PADRAO, mesmo_identificador, validar


class TestIdentificadores(unittest.TestCase):
    def test_regra_vazia_aceita_qualquer_coisa(self):
        resultado = validar("br 123-456", {})
        self.assertTrue(resultado["valido"])
        self.assertEqual(resultado["normalizado"], "BR123456")
        self.assertEqual(resultado["erros"], [])

    def test_normalizacao_remove_espaco_traco_e_ponto(self):
        resultado = validar(" br.123-456 ", {})
        self.assertEqual(resultado["normalizado"], "BR123456")

    def test_tamanho_exato_falha_com_valor_curto(self):
        resultado = validar("abc", {"tamanho": 5})
        self.assertFalse(resultado["valido"])
        self.assertIn("tamanho deve ser 5 caracteres", resultado["erros"])

    def test_tamanho_minimo_e_maximo(self):
        resultado = validar("abc", {"tamanho_min": 2, "tamanho_max": 4})
        self.assertTrue(resultado["valido"])

    def test_prefixo_deve_ser_checado(self):
        resultado = validar("br123", {"prefixo": "BR"})
        self.assertTrue(resultado["valido"])
        resultado = validar("xx123", {"prefixo": "BR"})
        self.assertFalse(resultado["valido"])
        self.assertIn("deve começar com 'BR'", resultado["erros"])

    def test_somente_digitos_rejeita_letras(self):
        resultado = validar("br123", {"somente_digitos": True})
        self.assertFalse(resultado["valido"])
        self.assertIn("deve conter apenas dígitos", resultado["erros"])

    def test_padrao_regex_compara_com_valor_normalizado(self):
        resultado = validar("br-123", {"padrao": r"BR\d{3}"})
        self.assertTrue(resultado["valido"])

    def test_mod10_verifica_digito(self):
        resultado = validar("79927398713", {"digito_verificador": "mod10"})
        self.assertTrue(resultado["valido"])
        resultado = validar("79927398710", {"digito_verificador": "mod10"})
        self.assertFalse(resultado["valido"])
        self.assertIn("dígito verificador mod10 inválido", resultado["erros"])

    def test_mod11_verifica_digito(self):
        resultado = validar("12345678903", {"digito_verificador": "mod11"})
        self.assertTrue(resultado["valido"])
        resultado = validar("12345678900", {"digito_verificador": "mod11"})
        self.assertFalse(resultado["valido"])
        self.assertIn("dígito verificador mod11 inválido", resultado["erros"])

    def test_mesmo_identificador_ignora_normalizacao(self):
        self.assertTrue(mesmo_identificador("BR 123-456", "br123456"))
        self.assertTrue(mesmo_identificador("RFID 00012", "rfid00012"))

    def test_multiplos_erros_sao_acumulados(self):
        resultado = validar(
            "abc",
            {
                "tamanho": 5,
                "tamanho_min": 4,
                "tamanho_max": 2,
                "prefixo": "Z",
                "somente_digitos": True,
                "padrao": r"\d+",
                "digito_verificador": "mod10",
            },
        )
        self.assertFalse(resultado["valido"])
        self.assertGreaterEqual(len(resultado["erros"]), 1)

    def test_regras_padrao_existentes(self):
        self.assertIn("rfid", REGRAS_PADRAO)
        self.assertIn("sisbov", REGRAS_PADRAO)
        self.assertIn("manejo", REGRAS_PADRAO)
        self.assertIn("oficial_pnib", REGRAS_PADRAO)


if __name__ == "__main__":
    unittest.main()
