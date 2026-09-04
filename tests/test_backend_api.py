"""Testes da API Backend em FastAPI (Spec 0044 v2 + Spec 0048 + Spec 0050 + Spec 0052).

Valida autenticação JWT, rate limiting, refresh tokens revogáveis,
endpoints essenciais de dados, registro de pesagens, movimentação entre piquetes,
sanidade/carência e fotos dos animais.
"""

import inspect
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
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
from backend_api.idempotency import get_cached_response, store_response
from backend_api.main import app, limiter
from backend_api.schemas import ConfirmarTratoInput
from repositories.animais import get_all_animals, get_animal
from repositories.conexao import _conn, configurar_sqlite
from repositories.pesagens import get_weighings
from repositories.sanidade import add_medication, get_withdrawal_end
from services.geometria import area_hectares, perimetro_metros, validar


class BackendApiTestCase(unittest.TestCase):
    def setUp(self):
        # Cria banco SQLite isolado para os testes
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_backend_api.db")
        configurar_sqlite(self.db_path)
        db.init_db()
        # Cada teste troca de banco SQLite (novo tmp_dir), mas os bulk loaders
        # cacheados (@_cache / st.cache_data, ex.: get_all_animals) não sabem
        # disso — sem isto, um teste pode ler um animal com o `uuid` do banco
        # temporário do teste ANTERIOR (o `id` é o mesmo por seed determinístico,
        # o `uuid` não), e uma escrita nova não aparece na consulta seguinte.
        db.clear_cache()

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


