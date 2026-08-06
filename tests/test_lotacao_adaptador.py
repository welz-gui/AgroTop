"""Testes unitários do adaptador de lotação (Spec 0043)."""

import unittest
from services import lotacao, lotacao_adaptador


class TestLotacaoAdaptador(unittest.TestCase):
    def test_tres_animais_ativos_no_mesmo_lote(self):
        """Critério 1: Três animais ativos no mesmo lote produzem um grupo com os três pesos."""
        lotes = [{"id": "lote-1", "area_ha": 10.0}]
        animais = [
            {"id": "a1", "lote_id": "lote-1", "peso": 450.0, "status": "ativo"},
            {"id": "a2", "lote_id": "lote-1", "peso": 400.0, "status": "ativo"},
            {"id": "a3", "lote_id": "lote-1", "peso": 500.0, "status": "ativo"},
        ]

        res = lotacao_adaptador.por_lote(animais, lotes)

        self.assertIn("lote-1", res)
        self.assertEqual(res["lote-1"]["area_ha"], 10.0)
        self.assertEqual(
            res["lote-1"]["animais"],
            [{"peso": 450.0}, {"peso": 400.0}, {"peso": 500.0}],
        )

    def test_animal_inativo_e_ignorado(self):
        """Critério 2: Animal com status != 'ativo' não aparece em nenhum grupo."""
        lotes = [{"id": "lote-1", "area_ha": 10.0}]
        animais = [
            {"id": "a1", "lote_id": "lote-1", "peso": 450.0, "status": "vendido"},
            {"id": "a2", "lote_id": "lote-1", "peso": 400.0, "status": "morto"},
            {"id": "a3", "lote_id": "lote-1", "peso": 500.0, "status": "inativo"},
        ]

        res = lotacao_adaptador.por_lote(animais, lotes)

        self.assertEqual(res["lote-1"]["animais"], [])

    def test_lote_sem_animais_ativos_retorna_lista_vazia(self):
        """Critério 3: Lote sem nenhum animal ativo aparece no resultado com 'animais': []."""
        lotes = [
            {"id": "lote-1", "area_ha": 10.0},
            {"id": "lote-2", "area_ha": 20.0},
        ]
        animais = [
            {"id": "a1", "lote_id": "lote-1", "peso": 450.0, "status": "ativo"}
        ]

        res = lotacao_adaptador.por_lote(animais, lotes)

        self.assertIn("lote-2", res)
        self.assertEqual(res["lote-2"]["animais"], [])

    def test_animal_com_lote_id_inexistente_ou_none_e_descartado(self):
        """Critério 4: Animal com lote_id inexistente ou None não entra em nenhum grupo e não quebra."""
        lotes = [{"id": "lote-1", "area_ha": 10.0}]
        animais = [
            {"id": "a1", "lote_id": "lote-999", "peso": 450.0, "status": "ativo"},
            {"id": "a2", "lote_id": None, "peso": 400.0, "status": "ativo"},
        ]

        res = lotacao_adaptador.por_lote(animais, lotes)

        self.assertEqual(list(res.keys()), ["lote-1"])
        self.assertEqual(res["lote-1"]["animais"], [])

    def test_listas_vazias_retornam_dict_vazio(self):
        """Critério 5: por_lote([], []) devolve {}."""
        self.assertEqual(lotacao_adaptador.por_lote([], []), {})

    def test_encadeamento_com_avaliar_lotacao(self):
        """Critério 6: O resultado aplicado com services.lotacao.avaliar_lotacao produz situação sem exceção."""
        lotes = [{"id": "lote-1", "area_ha": 10.0}]
        animais = [
            {"id": "a1", "lote_id": "lote-1", "peso": 450.0, "status": "ativo"},
            {"id": "a2", "lote_id": "lote-1", "peso": 450.0, "status": "ativo"},
        ]

        res = lotacao_adaptador.por_lote(animais, lotes)
        info_lote = res["lote-1"]

        avaliacao = lotacao.avaliar_lotacao(
            info_lote["area_ha"], info_lote["animais"], ua_por_ha_alvo=1.0
        )

        self.assertIn("situacao", avaliacao)
        self.assertIn(avaliacao["situacao"], ["ocioso", "adequado", "sobrecarregado"])
        self.assertEqual(avaliacao["cabecas"], 2)

    def test_animal_com_peso_zero_ou_ausente(self):
        """Animal com peso zero ou ausente ainda entra no grupo sem falhar."""
        lotes = [{"id": "lote-1", "area_ha": 10.0}]
        animais = [
            {"id": "a1", "lote_id": "lote-1", "peso": 0.0, "status": "ativo"},
            {"id": "a2", "lote_id": "lote-1", "peso": None, "status": "ativo"},
        ]

        res = lotacao_adaptador.por_lote(animais, lotes)

        self.assertEqual(len(res["lote-1"]["animais"]), 2)
        self.assertEqual(res["lote-1"]["animais"][0]["peso"], 0.0)
        self.assertEqual(res["lote-1"]["animais"][1]["peso"], 0.0)


if __name__ == "__main__":
    unittest.main()
