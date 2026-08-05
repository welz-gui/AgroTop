"""A fila de sincronização drena? (ADR 0005 · PNIB §10.3 e §10.4)

Até 2026-08-04 não drenava: `animal_events.status_sincronizacao` nascia
'pendente' e o gatilho append-only do §6.3 abortava qualquer `UPDATE`. O efeito
não ficava no banco — chegava na tela: o contador nunca zerava, então **toda**
liberação de saída exigia justificativa (§8.4) por um alerta que não informava
nada.

Estes testes travam as duas metades da decisão:

1. a fila agora fecha (e o alerta some junto);
2. `animal_events` continua **estritamente** imutável — a fila fechou sem abrir
   exceção nenhuma no §6.3. Se a segunda metade cair, a primeira não vale nada.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402
from repositories import eventos, movimentacoes, propriedades  # noqa: E402
from services import sincronizacao as sinc  # noqa: E402

HOJE = date.today().isoformat()


class BaseSinc(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "sinc.db"))
        db.init_db()
        db.clear_cache()
        self.animal = db.get_all_animals(status="ativo")[0]
        self.uuid = self.animal["uuid"]

    def _evento(self, tipo="pesagem"):
        eventos.registrar(self.uuid, tipo, usuario_registro="op1")
        return eventos.do_animal(self.uuid)[0]["id"]

    def _con(self):
        con = sqlite3.connect(db.DB_PATH)
        con.row_factory = sqlite3.Row
        return con


class TestFilaDrena(BaseSinc):
    """O defeito que este ADR existe para corrigir."""

    def test_evento_nasce_na_fila(self):
        self._evento()
        self.assertEqual(eventos.contar_pendentes(), 1)
        self.assertEqual(len(eventos.pendentes_de_sincronizacao()), 1)

    def test_marcar_sincronizado_tira_da_fila(self):
        """O teste que não passava antes do ADR 0005."""
        eid = self._evento()
        r = eventos.marcar_sincronizado([eid], protocolo="SEAPI-2026-0001",
                                        usuario="admin")
        self.assertTrue(r["ok"], r)
        self.assertEqual(eventos.contar_pendentes(), 0)
        self.assertEqual(eventos.pendentes_de_sincronizacao(), [])

    def test_protocolo_oficial_fica_guardado(self):
        """§6.2 "identificador retornado pelo sistema oficial" — sem UPDATE."""
        eid = self._evento()
        eventos.marcar_sincronizado([eid], protocolo="SEAPI-2026-0001",
                                    usuario="admin", conferido_por="tecnico")
        atual = eventos.situacao_atual(eid)["oficial"]
        self.assertEqual(atual["protocolo"], "SEAPI-2026-0001")
        self.assertEqual(atual["conferido_por"], "tecnico")

    def test_lote_inteiro_de_uma_vez(self):
        ids = [self._evento("pesagem"), self._evento("mudanca_lote")]
        eventos.marcar_sincronizado(ids, usuario="admin")
        self.assertEqual(eventos.contar_pendentes(), 0)

    def test_rejeitado_continua_na_fila(self):
        """O sistema oficial recusou: o dever de comunicar continua de pé."""
        eid = self._evento()
        eventos.registrar_situacao(eid, "rejeitado", mensagem="brinco inválido",
                                   usuario="integracao")
        self.assertEqual(eventos.contar_pendentes(), 1)
        pend = eventos.pendentes_de_sincronizacao()[0]
        self.assertEqual(pend["situacao_sincronizacao"], "rejeitado")

    def test_aceito_depois_de_rejeitado_fecha(self):
        eid = self._evento()
        eventos.registrar_situacao(eid, "enviado", usuario="integracao")
        eventos.registrar_situacao(eid, "rejeitado", usuario="integracao")
        eventos.registrar_situacao(eid, "aceito", protocolo="P2", usuario="integracao")
        self.assertEqual(eventos.contar_pendentes(), 0)

    def test_rejeitado_depois_de_aceito_reabre(self):
        """Vale a ÚLTIMA transição, não a melhor que já houve."""
        eid = self._evento()
        eventos.registrar_situacao(eid, "aceito", usuario="integracao")
        self.assertEqual(eventos.contar_pendentes(), 0)
        eventos.registrar_situacao(eid, "divergente", usuario="integracao")
        self.assertEqual(eventos.contar_pendentes(), 1)

    def test_nao_aplicavel_tambem_fecha(self):
        """§10.3: evento que nunca precisou ir não é pendência."""
        eid = self._evento()
        eventos.registrar_situacao(eid, "nao_aplicavel", usuario="admin")
        self.assertEqual(eventos.contar_pendentes(), 0)

    def test_cada_sistema_conta_por_si(self):
        """§10.1: aceito num destino e em aberto noutro continua pendente."""
        eid = self._evento()
        eventos.registrar_situacao(eid, "aceito", sistema="seapi_rs")
        eventos.registrar_situacao(eid, "em_fila", sistema="base_central_pnib")
        self.assertEqual(eventos.contar_pendentes(), 1)

        eventos.registrar_situacao(eid, "aceito", sistema="base_central_pnib")
        self.assertEqual(eventos.contar_pendentes(), 0)

    def test_situacao_em_aberto_vence_na_listagem(self):
        """Com dois sistemas, a fila mostra o que ainda prende o evento."""
        eid = self._evento()
        eventos.registrar_situacao(eid, "aceito", sistema="seapi_rs")
        eventos.registrar_situacao(eid, "erro_tecnico", sistema="base_central_pnib")
        pend = eventos.pendentes_de_sincronizacao()[0]
        self.assertEqual(pend["situacao_sincronizacao"], "erro_tecnico")


class TestImutabilidadeIntacta(BaseSinc):
    """A metade que não pode ter sido sacrificada pela outra."""

    def test_animal_events_continua_recusando_update(self):
        self._evento()
        con = self._con()
        try:
            with self.assertRaises(sqlite3.IntegrityError,
                                   msg="UPDATE em animal_events foi ACEITO"):
                con.execute("UPDATE animal_events SET tipo='venda'")
                con.commit()
        finally:
            con.close()

    def test_update_so_da_coluna_de_sincronizacao_tambem_e_recusado(self):
        """O caso exato que a opção recusada teria liberado (ADR 0005 §2)."""
        self._evento()
        con = self._con()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute(
                    "UPDATE animal_events SET status_sincronizacao='sincronizado'")
                con.commit()
        finally:
            con.close()

    def test_coluna_legada_nao_responde_pela_fila(self):
        """Marcar como sincronizado NÃO toca a coluna legada — e nem por isso a
        fila fica presa. É o que prova que quem responde é a tabela nova."""
        eid = self._evento()
        eventos.marcar_sincronizado([eid], usuario="admin")

        con = self._con()
        try:
            legado = con.execute(
                "SELECT status_sincronizacao, identificador_oficial "
                "FROM animal_events WHERE id=?", (eid,)).fetchone()
        finally:
            con.close()

        self.assertEqual(legado["status_sincronizacao"], "pendente",
                         "a coluna legada foi alterada — o evento deixou de ser imutável")
        self.assertIsNone(legado["identificador_oficial"])
        self.assertEqual(eventos.contar_pendentes(), 0)

    def test_transicao_de_sincronizacao_nao_pode_ser_alterada(self):
        eid = self._evento()
        eventos.registrar_situacao(eid, "enviado", usuario="integracao")
        con = self._con()
        try:
            with self.assertRaises(sqlite3.IntegrityError,
                                   msg="UPDATE em evento_sincronizacao foi ACEITO"):
                con.execute("UPDATE evento_sincronizacao SET situacao='aceito'")
                con.commit()
        finally:
            con.close()

    def test_transicao_de_sincronizacao_nao_pode_ser_apagada(self):
        eid = self._evento()
        eventos.registrar_situacao(eid, "rejeitado", usuario="integracao")
        con = self._con()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("DELETE FROM evento_sincronizacao")
                con.commit()
        finally:
            con.close()

    def test_historico_guarda_todas_as_tentativas(self):
        """§10.2 pede logs técnicos e tentativas; saem do histórico, não de contador."""
        eid = self._evento()
        for s in ("em_fila", "enviado", "erro_tecnico", "enviado", "aceito"):
            eventos.registrar_situacao(eid, s, usuario="integracao")
        hist = eventos.historico_de_sincronizacao(eid)
        self.assertEqual([h["situacao"] for h in hist],
                         ["em_fila", "enviado", "erro_tecnico", "enviado", "aceito"])
        self.assertEqual(sum(1 for h in hist if h["situacao"] == "enviado"), 2)


class TestValidacoes(BaseSinc):
    def test_situacao_fora_do_vocabulario_e_recusada(self):
        """§10.3 é lista fechada na norma — aqui a validação é restrição."""
        eid = self._evento()
        r = eventos.registrar_situacao(eid, "quase_la")
        self.assertFalse(r["ok"])
        self.assertEqual(eventos.historico_de_sincronizacao(eid), [])

    def test_sistema_fora_da_lista_e_aceito(self):
        """§10.1 termina em "protocolos privados homologados" — lista aberta."""
        eid = self._evento()
        r = eventos.registrar_situacao(eid, "aceito", sistema="frigorifico_x")
        self.assertTrue(r["ok"], r)

    def test_evento_inexistente_e_recusado(self):
        r = eventos.registrar_situacao(999999, "aceito")
        self.assertFalse(r["ok"])

    def test_marcar_sincronizado_recusa_situacao_que_nao_encerra(self):
        """`rejeitado` por esta porta seria mentira: o nome diz "sincronizado"."""
        eid = self._evento()
        r = eventos.marcar_sincronizado([eid], situacao="rejeitado")
        self.assertFalse(r["ok"])
        self.assertEqual(eventos.contar_pendentes(), 1)

    def test_ocorrido_e_registrado_sao_separados(self):
        """§6.2 vale aqui também: o atraso da comunicação é auditável."""
        eid = self._evento()
        eventos.registrar_situacao(eid, "aceito",
                                   ocorrido_em="2026-07-01T08:00:00+00:00")
        linha = eventos.situacao_atual(eid)["oficial"]
        self.assertEqual(linha["ocorrido_em"], "2026-07-01T08:00:00+00:00")
        self.assertNotEqual(linha["registrado_em"], linha["ocorrido_em"])


class TestRegraPura(unittest.TestCase):
    """`services/sincronizacao.py` — sem banco."""

    def test_as_catorze_situacoes_do_documento(self):
        self.assertEqual(len(sinc.SITUACOES), 14)

    def test_recusa_encerra_e_aceite_encerra_sao_coisas_diferentes(self):
        for s in ("aceito", "aceito_com_ressalva", "cancelado",
                  "nao_aplicavel", "reconciliado_manualmente"):
            self.assertTrue(sinc.resolvida(s), s)
        for s in ("aguardando_envio", "em_fila", "enviado", "processando",
                  "rejeitado", "erro_tecnico", "aguardando_correcao",
                  "cancelamento_solicitado", "divergente"):
            self.assertTrue(sinc.em_aberto(s), s)

    def test_situacao_desconhecida_conta_como_em_aberto(self):
        """Entre errar deixando na fila e errar tirando dela, só o segundo
        esconde uma obrigação de comunicar."""
        self.assertTrue(sinc.em_aberto("qualquer_coisa"))
        self.assertTrue(sinc.em_aberto(None))

    def test_valor_legado_conta_como_fila(self):
        self.assertTrue(sinc.em_aberto(sinc.SITUACAO_LEGADA))

    def test_toda_situacao_tem_rotulo(self):
        """R21: informação não depende de código interno na tela."""
        for s in sinc.SITUACOES:
            self.assertNotEqual(sinc.rotulo(s), s, s)


class TestAlertaDeSaida(unittest.TestCase):
    """§8.4 — a ponta onde o defeito aparecia para o usuário."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "sinc_mov.db"))
        db.init_db()
        db.clear_cache()

        self.origem = propriedades.padrao()
        self.destino_id = propriedades.criar_propriedade(
            self.origem["produtor_id"], "Propriedade de destino")
        db.clear_cache()
        self.animal = db.get_all_animals(status="ativo")[0]

    def _mov(self):
        r = movimentacoes.criar(
            "entre_propriedades_mesmo_titular",
            propriedade_origem_id=self.origem["id"],
            propriedade_destino_id=self.destino_id,
            data_prevista=HOJE, gta_numero="GTA123",
            animais=[self.animal["uuid"]], usuario="op1")
        self.assertTrue(r["ok"], r)
        return r["id"]

    def _codigos(self, v):
        return {p["codigo"] for p in v["problemas"]}

    def test_o_alerta_aparece_e_depois_some(self):
        """A prova de ponta a ponta: uma pesagem lançada passava a exigir
        justificativa em toda saída, para sempre."""
        db.add_weighing(self.animal["id"], 430.0, HOJE, operator="op1")
        db.clear_cache()
        mid = self._mov()

        antes = movimentacoes.pre_validar(mid)
        self.assertIn("sincronizacao_pendente", self._codigos(antes))
        self.assertTrue(antes["exige_confirmacao"])

        ids = [e["id"] for e in eventos.pendentes_de_sincronizacao()]
        self.assertTrue(ids)
        eventos.marcar_sincronizado(ids, protocolo="SEAPI-1", usuario="admin")
        db.clear_cache()

        depois = movimentacoes.pre_validar(mid)
        self.assertNotIn("sincronizacao_pendente", self._codigos(depois))
        self.assertFalse(depois["exige_confirmacao"],
                         f"ainda exige justificativa: {depois['problemas']}")

    def test_liberar_deixa_de_pedir_justificativa(self):
        db.add_weighing(self.animal["id"], 430.0, HOJE, operator="op1")
        db.clear_cache()
        mid = self._mov()

        r1 = movimentacoes.liberar(mid, usuario="op1")
        self.assertFalse(r1["ok"], "liberou com alerta pendente e sem justificativa")

        eventos.marcar_sincronizado(
            [e["id"] for e in eventos.pendentes_de_sincronizacao()],
            protocolo="SEAPI-1", usuario="admin")
        db.clear_cache()

        r2 = movimentacoes.liberar(mid, usuario="op1")
        self.assertTrue(r2["ok"], r2)


if __name__ == "__main__":
    unittest.main()