class TestMovimentacaoEndpoint(BackendApiTestCase):
    def test_get_lotes_sem_authorization_retorna_401(self):
        """Critério 1 (Spec 0048): GET /lotes sem Authorization devolve 401."""
        res = self.client.get("/lotes")
        self.assertEqual(res.status_code, 401)

    def test_get_lotes_autenticado_retorna_piquetes_do_banco(self):
        """Critério 2 (Spec 0048): GET /lotes com token válido devolve exatamente os piquetes que
        database.get_all_lotes() devolve no mesmo banco."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        res = self.client.get("/lotes", headers=headers)
        self.assertEqual(res.status_code, 200)
        items = res.json()

        db_lotes = db.get_all_lotes()
        self.assertEqual(len(items), len(db_lotes))

        for api_item, db_item in zip(items, db_lotes):
            self.assertEqual(api_item["id"], str(db_item["id"]))
            self.assertEqual(api_item["nome"], db_item.get("name") or "")
            self.assertEqual(api_item["capacidade_ua"], db_item.get("capacity_ua"))
            self.assertEqual(api_item["animais_ativos"], int(db_item.get("animal_count") or 0))

    def test_post_movimentar_move_de_fato_no_banco(self):
        """Critério 3 (Spec 0048): POST /animais/movimentar move de fato: compare animals.lote_id
        no banco antes e depois da chamada."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        animais = get_all_animals()
        self.assertTrue(len(animais) >= 2, "Necessário ao menos 2 animais.")
        lotes = db.get_all_lotes()
        self.assertTrue(len(lotes) >= 2, "Necessário ao menos 2 lotes.")

        destino_id = str(lotes[1]["id"])
        # Garante que os animais selecionados estejam em lote diferente do destino
        a1_id = animais[0]["id"]
        a2_id = animais[1]["id"]
        with _conn() as con:
            con.execute("UPDATE animals SET lote_id = ? WHERE id IN (?, ?)", (lotes[0]["id"], a1_id, a2_id))

        payload = {
            "animal_ids": [a1_id, a2_id],
            "to_lote_id": destino_id,
            "movement_date": "2026-08-22",
            "reason": "manejo",
            "notes": "Movimentação em lote via API",
        }

        res = self.client.post("/animais/movimentar", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn(a1_id, data["movidos"])
        self.assertIn(a2_id, data["movidos"])
        self.assertEqual(data["ja_no_destino"], [])
        self.assertEqual(data["erros"], [])

        # Verifica persistência no banco
        animal1 = get_animal(a1_id)
        animal2 = get_animal(a2_id)
        self.assertEqual(str(animal1["lote_id"]), destino_id)
        self.assertEqual(str(animal2["lote_id"]), destino_id)

    def test_post_movimentar_animal_inexistente_vai_para_erros(self):
        """Critério 4 (Spec 0048): Um animal_id inexistente na lista aparece em 'erros', e os outros
        animais válidos da mesma chamada são movidos mesmo assim."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        animais = get_all_animals()
        lotes = db.get_all_lotes()
        destino_id = str(lotes[1]["id"])
        a_valido = animais[0]["id"]

        with _conn() as con:
            con.execute("UPDATE animals SET lote_id = ? WHERE id = ?", (lotes[0]["id"], a_valido))

        payload = {
            "animal_ids": [a_valido, "ANIMAL_INEXISTENTE_999"],
            "to_lote_id": destino_id,
            "movement_date": "2026-08-22",
        }

        res = self.client.post("/animais/movimentar", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn(a_valido, data["movidos"])
        self.assertIn("ANIMAL_INEXISTENTE_999", data["erros"])

        # O animal válido foi movido mesmo com erro no outro
        self.assertEqual(str(get_animal(a_valido)["lote_id"]), destino_id)

    def test_post_movimentar_animal_ja_no_destino(self):
        """Critério 5 (Spec 0048): Um animal já no piquete de destino aparece em 'ja_no_destino'
        e não gera linha nova em animal_movements para ele."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        animais = get_all_animals()
        lotes = db.get_all_lotes()
        destino_id = str(lotes[0]["id"])
        animal_id = animais[0]["id"]

        with _conn() as con:
            con.execute("UPDATE animals SET lote_id = ? WHERE id = ?", (destino_id, animal_id))
            qtd_movements_antes = con.execute("SELECT COUNT(*) FROM animal_movements").fetchone()[0]

        payload = {
            "animal_ids": [animal_id],
            "to_lote_id": destino_id,
            "movement_date": "2026-08-22",
        }

        res = self.client.post("/animais/movimentar", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["movidos"], [])
        self.assertIn(animal_id, data["ja_no_destino"])

        with _conn() as con:
            qtd_movements_depois = con.execute("SELECT COUNT(*) FROM animal_movements").fetchone()[0]
        self.assertEqual(qtd_movements_depois, qtd_movements_antes, "Não deve gerar movimento quando já no destino.")

    def test_post_movimentar_operator_vem_do_token(self):
        """Critério 6 (Spec 0048): operator gravado em animal_movements é o usuário do token, mesmo
        que o corpo da requisição tente mandar outro nome."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        animais = get_all_animals()
        lotes = db.get_all_lotes()
        destino_id = str(lotes[1]["id"])
        animal_id = animais[0]["id"]

        with _conn() as con:
            con.execute("UPDATE animals SET lote_id = ? WHERE id = ?", (lotes[0]["id"], animal_id))

        payload = {
            "animal_ids": [animal_id],
            "to_lote_id": destino_id,
            "movement_date": "2026-08-22",
            "operator": "hacker_fake_operator",
        }

        res = self.client.post("/animais/movimentar", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200)

        animal = get_animal(animal_id)
        with _conn() as con:
            movement = con.execute(
                "SELECT * FROM animal_movements WHERE animal_uuid = ? ORDER BY id DESC LIMIT 1",
                (animal["uuid"],),
            ).fetchone()
            self.assertIsNotNone(movement)
            self.assertEqual(movement["operator"], "testuser")
            self.assertNotEqual(movement["operator"], "hacker_fake_operator")


class TestFotosEndpoint(BackendApiTestCase):
    def test_post_foto_sem_authorization_retorna_401(self):
        """Critério 1 (Spec 0052): POST /animais/{id}/fotos sem Authorization devolve 401."""
        res = self.client.post(
            "/animais/1/fotos",
            files={"arquivo": ("foto.jpg", b"fake-jpg-content", "image/jpeg")},
        )
        self.assertEqual(res.status_code, 401)

    def test_upload_foto_valida_grava_e_retorna_bytes_iguais(self):
        """Critério 2 (Spec 0052): Upload de imagem válida grava na tabela animal_photos e
        GET /fotos/{id} devolve exatamente os mesmos bytes enviados."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        animal_id = get_all_animals()[0]["id"]
        foto_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00test-image-content"

        res = self.client.post(
            f"/animais/{animal_id}/fotos",
            files={"arquivo": ("boi.jpg", foto_bytes, "image/jpeg")},
            data={"taken_date": "2026-08-22"},
            headers=headers,
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn("id", data)
        photo_id = data["id"]

        # 1. Verifica no banco que foi gravado
        with _conn() as con:
            row = con.execute("SELECT * FROM animal_photos WHERE id=?", (photo_id,)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(bytes(row["image"]), foto_bytes)
            self.assertEqual(row["mime"], "image/jpeg")
            self.assertEqual(row["taken_date"], "2026-08-22")
            self.assertEqual(row["operator"], "testuser")

        # 2. Verifica que GET /fotos/{id} devolve os mesmos bytes byte-a-byte
        get_res = self.client.get(f"/fotos/{photo_id}", headers=headers)
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.headers["content-type"], "image/jpeg")
        self.assertEqual(get_res.content, foto_bytes)

    def test_upload_foto_acima_5mb_retorna_413_sem_orfaos(self):
        """Critério 3 (Spec 0052): Upload acima de 5 MB devolve 413 antes de gravar qualquer coisa."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        animal_id = get_all_animals()[0]["id"]
        grande_bytes = b"X" * (5 * 1024 * 1024 + 10)  # > 5 MB

        with _conn() as con:
            qtd_antes = con.execute("SELECT COUNT(*) FROM animal_photos").fetchone()[0]

        res = self.client.post(
            f"/animais/{animal_id}/fotos",
            files={"arquivo": ("foto_grande.jpg", grande_bytes, "image/jpeg")},
            headers=headers,
        )
        self.assertEqual(res.status_code, 413)

        with _conn() as con:
            qtd_depois = con.execute("SELECT COUNT(*) FROM animal_photos").fetchone()[0]
        self.assertEqual(qtd_depois, qtd_antes, "Não pode gravar linha órfã no banco.")

    def test_upload_tipo_nao_aceito_retorna_415(self):
        """Critério 4 (Spec 0052): Upload de tipo não aceito devolve 415."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        animal_id = get_all_animals()[0]["id"]
        pdf_bytes = b"%PDF-1.4..."

        res = self.client.post(
            f"/animais/{animal_id}/fotos",
            files={"arquivo": ("documento.pdf", pdf_bytes, "application/pdf")},
            headers=headers,
        )
        self.assertEqual(res.status_code, 415)

    def test_get_animais_fotos_nao_inclui_bytes_no_json(self):
        """Critério 5 (Spec 0052): GET /animais/{id}/fotos nunca inclui os bytes da imagem no JSON."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        animal_id = get_all_animals()[0]["id"]
        foto_bytes = b"imagem_teste_bytes_12345"

        # Cadastra foto
        post_res = self.client.post(
            f"/animais/{animal_id}/fotos",
            files={"arquivo": ("foto.png", foto_bytes, "image/png")},
            headers=headers,
        )
        self.assertEqual(post_res.status_code, 201)

        # Consulta lista de fotos
        res = self.client.get(f"/animais/{animal_id}/fotos", headers=headers)
        self.assertEqual(res.status_code, 200)
        items = res.json()
        self.assertIsInstance(items, list)
        self.assertTrue(len(items) > 0)

        for item in items:
            self.assertIn("id", item)
            self.assertIn("taken_date", item)
            self.assertIn("mime", item)
            self.assertNotIn("image", item)
            self.assertNotIn("bytes", item)

    def test_get_foto_outro_animal_e_inexistente(self):
        """Critério 6 (Spec 0052): GET /fotos/{id} inexistente devolve 404, nunca 500."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        res = self.client.get("/fotos/999999", headers=headers)
        self.assertEqual(res.status_code, 404)

    def test_operator_gravado_vem_do_token(self):
        """Critério 7 (Spec 0052): operator gravado em animal_photos é o usuário do token."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        animal_id = get_all_animals()[0]["id"]
        foto_bytes = b"foto_valida"

        res = self.client.post(
            f"/animais/{animal_id}/fotos",
            files={"arquivo": ("teste.jpg", foto_bytes, "image/jpeg")},
            data={"operator": "hacker_fake"},  # Se tentar injetar operator, deve ser ignorado
            headers=headers,
        )
        self.assertEqual(res.status_code, 201)
        photo_id = res.json()["id"]

        with _conn() as con:
            row = con.execute("SELECT operator FROM animal_photos WHERE id=?", (photo_id,)).fetchone()
            self.assertEqual(row["operator"], "testuser")
            self.assertNotEqual(row["operator"], "hacker_fake")


class TestSanidadeEndpoint(BackendApiTestCase):
    def test_get_protocolos_sem_authorization_retorna_401(self):
        """Critério 1 (Spec 0050): GET /protocolos sem Authorization devolve 401."""
        res = self.client.get("/protocolos")
        self.assertEqual(res.status_code, 401)

    def test_get_protocolos_devolve_somente_ativos(self):
        """Critério 2 (Spec 0050): protocolos inativos não aparecem na API."""
        with _conn() as con:
            ativo_id = con.execute(
                """INSERT INTO health_protocols
                   (name, dose_unit, withdrawal_days, route, active)
                   VALUES (?, ?, ?, ?, ?)""",
                ("Protocolo API ativo", "mL", 14, "Subcutânea", 1),
            ).lastrowid
            con.execute(
                """INSERT INTO health_protocols
                   (name, dose_unit, withdrawal_days, route, active)
                   VALUES (?, ?, ?, ?, ?)""",
                ("Protocolo API inativo", "dose", 30, "Intramuscular", 0),
            )

        token = self._get_access_token()
        res = self.client.get(
            "/protocolos",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(res.status_code, 200)
        items = res.json()
        nomes = {item["nome"] for item in items}
        self.assertIn("Protocolo API ativo", nomes)
        self.assertNotIn("Protocolo API inativo", nomes)
        self.assertEqual(
            next(item for item in items if item["id"] == ativo_id),
            {
                "id": ativo_id,
                "nome": "Protocolo API ativo",
                "via": "Subcutânea",
                "carencia_dias": 14,
                "unidade_dose": "mL",
                "dose_sugerida": None,
            },
        )

    def test_get_protocolos_com_animal_id_inclui_dose_sugerida(self):
        """Achado da spec 0051 (mobile): a 0050 original não expunha dose nenhuma em
        GET /protocolos, então não havia como a tela preencher a dose ao escolher um
        protocolo sem duplicar a fórmula de `dose_for_animal` em Dart (proibido —
        ROADMAP: nenhuma fórmula de negócio no mobile). Corrigido: `?animal_id=` faz
        a API calcular a dose sugerida, fixa ou proporcional ao peso conforme o
        protocolo, igual ao que `repositories.sanidade.dose_for_animal` já faz."""
        animal_id = get_all_animals()[0]["id"]
        animal = get_animal(animal_id)

        with _conn() as con:
            fixo_id = con.execute(
                """INSERT INTO health_protocols
                   (name, dose_value, dose_ref_kg, dose_unit, withdrawal_days, route, active)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                ("Dose fixa", 5.0, 0, "mL", 0, "Subcutânea"),
            ).lastrowid
            proporcional_id = con.execute(
                """INSERT INTO health_protocols
                   (name, dose_value, dose_ref_kg, dose_unit, withdrawal_days, route, active)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                ("Dose por peso", 1.0, 100.0, "mL/100kg", 0, "Intramuscular"),
            ).lastrowid

        token = self._get_access_token()
        res = self.client.get(
            f"/protocolos?animal_id={animal_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 200)
        items = {item["id"]: item for item in res.json()}

        self.assertEqual(items[fixo_id]["dose_sugerida"], 5.0)
        esperado_proporcional = round(animal["current_weight"] / 100.0 * 1.0, 2)
        self.assertEqual(items[proporcional_id]["dose_sugerida"], esperado_proporcional)

    def test_get_protocolos_com_animal_id_inexistente_retorna_404(self):
        token = self._get_access_token()
        res = self.client.get(
            "/protocolos?animal_id=NAO_EXISTE_999",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 404)

    def test_get_medicamentos_usa_carencia_calculada_pelo_repositorio(self):
        """Critério 3 (Spec 0050): a API expõe a carência calculada pelo repositório."""
        animal_id = get_all_animals()[0]["id"]
        hoje = datetime.now().date().isoformat()
        add_medication(
            animal_id,
            "Medicamento de comparação",
            2.5,
            "mL",
            "Subcutânea",
            9,
            hoje,
            applied_by="preparo_teste",
            protocol_id=None,
        )
        esperado = get_withdrawal_end(animal_id)
        self.assertIsNotNone(esperado)

        token = self._get_access_token()
        res = self.client.get(
            f"/animais/{animal_id}/medicamentos",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["carencia_ate"], esperado.isoformat())
        self.assertIn(
            {
                "medicamento": "Medicamento de comparação",
                "dose": 2.5,
                "unidade": "mL",
                "via": "Subcutânea",
                "carencia_dias": 9,
                "data": hoje,
                "protocolo_id": None,
            },
            data["aplicacoes"],
        )

    def test_post_medicamento_persiste_usuario_carencia_e_nao_baixa_estoque(self):
        """Critérios 4–7 (Spec 0050): persiste, usa o token e não movimenta estoque."""
        animal = get_all_animals()[0]
        animal_id = animal["id"]
        hoje = datetime.now().date().isoformat()
        with _conn() as con:
            insumo_id = con.execute(
                "INSERT INTO insumos (name, current_stock) VALUES (?, ?)",
                ("Insumo que não deve baixar", 73.0),
            ).lastrowid

        token = self._get_access_token()
        payload = {
            "medicamento": "Medicamento via API",
            "dose": 3.0,
            "unidade": "mL",
            "via": "Intramuscular",
            "carencia_dias": 12,
            "data": hoje,
            "protocolo_id": None,
            "notas": "Aplicação individual",
            "applied_by": "usuario_falso",
            "operator": "operador_falso",
            "insumo_id": insumo_id,
        }
        headers = {"Authorization": f"Bearer {token}"}

        post_res = self.client.post(
            f"/animais/{animal_id}/medicamentos",
            json=payload,
            headers=headers,
        )

        self.assertEqual(post_res.status_code, 201)
        carencia_repositorio = get_withdrawal_end(animal_id)
        self.assertIsNotNone(carencia_repositorio)
        self.assertEqual(post_res.json(), {"carencia_ate": carencia_repositorio.isoformat()})

        with _conn() as con:
            row = con.execute(
                """SELECT * FROM medications
                   WHERE animal_uuid = ? AND medication_name = ?
                   ORDER BY id DESC LIMIT 1""",
                (animal["uuid"], "Medicamento via API"),
            ).fetchone()
            estoque = con.execute(
                "SELECT current_stock FROM insumos WHERE id = ?",
                (insumo_id,),
            ).fetchone()[0]

        self.assertIsNotNone(row)
        self.assertEqual(row["applied_by"], "testuser")
        self.assertNotEqual(row["applied_by"], "usuario_falso")
        self.assertIsNone(row["insumo_id"])
        self.assertEqual(estoque, 73.0)

        get_res = self.client.get(
            f"/animais/{animal_id}/medicamentos",
            headers=headers,
        )
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["carencia_ate"], carencia_repositorio.isoformat())
        self.assertGreater(carencia_repositorio, datetime.now().date())
        self.assertTrue(
            any(
                item["medicamento"] == "Medicamento via API"
                for item in get_res.json()["aplicacoes"]
            )
        )

    def test_backend_api_nao_duplica_sql_de_sanidade(self):
        """Critério 8 (Spec 0050): a rota delega persistência ao repositório."""
        source = inspect.getsource(main_mod)
        self.assertNotIn("INSERT INTO medications", source)
        self.assertNotIn("UPDATE animals SET status='carencia'", source)


class TestTratoEndpoint(BackendApiTestCase):
    def _create_plan(self, *, active=True, insumo_id=None, quantity=8.0):
        lote = db.get_all_lotes()[0]
        db.add_feeding_plan(
            str(lote["id"]),
            "Trato API",
            quantity,
            "kg",
            "diario",
            insumo_id=insumo_id,
        )
        with _conn() as con:
            plan_id = con.execute(
                "SELECT id FROM feeding_plans ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
        if not active:
            db.set_feeding_plan_active(plan_id, 0)
        return plan_id, str(lote["id"])

    def _create_insumo(self, stock):
        with _conn() as con:
            return con.execute(
                """INSERT INTO insumos
                   (name, category, unit, current_stock, min_stock, cost_per_unit)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("Insumo de trato API", "Ração", "kg", stock, 0, 1.0),
            ).lastrowid

    def _headers(self):
        return {"Authorization": f"Bearer {self._get_access_token()}"}

    def _payload(self, **changes):
        payload = {
            "situacao": "feito",
            "quantidade_aplicada": 3.0,
            "baixar_estoque": False,
            "notas": "Confirmação via API",
        }
        payload.update(changes)
        return payload

    def test_get_trato_pendentes_sem_authorization_retorna_401(self):
        """Critério 1 (Spec 0054): a lista de trato exige token."""
        res = self.client.get("/trato/pendentes")
        self.assertEqual(res.status_code, 401)

    def test_get_trato_pendentes_retorna_ativos_e_estado_do_database(self):
        """Critérios 2–3: só planos ativos e o período vem do serviço existente."""
        active_id, _ = self._create_plan()
        inactive_id, _ = self._create_plan(active=False)
        expected = {
            item["id"]: item
            for item in db.get_pending_feedings(date.today())
        }

        res = self.client.get("/trato/pendentes", headers=self._headers())

        self.assertEqual(res.status_code, 200)
        items = {item["plano_id"]: item for item in res.json()}
        self.assertIn(active_id, items)
        self.assertNotIn(inactive_id, items)
        self.assertEqual(items[active_id]["lote_id"], str(expected[active_id]["lote_id"]))
        self.assertEqual(items[active_id]["lote_nome"], expected[active_id]["lote_name"])
        self.assertEqual(items[active_id]["produto"], expected[active_id]["product_name"])
        self.assertEqual(items[active_id]["quantidade"], expected[active_id]["quantity"])
        self.assertEqual(items[active_id]["unidade"], expected[active_id]["unit"])
        self.assertEqual(items[active_id]["frequencia"], expected[active_id]["frequency"])
        self.assertEqual(items[active_id]["insumo_id"], expected[active_id]["insumo_id"])
        self.assertEqual(
            items[active_id]["confirmado_no_periodo"],
            expected[active_id]["done_this_period"],
        )
        self.assertEqual(
            items[active_id]["ultima_confirmacao"],
            expected[active_id]["last_check"],
        )

    def test_post_confirmar_trato_grava_token_e_atualiza_pendencia(self):
        """Critérios 4–6: persiste, usa token e GET seguinte reconhece a confirmação."""
        plan_id, lote_id = self._create_plan()
        payload = self._payload(
            operator="operador_falso",
            lote_id="LOTE_FALSO",
            insumo_id=999999,
            quantity_unit="litro",
            check_date="2000-01-01",
        )

        post_res = self.client.post(
            f"/trato/{plan_id}/confirmar",
            json=payload,
            headers=self._headers(),
        )

        self.assertEqual(post_res.status_code, 201)
        self.assertEqual(post_res.json(), {"ok": True})
        with _conn() as con:
            row = con.execute(
                """SELECT plan_id, lote_id, check_date, status, actual_quantity, operator, notes
                   FROM feeding_checks ORDER BY id DESC LIMIT 1"""
            ).fetchone()
        self.assertEqual(row["plan_id"], plan_id)
        self.assertEqual(str(row["lote_id"]), lote_id)
        self.assertEqual(row["check_date"], date.today().isoformat())
        self.assertEqual(row["status"], "feito")
        self.assertEqual(row["actual_quantity"], 3.0)
        self.assertEqual(row["operator"], "testuser")
        self.assertNotEqual(row["operator"], "operador_falso")
        self.assertEqual(row["notes"], "Confirmação via API")

        pending_res = self.client.get("/trato/pendentes", headers=self._headers())
        item = next(item for item in pending_res.json() if item["plano_id"] == plan_id)
        self.assertTrue(item["confirmado_no_periodo"])

    def test_post_confirmar_trato_baixa_estoque_do_insumo_vinculado(self):
        """Critério 7: a baixa é delegada ao plano que tem insumo vinculado."""
        insumo_id = self._create_insumo(20.0)
        plan_id, _ = self._create_plan(insumo_id=insumo_id)

        res = self.client.post(
            f"/trato/{plan_id}/confirmar",
            json=self._payload(quantidade_aplicada=3.5, baixar_estoque=True),
            headers=self._headers(),
        )

        self.assertEqual(res.status_code, 201)
        with _conn() as con:
            stock = con.execute(
                "SELECT current_stock FROM insumos WHERE id=?", (insumo_id,)
            ).fetchone()[0]
        self.assertEqual(stock, 16.5)

    def test_post_confirmar_trato_sem_insumo_nao_baixa_estoque(self):
        """Critério 8: um ID de insumo enviado pelo cliente não pode forçar baixa."""
        unrelated_insumo_id = self._create_insumo(20.0)
        plan_id, _ = self._create_plan()

        res = self.client.post(
            f"/trato/{plan_id}/confirmar",
            json=self._payload(baixar_estoque=True, insumo_id=unrelated_insumo_id),
            headers=self._headers(),
        )

        self.assertEqual(res.status_code, 201)
        with _conn() as con:
            stock = con.execute(
                "SELECT current_stock FROM insumos WHERE id=?", (unrelated_insumo_id,)
            ).fetchone()[0]
        self.assertEqual(stock, 20.0)

    def test_post_confirmar_trato_inexistente_ou_inativo_retorna_404(self):
        """Critério 9: planos inexistentes e inativos não são confirmáveis."""
        inactive_id, _ = self._create_plan(active=False)
        headers = self._headers()

        missing_res = self.client.post("/trato/999999/confirmar", json=self._payload(), headers=headers)
        inactive_res = self.client.post(
            f"/trato/{inactive_id}/confirmar",
            json=self._payload(),
            headers=headers,
        )

        self.assertEqual(missing_res.status_code, 404)
        self.assertEqual(inactive_res.status_code, 404)

    def test_post_confirmar_trato_situacao_invalida_retorna_422(self):
        """Critério 10: a validação de situação é responsabilidade do Pydantic."""
        plan_id, _ = self._create_plan()

        res = self.client.post(
            f"/trato/{plan_id}/confirmar",
            json=self._payload(situacao="invalido"),
            headers=self._headers(),
        )

        self.assertEqual(res.status_code, 422)

    def test_backend_api_delega_sql_e_schema_nao_aceita_ids_do_cliente(self):
        """Critérios 11–12: a rota não duplica SQL nem recebe dados do plano."""
        source = inspect.getsource(main_mod)
        self.assertNotIn("INSERT INTO feeding_checks", source)
        self.assertNotIn("UPDATE insumos SET current_stock", source)
        for field in ("lote_id", "insumo_id", "quantity_unit"):
            self.assertNotIn(field, ConfirmarTratoInput.model_fields)


class TestIdempotency(BackendApiTestCase):
    """Testes de idempotência nos endpoints de escrita (Spec 0059 / ADR 0006)."""

    def test_idempotency_module_functions(self):
        """Valida o funcionamento direto de get_cached_response e store_response."""
        self.assertIsNone(get_cached_response(""))
        self.assertIsNone(get_cached_response(None))
        self.assertIsNone(get_cached_response("nonexistent-key"))

        store_response("test-key-1", "/test/endpoint", 201, {"msg": "ok", "id": 123})
        cached = get_cached_response("test-key-1")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["status_code"], 201)
        self.assertEqual(cached["response_body"], {"msg": "ok", "id": 123})

    def test_pesagem_idempotente_mesma_chave_nao_duplica_e_retorna_mesma_resposta(self):
        """Critério 2: POST /animais/{id}/pesagens com mesma Idempotency-Key gera 1 linha em weighings e respostas idênticas."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "pesagem-uuid-1"}
        animal = get_all_animals()[0]
        animal_id = animal["id"]
        payload = {"peso": 450.5, "data": "2026-08-25", "method": "manual", "notes": "Pesagem teste idempotencia"}

        res1 = self.client.post(f"/animais/{animal_id}/pesagens", json=payload, headers=headers)
        self.assertEqual(res1.status_code, 201)
        body1 = res1.json()

        # Segunda chamada com a mesma chave
        res2 = self.client.post(f"/animais/{animal_id}/pesagens", json=payload, headers=headers)
        self.assertEqual(res2.status_code, 201)
        body2 = res2.json()

        self.assertEqual(body1, body2)

        # Confere que existe apenas 1 pesagem gravada no banco
        with _conn() as con:
            rows = con.execute("SELECT * FROM weighings WHERE notes = 'Pesagem teste idempotencia'").fetchall()
            self.assertEqual(len(rows), 1)

    def test_medicamentos_idempotente_mesma_chave_nao_duplica_e_retorna_mesma_resposta(self):
        """Critério 3: POST /animais/{id}/medicamentos com mesma Idempotency-Key gera 1 linha em medications e respostas idênticas."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "med-uuid-1"}
        animal = get_all_animals()[0]
        animal_id = animal["id"]
        payload = {
            "medicamento": "Vacina Aftosa",
            "dose": 5.0,
            "unidade": "ml",
            "via": "subcutanea",
            "carencia_dias": 15,
            "data": "2026-08-25",
            "notas": "Dose de rotina idempotente",
        }

        res1 = self.client.post(f"/animais/{animal_id}/medicamentos", json=payload, headers=headers)
        self.assertEqual(res1.status_code, 201)
        body1 = res1.json()

        res2 = self.client.post(f"/animais/{animal_id}/medicamentos", json=payload, headers=headers)
        self.assertEqual(res2.status_code, 201)
        body2 = res2.json()

        self.assertEqual(body1, body2)

        with _conn() as con:
            rows = con.execute("SELECT * FROM medications WHERE notes = 'Dose de rotina idempotente'").fetchall()
            self.assertEqual(len(rows), 1)

    def test_movimentar_idempotente_mesma_chave_nao_duplica_e_retorna_mesma_resposta(self):
        """Critério 3: POST /animais/movimentar com mesma Idempotency-Key executa uma vez e retorna respostas idênticas."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "mov-uuid-1"}
        animais = get_all_animals()
        lotes = db.get_all_lotes()
        origem_id = lotes[0]["id"]
        destino_id = str(lotes[1]["id"])
        a1_id = animais[0]["id"]
        a2_id = animais[1]["id"]

        with _conn() as con:
            con.execute("UPDATE animals SET lote_id = ? WHERE id IN (?, ?)", (origem_id, a1_id, a2_id))

        payload = {
            "animal_ids": [a1_id, a2_id],
            "to_lote_id": destino_id,
            "movement_date": "2026-08-25",
            "reason": "Manejo rotina",
            "notes": "Idempotency test movimentar",
        }

        res1 = self.client.post("/animais/movimentar", json=payload, headers=headers)
        self.assertEqual(res1.status_code, 200)
        body1 = res1.json()

        res2 = self.client.post("/animais/movimentar", json=payload, headers=headers)
        self.assertEqual(res2.status_code, 200)
        body2 = res2.json()

        self.assertEqual(body1, body2)

        with _conn() as con:
            rows = con.execute("SELECT * FROM animal_movements WHERE notes = 'Idempotency test movimentar'").fetchall()
            self.assertEqual(len(rows), 2)  # 2 animais movidos na única execução

    def test_fotos_idempotente_mesma_chave_nao_duplica_e_retorna_mesma_resposta(self):
        """Critério 3: POST /animais/{id}/fotos com mesma Idempotency-Key gera 1 foto em animal_photos e respostas idênticas."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "foto-uuid-1"}
        animal = get_all_animals()[0]
        animal_id = animal["id"]
        animal_uuid = animal.get("uuid") or animal.get("animal_uuid")
        photo_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"

        res1 = self.client.post(
            f"/animais/{animal_id}/fotos",
            files={"arquivo": ("foto.jpg", photo_bytes, "image/jpeg")},
            data={"taken_date": "2026-08-25"},
            headers=headers,
        )
        self.assertEqual(res1.status_code, 201)
        body1 = res1.json()

        res2 = self.client.post(
            f"/animais/{animal_id}/fotos",
            files={"arquivo": ("foto.jpg", photo_bytes, "image/jpeg")},
            data={"taken_date": "2026-08-25"},
            headers=headers,
        )
        self.assertEqual(res2.status_code, 201)
        body2 = res2.json()

        self.assertEqual(body1, body2)
        self.assertEqual(body1["id"], body2["id"])

        with _conn() as con:
            rows = con.execute("SELECT * FROM animal_photos WHERE animal_uuid = ?", (animal_uuid,)).fetchall()
            self.assertEqual(len(rows), 1)

    def test_chaves_diferentes_fazem_duas_escritas_normais(self):
        """Critério 4: Duas chamadas com chaves diferentes fazem duas escritas normais."""
        token = self._get_access_token()
        animal = get_all_animals()[0]
        animal_id = animal["id"]
        payload = {"peso": 460.0, "data": "2026-08-25", "method": "manual", "notes": "Pesagem diff key"}

        res1 = self.client.post(
            f"/animais/{animal_id}/pesagens",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key-alpha"},
        )
        self.assertEqual(res1.status_code, 201)

        res2 = self.client.post(
            f"/animais/{animal_id}/pesagens",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key-beta"},
        )
        self.assertEqual(res2.status_code, 201)

        with _conn() as con:
            rows = con.execute("SELECT * FROM weighings WHERE notes = 'Pesagem diff key'").fetchall()
            self.assertEqual(len(rows), 2)

    def test_chamada_que_falha_nao_grava_chave_e_permite_tentativa_com_mesma_chave(self):
        """Critério 5: Chamada com erro (ex. 404) não grava a chave; retry com mesma chave executa normalmente."""
        token = self._get_access_token()
        animal = get_all_animals()[0]
        animal_id = animal["id"]
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "fail-then-retry-key"}
        payload = {"peso": 470.0, "data": "2026-08-25", "method": "manual"}

        # Primeira chamada falha com 404 (animal inexistente)
        res_fail = self.client.post("/animais/999999/pesagens", json=payload, headers=headers)
        self.assertEqual(res_fail.status_code, 404)

        # Confirma que a chave NÃO foi gravada em cache
        self.assertIsNone(get_cached_response("fail-then-retry-key"))

        # Segunda chamada com animal válido e a MESMA chave tem sucesso (201)
        res_success = self.client.post(f"/animais/{animal_id}/pesagens", json=payload, headers=headers)
        self.assertEqual(res_success.status_code, 201)

        # Agora a chave foi gravada com sucesso
        cached = get_cached_response("fail-then-retry-key")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["status_code"], 201)


