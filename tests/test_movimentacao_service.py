import unittest
from datetime import date, timedelta
from services.movimentacao import (
    pre_validar_saida,
    pode_liberar,
    exige_confirmacao,
    resumo
)

class TestMovimentacaoService(unittest.TestCase):
    def setUp(self):
        self.hoje = date.today()
        self.ontem = self.hoje - timedelta(days=1)
        self.amanha = self.hoje + timedelta(days=1)
        self.hoje_str = self.hoje.isoformat()
        self.ontem_str = self.ontem.isoformat()
        self.amanha_str = self.amanha.isoformat()

        self.mov_valida = {
            "tipo": "venda",
            "propriedade_origem_id": 1,
            "propriedade_destino_id": 2,
            "finalidade": "reproducao",
            "data_prevista": self.amanha_str,
            "gta_numero": "123456",
            "status": "rascunho"
        }

        self.animal_valido = {
            "id": 100,
            "uuid": "uuid-100",
            "status": "ativo",
            "property_id": 1,
            "tem_identificacao_oficial": True,
            "carencia_ate": None
        }

        self.contexto_valido = {
            "hoje": self.hoje_str,
            "animais_em_outra_movimentacao": [],
            "eventos_pendentes_de_sincronizacao": 0,
            "identificacao_obrigatoria": False
        }

    def _extract_codes(self, problemas):
        return [p["codigo"] for p in problemas]

    def test_pre_validar_saida_valida(self):
        problemas = pre_validar_saida(self.mov_valida, [self.animal_valido], self.contexto_valido)
        self.assertEqual(problemas, [])

    def test_movimentacao_ja_concluida(self):
        mov = self.mov_valida.copy()
        mov["status"] = "concluida"
        problemas = pre_validar_saida(mov, [self.animal_valido], self.contexto_valido)
        self.assertIn("movimentacao_ja_concluida", self._extract_codes(problemas))

    def test_origem_igual_ao_destino(self):
        mov = self.mov_valida.copy()
        mov["propriedade_destino_id"] = 1
        problemas = pre_validar_saida(mov, [self.animal_valido], self.contexto_valido)
        self.assertIn("origem_igual_ao_destino", self._extract_codes(problemas))

    def test_tipo_desconhecido(self):
        mov = self.mov_valida.copy()
        mov["tipo"] = "tipo_invalido"
        problemas = pre_validar_saida(mov, [self.animal_valido], self.contexto_valido)
        self.assertIn("tipo_desconhecido", self._extract_codes(problemas))

    def test_data_prevista_no_passado(self):
        mov = self.mov_valida.copy()
        mov["data_prevista"] = self.ontem_str
        problemas = pre_validar_saida(mov, [self.animal_valido], self.contexto_valido)
        self.assertIn("data_prevista_no_passado", self._extract_codes(problemas))

    def test_sem_gta(self):
        mov = self.mov_valida.copy()
        mov["gta_numero"] = ""
        problemas = pre_validar_saida(mov, [self.animal_valido], self.contexto_valido)
        self.assertIn("sem_gta", self._extract_codes(problemas))

    def test_sem_animais(self):
        problemas = pre_validar_saida(self.mov_valida, [], self.contexto_valido)
        self.assertIn("sem_animais", self._extract_codes(problemas))

    def test_animal_morto_ou_abatido(self):
        animal = self.animal_valido.copy()
        animal["status"] = "morto"
        problemas = pre_validar_saida(self.mov_valida, [animal], self.contexto_valido)
        self.assertIn("animal_morto_ou_abatido", self._extract_codes(problemas))

        animal["status"] = "abatido"
        problemas2 = pre_validar_saida(self.mov_valida, [animal], self.contexto_valido)
        self.assertIn("animal_morto_ou_abatido", self._extract_codes(problemas2))

    def test_animal_de_outra_propriedade(self):
        animal = self.animal_valido.copy()
        animal["property_id"] = 999
        problemas = pre_validar_saida(self.mov_valida, [animal], self.contexto_valido)
        self.assertIn("animal_de_outra_propriedade", self._extract_codes(problemas))

    def test_animal_em_outra_movimentacao(self):
        contexto = self.contexto_valido.copy()
        contexto["animais_em_outra_movimentacao"] = [self.animal_valido["uuid"]]
        problemas = pre_validar_saida(self.mov_valida, [self.animal_valido], contexto)
        self.assertIn("animal_em_outra_movimentacao", self._extract_codes(problemas))

    def test_sem_identificacao_obrigatoria(self):
        contexto = self.contexto_valido.copy()
        contexto["identificacao_obrigatoria"] = True
        animal = self.animal_valido.copy()
        animal["tem_identificacao_oficial"] = False
        problemas = pre_validar_saida(self.mov_valida, [animal], contexto)
        self.assertIn("sem_identificacao_obrigatoria", self._extract_codes(problemas))

    def test_animal_em_carencia_abate(self):
        animal = self.animal_valido.copy()
        animal["carencia_ate"] = self.amanha_str
        mov = self.mov_valida.copy()
        mov["finalidade"] = "abate"
        problemas = pre_validar_saida(mov, [animal], self.contexto_valido)
        self.assertIn("animal_em_carencia", self._extract_codes(problemas))

        mov["finalidade"] = "frigorifico"
        problemas2 = pre_validar_saida(mov, [animal], self.contexto_valido)
        self.assertIn("animal_em_carencia", self._extract_codes(problemas2))

        mov["finalidade"] = "outra"
        mov["tipo"] = "frigorifico"
        problemas3 = pre_validar_saida(mov, [animal], self.contexto_valido)
        self.assertIn("animal_em_carencia", self._extract_codes(problemas3))

    def test_animal_em_carencia_sem_abate(self):
        animal = self.animal_valido.copy()
        animal["carencia_ate"] = self.amanha_str
        problemas = pre_validar_saida(self.mov_valida, [animal], self.contexto_valido)
        self.assertIn("animal_em_carencia_sem_abate", self._extract_codes(problemas))

    def test_sincronizacao_pendente(self):
        contexto = self.contexto_valido.copy()
        contexto["eventos_pendentes_de_sincronizacao"] = 5
        problemas = pre_validar_saida(self.mov_valida, [self.animal_valido], contexto)
        self.assertIn("sincronizacao_pendente", self._extract_codes(problemas))

    # Testes das funcoes auxiliares

    def test_pode_liberar(self):
        # sem problemas
        self.assertTrue(pode_liberar([]))

        # apenas informativos ou alertas
        self.assertTrue(pode_liberar([
            {"gravidade": "informativo"},
            {"gravidade": "alerta"}
        ]))

        # tem bloqueio
        self.assertFalse(pode_liberar([
            {"gravidade": "alerta"},
            {"gravidade": "bloqueio"}
        ]))

    def test_exige_confirmacao(self):
        # sem alertas
        self.assertFalse(exige_confirmacao([]))
        self.assertFalse(exige_confirmacao([
            {"gravidade": "informativo"},
            {"gravidade": "bloqueio"}
        ]))

        # com alertas
        self.assertTrue(exige_confirmacao([
            {"gravidade": "informativo"},
            {"gravidade": "alerta"}
        ]))

    def test_resumo(self):
        problemas = [
            {"gravidade": "informativo"},
            {"gravidade": "informativo"},
            {"gravidade": "alerta"},
            {"gravidade": "bloqueio"},
            {"gravidade": "bloqueio"},
            {"gravidade": "bloqueio"}
        ]
        r = resumo(problemas)
        self.assertEqual(r["informativo"], 2)
        self.assertEqual(r["alerta"], 1)
        self.assertEqual(r["bloqueio"], 3)

if __name__ == "__main__":
    unittest.main()
