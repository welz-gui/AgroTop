import unittest
import database as db
import repositories.conexao as conexao

class TestCacheInvalidation(unittest.TestCase):
    def setUp(self):
        db.init_db()
        db.clear_cache()
        with db._conn() as con:
            con.execute("DELETE FROM insumos")

    def test_cache_invalidation_get_all_insumos_dict(self):
        # Setup pure fn wrapper with mock cache_clear for non-streamlit testing
        # When running without streamlit, fallback cache is NO-OP.
        # But wait, we want to ensure clear_cache runs without error.

        # Initial call should return empty dict
        d1 = db.get_all_insumos_dict()
        self.assertEqual(d1, {})

        # Adding a new insumo should trigger cache invalidation
        db.add_new_insumo(db.InsumoCreate("Test Insumo", "A", "kg", 10, 5, 1.0))

        # Second call should fetch the newly added insumo
        d2 = db.get_all_insumos_dict()
        self.assertEqual(len(d2), 1)
        insumo = list(d2.values())[0]
        self.assertEqual(insumo["name"], "Test Insumo")

if __name__ == '__main__':
    unittest.main()