class TestImportarPesagensCsvEndpoint(BackendApiTestCase):
    def _headers(self):
        return {"Authorization": f"Bearer {self._get_access_token()}"}

    def _count_weighings(self):
        with _conn() as con:
            return con.execute("SELECT COUNT(*) FROM weighings").fetchone()[0]

    def test_post_importar_csv_sem_token_retorna_401(self):
        """Critério 1: POST /pesagens/importar-csv sem Authorization devolve 401."""
        csv_content = b"animal,peso,data\nBR0001,450.0,2026-08-20\n"
        res = self.client.post(
            "/pesagens/importar-csv",
            files={"arquivo": ("pesagens.csv", csv_content, "text/csv")},
            data={"confirmar": "false"},
        )
        self.assertEqual(res.status_code, 401)

    def test_post_importar_csv_confirmar_false_ou_ausente_nao_grava_no_banco(self):
        """Critério 2: Com confirmar=false (ou ausente), nada é gravado no banco."""
        animals = [a for a in get_all_animals(status="ativo")]
        self.assertTrue(len(animals) >= 2)
        a1, a2 = animals[0]["id"], animals[1]["id"]

        csv_content = f"brinco;peso;data\n{a1};480,5;2026-08-20\n{a2};510,0;2026-08-21\n".encode("utf-8")

        count_before = self._count_weighings()

        # Sem confirmar (ausente)
        res1 = self.client.post(
            "/pesagens/importar-csv",
            files={"arquivo": ("pesagens.csv", csv_content, "text/csv")},
            headers=self._headers(),
        )
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["gravadas"], 0)
        self.assertEqual(len(data1["aceitas"]), 2)
        self.assertEqual(self._count_weighings(), count_before)

        # Com confirmar=false
        res2 = self.client.post(
            "/pesagens/importar-csv",
            files={"arquivo": ("pesagens.csv", csv_content, "text/csv")},
            data={"confirmar": "false"},
            headers=self._headers(),
        )
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["gravadas"], 0)
        self.assertEqual(len(data2["aceitas"]), 2)
        self.assertEqual(self._count_weighings(), count_before)

    def test_post_importar_csv_confirmar_true_grava_no_banco(self):
        """Critério 3: Com confirmar=true, novas linhas em weighings bate com gravadas == len(aceitas)."""
        animals = [a for a in get_all_animals(status="ativo")]
        self.assertTrue(len(animals) >= 2)
        a1, a2 = animals[0]["id"], animals[1]["id"]

        csv_content = f"brinco;peso;data\n{a1};480.5;2026-08-20\n{a2};510.0;2026-08-21\n".encode("utf-8")

        count_before = self._count_weighings()

        res = self.client.post(
            "/pesagens/importar-csv",
            files={"arquivo": ("balanca.csv", csv_content, "text/csv")},
            data={"confirmar": "true"},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["gravadas"], 2)
        self.assertEqual(data["gravadas"], len(data["aceitas"]))
        self.assertEqual(self._count_weighings(), count_before + 2)

    def test_post_importar_csv_resultado_identico_ao_parse_pesagens(self):
        """Critério 4: aceitas, rejeitadas e total_linhas conferem com services.importacao.parse_pesagens."""
        from services.importacao import parse_pesagens

        ativos = {a["id"] for a in get_all_animals(status="ativo")}
        csv_text = "animal,peso,data\nBR0001,450.0,2026-08-20\nINVALIDO,abc,2026-08-20\nINEXISTENTE_9999,500.0,2026-08-20\n"
        csv_bytes = csv_text.encode("utf-8")

        expected_parse = parse_pesagens(csv_text, ids_conhecidos=ativos)

        res = self.client.post(
            "/pesagens/importar-csv",
            files={"arquivo": ("teste.csv", csv_bytes, "text/csv")},
            data={"confirmar": "false"},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["total_linhas"], expected_parse["total_linhas"])
        self.assertEqual(len(data["rejeitadas"]), len(expected_parse["rejeitadas"]))
        for r_api, r_exp in zip(data["rejeitadas"], expected_parse["rejeitadas"]):
            self.assertEqual(r_api["linha"], r_exp["linha"])
            self.assertEqual(r_api["conteudo"], r_exp["conteudo"])
            self.assertEqual(r_api["motivo"], r_exp["motivo"])

        self.assertEqual(len(data["aceitas"]), len(expected_parse["aceitas"]))
        expected_sorted = sorted(expected_parse["aceitas"], key=lambda x: (x["animal_id"], x["data"]))
        for a_api, a_exp in zip(data["aceitas"], expected_sorted):
            self.assertEqual(a_api["animal_id"], a_exp["animal_id"])
            self.assertEqual(a_api["peso"], a_exp["peso"])
            self.assertEqual(a_api["data"], a_exp["data"])

    def test_post_importar_csv_alertas_severidade_alta(self):
        """Critério 5: Alertas batem com severidade alta de avaliar_pesagem."""
        animals = [a for a in get_all_animals(status="ativo")]
        a1, a2 = animals[0]["id"], animals[1]["id"]
        w2 = float(animals[1].get("current_weight") or 400.0)

        # a1 tem peso com variação absurda (> 20%), a2 tem peso idêntico ao atual (sem alerta de variação/GMD)
        csv_text = f"brinco,peso,data\n{a1},800.0,2026-08-20\n{a2},{w2:.1f},2026-08-20\n"
        res = self.client.post(
            "/pesagens/importar-csv",
            files={"arquivo": ("alertas.csv", csv_text.encode("utf-8"), "text/csv")},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        aceitas_map = {item["animal_id"]: item for item in data["aceitas"]}

        self.assertIn(a1, aceitas_map)
        self.assertIn(a2, aceitas_map)
        self.assertTrue(len(aceitas_map[a1]["alertas"]) >= 1)
        self.assertTrue(any("Variação" in alerta or "fora da faixa" in alerta for alerta in aceitas_map[a1]["alertas"]))
        self.assertEqual(len(aceitas_map[a2]["alertas"]), 0)

    def test_post_importar_csv_acumulo_historico_mesmo_animal(self):
        """Critério 6: Duas linhas do mesmo animal fazem a segunda enxergar a primeira no histórico."""
        animals = [a for a in get_all_animals(status="ativo")]
        a1 = animals[0]["id"]

        # Primeira pesagem em 2026-08-01 com 400kg. Segunda pesagem em 2026-08-02 com 800kg (GMD absurdo de 400kg/dia -> gera alerta)
        csv_text = f"brinco,peso,data\n{a1},400.0,2026-08-01\n{a1},800.0,2026-08-02\n"
        res = self.client.post(
            "/pesagens/importar-csv",
            files={"arquivo": ("duas_pesagens.csv", csv_text.encode("utf-8"), "text/csv")},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["aceitas"]), 2)

        # Primeira pesagem (400kg)
        self.assertEqual(data["aceitas"][0]["peso"], 400.0)
        # Segunda pesagem (800kg) enxergou os 400kg no histórico acumulado e gerou alerta de variação
        self.assertEqual(data["aceitas"][1]["peso"], 800.0)
        self.assertTrue(len(data["aceitas"][1]["alertas"]) >= 1)

    def test_post_importar_csv_operator_vem_do_token(self):
        """Critério 7: operator gravado em weighings é o usuário do token, ignorando campos extras."""
        animals = [a for a in get_all_animals(status="ativo")]
        a1 = animals[0]["id"]

        csv_text = f"brinco,peso,data\n{a1},460.0,2026-08-20\n"
        res = self.client.post(
            "/pesagens/importar-csv",
            files={"arquivo": ("pesagem_op.csv", csv_text.encode("utf-8"), "text/csv")},
            data={"confirmar": "true", "operator": "hacker_operator"},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 200)

        with _conn() as con:
            row = con.execute(
                "SELECT operator, notes FROM weighings WHERE animal_uuid = (SELECT uuid FROM animals WHERE id = ?) ORDER BY id DESC LIMIT 1",
                (a1,),
            ).fetchone()
            self.assertEqual(row["operator"], "testuser")
            self.assertIn("importado de pesagem_op.csv", row["notes"])

    def test_post_importar_csv_latin1_encoding(self):
        """Critério 8: Arquivo em latin-1 (cp1252) é decodificado e aceito corretamente."""
        animals = [a for a in get_all_animals(status="ativo")]
        a1 = animals[0]["id"]

        # Cabeçalho com acentuação em latin-1
        csv_latin1 = f"cabeçalho_não_usado\n{a1};475,5;2026-08-20\n".encode("latin-1")

        res = self.client.post(
            "/pesagens/importar-csv",
            files={"arquivo": ("balanca_latin1.txt", csv_latin1, "text/plain")},
            data={"confirmar": "false"},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["aceitas"]), 1)
        self.assertEqual(data["aceitas"][0]["animal_id"], a1)
        self.assertEqual(data["aceitas"][0]["peso"], 475.5)

    def test_post_importar_csv_validacoes_tamanho_e_extensao(self):
        """Critério 9: Arquivo > 1MB retorna 413, arquivo vazio ou extensão inválida retorna 422."""
        # Arquivo > 1 MB
        big_bytes = b"a,100,2026-08-20\n" * 70000  # > 1 MB
        res_big = self.client.post(
            "/pesagens/importar-csv",
            files={"arquivo": ("grande.csv", big_bytes, "text/csv")},
            headers=self._headers(),
        )
        self.assertEqual(res_big.status_code, 413)

        # Arquivo vazio
        res_empty = self.client.post(
            "/pesagens/importar-csv",
            files={"arquivo": ("vazio.csv", b"", "text/csv")},
            headers=self._headers(),
        )
        self.assertEqual(res_empty.status_code, 422)

        # Extensão inválida (.pdf)
        res_ext = self.client.post(
            "/pesagens/importar-csv",
            files={"arquivo": ("pesagens.pdf", b"qualquer conteudo", "application/pdf")},
            headers=self._headers(),
        )
        self.assertEqual(res_ext.status_code, 422)

    def test_backend_api_nao_duplica_sql_pesagens_importacao(self):
        """Critério 10: backend_api não contém SQL direto de escrita em weighings ou animals."""
        source = inspect.getsource(main_mod)
        self.assertNotIn("INSERT INTO weighings", source)
        self.assertNotIn("UPDATE animals SET current_weight", source)


