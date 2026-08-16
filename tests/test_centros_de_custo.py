import unittest

from services.centros_de_custo import consolidar


class TestConsolidar(unittest.TestCase):
    def test_junta_fixo_e_animal_do_mesmo_piquete(self):
        linhas = consolidar(
            fixos_por_lote={"P1": 500.0},
            animal_por_lote={"P1": 300.0},
            cabecas_por_lote={"P1": 10},
            nomes_lotes={"P1": "Piquete Norte"})
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0], {
            "lote_id": "P1", "nome": "Piquete Norte", "cabecas": 10,
            "custos_fixos": 500.0, "custos_animal": 300.0, "total": 800.0})

    def test_lote_id_none_vira_geral_da_fazenda(self):
        linhas = consolidar(
            fixos_por_lote={None: 1000.0},
            animal_por_lote={},
            cabecas_por_lote={},
            nomes_lotes={})
        self.assertEqual(linhas[0]["nome"], "Geral da Fazenda")
        self.assertEqual(linhas[0]["lote_id"], None)
        self.assertEqual(linhas[0]["cabecas"], 0)

    def test_piquete_so_com_custo_de_animal_sem_fixo_alocado(self):
        linhas = consolidar(
            fixos_por_lote={}, animal_por_lote={"P2": 150.0},
            cabecas_por_lote={"P2": 5}, nomes_lotes={"P2": "Piquete Sul"})
        self.assertEqual(linhas[0]["custos_fixos"], 0.0)
        self.assertEqual(linhas[0]["custos_animal"], 150.0)
        self.assertEqual(linhas[0]["total"], 150.0)

    def test_ordena_do_maior_total_para_o_menor(self):
        linhas = consolidar(
            fixos_por_lote={"P1": 100.0, "P2": 900.0, "P3": 500.0},
            animal_por_lote={}, cabecas_por_lote={},
            nomes_lotes={"P1": "A", "P2": "B", "P3": "C"})
        self.assertEqual([l["lote_id"] for l in linhas], ["P2", "P3", "P1"])

    def test_nome_de_lote_desconhecido_cai_no_proprio_id(self):
        linhas = consolidar(
            fixos_por_lote={"P9": 10.0}, animal_por_lote={},
            cabecas_por_lote={}, nomes_lotes={})
        self.assertEqual(linhas[0]["nome"], "P9")

    def test_sem_nenhum_custo_devolve_lista_vazia(self):
        self.assertEqual(consolidar({}, {}, {}, {}), [])

    def test_empate_no_total_desempata_por_nome(self):
        linhas = consolidar(
            fixos_por_lote={"P1": 100.0, "P2": 100.0},
            animal_por_lote={}, cabecas_por_lote={},
            nomes_lotes={"P1": "Zebra", "P2": "Alfa"})
        self.assertEqual([l["nome"] for l in linhas], ["Alfa", "Zebra"])


if __name__ == "__main__":
    unittest.main()
