"""Testes da API Backend em FastAPI (Spec 0044 v2).

Valida autenticação JWT, rate limiting, refresh tokens revogáveis,
endpoints essenciais de dados e registro de pesagens.
"""

import inspect
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

# Força segredo de teste com tamanho adequado (>= 32 chars) e modo SQLite
os.environ["AGROTOP_API_SECRET"] = "agrotop-super-secret-jwt-key-32chars-min!!"
os.environ["AGROTOP_FORCE_SQLITE"] = "1"

import jwt
from fastapi.testclient import TestClient

import backend_api.main as main_mod
import database as db
from backend_api.config import (
    ACCESS_TOKEN_EXPIRE_SECONDS,
    TOKEN_ALGORITHM,
    TOKEN_ISSUER,
    get_secret_key,
)
from backend_api.main import app, limiter
from repositories.animais import get_all_animals, get_animal
from repositories.conexao import _conn, configurar_sqlite
from repositories.pesagens import get_weighings


class BackendApiTestCase(unittest.TestCase):
    def setUp(self):
        # Cria banco SQLite isolado para os testes
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_backend_api.db")
        configurar_sqlite(self.db_path)
        db.init_db()

        # Cria usuário de teste com senha conhecida
        with _conn() as con:
            from services.seguranca import _hash
            con.execute(
                "INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                ("testuser", _hash("SenhaForte123!"), "Test User", "operator"),
            )

        # Reset rate limiter memory before each test
        limiter.reset()
        self.client = TestClient(app)

    def tearDown(self):
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except Exception:
            pass

    def _get_access_token(self, username="testuser", password="SenhaForte123!"):
        res = self.client.post("/auth/login", json={"username": username, "password": password})
        self.assertEqual(res.status_code, 200)
        return res.json()["access_token"]


class TestAuthAndTokens(BackendApiTestCase):
    def test_login_sucesso_retorna_tokens_e_usuario(self):
        """Critério 1: POST /auth/login com credenciais válidas retorna access_token (JWT, 15 min),
        refresh_token (7 dias) e dados do usuário."""
        res = self.client.post("/auth/login", json={"username": "testuser", "password": "SenhaForte123!"})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertEqual(data["expires_in"], ACCESS_TOKEN_EXPIRE_SECONDS)
        self.assertEqual(data["expires_in"], 900)  # 15 minutos

        # Valida payload do JWT
        claims = jwt.decode(
            data["access_token"],
            get_secret_key(),
            algorithms=[TOKEN_ALGORITHM],
            issuer=TOKEN_ISSUER,
        )
        self.assertEqual(claims["username"], "testuser")
        self.assertEqual(claims["name"], "Test User")
        self.assertEqual(claims["role"], "operator")
        self.assertEqual(claims["type"], "access")

        # Valida que o refresh_token foi persistido na tabela api_refresh_tokens
        with _conn() as con:
            row = con.execute(
                "SELECT * FROM api_refresh_tokens WHERE token = ?", (data["refresh_token"],)
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(int(row["revoked"]), 0)

    def test_login_invalido_e_rate_limiting(self):
        """Critério 2: Credenciais erradas retornam 401. Após 5 tentativas erradas, a 6ª retorna 429."""
        # 5 tentativas com senha errada -> todas devem ser 401
        for _ in range(5):
            res = self.client.post("/auth/login", json={"username": "testuser", "password": "wrongpassword"})
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.json()["detail"], "Usuário ou senha inválidos.")

        # 6ª tentativa deve estourar o rate limit (429)
        res_6 = self.client.post("/auth/login", json={"username": "testuser", "password": "wrongpassword"})
        self.assertEqual(res_6.status_code, 429)

    def test_refresh_token_e_logout(self):
        """Critério 3: POST /auth/refresh com token válido retorna novo access_token.
        Após POST /auth/logout, o refresh_token fica revogado e retorna 401."""
        login_res = self.client.post("/auth/login", json={"username": "testuser", "password": "SenhaForte123!"})
        refresh_token = login_res.json()["refresh_token"]

        # Renovação com refresh token válido
        refresh_res = self.client.post("/auth/refresh", json={"refresh_token": refresh_token})
        self.assertEqual(refresh_res.status_code, 200)
        new_token_data = refresh_res.json()
        self.assertIn("access_token", new_token_data)
        self.assertEqual(new_token_data["expires_in"], 900)

        # Logout revoga o refresh_token
        logout_res = self.client.post("/auth/logout", json={"refresh_token": refresh_token})
        self.assertEqual(logout_res.status_code, 204)

        # Tentar renovar com token revogado retorna 401
        revoked_res = self.client.post("/auth/refresh", json={"refresh_token": refresh_token})
        self.assertEqual(revoked_res.status_code, 401)
        self.assertEqual(revoked_res.json()["detail"], "Refresh token inválido ou expirado.")

    def test_refresh_token_expirado_retorna_401(self):
        """Refresh token com data no passado retorna 401."""
        expired_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        with _conn() as con:
            con.execute(
                "INSERT INTO api_refresh_tokens (token, user_id, expires_at, revoked) VALUES (?, 1, ?, 0)",
                ("expired_tok_123", expired_date),
            )

        res = self.client.post("/auth/refresh", json={"refresh_token": "expired_tok_123"})
        self.assertEqual(res.status_code, 401)


