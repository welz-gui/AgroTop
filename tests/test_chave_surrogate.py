"""Guardas da chave surrogate de `animals` (ADR 0004, etapa B1).

O PNIB §4.1 exige identificador interno **imutável e separado do brinco**: trocar
o brinco não pode trocar a identidade do animal. A migração aconteceu por
etapas (B1.1 a B1.7), e estes testes travam o que cada uma conquistou —
`uuid` é a PK desde a B1.7; `id` (o brinco) continua único, mas não é mais a
identidade do registro.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402
from repositories import identificadores as ident_repo  # noqa: E402
from repositories.animais import novo_uuid  # noqa: E402


class BaseSurrogate(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "surrogate.db"))
        db.init_db()
        db.clear_cache()

    def _linhas(self, sql, args=()):
        con = sqlite3.connect(db.DB_PATH)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args).fetchall()]
        finally:
            con.close()


class TestUuidGerado(BaseSurrogate):
    def test_todo_animal_tem_uuid(self):
        """Nenhum animal pode ficar sem identificador interno — nem os de seed."""
        sem = self._linhas("SELECT id FROM animals WHERE uuid IS NULL OR uuid=''")
        self.assertEqual(sem, [], f"animais sem uuid: {[a['id'] for a in sem]}")

    def test_uuid_e_unico(self):
        linhas = self._linhas("SELECT uuid FROM animals")
        valores = [l["uuid"] for l in linhas]
        self.assertEqual(len(valores), len(set(valores)), "há uuid repetido")

    def test_animal_novo_nasce_com_uuid(self):
        db.add_animal(db.AnimalData("SURR1", "Nelore", "M", None, "2026-01-01",
                      300.0, 500.0, 0.0, None, None))
        a = self._linhas("SELECT uuid FROM animals WHERE id=?", ("SURR1",))[0]
        self.assertTrue(a["uuid"], "add_animal não gerou uuid")

    def test_backfill_e_idempotente(self):
        """Rodar de novo não pode reescrever uuid já atribuído.

        Se reescrevesse, o identificador deixaria de ser imutável — que é
        exatamente o que o §4.1 exige dele.
        """
        antes = {l["id"]: l["uuid"] for l in self._linhas("SELECT id, uuid FROM animals")}
        with db._conn() as con:
            alterados = db._backfill_uuids(con)
        depois = {l["id"]: l["uuid"] for l in self._linhas("SELECT id, uuid FROM animals")}
        self.assertEqual(alterados, 0, "backfill mexeu em quem já tinha uuid")
        self.assertEqual(antes, depois)

    def test_backfill_preenche_quem_esta_sem(self):
        """`_backfill_uuids` só importa para banco anterior à etapa B1.1, de
        quando `uuid` nem existia. Desde a B1.7 a coluna é PK NOT NULL, então
        um `UPDATE ... SET uuid=NULL` real vira `IntegrityError` em vez de
        simular o cenário legado — por isso o teste monta um schema à parte,
        sem a restrição, só para esse caso antigo (mesma solução usada para
        `_backfill_property_id` na dívida nº 3 do ROADMAP)."""
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("CREATE TABLE animals (id TEXT PRIMARY KEY, uuid TEXT)")
        con.execute("INSERT INTO animals VALUES ('A1', 'uuid-existente')")
        con.execute("INSERT INTO animals VALUES ('A2', NULL)")
        con.commit()

        alterados = db._backfill_uuids(con)
        con.commit()

        self.assertEqual(alterados, 1)
        depois = {r["id"]: r["uuid"] for r in con.execute(
            "SELECT id, uuid FROM animals").fetchall()}
        self.assertEqual(depois["A1"], "uuid-existente",
                          "backfill mexeu em quem já tinha uuid")
        self.assertTrue(depois["A2"], "backfill não preencheu quem estava sem")


class TestFormatoDoUuid(unittest.TestCase):
    def test_novo_uuid_gera_valores_distintos(self):
        valores = {novo_uuid() for _ in range(200)}
        self.assertEqual(len(valores), 200)

    def test_formato_uuid4(self):
        v = novo_uuid()
        self.assertEqual(len(v), 36)
        self.assertEqual([len(p) for p in v.split("-")], [8, 4, 4, 4, 12])


# ══════════════════════════════════════════════════════════════════════════════
class TestEspelhoNasFilhas(BaseSurrogate):
    """Etapa B1.6 — `animal_uuid` é a ÚNICA ligação com o animal.

    Até a etapa 5 as duas colunas conviviam e o teste comparava uma com a outra.
    A etapa 6 removeu `animal_id`, então não há mais espelho a conferir: a
    garantia passou a ser mais forte — nenhuma linha órfã e nenhum uuid nulo.
    """

    TABELAS = ["weighings", "medications", "animal_costs", "animal_movements",
               "animal_photos", "deaths", "sales", "insumo_transactions"]

    def test_todas_as_filhas_tem_a_coluna(self):
        for t in self.TABELAS:
            with self.subTest(tabela=t):
                qt = f'"{t}"'
                cols = {r["name"] for r in self._linhas(f"PRAGMA table_info({qt})")}
                self.assertIn("animal_uuid", cols)

    def test_animal_id_foi_removido(self):
        """A coluna legada não pode voltar por descuido num CREATE TABLE."""
        for t in self.TABELAS:
            with self.subTest(tabela=t):
                qt = f'"{t}"'
                cols = {r["name"] for r in self._linhas(f"PRAGMA table_info({qt})")}
                self.assertNotIn("animal_id", cols,
                                 f"{t}: coluna legada reapareceu (etapa B1.6)")

    def test_nenhuma_linha_orfa(self):
        """Todo `animal_uuid` preenchido aponta para um animal que existe.

        Sem `animal_id`, esta é a única coisa que liga a linha ao animal — se
        apontar para nada, o histórico do animal se perde em silêncio.
        """
        for t in self.TABELAS:
            with self.subTest(tabela=t):
                orfas = self._linhas(
                    f"SELECT t.id FROM {t} t LEFT JOIN animals a ON a.uuid = t.animal_uuid "
                    f"WHERE t.animal_uuid IS NOT NULL AND a.uuid IS NULL")
                self.assertEqual(orfas, [], f"{t}: linhas órfãs")

    def test_backfill_das_filhas_e_idempotente(self):
        with db._conn() as con:
            n = db._backfill_animal_uuid(con)
        self.assertEqual(n, 0, "backfill reescreveu linha que já tinha animal_uuid")

    def test_escrita_nova_ja_preenche_o_espelho(self):
        """MUDANÇA DECLARADA na etapa B1.4 — antes afirmava o contrário.

        Na etapa 2 este teste documentava que só o backfill preenchia, e o
        docstring anunciava que mudaria quando as escritas passassem a gravar o
        uuid. Foi o que aconteceu: agora a escrita já chega completa, e o
        backfill vira rede de segurança para dados anteriores.

        A troca é deliberada, não regressão silenciosa.
        """
        aid = self._linhas("SELECT id FROM animals LIMIT 1")[0]["id"]
        db.add_weighing(aid, 400.0, "2026-07-31")
        pendente = self._linhas("SELECT id FROM weighings WHERE animal_uuid IS NULL")
        self.assertEqual(pendente, [], "escrita nova deixou o espelho vazio")

        # O backfill continua idempotente: não há o que preencher.
        with db._conn() as con:
            self.assertEqual(db._backfill_animal_uuid(con), 0)


# ══════════════════════════════════════════════════════════════════════════════
class TestIdentificadores(BaseSurrogate):
    """Etapa B1.3 — o brinco vira um identificador, não a identidade.

    É a etapa que torna possível o §4.2.3: trocar brinco sem apagar o anterior.
    Antes do ADR 0004 isso exigiria trocar a chave primária.
    """

    def _uuid_de(self, animal_id):
        return self._linhas("SELECT uuid FROM animals WHERE id=?", (animal_id,))[0]["uuid"]

    def test_todo_animal_tem_manejo_ativo(self):
        sem = self._linhas(
            "SELECT a.id FROM animals a WHERE NOT EXISTS ("
            "  SELECT 1 FROM animal_identifiers i WHERE i.animal_uuid=a.uuid"
            "  AND i.tipo='manejo' AND i.status='ativo')")
        self.assertEqual(sem, [], f"animais sem identificador de manejo: {sem}")

    def test_manejo_guarda_o_brinco_atual(self):
        for a in self._linhas("SELECT id, uuid FROM animals LIMIT 3"):
            with self.subTest(animal=a["id"]):
                ident = ident_repo.get_ativo(a["uuid"], "manejo")
                self.assertIsNotNone(ident)
                self.assertEqual(ident["valor"], a["id"])

    def test_backfill_de_identificadores_e_idempotente(self):
        with db._conn() as con:
            n = db._backfill_identificadores(con)
        self.assertEqual(n, 0, "backfill duplicou identificador já existente")

    def test_substituicao_preserva_o_anterior(self):
        """O coração do §4.2.3: trocar brinco não apaga o histórico."""
        a = self._linhas("SELECT id, uuid FROM animals LIMIT 1")[0]
        antigo = ident_repo.get_ativo(a["uuid"], "manejo")["valor"]

        r = ident_repo.substituir(a["uuid"], "manejo", "BRINCO-NOVO",
                                  motivo="perda do brinco original")
        self.assertTrue(r["ok"])
        db.clear_cache()

        todos = ident_repo.get_identificadores(a["uuid"])
        valores = {i["valor"]: i for i in todos}
        self.assertIn(antigo, valores, "identificador anterior foi APAGADO")
        self.assertEqual(valores[antigo]["status"], "removido")
        self.assertEqual(valores[antigo]["motivo_remocao"], "perda do brinco original")
        self.assertEqual(valores["BRINCO-NOVO"]["status"], "ativo")
        self.assertEqual(ident_repo.get_ativo(a["uuid"], "manejo")["valor"], "BRINCO-NOVO")

    def test_mesmo_valor_ativo_em_dois_animais_e_recusado(self):
        """§4.2.1/§4.2.2 — código ativo não pode estar em dois animais."""
        animais = self._linhas("SELECT uuid FROM animals LIMIT 2")
        ident_repo.aplicar(animais[0]["uuid"], "rfid", "982000123456789")
        db.clear_cache()
        r = ident_repo.aplicar(animais[1]["uuid"], "rfid", "982000123456789")
        self.assertFalse(r["ok"])
        self.assertIn("já está ativo", r["erro"])

    def test_valor_liberado_apos_remocao(self):
        """Removido não bloqueia: o histórico convive com a reutilização."""
        animais = self._linhas("SELECT uuid FROM animals LIMIT 2")
        ident_repo.aplicar(animais[0]["uuid"], "visual", "V-100")
        db.clear_cache()
        ident_repo.remover(animais[0]["uuid"], "visual", motivo="danificado")
        db.clear_cache()
        r = ident_repo.aplicar(animais[1]["uuid"], "visual", "V-100")
        self.assertTrue(r["ok"], "valor não foi liberado após remoção")

    def test_reaplicar_no_mesmo_animal_nao_duplica(self):
        a = self._linhas("SELECT uuid FROM animals LIMIT 1")[0]
        ident_repo.aplicar(a["uuid"], "sisbov", "105000000000001")
        db.clear_cache()
        r = ident_repo.aplicar(a["uuid"], "sisbov", "105000000000001")
        self.assertTrue(r["ok"])
        self.assertTrue(r["ja_existia"])


# ══════════════════════════════════════════════════════════════════════════════
class TestEscritaPreencheUuid(BaseSurrogate):
    """Etapa B1.4 — toda escrita preenche `animal_uuid` na hora.

    Antes desta etapa só o backfill preenchia, então uma linha recém-criada
    ficava com o espelho nulo até o próximo `init_db()`. Isso impede adicionar a
    FK (etapa 5): a restrição existiria, mas o dado chegaria incompleto.

    Por isso a ordem do ADR 0004 foi invertida — escrita antes da FK.
    """

    def _sem_espelho(self, tabela, animal_id):
        """Linhas sem `animal_uuid` na tabela.

        Depois da etapa 6 uma linha assim é invisível: sem `animal_id`, ela não
        pertence a animal nenhum e some do histórico sem erro nenhum.
        O `animal_id` fica no parâmetro só para a mensagem de falha ser legível.
        """
        return self._linhas(f"SELECT id FROM {tabela} WHERE animal_uuid IS NULL")

    def test_cadastro_de_animal_preenche_tudo(self):
        db.add_animal(db.AnimalData("E4A", "Nelore", "M", None, "2026-01-01",
                      300.0, 500.0, 1000.0, None, None))
        for t in ("weighings", "animal_costs"):
            with self.subTest(tabela=t):
                self.assertEqual(self._sem_espelho(t, "E4A"), [])

    def test_pesagem_preenche(self):
        aid = self._linhas("SELECT id FROM animals LIMIT 1")[0]["id"]
        db.add_weighing(aid, 411.0, "2026-07-31")
        self.assertEqual(self._sem_espelho("weighings", aid), [])

    def test_medicacao_preenche(self):
        aid = self._linhas("SELECT id FROM animals LIMIT 1")[0]["id"]
        db.add_medication(aid, "Ivermectina", 5.0, "ml", "Subcutânea", 30,
                          "2026-07-31")
        self.assertEqual(self._sem_espelho("medications", aid), [])

    def test_custo_preenche(self):
        aid = self._linhas("SELECT id FROM animals LIMIT 1")[0]["id"]
        db.add_animal_cost(aid, "sanitario", "Vacina", 25.0, "2026-07-31")
        self.assertEqual(self._sem_espelho("animal_costs", aid), [])

    def test_movimentacao_preenche(self):
        aid = self._linhas("SELECT id FROM animals LIMIT 1")[0]["id"]
        lote = self._linhas("SELECT id FROM lotes LIMIT 1")[0]["id"]
        db.move_animal(aid, lote, "manejo", "teste")
        self.assertEqual(self._sem_espelho("animal_movements", aid), [])

    def test_venda_preenche(self):
        db.add_animal(db.AnimalData("E4V", "Nelore", "M", None, "2026-01-01",
                      300.0, 500.0, 0.0, None, None))
        db.register_sale(["E4V"], "2026-07-31", "abate", "kg", 10.0)
        self.assertEqual(self._sem_espelho("sales", "E4V"), [])

    def test_obito_preenche(self):
        db.add_animal(db.AnimalData("E4M", "Nelore", "M", None, "2026-01-01",
                      300.0, 500.0, 0.0, None, None))
        db.register_death("E4M", "2026-07-31", "Cobra")
        self.assertEqual(self._sem_espelho("deaths", "E4M"), [])

    def test_nenhuma_tabela_fica_com_espelho_pendente(self):
        """Varredura final: depois de exercitar as escritas, zero pendências."""
        aid = self._linhas("SELECT id FROM animals LIMIT 1")[0]["id"]
        db.add_weighing(aid, 420.0, "2026-07-31")
        db.add_animal_cost(aid, "operacional", "Sal", 10.0, "2026-07-31")

        pendentes = {}
        for t in ("weighings", "medications", "animal_costs", "animal_movements",
                  "animal_photos", "deaths", "sales", "insumo_transactions"):
            n = self._linhas(
                f"SELECT id FROM {t} WHERE animal_uuid IS NULL")
            if n:
                pendentes[t] = len(n)
        self.assertEqual(pendentes, {}, f"escritas deixaram espelho pendente: {pendentes}")


# ══════════════════════════════════════════════════════════════════════════════
class TestIntegridadeReferencial(BaseSurrogate):
    """Etapa B1.5 — as FKs passam a apontar para `animals(uuid)`.

    Primeira etapa que **restringe** em vez de acrescentar. Só foi possível
    porque a etapa 4 garantiu que toda escrita preenche o espelho: a restrição
    encontra dado consistente.
    """

    TABELAS = ["weighings", "medications", "animal_costs", "animal_movements",
               "animal_photos", "deaths", "sales", "insumo_transactions"]

    def test_fk_declarada_nas_oito_tabelas(self):
        for t in self.TABELAS:
            with self.subTest(tabela=t):
                fks = self._linhas(f"PRAGMA foreign_key_list({t})")
                alvos = {(f["from"], f["table"], f["to"]) for f in fks}
                self.assertIn(("animal_uuid", "animals", "uuid"), alvos,
                              f"{t} sem FK de animal_uuid para animals(uuid)")

    def test_uuid_inexistente_e_recusado(self):
        """A restrição precisa BLOQUEAR de verdade, não só existir."""
        con = sqlite3.connect(db.DB_PATH)
        con.execute("PRAGMA foreign_keys=ON")
        aid = self._linhas("SELECT id FROM animals LIMIT 1")[0]["id"]
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute(
                    "INSERT INTO weighings (animal_uuid,weight,weigh_date) "
                    "VALUES(?,?,?)", ("uuid-que-nao-existe", 400.0, "2026-07-31"))
                con.commit()
        finally:
            con.close()

    def test_uuid_valido_e_aceito(self):
        """O contraponto: a FK não pode bloquear dado correto."""
        con = sqlite3.connect(db.DB_PATH)
        con.execute("PRAGMA foreign_keys=ON")
        a = self._linhas("SELECT id, uuid FROM animals LIMIT 1")[0]
        try:
            con.execute(
                "INSERT INTO weighings (animal_uuid,weight,weigh_date) "
                "VALUES(?,?,?)", (a["uuid"], 405.0, "2026-07-31"))
            con.commit()
        finally:
            con.close()
        self.assertTrue(self._linhas(
            "SELECT id FROM weighings WHERE animal_uuid=? AND weight=405.0", (a["uuid"],)))

    def test_animals_uuid_e_unico_no_schema(self):
        """A FK só é possível porque `uuid` é UNIQUE — sem isso, não há alvo."""
        idx = self._linhas("PRAGMA index_list(animals)")
        unicos = [i for i in idx if i["unique"]]
        colunas = set()
        for i in unicos:
            for c in self._linhas(f"PRAGMA index_info({i['name']})"):
                colunas.add(c["name"])
        self.assertIn("uuid", colunas, "animals.uuid não é único — a FK não se sustenta")


# ══════════════════════════════════════════════════════════════════════════════
class TestPkEhUuid(BaseSurrogate):
    """Etapa B1.7 — `uuid` vira a PK de fato, não só o alvo das FKs.

    As etapas 1 a 6 já deixavam o §4.1 verdadeiro na prática: `uuid` era
    NOT NULL/UNIQUE desde a etapa 1, e as treze tabelas com FK para `animals`
    já apontavam para `animals(uuid)`, nunca para `id` (etapa 5). Faltava só
    a PK do SQL reconhecer isso — dívida nº 2 do ROADMAP. Bancos SQLite
    antigos não recebem a troca via ALTER (mesma limitação aceita para as
    FKs, dívida nº 8): só quem nasce depois desta etapa tem `uuid` como PK.
    """

    def test_uuid_e_a_pk(self):
        cols = self._linhas("PRAGMA table_info(animals)")
        pk = {c["name"] for c in cols if c["pk"]}
        self.assertEqual(pk, {"uuid"}, f"PK de animals é {pk}, esperado uuid")

    def test_id_continua_unico_mesmo_sem_ser_pk(self):
        """O brinco não perde a unicidade ao deixar de ser identidade."""
        idx = self._linhas("PRAGMA index_list(animals)")
        colunas_unicas = set()
        for i in (r for r in idx if r["unique"]):
            for c in self._linhas(f"PRAGMA index_info({i['name']})"):
                colunas_unicas.add(c["name"])
        self.assertIn("id", colunas_unicas,
                       "id perdeu a unicidade ao deixar de ser PK")


if __name__ == "__main__":
    unittest.main()
