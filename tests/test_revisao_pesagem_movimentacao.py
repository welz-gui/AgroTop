"""Revisão de pesagem e movimentação (plano de rastreabilidade, Fase 2).

Mesmo desenho do tratamento (tests/test_correcao_tratamento.py): o registro errado não é
apagado nem editado; é cancelado ou substituído por outro que aponta para ele, com motivo e
autor. A linha cancelada permanece no histórico e sai de tudo que olha a situação vigente
(peso atual, GMD, piquete atual, datas do piquete).
"""

import sqlite3
import unittest
from datetime import timedelta

import database as db
from repositories import eventos
from repositories.animais import get_animal, get_last_movements_bulk, get_movements
from repositories.pesagens import get_weighings
from repositories.revisao import RegistroJaCancelado, RegistroNaoEncontrado, RevisaoNaoPermitida
from tests.test_regras_negocio import BaseRegras, HOJE


def _dia(n):
    """Data de n dias atrás, em texto ISO."""
    return (HOJE - timedelta(days=n)).isoformat()


class TestRevisaoPesagem(BaseRegras):
    def setUp(self):
        super().setUp()
        self.animal("A1", peso=300.0, peso_entrada=300.0, entrada=_dia(100))
        self.uuid = self._uuid("A1")

    def _id_da_data(self, data, peso):
        return [w for w in db.get_weighing_history("A1")
                if w["weigh_date"] == data and w["weight"] == peso][0]["id"]

    def _peso_atual(self):
        db.clear_cache()
        return get_animal("A1")["current_weight"]

    def _eventos(self, tipo=None):
        return [e for e in sorted(eventos.do_animal(self.uuid), key=lambda e: e["id"])
                if tipo is None or e["tipo"] == tipo]

    def _dados(self, peso, dias_atras, method="pesado"):
        return db.WeighingCreate("A1", peso, _dia(dias_atras), "", "", method)

    # ── vínculo com o evento ─────────────────────────────────────────────────
    def test_pesagem_guarda_o_id_do_evento(self):
        self._pesar(350.0, 30)
        linha = [x for x in db.get_weighing_history("A1") if x["weight"] == 350.0][0]
        self.assertEqual(linha["evento_id"], self._eventos("pesagem")[-1]["id"])
        self.assertIsNone(linha["cancelada_em"])

    def _pesar(self, peso, dias_atras):
        db.add_weighing(db.WeighingCreate("A1", peso, _dia(dias_atras), "op", "", "pesado"))
        db.clear_cache()

    # ── cancelar ─────────────────────────────────────────────────────────────
    def test_cancelar_a_mais_recente_devolve_o_peso_da_anterior(self):
        self._pesar(350.0, 30)
        self._pesar(380.0, 10)
        self.assertEqual(self._peso_atual(), 380.0)
        w = self._id_da_data(_dia(10), 380.0)

        r = db.cancelar_pesagem(w, "  digitei errado ", "ana")

        self.assertEqual(r["cancelada"], w)
        self.assertEqual(self._peso_atual(), 350.0)
        self.assertEqual([x["weight"] for x in get_weighings("A1")], [350.0])
        hist = [x for x in db.get_weighing_history("A1") if x["id"] == w][0]
        self.assertEqual((hist["cancelada_por"], hist["motivo_cancelamento"]), ("ana", "digitei errado"))

    def test_cancelar_uma_antiga_nao_mexe_no_peso_atual(self):
        self._pesar(350.0, 30)
        self._pesar(380.0, 10)
        db.cancelar_pesagem(self._id_da_data(_dia(30), 350.0), "erro", "ana")
        self.assertEqual(self._peso_atual(), 380.0)

    def test_cancelar_todas_volta_ao_peso_de_entrada(self):
        self._pesar(350.0, 30)
        db.cancelar_pesagem(self._id_da_data(_dia(30), 350.0), "erro", "ana")
        self.assertEqual(self._peso_atual(), 300.0)

    def test_gmd_ignora_a_cancelada(self):
        self._pesar(300.0, 31)
        self._pesar(330.0, 1)
        self.assertEqual(db.calculate_gmd("A1"), 1.0)
        db.cancelar_pesagem(self._id_da_data(_dia(1), 330.0), "erro", "ana")
        db.clear_cache()
        self.assertIsNone(db.calculate_gmd("A1"), "sobrou uma só pesagem vigente")

    def test_cancelar_exige_motivo_e_nao_grava_nada(self):
        self._pesar(350.0, 30)
        w = self._id_da_data(_dia(30), 350.0)
        antes = len(self._eventos())
        for vazio in ("", "   ", None):
            with self.assertRaises(RevisaoNaoPermitida):
                db.cancelar_pesagem(w, vazio, "ana")
        self.assertEqual(len(get_weighings("A1")), 1)
        self.assertEqual(len(self._eventos()), antes)

    def test_cancelar_duas_vezes_e_inexistente_e_de_outro_animal(self):
        self.animal("A2", peso=300.0)
        self._pesar(350.0, 30)
        w = self._id_da_data(_dia(30), 350.0)
        with self.assertRaises(RegistroNaoEncontrado):
            db.cancelar_pesagem(w, "erro", "ana", animal_id="A2")
        with self.assertRaises(RegistroNaoEncontrado):
            db.cancelar_pesagem(99999, "erro", "ana")
        db.cancelar_pesagem(w, "erro", "ana", animal_id="A1")
        with self.assertRaises(RegistroJaCancelado):
            db.cancelar_pesagem(w, "erro de novo", "ana")

    def test_pesagem_de_entrada_nao_se_cancela_nem_se_corrige(self):
        self._sql("INSERT INTO weighings (animal_uuid,weight,weigh_date,operator) VALUES(?,?,?,?)",
                  (self.uuid, 300.0, _dia(100), "Cadastro"))
        db.clear_cache()
        entrada = db.get_weighing_history("A1")[0]["id"]
        with self.assertRaises(RevisaoNaoPermitida):
            db.cancelar_pesagem(entrada, "erro", "ana")
        with self.assertRaises(RevisaoNaoPermitida):
            db.corrigir_pesagem(entrada, self._dados(310.0, 100), "erro", "ana")
        self.assertEqual(len(get_weighings("A1")), 1)

    def test_cancelar_grava_estorno_e_auditoria(self):
        self._pesar(350.0, 30)
        w = self._id_da_data(_dia(30), 350.0)
        db.cancelar_pesagem(w, "dose errada", "ana")
        original, estorno = self._eventos("pesagem")[-1], self._eventos("estorno")[-1]
        self.assertEqual(estorno["evento_anterior_id"], original["id"])
        self.assertEqual((estorno["versao"], estorno["justificativa"]), (2, "dose errada"))
        t = [x for x in eventos.trilha(entidade="weighings", entidade_id=str(w))
             if x["acao"] == "cancelar_pesagem"]
        self.assertEqual((len(t), t[0]["usuario"], t[0]["motivo"]), (1, "ana", "dose errada"))
        self.assertEqual(t[0]["registro_anterior"]["weight"], 350.0)

    def test_pesagem_nova_depois_de_cancelar_compara_so_com_as_vigentes(self):
        self._pesar(350.0, 30)
        self._pesar(380.0, 1)
        db.cancelar_pesagem(self._id_da_data(_dia(1), 380.0), "erro", "ana")
        # Mais antiga que a cancelada, mas mais nova que a única vigente: passa a ser o peso atual.
        self.assertTrue(db.add_weighing(db.WeighingCreate("A1", 360.0, _dia(5), "op")))
        self.assertEqual(self._peso_atual(), 360.0)

    # ── corrigir ─────────────────────────────────────────────────────────────
    def test_corrigir_troca_a_vigente_e_ajusta_o_peso_atual(self):
        self._pesar(380.0, 10)
        w = self._id_da_data(_dia(10), 380.0)

        r = db.corrigir_pesagem(w, self._dados(350.0, 10), "balança descalibrada", "ana")

        self.assertEqual(r["cancelada"], w)
        self.assertEqual(self._peso_atual(), 350.0)
        vigentes = get_weighings("A1")
        self.assertEqual([x["id"] for x in vigentes], [r["nova"]])
        self.assertEqual(vigentes[0]["corrige_id"], w)
        self.assertEqual(len(db.get_weighing_history("A1")), 2)

    def test_corrigir_encadeia_o_evento_novo_ao_original(self):
        self._pesar(380.0, 10)
        w = self._id_da_data(_dia(10), 380.0)
        r = db.corrigir_pesagem(w, self._dados(350.0, 10), "erro", "ana")
        evs = self._eventos("pesagem")
        self.assertEqual(len(evs), 2)
        self.assertEqual((evs[1]["evento_anterior_id"], evs[1]["versao"]), (evs[0]["id"], 2))
        self.assertEqual(evs[1]["justificativa"], "erro")
        nova = [x for x in db.get_weighing_history("A1") if x["id"] == r["nova"]][0]
        self.assertEqual(nova["evento_id"], evs[1]["id"])

    def test_corrigir_a_data_reordena_e_o_peso_atual_acompanha(self):
        self._pesar(350.0, 30)
        self._pesar(380.0, 10)
        w = self._id_da_data(_dia(10), 380.0)
        # A pesagem "mais recente" era de fato anterior à outra: o peso atual passa a ser o de 350.
        db.corrigir_pesagem(w, self._dados(380.0, 40), "data errada", "ana")
        self.assertEqual(self._peso_atual(), 350.0)

    def test_corrigir_mantem_o_piquete_da_original(self):
        self._pesar(380.0, 10)
        w = self._id_da_data(_dia(10), 380.0)
        self._sql("UPDATE weighings SET lote_id='P9' WHERE id=?", (w,))
        r = db.corrigir_pesagem(w, self._dados(350.0, 10), "erro", "ana")
        nova = [x for x in db.get_weighing_history("A1") if x["id"] == r["nova"]][0]
        self.assertEqual(nova["lote_id"], "P9")

    def test_corrigir_exige_motivo_e_de_outro_animal_e_404(self):
        self.animal("A2", peso=300.0)
        self._pesar(380.0, 10)
        w = self._id_da_data(_dia(10), 380.0)
        with self.assertRaises(RevisaoNaoPermitida):
            db.corrigir_pesagem(w, self._dados(350.0, 10), " ", "ana")
        outro = db.WeighingCreate("A2", 350.0, _dia(10), "", "", "pesado")
        with self.assertRaises(RegistroNaoEncontrado):
            db.corrigir_pesagem(w, outro, "erro", "ana")
        self.assertEqual([x["id"] for x in get_weighings("A1")], [w])

    def test_corrigir_a_ja_corrigida_recusa_e_a_correcao_forma_cadeia(self):
        self._pesar(380.0, 10)
        w = self._id_da_data(_dia(10), 380.0)
        r1 = db.corrigir_pesagem(w, self._dados(370.0, 10), "erro 1", "ana")
        with self.assertRaises(RegistroJaCancelado):
            db.corrigir_pesagem(w, self._dados(360.0, 10), "erro", "ana")
        r2 = db.corrigir_pesagem(r1["nova"], self._dados(360.0, 10), "erro 2", "ana")
        self.assertEqual([e["versao"] for e in self._eventos("pesagem")], [1, 2, 3])
        self.assertEqual([x["id"] for x in get_weighings("A1")], [r2["nova"]])
        self.assertEqual(self._peso_atual(), 360.0)



