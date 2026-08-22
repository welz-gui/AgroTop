"""Testes da API Backend em FastAPI (Spec 0044 v2 + Spec 0048 + Spec 0050 + Spec 0052).

Valida autenticação JWT, rate limiting, refresh tokens revogáveis,
endpoints essenciais de dados, registro de pesagens, movimentação entre piquetes,
sanidade/carência e fotos dos animais.
"""

import inspect
import io
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
from repositories.sanidade import add_medication, get_withdrawal_end


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
            },
        )

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