class TestAlertasEndpoint(BackendApiTestCase):
    def _headers(self):
        return {"Authorization": f"Bearer {self._get_access_token()}"}

    def test_get_alertas_sem_token_retorna_401(self):
        """Critério 1 (Spec 0063): alertas exige autenticação."""
        response = self.client.get("/alertas")
        self.assertEqual(response.status_code, 401)

    def test_get_alertas_sem_itens_retorna_cinco_listas_vazias(self):
        """Critério 2: fazenda sem alerta mantém todas as categorias no contrato."""
        with patch.object(main_mod, "get_alert_animals", return_value={"sumidos": [], "carencia": [], "prontos": []}), \
             patch.object(main_mod, "check_low_stock", return_value=[]), \
             patch.object(main_mod, "get_low_performance", return_value=[]):
            response = self.client.get("/alertas", headers=self._headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "sumidos": [],
                "carencia": [],
                "prontos_para_abate": [],
                "estoque_baixo": [],
                "baixo_desempenho": [],
            },
        )

    def test_get_alertas_expoe_alertas_calculados_pelas_funcoes_existentes(self):
        """Critérios 2–7: a rota só adapta os cinco conjuntos já calculados."""
        today = date.today()
        lote_id = str(db.get_all_lotes()[0]["id"])

        def add_animal(animal_id, weight, target_weight, entry_date):
            db.add_animal(
                db.AnimalData(animal_id,
                "Nelore",
                "M",
                None,
                entry_date.isoformat(),
                weight,
                target_weight,
                0.0,
                lote_id,
                None,
            ))

        add_animal("ALERTA_SUMIDO", 410.0, 500.0, today - timedelta(days=31))
        add_animal("ALERTA_RECENTE", 410.0, 500.0, today)
        add_animal("ALERTA_CARENCIA", 410.0, 500.0, today)
        add_animal("ALERTA_CARENCIA_VENCIDA", 410.0, 500.0, today)
        add_animal("ALERTA_ABATE", 520.0, None, today)
        add_animal("ALERTA_NAO_ABATE", 499.0, None, today)
        add_animal("ALERTA_GMD", 300.0, 500.0, today - timedelta(days=20))
        add_animal("ALERTA_SEM_GMD", 300.0, 500.0, today)

        add_medication(
            "ALERTA_CARENCIA",
            "Medicamento com carência",
            1.0,
            "mL",
            "Subcutânea",
            4,
            today.isoformat(),
            applied_by="teste",
        )
        add_medication(
            "ALERTA_CARENCIA_VENCIDA",
            "Medicamento vencido",
            1.0,
            "mL",
            "Subcutânea",
            2,
            (today - timedelta(days=5)).isoformat(),
            applied_by="teste",
        )
        db.add_weighing("ALERTA_GMD", 308.0, today.isoformat())
        db.set_setting("gmd_meta", "0.5")
        with _conn() as con:
            stock_id = con.execute(
                """INSERT INTO insumos
                   (name, category, unit, current_stock, min_stock, cost_per_unit)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("Estoque no mínimo", "Ração", "kg", 5.0, 5.0, 1.0),
            ).lastrowid
            con.execute(
                """INSERT INTO insumos
                   (name, category, unit, current_stock, min_stock, cost_per_unit)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("Estoque suficiente", "Ração", "kg", 6.0, 5.0, 1.0),
            )
        db.clear_cache()

        response = self.client.get("/alertas", headers=self._headers())

        self.assertEqual(response.status_code, 200)
        alertas = response.json()
        sumidos = {item["animal_id"]: item for item in alertas["sumidos"]}
        carencia = {item["animal_id"]: item for item in alertas["carencia"]}
        prontos = {item["animal_id"]: item for item in alertas["prontos_para_abate"]}
        estoque = {item["insumo_id"]: item for item in alertas["estoque_baixo"]}
        desempenho = {item["animal_id"]: item for item in alertas["baixo_desempenho"]}

        self.assertEqual(sumidos["ALERTA_SUMIDO"]["dias_sem_pesagem"], 31)
        self.assertNotIn("ALERTA_RECENTE", sumidos)
        self.assertEqual(carencia["ALERTA_CARENCIA"]["dias_restantes"], 4)
        self.assertNotIn("ALERTA_CARENCIA_VENCIDA", carencia)
        self.assertEqual(prontos["ALERTA_ABATE"]["peso_alvo"], 500.0)
        self.assertNotIn("ALERTA_NAO_ABATE", prontos)
        self.assertEqual(estoque[stock_id]["estoque_atual"], 5.0)
        self.assertEqual(estoque[stock_id]["estoque_minimo"], 5.0)
        self.assertNotIn("Estoque suficiente", {item["nome"] for item in estoque.values()})
        self.assertEqual(desempenho["ALERTA_GMD"]["gmd"], 0.4)
        self.assertEqual(desempenho["ALERTA_GMD"]["meta_gmd"], 0.5)
        self.assertNotIn("ALERTA_SEM_GMD", desempenho)


