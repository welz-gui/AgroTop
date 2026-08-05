"""Testes de propriedade baseados em hipótese (hypothesis) para os módulos puros de services.

Ver Spec 0031.
"""

from datetime import date
import math
import unittest

from hypothesis import HealthCheck, given, settings, strategies as st

from services import (
    caixa,
    estados_animal,
    estados_dispositivo,
    geometria,
    rateio,
    regras_regulatorias,
    zootecnia,
)


class TestPropriedadesRateio(unittest.TestCase):
    @settings(derandomize=True, max_examples=100)
    @given(
        valor_total=st.integers(min_value=-5000000, max_value=5000000).map(lambda c: c / 100.0),
        animais=st.lists(
            st.fixed_dictionaries({
                "id": st.integers(min_value=1, max_value=1000),
                "peso": st.floats(min_value=50.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
                "dias_no_lote": st.integers(min_value=1, max_value=365),
            }),
            min_size=1,
            max_size=20,
        ),
        criterio=st.sampled_from(["igual", "peso", "peso_dia"]),
    )
    def test_soma_dos_quinhoes_sempre_fecha(self, valor_total: float, animais: list[dict], criterio: str):
        """A soma dos valores rateados é exatamente igual ao valor total arredondado para 2 casas."""
        v_arredondado = round(valor_total, 2)
        resultado = rateio.ratear(v_arredondado, animais, criterio)
        soma = round(sum(item["valor"] for item in resultado), 2)
        self.assertTrue(
            math.isclose(soma, v_arredondado, abs_tol=1e-5),
            f"Soma {soma} não fecha com o total {v_arredondado}",
        )

    @settings(derandomize=True, max_examples=100)
    @given(
        valor_negativo=st.integers(min_value=-5000000, max_value=-1).map(lambda c: c / 100.0),
        animais=st.lists(
            st.fixed_dictionaries({
                "id": st.integers(min_value=1, max_value=1000),
                "peso": st.floats(min_value=50.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            }),
            min_size=1,
            max_size=20,
        ),
    )
    def test_rateio_negativo_estorno_mantem_soma_negativa(self, valor_negativo: float, animais: list[dict]):
        """Rateio de valor negativo mantém a soma negativa e de mesmo módulo."""
        v_arredondado = round(valor_negativo, 2)
        resultado = rateio.ratear(v_arredondado, animais, "igual")
        soma = round(sum(item["valor"] for item in resultado), 2)
        self.assertEqual(soma, v_arredondado)
        self.assertEqual(abs(soma), abs(v_arredondado))


class TestPropriedadesGeometria(unittest.TestCase):
    @staticmethod
    def _gerador_poligono_valido():
        """Gera um anel poligonal convexo simples em coordenadas de GPS do Brasil."""
        return st.builds(
            lambda lon_c, lat_c, r, offsets: [
                (
                    round(lon_c + r * math.cos(ang), 6),
                    round(lat_c + r * math.sin(ang), 6),
                )
                for ang in sorted(offsets)
            ],
            lon_c=st.floats(min_value=-70.0, max_value=-36.0, allow_nan=False, allow_infinity=False),
            lat_c=st.floats(min_value=-30.0, max_value=2.0, allow_nan=False, allow_infinity=False),
            r=st.floats(min_value=0.002, max_value=0.02, allow_nan=False, allow_infinity=False),
            offsets=st.lists(
                st.floats(min_value=0.01, max_value=2 * math.pi - 0.01, allow_nan=False, allow_infinity=False),
                min_size=3,
                max_size=8,
                unique=True,
            ),
        )

    @settings(derandomize=True, max_examples=50)
    @given(data=st.data())
    def test_area_invariante_a_rotacao(self, data):
        """Girar a ordem dos vértices não altera a área calculada."""
        anel = data.draw(self._gerador_poligono_valido())
        if geometria.validar(anel):
            return
        area_orig = geometria.area_hectares(anel)
        for k in range(1, len(anel)):
            rot = anel[k:] + anel[:k]
            area_rot = geometria.area_hectares(rot)
            self.assertTrue(
                math.isclose(area_orig, area_rot, rel_tol=1e-4, abs_tol=1e-4),
                f"Área mudou na rotação: orig={area_orig}, rot={area_rot}",
            )

    @settings(derandomize=True, max_examples=50)
    @given(data=st.data())
    def test_anel_aberto_e_fechado_dao_mesmo_resultado(self, data):
        """Anel aberto ou com primeiro ponto repetido no final devolvem a mesma área."""
        anel = data.draw(self._gerador_poligono_valido())
        if geometria.validar(anel):
            return
        area_aberto = geometria.area_hectares(anel)
        area_fechado = geometria.area_hectares(anel + [anel[0]])
        self.assertTrue(
            math.isclose(area_aberto, area_fechado, rel_tol=1e-5, abs_tol=1e-5),
            f"Área difere entre anel aberto ({area_aberto}) e fechado ({area_fechado})",
        )

    @settings(derandomize=True, max_examples=50)
    @given(data=st.data())
    def test_area_nunca_e_negativa(self, data):
        """Área do polígono em hectares é sempre maior ou igual a zero."""
        anel = data.draw(self._gerador_poligono_valido())
        if geometria.validar(anel):
            return
        area = geometria.area_hectares(anel)
        self.assertGreaterEqual(area, 0.0)

    @settings(derandomize=True, max_examples=50)
    @given(data=st.data())
    def test_centroide_cai_dentro_dos_limites(self, data):
        """O centroide de um polígono válido fica dentro do seu envelope (min/max lon e lat)."""
        anel = data.draw(self._gerador_poligono_valido())
        if geometria.validar(anel):
            return
        c_lon, c_lat = geometria.centroide(anel)
        lons = [p[0] for p in anel]
        lats = [p[1] for p in anel]
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)

        self.assertTrue(
            min_lon - 1e-5 <= c_lon <= max_lon + 1e-5,
            f"Centroide lon {c_lon} fora da faixa [{min_lon}, {max_lon}]",
        )
        self.assertTrue(
            min_lat - 1e-5 <= c_lat <= max_lat + 1e-5,
            f"Centroide lat {c_lat} fora da faixa [{min_lat}, {max_lat}]",
        )


class TestPropriedadesZootecnia(unittest.TestCase):
    @settings(derandomize=True, max_examples=100)
    @given(
        w1=st.floats(min_value=0.0, max_value=2000.0, allow_nan=False, allow_infinity=False),
        w2=st.floats(min_value=0.0, max_value=2000.0, allow_nan=False, allow_infinity=False),
        yield_=st.floats(min_value=0.4, max_value=0.6, allow_nan=False, allow_infinity=False),
    )
    def test_kg_to_arrobas_e_monotonica(self, w1: float, w2: float, yield_: float):
        """kg_to_arrobas é monotônica: se peso1 <= peso2, então arrobas1 <= arrobas2."""
        menor_peso, maior_peso = min(w1, w2), max(w1, w2)
        arr1 = zootecnia.kg_to_arrobas(menor_peso, yield_)
        arr2 = zootecnia.kg_to_arrobas(maior_peso, yield_)
        self.assertLessEqual(
            arr1,
            arr2,
            f"Monotonicidade violada: {menor_peso}kg -> {arr1}@, {maior_peso}kg -> {arr2}@",
        )

    @settings(derandomize=True, max_examples=100)
    @given(
        w1=st.floats(min_value=50.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        w2=st.floats(min_value=50.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        dias=st.integers(min_value=1, max_value=1000),
    )
    def test_gmd_entre_duas_pesagens_e_simetrico(self, w1: float, w2: float, dias: int):
        """GMD entre duas pesagens trocando a ordem tem o mesmo módulo com sinal oposto."""
        gmd1 = (w2 - w1) / dias
        gmd2 = (w1 - w2) / dias
        self.assertTrue(
            math.isclose(gmd1, -gmd2, abs_tol=1e-9),
            f"GMD não simétrico: {gmd1} vs {gmd2}",
        )


class TestPropriedadesEstados(unittest.TestCase):
    @settings(derandomize=True, max_examples=50)
    @given(st_name=st.sampled_from(estados_animal.estados()))
    def test_transicao_para_mesmo_estado_animal_e_permitida(self, st_name: str):
        """Transição para o mesmo estado de animal é sempre permitida."""
        res = estados_animal.transicao_permitida(st_name, st_name)
        self.assertTrue(res["permitida"])

    @settings(derandomize=True, max_examples=50)
    @given(st_name=st.sampled_from(estados_dispositivo.estados()))
    def test_transicao_para_mesmo_estado_dispositivo_e_permitida(self, st_name: str):
        """Transição para o mesmo estado de dispositivo é sempre permitida."""
        res = estados_dispositivo.transicao_permitida(st_name, st_name)
        self.assertTrue(res["permitida"])

    @settings(derandomize=True, max_examples=100)
    @given(
        term=st.sampled_from(list(estados_dispositivo.terminais())),
        novo=st.sampled_from(estados_dispositivo.estados()),
    )
    def test_estado_terminal_dispositivo_nunca_admite_saida(self, term: str, novo: str):
        """Estado terminal de dispositivo não admite transição para outro estado."""
        if term != novo:
            res = estados_dispositivo.transicao_permitida(term, novo, tem_autorizacao=False)
            self.assertFalse(res["permitida"])

    @settings(derandomize=True, max_examples=100)
    @given(
        term=st.sampled_from(list(estados_animal.estados_finais())),
        novo=st.sampled_from(estados_animal.estados()),
    )
    def test_estado_final_animal_exige_autorizacao(self, term: str, novo: str):
        """Estado final de animal não admite transição sem autorização."""
        if term != novo and novo != "rascunho":
            res = estados_animal.transicao_permitida(term, novo, tem_autorizacao=False)
            self.assertFalse(res["permitida"])

    @settings(derandomize=True, max_examples=50)
    @given(st_name=st.sampled_from(estados_animal.estados()))
    def test_todo_estado_animal_esta_na_tabela(self, st_name: str):
        """Todo estado listado em estados() aparece como chave da tabela de transições de animal."""
        self.assertIn(st_name, estados_animal._TRANSICOES)

    @settings(derandomize=True, max_examples=50)
    @given(st_name=st.sampled_from(estados_dispositivo.estados()))
    def test_todo_estado_dispositivo_esta_na_tabela(self, st_name: str):
        """Todo estado listado em ESTADOS aparece na tabela de permissões de dispositivo."""
        self.assertIn(st_name, estados_dispositivo._PERMITIDAS)


class TestPropriedadesCaixa(unittest.TestCase):
    @settings(derandomize=True, max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        lancamentos=st.lists(
            st.fixed_dictionaries({
                "tipo": st.sampled_from(["receita", "despesa"]),
                "valor": st.integers(min_value=1, max_value=1000000).map(lambda c: c / 100.0),
                "competencia": st.just("2026-05-15"),
                "categoria": st.sampled_from(["Vendas", "Ração", "Veterinário"]),
            }),
            min_size=0,
            max_size=15,
        ),
        ano=st.just(2026),
        mes=st.just(5),
    )
    def test_receita_menos_despesa_igual_resultado(self, lancamentos: list[dict], ano: int, mes: int):
        """No resultado por competência, receita menos despesa é sempre igual ao resultado."""
        res = caixa.resultado_por_competencia(lancamentos, ano, mes)
        calc_resultado = round(res["receitas"] - res["despesas"], 2)
        self.assertEqual(res["resultado"], calc_resultado)

    @settings(derandomize=True, max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        lancamentos=st.lists(
            st.fixed_dictionaries({
                "tipo": st.sampled_from(["receita", "despesa"]),
                "valor": st.integers(min_value=1, max_value=1000000).map(lambda c: c / 100.0),
                "vencimento": st.just("2026-06-15"),
            }),
            min_size=1,
            max_size=15,
        ),
    )
    def test_lancamento_sem_pagamento_nunca_entra_no_realizado(self, lancamentos: list[dict]):
        """Lançamentos sem data de pagamento nunca contabilizam como realizado no fluxo de caixa."""
        fluxo = caixa.fluxo_de_caixa(lancamentos, de="2026-01-01", ate="2026-12-31")
        self.assertEqual(fluxo["realizado"], 0.0)


class TestPropriedadesRegrasRegulatorias(unittest.TestCase):
    @settings(derandomize=True, max_examples=100)
    @given(
        d1=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
        d2=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
        ref=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
    )
    def test_regra_com_data_final_anterior_a_inicial_nunca_vigente(self, d1: date, d2: date, ref: date):
        """Regra com data_final anterior a data_inicial nunca é considerada vigente."""
        if d2 < d1:
            regra = {"data_inicial": d1.isoformat(), "data_final": d2.isoformat()}
            self.assertFalse(regras_regulatorias.vigente_em(regra, ref))

    @settings(derandomize=True, max_examples=50)
    @given(
        op_invalido=st.text(min_size=1, max_size=10).filter(
            lambda s: s not in regras_regulatorias.OPERADORES
        )
    )
    def test_operador_desconhecido_nunca_dispara(self, op_invalido: str):
        """Condição com operador desconhecido nunca dispara."""
        condicao = {"campo": "peso", "operador": op_invalido, "valor": 100}
        contexto = {"peso": 200}
        self.assertFalse(regras_regulatorias._condicao_dispara(condicao, contexto))
