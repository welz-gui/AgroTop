"""Privacidade dos agregados e contrato HTTP, sem rede externa."""

import ast
import inspect
import json
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

import requests

from database import AnimalStats
from services import assistente_ia as ia


class TestContextoAssistente(unittest.TestCase):
    def test_contexto_real_do_motor_so_exporta_agregados(self):
        privado = "550e8400-e29b-41d4-a716-446655440000"
        bruto = {
            "hoje": "2026-09-09",
            "animais": [
                {
                    "id": privado,
                    "peso": 600,
                    "peso_alvo": 500,
                    "carencia_ate": "2026-10-10",
                    "gmd": 0.2,
                },
                {"id": "outro-uuid", "peso": 610, "peso_alvo": 500, "gmd": 0.1},
            ],
            "insumos": [
                {
                    "id": "insumo-secreto",
                    "nome": "Fornecedor Sigiloso",
                    "saldo": 10,
                    "consumo_diario": 5,
                }
            ],
            "lotes": [
                {
                    "id": "lote-secreto",
                    "nome": "Comprador Sigiloso",
                    "ua_atual": 30,
                    "capacidade_ua": 10,
                }
            ],
            "custo_por_arroba": 400,
            "preco_arroba": 300,
            "valor_individual": 98765.43,
        }
        original = deepcopy(bruto)
        stats = AnimalStats(total=2, avg_weight=605, avg_gmd=0.15)
        stats.uuid = privado
        stats.fornecedor = "Fornecedor Sigiloso"
        stats.valor_individual = 98765.43
        alertas = {"sumidos": [bruto], "carencia": [bruto], "prontos": []}
        with (
            patch.object(ia.db, "get_rebanho_stats", return_value=stats),
            patch.object(ia.db, "get_alert_animals", return_value=alertas),
            patch.object(ia.db, "contexto_recomendacoes", return_value=bruto),
            patch.object(ia, "avaliar", wraps=ia.avaliar) as motor,
        ):
            contexto = ia.montar_contexto()
        motor.assert_called_once_with(bruto)
        self.assertEqual(bruto, original)
        self.assertEqual(contexto["rebanho"]["avg_weight"], 605)
        self.assertEqual(contexto["alertas_contagem"], {"sumidos": 1, "carencia": 1, "prontos": 0})
        recs = {r["regra"]: r for r in contexto["recomendacoes"]}
        self.assertEqual(len(recs), 6)
        self.assertEqual(recs["gmd_abaixo_da_meta"]["quantidade"], 2)
        for rec in recs.values():
            self.assertEqual(set(rec), {"regra", "severidade", "quantidade", "motivo"})
        serializado = json.dumps(contexto, ensure_ascii=False)
        for proibido in (
            privado,
            "outro-uuid",
            "insumo-secreto",
            "lote-secreto",
            "Fornecedor Sigiloso",
            "Comprador Sigiloso",
            "98765.43",
            '"animal_id"',
            '"uuid"',
            '"dados"',
            '"animais"',
            '"fornecedor"',
            '"valor_individual"',
        ):
            self.assertNotIn(proibido, serializado)
        print("CONTEXTO SINTÉTICO VERIFICADO (motor real): " + serializado)

    def test_textos_e_campos_novos_do_motor_nao_vazam(self):
        rec = {
            "regra": "margem_em_risco",
            "severidade": "alta",
            "titulo": "SEGREDO",
            "motivo": "SEGREDO",
            "acao": "SEGREDO",
            "dados": {"buyer": "SEGREDO", "profit": 88888},
        }
        with (
            patch.object(ia.db, "get_rebanho_stats", return_value=AnimalStats()),
            patch.object(
                ia.db,
                "get_alert_animals",
                return_value={"sumidos": [], "carencia": [], "prontos": []},
            ),
            patch.object(ia.db, "contexto_recomendacoes", return_value={}),
            patch.object(
                ia,
                "avaliar",
                return_value=[rec, {**rec, "regra": "SEGREDO"}, {**rec, "severidade": "SEGREDO"}],
            ),
        ):
            contexto = ia.montar_contexto()
        self.assertNotIn("SEGREDO", json.dumps(contexto))
        self.assertEqual(len(contexto["recomendacoes"]), 1)

    def test_vazio_e_numeros_nao_finitos(self):
        with (
            patch.object(
                ia.db,
                "get_rebanho_stats",
                return_value=AnimalStats(avg_weight=float("nan"), avg_gmd=float("inf")),
            ),
            patch.object(
                ia.db,
                "get_alert_animals",
                return_value={"sumidos": [], "carencia": [], "prontos": []},
            ),
            patch.object(ia.db, "contexto_recomendacoes", return_value={}),
        ):
            contexto = ia.montar_contexto()
        self.assertEqual(contexto["recomendacoes"], [])
        self.assertIsNone(contexto["rebanho"]["avg_weight"])
        json.dumps(contexto, allow_nan=False)

    def test_so_tres_leituras_autorizadas_do_banco(self):
        arvore = ast.parse(inspect.getsource(ia))
        acessos = {
            n.attr
            for n in ast.walk(arvore)
            if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == "db"
        }
        self.assertEqual(
            acessos, {"get_rebanho_stats", "get_alert_animals", "contexto_recomendacoes"}
        )