class TestDispositivosAPI(BackendApiTestCase):
    def _headers(self):
        token = self._get_access_token()
        return {"Authorization": f"Bearer {token}"}

    def _criar_dispositivo(self, codigo_visual="BR-9001", tipo="brinco_visual", status="disponivel", lote="L01"):
        disp_id = f"disp-{codigo_visual}"
        with _conn() as con:
            con.execute(
                """INSERT INTO dispositivos
                   (id, codigo_visual, tipo, status, lote)
                   VALUES (?, ?, ?, ?, ?)""",
                (disp_id, codigo_visual, tipo, status, lote),
            )
        return disp_id

    def test_get_dispositivo_sem_token_retorna_401(self):
        """Critério 1: GET /dispositivos/{codigo} sem token -> 401."""
        res = self.client.get("/dispositivos/BR-9001")
        self.assertEqual(res.status_code, 401)

    def test_get_dispositivo_inexistente_retorna_404(self):
        """Critério 2: GET /dispositivos/{codigo} com código inexistente -> 404."""
        res = self.client.get("/dispositivos/CODIGO_INEXISTENTE_999", headers=self._headers())
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"], "Dispositivo não encontrado.")

    def test_get_dispositivo_inutilizado_retorna_404(self):
        """Critério 3: GET /dispositivos/{codigo} com dispositivo inutilizado -> 404."""
        self._criar_dispositivo(codigo_visual="BR-INUT-01", status="inutilizado")
        res = self.client.get("/dispositivos/BR-INUT-01", headers=self._headers())
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"], "Dispositivo não encontrado.")

    def test_get_dispositivo_valido_retorna_contrato_e_transicoes(self):
        """Critério 4: GET /dispositivos/{codigo} devolve os campos do contrato e transicoes_permitidas."""
        disp_id_disp = self._criar_dispositivo(codigo_visual="BR-DISP-01", status="disponivel", lote="LOTE-A")
        res_disp = self.client.get("/dispositivos/BR-DISP-01", headers=self._headers())
        self.assertEqual(res_disp.status_code, 200)
        data_disp = res_disp.json()

        self.assertEqual(data_disp["id"], disp_id_disp)
        self.assertEqual(data_disp["codigo_visual"], "BR-DISP-01")
        self.assertEqual(data_disp["tipo"], "brinco_visual")
        self.assertEqual(data_disp["status"], "disponivel")
        self.assertEqual(data_disp["lote"], "LOTE-A")

        transicoes_disp = data_disp["transicoes_permitidas"]
        destinos_disp = [t["para"] for t in transicoes_disp]
        # Destinos esperados a partir de "disponivel"
        esperados_disp = ["reservado", "aplicado", "perdido", "danificado", "inutilizado", "devolvido", "bloqueado_orgao"]
        for esperado in esperados_disp:
            self.assertIn(esperado, destinos_disp)
        self.assertNotIn("disponivel", destinos_disp)
        self.assertNotIn("recebido", destinos_disp)

        # Checa flags de motivo para transições específicas
        inut_meta = next(t for t in transicoes_disp if t["para"] == "inutilizado")
        self.assertTrue(inut_meta["exige_motivo"])
        self.assertFalse(inut_meta["exige_autorizacao"])

        res_meta = next(t for t in transicoes_disp if t["para"] == "reservado")
        self.assertFalse(res_meta["exige_motivo"])
        self.assertFalse(res_meta["exige_autorizacao"])

        # Teste com segundo estado de origem: "aplicado"
        disp_id_app = self._criar_dispositivo(codigo_visual="BR-APP-01", status="aplicado")
        res_app = self.client.get("/dispositivos/BR-APP-01", headers=self._headers())
        self.assertEqual(res_app.status_code, 200)
        data_app = res_app.json()
        destinos_app = [t["para"] for t in data_app["transicoes_permitidas"]]
        self.assertCountEqual(destinos_app, ["perdido", "danificado", "substituido", "inutilizado"])

    def test_post_status_transicao_permitida_sem_motivo(self):
        """Critério 5: POST /dispositivos/{id}/status com transição permitida -> 200 e muda o status."""
        disp_id = self._criar_dispositivo(codigo_visual="BR-MUD-01", status="disponivel")
        res = self.client.post(
            f"/dispositivos/{disp_id}/status",
            json={"novo_status": "reservado"},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"ok": True, "de": "disponivel", "para": "reservado"})

        # Confirma consultando novamente
        res_get = self.client.get("/dispositivos/BR-MUD-01", headers=self._headers())
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["status"], "reservado")

    def test_post_status_exige_motivo_sem_motivo_recusado_400(self):
        """Critério 6: POST /dispositivos/{id}/status para estado que exige motivo sem motivo -> 400 e não altera."""
        disp_id = self._criar_dispositivo(codigo_visual="BR-MOT-01", status="disponivel")
        res = self.client.post(
            f"/dispositivos/{disp_id}/status",
            json={"novo_status": "inutilizado", "motivo": None},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data["ok"])
        self.assertIn("exige motivo", data.get("motivo", ""))

        # Confirma que o dispositivo não mudou
        res_get = self.client.get("/dispositivos/BR-MOT-01", headers=self._headers())
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["status"], "disponivel")

    def test_post_status_exige_motivo_com_motivo_grava_e_retorna_200(self):
        """Critério 7: POST /dispositivos/{id}/status para estado com motivo -> 200 e grava motivo."""
        disp_id = self._criar_dispositivo(codigo_visual="BR-MOT-02", status="disponivel")
        res = self.client.post(
            f"/dispositivos/{disp_id}/status",
            json={"novo_status": "inutilizado", "motivo": "Brinco quebrou no aplicador"},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"ok": True, "de": "disponivel", "para": "inutilizado"})

        # Confirma no banco que motivo_inutilizacao e status foram gravados
        with _conn() as con:
            row = con.execute("SELECT status, motivo_inutilizacao, data_baixa FROM dispositivos WHERE id=?", (disp_id,)).fetchone()
            self.assertEqual(row["status"], "inutilizado")
            self.assertEqual(row["motivo_inutilizacao"], "Brinco quebrou no aplicador")
            self.assertIsNotNone(row["data_baixa"])

    def test_post_status_transicao_nao_permitida_retorna_400(self):
        """Critério 8: POST /dispositivos/{id}/status com transição não permitida -> 400 e indica definitivo."""
        disp_id = self._criar_dispositivo(codigo_visual="BR-DEF-01", status="inutilizado")
        res = self.client.post(
            f"/dispositivos/{disp_id}/status",
            json={"novo_status": "disponivel"},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data["ok"])
        self.assertIn("definitivo", data.get("motivo", ""))


