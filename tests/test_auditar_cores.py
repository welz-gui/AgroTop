import inspect
import unittest
from pathlib import Path

from tools.auditar_cores import distancia, extrair_hex, mapear
from ui.tema import TEMAS


class TestExtrairHex(unittest.TestCase):
    def test_assinaturas_do_contrato(self):
        self.assertEqual(list(inspect.signature(extrair_hex).parameters), ["codigo"])
        self.assertEqual(list(inspect.signature(mapear).parameters), ["hexes", "tema"])
        self.assertEqual(
            list(inspect.signature(distancia).parameters), ["hex_a", "hex_b"]
        )

    def test_encontra_nos_quatro_contextos_reais(self):
        codigo = '''
cor = f"<span style='color:#AABBCC'>{valor}</span>"
st.markdown("<b style='color:#123456'>texto</b>")
paleta = {"fundo": "#abcdef"}
css = """.card { border-color: #FEDCBA; }"""
'''

        resultado = extrair_hex(codigo)

        self.assertEqual(
            [item["hex"] for item in resultado],
            ["#aabbcc", "#123456", "#abcdef", "#fedcba"],
        )
        self.assertTrue(all(item["linha"] > 0 for item in resultado))
        self.assertTrue(all(item["contexto"] for item in resultado))

    def test_ignora_comentario_e_fragmentos_de_url(self):
        codigo = '''
# comentário com #aabbcc
pagina = "https://exemplo.test/#abc"
icone = "url(#def)"
link = "<a href='#123456'>atalho</a>"
cor = "#AABBCC"
'''

        self.assertEqual(
            [item["hex"] for item in extrair_hex(codigo)],
            ["#aabbcc"],
        )

    def test_normaliza_forma_curta_e_maiuscula(self):
        resultado = extrair_hex('a = "#abc"\nb = "#AABBCC"')

        self.assertEqual([item["hex"] for item in resultado], ["#aabbcc", "#aabbcc"])


class TestDistancia(unittest.TestCase):
    def test_cor_igual_tem_distancia_zero(self):
        self.assertEqual(distancia("#4ade80", "#4ade80"), 0.0)

    def test_preto_e_branco_ocupam_a_escala_de_luminosidade(self):
        self.assertAlmostEqual(distancia("#000", "#fff"), 100.0, places=3)
        self.assertGreater(
            distancia("#000", "#fff"),
            distancia("#000", "#777"),
        )


class TestMapear(unittest.TestCase):
    def test_conta_exatos_e_sem_token(self):
        hexes = [
            {"hex": "#abc", "linha": 1, "contexto": ""},
            {"hex": "#AABBCC", "linha": 2, "contexto": ""},
            {"hex": "#000000", "linha": 3, "contexto": ""},
        ]
        tema = {"escuro": {"destaque": "#aabbcc", "fundo": "#111111"}}

        resultado = mapear(hexes, tema)

        self.assertEqual(resultado["resumo"], {
            "total": 3,
            "distintos": 2,
            "com_token": 1,
            "sem_token": 1,
        })
        self.assertEqual(resultado["exatos"][0], {
            "hex": "#aabbcc",
            "token": "destaque",
            "ocorrencias": 2,
        })
        self.assertEqual(resultado["sem_token"][0]["mais_proximo"], "fundo")

    def test_tema_vazio_devolve_tudo_sem_token(self):
        hexes = [{"hex": "#123456", "linha": 1, "contexto": "cor"}]

        resultado = mapear(hexes, {})

        self.assertEqual(resultado["exatos"], [])
        self.assertEqual(resultado["resumo"]["sem_token"], 1)
        self.assertEqual(resultado["sem_token"][0]["mais_proximo"], "")

    def test_app_real_e_mapeado_sem_erro(self):
        raiz = Path(__file__).resolve().parents[1]
        codigo = (raiz / "app.py").read_text(encoding="utf-8")

        resultado = mapear(extrair_hex(codigo), TEMAS)

        self.assertGreater(resultado["resumo"]["total"], 0)
        self.assertGreater(resultado["resumo"]["distintos"], 0)


if __name__ == "__main__":
    unittest.main()
