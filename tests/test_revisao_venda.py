"""Revisão de venda por cancelamento ou correção (plano de rastreabilidade, Fase 2).

Cancelar vale para a venda inteira (o lote, `lot_ref`, ou a venda avulsa): as linhas ficam, com motivo e
autor, saem de receita, custo e lucro, os animais voltam ao rebanho e as parcelas a receber em aberto
são canceladas. Corrigir cancela e grava a certa, ligada à original, na mesma transação.
"""

from datetime import timedelta

import database as db
from repositories import eventos
from repositories.animais import get_animal
from repositories.revisao import RegistroJaCancelado, RegistroNaoEncontrado, RevisaoNaoPermitida
from tests.test_regras_negocio import BaseRegras, HOJE


def _dia(n):
    return (HOJE - timedelta(days=n)).isoformat()


def _venda(ids, valor=10.0, modo="kg", tipo="criacao", **extra):
    return db.SaleParams(animal_ids=ids, sale_date=_dia(1), sale_type=tipo, pricing_mode=modo,
                         value=valor, buyer="Frigorífico X", operator="op", **extra)


class BaseVenda(BaseRegras):
    def setUp(self):
        super().setUp()
        self.animal("A1", peso=400.0)
        self.animal("A2", peso=300.0)

    def _status(self, aid):
        db.clear_cache()
        return get_animal(aid)["status"]

    def _linhas(self, incluir_canceladas=True):
        return db.get_sales(incluir_canceladas=incluir_canceladas)

    def _eventos(self, aid, tipo=None):
        return [e for e in sorted(eventos.do_animal(self._uuid(aid)), key=lambda e: e["id"])
                if tipo is None or e["tipo"] == tipo]

    def _receita(self):
        return db.get_financial_summary()["receita_total"]


class TestVendaGuardaOEvento(BaseVenda):
    def test_a_linha_da_venda_guarda_o_id_do_evento(self):
        db.register_sale(_venda(["A1"]))

        (linha,) = self._linhas()
        self.assertEqual(linha["evento_id"], self._eventos("A1", "venda")[0]["id"])

    def test_venda_avulsa_a_vista_nao_tem_lote(self):
        db.register_sale(_venda(["A1"]))
        self.assertIsNone(self._linhas()[0]["lot_ref"])

    def test_venda_a_prazo_avulsa_agora_tem_lote_para_ligar_as_parcelas(self):
        db.register_sale(_venda(["A1"], a_prazo=True, num_parcelas=2,
                                primeiro_vencimento=(HOJE + timedelta(days=30)).isoformat()))

        ref = self._linhas()[0]["lot_ref"]
        self.assertTrue(ref)
        self.assertEqual({c["lot_ref"] for c in db.listar_contas_receber()}, {ref})


