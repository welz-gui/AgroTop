import unittest
from unittest.mock import patch

from services.arquivo_dispositivos import conferir_pareamento, ler


class TestLerArquivoDispositivos(unittest.TestCase):
    def test_texto_vazio(self):
        self.assertEqual(
            ler(""),
            {
                "aceitos": [],
                "rejeitados": [],
                "duplicados_no_arquivo": [],
                "total_linhas": 0,
                "colunas_detectadas": [],
            },
        )

    def test_cabecalho_com_acentos_caixa_e_ponto_e_virgula(self):
        resultado = ler(
            "Código Eletrônico;CÓDIGO VISUAL;Fabricante\n"
            "9820000000BR0001;BR0001;BovTag"
        )

        self.assertEqual(
            resultado["colunas_detectadas"],
            ["codigo_eletronico", "codigo_visual", "fabricante"],
        )
        self.assertEqual(resultado["total_linhas"], 1)
        self.assertEqual(resultado["aceitos"][0]["codigo_visual"], "BR0001")
        self.assertEqual(
            resultado["aceitos"][0]["codigo_eletronico"],
            "9820000000BR0001",
        )
        self.assertEqual(resultado["aceitos"][0]["fabricante"], "BovTag")

    def test_sem_cabecalho_primeira_linha_e_dado(self):
        resultado = ler("BR0001,9820000000BR0001\nBR0002,9820000000BR0002")

        self.assertEqual(
            resultado["colunas_detectadas"],
            ["codigo_visual", "codigo_eletronico"],
        )
        self.assertEqual(
            [item["codigo_visual"] for item in resultado["aceitos"]],
            ["BR0001", "BR0002"],
        )
        self.assertEqual(resultado["total_linhas"], 2)

    def test_duplicado_fica_uma_vez_nos_aceitos_e_na_lista(self):
        resultado = ler(
            "codigo_visual;codigo_eletronico\n"
            "BR0001;E1\n"
            "br0001;E1\n"
            "BR0001;E1"
        )

        self.assertEqual(len(resultado["aceitos"]), 1)
        self.assertEqual(resultado["duplicados_no_arquivo"], ["br0001"])
        self.assertEqual(len(resultado["rejeitados"]), 2)
        self.assertTrue(
            all("duplicado" in item["motivo"] for item in resultado["rejeitados"])
        )

    def test_linha_vazia_e_rodape_sao_rejeitados(self):
        resultado = ler(
            "codigo_visual;codigo_eletronico\n"
            "BR0001;E1\n"
            "\n"
            "Total: 100"
        )

        self.assertEqual(resultado["total_linhas"], 3)
        self.assertEqual(
            [(item["linha"], item["motivo"]) for item in resultado["rejeitados"]],
            [
                (3, "linha vazia"),
                (4, "rodapé de totais não é um dispositivo"),
            ],
        )

    def test_linha_ruim_antes_do_cabecalho_nao_impede_as_demais(self):
        resultado = ler(
            "\n"
            "codigo_visual;codigo_eletronico\n"
            "BR0001;E1"
        )

        self.assertEqual(resultado["total_linhas"], 2)
        self.assertEqual(resultado["rejeitados"][0]["linha"], 1)
        self.assertEqual(resultado["aceitos"][0]["codigo_visual"], "BR0001")

    def test_codigo_visual_vazio_rejeita_so_a_linha_ruim(self):
        resultado = ler(
            "codigo visual;modelo;lote\n"
            ";M1;L1\n"
            "BR0002;M2;L1"
        )

        self.assertEqual([item["codigo_visual"] for item in resultado["aceitos"]], ["BR0002"])
        self.assertEqual(resultado["rejeitados"][0]["linha"], 2)
        self.assertIn("visual vazio", resultado["rejeitados"][0]["motivo"])

    def test_dez_mil_linhas(self):
        linhas = ["codigo_visual,codigo_eletronico"]
        linhas.extend(f"BR{numero:05d},E{numero:05d}" for numero in range(10_000))

        resultado = ler("\n".join(linhas))

        self.assertEqual(len(resultado["aceitos"]), 10_000)
        self.assertEqual(resultado["rejeitados"], [])
        self.assertEqual(resultado["total_linhas"], 10_000)


class TestConferirPareamento(unittest.TestCase):
    def test_prefixo_eletronico_confere_pelos_seis_ultimos_caracteres(self):
        divergencias = conferir_pareamento(
            [
                {
                    "codigo_visual": "BR0001",
                    "codigo_eletronico": "9820000000BR0001",
                }
            ],
            digitos_comparados=6,
        )

        self.assertEqual(divergencias, [])

    def test_retorna_apenas_divergencias(self):
        divergencias = conferir_pareamento(
            [
                {"codigo_visual": "BR0001", "codigo_eletronico": "BR0001"},
                {"codigo_visual": "BR0002", "codigo_eletronico": "BR9999"},
            ]
        )

        self.assertEqual(
            divergencias,
            [
                {
                    "codigo_visual": "BR0002",
                    "codigo_eletronico": "BR9999",
                    "divergencia": "codigos_divergentes",
                }
            ],
        )

    @patch("services.arquivo_dispositivos.conferir_codigos")
    def test_delega_a_conferencia_ao_servico_existente(self, conferir):
        conferir.return_value = {
            "confere": False,
            "divergencia": "resultado_do_servico",
            "mensagem": "",
        }

        resultado = conferir_pareamento(
            [{"codigo_visual": "V1", "codigo_eletronico": "E1"}],
            digitos_comparados=4,
        )

        conferir.assert_called_once_with("V1", "E1", digitos_comparados=4)
        self.assertEqual(resultado[0]["divergencia"], "resultado_do_servico")


if __name__ == "__main__":
    unittest.main()