class TestCriarLoteEndpoint(BackendApiTestCase):
    def _headers(self):
        token = self._get_access_token()
        return {"Authorization": f"Bearer {token}"}

    def test_post_lotes_sem_token_retorna_401(self):
        """Critério 1: POST /lotes sem token -> 401."""
        res = self.client.post(
            "/lotes",
            json={"id": "P99", "nome": "Piquete Novo", "area_ha": 15.0, "capacidade_ua": 20.0},
        )
        self.assertEqual(res.status_code, 401)

    def test_post_lotes_corpo_valido_retorna_201_e_aparece_em_get_lotes(self):
        """Critério 2: Corpo válido -> 201, lote aparece depois em GET /lotes."""
        headers = self._headers()
        payload = {
            "id": "P99",
            "nome": "Piquete Novo",
            "area_ha": 15.5,
            "capacidade_ua": 25.0,
            "observacoes": "Piquete reformado",
        }
        res = self.client.post("/lotes", json=payload, headers=headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(
            res.json(),
            {"id": "P99", "nome": "Piquete Novo", "capacidade_ua": 25.0, "animais_ativos": 0},
        )

        res_get = self.client.get("/lotes", headers=headers)
        self.assertEqual(res_get.status_code, 200)
        lote_ids = {l["id"]: l for l in res_get.json()}
        self.assertIn("P99", lote_ids)
        self.assertEqual(lote_ids["P99"]["nome"], "Piquete Novo")
        self.assertEqual(lote_ids["P99"]["capacidade_ua"], 25.0)
        self.assertEqual(lote_ids["P99"]["animais_ativos"], 0)

    def test_post_lotes_id_duplicado_retorna_409_e_nao_altera_existente(self):
        """Critério 3: id repetido de lote existente -> 409, não cria nem altera o existente."""
        headers = self._headers()
        # "P01" já existe no seed
        lote_original = db.get_lote("P01")
        self.assertIsNotNone(lote_original)
        nome_original = lote_original["name"]

        payload = {
            "id": "P01",
            "nome": "Nome Alterado Falso",
            "area_ha": 99.0,
            "capacidade_ua": 99.0,
        }
        res = self.client.post("/lotes", json=payload, headers=headers)
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["detail"], "Lote P01 já existe.")

        # Confirma que não foi alterado
        lote_depois = db.get_lote("P01")
        self.assertEqual(lote_depois["name"], nome_original)

    def test_post_lotes_validacao_schema_retorna_422(self):
        """Critério 4: id/nome vazio, ou area_ha/capacidade_ua negativo -> 422."""
        headers = self._headers()

        # id vazio
        res = self.client.post(
            "/lotes",
            json={"id": "", "nome": "Lote", "area_ha": 10.0, "capacidade_ua": 10.0},
            headers=headers,
        )
        self.assertEqual(res.status_code, 422)

        # nome vazio
        res = self.client.post(
            "/lotes",
            json={"id": "P98", "nome": "  ", "area_ha": 10.0, "capacidade_ua": 10.0},
            headers=headers,
        )
        self.assertEqual(res.status_code, 422)

        # area_ha negativo
        res = self.client.post(
            "/lotes",
            json={"id": "P98", "nome": "Lote", "area_ha": -5.0, "capacidade_ua": 10.0},
            headers=headers,
        )
        self.assertEqual(res.status_code, 422)

        # capacidade_ua negativo
        res = self.client.post(
            "/lotes",
            json={"id": "P98", "nome": "Lote", "area_ha": 10.0, "capacidade_ua": -2.0},
            headers=headers,
        )
        self.assertEqual(res.status_code, 422)

    def test_post_lotes_recebe_property_id_padrao(self):
        """Critério 5: Lote criado sem property_id recebe a propriedade padrão."""
        headers = self._headers()
        payload = {
            "id": "P88",
            "nome": "Piquete Padrão",
            "area_ha": 12.0,
            "capacidade_ua": 18.0,
        }
        res = self.client.post("/lotes", json=payload, headers=headers)
        self.assertEqual(res.status_code, 201)

        with _conn() as con:
            row = con.execute("SELECT property_id FROM lotes WHERE id='P88'").fetchone()
            prop_default = con.execute("SELECT id FROM properties ORDER BY created_at LIMIT 1").fetchone()
            self.assertIsNotNone(row["property_id"])
            self.assertEqual(row["property_id"], prop_default["id"])


