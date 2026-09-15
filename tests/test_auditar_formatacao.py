import inspect
import unittest
from datetime import date, datetime
from pathlib import Path

from app import _data_br, _num_br
from tools.auditar_formatacao import (
    classificar_data,
    classificar_decimal,
    extrair_ocorrencias,
)


class TestHelpersFormatacao(unittest.TestCase):
    def test_num_br_inteiro_e_decimais(self):
        self.assertEqual(_num_br(1234.56, casas=2), "1234,56")
        self.assertEqual(_num_br(1234.5, casas=1), "1234,5")
        self.assertEqual(_num_br(1234, casas=0), "1234")
        self.assertEqual(_num_br(0.0, casas=1), "0,0")

    def test_num_br_com_sinal(self):
        self.assertEqual(_num_br(5.2, casas=1, sinal=True), "+5,2")
        self.assertEqual(_num_br(-5.2, casas=1, sinal=True), "-5,2")
        self.assertEqual(_num_br(0.0, casas=1, sinal=True), "+0,0")

    def test_num_br_nulo_ou_invalido(self):
        self.assertEqual(_num_br(None), "None")
        self.assertEqual(_num_br("invalido"), "invalido")

    def test_data_br_formatos_aceitos(self):
        self.assertEqual(_data_br("2026-09-15"), "15/09/2026")
        self.assertEqual(_data_br(date(2026, 9, 15)), "15/09/2026")
        self.assertEqual(_data_br(datetime(2026, 9, 15, 10, 30)), "15/09/2026")

    def test_data_br_vazio_ou_invalido(self):
        self.assertEqual(_data_br(None), "—")
        self.assertEqual(_data_br(""), "—")
        self.assertEqual(_data_br("data-invalida"), "data-invalida")


class TestClassificacaoAuditoria(unittest.TestCase):
    def test_assinaturas_do_contrato(self):
        self.assertEqual(list(inspect.signature(classificar_decimal).parameters), ["linha"])
        self.assertEqual(list(inspect.signature(classificar_data).parameters), ["linha"])
        self.assertEqual(list(inspect.signature(extrair_ocorrencias).parameters), ["codigo"])

    def test_classificar_decimal_interno_vs_visivel(self):
        linha_plotly = 'hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f} kg"'
        self.assertEqual(classificar_decimal(linha_plotly), "interno")

        linha_css = 'f\'<div style="width:{pct:.0f}%;"></div>\''
        self.assertEqual(classificar_decimal(linha_css), "interno")

        linha_nota_db = 'medida_nota = f"PT={pt:.0f}cm Comp={comp:.0f}cm"'
        self.assertEqual(classificar_decimal(linha_nota_db), "interno")

        linha_visivel = 'st.metric("Peso", f"{peso:.1f} kg")'
        self.assertEqual(classificar_decimal(linha_visivel), "visivel")

    def test_classificar_data_interno_vs_visivel(self):
        linha_carencia = 'st.warning(f"Carência até {dt.isoformat()}")'
        self.assertEqual(classificar_data(linha_carencia), "visivel")

        linha_db = 'db.get_rain(start.isoformat(), end.isoformat())'
        self.assertEqual(classificar_data(linha_db), "interno")


class TestAuditoriaAppReal(unittest.TestCase):
    def test_app_sem_ocorrencias_visiveis_sem_formatacao(self):
        raiz = Path(__file__).resolve().parents[1]
        codigo = (raiz / "app.py").read_text(encoding="utf-8")

        resultado = extrair_ocorrencias(codigo)
        resumo = resultado["resumo"]

        self.assertEqual(
            resumo["decimal_visivel"],
            0,
            f"Ainda restam {resumo['decimal_visivel']} ocorrências decimais visíveis sem _num_br",
        )
        self.assertEqual(
            resumo["data_visivel"],
            0,
            f"Ainda restam {resumo['data_visivel']} ocorrências de data visíveis sem _data_br",
        )
        self.assertEqual(
            resumo["decimal_interno"],
            11,
            f"Ocorrências decimais internas esperadas: 11, encontradas: {resumo['decimal_interno']}",
        )
        self.assertEqual(
            resumo["data_interno"],
            41,
            f"Ocorrências de data internas esperadas: 41, encontradas: {resumo['data_interno']}",
        )


if __name__ == "__main__":
    unittest.main()