class TestCancelarVenda(BaseVenda):
    def test_cancelar_tira_a_venda_das_somas_e_devolve_o_animal(self):
        db.register_sale(_venda(["A1"]))
        sid = self._linhas()[0]["id"]
        self.assertEqual(self._status("A1"), "vendido")
        self.assertEqual(self._receita(), 4000.0)

        r = db.cancelar_venda(sid, "animal errado", "Maria")

        self.assertEqual((r["cancelada"], r["animais"], r["parcelas_canceladas"]), ([sid], ["A1"], 0))
        self.assertEqual(self._status("A1"), "ativo")
        self.assertEqual(self._linhas(incluir_canceladas=False), [])
        self.assertEqual(self._receita(), 0)
        (linha,) = self._linhas()
        self.assertEqual((linha["cancelada_por"], linha["motivo_cancelamento"]), ("Maria", "animal errado"))

    def test_cancelar_grava_o_estorno_encadeado_e_a_trilha(self):
        db.register_sale(_venda(["A1"]))
        sid = self._linhas()[0]["id"]
        original = self._eventos("A1", "venda")[0]

        db.cancelar_venda(sid, "animal errado", "Maria")

        (estorno,) = self._eventos("A1", "estorno")
        self.assertEqual((estorno["evento_anterior_id"], estorno["versao"]), (original["id"], 2))
        (t,) = eventos.trilha(entidade="sales", entidade_id=str(sid))
        self.assertEqual((t["acao"], t["usuario"]), ("cancelar_venda", "Maria"))
        self.assertEqual(t["registro_anterior"]["total_value"], 4000.0)

    def test_cancelar_um_lote_cancela_todas_as_linhas_e_devolve_todos(self):
        db.register_sale(_venda(["A1", "A2"]))
        linhas = self._linhas()
        self.assertEqual(len(linhas), 2)
        self.assertTrue(linhas[0]["lot_ref"])

        r = db.cancelar_venda(linhas[1]["id"], "lote errado", "Maria")

        self.assertEqual(sorted(r["animais"]), ["A1", "A2"])
        self.assertEqual((self._status("A1"), self._status("A2")), ("ativo", "ativo"))
        self.assertEqual(self._linhas(incluir_canceladas=False), [])

    def test_sem_motivo_inexistente_ou_duas_vezes_nada_muda(self):
        db.register_sale(_venda(["A1"]))
        sid = self._linhas()[0]["id"]
        with self.assertRaises(RevisaoNaoPermitida):
            db.cancelar_venda(sid, " ", "Maria")
        with self.assertRaises(RegistroNaoEncontrado):
            db.cancelar_venda(999, "engano", "Maria")
        self.assertEqual(self._status("A1"), "vendido")

        db.cancelar_venda(sid, "engano", "Maria")
        with self.assertRaises(RegistroJaCancelado):
            db.cancelar_venda(sid, "de novo", "Maria")

    def test_cancelar_com_carencia_vigente_devolve_como_carencia(self):
        self.medicacao("A1", _dia(1), 30)
        db.register_sale(_venda(["A1"]))
        db.cancelar_venda(self._linhas()[0]["id"], "engano", "Maria")
        self.assertEqual(self._status("A1"), "carencia")


class TestCancelarVendaAPrazo(BaseVenda):
    def _a_prazo(self):
        db.register_sale(_venda(["A1", "A2"], a_prazo=True, num_parcelas=3,
                                primeiro_vencimento=(HOJE + timedelta(days=30)).isoformat()))
        return self._linhas()[0]["id"]

    def test_cancelar_cancela_as_parcelas_em_aberto(self):
        sid = self._a_prazo()
        self.assertEqual([c["status"] for c in db.listar_contas_receber()], ["aberto"] * 3)

        r = db.cancelar_venda(sid, "venda desfeita", "Maria")

        self.assertEqual(r["parcelas_canceladas"], 3)
        self.assertEqual([c["status"] for c in db.listar_contas_receber()], ["cancelado"] * 3)

    def test_parcela_ja_recebida_impede_e_nada_muda(self):
        sid = self._a_prazo()
        db.marcar_recebido(db.listar_contas_receber()[0]["id"], HOJE.isoformat())

        with self.assertRaises(RevisaoNaoPermitida) as ctx:
            db.cancelar_venda(sid, "venda desfeita", "Maria")

        self.assertIn("recebida", str(ctx.exception))
        self.assertEqual(self._status("A1"), "vendido")
        self.assertEqual(len(self._linhas(incluir_canceladas=False)), 2)
        self.assertEqual(sorted(c["status"] for c in db.listar_contas_receber()),
                         ["aberto", "aberto", "recebido"])

    def test_venda_a_prazo_anterior_ao_vinculo_com_as_parcelas_e_recusada(self):
        db.register_sale(_venda(["A1"]))
        sid = self._linhas()[0]["id"]
        self._sql("UPDATE sales SET a_prazo=1 WHERE id=?", (sid,))     # a prazo, sem lot_ref: como as antigas

        with self.assertRaises(RevisaoNaoPermitida) as ctx:
            db.cancelar_venda(sid, "engano", "Maria")

        self.assertIn("anterior ao vínculo", str(ctx.exception))
        self.assertEqual(self._status("A1"), "vendido")


