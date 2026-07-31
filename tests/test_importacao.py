"""Testes do parser puro de pesagens em CSV."""

from datetime import date, timedelta
import unittest

from services.importacao import parse_pesagens


class TestParsePesagens(unittest.TestCase):
    def test_caminho_feliz(self):
        resultado = parse_pesagens(
            "BR0001,450.5,2026-01-10\nBR0002,512,2026-02-20"
        )

        self.assertEqual(
            resultado["aceitas"],
            [
                {"animal_id": "BR0001", "peso": 450.5, "data": "2026-01-10"},
                {"animal_id": "BR0002", "peso": 512.0, "data": "2026-02-20"},
            ],
        )
        self.assertEqual(resultado["rejeitadas"], [])
        self.assertEqual(resultado["total_linhas"], 2)

    def test_detecta_os_dois_separadores(self):
        for texto in (
            "BR0001,450.5,2026-01-10",
            "BR0001;450.5;2026-01-10",
        ):
            with self.subTest(texto=texto):
                resultado = parse_pesagens(texto)
                self.assertEqual(len(resultado["aceitas"]), 1)

    def test_aceita_os_dois_formatos_de_data_e_devolve_iso(self):
        resultado = parse_pesagens(
            "BR0001;450;2026-01-10\nBR0002;460;11/01/2026"
        )

        self.assertEqual(
            [item["data"] for item in resultado["aceitas"]],
            ["2026-01-10", "2026-01-11"],
        )

    def test_aceita_decimal_com_virgula(self):
        resultado = parse_pesagens("BR0001;450,5;10/01/2026")

        self.assertEqual(resultado["aceitas"][0]["peso"], 450.5)

    def test_rejeita_colunas_de_menos(self):
        resultado = parse_pesagens("BR0001,450")

        self.assertEqual(
            resultado["rejeitadas"][0]["motivo"],
            "esperado 3 colunas, encontrado 2",
        )

    def test_rejeita_peso_nao_numerico(self):
        resultado = parse_pesagens("BR0001,abc,2026-01-10")

        self.assertEqual(
            resultado["rejeitadas"][0]["motivo"], "peso inválido: 'abc'"
        )

    def test_rejeita_peso_fora_da_faixa(self):
        for peso in ("0", "-1", "1500.1", "2300"):
            with self.subTest(peso=peso):
                resultado = parse_pesagens(f"BR0001,{peso},2026-01-10")
                self.assertIn(
                    "peso fora da faixa plausível",
                    resultado["rejeitadas"][0]["motivo"],
                )

    def test_rejeita_data_invalida(self):
        resultado = parse_pesagens("BR0001,450,32/13/2026")

        self.assertEqual(
            resultado["rejeitadas"][0]["motivo"],
            "data inválida: '32/13/2026'",
        )

    def test_rejeita_data_no_futuro(self):
        futura = (date.today() + timedelta(days=1)).isoformat()
        resultado = parse_pesagens(f"BR0001,450,{futura}")

        self.assertEqual(
            resultado["rejeitadas"][0]["motivo"], f"data no futuro: {futura}"
        )

    def test_rejeita_brinco_desconhecido_quando_ids_sao_informados(self):
        resultado = parse_pesagens(
            "BR9999,450,2026-01-10", ids_conhecidos={"BR0001"}
        )

        self.assertEqual(
            resultado["rejeitadas"][0]["motivo"],
            "animal não encontrado: BR9999",
        )

    def test_nao_valida_brinco_quando_ids_nao_sao_informados(self):
        resultado = parse_pesagens("BR9999,450,2026-01-10")

        self.assertEqual(len(resultado["aceitas"]), 1)

    def test_rejeita_brinco_vazio(self):
        resultado = parse_pesagens(",450,2026-01-10")

        self.assertEqual(resultado["rejeitadas"][0]["motivo"], "brinco vazio")

    def test_arquivo_vazio(self):
        self.assertEqual(
            parse_pesagens("\n  \n"),
            {"aceitas": [], "rejeitadas": [], "total_linhas": 0},
        )

    def test_so_cabecalho(self):
        resultado = parse_pesagens("animal_id,peso,data")

        self.assertEqual(
            resultado,
            {"aceitas": [], "rejeitadas": [], "total_linhas": 0},
        )

    def test_arquivo_misto_ignora_vazias_e_preserva_numero_da_linha(self):
        resultado = parse_pesagens(
            "brinco;peso;data\n"
            "BR0001;450,5;10/01/2026\n"
            "\n"
            "BR0002;abc;11/01/2026\n"
            "BR0003;470;12/01/2026"
        )

        self.assertEqual(len(resultado["aceitas"]), 2)
        self.assertEqual(len(resultado["rejeitadas"]), 1)
        self.assertEqual(resultado["rejeitadas"][0]["linha"], 4)
        self.assertEqual(resultado["rejeitadas"][0]["conteudo"], "BR0002;abc;11/01/2026")
        self.assertEqual(resultado["total_linhas"], 3)


if __name__ == "__main__":
    unittest.main()
