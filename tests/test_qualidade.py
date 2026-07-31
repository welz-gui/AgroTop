import unittest
from datetime import date, timedelta

from services.qualidade import avaliar_pesagem

HOJE = date.today()


def _dias_atras(n: int) -> str:
    return (HOJE - timedelta(days=n)).isoformat()


class TestQualidadePesagem(unittest.TestCase):
    def test_fora_de_faixa_zero(self):
        alerts = avaliar_pesagem(0.0, HOJE.isoformat(), [])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["tipo"], "fora_de_faixa")
        self.assertEqual(alerts[0]["severidade"], "alta")

    def test_fora_de_faixa_acima_do_limite(self):
        alerts = avaliar_pesagem(1501.0, HOJE.isoformat(), [])
        self.assertEqual(alerts[0]["tipo"], "fora_de_faixa")
        self.assertEqual(alerts[0]["severidade"], "alta")

    def test_data_futura(self):
        futura = (HOJE + timedelta(days=1)).isoformat()
        alerts = avaliar_pesagem(400.0, futura, [])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["tipo"], "data_futura")
        self.assertEqual(alerts[0]["severidade"], "alta")

    def test_sem_historico(self):
        alerts = avaliar_pesagem(400.0, HOJE.isoformat(), [])
        self.assertEqual(alerts, [])

    def test_duplicidade_mesma_data(self):
        alerts = avaliar_pesagem(400.0, HOJE.isoformat(), [{"peso": 400.0, "data": HOJE.isoformat()}])
        self.assertTrue(any(alert["tipo"] == "duplicidade" for alert in alerts))
        self.assertEqual(len(alerts), 1)

    def test_variacao_absurda_20_1_porcento(self):
        alerts = avaliar_pesagem(241.0, HOJE.isoformat(), [{"peso": 200.0, "data": _dias_atras(10)}])
        self.assertTrue(any(alert["tipo"] == "variacao_absurda" for alert in alerts))

    def test_variacao_absurda_20_0_porcento_nao_gera_alerta(self):
        alerts = avaliar_pesagem(240.0, HOJE.isoformat(), [{"peso": 200.0, "data": _dias_atras(10)}])
        self.assertFalse(any(alert["tipo"] == "variacao_absurda" for alert in alerts))

    def test_gmd_implausivel_3_1(self):
        alerts = avaliar_pesagem(403.0, HOJE.isoformat(), [{"peso": 300.0, "data": _dias_atras(30)}])
        self.assertTrue(any(alert["tipo"] == "gmd_implausivel" for alert in alerts))

    def test_gmd_implausivel_3_0_nao_gera_alerta(self):
        alerts = avaliar_pesagem(390.0, HOJE.isoformat(), [{"peso": 300.0, "data": _dias_atras(30)}])
        self.assertFalse(any(alert["tipo"] == "gmd_implausivel" for alert in alerts))

    def test_perda_de_peso(self):
        alerts = avaliar_pesagem(290.0, HOJE.isoformat(), [{"peso": 300.0, "data": _dias_atras(10)}])
        self.assertTrue(any(alert["tipo"] == "perda_de_peso" for alert in alerts))

    def test_multiplos_alertas_simultaneos(self):
        futura = (HOJE + timedelta(days=1)).isoformat()
        alerts = avaliar_pesagem(1600.0, futura, [{"peso": 100.0, "data": HOJE.isoformat()}])
        tipos = {alert["tipo"] for alert in alerts}
        self.assertIn("fora_de_faixa", tipos)
        self.assertIn("data_futura", tipos)
        self.assertIn("variacao_absurda", tipos)
        self.assertIn("gmd_implausivel", tipos)

if __name__ == "__main__":
    unittest.main()
