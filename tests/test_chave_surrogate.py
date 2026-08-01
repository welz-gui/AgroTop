"""Guardas da chave surrogate de `animals` (ADR 0004, etapa B1).

O PNIB §4.1 exige identificador interno **imutável e separado do brinco**: trocar
o brinco não pode trocar a identidade do animal. Hoje `animals.id` ainda é o
brinco e ainda é a PK — a migração acontece por etapas, e estes testes travam o
que já foi conquistado em cada uma.
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
        db.add_animal("SURR1", "Nelore", "M", None, "2026-01-01",
                      300.0, 500.0, 0.0, None, None)
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
        con = sqlite3.connect(db.DB_PATH)
        con.execute("UPDATE animals SET uuid=NULL WHERE id=(SELECT MIN(id) FROM animals)")
        con.commit(); con.close()

        with db._conn() as c:
            alterados = db._backfill_uuids(c)
        self.assertEqual(alterados, 1)
        self.assertEqual(
            self._linhas("SELECT id FROM animals WHERE uuid IS NULL"), [])


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
    """Etapa B1.2 — `animal_uuid` espelhado nas 8 tabelas filhas.

    Enquanto as FKs ainda apontam para `animal_id`, as duas colunas convivem.
    É o que torna a etapa reversível: nada depende do espelho ainda.
    """

    TABELAS = ["weighings", "medications", "animal_costs", "animal_movements",
               "animal_photos", "deaths", "sales", "insumo_transactions"]

    def test_todas_as_filhas_tem_a_coluna(self):
        for t in self.TABELAS:
            with self.subTest(tabela=t):
                cols = {r["name"] for r in self._linhas(f"PRAGMA table_info({t})")}
                self.assertIn("animal_uuid", cols)

    def test_espelho_confere_com_o_animal(self):
        """Toda linha com animal_id tem o uuid do animal correspondente."""
        for t in self.TABELAS:
            with self.subTest(tabela=t):
                divergentes = self._linhas(
                    f"SELECT t.animal_id FROM {t} t JOIN animals a ON a.id = t.animal_id "
                    f"WHERE t.animal_uuid IS NULL OR t.animal_uuid <> a.uuid")
                self.assertEqual(divergentes, [],
                                 f"{t}: espelho divergente do animals.uuid")

    def test_backfill_das_filhas_e_idempotente(self):
        with db._conn() as con:
            n = db._backfill_animal_uuid(con)
        self.assertEqual(n, 0, "backfill reescreveu linha que já tinha animal_uuid")

    def test_escrita_nova_ainda_nao_preenche_o_espelho(self):
        """Documenta o estado ATUAL da migração, não o desejado.

        Hoje só o backfill preenche. Na etapa 5 as consultas passam a gravar o
        uuid direto — e este teste muda junto, deliberadamente.
        """
        aid = self._linhas("SELECT id FROM animals LIMIT 1")[0]["id"]
        db.add_weighing(aid, 400.0, "2026-07-31")
        pendente = self._linhas(
            "SELECT id FROM weighings WHERE animal_uuid IS NULL AND animal_id=?", (aid,))
        self.assertTrue(pendente, "esperado: escrita nova ainda não preenche o espelho")

        with db._conn() as con:
            db._backfill_animal_uuid(con)
        self.assertEqual(
            self._linhas("SELECT id FROM weighings WHERE animal_uuid IS NULL"), [])


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


if __name__ == "__main__":
    unittest.main()
