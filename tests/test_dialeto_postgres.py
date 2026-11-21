"""Integração real do caminho PostgreSQL usando apenas o banco efêmero do CI."""

import os
import subprocess
import sys
import textwrap
import unittest


RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTGRES_NO_CI = os.environ.get("AGROTOP_TEST_POSTGRES") == "1"


class _ExecutaEmPostgres(unittest.TestCase):
    def _executar(self, codigo: str) -> None:
        """Executa o cenário num processo que realmente importa USE_PG=True."""
        env = dict(os.environ)
        env.pop("AGROTOP_FORCE_SQLITE", None)
        self.assertTrue(env.get("DATABASE_URL"), "DATABASE_URL de teste ausente")

        processo = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(codigo)],
            cwd=RAIZ,
            env=env,
            capture_output=True,
            text=True,
        )
        saida = f"{processo.stdout}\n{processo.stderr}"
        url = env.get("DATABASE_URL", "")
        if url:
            saida = saida.replace(url, "<DATABASE_URL omitida>")
        self.assertEqual(
            processo.returncode,
            0,
            f"Cenário PostgreSQL falhou (credencial omitida):\n{saida}",
        )

@unittest.skipUnless(POSTGRES_NO_CI, "PostgreSQL efêmero não solicitado")
class TestDialetoPostgres(_ExecutaEmPostgres):
    def test_init_db_completa(self):
        self._executar(
            """
            import database as db

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            """
        )

    def test_ciclo_de_escrita_e_leitura(self):
        self._executar(
            """
            import uuid

            import database as db
            from repositories.animais import get_animal

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            animal_id = "PG" + uuid.uuid4().hex[:10]
            db.add_animal(db.AnimalData(
                animal_id, "Nelore", "M", None, "2026-08-01",
                300.0, 500.0, 0.0, None, None,
            ))
            db.add_weighing(db.WeighingCreate(animal_id=animal_id, weight=345.0, weigh_date="2026-08-02", operator="CI"))

            animal = get_animal(animal_id)
            assert animal is not None
            assert animal["current_weight"] == 345.0
            pesagens = db.get_weighings(animal_id)
            assert any(p["weight"] == 345.0 for p in pesagens)
            """
        )

    def test_executemany_grava_em_lote(self):
        """`_PGConn` precisa expor `executemany`, não só `execute`.

        Vários pontos do código (importação de dispositivos/pesagens,
        backfill de uuid/identificadores, confirmação de chegada) trocaram
        um loop de `execute` por um único `executemany` para ganho de
        performance. SQLite tem `executemany` nativo, então esse caminho
        nunca quebrava em CI — só no Postgres real, onde `_PGConn` só
        proxeava `execute`. Achado ao revisar PRs automatizadas do Jules
        (2026-09-01): `AttributeError: '_PGConn' object has no attribute
        'executemany'`.
        """
        self._executar(
            """
            import uuid

            import database as db
            from repositories.animais import get_animal

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            animal_id = "EM" + uuid.uuid4().hex[:10]
            db.add_animal(db.AnimalData(
                animal_id, "Nelore", "M", None, "2026-08-01",
                300.0, 500.0, 0.0, None, None,
            ))
            animal_uuid = get_animal(animal_id)["uuid"]

            with db._conn() as con:
                con.executemany(
                    "INSERT INTO weighings (animal_uuid,weigh_date,weight) "
                    "VALUES(?,?,?)",
                    [(animal_uuid, "2026-08-03", 350.0),
                     (animal_uuid, "2026-08-10", 360.0)],
                )

            pesagens = db.get_weighings(animal_id)
            pesos = {p["weight"] for p in pesagens}
            assert 350.0 in pesos and 360.0 in pesos, pesagens
            """
        )

    def test_animal_events_recusa_update_e_delete(self):
        self._executar(
            """
            import uuid

            import psycopg2

            import database as db

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            animal_id = "EV" + uuid.uuid4().hex[:10]
            db.add_animal(db.AnimalData(
                animal_id, "Nelore", "F", None, "2026-08-01",
                280.0, 480.0, 0.0, None, None,
            ))
            with db._conn() as con:
                evento = con.execute(
                    "SELECT e.id FROM animal_events e "
                    "JOIN animals a ON a.uuid=e.animal_uuid "
                    "WHERE a.id=? ORDER BY e.id LIMIT 1",
                    (animal_id,),
                ).fetchone()
            assert evento is not None

            for sql in (
                "UPDATE animal_events SET tipo='venda' WHERE id=?",
                "DELETE FROM animal_events WHERE id=?",
            ):
                try:
                    with db._conn() as con:
                        con.execute(sql, (evento["id"],))
                except psycopg2.Error:
                    pass
                else:
                    raise AssertionError(f"gatilho append-only aceitou: {sql}")
            """
        )

    def test_fila_de_sincronizacao_drena(self):
        """ADR 0005 — o mesmo cenário do SQLite, no dialeto que vai para produção.

        Interessa aqui o que só o Postgres exercita: `bigserial`, `timestamptz`
        voltando como `datetime` (normalizado pelo repositório) e a subconsulta
        `MAX(id)` por par (evento, sistema).
        """
        self._executar(
            """
            import uuid

            import database as db
            from repositories.animais import get_animal
            from repositories import eventos

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            animal_id = "SY" + uuid.uuid4().hex[:10]
            db.add_animal(db.AnimalData(
                animal_id, "Nelore", "F", None, "2026-08-01",
                280.0, 480.0, 0.0, None, None,
            ))
            animal_uuid = get_animal(animal_id)["uuid"]
            evento_id = eventos.do_animal(animal_uuid)[0]["id"]

            antes = eventos.contar_pendentes()
            assert antes > 0, "nenhum evento na fila para exercitar o cenário"

            eventos.registrar_situacao(evento_id, "enviado", usuario="CI")
            eventos.registrar_situacao(evento_id, "rejeitado", usuario="CI")
            assert eventos.contar_pendentes() == antes, "rejeitado saiu da fila"

            r = eventos.marcar_sincronizado(
                [evento_id], protocolo="CI-1", usuario="CI")
            assert r["ok"], r
            assert eventos.contar_pendentes() == antes - 1, "a fila não drenou"

            atual = eventos.situacao_atual(evento_id)["oficial"]
            assert atual["situacao"] == "aceito", atual
            assert atual["protocolo"] == "CI-1", atual
            assert isinstance(atual["registrado_em"], str), (
                "timestamptz não foi normalizado para texto ISO")
            assert len(eventos.historico_de_sincronizacao(evento_id)) == 3
            """
        )

    def test_evento_sincronizacao_recusa_update_e_delete(self):
        """A tabela nova é append-only como as outras duas (ADR 0005)."""
        self._executar(
            """
            import uuid

            import psycopg2

            import database as db
            from repositories.animais import get_animal
            from repositories import eventos

            assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
            db.init_db()
            animal_id = "SZ" + uuid.uuid4().hex[:10]
            db.add_animal(db.AnimalData(
                animal_id, "Nelore", "M", None, "2026-08-01",
                300.0, 500.0, 0.0, None, None,
            ))
            animal_uuid = get_animal(animal_id)["uuid"]
            evento_id = eventos.do_animal(animal_uuid)[0]["id"]
            eventos.registrar_situacao(evento_id, "enviado", usuario="CI")

            with db._conn() as con:
                linha = con.execute(
                    "SELECT id FROM evento_sincronizacao WHERE evento_id=?",
                    (evento_id,),
                ).fetchone()
            assert linha is not None

            for sql in (
                "UPDATE evento_sincronizacao SET situacao='aceito' WHERE id=?",
                "DELETE FROM evento_sincronizacao WHERE id=?",
            ):
                try:
                    with db._conn() as con:
                        con.execute(sql, (linha["id"],))
                except psycopg2.Error:
                    pass
                else:
                    raise AssertionError(f"gatilho append-only aceitou: {sql}")

            # E o evento em si continua intocável, inclusive na coluna legada.
            try:
                with db._conn() as con:
                    con.execute(
                        "UPDATE animal_events SET status_sincronizacao='sincronizado' "
                        "WHERE id=?",
                        (evento_id,),
                    )
            except psycopg2.Error:
                pass
            else:
                raise AssertionError(
                    "UPDATE de status_sincronizacao foi aceito — a exceção "
                    "recusada pelo ADR 0005 entrou por alguma porta")
            """
        )


