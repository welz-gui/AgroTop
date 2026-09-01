import unittest
from services.estados_dispositivo import (
    transicao_permitida,
    estados,
    terminais,
    conferir_codigos,
)


class TestEstadosDispositivo(unittest.TestCase):
    def test_transicao_permitida_mesmo_estado(self):
        res = transicao_permitida("disponivel", "disponivel")
        self.assertTrue(res["permitida"])
        self.assertFalse(res["exige_motivo"])
        self.assertFalse(res["exige_autorizacao"])

    def test_transicao_permitida_estado_invalido(self):
        res_atual = transicao_permitida("invalido", "disponivel")
        self.assertFalse(res_atual["permitida"])
        self.assertIn("Estado atual inválido", res_atual["motivo"])

        res_novo = transicao_permitida("disponivel", "invalido")
        self.assertFalse(res_novo["permitida"])
        self.assertIn("Estado novo inválido", res_novo["motivo"])

    def test_transicao_permitida_bloqueado_orgao(self):
        res_sem_auth = transicao_permitida("bloqueado_orgao", "disponivel", tem_autorizacao=False)
        self.assertFalse(res_sem_auth["permitida"])
        self.assertTrue(res_sem_auth["exige_autorizacao"])
        self.assertIn("só o órgão libera", res_sem_auth["motivo"])

        res_com_auth = transicao_permitida("bloqueado_orgao", "disponivel", tem_autorizacao=True)
        self.assertTrue(res_com_auth["permitida"])

    def test_transicao_permitida_terminais(self):
        for term in terminais():
            res = transicao_permitida(term, "disponivel")
            self.assertFalse(res["permitida"])
            self.assertIn("estado definitivo", res["motivo"])

    def test_transicao_permitida_nao_prevista(self):
        res = transicao_permitida("aplicado", "disponivel")
        self.assertFalse(res["permitida"])
        self.assertIn("não é prevista", res["motivo"])

    def test_transicao_permitida_exige_motivo(self):
        res_motivo = transicao_permitida("aplicado", "perdido")
        self.assertTrue(res_motivo["permitida"])
        self.assertTrue(res_motivo["exige_motivo"])

        res_sem_motivo = transicao_permitida("recebido", "disponivel")
        self.assertTrue(res_sem_motivo["permitida"])
        self.assertFalse(res_sem_motivo["exige_motivo"])

    def test_conferir_codigos_ausentes(self):
        res_visual = conferir_codigos("", "123")
        self.assertFalse(res_visual["confere"])
        self.assertEqual(res_visual["divergencia"], "codigo_ausente")

        res_eletronico = conferir_codigos("123", None)
        self.assertFalse(res_eletronico["confere"])
        self.assertEqual(res_eletronico["divergencia"], "codigo_ausente")

    def test_conferir_codigos_iguais(self):
        res = conferir_codigos("br-123", "BR123")
        self.assertTrue(res["confere"])
        self.assertIsNone(res["divergencia"])
        self.assertEqual(res["mensagem"], "")

    def test_conferir_codigos_divergentes(self):
        res = conferir_codigos("br-123", "BR124")
        self.assertFalse(res["confere"])
        self.assertEqual(res["divergencia"], "codigos_divergentes")
        self.assertIn("não conferem", res["mensagem"])

    def test_conferir_codigos_parciais(self):
        res = conferir_codigos("123", "001BR123", digitos_comparados=3)
        self.assertTrue(res["confere"])
        self.assertIsNone(res["divergencia"])

        res_divergente = conferir_codigos("124", "001BR123", digitos_comparados=3)
        self.assertFalse(res_divergente["confere"])
        self.assertEqual(res_divergente["divergencia"], "codigos_divergentes")

    def test_estados(self):
        est = estados()
        self.assertIsInstance(est, list)
        self.assertIn("disponivel", est)
        self.assertIn("bloqueado_orgao", est)

    def test_terminais(self):
        term = terminais()
        self.assertIsInstance(term, set)
        self.assertIn("inutilizado", term)


if __name__ == "__main__":
    unittest.main()
