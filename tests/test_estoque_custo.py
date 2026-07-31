import unittest
from services.estoque import custo_medio_ponderado


class TestCustoMedioPonderado(unittest.TestCase):
    def test_calculo_normal(self):
        """Testa o cálculo do custo médio ponderado em um cenário normal."""
        resultado = custo_medio_ponderado(
            saldo_atual=100.0,
            custo_atual=2.0,
            quantidade_entrada=100.0,
            custo_entrada=4.0,
        )
        self.assertEqual(resultado, 3.0)

    def test_estoque_zerado(self):
        """Testa entrada quando o estoque atual é zero (deve assumir custo da entrada)."""
        resultado = custo_medio_ponderado(
            saldo_atual=0.0,
            custo_atual=2.5,
            quantidade_entrada=50.0,
            custo_entrada=6.0,
        )
        self.assertEqual(resultado, 6.0)

    def test_estoque_negativo(self):
        """Testa entrada quando o estoque atual é negativo (baixa antes da compra).

        Neste caso, o saldo anterior negativo não distorce o cálculo e o custo
        passa a ser o da nova entrada.
        """
        resultado = custo_medio_ponderado(
            saldo_atual=-10.0,
            custo_atual=2.0,
            quantidade_entrada=50.0,
            custo_entrada=5.5,
        )
        self.assertEqual(resultado, 5.5)

    def test_quantidade_entrada_zero(self):
        """Testa entrada com quantidade zero (custo permanece inalterado, sem divisão por zero)."""
        resultado = custo_medio_ponderado(
            saldo_atual=100.0,
            custo_atual=4.5,
            quantidade_entrada=0.0,
            custo_entrada=10.0,
        )
        self.assertEqual(resultado, 4.5)

    def test_custo_entrada_zero_doacao_ou_brinde(self):
        """Testa entrada com custo zero (doação/brinde é entrada válida)."""
        resultado = custo_medio_ponderado(
            saldo_atual=100.0,
            custo_atual=10.0,
            quantidade_entrada=100.0,
            custo_entrada=0.0,
        )
        self.assertEqual(resultado, 5.0)

    def test_arredondamento_dizima(self):
        """Testa se valores com dízima periódica são corretamente arredondados para 2 casas."""
        resultado = custo_medio_ponderado(
            saldo_atual=10.0,
            custo_atual=10.0,
            quantidade_entrada=20.0,
            custo_entrada=11.0,
        )
        self.assertEqual(resultado, 10.67)

    def test_tres_entradas_sequenciais(self):
        """Testa a evolução da média ponderada ao longo de 3 entradas consecutivas."""
        saldo = 0.0
        custo = 0.0

        # Entrada 1: 100 kg a R$ 10,00
        custo = custo_medio_ponderado(
            saldo_atual=saldo,
            custo_atual=custo,
            quantidade_entrada=100.0,
            custo_entrada=10.0,
        )
        saldo += 100.0
        self.assertEqual(custo, 10.0)
        self.assertEqual(saldo, 100.0)

        # Entrada 2: 100 kg a R$ 20,00
        custo = custo_medio_ponderado(
            saldo_atual=saldo,
            custo_atual=custo,
            quantidade_entrada=100.0,
            custo_entrada=20.0,
        )
        saldo += 100.0
        self.assertEqual(custo, 15.0)
        self.assertEqual(saldo, 200.0)

        # Entrada 3: 300 kg a R$ 5,00
        custo = custo_medio_ponderado(
            saldo_atual=saldo,
            custo_atual=custo,
            quantidade_entrada=300.0,
            custo_entrada=5.0,
        )
        saldo += 300.0
        self.assertEqual(custo, 9.0)
        self.assertEqual(saldo, 500.0)


if __name__ == "__main__":
    unittest.main()