if __name__ == "__main__":
    unittest.main()


# Trechos que todo cenário de negócio repete. Cada cenário roda num subprocesso com USE_PG=True.
_PRELUDIO = """
import uuid
from datetime import date, timedelta

import database as db
from repositories import contexto, eventos
from repositories.animais import cancelar_movimentacao, corrigir_movimentacao, get_animal
from repositories.pesagens import WeighingCreate, add_weighing, cancelar_pesagem, corrigir_pesagem
from repositories.revisao import RevisaoNaoPermitida

assert db.USE_PG, "o subprocesso não selecionou PostgreSQL"
db.init_db()
HOJE = date.today()


def novo(prefixo, sexo="M", lote=None):
    animal_id = prefixo + uuid.uuid4().hex[:10]
    db.add_animal(db.AnimalData(
        animal_id, "Nelore", sexo, None, "2026-08-01", 300.0, 500.0, 0.0, lote, None))
    return animal_id


def venda(ids, valor=10.0, modo="kg", tipo="criacao", sale_date="2026-11-01", **extra):
    return db.SaleParams(animal_ids=ids, sale_date=sale_date, sale_type=tipo, pricing_mode=modo,
                         value=valor, buyer="CI", operator="CI", **extra)


def linha(sql, args=()):
    with db._conn() as con:
        return con.execute(sql, args).fetchone()


def todas(sql, args=()):
    with db._conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def uuid_de(animal_id):
    return linha("SELECT uuid FROM animals WHERE id=?", (animal_id,))["uuid"]


def status_de(animal_id):
    return linha("SELECT status FROM animals WHERE id=?", (animal_id,))["status"]


def id_da_venda(animal_id):
    return linha(
        "SELECT s.id FROM sales s JOIN animals x ON x.uuid=s.animal_uuid "
        "WHERE x.id=? AND s.cancelada_em IS NULL", (animal_id,))["id"]


def tipos_de_evento(animal_id):
    return [e["tipo"] for e in eventos.do_animal(uuid_de(animal_id))]
"""


