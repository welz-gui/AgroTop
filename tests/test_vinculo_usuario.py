"""Usuário vinculado à organização e à propriedade (D1 do plano de rastreabilidade).

`users` não dizia a que organização nem propriedade a pessoa pertence, então a
sessão, o JWT e a auditoria não sabiam "quem é de quem". O vínculo é opcional
(NULL = sem vínculo / todas as propriedades) e validado: propriedade de outra
organização é recusada.
"""

import os
import sqlite3
import tempfile
import unittest

import jwt

import database as db
from backend_api.config import TOKEN_ALGORITHM, TOKEN_ISSUER, get_secret_key
from repositories import eventos, propriedades
from tests.test_backend_api import BackendApiTestCase
from tests.test_regras_negocio import BaseRegras


def _usuario(username):
    with db._conn() as con:
        r = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(r) if r else None


class TestVinculoDeUsuario(BaseRegras):
    def setUp(self):
        super().setUp()
        with db._conn() as con:
            self.org1 = con.execute("SELECT id FROM organizacoes").fetchone()["id"]
            self.prop1 = con.execute("SELECT id FROM properties").fetchone()["id"]

    def _segunda_organizacao(self):
        oid = propriedades.criar_organizacao("Organização B")
        prid = propriedades.criar_produtor(oid, "Produtor B")
        pid = propriedades.criar_propriedade(propriedades.PropriedadeCreate(produtor_id=prid, nome="Fazenda B"))
        return oid, pid

    def test_sem_vinculo_informado_usa_a_unica_organizacao_do_banco(self):
        db.add_user("u1", "Senha123!", "Um")
        u = _usuario("u1")
        self.assertEqual((u["organizacao_id"], u["property_id"]), (self.org1, None))

    def test_com_varias_organizacoes_e_sem_vinculo_fica_sem_vinculo(self):
        self._segunda_organizacao()
        db.add_user("u2", "Senha123!", "Dois")
        u = _usuario("u2")
        self.assertEqual((u["organizacao_id"], u["property_id"]), (None, None))

    def test_propriedade_sem_organizacao_herda_a_da_propriedade(self):
        oid, pid = self._segunda_organizacao()
        db.add_user("u3", "Senha123!", "Três", property_id=pid)
        u = _usuario("u3")
        self.assertEqual((u["organizacao_id"], u["property_id"]), (oid, pid))

    def test_propriedade_de_outra_organizacao_e_recusada(self):
        _, pid_b = self._segunda_organizacao()
        with self.assertRaises(ValueError) as ctx:
            db.add_user("u4", "Senha123!", "Quatro", organizacao_id=self.org1, property_id=pid_b)
        self.assertIn("não pertence", str(ctx.exception))
        self.assertIsNone(_usuario("u4"))

    def test_organizacao_ou_propriedade_inexistente_e_recusada(self):
        with self.assertRaises(ValueError):
            db.add_user("u5", "Senha123!", "Cinco", organizacao_id="nao-existe")
        with self.assertRaises(ValueError):
            db.add_user("u5", "Senha123!", "Cinco", property_id="nao-existe")

    def test_definir_e_limpar_vinculo(self):
        db.add_user("u6", "Senha123!", "Seis")
        uid = _usuario("u6")["id"]

        db.definir_vinculo_usuario(uid, self.org1, self.prop1)
        self.assertEqual((_usuario("u6")["organizacao_id"], _usuario("u6")["property_id"]),
                         (self.org1, self.prop1))

        db.definir_vinculo_usuario(uid, None, None)
        self.assertEqual((_usuario("u6")["organizacao_id"], _usuario("u6")["property_id"]), (None, None))

    def test_definir_vinculo_de_usuario_inexistente_e_recusado(self):
        with self.assertRaises(ValueError):
            db.definir_vinculo_usuario(999999, self.org1)

    def test_leituras_de_usuario_trazem_o_vinculo(self):
        db.add_user("u7", "Senha123!", "Sete", property_id=self.prop1)
        uid = _usuario("u7")["id"]

        self.assertEqual(db.get_user(uid)["property_id"], self.prop1)
        lista = {u["username"]: u for u in db.get_all_users()}
        self.assertEqual(lista["u7"]["organizacao_nome"], "Organização principal")
        self.assertTrue(lista["u7"]["property_nome"])
        token = db.create_session(uid)
        self.assertEqual(db.get_session_user(token)["organizacao_id"], self.org1)
        self.assertEqual(db.verify_login("u7", "Senha123!")["organizacao_id"], self.org1)

    def test_backfill_liga_usuarios_sem_vinculo_so_com_uma_organizacao(self):
        with db._conn() as con:
            con.execute("INSERT INTO users (username,password_hash,name,role) VALUES ('velho','x','V','operator')")
            self.assertEqual(propriedades._backfill_user_org(con), 1)
            self.assertEqual(con.execute("SELECT organizacao_id FROM users WHERE username='velho'")
                             .fetchone()["organizacao_id"], self.org1)
            self.assertEqual(propriedades._backfill_user_org(con), 0, "idempotente")

        self._segunda_organizacao()
        with db._conn() as con:
            con.execute("INSERT INTO users (username,password_hash,name,role) VALUES ('novo','x','N','operator')")
            self.assertEqual(propriedades._backfill_user_org(con), 0)
            self.assertIsNone(con.execute("SELECT organizacao_id FROM users WHERE username='novo'")
                              .fetchone()["organizacao_id"])