class TestSalvarPerimetroLoteEndpoint(BackendApiTestCase):
    pontos_validos = [
        [-56.0000, -15.0000],
        [-55.9900, -15.0000],
        [-55.9900, -15.0100],
        [-56.0000, -15.0100],
    ]

    def _headers(self):
        token = self._get_access_token()
        return {"Authorization": f"Bearer {token}"}

    def _salvar_poligono_conhecido(self):
        poligono = json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [[-56.0, -15.0], [-55.99, -15.0], [-55.99, -15.01]]
                ],
            }
        )
        self.assertTrue(db.set_lote_poligono("P01", poligono))
        return poligono

    def test_post_perimetro_sem_token_retorna_401(self):
        """Critério 1: POST sem token é recusado."""
        res = self.client.post(
            "/lotes/P01/perimetro", json={"pontos": self.pontos_validos}
        )
        self.assertEqual(res.status_code, 401)

    def test_post_perimetro_lote_inexistente_retorna_404(self):
        """Critério 2: o lote precisa existir antes da gravação."""
        res = self.client.post(
            "/lotes/AUSENTE/perimetro",
            json={"pontos": self.pontos_validos},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 404)

    def test_post_perimetro_valido_grava_area_e_geometria(self):
        """Critérios 3 e 6: resposta e persistência usam a geometria existente."""
        res = self.client.post(
            "/lotes/P01/perimetro",
            json={"pontos": self.pontos_validos},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 200)

        anel = [tuple(ponto) for ponto in self.pontos_validos]
        resposta = res.json()
        self.assertEqual(resposta["ok"], True)
        self.assertAlmostEqual(resposta["area_ha"], area_hectares(anel), places=2)
        self.assertAlmostEqual(resposta["perimetro_m"], perimetro_metros(anel), places=6)

        lote = db.get_lote("P01")
        self.assertAlmostEqual(float(lote["area_ha"]), area_hectares(anel), places=2)
        self.assertEqual(json.loads(lote["poligono"])["coordinates"][0], self.pontos_validos)

    def test_post_perimetro_com_poucos_pontos_retorna_422_sem_gravar(self):
        """Critério 4: a validação existente recusa e preserva a geometria anterior."""
        poligono_anterior = self._salvar_poligono_conhecido()
        pontos_invalidos = [[-56.0, -15.0], [-55.99, -15.0]]

        res = self.client.post(
            "/lotes/P01/perimetro",
            json={"pontos": pontos_invalidos},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 422)
        self.assertEqual(
            res.json()["detail"], validar([tuple(ponto) for ponto in pontos_invalidos])
        )
        self.assertEqual(db.get_lote("P01")["poligono"], poligono_anterior)

    def test_post_perimetro_auto_interceptante_retorna_422_sem_gravar(self):
        """Critério 5: a gravata é recusada pela validação de geometria existente."""
        poligono_anterior = self._salvar_poligono_conhecido()
        gravata = [
            [-56.0, -15.0],
            [-55.99, -15.01],
            [-55.99, -15.0],
            [-56.0, -15.01],
        ]

        res = self.client.post(
            "/lotes/P01/perimetro",
            json={"pontos": gravata},
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["detail"], validar([tuple(ponto) for ponto in gravata]))
        self.assertEqual(db.get_lote("P01")["poligono"], poligono_anterior)