class TestRevisaoMovimentacao(BaseRegras):
    def setUp(self):
        super().setUp()
        con = sqlite3.connect(db.DB_PATH)
        try:
            prop = con.execute("SELECT id FROM properties ORDER BY created_at LIMIT 1").fetchone()[0]
            for lid in ("P1", "P2", "P3"):
                con.execute("INSERT INTO lotes (id,name,property_id) VALUES(?,?,?)",
                            (lid, f"Piquete {lid}", prop))
            con.commit()
        finally:
            con.close()
        self.animal("A1", lote="P1")
        self.uuid = self._uuid("A1")

    def _mover(self, animal, destino, dias_atras=0, razao="manejo"):
        db.move_animal(animal, db.MovementParams(destino, _dia(dias_atras), razao, "op"))
        db.clear_cache()

    def _lote(self, aid="A1"):
        db.clear_cache()
        return get_animal(aid)["lote_id"]

    def _mov_id(self, de, para):
        return [m for m in get_movements("A1", incluir_canceladas=True)
                if m["from_lote_id"] == de and m["to_lote_id"] == para][0]["id"]

    def _lote_linha(self, lid):
        con = sqlite3.connect(db.DB_PATH)
        con.row_factory = sqlite3.Row
        try:
            return dict(con.execute("SELECT * FROM lotes WHERE id=?", (lid,)).fetchone())
        finally:
            con.close()

    def _eventos(self, tipo=None):
        return [e for e in sorted(eventos.do_animal(self.uuid), key=lambda e: e["id"])
                if tipo is None or e["tipo"] == tipo]

    # ── vínculo com o evento ─────────────────────────────────────────────────
    def test_movimentacao_guarda_o_id_do_evento(self):
        self._mover("A1", "P2")
        m = get_movements("A1")[0]
        self.assertEqual(m["evento_id"], self._eventos("mudanca_lote")[-1]["id"])

    def test_movimentacao_em_lote_tambem_guarda_o_id_do_evento(self):
        self.animal("A2", lote="P1")
        db.move_animals_bulk(["A1", "A2"], db.MovementParams("P2", _dia(0), "manejo", "op"))
        db.clear_cache()
        for aid in ("A1", "A2"):
            uuid = self._uuid(aid)
            m = get_movements(aid)[0]
            ev = [e for e in eventos.do_animal(uuid) if e["tipo"] == "mudanca_lote"]
            self.assertEqual(len(ev), 1)
            self.assertEqual(m["evento_id"], ev[0]["id"])

    # ── cancelar ─────────────────────────────────────────────────────────────
    def test_cancelar_devolve_o_animal_ao_piquete_de_origem(self):
        self._mover("A1", "P2", 3)
        m = self._mov_id("P1", "P2")

        r = db.cancelar_movimentacao(m, "  piquete errado ", "ana")

        self.assertEqual((r["cancelada"], r["devolvido_a"]), (m, "P1"))
        self.assertEqual(self._lote(), "P1")
        self.assertEqual(get_movements("A1"), [], "a vigente sai do histórico padrão")
        todas = get_movements("A1", incluir_canceladas=True)
        self.assertEqual((todas[0]["cancelada_por"], todas[0]["motivo_cancelamento"]),
                         ("ana", "piquete errado"))

    def test_cancelar_refaz_as_datas_do_piquete(self):
        self._mover("A1", "P2", 3)
        self.assertEqual(self._lote_linha("P2")["last_entry_date"], _dia(3))
        self.assertEqual(self._lote_linha("P1")["last_exit_date"], _dia(3))
        db.cancelar_movimentacao(self._mov_id("P1", "P2"), "erro", "ana")
        self.assertIsNone(self._lote_linha("P2")["last_entry_date"])
        self.assertIsNone(self._lote_linha("P1")["last_exit_date"])

    def test_cancelar_nao_apaga_data_que_vem_de_outra_movimentacao(self):
        self.animal("A2", lote="P1")
        self._mover("A2", "P2", 1)          # outra movimentação define a entrada em P2
        self._mover("A1", "P2", 5)
        db.cancelar_movimentacao(self._mov_id("P1", "P2"), "erro", "ana", animal_id="A1")
        self.assertEqual(self._lote_linha("P2")["last_entry_date"], _dia(1))

    def test_cancelar_grava_estorno_e_auditoria(self):
        self._mover("A1", "P2")
        m = self._mov_id("P1", "P2")
        db.cancelar_movimentacao(m, "erro", "ana")
        original, estorno = self._eventos("mudanca_lote")[-1], self._eventos("estorno")[-1]
        self.assertEqual(estorno["evento_anterior_id"], original["id"])
        self.assertEqual((estorno["versao"], estorno["justificativa"]), (2, "erro"))
        t = [x for x in eventos.trilha(entidade="animal_movements", entidade_id=str(m))
             if x["acao"] == "cancelar_movimentacao"]
        self.assertEqual((len(t), t[0]["usuario"]), (1, "ana"))

    def test_cancelar_exige_motivo_e_nao_grava_nada(self):
        self._mover("A1", "P2")
        m = self._mov_id("P1", "P2")
        antes = len(self._eventos())
        with self.assertRaises(RevisaoNaoPermitida):
            db.cancelar_movimentacao(m, "  ", "ana")
        self.assertEqual(self._lote(), "P2")
        self.assertEqual(len(self._eventos()), antes)

    def test_so_a_ultima_movimentacao_se_cancela(self):
        self._mover("A1", "P2", 5)
        self._mover("A1", "P3", 2)
        primeira, segunda = self._mov_id("P1", "P2"), self._mov_id("P2", "P3")
        with self.assertRaises(RevisaoNaoPermitida):
            db.cancelar_movimentacao(primeira, "erro", "ana")
        self.assertEqual(self._lote(), "P3")
        db.cancelar_movimentacao(segunda, "erro", "ana")
        db.cancelar_movimentacao(primeira, "erro", "ana")      # agora é a última vigente
        self.assertEqual(self._lote(), "P1")

    def test_animal_que_ja_saiu_do_destino_nao_volta(self):
        self._mover("A1", "P2")
        m = self._mov_id("P1", "P2")
        self._sql("UPDATE animals SET lote_id='P3' WHERE id='A1'")    # mudou sem registro
        with self.assertRaises(RevisaoNaoPermitida):
            db.cancelar_movimentacao(m, "erro", "ana")
        self.assertEqual(self._lote(), "P3")

    def test_entrada_do_animal_nao_se_cancela(self):
        self._sql("INSERT INTO animal_movements (animal_uuid,from_lote_id,to_lote_id,movement_date,reason)"
                  " VALUES(?,?,?,?,?)", (self.uuid, None, "P1", _dia(100), "entrada"))
        entrada = get_movements("A1")[0]["id"]
        with self.assertRaises(RevisaoNaoPermitida):
            db.cancelar_movimentacao(entrada, "erro", "ana")

    def test_cancelar_duas_vezes_inexistente_e_de_outro_animal(self):
        self.animal("A2", lote="P1")
        self._mover("A1", "P2")
        m = self._mov_id("P1", "P2")
        with self.assertRaises(RegistroNaoEncontrado):
            db.cancelar_movimentacao(m, "erro", "ana", animal_id="A2")
        with self.assertRaises(RegistroNaoEncontrado):
            db.cancelar_movimentacao(99999, "erro", "ana")
        db.cancelar_movimentacao(m, "erro", "ana")
        with self.assertRaises(RegistroJaCancelado):
            db.cancelar_movimentacao(m, "de novo", "ana")

    def test_ultima_movimentacao_ignora_a_cancelada(self):
        self._mover("A1", "P2", 5)
        self.assertEqual(get_last_movements_bulk(["A1"]), {"A1": _dia(5)})
        db.cancelar_movimentacao(self._mov_id("P1", "P2"), "erro", "ana")
        self.assertEqual(get_last_movements_bulk(["A1"]), {})

    def test_movimentacao_revisavel(self):
        self.assertIsNone(db.movimentacao_revisavel("A1"), "sem movimentação")
        self._mover("A1", "P2", 5)
        self._mover("A1", "P3", 2)
        self.assertEqual(db.movimentacao_revisavel("A1")["to_lote_id"], "P3")
        self._sql("UPDATE animals SET lote_id='P1' WHERE id='A1'")
        db.clear_cache()
        self.assertIsNone(db.movimentacao_revisavel("A1"), "o animal já saiu do destino")
        self.assertIsNone(db.movimentacao_revisavel("NAO_EXISTE"))

    # ── corrigir ─────────────────────────────────────────────────────────────
    def test_corrigir_leva_o_animal_ao_destino_certo_a_partir_da_origem(self):
        self._mover("A1", "P2", 3)
        m = self._mov_id("P1", "P2")

        r = db.corrigir_movimentacao(
            m, db.MovementParams("P3", _dia(3), "manejo", ""), "era o P3", "ana")

        self.assertEqual(self._lote(), "P3")
        self.assertEqual(r["cancelada"], m)
        vigentes = get_movements("A1")
        self.assertEqual([(x["from_lote_id"], x["to_lote_id"]) for x in vigentes], [("P1", "P3")])
        self.assertEqual(vigentes[0]["corrige_id"], m)
        self.assertEqual(vigentes[0]["operator"], "op", "mantém quem movimentou")
        self.assertEqual(len(get_movements("A1", incluir_canceladas=True)), 2)

    def test_corrigir_encadeia_o_evento_novo_ao_original(self):
        self._mover("A1", "P2", 3)
        m = self._mov_id("P1", "P2")
        db.corrigir_movimentacao(m, db.MovementParams("P3", _dia(3), "manejo", ""), "era o P3", "ana")
        evs = self._eventos("mudanca_lote")
        self.assertEqual(len(evs), 2)
        self.assertEqual((evs[1]["evento_anterior_id"], evs[1]["versao"]), (evs[0]["id"], 2))
        self.assertEqual(evs[1]["justificativa"], "era o P3")
        self.assertEqual(get_movements("A1")[0]["evento_id"], evs[1]["id"])

    def test_corrigir_para_a_origem_e_cancelar_e_nada_muda(self):
        self._mover("A1", "P2")
        m = self._mov_id("P1", "P2")
        with self.assertRaises(RevisaoNaoPermitida):
            db.corrigir_movimentacao(m, db.MovementParams("P1", _dia(0), "manejo", ""), "erro", "ana")
        self.assertEqual(self._lote(), "P2")
        self.assertEqual([x["id"] for x in get_movements("A1")], [m])

    def test_corrigir_para_piquete_inexistente_recusa(self):
        self._mover("A1", "P2")
        m = self._mov_id("P1", "P2")
        with self.assertRaises(RevisaoNaoPermitida):
            db.corrigir_movimentacao(m, db.MovementParams("XX", _dia(0), "manejo", ""), "erro", "ana")
        self.assertEqual(self._lote(), "P2")

    def test_corrigir_exige_motivo_e_so_a_ultima(self):
        self._mover("A1", "P2", 5)
        self._mover("A1", "P3", 2)
        primeira = self._mov_id("P1", "P2")
        with self.assertRaises(RevisaoNaoPermitida):
            db.corrigir_movimentacao(primeira, db.MovementParams("P3", _dia(5), "manejo", ""), "erro", "ana")
        segunda = self._mov_id("P2", "P3")
        with self.assertRaises(RevisaoNaoPermitida):
            db.corrigir_movimentacao(segunda, db.MovementParams("P1", _dia(2), "manejo", ""), " ", "ana")
        self.assertEqual(self._lote(), "P3")



if __name__ == "__main__":
    unittest.main()