class TestPerguntar(unittest.TestCase):
    def setUp(self):
        self.post = patch.object(ia.requests, "post").start()
        self.addCleanup(patch.stopall)
        self.resposta = Mock(status_code=200)
        self.resposta.json.return_value = {
            "choices": [{"message": {"content": " Há dois alertas. "}}]
        }
        self.post.return_value = self.resposta
        self.chave = "credencial-ficticia-nao-expor"

    def perguntar(self, **kwargs):
        params = {"api_key": self.chave, "modelo": "modelo-de-teste"}
        params.update(kwargs)
        return ia.perguntar("Como está o rebanho?", {"rebanho": {"total": 2}}, **params)

    def test_sucesso_payload_timeout_e_sem_historico_ou_ferramentas(self):
        self.assertEqual(self.perguntar(timeout=17), "Há dois alertas.")
        args, kwargs = self.post.call_args
        self.assertEqual(args, ("https://openrouter.ai/api/v1/chat/completions",))
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {self.chave}")
        self.assertEqual(kwargs["timeout"], 17)
        self.assertFalse(kwargs["allow_redirects"])
        payload = kwargs["json"]
        self.assertEqual(set(payload), {"model", "messages"})
        self.assertEqual(len(payload["messages"]), 2)
        sistema = payload["messages"][0]["content"]
        for aviso in (
            "Não invente",
            "diga que não sabe",
            "veterinário",
            "financeiro",
            "não executa ações",
        ):
            self.assertIn(aviso, sistema)
        self.assertNotIn(self.chave, json.dumps(payload))
        self.assertEqual(
            json.loads(payload["messages"][1]["content"]),
            {"pergunta": "Como está o rebanho?", "contexto": {"rebanho": {"total": 2}}},
        )
        self.perguntar()
        self.assertEqual(len(self.post.call_args.kwargs["json"]["messages"]), 2)

    def test_falhas_http_sem_corpo_ou_credencial_na_excecao(self):
        for status, mensagem in (
            (401, "chave"),
            (403, "chave"),
            (429, "limite"),
            (500, "indisponível"),
            (302, "indisponível"),
        ):
            with self.subTest(status=status):
                self.resposta.status_code = status
                self.resposta.text = self.chave
                with self.assertRaises(ia.AssistenteIndisponivelError) as ctx:
                    self.perguntar()
                self.assertIn(mensagem, str(ctx.exception))
                self.assertNotIn(self.chave, str(ctx.exception))
        self.resposta.json.assert_not_called()

    def test_rede_e_timeout_sem_vazar_erro_original(self):
        for erro in (requests.ConnectionError, requests.Timeout):
            with self.subTest(erro=erro):
                self.post.side_effect = erro(self.chave)
                with self.assertRaises(ia.AssistenteIndisponivelError) as ctx:
                    self.perguntar()
                self.assertNotIn(self.chave, str(ctx.exception))
                self.assertTrue(ctx.exception.__suppress_context__)

    def test_chave_ausente_e_modelo_vazio_nao_fazem_rede(self):
        for kwargs in ({"api_key": ""}, {"api_key": None}, {"api_key": " "}, {"modelo": ""}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ia.AssistenteIndisponivelError):
                self.perguntar(**kwargs)
        self.post.assert_not_called()

    def test_pergunta_vazia_nao_faz_rede(self):
        with self.assertRaises(ia.AssistenteIndisponivelError):
            ia.perguntar(" ", {}, api_key=self.chave, modelo="teste")
        self.post.assert_not_called()

    def test_respostas_malformadas(self):
        for resposta in (
            {},
            {"choices": []},
            {"choices": None},
            {"choices": [{"message": {"content": None}}]},
            {"choices": [{"message": {"content": " "}}]},
            {"choices": [{"message": {"content": ["texto"]}}]},
        ):
            with self.subTest(resposta=resposta):
                self.resposta.json.return_value = resposta
                with self.assertRaises(ia.AssistenteIndisponivelError):
                    self.perguntar()
        self.resposta.json.side_effect = ValueError(self.chave)
        with self.assertRaises(ia.AssistenteIndisponivelError) as ctx:
            self.perguntar()
        self.assertNotIn(self.chave, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
