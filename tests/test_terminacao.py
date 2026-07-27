"""Testes do simulador de terminação (pasto × semi × confinamento)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db  # noqa: E402


CENARIOS = [
    {"nome": "Pasto",            "gmd": 0.5, "custo_dia":  3.5, "rendimento": 0.50},
    {"nome": "Confinamento",     "gmd": 1.5, "custo_dia": 14.0, "rendimento": 0.55},
]


class TestSimularTerminacao(unittest.TestCase):
    def test_calculo_basico(self):
        sim = db.simular_terminacao(380, 500, 300, CENARIOS)
        by = {s["nome"]: s for s in sim}
        # Pasto: 120 kg / 0.5 = 240 dias; custo = 240*3.5 = 840
        self.assertEqual(by["Pasto"]["dias"], 240)
        self.assertAlmostEqual(by["Pasto"]["custo_alimentar"], 840.0, places=2)
        # receita = 500*0.5/15*300 = 5000
        self.assertAlmostEqual(by["Pasto"]["receita"], 5000.0, places=2)
        # @ produzidas = 120*0.5/15 = 4.0
        self.assertAlmostEqual(by["Pasto"]["arrobas_produzidas"], 4.0, places=2)

    def test_ordena_por_lucro(self):
        sim = db.simular_terminacao(380, 500, 300, CENARIOS)
        lucros = [s["lucro"] for s in sim]
        self.assertEqual(lucros, sorted(lucros, reverse=True))

    def test_custo_boi_magro_reduz_lucro(self):
        sem = db.simular_terminacao(380, 500, 300, CENARIOS)[0]["lucro"]
        com = db.simular_terminacao(380, 500, 300, CENARIOS, custo_boi_magro=1000)[0]["lucro"]
        self.assertAlmostEqual(sem - com, 1000.0, places=2)

    def test_meta_invalida(self):
        # peso de abate <= peso atual → cenário sem dias/lucro
        sim = db.simular_terminacao(500, 480, 300, CENARIOS)
        self.assertTrue(all(s["dias"] is None and s["lucro"] is None for s in sim))
        self.assertTrue(all(not s["viavel"] for s in sim))

    def test_gmd_zero_nao_divide(self):
        cen = [{"nome": "Parado", "gmd": 0.0, "custo_dia": 5.0, "rendimento": 0.52}]
        sim = db.simular_terminacao(380, 500, 300, cen)
        self.assertIsNone(sim[0]["dias"])

    def test_defaults_disponiveis(self):
        self.assertEqual(len(db.TERMINACAO_DEFAULTS), 3)
        cen = db.get_terminacao_cenarios()
        self.assertTrue(all("gmd" in c and "rendimento" in c for c in cen))


if __name__ == "__main__":
    unittest.main()
