"""Venda para abate não pode sair de animal ainda em carência.

A carência já bloqueava abate em movimentação (`services/movimentacao.py`) e em
GTA (`services/gta.py`), mas `register_sale` gravava a venda sem olhar. A regra
é a mesma daqueles dois: carência impede ABATE, não venda para criação.
"""

import unittest
from datetime import timedelta

import database as db
from repositories.animais import get_animal
from tests.test_regras_negocio import BaseRegras, HOJE


def get_status(aid):
    db.clear_cache()
    return get_animal(aid)["status"]


def _venda(ids, data, tipo="abate", modo="kg", valor=10.0):
    return db.SaleParams(animal_ids=ids, sale_date=data.isoformat(), sale_type=tipo,
                         pricing_mode=modo, value=valor)


class TestVendaEmCarencia(BaseRegras):
    def _em_carencia(self, aid, aplicado_ha=2, dias=10):
        """Aplicação há `aplicado_ha` dias, com `dias` de carência."""
        self.medicacao(aid, (HOJE - timedelta(days=aplicado_ha)).isoformat(), dias)
        return HOJE - timedelta(days=aplicado_ha) + timedelta(days=dias)   # fim

    def test_abate_de_animal_em_carencia_e_recusado_e_nada_e_gravado(self):
        a = self.animal("C1")
        fim = self._em_carencia(a)

        with self.assertRaises(db.VendaBloqueadaPorCarencia) as ctx:
            db.register_sale(_venda([a], HOJE))

        self.assertEqual(ctx.exception.bloqueados, {a: fim.isoformat()})
        self.assertIsInstance(ctx.exception, ValueError)
        self.assertEqual(db.get_sales(), [])
        self.assertEqual(get_status(a), "ativo")

    def test_venda_para_criacao_nao_e_travada_pela_carencia(self):
        a = self.animal("C2")
        self._em_carencia(a)

        r = db.register_sale(_venda([a], HOJE, tipo="criacao"))

        self.assertEqual(r["n"], 1)

    def test_um_dia_antes_do_fim_da_carencia_ainda_bloqueia(self):
        a = self.animal("C3")
        fim = self._em_carencia(a)

        with self.assertRaises(db.VendaBloqueadaPorCarencia):
            db.register_sale(_venda([a], fim - timedelta(days=1)))

    def test_no_dia_do_fim_da_carencia_o_abate_passa(self):
        """Mesmo critério de `get_withdrawal_end`: no dia do fim já está liberado."""
        a = self.animal("C4")
        fim = self._em_carencia(a)

        r = db.register_sale(_venda([a], fim))

        self.assertEqual(r["n"], 1)

    def test_carencia_vencida_nao_bloqueia(self):
        a = self.animal("C5")
        self._em_carencia(a, aplicado_ha=30, dias=10)

        self.assertEqual(db.register_sale(_venda([a], HOJE))["n"], 1)

    def test_animal_sem_carencia_nao_bloqueia(self):
        a = self.animal("C6")
        self.medicacao(a, HOJE.isoformat(), 0)

        self.assertEqual(db.register_sale(_venda([a], HOJE))["n"], 1)

    def test_lote_com_um_animal_em_carencia_recusa_o_lote_inteiro(self):
        livre = self.animal("C7")
        preso = self.animal("C8")
        self._em_carencia(preso)

        with self.assertRaises(db.VendaBloqueadaPorCarencia) as ctx:
            db.register_sale(_venda([livre, preso], HOJE, modo="lote", valor=10000.0))

        self.assertEqual(list(ctx.exception.bloqueados), [preso])
        self.assertEqual(db.get_sales(), [])
        self.assertEqual(get_status(livre), "ativo")

    def test_venda_retroativa_ignora_remedio_dado_depois(self):
        a = self.animal("C9")
        self.medicacao(a, (HOJE - timedelta(days=2)).isoformat(), 30)

        r = db.register_sale(_venda([a], HOJE - timedelta(days=10)))

        self.assertEqual(r["n"], 1)

    def test_a_mensagem_diz_quais_animais_e_ate_quando(self):
        a = self.animal("C10")
        fim = self._em_carencia(a)

        with self.assertRaises(db.VendaBloqueadaPorCarencia) as ctx:
            db.register_sale(_venda([a], HOJE))

        self.assertIn(a, str(ctx.exception))
        self.assertIn(fim.isoformat(), str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