@unittest.skipUnless(POSTGRES_NO_CI, "PostgreSQL efêmero não solicitado")
class TestNegocioPostgres(_ExecutaEmPostgres):
    """Venda, revisão e origem do evento no Postgres de verdade.

    O CI só roda a suíte inteira em SQLite. Estes cenários exercitam, no dialeto que vai para
    produção, os caminhos que mais escrevem (várias linhas na mesma transação, estorno encadeado,
    auditoria) e que um erro de dialeto quebraria sem ninguém ver: `a_prazo` como inteiro numa
    coluna booleana, `IN (?, ?)` com lista, datas e valores numéricos voltando em outro tipo.
    """

    def _cenario(self, corpo: str) -> None:
        self._executar(textwrap.dedent(_PRELUDIO) + textwrap.dedent(corpo))

    # -- venda ----------------------------------------------------------------------------

    def test_venda_a_vista_grava_a_venda_o_evento_e_muda_o_status(self):
        self._cenario(
            """
            a = novo("VA")
            peso = get_animal(a)["current_weight"]

            r = db.register_sale(venda([a]))

            assert r["n"] == 1, r
            assert r["receita"] == round(10.0 * peso, 2), (r, peso)
            assert status_de(a) == "vendido"
            assert linha(
                "SELECT COUNT(*) AS c FROM sales s JOIN animals x ON x.uuid=s.animal_uuid "
                "WHERE x.id=? AND s.cancelada_em IS NULL", (a,))["c"] == 1
            assert tipos_de_evento(a).count("venda") == 1, tipos_de_evento(a)
            """
        )

    def test_venda_a_prazo_gera_as_parcelas_a_receber(self):
        """`a_prazo` é gravado como 0/1: o Postgres tem de aceitar na coluna dele."""
        self._cenario(
            """
            a = novo("VP")

            r = db.register_sale(venda([a], a_prazo=True, num_parcelas=3,
                                       primeiro_vencimento="2026-12-01"))

            assert r["parcelas_a_receber"] == 3, r
            parcelas = todas(
                "SELECT valor, status, parcela_numero, parcela_total FROM contas_receber "
                "WHERE lot_ref=? ORDER BY parcela_numero", (r["lot_ref"],))
            assert [p["parcela_numero"] for p in parcelas] == [1, 2, 3], parcelas
            assert all(p["status"] == "aberto" for p in parcelas), parcelas
            assert round(sum(float(p["valor"]) for p in parcelas), 2) == r["receita"], parcelas
            """
        )

    def test_animal_ja_vendido_nao_e_vendido_de_novo(self):
        """O status é lido na transação: o cache de `get_animal` ainda diz `ativo` (#701)."""
        self._cenario(
            """
            a = novo("RV")
            db.register_sale(venda([a]))

            try:
                db.register_sale(venda([a], valor=20.0))
            except RevisaoNaoPermitida as e:
                assert a in str(e), e
            else:
                raise AssertionError("vendeu o mesmo animal duas vezes")

            assert linha(
                "SELECT COUNT(*) AS c FROM sales s JOIN animals x ON x.uuid=s.animal_uuid "
                "WHERE x.id=?", (a,))["c"] == 1
            assert tipos_de_evento(a).count("venda") == 1
            """
        )

    def test_abate_em_carencia_e_bloqueado_e_a_venda_para_criacao_passa(self):
        self._cenario(
            """
            a = novo("CA")
            db.add_medication(db.MedicationData(
                animal_id=a, medication_name="Ivermectina", dose=5.0, unit="ml",
                application_route="Subcutânea", withdrawal_days=30,
                med_date=(HOJE - timedelta(days=1)).isoformat(), applied_by="CI"))

            try:
                db.register_sale(venda([a], tipo="abate", sale_date=HOJE.isoformat()))
            except db.VendaBloqueadaPorCarencia as e:
                assert a in e.bloqueados, e.bloqueados
            else:
                raise AssertionError("abate em carência foi aceito")
            assert linha("SELECT COUNT(*) AS c FROM sales s JOIN animals x ON x.uuid=s.animal_uuid "
                         "WHERE x.id=?", (a,))["c"] == 0, "a venda recusada gravou algo"

            r = db.register_sale(venda([a], tipo="criacao", sale_date=HOJE.isoformat()))
            assert r["n"] == 1, r
            assert status_de(a) == "vendido"
            """
        )

    # -- revisão de venda -----------------------------------------------------------------

    def test_cancelar_venda_devolve_o_animal_e_fecha_a_trilha(self):
        self._cenario(
            """
            a = novo("CV")
            db.register_sale(venda([a]))
            sid = id_da_venda(a)

            db.cancelar_venda(sid, "lançada por engano", "CI")

            assert status_de(a) == "ativo"
            assert linha("SELECT cancelada_em FROM sales WHERE id=?", (sid,))["cancelada_em"] is not None
            assert tipos_de_evento(a).count("estorno") == 1, tipos_de_evento(a)
            acoes = [t["acao"] for t in eventos.trilha(entidade="sales", entidade_id=str(sid))]
            assert "cancelar_venda" in acoes, acoes
            """
        )

    def test_corrigir_venda_troca_os_animais_na_mesma_transacao(self):
        self._cenario(
            """
            a1, a2, a3 = novo("T1"), novo("T2"), novo("T3")
            db.register_sale(venda([a1, a2]))
            sid = id_da_venda(a1)

            db.corrigir_venda(sid, venda([a1, a3], valor=12.0), "A2 não foi vendido", "CI")

            assert (status_de(a1), status_de(a2), status_de(a3)) == ("vendido", "ativo", "vendido")
            assert tipos_de_evento(a2).count("estorno") == 1, tipos_de_evento(a2)
            assert tipos_de_evento(a1).count("estorno") == 0, "quem fica na venda não é estornado"
            vigentes = linha(
                "SELECT COUNT(*) AS c FROM sales s JOIN animals x ON x.uuid=s.animal_uuid "
                "WHERE x.id IN (?,?,?) AND s.cancelada_em IS NULL", (a1, a2, a3))["c"]
            assert vigentes == 2, vigentes
            acoes = [t["acao"] for t in eventos.trilha(entidade="sales", entidade_id=str(sid))]
            assert "corrigir_venda" in acoes, acoes
            """
        )

    # -- revisão de pesagem e de movimentação ----------------------------------------------

    def test_cancelar_e_corrigir_pesagem_recalculam_o_peso_atual(self):
        self._cenario(
            """
            a = novo("PE")
            add_weighing(WeighingCreate(animal_id=a, weight=350.0, weigh_date="2026-10-01", operator="CI"))
            add_weighing(WeighingCreate(animal_id=a, weight=380.0, weigh_date="2026-10-20", operator="CI"))

            def pesagem(peso):
                return linha(
                    "SELECT w.id FROM weighings w JOIN animals x ON x.uuid=w.animal_uuid "
                    "WHERE x.id=? AND w.weight=? AND w.cancelada_em IS NULL", (a, peso))["id"]

            def peso_atual():
                return float(linha("SELECT current_weight FROM animals WHERE id=?", (a,))["current_weight"])

            assert peso_atual() == 380.0
            cancelar_pesagem(pesagem(380.0), "animal errado", "CI")
            assert peso_atual() == 350.0, peso_atual()
            assert tipos_de_evento(a).count("estorno") == 1, tipos_de_evento(a)

            corrigir_pesagem(
                pesagem(350.0),
                WeighingCreate(animal_id=a, weight=355.0, weigh_date="2026-10-01", operator="CI"),
                "balança descalibrada", "CI")
            assert peso_atual() == 355.0, peso_atual()
            """
        )

    def test_cancelar_e_corrigir_movimentacao_devolvem_o_animal_ao_piquete(self):
        self._cenario(
            """
            l1, l2, l3 = ("L" + k + uuid.uuid4().hex[:8] for k in "ABC")
            for lid in (l1, l2, l3):
                db.add_lote(db.LoteData(lid, "Piquete " + lid, 5.0, 10.0))
            a = novo("MO", lote=l1)

            def lote_atual():
                return linha("SELECT lote_id FROM animals WHERE id=?", (a,))["lote_id"]

            def ultima(destino):
                return linha(
                    "SELECT m.id FROM animal_movements m JOIN animals x ON x.uuid=m.animal_uuid "
                    "WHERE x.id=? AND m.to_lote_id=? AND m.cancelada_em IS NULL", (a, destino))["id"]

            db.move_animal(a, db.MovementParams(to_lote_id=l2, movement_date="2026-10-21", operator="CI"))
            assert lote_atual() == l2
            cancelar_movimentacao(ultima(l2), "piquete errado", "CI")
            assert lote_atual() == l1, lote_atual()

            db.move_animal(a, db.MovementParams(to_lote_id=l2, movement_date="2026-10-22", operator="CI"))
            corrigir_movimentacao(
                ultima(l2), db.MovementParams(to_lote_id=l3, movement_date="2026-10-22", operator="CI"),
                "era o piquete C", "CI")
            assert lote_atual() == l3, lote_atual()
            """
        )

    # -- origem da informação e aparelho (#700) ---------------------------------------------

    def test_origem_e_aparelho_vao_para_o_evento_e_para_a_auditoria(self):
        self._cenario(
            """
            a = novo("OR")

            def ultimo_evento_de_pesagem():
                return linha(
                    "SELECT e.origem_informacao, e.dispositivo FROM animal_events e "
                    "JOIN animals x ON x.uuid=e.animal_uuid "
                    "WHERE x.id=? AND e.tipo='pesagem' ORDER BY e.id DESC LIMIT 1", (a,))

            tokens = contexto.definir("app", "ci-aparelho-0001")
            try:
                add_weighing(WeighingCreate(animal_id=a, weight=410.0, weigh_date="2026-10-20", operator="CI"))
                ev = ultimo_evento_de_pesagem()
                assert (ev["origem_informacao"], ev["dispositivo"]) == ("app", "ci-aparelho-0001"), dict(ev)

                wid = linha(
                    "SELECT w.id FROM weighings w JOIN animals x ON x.uuid=w.animal_uuid "
                    "WHERE x.id=? AND w.weight=?", (a, 410.0))["id"]
                cancelar_pesagem(wid, "teste de origem", "CI", origem="app")
            finally:
                contexto.restaurar(tokens)

            (trilha,) = [t for t in eventos.trilha(entidade="weighings", entidade_id=str(wid))
                         if t["acao"] == "cancelar_pesagem"]
            assert (trilha["origem"], trilha["dispositivo"]) == ("app", "ci-aparelho-0001"), trilha

            # Fora do contexto do app, volta a ser web e sem aparelho.
            add_weighing(WeighingCreate(animal_id=a, weight=420.0, weigh_date="2026-10-21", operator="CI"))
            ev = ultimo_evento_de_pesagem()
            assert (ev["origem_informacao"], ev["dispositivo"]) == ("web", None), dict(ev)
            """
        )
