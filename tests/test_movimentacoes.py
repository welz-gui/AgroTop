"""Movimentação entre propriedades (ADR 0004 · B6 · PNIB §8).

A regra pura é `services/movimentacao.py`. Estes testes travam a **ligação** e,
principalmente, o que o §8.4 exige: **três níveis com efeitos diferentes**.

Confundir alerta com bloqueio trava o usuário sem prova; confundir bloqueio com
alerta deixa sair animal morto. A gravidade é a regra, não um enfeite — e é o
que estes testes verificam.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402
from repositories import eventos, movimentacoes, propriedades  # noqa: E402

HOJE = date.today().isoformat()


class BaseB6(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "b6.db"))
        db.init_db()
        db.clear_cache()

        self.origem = propriedades.padrao()
        self.destino_id = propriedades.criar_propriedade(
            self.origem["produtor_id"], "Propriedade de destino")
        db.clear_cache()

        ativos = db.get_all_animals(status="ativo")
        self.a1, self.a2 = ativos[0], ativos[1]

    def _mov(self, animais=None, **kw):
        r = movimentacoes.criar(
            kw.pop("tipo", "entre_propriedades_mesmo_titular"),
            propriedade_origem_id=self.origem["id"],
            propriedade_destino_id=self.destino_id,
            data_prevista=kw.pop("data_prevista", HOJE),
            gta_numero=kw.pop("gta_numero", "GTA123"),
            animais=animais if animais is not None else [self.a1["uuid"]],
            usuario="op1", **kw)
        self.assertTrue(r["ok"], r)
        return r["id"]

    def _codigos(self, problemas):
        return {p["codigo"]: p["gravidade"] for p in problemas}

    def _sql(self, sql, args=()):
        con = sqlite3.connect(db.DB_PATH)
        try:
            con.execute(sql, args); con.commit()
        finally:
            con.close()
        db.clear_cache()


class TestTresNiveis(BaseB6):
    """§8.4: informativo permite, alerta exige justificativa, bloqueio impede."""

    def test_movimentacao_limpa_libera_sem_justificativa(self):
        mid = self._mov()
        r = movimentacoes.liberar(mid, usuario="op1")
        self.assertTrue(r["ok"], r)

    def test_bloqueio_impede_mesmo_com_justificativa(self):
        """Animal morto não sai nem com justificativa — é bloqueio, não alerta."""
        self._sql("UPDATE animals SET status='morto' WHERE uuid=?", (self.a1["uuid"],))
        mid = self._mov()
        r = movimentacoes.liberar(mid, usuario="op1",
                                  justificativa="preciso muito mandar assim mesmo")
        self.assertFalse(r["ok"])
        self.assertIn("animal_morto_ou_abatido", self._codigos(r["problemas"]))
        self.assertEqual(
            movimentacoes.get(mid)["status"], "rascunho",
            "movimentação foi liberada apesar do bloqueio")

    def test_alerta_exige_justificativa_mas_nao_impede(self):
        mid = self._mov(gta_numero="")   # sem GTA é alerta
        r1 = movimentacoes.liberar(mid, usuario="op1")
        self.assertFalse(r1["ok"])
        self.assertTrue(r1.get("exige_confirmacao"), r1)

        r2 = movimentacoes.liberar(mid, usuario="op1",
                                   justificativa="GTA sai amanhã, conferido com o escritório")
        self.assertTrue(r2["ok"], r2)
        self.assertEqual(movimentacoes.get(mid)["status"], "liberada")

    def test_informativo_nao_atrapalha(self):
        """Carência com destino que não é abate é informativo — libera direto."""
        self._sql("INSERT INTO medications (animal_uuid,medication_name,dose,unit,"
                  "application_route,withdrawal_days,med_date,applied_by) "
                  "VALUES(?,?,?,?,?,?,?,?)",
                  (self.a1["uuid"], "Ivermectina", 10, "ml", "SC", 60, HOJE, "op1"))
        mid = self._mov()
        r = movimentacoes.liberar(mid, usuario="op1")
        self.assertTrue(r["ok"], f"informativo virou impedimento: {r}")
        self.assertIn("animal_em_carencia_sem_abate", self._codigos(r["problemas"]))

    def test_carencia_com_destino_abate_bloqueia(self):
        """O contraponto do teste acima: a mesma carência, destino frigorífico."""
        self._sql("INSERT INTO medications (animal_uuid,medication_name,dose,unit,"
                  "application_route,withdrawal_days,med_date,applied_by) "
                  "VALUES(?,?,?,?,?,?,?,?)",
                  (self.a1["uuid"], "Ivermectina", 10, "ml", "SC", 60, HOJE, "op1"))
        mid = self._mov(tipo="frigorifico", finalidade="abate")
        r = movimentacoes.liberar(mid, usuario="op1", justificativa="urgente")
        self.assertFalse(r["ok"])
        self.assertIn("animal_em_carencia", self._codigos(r["problemas"]))


class TestPreValidacao(BaseB6):
    """§8.3 — as verificações antes de liberar."""

    def test_animal_de_outra_propriedade_bloqueia(self):
        self._sql("UPDATE animals SET property_id=? WHERE uuid=?",
                  (self.destino_id, self.a1["uuid"]))
        mid = self._mov()
        v = movimentacoes.pre_validar(mid)
        self.assertIn("animal_de_outra_propriedade", self._codigos(v["problemas"]))

    def test_animal_em_duas_movimentacoes_bloqueia(self):
        self._mov()                     # primeira, fica em rascunho
        segunda = self._mov()           # mesma cabeça em outra
        v = movimentacoes.pre_validar(segunda)
        self.assertIn("animal_em_outra_movimentacao", self._codigos(v["problemas"]))

    def test_sem_animais_bloqueia(self):
        mid = self._mov(animais=[])
        v = movimentacoes.pre_validar(mid)
        self.assertIn("sem_animais", self._codigos(v["problemas"]))

    def test_identificacao_so_bloqueia_quando_obrigatoria(self):
        """§4.1: exigível a partir de 2033. Hoje é configuração, não código."""
        mid = self._mov()
        sem = movimentacoes.pre_validar(mid, identificacao_obrigatoria=False)
        com = movimentacoes.pre_validar(mid, identificacao_obrigatoria=True)
        self.assertNotIn("sem_identificacao_obrigatoria", self._codigos(sem["problemas"]))
        self.assertIn("sem_identificacao_obrigatoria", self._codigos(com["problemas"]))

    def test_pre_validar_nao_muda_status(self):
        mid = self._mov()
        movimentacoes.pre_validar(mid)
        self.assertEqual(movimentacoes.get(mid)["status"], "rascunho")


class TestChegada(BaseB6):
    def test_chegada_muda_a_propriedade_do_animal(self):
        mid = self._mov()
        movimentacoes.liberar(mid, usuario="op1")
        r = movimentacoes.confirmar_chegada(mid, data=HOJE, usuario="op1")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["status"], "concluida")

        con = sqlite3.connect(db.DB_PATH); con.row_factory = sqlite3.Row
        prop = con.execute("SELECT property_id FROM animals WHERE uuid=?",
                           (self.a1["uuid"],)).fetchone()["property_id"]
        con.close()
        self.assertEqual(prop, self.destino_id,
                         "animal chegou mas continuou na propriedade de origem")

    def test_animal_que_nao_chegou_vira_divergencia(self):
        """§8.2: recusa ou divergência na recepção precisa ficar registrada."""
        mid = self._mov(animais=[self.a1["uuid"], self.a2["uuid"]])
        movimentacoes.liberar(mid, usuario="op1")
        r = movimentacoes.confirmar_chegada(mid, data=HOJE, usuario="op1",
                                            recebidos=[self.a1["uuid"]])
        self.assertEqual(r["status"], "divergente",
                         "faltou animal e a movimentação foi dada como concluída")
        self.assertEqual(r["nao_recebidos"], [self.a2["uuid"]])

        mov = movimentacoes.get(mid)
        divergentes = [a for a in mov["animais"] if a["divergencia"]]
        self.assertEqual(len(divergentes), 1)

    def test_chegada_gera_eventos_distintos(self):
        mid = self._mov(animais=[self.a1["uuid"], self.a2["uuid"]])
        movimentacoes.liberar(mid, usuario="op1")
        movimentacoes.confirmar_chegada(mid, data=HOJE, usuario="op1",
                                        recebidos=[self.a1["uuid"]])
        chegou = [e["tipo"] for e in eventos.do_animal(self.a1["uuid"])]
        faltou = [e["tipo"] for e in eventos.do_animal(self.a2["uuid"])]
        self.assertIn("chegada_confirmada", chegou)
        self.assertIn("recusa_recepcao", faltou)

    def test_nao_conclui_duas_vezes(self):
        mid = self._mov()
        movimentacoes.liberar(mid, usuario="op1")
        movimentacoes.confirmar_chegada(mid, data=HOJE, usuario="op1")
        r = movimentacoes.confirmar_chegada(mid, data=HOJE, usuario="op1")
        self.assertFalse(r["ok"])


class TestAuditoria(BaseB6):
    def test_liberacao_fica_na_trilha_com_justificativa(self):
        mid = self._mov(gta_numero="")
        movimentacoes.liberar(mid, usuario="admin",
                              justificativa="GTA pendente, autorizado pelo escritório")
        t = eventos.trilha(entidade="movimentacoes", entidade_id=mid)
        libera = [x for x in t if x["acao"] == "liberacao_de_movimentacao"]
        self.assertTrue(libera, "liberação não foi auditada")
        self.assertIn("escritório", libera[0]["motivo"])
        self.assertEqual(libera[0]["autorizacao"], "admin")

    def test_saida_gera_evento_no_animal(self):
        mid = self._mov()
        movimentacoes.liberar(mid, usuario="op1")
        self.assertIn("saida_propriedade",
                      [e["tipo"] for e in eventos.do_animal(self.a1["uuid"])])


if __name__ == "__main__":
    unittest.main()
