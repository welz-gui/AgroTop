"""A edição direta da tela de administração deixa trilha em `audit_logs`.

Corrigir um peso ou apagar um fornecedor reescrevia o dado sem registro de quem
mexeu, quando e o que havia antes. Agora cada exclusão, edição e inclusão grava
uma linha (`admin_exclusao`, `admin_edicao`, `admin_inclusao`) na mesma transação.
"""

import json
import unittest
from datetime import timedelta
from unittest.mock import patch

import database as db
from repositories import eventos
from repositories.pesagens import WeighingCreate, add_weighing
from tests.test_regras_negocio import BaseRegras, HOJE


def _trilha(acao=None, entidade=None):
    with db._conn() as con:
        sql, args = "SELECT * FROM audit_logs WHERE acao LIKE 'admin_%'", []
        if acao:
            sql += " AND acao=?"; args.append(acao)
        if entidade:
            sql += " AND entidade=?"; args.append(entidade)
        rows = [dict(r) for r in con.execute(sql + " ORDER BY id", args).fetchall()]
    for r in rows:
        for k in ("registro_anterior", "registro_posterior"):
            r[k] = json.loads(r[k]) if r[k] else None
    return rows


class TestAdminAuditoria(BaseRegras):
    def _pesagem(self):
        self.animal("A1")
        add_weighing(WeighingCreate(
            animal_id="A1", weight=410.0, weigh_date=(HOJE - timedelta(days=1)).isoformat(), operator="t"))
        with db._conn() as con:
            return dict(con.execute("SELECT * FROM weighings").fetchone())

    def test_edicao_registra_so_os_campos_que_mudaram_com_antes_e_depois(self):
        p = self._pesagem()

        db.admin_apply_changes("weighings", [dict(p, weight=415.0)], [], [], usuario="admin1")

        (t,) = _trilha("admin_edicao")
        self.assertEqual(t["entidade"], "weighings")
        self.assertEqual(t["entidade_id"], str(p["id"]))
        self.assertEqual(t["usuario"], "admin1")
        self.assertEqual(t["registro_anterior"], {"weight": 410.0})
        self.assertEqual(t["registro_posterior"], {"weight": 415.0})

    def test_edicao_sem_mudanca_nao_gera_trilha(self):
        p = self._pesagem()
        db.admin_apply_changes("weighings", [dict(p)], [], [], usuario="admin1")
        self.assertEqual(_trilha("admin_edicao"), [])

    def test_inclusao_registra_os_valores_e_o_id_gerado(self):
        p = self._pesagem()
        nova = {"animal_uuid": p["animal_uuid"], "weight": 420.0,
                "weigh_date": HOJE.isoformat(), "method": "pesado"}

        db.admin_apply_changes("weighings", [], [nova], [], usuario="admin1")

        (t,) = _trilha("admin_inclusao")
        self.assertEqual(t["registro_posterior"]["weight"], 420.0)
        self.assertEqual(t["usuario"], "admin1")
        self.assertIsNotNone(t["entidade_id"])
        self.assertIsNone(t["registro_anterior"])

    def test_exclusao_guarda_a_linha_inteira(self):
        db.admin_apply_changes("fornecedores", [], [{"name": "Fazenda Boa", "city": "Lajeado"}], [])
        with db._conn() as con:
            fid = con.execute("SELECT id FROM fornecedores WHERE name='Fazenda Boa'").fetchone()["id"]

        db.admin_apply_changes("fornecedores", [], [], [fid], usuario="admin1")

        (t,) = _trilha("admin_exclusao")
        self.assertEqual(t["entidade_id"], str(fid))
        self.assertEqual(t["registro_anterior"]["name"], "Fazenda Boa")
        self.assertEqual(t["registro_anterior"]["city"], "Lajeado")
        self.assertIsNone(t["registro_posterior"])

    def test_hash_de_senha_nao_vai_para_a_trilha_mas_a_mudanca_fica_registrada(self):
        with db._conn() as con:
            con.execute("INSERT INTO users (username, password_hash, name, role) "
                        "VALUES ('op1', 'HASH-ANTIGO', 'Operador', 'operator')")
            u = dict(con.execute("SELECT * FROM users WHERE username='op1'").fetchone())

        db.admin_apply_changes("users", [dict(u, password_hash="SEGREDO-NOVO", name="Novo Nome")], [], [],
                               usuario="admin1")

        (t,) = _trilha("admin_edicao", "users")
        self.assertEqual(t["registro_anterior"]["password_hash"], "[oculto]")
        self.assertEqual(t["registro_posterior"]["password_hash"], "[oculto]")
        self.assertEqual(t["registro_posterior"]["name"], "Novo Nome")
        with db._conn() as con:
            bruto = " ".join(str(v) for r in con.execute("SELECT * FROM audit_logs").fetchall() for v in dict(r).values())
        self.assertNotIn("SEGREDO-NOVO", bruto)
        self.assertNotIn(u["password_hash"], bruto)

    def test_configuracao_com_chave_secreta_fica_oculta_e_as_demais_nao(self):
        db.admin_apply_changes("settings", [], [{"key": "openrouter_api_key", "value": "sk-123"}], [], usuario="a")
        db.admin_apply_changes("settings", [], [{"key": "preco_arroba", "value": "310"}], [], usuario="a")
        db.admin_apply_changes("settings", [{"key": "openrouter_api_key", "value": "sk-456"}], [], [], usuario="a")

        por_chave = {t["registro_posterior"].get("key"): t for t in _trilha("admin_inclusao", "settings")}
        self.assertEqual(por_chave["openrouter_api_key"]["registro_posterior"]["value"], "[oculto]")
        self.assertEqual(por_chave["preco_arroba"]["registro_posterior"]["value"], "310")
        edicao = _trilha("admin_edicao", "settings")[0]
        self.assertEqual(edicao["registro_anterior"]["value"], "[oculto]")
        self.assertEqual(edicao["registro_posterior"]["value"], "[oculto]")
        with db._conn() as con:
            bruto = " ".join(str(v) for r in con.execute("SELECT * FROM audit_logs").fetchall() for v in dict(r).values())
        self.assertNotIn("sk-123", bruto)
        self.assertNotIn("sk-456", bruto)

    def test_se_a_trilha_falhar_a_alteracao_nao_e_gravada(self):
        p = self._pesagem()

        with patch.object(eventos, "auditar_em", side_effect=RuntimeError("falha na trilha")):
            with self.assertRaises(RuntimeError):
                db.admin_apply_changes("weighings", [dict(p, weight=999.0)], [], [], usuario="admin1")

        with db._conn() as con:
            self.assertEqual(con.execute("SELECT weight FROM weighings").fetchone()["weight"], 410.0)

    def test_exclusao_recusada_nao_gera_trilha(self):
        p = self._pesagem()
        with self.assertRaises(db.ExclusaoNaoPermitida):
            db.admin_apply_changes("weighings", [], [], [p["id"]], usuario="admin1")
        self.assertEqual(_trilha(), [])

    def test_a_trilha_aparece_em_eventos_trilha_por_entidade(self):
        p = self._pesagem()
        db.admin_apply_changes("weighings", [dict(p, weight=415.0)], [], [], usuario="admin1")

        linhas = eventos.trilha(entidade="weighings", entidade_id=str(p["id"]))

        self.assertEqual([l["acao"] for l in linhas], ["admin_edicao"])


if __name__ == "__main__":
    unittest.main()
