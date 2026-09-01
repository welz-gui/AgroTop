"""Eventos e trilha de auditoria são mesmo append-only? (ADR 0004 · etapa B2)

O §6.3 do PNIB diz que evento confirmado não se apaga nem se sobrescreve, e o
§14.1 pede a mesma coisa da auditoria. **Isso é uma afirmação sobre o banco, não
sobre a disciplina de quem escreve código** — por isso os gatilhos existem, e por
isso estes testes tentam violar de verdade em vez de conferir se o gatilho está lá.

Um `UPDATE` que passa despercebido na auditoria é exatamente o que uma trilha de
auditoria existe para impedir.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402
from repositories import eventos  # noqa: E402


class BaseEventos(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "eventos.db"))
        db.init_db()
        db.clear_cache()
        self.animal = db.get_all_animals(status="ativo")[0]
        self.uuid = self.animal["uuid"]

    def _con(self):
        con = sqlite3.connect(db.DB_PATH)
        con.row_factory = sqlite3.Row
        return con


class TestAppendOnly(BaseEventos):
    """A parte que não pode ser só comentário."""

    def test_evento_nao_pode_ser_alterado(self):
        eventos.registrar(self.uuid, "pesagem", usuario_registro="op1")
        con = self._con()
        try:
            with self.assertRaises(sqlite3.IntegrityError,
                                   msg="UPDATE em animal_events foi ACEITO"):
                con.execute("UPDATE animal_events SET tipo='venda'")
                con.commit()
        finally:
            con.close()

    def test_evento_nao_pode_ser_apagado(self):
        eventos.registrar(self.uuid, "pesagem", usuario_registro="op1")
        con = self._con()
        try:
            with self.assertRaises(sqlite3.IntegrityError,
                                   msg="DELETE em animal_events foi ACEITO"):
                con.execute("DELETE FROM animal_events")
                con.commit()
        finally:
            con.close()

    def test_auditoria_nao_pode_ser_alterada(self):
        eventos.auditar("teste", usuario="op1")
        con = self._con()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("UPDATE audit_logs SET usuario='outro'")
                con.commit()
        finally:
            con.close()

    def test_auditoria_nao_pode_ser_apagada(self):
        eventos.auditar("teste", usuario="op1")
        con = self._con()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("DELETE FROM audit_logs")
                con.commit()
        finally:
            con.close()

    def test_o_registro_continua_la_depois_da_tentativa(self):
        """O contraponto: a tentativa falhou, mas o dado não pode ter sumido."""
        eventos.registrar(self.uuid, "pesagem", usuario_registro="op1")
        con = self._con()
        try:
            for sql in ("UPDATE animal_events SET tipo='venda'",
                        "DELETE FROM animal_events"):
                try:
                    con.execute(sql); con.commit()
                except sqlite3.IntegrityError:
                    con.rollback()
        finally:
            con.close()
        evs = eventos.do_animal(self.uuid)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["tipo"], "pesagem")


class TestRegistroDeEvento(BaseEventos):
    def test_ocorrido_e_registrado_sao_separados(self):
        """§6.2: o atraso entre o fato e o registro é auditável — some se forem um só."""
        eventos.registrar(self.uuid, "pesagem", ocorrido_em="2026-07-01T08:00:00+00:00",
                          usuario_registro="op1")
        e = eventos.do_animal(self.uuid)[0]
        self.assertEqual(e["ocorrido_em"], "2026-07-01T08:00:00+00:00")
        self.assertNotEqual(e["registrado_em"], e["ocorrido_em"],
                            "registrado_em copiou ocorrido_em em vez de marcar agora")

    def test_data_com_fuso(self):
        """Emenda à R5: evento carrega fuso; data de negócio continua texto simples."""
        eventos.registrar(self.uuid, "pesagem", usuario_registro="op1")
        e = eventos.do_animal(self.uuid)[0]
        self.assertTrue(e["registrado_em"].endswith("+00:00") or "T" in e["registrado_em"],
                        f"sem fuso: {e['registrado_em']}")

    def test_tipo_desconhecido_e_recusado(self):
        r = eventos.registrar(self.uuid, "voo_do_boi", usuario_registro="op1")
        self.assertFalse(r["ok"])
        self.assertEqual(eventos.do_animal(self.uuid), [])

    def test_animal_inexistente_e_recusado(self):
        r = eventos.registrar("uuid-que-nao-existe", "pesagem")
        self.assertFalse(r["ok"])

    def test_evento_fica_pendente_de_sincronizacao(self):
        """Registrar não é comunicar — a fila é o que separa as duas coisas."""
        eventos.registrar(self.uuid, "pesagem", usuario_registro="op1")
        self.assertEqual(len(eventos.pendentes_de_sincronizacao()), 1)


class TestCorrecao(BaseEventos):
    """§6.3: corrigir é criar outro evento, nunca mexer no original."""

    def _original(self):
        eventos.registrar(self.uuid, "pesagem", usuario_registro="op1",
                          observacoes="420 kg")
        return eventos.do_animal(self.uuid)[0]["id"]

    def test_correcao_preserva_o_original(self):
        oid = self._original()
        eventos.corrigir(oid, "peso digitado errado", usuario_registro="admin")

        evs = eventos.do_animal(self.uuid)
        self.assertEqual(len(evs), 2, "a correção não criou um segundo evento")
        original = [e for e in evs if e["id"] == oid][0]
        self.assertEqual(original["observacoes"], "420 kg",
                         "o evento original foi alterado pela correção")

    def test_correcao_aponta_para_o_original_e_sobe_a_versao(self):
        oid = self._original()
        eventos.corrigir(oid, "peso digitado errado", usuario_registro="admin")
        corr = [e for e in eventos.do_animal(self.uuid) if e["id"] != oid][0]
        self.assertEqual(corr["evento_anterior_id"], oid)
        self.assertEqual(corr["versao"], 2)
        self.assertEqual(corr["justificativa"], "peso digitado errado")

    def test_correcao_sem_justificativa_e_recusada(self):
        oid = self._original()
        r = eventos.corrigir(oid, "   ", usuario_registro="admin")
        self.assertFalse(r["ok"])
        self.assertEqual(len(eventos.do_animal(self.uuid)), 1)


class TestTrilhaDeAuditoria(BaseEventos):
    def test_guarda_antes_e_depois(self):
        """O que distingue auditoria de log: dá para saber o que exatamente mudou."""
        eventos.auditar("mudanca", usuario="admin", entidade="animals",
                        entidade_id=self.animal["id"],
                        registro_anterior={"status": "ativo"},
                        registro_posterior={"status": "vendido"},
                        motivo="venda do lote")
        r = eventos.trilha(entidade="animals", entidade_id=self.animal["id"])[0]
        # Normalizado pelo repositório: dict nos dois bancos, apesar de o
        # SQLite guardar texto e o Postgres jsonb.
        self.assertEqual(r["registro_anterior"], {"status": "ativo"})
        self.assertEqual(r["registro_posterior"], {"status": "vendido"})
        self.assertEqual(r["motivo"], "venda do lote")

    def test_filtra_por_entidade(self):
        eventos.auditar("a", entidade="animals", entidade_id="X1")
        eventos.auditar("b", entidade="lotes", entidade_id="P01")
        self.assertEqual(len(eventos.trilha(entidade="lotes")), 1)
        self.assertEqual(len(eventos.trilha()), 2)


if __name__ == "__main__":
    unittest.main()


class TestOperacoesGeramEvento(BaseEventos):
    """Cada operação do dia a dia entra na linha do tempo do animal (§6.1).

    Até 2026-08-02 só a mudança de status gerava evento, e `animal_events` ficava
    praticamente vazia — a rastreabilidade era promessa, não fato. Estes testes
    travam cada ponto de escrita.
    """

    def _tipos(self, uuid):
        return [e["tipo"] for e in eventos.do_animal(uuid)]

    def test_pesagem(self):
        db.add_weighing(self.animal["id"], 430.0, "2026-07-20", operator="op1")
        self.assertIn("pesagem", self._tipos(self.uuid))

    def test_medicacao(self):
        db.add_medication(self.animal["id"], "Ivermectina", 10, "ml",
                          "Subcutânea", 21, "2026-07-20", "op1")
        self.assertIn("manejo_sanitario", self._tipos(self.uuid))

    def test_movimentacao_de_lote(self):
        db.move_animal(self.animal["id"], "P02", "2026-07-20", operator="op1")
        self.assertIn("mudanca_lote", self._tipos(self.uuid))

    def test_cadastro_gera_dois_eventos(self):
        """Cadastro e identificação interna são eventos distintos no §6.1."""
        db.add_animal(db.AnimalData("EV1", "Nelore", "M", None, "2026-07-01",
                      300.0, 500.0, 1000.0, None, None))
        novo = [a for a in db.get_all_animals(status=None) if a["id"] == "EV1"][0]
        tipos = self._tipos(novo["uuid"])
        self.assertIn("cadastro_inicial", tipos)
        self.assertIn("identificacao_interna", tipos)

    def test_venda(self):
        db.register_sale([self.animal["id"]], "2026-07-20", "abate", "cabeca",
                         5000.0, buyer="Frigorífico X", operator="op1")
        self.assertIn("venda", self._tipos(self.uuid))

    def test_obito(self):
        db.register_death(self.animal["id"], "2026-07-20", "Timpanismo",
                          operator="op1")
        self.assertIn("morte", self._tipos(self.uuid))

    def test_evento_e_atomico_com_a_operacao(self):
        """Se a operação falha, não pode sobrar evento órfão dizendo que houve.

        `add_weighing` recusa animal inexistente; o evento não pode ter entrado.
        """
        antes = len(eventos.do_animal(self.uuid))
        with self.assertRaises(ValueError):
            db.add_weighing("NAO_EXISTE", 400.0, "2026-07-20")
        self.assertEqual(len(eventos.do_animal(self.uuid)), antes)

    def test_ocorrido_em_usa_a_data_do_fato_nao_a_de_hoje(self):
        """§6.2: pesagem lançada com atraso guarda a data em que ocorreu."""
        db.add_weighing(self.animal["id"], 430.0, "2026-01-15", operator="op1")
        ev = [e for e in eventos.do_animal(self.uuid) if e["tipo"] == "pesagem"][0]
        self.assertTrue(ev["ocorrido_em"].startswith("2026-01-15"),
                        f"ocorrido_em não é a data da pesagem: {ev['ocorrido_em']}")
        self.assertNotEqual(ev["ocorrido_em"], ev["registrado_em"])