class TestRecomendacoesApi(BackendApiTestCase):

    def test_recomendacoes_sem_token_retorna_401(self):
        """Critério 1: GET /recomendacoes sem token -> 401."""
        res = self.client.get("/recomendacoes")
        self.assertEqual(res.status_code, 401)

    def test_recomendacoes_fazenda_limpa_retorna_200_lista_vazia(self):
        """Critério 2: Fazenda limpa sem pendências retorna 200 e lista vazia."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        with _conn() as con:
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("DELETE FROM feeding_checks")
            con.execute("DELETE FROM feeding_plans")
            con.execute("DELETE FROM medications")
            con.execute("DELETE FROM weighings")
            con.execute("DELETE FROM animal_movements")
            con.execute("DELETE FROM animal_photos")
            con.execute("DELETE FROM animal_costs")
            con.execute("DELETE FROM animal_events")
            con.execute("DELETE FROM animals")
            con.execute("DELETE FROM lotes")
            con.execute("DELETE FROM insumos")
            con.execute("PRAGMA foreign_keys = ON")
        db.clear_cache()

        res = self.client.get("/recomendacoes", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_recomendacoes_dispara_regras_com_paridade_direta(self):
        """Critério 3: Dispara regras reais e confere paridade com services.recomendacoes.avaliar."""
        from services.recomendacoes import avaliar as avaliar_recomendacoes

        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        with _conn() as con:
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("DELETE FROM feeding_checks")
            con.execute("DELETE FROM feeding_plans")
            con.execute("DELETE FROM medications")
            con.execute("DELETE FROM weighings")
            con.execute("DELETE FROM animal_movements")
            con.execute("DELETE FROM animal_photos")
            con.execute("DELETE FROM animal_costs")
            con.execute("DELETE FROM animal_events")
            con.execute("DELETE FROM animals")
            con.execute("DELETE FROM lotes")
            con.execute("DELETE FROM insumos")
            con.execute("PRAGMA foreign_keys = ON")

            con.execute(
                "INSERT INTO lotes (id, name, property_id, capacity_ua) VALUES (?, ?, ?, ?)",
                ("L01", "Pasto 1", "PROP1", 10.0),
            )
            con.execute(
                "INSERT INTO insumos (id, name, category, unit, current_stock, min_stock, cost_per_unit) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1, "Ração Confinamento", "nutricao", "kg", 10.0, 50.0, 2.5),
            )
            con.execute(
                "INSERT INTO feeding_plans (id, lote_id, product_name, insumo_id, quantity, unit, frequency, active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "L01", "Ração Confinamento", 1, 10.0, "kg", "diario", 1),
            )
            from repositories.animais import novo_uuid
            a_uuid = novo_uuid()
            con.execute(
                "INSERT INTO animals (uuid, id, breed, sex, birth_date, entry_date, entry_weight, current_weight, target_weight, status, lote_id, property_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (a_uuid, "BOV001", "Nelore", "M", "2024-01-01", "2024-01-01", 300.0, 310.0, 500.0, "ativo", "L01", "PROP1"),
            )
        d1 = (date.today() - timedelta(days=100)).isoformat()
        d2 = date.today().isoformat()
        db.add_weighing("BOV001", 300.0, d1)
        db.add_weighing("BOV001", 310.0, d2)
        db.clear_cache()

        contexto_direto = db.contexto_recomendacoes()
        esperado = avaliar_recomendacoes(contexto_direto)
        self.assertGreaterEqual(len(esperado), 2)

        res = self.client.get("/recomendacoes", headers=headers)
        self.assertEqual(res.status_code, 200)
        dados_api = res.json()
        self.assertEqual(dados_api, esperado)
        regras_retornadas = {r["regra"] for r in dados_api}
        self.assertIn("estoque_insuficiente", regras_retornadas)
        self.assertIn("gmd_abaixo_da_meta", regras_retornadas)
        for r in dados_api:
            self.assertIn("motivo", r)
            self.assertIn("dados", r)
            self.assertIn("acao", r)
            self.assertIn("titulo", r)
            self.assertIn("severidade", r)

    def test_database_contexto_recomendacoes_isolado(self):
        """Critério 4: database.contexto_recomendacoes devolve estrutura esperada sem a API."""
        ctx = db.contexto_recomendacoes()
        self.assertIsInstance(ctx, dict)
        chaves_esperadas = {"animais", "lotes", "insumos", "preco_arroba", "custo_por_arroba", "hoje"}
        self.assertEqual(set(ctx.keys()), chaves_esperadas)
        self.assertIsInstance(ctx["animais"], list)
        self.assertIsInstance(ctx["lotes"], list)
        self.assertIsInstance(ctx["insumos"], list)
        self.assertIsInstance(ctx["hoje"], str)

    def test_app_py_funcoes_relocadas_removidas(self):
        """Critério 5: app.py não define mais as funções relocadas."""
        import app as app_mod
        self.assertFalse(hasattr(app_mod, "_contexto_recomendacoes"))
        self.assertFalse(hasattr(app_mod, "_custo_medio_por_arroba"))
        self.assertFalse(hasattr(app_mod, "_consumo_diario_por_insumo"))

class TestEstoqueApi(BackendApiTestCase):
    """Testes para GET /estoque e GET /estoque/previsao (Spec 0073)."""

    def test_estoque_sem_token_retorna_401(self):
        """Critério 1: GET /estoque e GET /estoque/previsao sem token retornam 401."""
        res_inv = self.client.get("/estoque")
        self.assertEqual(res_inv.status_code, 401)

        res_prev = self.client.get("/estoque/previsao")
        self.assertEqual(res_prev.status_code, 401)

    def test_estoque_inventario_status_critico_baixo_ok(self):
        """Critério 2: GET /estoque com insumos em situação crítica, baixa e ok bate com o web."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        with _conn() as con:
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("DELETE FROM feeding_checks")
            con.execute("DELETE FROM feeding_plans")
            con.execute("DELETE FROM insumos")
            con.execute("PRAGMA foreign_keys = ON")

            # 1. Crítico: pct < 50% (40 / 100 = 40%)
            con.execute(
                "INSERT INTO insumos (id, name, category, unit, current_stock, min_stock, cost_per_unit) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1, "Milho Moído", "racao", "kg", 40.0, 100.0, 2.5),
            )
            # 2. Baixo: 50% <= pct < 100% (70 / 100 = 70%)
            con.execute(
                "INSERT INTO insumos (id, name, category, unit, current_stock, min_stock, cost_per_unit) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (2, "Farelo de Soja", "racao", "kg", 70.0, 100.0, 3.0),
            )
            # 3. OK: pct >= 100% (150 / 100 = 150%)
            con.execute(
                "INSERT INTO insumos (id, name, category, unit, current_stock, min_stock, cost_per_unit) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (3, "Sal Mineral", "mineral", "kg", 150.0, 100.0, 1.2),
            )
        db.clear_cache()

        res = self.client.get("/estoque", headers=headers)
        self.assertEqual(res.status_code, 200)
        itens = res.json()
        self.assertEqual(len(itens), 3)

        itens_por_id = {i["id"]: i for i in itens}

        # Verifica Insumo 1 (Crítico)
        i1 = itens_por_id[1]
        self.assertEqual(i1["nome"], "Milho Moído")
        self.assertEqual(i1["categoria"], "racao")
        self.assertEqual(i1["estoque_atual"], 40.0)
        self.assertEqual(i1["estoque_minimo"], 100.0)
        self.assertEqual(i1["unidade"], "kg")
        self.assertEqual(i1["custo_unitario"], 2.5)
        self.assertEqual(i1["valor_total"], 100.0)  # 40.0 * 2.5
        self.assertEqual(i1["status"], "critico")

        # Verifica Insumo 2 (Baixo)
        i2 = itens_por_id[2]
        self.assertEqual(i2["nome"], "Farelo de Soja")
        self.assertEqual(i2["categoria"], "racao")
        self.assertEqual(i2["estoque_atual"], 70.0)
        self.assertEqual(i2["estoque_minimo"], 100.0)
        self.assertEqual(i2["unidade"], "kg")
        self.assertEqual(i2["custo_unitario"], 3.0)
        self.assertEqual(i2["valor_total"], 210.0)  # 70.0 * 3.0
        self.assertEqual(i2["status"], "baixo")

        # Verifica Insumo 3 (OK)
        i3 = itens_por_id[3]
        self.assertEqual(i3["nome"], "Sal Mineral")
        self.assertEqual(i3["categoria"], "mineral")
        self.assertEqual(i3["estoque_atual"], 150.0)
        self.assertEqual(i3["estoque_minimo"], 100.0)
        self.assertEqual(i3["unidade"], "kg")
        self.assertEqual(i3["custo_unitario"], 1.2)
        self.assertEqual(i3["valor_total"], 180.0)  # 150.0 * 1.2
        self.assertEqual(i3["status"], "ok")

    def test_estoque_inventario_min_stock_zero_nao_quebra(self):
        """Critério 3: GET /estoque com min_stock=0 não quebra e retorna status ok."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        with _conn() as con:
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("DELETE FROM feeding_checks")
            con.execute("DELETE FROM feeding_plans")
            con.execute("DELETE FROM insumos")
            con.execute("PRAGMA foreign_keys = ON")

            con.execute(
                "INSERT INTO insumos (id, name, category, unit, current_stock, min_stock, cost_per_unit) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (10, "Vacina Aftosa", "vacina", "dose", 25.0, 0.0, 5.0),
            )
        db.clear_cache()

        res = self.client.get("/estoque", headers=headers)
        self.assertEqual(res.status_code, 200)
        dados = res.json()
        self.assertEqual(len(dados), 1)
        item = dados[0]
        self.assertEqual(item["id"], 10)
        self.assertEqual(item["estoque_minimo"], 0.0)
        self.assertEqual(item["status"], "ok")
        self.assertEqual(item["valor_total"], 125.0)

    def test_estoque_previsao_sem_plano_de_trato_retorna_sem_dados(self):
        """Critério 4: GET /estoque/previsao sem plano de trato ativo retorna urgencia sem_dados e datas null."""
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        with _conn() as con:
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("DELETE FROM feeding_checks")
            con.execute("DELETE FROM feeding_plans")
            con.execute("DELETE FROM insumos")
            con.execute("PRAGMA foreign_keys = ON")

            con.execute(
                "INSERT INTO insumos (id, name, category, unit, current_stock, min_stock, cost_per_unit) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (20, "Núcleo Mineral", "mineral", "kg", 80.0, 50.0, 4.0),
            )
        db.clear_cache()

        res = self.client.get("/estoque/previsao", headers=headers)
        self.assertEqual(res.status_code, 200)
        dados = res.json()
        self.assertEqual(len(dados), 1)
        prev = dados[0]
        self.assertEqual(prev["insumo_id"], 20)
        self.assertEqual(prev["nome"], "Núcleo Mineral")
        self.assertEqual(prev["urgencia"], "sem_dados")
        self.assertIsNone(prev["dias_restantes"])
        self.assertIsNone(prev["data_ruptura"])
        self.assertIsNone(prev["comprar_ate"])

    def test_estoque_previsao_com_plano_bate_com_prever_direto(self):
        """Critério 5: GET /estoque/previsao com plano ativo bate com chamada direta a prever."""
        from services.previsao_estoque import prever as prever_direto
        from services.previsao_estoque_adaptador import montar_insumos as montar_direto

        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        with _conn() as con:
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("DELETE FROM feeding_checks")
            con.execute("DELETE FROM feeding_plans")
            con.execute("DELETE FROM lotes")
            con.execute("DELETE FROM insumos")
            con.execute("PRAGMA foreign_keys = ON")

            con.execute(
                "INSERT INTO lotes (id, name, property_id, capacity_ua) VALUES (?, ?, ?, ?)",
                ("L01", "Pasto 1", "PROP1", 10.0),
            )
            con.execute(
                "INSERT INTO insumos (id, name, category, unit, current_stock, min_stock, cost_per_unit) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1, "Ração Confinamento", "racao", "kg", 100.0, 20.0, 2.0),
            )
            con.execute(
                "INSERT INTO feeding_plans (id, lote_id, product_name, insumo_id, quantity, unit, frequency, active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "L01", "Ração Confinamento", 1, 10.0, "kg", "diario", 1),
            )
        db.clear_cache()

        # Prova real independente
        insumos = db.get_all_insumos()
        consumo = db._consumo_diario_por_insumo()
        montados = montar_direto(insumos, consumo)
        esperado_prever = prever_direto(montados, date.today().isoformat())
        self.assertEqual(len(esperado_prever), 1)

        res = self.client.get("/estoque/previsao", headers=headers)
        self.assertEqual(res.status_code, 200)
        dados = res.json()
        self.assertEqual(len(dados), 1)

        api_item = dados[0]
        dir_item = esperado_prever[0]
        self.assertEqual(api_item["insumo_id"], dir_item["id"])
        self.assertEqual(api_item["nome"], dir_item["nome"])
        self.assertEqual(api_item["dias_restantes"], dir_item["dias_restantes"])
        self.assertEqual(api_item["data_ruptura"], dir_item["data_ruptura"])
        self.assertEqual(api_item["comprar_ate"], dir_item["comprar_ate"])
        self.assertEqual(api_item["urgencia"], dir_item["urgencia"])

    def test_database_previsao_e_inventario_isolados(self):
        """Critério 6: database.previsao_estoque() e inventario_estoque() funcionam isolados."""
        prev = db.previsao_estoque()
        self.assertIsInstance(prev, list)
        if prev:
            p = prev[0]
            self.assertIn("id", p)
            self.assertIn("nome", p)
            self.assertIn("dias_restantes", p)
            self.assertIn("data_ruptura", p)
            self.assertIn("comprar_ate", p)
            self.assertIn("urgencia", p)

        inv = db.inventario_estoque()
        self.assertIsInstance(inv, list)
        if inv:
            i = inv[0]
            self.assertIn("id", i)
            self.assertIn("nome", i)
            self.assertIn("categoria", i)
            self.assertIn("estoque_atual", i)
            self.assertIn("estoque_minimo", i)
            self.assertIn("unidade", i)
            self.assertIn("custo_unitario", i)
            self.assertIn("valor_total", i)
            self.assertIn("status", i)

    def test_app_py_previsao_estoque_relocada(self):
        """Critério 7: app.py não define mais _previsao_estoque e database define previsao_estoque."""
        import app as app_mod
        self.assertFalse(hasattr(app_mod, "_previsao_estoque"))
        self.assertTrue(hasattr(db, "previsao_estoque"))
        self.assertTrue(hasattr(db, "inventario_estoque"))


class TestSecurityAndIsolation(unittest.TestCase):

    def test_secret_inseguro_rejeitado(self):
        """Critério de segurança: Secret com menos de 32 caracteres levanta erro."""
        with patch.dict(os.environ, {"AGROTOP_API_SECRET": "curto"}):
            with self.assertRaises(RuntimeError):
                get_secret_key()

    def test_sem_duplicacao_de_logica_de_negocio(self):
        """Critério 6 (0044), Critério 7 (0048), Critério 8 (0050/0052): Nenhum cálculo de negócio ou SQL duplicado dentro de backend_api/."""
        # backend_api reutiliza por import, não define novas fórmulas de zootecnia
        forbidden_funcs = [
            "calculate_gmd",
            "calculate_gmd_total",
            "estimate_weight_by_measurement",
            "register_sale",
            "move_animals_bulk",
            "add_photo",
        ]
        defined_funcs = [name for name, _ in inspect.getmembers(main_mod, inspect.isfunction)
                         if inspect.getmodule(_) == main_mod]

        for forbidden in forbidden_funcs:
            self.assertNotIn(forbidden, defined_funcs, f"{forbidden} não deve ser reimplementada em backend_api")


if __name__ == "__main__":
    unittest.main()

