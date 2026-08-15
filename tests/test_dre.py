import unittest

from services.dre import montar_dre


def _resumo(**over):
    base = {
        "compra_animais": 0.0,
        "operacional": 0.0,
        "custos_fixos": 0.0,
        "medicamentos": 0.0,
        "nutricao": 0.0,
        "saidas_total": 0.0,
        "perda_mortalidade": 0.0,
        "vendas": {},
        "receita_total": 0.0,
        "resultado": 0.0,
    }
    base.update(over)
    return base


class TestMontarDRE(unittest.TestCase):
    def test_dre_vazia_e_zero_em_tudo(self):
        dre = montar_dre(_resumo())
        self.assertEqual(dre["receita_bruta"], 0.0)
        self.assertEqual(dre["cpv"], 0.0)
        self.assertEqual(dre["lucro_bruto"], 0.0)
        self.assertEqual(dre["resultado_liquido"], 0.0)
        self.assertIsNone(dre["margem_bruta_pct"])
        self.assertIsNone(dre["margem_liquida_pct"])

    def test_cpv_vem_do_lucro_ja_casado_com_a_venda_nao_da_compra_do_periodo(self):
        """O caso que separa a DRE do Resultado (Caixa): comprar um animal e
        não vendê-lo no período não pode virar despesa da DRE."""
        resumo = _resumo(
            compra_animais=50000.0,  # comprou muito, mas não é o que a DRE mede
            receita_total=10000.0,
            vendas={"abate": {"receita": 10000.0, "lucro": 4000.0, "n": 2}})
        dre = montar_dre(resumo)
        self.assertEqual(dre["receita_bruta"], 10000.0)
        self.assertEqual(dre["lucro_bruto"], 4000.0)
        self.assertEqual(dre["cpv"], 6000.0)  # 10000 - 4000, não 50000

    def test_soma_lucro_de_varios_tipos_de_venda(self):
        resumo = _resumo(
            receita_total=15000.0,
            vendas={
                "abate": {"receita": 10000.0, "lucro": 4000.0, "n": 2},
                "criacao": {"receita": 5000.0, "lucro": 1000.0, "n": 1},
            })
        dre = montar_dre(resumo)
        self.assertEqual(dre["lucro_bruto"], 5000.0)
        self.assertEqual(dre["cpv"], 10000.0)

    def test_despesas_operacionais_sao_medicamento_nutricao_e_fixos_apenas(self):
        """`operacional` (animal_costs por animal) fica de fora de propósito:
        ou já está dentro do CPV do animal vendido, ou está capitalizado no
        rebanho ainda ativo — nunca é despesa direta da DRE."""
        resumo = _resumo(
            operacional=999999.0,  # não deve aparecer em lugar nenhum da DRE
            medicamentos=500.0, nutricao=1500.0, custos_fixos=2000.0)
        dre = montar_dre(resumo)
        self.assertEqual(dre["despesas_operacionais"], {
            "Medicamentos": 500.0, "Nutrição/Trato": 1500.0, "Custos Fixos": 2000.0})
        self.assertEqual(dre["total_despesas_operacionais"], 4000.0)

    def test_resultado_operacional_e_liquido_em_cascata(self):
        resumo = _resumo(
            receita_total=10000.0,
            vendas={"abate": {"receita": 10000.0, "lucro": 6000.0, "n": 1}},
            medicamentos=500.0, nutricao=1000.0, custos_fixos=1500.0,
            perda_mortalidade=800.0)
        dre = montar_dre(resumo)
        self.assertEqual(dre["lucro_bruto"], 6000.0)
        self.assertEqual(dre["total_despesas_operacionais"], 3000.0)
        self.assertEqual(dre["resultado_operacional"], 3000.0)   # 6000 - 3000
        self.assertEqual(dre["resultado_liquido"], 2200.0)       # 3000 - 800

    def test_margens_em_percentual_da_receita_bruta(self):
        resumo = _resumo(
            receita_total=10000.0,
            vendas={"abate": {"receita": 10000.0, "lucro": 5000.0, "n": 1}},
            custos_fixos=2000.0)
        dre = montar_dre(resumo)
        self.assertEqual(dre["margem_bruta_pct"], 50.0)
        self.assertEqual(dre["resultado_operacional"], 3000.0)
        self.assertEqual(dre["margem_liquida_pct"], 30.0)

    def test_resultado_liquido_pode_ser_negativo(self):
        resumo = _resumo(
            receita_total=1000.0,
            vendas={"abate": {"receita": 1000.0, "lucro": 200.0, "n": 1}},
            custos_fixos=5000.0)
        dre = montar_dre(resumo)
        self.assertEqual(dre["resultado_operacional"], -4800.0)
        self.assertLess(dre["margem_liquida_pct"], 0)


if __name__ == "__main__":
    unittest.main()
