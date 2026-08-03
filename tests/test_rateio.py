import unittest
from services.rateio import ratear


class TestRateio(unittest.TestCase):
    def test_lista_vazia(self):
        self.assertEqual(ratear(100.0, [], "igual"), [])

    def test_cento_por_tres_fecha(self):
        animais = [
            {"id": "a", "peso": 100.0, "dias_no_lote": 10},
            {"id": "b", "peso": 100.0, "dias_no_lote": 10},
            {"id": "c", "peso": 100.0, "dias_no_lote": 10},
        ]
        out = ratear(100.0, animais, "igual")
        soma = sum(x["valor"] for x in out)
        self.assertAlmostEqual(soma, 100.00, places=2)

    def test_peso_criterio_proporcional(self):
        animais = [
            {"id": "a", "peso": 1.0, "dias_no_lote": 1},
            {"id": "b", "peso": 3.0, "dias_no_lote": 1},
        ]
        out = ratear(40.0, animais, "peso")
        # expect a gets 10, b gets 30
        d = {x["animal_id"]: x["valor"] for x in out}
        self.assertAlmostEqual(d["a"], 10.00, places=2)
        self.assertAlmostEqual(d["b"], 30.00, places=2)

    def test_peso_dia(self):
        animais = [
            {"id": 1, "peso": 100.0, "dias_no_lote": 10},
            {"id": 2, "peso": 200.0, "dias_no_lote": 5},
        ]
        out = ratear(300.0, animais, "peso_dia")
        soma = sum(x["valor"] for x in out)
        self.assertAlmostEqual(soma, 300.0, places=2)

    def test_divisao_por_zero_nao_estoura(self):
        animais = [
            {"id": "x", "peso": 0.0, "dias_no_lote": 0},
            {"id": "y", "peso": 0.0, "dias_no_lote": 0},
        ]
        out = ratear(50.0, animais, "peso")
        soma = sum(x["valor"] for x in out)
        self.assertAlmostEqual(soma, 50.0, places=2)

    def test_valor_negativo_estorno(self):
        animais = [
            {"id": "a", "peso": 1.0, "dias_no_lote": 1},
            {"id": "b", "peso": 1.0, "dias_no_lote": 1},
        ]
        out = ratear(-10.0, animais, "igual")
        soma = sum(x["valor"] for x in out)
        self.assertAlmostEqual(soma, -10.0, places=2)


if __name__ == "__main__":
    unittest.main()
