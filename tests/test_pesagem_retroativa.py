"""Pesagem retroativa não sobrescreve o peso atual (D2 / ADR 0006).

A fila offline do mobile pode entregar uma pesagem de dias atrás depois de uma
mais nova. `add_weighing` fazia `UPDATE animals SET current_weight` sem olhar a
data, então o peso atual voltava para um valor velho. A pesagem sempre entra no
histórico; só vira peso atual se não houver nada mais recente.
"""

import unittest
from datetime import timedelta

import database as db
from repositories.animais import get_animal
from repositories.pesagens import WeighingCreate, add_weighing, get_weighings
from tests.test_regras_negocio import BaseRegras, HOJE


def _d(dias_atras):
    return (HOJE - timedelta(days=dias_atras)).isoformat()


def _pesar(aid, peso, dias_atras):
    return add_weighing(WeighingCreate(animal_id=aid, weight=peso, weigh_date=_d(dias_atras), operator="t"))


def _peso_atual(aid):
    db.clear_cache()
    return get_animal(aid)["current_weight"]


class TestPesagemRetroativa(BaseRegras):
    def test_pesagem_mais_nova_vira_peso_atual(self):
        a = self.animal("P1", peso=400.0)
        self.assertTrue(_pesar(a, 420.0, 2))
        self.assertEqual(_peso_atual(a), 420.0)

    def test_pesagem_retroativa_entra_no_historico_mas_nao_muda_o_peso_atual(self):
        a = self.animal("P2", peso=400.0)
        _pesar(a, 430.0, 2)

        virou = _pesar(a, 410.0, 5)

        self.assertFalse(virou)
        self.assertEqual(_peso_atual(a), 430.0)
        db.clear_cache()
        self.assertEqual(sorted(w["weight"] for w in get_weighings(a)), [410.0, 430.0])

    def test_ordem_de_chegada_nao_muda_o_resultado(self):
        """A mais nova chega primeiro ou por último: o peso atual é o da data mais nova."""
        a1 = self.animal("P3", peso=400.0)
        _pesar(a1, 410.0, 5)
        _pesar(a1, 430.0, 2)
        a2 = self.animal("P4", peso=400.0)
        _pesar(a2, 430.0, 2)
        _pesar(a2, 410.0, 5)

        self.assertEqual(_peso_atual(a1), 430.0)
        self.assertEqual(_peso_atual(a2), 430.0)

    def test_mesma_data_da_ultima_conta_como_mais_nova(self):
        """Repesar no mesmo dia continua corrigindo o peso atual, como sempre foi."""
        a = self.animal("P5", peso=400.0)
        _pesar(a, 420.0, 2)

        self.assertTrue(_pesar(a, 425.0, 2))
        self.assertEqual(_peso_atual(a), 425.0)

    def test_pesagem_anterior_a_entrada_sem_historico_nao_muda_o_peso_atual(self):
        a = self.animal("P6", peso=400.0, entrada=_d(10))

        virou = _pesar(a, 250.0, 30)

        self.assertFalse(virou)
        self.assertEqual(_peso_atual(a), 400.0)

    def test_primeira_pesagem_depois_da_entrada_vira_peso_atual(self):
        a = self.animal("P7", peso=300.0, entrada=_d(10))

        self.assertTrue(_pesar(a, 320.0, 3))
        self.assertEqual(_peso_atual(a), 320.0)

    def test_animal_inexistente_continua_levantando_value_error(self):
        with self.assertRaises(ValueError):
            _pesar("NAO-EXISTE", 400.0, 1)


if __name__ == "__main__":
    unittest.main()
