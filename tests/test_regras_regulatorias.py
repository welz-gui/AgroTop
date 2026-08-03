"""Motor de regras regulatórias (ADR 0004 · B5 · PNIB §11).

O §11 abre exigindo que **"as regras não devem ficar fixadas no código-fonte"**.
Estes testes verificam as três coisas que tornam isso real:

1. **vigência** — a regra que vale em 2027 não é a de 2030;
2. **versionamento** — alterar cria versão nova, não sobrescreve;
3. **simulação** — dá para medir o alcance antes de ativar.

Sem vigência, a norma de hoje julgaria o que aconteceu antes de ela existir.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402
from repositories import eventos, regras  # noqa: E402
from services.regras_regulatorias import avaliar, simular, vigente_em  # noqa: E402


class BaseB5(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "b5.db"))
        db.init_db()
        db.clear_cache()

    def _criar(self, nome="Regra teste", **kw):
        kw.setdefault("aprovado_por", "admin")
        kw.setdefault("usuario", "admin")
        r = regras.criar(nome, **kw)
        self.assertTrue(r["ok"], r)
        db.clear_cache()
        return r["id"]


class TestVigencia(BaseB5):
    """A parte que se esquece — e que reescreveria o passado se faltasse."""

    def test_regra_futura_nao_dispara_hoje(self):
        """O PNIB só exige identificação para trânsito a partir de 2033."""
        self._criar("Identificação obrigatória",
                    nivel="bloqueio", evento_aplicacao="movimentacao",
                    data_inicial="2033-01-01",
                    condicao={"campo": "tem_id", "operador": "igual", "valor": False})
        ctx = {"evento_aplicacao": "movimentacao", "tem_id": False}

        hoje = regras.aplicar_a(ctx, evento="movimentacao", referencia="2026-08-03")
        futuro = regras.aplicar_a(ctx, evento="movimentacao", referencia="2033-06-01")

        self.assertEqual(len(hoje["disparadas"]), 0)
        self.assertTrue(hoje["pode_prosseguir"])
        self.assertEqual(len(futuro["disparadas"]), 1)
        self.assertFalse(futuro["pode_prosseguir"])

    def test_regra_revogada_nao_dispara_depois(self):
        self._criar("Regra antiga", nivel="alerta",
                    data_inicial="2020-01-01", data_final="2025-12-31")
        antes = regras.aplicar_a({}, referencia="2024-06-01")
        depois = regras.aplicar_a({}, referencia="2026-06-01")
        self.assertEqual(len(antes["disparadas"]), 1)
        self.assertEqual(len(depois["disparadas"]), 0)

    def test_sem_datas_vale_sempre(self):
        r = {"nome": "X", "nivel": "informativo"}
        self.assertTrue(vigente_em(r, date(2020, 1, 1)))
        self.assertTrue(vigente_em(r, date(2040, 1, 1)))

    def test_referencia_omitida_usa_hoje(self):
        self._criar("Vigente agora", nivel="alerta",
                    data_inicial=(date.today() - timedelta(days=1)).isoformat())
        self.assertEqual(len(regras.aplicar_a({})["disparadas"]), 1)


class TestEscopo(BaseB5):
    def test_campo_vazio_significa_qualquer(self):
        """Regra federal não pode precisar enumerar as 27 UFs."""
        self._criar("Federal", nivel="alerta", esfera="federal", uf=None)
        for uf in ("MT", "RS", "GO"):
            self.assertEqual(len(regras.aplicar_a({"uf": uf})["disparadas"]), 1)

    def test_regra_estadual_so_dispara_na_uf(self):
        self._criar("Só do RS", nivel="alerta", esfera="estadual", uf="RS")
        self.assertEqual(len(regras.aplicar_a({"uf": "RS"})["disparadas"]), 1)
        self.assertEqual(len(regras.aplicar_a({"uf": "MT"})["disparadas"]), 0)

    def test_faixa_etaria(self):
        self._criar("Só bezerro", nivel="alerta",
                    idade_min_meses=0, idade_max_meses=12)
        self.assertEqual(len(regras.aplicar_a({"idade_meses": 6})["disparadas"]), 1)
        self.assertEqual(len(regras.aplicar_a({"idade_meses": 24})["disparadas"]), 0)


class TestCondicao(BaseB5):
    def test_operadores_de_ordem_exigem_numero(self):
        """Comparar texto com `>` daria ordem alfabética — ninguém espera isso."""
        r = [{"nome": "R", "nivel": "alerta",
              "condicao": {"campo": "peso", "operador": "maior", "valor": 400}}]
        self.assertEqual(len(avaliar(r, {"peso": 500})), 1)
        self.assertEqual(len(avaliar(r, {"peso": 300})), 0)
        self.assertEqual(len(avaliar(r, {"peso": "boi gordo"})), 0)

    def test_operador_desconhecido_nunca_dispara(self):
        r = [{"nome": "R", "nivel": "bloqueio",
              "condicao": {"campo": "x", "operador": "execute_isto", "valor": 1}}]
        self.assertEqual(avaliar(r, {"x": 1}), [])

    def test_condicoes_multiplas_sao_E_logico(self):
        r = [{"nome": "R", "nivel": "alerta", "condicao": [
            {"campo": "uf", "operador": "igual", "valor": "RS"},
            {"campo": "peso", "operador": "maior", "valor": 400}]}]
        self.assertEqual(len(avaliar(r, {"uf": "RS", "peso": 500})), 1)
        self.assertEqual(len(avaliar(r, {"uf": "RS", "peso": 300})), 0)

    def test_vazio_e_preenchido(self):
        r = [{"nome": "R", "nivel": "alerta",
              "condicao": {"campo": "gta", "operador": "vazio"}}]
        self.assertEqual(len(avaliar(r, {"gta": None})), 1)
        self.assertEqual(len(avaliar(r, {"gta": "123"})), 0)


class TestNiveis(BaseB5):
    def test_bloqueio_impede_e_vem_primeiro(self):
        self._criar("Informativa", nivel="informativo")
        self._criar("Bloqueio", nivel="bloqueio")
        self._criar("Alerta", nivel="alerta")
        r = regras.aplicar_a({})
        self.assertEqual([d["nivel"] for d in r["disparadas"]],
                         ["bloqueio", "alerta", "informativo"])
        self.assertFalse(r["pode_prosseguir"])

    def test_alerta_pede_confirmacao_mas_deixa_prosseguir(self):
        self._criar("Alerta", nivel="alerta")
        r = regras.aplicar_a({})
        self.assertTrue(r["pode_prosseguir"])
        self.assertTrue(r["exige_confirmacao"])


class TestAprovacao(BaseB5):
    def test_regra_sem_aprovador_nasce_inativa(self):
        """§11.1 pede responsável pela aprovação — sem ele, não vale."""
        r = regras.criar("Sem dono", nivel="bloqueio", aprovado_por="")
        self.assertTrue(r["ok"])
        self.assertFalse(r["ativa"])
        db.clear_cache()
        self.assertEqual(len(regras.aplicar_a({})["disparadas"]), 0)

    def test_criacao_e_auditada(self):
        rid = self._criar("Auditada")
        t = eventos.trilha(entidade="regras_regulatorias", entidade_id=rid)
        self.assertTrue(t, "criação de regra não foi auditada")


class TestVersionamento(BaseB5):
    """Alterar regra cria versão; não reescreve o passado."""

    def test_nova_versao_encerra_a_anterior_e_incrementa(self):
        rid = self._criar("Original", nivel="alerta",
                          data_inicial="2020-01-01")
        r = regras.nova_versao(rid, aprovado_por="admin", usuario="admin",
                               nivel="bloqueio")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["versao"], 2)

        antiga = regras.get(rid)
        self.assertIsNotNone(antiga["data_final"], "versão antiga sem data final")
        self.assertEqual(antiga["ativa"], 1,
                         "versão antiga foi marcada inativa — `ativa` significa "
                         "APROVADA, e quem encerra a vigência é a data_final")

        nova = regras.get(r["id"])
        self.assertEqual(nova["nivel"], "bloqueio")
        self.assertEqual(nova["data_inicial"], date.today().isoformat())

    def test_a_versao_antiga_continua_explicando_o_passado(self):
        """O ponto todo do versionamento: reexaminar 2024 com a regra de 2024."""
        rid = self._criar("Muda com o tempo", nivel="informativo",
                          data_inicial="2020-01-01")
        regras.nova_versao(rid, aprovado_por="admin", usuario="admin",
                           nivel="bloqueio")
        db.clear_cache()

        passado = regras.aplicar_a({}, referencia="2024-06-01")
        self.assertEqual([d["nivel"] for d in passado["disparadas"]],
                         ["informativo"],
                         "a regra de hoje julgou um fato de 2024")

    def test_nova_versao_exige_aprovador(self):
        rid = self._criar("X")
        self.assertFalse(regras.nova_versao(rid, aprovado_por="  ",
                                            usuario="admin")["ok"])


class TestSimulacao(BaseB5):
    """§11.3: medir o alcance ANTES de ativar."""

    def test_mede_quantos_casos_a_regra_atinge(self):
        regra = {"nome": "Sem GTA", "nivel": "bloqueio",
                 "condicao": {"campo": "gta", "operador": "vazio"}}
        casos = [{"id": "A", "gta": None}, {"id": "B", "gta": "123"},
                 {"id": "C", "gta": None}, {"id": "D", "gta": "456"}]
        s = simular(regra, casos)
        self.assertEqual(s["atingidos"], 2)
        self.assertEqual(sorted(s["ids"]), ["A", "C"])
        self.assertEqual(s["percentual"], 50.0)

    def test_simular_regra_futura_avisa_que_nao_vigora(self):
        rid = self._criar("Futura", nivel="bloqueio", data_inicial="2033-01-01")
        s = regras.simular_regra(rid, [{"id": "A"}], referencia="2026-08-03")
        self.assertFalse(s["vigente_na_data"])
        self.assertEqual(s["atingidos"], 0)

    def test_lista_vazia_nao_divide_por_zero(self):
        self.assertEqual(simular({"nome": "X"}, [])["percentual"], 0.0)


if __name__ == "__main__":
    unittest.main()
