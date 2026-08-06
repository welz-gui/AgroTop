import unittest

from services.conformidade import avaliar
from services.conformidade_adaptador import montar_rebanho


class MontarRebanhoTests(unittest.TestCase):
    def test_monta_indicadores_e_passa_no_avaliador(self):
        animais = [
            {"uuid": "a1", "status": "ativo", "property_id": "p1", "origem": "nascido", "birth_estimated": False, "mae_uuid": "m1"},
            {"uuid": "a2", "status": "ativo", "property_id": None, "origem": "nascido", "birth_estimated": True, "mae_uuid": None},
            {"uuid": "a3", "status": "ativo", "property_id": "p1", "origem": "comprado", "birth_estimated": True, "mae_uuid": None},
        ]
        resultado = montar_rebanho(
            animais=animais,
            identificadores_ativos=[
                {"animal_uuid": "a1", "tipo": "oficial_pnib"},
                {"animal_uuid": "a1", "tipo": "manejo"},
                {"animal_uuid": "a2", "tipo": "manejo"},
            ],
            dispositivos=[
                {"animal_uuid": "a1", "divergencia": True},
                {"animal_uuid": "a2", "divergencia": None},
            ],
            eventos_pendentes=2,
            movimentacoes_abertas=[
                {"status": "rascunho", "data_prevista": "2032-12-31"},
                {"status": "em_transito", "data_prevista": "2033-01-02"},
            ],
            referencia="2033-01-01",
        )

        self.assertEqual(
            resultado,
            {
                "animais_ativos": 3,
                "com_identificacao_oficial": 1,
                "com_identificacao_manejo": 2,
                "com_propriedade": 2,
                "nascidos_sem_mae": 1,
                "eventos_pendentes_sincronizacao": 2,
                "com_nascimento_estimado": 2,
                "dispositivos_com_divergencia": 1,
                "movimentacoes_abertas_vencidas": 1,
            },
        )
        self.assertEqual(avaliar(resultado, "2033-01-01")["escore"], 46.67)

    def test_ignora_inativos_em_todos_os_indicadores(self):
        resultado = montar_rebanho(
            animais=[
                {"uuid": "ativo", "status": "ativo", "property_id": "p1", "origem": "comprado", "birth_estimated": False, "mae_uuid": "m"},
                {"uuid": "inativo", "status": "vendido", "property_id": "p2", "origem": "nascido", "birth_estimated": True, "mae_uuid": None},
            ],
            identificadores_ativos=[
                {"animal_uuid": "inativo", "tipo": "oficial_pnib"},
                {"animal_uuid": "inativo", "tipo": "manejo"},
            ],
            dispositivos=[{"animal_uuid": "inativo", "divergencia": True}],
            eventos_pendentes=0,
            movimentacoes_abertas=[],
            referencia="2033-01-01",
        )

        self.assertEqual(resultado["animais_ativos"], 1)
        self.assertEqual(resultado["com_propriedade"], 1)
        self.assertEqual(resultado["com_identificacao_oficial"], 0)
        self.assertEqual(resultado["com_identificacao_manejo"], 0)
        self.assertEqual(resultado["dispositivos_com_divergencia"], 0)
        self.assertEqual(resultado["nascidos_sem_mae"], 0)

    def test_propriedade_atual_nao_e_propriedade_de_nascimento(self):
        resultado = montar_rebanho(
            animais=[
                {
                    "uuid": "a1",
                    "status": "ativo",
                    "property_id": None,
                    "propriedade_nascimento_id": "p1",
                    "origem": "nascido",
                    "birth_estimated": False,
                    "mae_uuid": None,
                }
            ],
            identificadores_ativos=[],
            dispositivos=[],
            eventos_pendentes=0,
            movimentacoes_abertas=[],
            referencia="2033-01-01",
        )
        self.assertEqual(resultado["com_propriedade"], 0)
        self.assertEqual(resultado["nascidos_sem_mae"], 1)

    def test_conta_so_movimentacao_aberta_vencida(self):
        resultado = montar_rebanho(
            animais=[],
            identificadores_ativos=[],
            dispositivos=[],
            eventos_pendentes=7,
            movimentacoes_abertas=[
                {"status": "rascunho", "data_prevista": "2032-12-31"},
                {"status": "liberada", "data_prevista": "2033-01-01"},
                {"status": "em_transito", "data_prevista": "2033-01-02"},
                {"status": "concluida", "data_prevista": "2032-01-01"},
                {"status": "rascunho", "data_prevista": "invalida"},
            ],
            referencia="2033-01-01",
        )
        self.assertEqual(resultado["movimentacoes_abertas_vencidas"], 1)
        self.assertEqual(resultado["eventos_pendentes_sincronizacao"], 7)

    def test_vazio_e_todos_pendentes_sao_validos_no_avaliador(self):
        vazio = montar_rebanho(
            animais=[],
            identificadores_ativos=[],
            dispositivos=[],
            eventos_pendentes=0,
            movimentacoes_abertas=[],
            referencia="2033-01-01",
        )
        self.assertTrue(all(valor == 0 for valor in vazio.values()))
        self.assertEqual(avaliar(vazio, "2033-01-01")["escore"], 100.0)

        perfeito = montar_rebanho(
            animais=[
                {"uuid": "p1", "status": "ativo", "property_id": "fazenda", "origem": "nascido", "birth_estimated": False, "mae_uuid": "mae"}
            ],
            identificadores_ativos=[
                {"animal_uuid": "p1", "tipo": "oficial_pnib"},
                {"animal_uuid": "p1", "tipo": "manejo"},
            ],
            dispositivos=[{"animal_uuid": "p1", "divergencia": None}],
            eventos_pendentes=0,
            movimentacoes_abertas=[],
            referencia="2033-01-01",
        )
        self.assertEqual(avaliar(perfeito, "2033-01-01")["escore"], 100.0)

        pendente = montar_rebanho(
            animais=[
                {"uuid": "a1", "status": "ativo", "property_id": None, "origem": "nascido", "birth_estimated": True, "mae_uuid": None}
            ],
            identificadores_ativos=[],
            dispositivos=[{"animal_uuid": "a1", "divergencia": True}],
            eventos_pendentes=4,
            movimentacoes_abertas=[{"status": "liberada", "data_prevista": "2032-01-01"}],
            referencia="2033-01-01",
        )
        self.assertEqual(avaliar(pendente, "2033-01-01")["escore"], 0.0)


if __name__ == "__main__":
    unittest.main()
