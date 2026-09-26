import unittest
from unittest.mock import patch, MagicMock
import database as db

class TestDatabaseSetLotePoligono(unittest.TestCase):
    @patch('database._conn')
    def test_set_lote_poligono_fallback_on_invalid_geojson(self, mock_conn):
        """
        Garante que quando json.loads falhar no parse ou a geometria for inválida
        para extrair os vértices, o except lida com a exceção graciosamente e
        faz a atualização usando o SQL de fallback.
        """
        mock_con_instance = MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_con_instance

        # Garante que cur.rowcount seja um int
        mock_cur = MagicMock()
        mock_cur.rowcount = 1
        mock_con_instance.execute.return_value = mock_cur

        # Isso lançará uma KeyError ao tentar acessar "coordinates"
        poligono_geojson = '{"type": "Polygon", "wrong": "format"}'
        lote_id = "LOTE_123"

        result = db.set_lote_poligono(lote_id, poligono_geojson)

        # Deve ter caído no fallback onde area_calculada = None,
        # portanto sem atualizar area_ha
        mock_con_instance.execute.assert_called_once_with(
            "UPDATE lotes SET poligono=? WHERE id=?", (poligono_geojson, lote_id)
        )
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