class TestCorrigirVenda(BaseVenda):
    def test_corrigir_grava_a_certa_ligada_a_original(self):
        db.register_sale(_venda(["A1"], valor=10.0))
        original = self._linhas()[0]
        evento_original = self._eventos("A1", "venda")[0]

        r = db.corrigir_venda(original["id"], _venda(["A1"], valor=12.0), "preço errado", "Maria")

        self.assertEqual((r["receita"], r["n"]), (4800.0, 1))
        self.assertEqual(self._receita(), 4800.0)
        (nova,) = self._linhas(incluir_canceladas=False)
        self.assertEqual((nova["total_value"], nova["corrige_id"]), (4800.0, original["id"]))
        self.assertTrue([l for l in self._linhas() if l["id"] == original["id"]][0]["cancelada_em"])
        self.assertEqual(self._status("A1"), "vendido")
        novo_ev = [e for e in self._eventos("A1", "venda") if e["id"] != evento_original["id"]][0]
        self.assertEqual((novo_ev["evento_anterior_id"], novo_ev["versao"]), (evento_original["id"], 2))
        self.assertEqual(nova["evento_id"], novo_ev["id"])
        t = eventos.trilha(entidade="sales", entidade_id=str(original["id"]))[0]
        self.assertEqual((t["acao"], t["registro_posterior"]["receita"]), ("corrigir_venda", 4800.0))

    def test_o_peso_na_venda_e_o_do_registro_original_e_nao_o_de_hoje(self):
        db.register_sale(_venda(["A1"], valor=10.0))
        self._sql("UPDATE animals SET current_weight=500.0 WHERE id='A1'")

        db.corrigir_venda(self._linhas()[0]["id"], _venda(["A1"], valor=11.0), "preço errado", "Maria")

        (nova,) = self._linhas(incluir_canceladas=False)
        self.assertEqual((nova["weight_kg"], nova["total_value"]), (400.0, 4400.0))

    def test_o_lote_mantem_o_lot_ref_e_um_animal_retirado_volta_ao_rebanho(self):
        db.register_sale(_venda(["A1", "A2"]))
        original = self._linhas()
        ref = original[0]["lot_ref"]

        r = db.corrigir_venda(original[0]["id"], _venda(["A1"]), "A2 não foi vendido", "Maria")

        self.assertEqual(r["lot_ref"], ref)
        (nova,) = self._linhas(incluir_canceladas=False)
        self.assertEqual((nova["lot_ref"], nova["animal_id"]), (ref, "A1"))
        self.assertEqual((self._status("A1"), self._status("A2")), ("vendido", "ativo"))

    def test_um_animal_acrescentado_entra_ligado_a_venda(self):
        db.register_sale(_venda(["A1"]))
        original = self._linhas()[0]

        db.corrigir_venda(original["id"], _venda(["A1", "A2"]), "faltou um animal", "Maria")

        novas = self._linhas(incluir_canceladas=False)
        self.assertEqual(sorted(l["animal_id"] for l in novas), ["A1", "A2"])
        self.assertEqual({l["corrige_id"] for l in novas}, {original["id"]})
        self.assertEqual(len({l["lot_ref"] for l in novas}), 1)
        self.assertEqual(self._status("A2"), "vendido")

    def test_corrigir_a_prazo_cancela_as_parcelas_antigas_e_gera_as_novas(self):
        prazo = {"a_prazo": True, "primeiro_vencimento": (HOJE + timedelta(days=30)).isoformat()}
        db.register_sale(_venda(["A1"], valor=10.0, num_parcelas=2, **prazo))
        original = self._linhas()[0]

        r = db.corrigir_venda(original["id"], _venda(["A1"], valor=12.0, num_parcelas=4, **prazo),
                              "condição errada", "Maria")

        self.assertEqual((r["parcelas_canceladas"], r["parcelas_a_receber"]), (2, 4))
        status = sorted(c["status"] for c in db.listar_contas_receber())
        self.assertEqual(status, ["aberto"] * 4 + ["cancelado"] * 2)
        self.assertEqual({c["lot_ref"] for c in db.listar_contas_receber()}, {original["lot_ref"]})
        self.assertEqual(round(sum(c["valor"] for c in db.listar_contas_receber() if c["status"] == "aberto"), 2),
                         4800.0)

    def test_abate_em_carencia_na_correcao_recusa_e_a_original_continua_valendo(self):
        db.register_sale(_venda(["A1"], tipo="criacao"))
        original = self._linhas()[0]
        self.medicacao("A1", _dia(1), 30)

        with self.assertRaises(db.VendaBloqueadaPorCarencia):
            db.corrigir_venda(original["id"], _venda(["A1"], tipo="abate"), "tipo errado", "Maria")

        (linha,) = self._linhas()
        self.assertIsNone(linha["cancelada_em"], "a transação inteira volta atrás")
        self.assertEqual(self._status("A1"), "vendido")

    def test_corrigir_sem_motivo_ou_sem_animal_nada_muda(self):
        db.register_sale(_venda(["A1"]))
        sid = self._linhas()[0]["id"]
        with self.assertRaises(RevisaoNaoPermitida):
            db.corrigir_venda(sid, _venda(["A1"], valor=12.0), "", "Maria")
        with self.assertRaises(RevisaoNaoPermitida):
            db.corrigir_venda(sid, _venda(["NAO_EXISTE"]), "engano", "Maria")
        self.assertEqual(self._receita(), 4000.0)
        self.assertEqual(self._status("A1"), "vendido")


