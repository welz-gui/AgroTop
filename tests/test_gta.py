import inspect
import unittest

from datetime import date

from services.gta import _data_iso, validar


class TestValidacaoGta(unittest.TestCase):
    def setUp(self):
        self.gta = {
            "numero": "GTA-001",
            "uf_origem": "MT",
            "uf_destino": "MT",
            "propriedade_origem": "Fazenda Norte",
            "propriedade_destino": "Fazenda Sul",
            "emissao": "2026-08-01",
            "validade": "2026-08-07",
            "finalidade": "engorda",
            "quantidade": 2,
            "animais": ["A1", "A2"],
        }
        self.contexto = {
            "hoje": "2026-08-03",
            "animais_no_embarque": ["A1", "A2"],
            "animais_em_carencia": [],
            "validade_maxima_dias": 7,
        }

    @staticmethod
    def codigos(problemas):
        return [problema["codigo"] for problema in problemas]

    def test_assinatura_do_contrato(self):
        self.assertEqual(
            str(inspect.signature(validar)),
            "(gta: dict, contexto: dict | None = None) -> list[dict]",
        )

    def test_gta_valida_nao_tem_problemas(self):
        self.assertEqual(validar(self.gta, self.contexto), [])

    def test_gta_vencida_e_gta_que_vence_hoje(self):
        vencida = dict(self.gta, validade="2026-08-02")
        self.assertIn("gta_vencida", self.codigos(validar(vencida, self.contexto)))

        vence_hoje = dict(self.gta, validade="2026-08-03")
        problemas = validar(vence_hoje, self.contexto)
        self.assertNotIn("gta_vencida", self.codigos(problemas))
        self.assertEqual(problemas, [])

    def test_gta_futura(self):
        futura = dict(self.gta, emissao="2026-08-04", validade="2026-08-07")
        self.assertIn("gta_futura", self.codigos(validar(futura, self.contexto)))

        emitida_hoje = dict(self.gta, emissao="2026-08-03")
        self.assertNotIn("gta_futura", self.codigos(validar(emitida_hoje, self.contexto)))

    def test_validade_maior_que_o_permitido(self):
        longa = dict(self.gta, validade="2026-08-09")
        self.assertIn(
            "validade_maior_que_o_permitido",
            self.codigos(validar(longa, self.contexto)),
        )

        limite_exato = dict(self.gta, validade="2026-08-08")
        self.assertNotIn(
            "validade_maior_que_o_permitido",
            self.codigos(validar(limite_exato, self.contexto)),
        )

    def test_quantidade_divergente_e_lista_vazia(self):
        divergente = dict(self.gta, quantidade=3)
        self.assertIn(
            "quantidade_divergente",
            self.codigos(validar(divergente, self.contexto)),
        )
        self.assertNotIn(
            "quantidade_divergente",
            self.codigos(validar(self.gta, self.contexto)),
        )

        vazia = dict(self.gta, quantidade=0, animais=[])
        contexto_vazio = dict(self.contexto, animais_no_embarque=[])
        self.assertEqual(validar(vazia, contexto_vazio), [])

        vazia_divergente = dict(vazia, quantidade=1)
        self.assertIn(
            "quantidade_divergente",
            self.codigos(validar(vazia_divergente, contexto_vazio)),
        )

    def test_animal_no_embarque_fora_da_gta(self):
        contexto = dict(self.contexto, animais_no_embarque=["A1", "A2", "A3"])
        self.assertIn(
            "animal_no_embarque_fora_da_gta",
            self.codigos(validar(self.gta, contexto)),
        )
        self.assertNotIn(
            "animal_no_embarque_fora_da_gta",
            self.codigos(validar(self.gta, self.contexto)),
        )

    def test_animal_da_gta_ausente(self):
        contexto = dict(self.contexto, animais_no_embarque=["A1"])
        self.assertIn("animal_da_gta_ausente", self.codigos(validar(self.gta, contexto)))
        self.assertNotIn(
            "animal_da_gta_ausente",
            self.codigos(validar(self.gta, self.contexto)),
        )

    def test_animal_em_carencia_so_bloqueia_abate(self):
        abate = dict(self.gta, finalidade="abate")
        contexto = dict(self.contexto, animais_em_carencia=["A2"])
        self.assertIn("animal_em_carencia", self.codigos(validar(abate, contexto)))

        self.assertNotIn("animal_em_carencia", self.codigos(validar(self.gta, contexto)))
        outro_animal = dict(contexto, animais_em_carencia=["A3"])
        self.assertNotIn(
            "animal_em_carencia",
            self.codigos(validar(abate, outro_animal)),
        )

    def test_origem_igual_ao_destino(self):
        mesma = dict(self.gta, propriedade_destino="Fazenda Norte")
        self.assertIn("origem_igual_ao_destino", self.codigos(validar(mesma, self.contexto)))
        self.assertNotIn(
            "origem_igual_ao_destino",
            self.codigos(validar(self.gta, self.contexto)),
        )

    def test_uf_diferente_sem_finalidade(self):
        sem_finalidade = dict(self.gta, uf_destino="GO", finalidade="")
        problemas = validar(sem_finalidade, self.contexto)
        self.assertIn("uf_diferente_sem_finalidade", self.codigos(problemas))
        alerta = next(
            problema
            for problema in problemas
            if problema["codigo"] == "uf_diferente_sem_finalidade"
        )
        self.assertEqual(alerta["gravidade"], "alerta")

        com_finalidade = dict(sem_finalidade, finalidade="reproducao")
        self.assertNotIn(
            "uf_diferente_sem_finalidade",
            self.codigos(validar(com_finalidade, self.contexto)),
        )

    def test_contexto_vazio_pula_validacoes_dependentes(self):
        sem_contexto = dict(
            self.gta,
            emissao="2026-08-01",
            validade="2026-08-07",
        )
        self.assertEqual(validar(sem_contexto), [])
        self.assertEqual(validar(sem_contexto, {}), [])

    def test_problema_tem_formato_do_contrato(self):
        problema = validar(dict(self.gta, quantidade=3), self.contexto)[0]
        self.assertEqual(set(problema), {"codigo", "gravidade", "mensagem"})
        self.assertIn(problema["gravidade"], {"bloqueio", "alerta"})
        self.assertTrue(problema["mensagem"])


class TestDataIso(unittest.TestCase):
    def test_converte_string_iso_valida(self):
        self.assertEqual(_data_iso("2026-08-01"), date(2026, 8, 1))

    def test_ignora_espacos_ao_redor(self):
        self.assertEqual(_data_iso(" 2026-08-01 "), date(2026, 8, 1))

    def test_retorna_none_para_string_invalida(self):
        self.assertIsNone(_data_iso("data-invalida"))

    def test_retorna_none_para_tipo_que_nao_e_string(self):
        self.assertIsNone(_data_iso(None))
        self.assertIsNone(_data_iso(20260801))

    def test_retorna_none_para_data_inexistente(self):
        self.assertIsNone(_data_iso("2026-02-29"))  # 2026 não é bissexto


if __name__ == "__main__":
    unittest.main()