class TestProtectedDataEndpoints(BackendApiTestCase):
    def test_endpoints_protegidos_sem_token_ou_invalido(self):
        """Critério 4: Rejeita chamadas sem token ou com token inválido/expirado com 401."""
        # Sem token
        res_no_tok = self.client.get("/animais")
        self.assertEqual(res_no_tok.status_code, 401)

        # Token malformado
        res_bad_tok = self.client.get("/animais", headers={"Authorization": "Bearer token_invalido"})
        self.assertEqual(res_bad_tok.status_code, 401)

        # Token expirado
        expired_claims = {
            "sub": "1",
            "username": "testuser",
            "name": "Test User",
            "role": "operator",
            "iat": datetime.now(timezone.utc) - timedelta(minutes=30),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=15),
            "iss": TOKEN_ISSUER,
            "type": "access",
        }
        expired_jwt = jwt.encode(expired_claims, get_secret_key(), algorithm=TOKEN_ALGORITHM)
        res_exp = self.client.get("/animais", headers={"Authorization": f"Bearer {expired_jwt}"})
        self.assertEqual(res_exp.status_code, 401)

    def test_list_animais_com_paginacao(self):
        """Critério 4: GET /animais autenticado lista animais com paginação."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        res = self.client.get("/animais?skip=0&limit=5", headers=headers)
        self.assertEqual(res.status_code, 200)
        items = res.json()
        self.assertIsInstance(items, list)
        if len(items) > 0:
            item = items[0]
            self.assertIn("id", item)
            self.assertIn("breed", item)
            self.assertIn("sex", item)
            self.assertIn("current_weight", item)
            self.assertIn("status", item)

    def test_get_animal_detalhes_com_gmd(self):
        """Critério 4: GET /animais/{id} retorna detalhes e cálculos de GMD."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Pega um animal existente do seed
        animais = get_all_animals()
        self.assertTrue(len(animais) > 0, "Deve haver animais no seed.")
        animal_id = animais[0]["id"]

        res = self.client.get(f"/animais/{animal_id}", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], animal_id)
        self.assertIn("gmd_recent_kg_day", data)
        self.assertIn("gmd_total_kg_day", data)

    def test_get_animal_inexistente_retorna_404(self):
        """GET /animais/{id} para ID inexistente retorna 404."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        res = self.client.get("/animais/999999", headers=headers)
        self.assertEqual(res.status_code, 404)

    def test_get_animal_inativo_continua_consultavel(self):
        """Animal vendido/morto NÃO pode virar 404 — a ficha continua existindo
        (mesmo comportamento de `get_animal()`, que o web usa sem filtrar por
        status). Só a LISTAGEM filtra por ativo por padrão, não a ficha."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        animais = get_all_animals()
        animal_id = animais[0]["id"]
        with _conn() as con:
            con.execute("UPDATE animals SET status='vendido' WHERE id=?", (animal_id,))

        res = self.client.get(f"/animais/{animal_id}", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "vendido")

    def test_campos_de_animal_nao_incluem_tag_nem_name(self):
        """`animals` não tem coluna `tag` nem `name` — expor esses campos
        sempre nulos é contrato enganoso. Regressão do que a v2 corrigiu."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        animal_id = get_all_animals()[0]["id"]

        detalhe = self.client.get(f"/animais/{animal_id}", headers=headers).json()
        lista = self.client.get("/animais", headers=headers).json()[0]

        self.assertNotIn("tag", detalhe)
        self.assertNotIn("name", detalhe)
        self.assertNotIn("tag", lista)
        self.assertNotIn("name", lista)


class TestPesagensEndpoint(BackendApiTestCase):
    def test_post_pesagem_cria_registro_atualiza_peso_e_evento(self):
        """Critério 5: POST /animais/{id}/pesagens cria registro em weighings,
        atualiza animals.current_weight e registra em animal_events."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        animais = get_all_animals()
        animal_id = animais[0]["id"]
        novo_peso = 465.5
        data_pesagem = "2026-08-21"

        payload = {
            "peso": novo_peso,
            "data": data_pesagem,
            "method": "pesado",
            "notes": "Pesagem de teste via API",
        }

        res = self.client.post(f"/animais/{animal_id}/pesagens", json=payload, headers=headers)
        self.assertEqual(res.status_code, 201)
        res_data = res.json()
        self.assertEqual(res_data["status"], "success")
        self.assertEqual(res_data["peso"], novo_peso)

        # 1. Verifica se foi gravado em weighings
        weighings = get_weighings(animal_id)
        self.assertTrue(any(w["weight"] == novo_peso for w in weighings))

        # 2. Verifica se animals.current_weight foi atualizado
        updated_animal = get_animal(animal_id)
        self.assertEqual(updated_animal["current_weight"], novo_peso)

        # 3. Verifica se o evento foi registrado em animal_events
        with _conn() as con:
            events = con.execute(
                "SELECT * FROM animal_events WHERE animal_uuid = ? AND tipo = 'pesagem'",
                (updated_animal["uuid"],),
            ).fetchall()
            self.assertTrue(len(events) > 0)
            last_event = dict(events[-1])
            self.assertIn("465.5 kg", last_event["observacoes"])

    def test_post_pesagem_animal_inexistente_retorna_404(self):
        """POST /animais/{id}/pesagens com ID inexistente retorna 404."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "peso": 400.0,
            "data": "2026-08-21",
        }
        res = self.client.post("/animais/999999/pesagens", json=payload, headers=headers)
        self.assertEqual(res.status_code, 404)


class TestSecurityAndIsolation(unittest.TestCase):
    def test_secret_inseguro_rejeitado(self):
        """Critério de segurança: Secret com menos de 32 caracteres levanta erro."""
        with patch.dict(os.environ, {"AGROTOP_API_SECRET": "curto"}):
            with self.assertRaises(RuntimeError):
                get_secret_key()

    def test_sem_duplicacao_de_logica_de_negocio(self):
        """Critério 6: Nenhum cálculo de negócio ou SQL duplicado dentro de backend_api/."""
        # backend_api reutiliza por import, não define novas fórmulas de zootecnia
        forbidden_funcs = ["calculate_gmd", "calculate_gmd_total", "estimate_weight_by_measurement", "register_sale"]
        defined_funcs = [name for name, _ in inspect.getmembers(main_mod, inspect.isfunction)
                         if inspect.getmodule(_) == main_mod]

        for forbidden in forbidden_funcs:
            self.assertNotIn(forbidden, defined_funcs, f"{forbidden} não deve ser reimplementada em backend_api")


if __name__ == "__main__":
    unittest.main()
