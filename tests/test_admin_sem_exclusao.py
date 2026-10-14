"""A tela de administração não exclui histórico do animal.

`admin_apply_changes` apagava linhas de qualquer tabela da lista, inclusive
pesagens, medicamentos, vendas, mortes e movimentações. Nas tabelas de histórico
(`ADMIN_SEM_EXCLUSAO`) a exclusão agora é recusada antes de qualquer escrita; editar
e acrescentar continuam possíveis, e as demais tabelas não mudam.
"""

import unittest
from datetime import timedelta

import database as db
from repositories.pesagens import WeighingCreate, add_weighing
from tests.test_regras_negocio import BaseRegras, HOJE


def _pesagens():
    with db._conn() as con:
        return [dict(r) for r in con.execute("SELECT * FROM weighings ORDER BY id").fetchall()]


class TestAdminSemExclusao(BaseRegras):
    def _pesagem(self, aid="A1"):
        self.animal(aid)
        add_weighing(WeighingCreate(
            animal_id=aid, weight=410.0, weigh_date=(HOJE - timedelta(days=1)).isoformat(), operator="t"))
        return _pesagens()[-1]

    def test_excluir_pesagem_pelo_admin_e_recusado_e_a_linha_continua(self):
        p = self._pesagem()

        with self.assertRaises(db.ExclusaoNaoPermitida) as ctx:
            db.admin_apply_changes("weighings", [], [], [p["id"]])

        self.assertIsInstance(ctx.exception, ValueError)
        self.assertIn("weighings", str(ctx.exception))
        self.assertEqual([x["id"] for x in _pesagens()], [p["id"]])

    def test_pedido_misto_editar_e_excluir_nao_grava_nada(self):
        p = self._pesagem()
        outra = dict(p, weight=999.0)

        with self.assertRaises(db.ExclusaoNaoPermitida):
            db.admin_apply_changes("weighings", [outra], [], [p["id"]])

        self.assertEqual(_pesagens()[0]["weight"], 410.0)

    def test_todas_as_tabelas_de_historico_recusam_exclusao(self):
        for tabela in sorted(db.ADMIN_SEM_EXCLUSAO):
            with self.subTest(tabela=tabela):
                self.assertIn(tabela, db.ADMIN_TABLES)
                with self.assertRaises(db.ExclusaoNaoPermitida):
                    db.admin_apply_changes(tabela, [], [], [1])

    def test_corrigir_e_acrescentar_em_tabela_de_historico_continuam_funcionando(self):
        p = self._pesagem()

        r = db.admin_apply_changes("weighings", [dict(p, weight=415.0)], [], [])
        self.assertEqual(r["updated"], 1)
        self.assertEqual(_pesagens()[0]["weight"], 415.0)

        nova = {"animal_uuid": p["animal_uuid"], "weight": 420.0,
                "weigh_date": HOJE.isoformat(), "method": "pesado"}
        r = db.admin_apply_changes("weighings", [], [nova], [])
        self.assertEqual(r["inserted"], 1)
        self.assertEqual(len(_pesagens()), 2)

    def test_tabelas_fora_da_lista_continuam_podendo_excluir(self):
        db.admin_apply_changes("fornecedores", [], [{"name": "Fornecedor de teste"}], [])
        with db._conn() as con:
            fid = con.execute("SELECT id FROM fornecedores WHERE name='Fornecedor de teste'").fetchone()["id"]

        r = db.admin_apply_changes("fornecedores", [], [], [fid])

        self.assertEqual(r["deleted"], 1)

    def test_a_lista_so_tem_tabelas_que_o_admin_enxerga(self):
        self.assertTrue(db.ADMIN_SEM_EXCLUSAO <= set(db.ADMIN_TABLES))


if __name__ == "__main__":
    unittest.main()
