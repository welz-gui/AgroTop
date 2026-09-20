import unittest
import os
import sqlite3
import datetime
import tempfile

os.environ["AGROTOP_TESTING"] = "1"
os.environ["AGROTOP_FORCE_SQLITE"] = "1"

import database as db

class TestInsumoPrazoReposicao(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, f"test_db_prazo_{id(self)}.sqlite3")
        # configurar_sqlite() (não mutação direta de db._conexao.DB_PATH) é o
        # jeito certo de trocar de banco em teste — ela fecha o pool antigo
        # antes de apontar pro novo caminho. Sem isso, uma conexão SQLite
        # ociosa continua com o arquivo antigo aberto, e no Windows isso
        # impede o tempfile.TemporaryDirectory de apagar o diretório no
        # tearDown (PermissionError: arquivo em uso).
        db.configurar_sqlite(self.db_path)
        db.init_db(forcar=True)
        db.clear_cache()

    def tearDown(self):
        db.configurar_sqlite(":memory:")
        db.clear_cache()
        self.temp_dir.cleanup()

    def test_migration_existing_database(self):
        """Migration should add prazo_reposicao_dias with DEFAULT 0."""
        db_path_old = os.path.join(self.temp_dir.name, f"test_db_old_{id(self)}.sqlite3")
        db.configurar_sqlite(db_path_old)
        db.init_db(forcar=True)

        # `sqlite3.Connection` como context manager só gerencia a transação
        # (commit/rollback) — não fecha a conexão. Sem `.close()` explícito,
        # o handle do arquivo continua aberto, e o Windows recusa apagar o
        # diretório temporário no tearDown (funciona "por acaso" no Linux,
        # que permite deletar arquivo aberto).
        con = sqlite3.connect(db_path_old)
        con.row_factory = sqlite3.Row
        try:
            # Now drop the column
            con.execute("CREATE TABLE insumos_old AS SELECT id, name, category, unit, current_stock, min_stock, cost_per_unit, supplier, notes, created_at FROM insumos")
            con.execute("DROP TABLE insumos")
            con.execute("ALTER TABLE insumos_old RENAME TO insumos")
            con.execute("INSERT INTO insumos (name, category, unit, current_stock, min_stock, cost_per_unit) VALUES ('Old Insumo', 'medicamento', 'ml', 0, 0, 0)")
            con.commit()

            # Now trigger migration
            db._migrate(con)
            con.commit()

            # Verify the column was added and the old row has default 0
            row = con.execute("SELECT * FROM insumos WHERE name='Old Insumo'").fetchone()
            self.assertIn("prazo_reposicao_dias", row.keys())
            self.assertEqual(row["prazo_reposicao_dias"], 0)
        finally:
            con.close()

        # Volta pro banco da spec desta classe.
        db.configurar_sqlite(self.db_path)
        db.init_db(forcar=True)

    def test_create_read_roundtrip_with_nonzero_prazo(self):
        """We can create an insumo with a specific prazo and read it back."""
        insumo = db.InsumoCreate(
            name="Insumo Rapido",
            category="trato",
            unit="kg",
            initial_stock=100.0,
            min_stock=20.0,
            cost_per_unit=5.0,
            prazo_reposicao_dias=7
        )
        db.add_new_insumo(insumo)
        db.clear_cache()

        all_insumos = db.get_all_insumos()
        created = next(i for i in all_insumos if i["name"] == "Insumo Rapido")
        self.assertEqual(created["prazo_reposicao_dias"], 7)

    def test_create_read_roundtrip_with_default_zero(self):
        """If prazo is not provided, it defaults to 0."""
        insumo = db.InsumoCreate(
            name="Insumo Normal",
            category="trato",
            unit="kg",
            initial_stock=100.0,
            min_stock=20.0,
            cost_per_unit=5.0
            # prazo_reposicao_dias omitted, should default to 0
        )
        db.add_new_insumo(insumo)
        db.clear_cache()

        all_insumos = db.get_all_insumos()
        created = next(i for i in all_insumos if i["name"] == "Insumo Normal")
        self.assertEqual(created["prazo_reposicao_dias"], 0)

    def test_previsao_estoque_incorporates_nonzero_prazo(self):
        """The previsao_estoque function passes the nonzero prazo correctly."""
        insumo = db.InsumoCreate(
            name="Insumo Demorado",
            category="trato",
            unit="kg",
            initial_stock=10.0,
            min_stock=0.0,
            cost_per_unit=1.0,
            prazo_reposicao_dias=4
        )
        db.add_new_insumo(insumo)

        with db._conn() as con:
            prop_id = con.execute("SELECT id FROM properties LIMIT 1").fetchone()[0]
            con.execute("INSERT OR IGNORE INTO lotes (id, name, property_id) VALUES ('lote-1', 'Lote Teste', ?)", (prop_id,))
            insumo_id = con.execute("SELECT id FROM insumos WHERE name='Insumo Demorado'").fetchone()[0]
            con.execute(
                "INSERT INTO feeding_plans (lote_id, product_name, insumo_id, quantity, unit, frequency) VALUES (?, ?, ?, ?, ?, ?)",
                ('lote-1', "Trato Teste", insumo_id, 5.0, "kg", "diario")
            )

        db.clear_cache()

        previsao = db.previsao_estoque()
        item = next(i for i in previsao if i["nome"] == "Insumo Demorado")

        self.assertEqual(item["urgencia"], "critica")

        ruptura_dt = datetime.date.fromisoformat(item["data_ruptura"])
        comprar_dt = datetime.date.fromisoformat(item["comprar_ate"])
        self.assertEqual((ruptura_dt - comprar_dt).days, 4)

if __name__ == '__main__':
    unittest.main()