class TestCorrigirVendaTrocandoAnimais(BaseVenda):
    """A correção pode mudar QUEM está na venda. A tela de correção passa a permitir isso, então o
    repositório precisa sustentar: o retirado fica com a trilha fechada e só entra quem pode ser vendido."""

    def setUp(self):
        super().setUp()
        self.animal("A3", peso=350.0)

    def test_animal_retirado_da_venda_ganha_o_estorno_encadeado(self):
        db.register_sale(_venda(["A1", "A2"]))
        original = self._linhas()[0]
        venda_a2 = self._eventos("A2", "venda")[0]

        db.corrigir_venda(original["id"], _venda(["A1"]), "A2 não foi vendido", "Maria")

        (estorno,) = self._eventos("A2", "estorno")
        self.assertEqual((estorno["evento_anterior_id"], estorno["versao"]),
                         (venda_a2["id"], venda_a2["versao"] + 1))
        self.assertEqual((estorno["justificativa"], estorno["usuario_registro"]), ("A2 não foi vendido", "Maria"))
        self.assertEqual(self._status("A2"), "ativo")
        self.assertEqual(self._eventos("A1", "estorno"), [], "quem continua na venda não é estornado")

    def test_animal_acrescentado_que_ja_foi_vendido_em_outra_venda_e_recusado(self):
        db.register_sale(_venda(["A1"]))
        db.register_sale(_venda(["A2"]))
        sid = [l for l in self._linhas() if l["animal_id"] == "A1"][0]["id"]

        with self.assertRaises(RevisaoNaoPermitida) as ctx:
            db.corrigir_venda(sid, _venda(["A1", "A2"]), "faltou um", "Maria")

        self.assertIn("A2", str(ctx.exception))
        self.assertEqual(sorted(l["animal_id"] for l in self._linhas(incluir_canceladas=False)), ["A1", "A2"])
        self.assertTrue(all(not l["cancelada_em"] for l in self._linhas()), "a transação inteira volta atrás")
        self.assertEqual(self._receita(), 4000.0 + 3000.0)

    def test_animal_morto_nao_entra_na_venda(self):
        self._sql("UPDATE animals SET status='morto' WHERE id='A3'")
        db.register_sale(_venda(["A1"]))
        sid = self._linhas()[0]["id"]

        with self.assertRaises(RevisaoNaoPermitida):
            db.corrigir_venda(sid, _venda(["A1", "A3"]), "faltou um", "Maria")

        self.assertEqual(self._status("A3"), "morto")
        self.assertEqual([l["animal_id"] for l in self._linhas(incluir_canceladas=False)], ["A1"])

    def test_trocar_um_animal_por_outro_numa_so_correcao(self):
        db.register_sale(_venda(["A1", "A2"]))
        original = self._linhas()[0]

        db.corrigir_venda(original["id"], _venda(["A1", "A3"]), "foi o A3, não o A2", "Maria")

        novas = self._linhas(incluir_canceladas=False)
        self.assertEqual(sorted(l["animal_id"] for l in novas), ["A1", "A3"])
        self.assertEqual({l["lot_ref"] for l in novas}, {original["lot_ref"]})
        self.assertEqual((self._status("A1"), self._status("A2"), self._status("A3")),
                         ("vendido", "ativo", "vendido"))
        self.assertEqual(len(self._eventos("A2", "estorno")), 1)
        self.assertEqual(self._eventos("A3", "estorno"), [])
