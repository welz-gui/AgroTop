"""Hierarquia Organização → Produtor → Propriedade (ADR 0004 · B4 · PNIB §3).

O PNIB exige a estrutura **mesmo com uma fazenda só**, porque o titular pode ter
várias propriedades e movimentar animais entre elas. Antes desta etapa, `lote_id`
(piquete) era a única noção de lugar — e piquete não é estabelecimento perante o
órgão.

Estes testes travam o que a etapa conquistou: a hierarquia nasce completa, nada
fica sem propriedade, e o identificador da propriedade é imutável.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402
from repositories import propriedades  # noqa: E402


class BaseB4(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "b4.db"))
        db.init_db()
        db.clear_cache()

    def _linhas(self, sql, args=()):
        con = sqlite3.connect(db.DB_PATH)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args).fetchall()]
        finally:
            con.close()


class TestHierarquiaNasceCompleta(BaseB4):
    def test_banco_novo_tem_a_cadeia_inteira(self):
        """Sem hierarquia, um banco novo não tem onde ancorar animal nem piquete."""
        for tabela in ("organizacoes", "produtores", "properties"):
            with self.subTest(tabela=tabela):
                self.assertEqual(len(self._linhas(f"SELECT id FROM {tabela}")), 1)

    def test_a_cadeia_esta_ligada(self):
        p = self._linhas(
            """SELECT p.id, pr.organizacao_id
               FROM properties p JOIN produtores pr ON pr.id = p.produtor_id""")
        self.assertEqual(len(p), 1, "propriedade órfã de produtor")
        self.assertTrue(p[0]["organizacao_id"], "produtor órfão de organização")

    def test_seed_e_idempotente(self):
        """Rodar init_db duas vezes não pode duplicar a hierarquia."""
        db.init_db(forcar=True)   # a guarda pularia; aqui o seed tem de rodar
        self.assertEqual(len(self._linhas("SELECT id FROM properties")), 1)

    def test_padrao_devolve_a_propriedade_com_nomes_da_cadeia(self):
        p = propriedades.padrao()
        self.assertEqual(p["nome"], propriedades.NOME_PADRAO)
        self.assertTrue(p["produtor_nome"])
        self.assertTrue(p["organizacao_nome"])


class TestNadaFicaSemPropriedade(BaseB4):
    def test_animais_do_seed_tem_propriedade(self):
        sem = self._linhas("SELECT id FROM animals WHERE property_id IS NULL")
        self.assertEqual(sem, [], f"animais sem propriedade: {sem}")

    def test_lotes_do_seed_tem_propriedade(self):
        sem = self._linhas("SELECT id FROM lotes WHERE property_id IS NULL")
        self.assertEqual(sem, [], f"lotes sem propriedade: {sem}")

    def test_animal_novo_nasce_com_propriedade(self):
        """Se a escrita não preencher, a etapa B4.3 nunca poderá exigir a coluna."""
        db.add_animal("P1", "Nelore", "M", None, "2026-01-01",
                      300.0, 500.0, 1000.0, "P01", None)
        a = self._linhas("SELECT property_id FROM animals WHERE id='P1'")[0]
        self.assertTrue(a["property_id"], "animal novo sem propriedade")

    def test_animal_herda_a_propriedade_do_piquete(self):
        lote = self._linhas("SELECT id, property_id FROM lotes LIMIT 1")[0]
        db.add_animal("P2", "Nelore", "M", None, "2026-01-01",
                      300.0, 500.0, 1000.0, lote["id"], None)
        a = self._linhas("SELECT property_id FROM animals WHERE id='P2'")[0]
        self.assertEqual(a["property_id"], lote["property_id"])

    def test_animal_sem_piquete_usa_a_padrao(self):
        db.add_animal("P3", "Nelore", "M", None, "2026-01-01",
                      300.0, 500.0, 1000.0, None, None)
        a = self._linhas("SELECT property_id FROM animals WHERE id='P3'")[0]
        self.assertEqual(a["property_id"], propriedades.padrao()["id"])

    def test_piquete_novo_nasce_com_propriedade(self):
        db.add_lote(db.LoteData("PX", "Piquete Novo", 10.0, 12.0))
        l = self._linhas("SELECT property_id FROM lotes WHERE id='PX'")[0]
        self.assertTrue(l["property_id"], "piquete novo sem propriedade")

    def test_backfill_e_idempotente(self):
        con = sqlite3.connect(db.DB_PATH)
        con.row_factory = sqlite3.Row
        try:
            n1 = propriedades._backfill_property_id(con)
            con.commit()
        finally:
            con.close()
        self.assertEqual(n1, 0, "backfill mexeu em linha já preenchida")


class TestIdentificadorImutavel(BaseB4):
    """§3.4: o identificador da propriedade é interno e não muda."""

    def test_atualizar_nao_altera_id_nem_produtor(self):
        p = propriedades.padrao()
        propriedades.atualizar(p["id"], id="OUTRO", produtor_id="OUTRO",
                               nome="Fazenda Boa Vista")
        depois = propriedades.get(p["id"])
        self.assertIsNotNone(depois, "o id da propriedade mudou")
        self.assertEqual(depois["produtor_id"], p["produtor_id"],
                         "titularidade mudou por edição de cadastro — isso é a B6")
        self.assertEqual(depois["nome"], "Fazenda Boa Vista")

    def test_atualizar_sem_campo_valido_nao_faz_nada(self):
        p = propriedades.padrao()
        self.assertFalse(propriedades.atualizar(p["id"], campo_inventado="x"))


class TestMovimentacaoEntrePropriedades(BaseB4):
    def test_animal_acompanha_a_propriedade_do_piquete_de_destino(self):
        """Hoje o animal segue o piquete. Tratar isso como trânsito é a B6."""
        outra = propriedades.criar_propriedade(
            propriedades.padrao()["produtor_id"], "Segunda propriedade")
        db.add_lote(db.LoteData("PZ", "Piquete da segunda", 10.0, 12.0, property_id=outra))
        db.clear_cache()

        aid = db.get_all_animals(status="ativo")[0]["id"]
        db.move_animal(aid, "PZ", "2026-07-20", operator="op1")

        a = self._linhas("SELECT property_id FROM animals WHERE id=?", (aid,))[0]
        self.assertEqual(a["property_id"], outra,
                         "animal mudou de piquete mas ficou na propriedade antiga")


class TestBackfillComVariasPropriedades(unittest.TestCase):
    """_backfill_property_id só serve como rede de segurança para bancos
    anteriores à migração 0016 (property_id virou NOT NULL) — no schema
    atual, criado por db.init_db(), a coluna nunca fica NULL. Por isso este
    teste monta à parte um schema mínimo sem a restrição, simulando um banco
    antigo, em vez de usar BaseB4 (onde `UPDATE ... SET property_id=NULL`
    hoje violaria a constraint e mascararia o que se quer provar)."""

    def test_backfill_nao_adivinha_com_mais_de_uma(self):
        """Com várias propriedades, atribuir seria inventar localização.

        Localização errada num sistema de rastreabilidade é pior que ausente.
        """
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("CREATE TABLE properties (id TEXT PRIMARY KEY)")
        con.execute("CREATE TABLE animals (id TEXT PRIMARY KEY, property_id TEXT)")
        con.execute("CREATE TABLE lotes (id TEXT PRIMARY KEY, property_id TEXT)")
        con.execute("INSERT INTO properties VALUES ('P1')")
        con.execute("INSERT INTO properties VALUES ('P2')")
        con.execute("INSERT INTO animals VALUES ('A1', NULL)")
        con.commit()

        n = propriedades._backfill_property_id(con)
        con.commit()

        self.assertEqual(n, 0, "backfill adivinhou a propriedade")
        a = con.execute(
            "SELECT property_id FROM animals WHERE id='A1'").fetchone()
        self.assertIsNone(a["property_id"],
                           "backfill preencheu mesmo sem poder decidir")


if __name__ == "__main__":
    unittest.main()
