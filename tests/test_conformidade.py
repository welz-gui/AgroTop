import inspect
import unittest

from services.conformidade import avaliar, dimensoes_avaliadas


def _rebanho_perfeito(animais=20):
    return {
        "animais_ativos": animais,
        "com_identificacao_oficial": animais,
        "com_identificacao_manejo": animais,
        "com_propriedade": animais,
        "nascidos_sem_mae": 0,
        "com_nascimento_estimado": 0,
        "eventos_pendentes_sincronizacao": 0,
        "movimentacoes_abertas_vencidas": 0,
        "dispositivos_com_divergencia": 0,
    }


class TestEscoreConformidade(unittest.TestCase):
    def test_assinaturas_do_contrato(self):
        self.assertEqual(
            list(inspect.signature(avaliar).parameters),
            ["rebanho", "referencia"],
        )
        self.assertEqual(
            list(inspect.signature(dimensoes_avaliadas).parameters), []
        )

    def test_rebanho_perfeito(self):
        resultado = avaliar(_rebanho_perfeito(), "2033-01-01")

        self.assertEqual(resultado["escore"], 100.0)
        self.assertEqual(resultado["faixa"], "conforme")
        self.assertEqual(resultado["pendencias_criticas"], [])
        self.assertIsNone(resultado["prazo_relevante"])

    def test_mesmo_rebanho_muda_quando_o_prazo_chega(self):
        rebanho = _rebanho_perfeito()
        rebanho["com_identificacao_oficial"] = 0

        em_2026 = avaliar(rebanho, "2026-08-04")
        em_2033 = avaliar(rebanho, "2033-01-01")

        self.assertEqual(em_2026["escore"], 100.0)
        self.assertNotEqual(em_2026["faixa"], "critico")
        self.assertEqual(em_2026["prazo_relevante"], "2033-01-01")
        self.assertEqual(em_2033["escore"], 65.0)
        self.assertEqual(em_2033["faixa"], "critico")
        self.assertIsNone(em_2033["prazo_relevante"])

    def test_sempre_mostra_as_seis_dimensoes(self):
        resultado = avaliar(_rebanho_perfeito(), "2026-08-04")

        self.assertEqual(len(resultado["dimensoes"]), 6)
        self.assertEqual(
            [item["nome"] for item in resultado["dimensoes"]],
            [item["nome"] for item in dimensoes_avaliadas()],
        )
        self.assertTrue(all(item["nota"] == 100.0 for item in resultado["dimensoes"]))
        self.assertEqual(
            sum(item["peso"] for item in dimensoes_avaliadas()), 100.0
        )

    def test_rebanho_vazio_nao_divide_por_zero(self):
        resultado = avaliar(_rebanho_perfeito(animais=0), "2026-08-04")

        self.assertEqual(resultado["escore"], 100.0)
        self.assertEqual(resultado["faixa"], "conforme")
        self.assertEqual(resultado["pendencias_criticas"], [])
        self.assertTrue(
            all(
                "Sem animais ativos" in item["mensagem"]
                for item in resultado["dimensoes"]
            )
        )

    def test_pendencias_sao_frases_acionaveis(self):
        rebanho = _rebanho_perfeito(animais=20)
        rebanho.update(
            {
                "com_propriedade": 8,
                "nascidos_sem_mae": 2,
                "eventos_pendentes_sincronizacao": 3,
                "movimentacoes_abertas_vencidas": 1,
                "dispositivos_com_divergencia": 4,
            }
        )

        pendencias = avaliar(rebanho, "2033-01-01")["pendencias_criticas"]

        self.assertIn("12 animais sem propriedade definida.", pendencias)
        self.assertTrue(any("mãe vinculada" in item for item in pendencias))
        self.assertTrue(any("sincronização" in item for item in pendencias))
        self.assertTrue(any("movimentação aberta vencida" in item for item in pendencias))
        self.assertTrue(any("divergência" in item for item in pendencias))
        self.assertFalse(any("com_propriedade" in item for item in pendencias))

    def test_notas_proporcionais_e_limitadas(self):
        rebanho = _rebanho_perfeito(animais=10)
        rebanho["com_propriedade"] = 5
        rebanho["nascidos_sem_mae"] = 50

        resultado = avaliar(rebanho, "2033-01-01")
        por_nome = {item["nome"]: item for item in resultado["dimensoes"]}

        self.assertEqual(por_nome["Propriedade definida"]["nota"], 50.0)
        self.assertEqual(por_nome["Vínculo materno"]["nota"], 0.0)
        self.assertGreaterEqual(resultado["escore"], 0.0)
        self.assertLessEqual(resultado["escore"], 100.0)

    def test_mensagens_deixam_claro_que_nao_e_parecer_legal(self):
        resultado = avaliar(_rebanho_perfeito(), "2026-08-04")

        self.assertTrue(
            all(
                "não substitui avaliação de conformidade legal" in item["mensagem"]
                for item in resultado["dimensoes"]
            )
        )


if __name__ == "__main__":
    unittest.main()