class TestAuditoriaComVinculo(BaseRegras):
    def setUp(self):
        super().setUp()
        with db._conn() as con:
            self.org1 = con.execute("SELECT id FROM organizacoes").fetchone()["id"]
            self.prop1 = con.execute("SELECT id FROM properties").fetchone()["id"]
        db.add_user("auditor", "Senha123!", "Auditor", property_id=self.prop1)

    def _ultima(self):
        with db._conn() as con:
            return dict(con.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone())

    def test_auditoria_grava_o_vinculo_do_autor(self):
        eventos.auditar("teste", usuario="auditor", entidade="x", entidade_id="1")
        a = self._ultima()
        self.assertEqual((a["organizacao_id"], a["property_id"]), (self.org1, self.prop1))

    def test_usuario_que_nao_e_login_fica_sem_vinculo(self):
        eventos.auditar("teste", usuario="Fulano de Tal", entidade="x", entidade_id="1")
        a = self._ultima()
        self.assertEqual((a["organizacao_id"], a["property_id"]), (None, None))

    def test_vinculo_explicito_prevalece(self):
        eventos.auditar("teste", usuario="auditor", organizacao_id="org-x", property_id="prop-x")
        a = self._ultima()
        self.assertEqual((a["organizacao_id"], a["property_id"]), ("org-x", "prop-x"))

    def test_edicao_direta_do_admin_grava_o_vinculo_do_autor(self):
        db.admin_apply_changes("fornecedores", [], [{"name": "F"}], [], usuario="auditor")
        a = self._ultima()
        self.assertEqual(a["acao"], "admin_inclusao")
        self.assertEqual((a["organizacao_id"], a["property_id"]), (self.org1, self.prop1))


class TestMigracaoDeBancoAntigo(unittest.TestCase):
    def test_init_db_acrescenta_as_colunas_em_banco_criado_antes(self):
        d = tempfile.mkdtemp()
        caminho = os.path.join(d, "antigo.db")
        con = sqlite3.connect(caminho)
        con.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'operator');
            INSERT INTO users (username,password_hash,name,role) VALUES ('legado','x','Legado','operator');
            CREATE TABLE audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT,
                ocorrido_em TEXT NOT NULL, dispositivo TEXT, ip TEXT, acao TEXT NOT NULL, entidade TEXT,
                entidade_id TEXT, registro_anterior TEXT, registro_posterior TEXT, motivo TEXT,
                autorizacao TEXT, origem TEXT NOT NULL DEFAULT 'web', protocolo_externo TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')));
        """)
        con.commit()
        con.close()

        db.configurar_sqlite(caminho)
        db.init_db(forcar=True)

        with db._conn() as c:
            ucols = {r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()}
            acols = {r["name"] for r in c.execute("PRAGMA table_info(audit_logs)").fetchall()}
            legado = dict(c.execute("SELECT * FROM users WHERE username='legado'").fetchone())
            org = c.execute("SELECT id FROM organizacoes").fetchone()["id"]
        self.assertTrue({"organizacao_id", "property_id"} <= ucols)
        self.assertTrue({"organizacao_id", "property_id"} <= acols)
        self.assertEqual(legado["organizacao_id"], org, "backfill com uma só organização")


class TestVinculoNoJwt(BackendApiTestCase):
    def _claims(self, token):
        return jwt.decode(token, get_secret_key(), algorithms=[TOKEN_ALGORITHM], issuer=TOKEN_ISSUER)

    def test_login_carrega_o_vinculo_no_token_e_na_resposta(self):
        with db._conn() as con:
            org = con.execute("SELECT id FROM organizacoes").fetchone()["id"]
            prop = con.execute("SELECT id FROM properties").fetchone()["id"]
            con.execute("UPDATE users SET organizacao_id=?, property_id=? WHERE username='testuser'", (org, prop))

        res = self.client.post("/auth/login", json={"username": "testuser", "password": "SenhaForte123!"})

        self.assertEqual(res.status_code, 200)
        corpo = res.json()
        self.assertEqual((corpo["user"]["organizacao_id"], corpo["user"]["property_id"]), (org, prop))
        claims = self._claims(corpo["access_token"])
        self.assertEqual((claims["organizacao_id"], claims["property_id"]), (org, prop))

    def test_refresh_mantem_o_vinculo(self):
        with db._conn() as con:
            org = con.execute("SELECT id FROM organizacoes").fetchone()["id"]
            con.execute("UPDATE users SET organizacao_id=? WHERE username='testuser'", (org,))
        login = self.client.post("/auth/login", json={"username": "testuser", "password": "SenhaForte123!"}).json()

        novo = self.client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]}).json()

        claims = self._claims(novo["access_token"])
        self.assertEqual(claims["organizacao_id"], org)
        self.assertIsNone(claims["property_id"])

    def test_usuario_sem_vinculo_recebe_claims_nulos(self):
        claims = self._claims(self._get_access_token())
        self.assertIn("organizacao_id", claims)
        self.assertIsNone(claims["organizacao_id"])
        self.assertIsNone(claims["property_id"])


if __name__ == "__main__":
    unittest.main()
