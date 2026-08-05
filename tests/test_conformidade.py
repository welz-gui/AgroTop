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

    def test_rebanho_perfeito_e_completo(self):
        resultado = avaliar(_rebanho_perfeito(), "2033-01-01")

        self.assertEqual(resultado["escore"], 100.0)
        self.assertEqual(resultado["faixa"], "completo")
        self.assertEqual(resultado["pendencias_criticas"], [])
        self.assertEqual(resultado["pendencias_informativas"], [])
        self.assertIsNone(resultado["prazo_relevante"])

    def test_mesmo_rebanho_muda_quando_o_prazo_chega(self):
        rebanho = _rebanho_perfeito()
        rebanho["com_identificacao_oficial"] = 0

        em_2026 = avaliar(rebanho, "2026-08-04")
        em_2033 = avaliar(rebanho, "2033-01-01")

        self.assertEqual(em_2026["escore"], 100.0)
        self.assertNotEqual(em_2026["faixa"], "critico")
        self.assertEqual(em_2026["pendencias_criticas"], [])
        self.assertEqual(em_2026["prazo_relevante"], "2033-01-01")
        self.assertEqual(em_2033["escore"], 65.0)
        self.assertEqual(em_2033["faixa"], "critico")
        self.assertTrue(em_2033["pendencias_criticas"])
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

    def test_rebanho_vazio_ignora_contadores_e_nao_divide_por_zero(self):
        rebanho = _rebanho_perfeito(animais=0)
        rebanho.update(
            {
                "nascidos_sem_mae": 4,
                "eventos_pendentes_sincronizacao": 2,
                "movimentacoes_abertas_vencidas": 1,
            }
        )
        resultado = avaliar(rebanho, "2026-08-04")

        self.assertEqual(resultado["escore"], 100.0)
        self.assertEqual(resultado["faixa"], "completo")
        self.assertEqual(resultado["pendencias_criticas"], [])
        self.assertEqual(resultado["pendencias_informativas"], [])
        self.assertTrue(
            all(
                "Sem animais ativos" in item["mensagem"]
                for item in resultado["dimensoes"]
            )
        )

    def test_todo_deficit_de_dimensao_e_critico_e_reduz_o_escore(self):
        rebanho = _rebanho_perfeito(animais=20)
        rebanho.update(
            {
                "com_propriedade": 8,
                "nascidos_sem_mae": 2,
                "eventos_pendentes_sincronizacao": 3,
                "com_nascimento_estimado": 4,
                "dispositivos_com_divergencia": 5,
            }
        )

        resultado = avaliar(rebanho, "2033-01-01")

        self.assertLess(resultado["escore"], 100.0)
        self.assertEqual(len(resultado["pendencias_criticas"]), 5)
        self.assertTrue(any(item["faltam"] > 0 for item in resultado["dimensoes"]))
        self.assertTrue(
            all(
                any(termo in pendencia for termo in ("propriedade", "mãe", "sincronização", "nascimento", "divergência"))
                for pendencia in resultado["pendencias_criticas"]
            )
        )

    def test_manejo_e_movimentacoes_sao_informativos(self):
        rebanho = _rebanho_perfeito()
        rebanho.update(
            {
                "com_identificacao_manejo": 8,
                "movimentacoes_abertas_vencidas": 4,
            }
        )

        resultado = avaliar(rebanho, "2033-01-01")

        self.assertEqual(resultado["escore"], 100.0)
        self.assertEqual(resultado["pendencias_criticas"], [])
        self.assertTrue(
            any("identificação de manejo" in item for item in resultado["pendencias_informativas"])
        )
        self.assertTrue(
            any("movimentações abertas vencidas" in item for item in resultado["pendencias_informativas"])
        )

    def test_pendencias_sao_frases_acionaveis(self):
        rebanho = _rebanho_perfeito(animais=20)
        rebanho["com_propriedade"] = 8

        pendencias = avaliar(rebanho, "2033-01-01")["pendencias_criticas"]

        self.assertIn("12 animais sem propriedade definida.", pendencias)
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
        self.assertNotIn("conforme", resultado["faixa"])


if __name__ == "__main__":
    unittest.main()
