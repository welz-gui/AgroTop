import unittest

from services.estados_dispositivo import ESTADOS
from services.reconciliacao_dispositivos import reconciliar


class TestReconciliar(unittest.TestCase):
    def test_separa_novos_e_existentes_preservando_a_ordem(self):
        novos = [
            {"codigo_visual": "BR0002", "tipo": "brinco"},
            {"codigo_visual": "BR0004", "tipo": "boton"},
        ]
        resultado = reconciliar(
            [
                {"codigo_visual": "BR0001", "tipo": "brinco"},
                novos[0],
                {"codigo_visual": "BR0003", "tipo": "boton"},
                novos[1],
            ],
            {"BR0001": "aplicado", "BR0003": "disponivel"},
        )

        self.assertEqual(resultado["para_gravar"], novos)
        self.assertEqual(
            resultado["ja_existentes"],
            [
                {"codigo_visual": "BR0001", "status_atual": "aplicado"},
                {"codigo_visual": "BR0003", "status_atual": "disponivel"},
            ],
        )
        self.assertEqual(
            resultado["resumo"], {"total": 4, "para_gravar": 2, "ja_existentes": 2}
        )

    def test_todos_os_doze_estados_bloqueiam_nova_linha(self):
        itens = [{"codigo_visual": f"BR{indice:04d}"} for indice in range(12)]
        estoque = dict(zip((item["codigo_visual"] for item in itens), ESTADOS))

        resultado = reconciliar(itens, estoque)

        self.assertEqual(resultado["para_gravar"], [])
        self.assertEqual(
            resultado["ja_existentes"],
            [
                {"codigo_visual": f"BR{indice:04d}", "status_atual": estado}
                for indice, estado in enumerate(ESTADOS)
            ],
        )
        self.assertEqual(
            resultado["resumo"], {"total": 12, "para_gravar": 0, "ja_existentes": 12}
        )

    def test_estado_terminal_tambem_e_reportado_com_status(self):
        resultado = reconciliar(
            [{"codigo_visual": "BR0001"}],
            {"BR0001": "inutilizado"},
        )

        self.assertEqual(resultado["para_gravar"], [])
        self.assertEqual(
            resultado["ja_existentes"],
            [{"codigo_visual": "BR0001", "status_atual": "inutilizado"}],
        )

    def test_item_sem_codigo_vai_para_existentes_com_motivo(self):
        itens = [{"tipo": "brinco"}, {"codigo_visual": ""}, {"codigo_visual": None}]

        resultado = reconciliar(itens, {})

        self.assertEqual(resultado["para_gravar"], [])
        self.assertEqual(
            resultado["ja_existentes"],
            [
                {"codigo_visual": "", "status_atual": "sem_codigo"},
                {"codigo_visual": "", "status_atual": "sem_codigo"},
                {"codigo_visual": "", "status_atual": "sem_codigo"},
            ],
        )
        self.assertEqual(
            resultado["resumo"], {"total": 3, "para_gravar": 0, "ja_existentes": 3}
        )

    def test_listas_vazias_e_consistentes(self):
        esperado = {
            "para_gravar": [],
            "ja_existentes": [],
            "resumo": {"total": 0, "para_gravar": 0, "ja_existentes": 0},
        }

        self.assertEqual(reconciliar([], {}), esperado)
        self.assertEqual(
            reconciliar([{"codigo_visual": "BR0001"}], {}),
            {
                "para_gravar": [{"codigo_visual": "BR0001"}],
                "ja_existentes": [],
                "resumo": {"total": 1, "para_gravar": 1, "ja_existentes": 0},
            },
        )
        self.assertEqual(
            reconciliar([], {"BR0001": "disponivel"}),
            esperado,
        )

    def test_quinhentos_itens_duplicados_usam_lookup_do_dict(self):
        itens = [{"codigo_visual": f"BR{indice:04d}"} for indice in range(500)]
        estoque = {
            item["codigo_visual"]: "disponivel"
            for item in itens
        }

        resultado = reconciliar(itens, estoque)

        self.assertEqual(resultado["para_gravar"], [])
        self.assertEqual(resultado["resumo"], {"total": 500, "para_gravar": 0, "ja_existentes": 500})


if __name__ == "__main__":
    unittest.main()
