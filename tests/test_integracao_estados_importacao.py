"""Integração das funções puras entregues por agentes ao app (ROADMAP R31).

Duas funções estavam prontas e testadas, mas não ligadas a nada:
`services.estados_animal.transicao_permitida` e `services.importacao.parse_pesagens`.
Testes de unidade delas já existem; estes aqui travam a **ligação** — que é onde
integração costuma quebrar sem ninguém notar.

O que importa: `update_animal_status` é o único funil de mudança de status, então
a regra do PNIB §14.2 vale para todos os chamadores, inclusive os futuros.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402


class BaseIntegracao(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "integracao.db"))
        db.init_db()
        db.clear_cache()

    def _animal(self, animal_id):
        con = sqlite3.connect(db.DB_PATH)
        con.row_factory = sqlite3.Row
        try:
            r = con.execute("SELECT * FROM animals WHERE id=?", (animal_id,)).fetchone()
            return dict(r) if r else None
        finally:
            con.close()

    def _qualquer_ativo(self):
        return db.get_all_animals(status="ativo")[0]["id"]


class TestTransicaoLivre(BaseIntegracao):
    """O caminho cotidiano não pode ter ficado mais difícil."""

    def test_ativo_para_vendido_nao_exige_nada(self):
        a = self._qualquer_ativo()
        r = db.update_animal_status(a, "vendido")
        self.assertTrue(r["ok"], r)
        self.assertFalse(r["exige_autorizacao"])
        self.assertEqual(self._animal(a)["status"], "vendido")

    def test_carencia_para_ativo_nao_exige_nada(self):
        """É o caminho de `refresh_carencia_status`, que roda sozinho."""
        a = self._qualquer_ativo()
        db.update_animal_status(a, "carencia")
        db.clear_cache()
        r = db.update_animal_status(a, "ativo")
        self.assertTrue(r["ok"], r)
        self.assertEqual(self._animal(a)["status"], "ativo")

    def test_refresh_carencia_continua_funcionando(self):
        """Guarda de regressão: a rotina automática não passa autorização.

        Escolhe um animal **sem carência pendente** — o seed medica alguns, e
        para esses o correto é justamente NÃO reverter.
        """
        sem_carencia = [a["id"] for a in db.get_all_animals(status="ativo")
                        if db.get_withdrawal_end(a["id"]) is None]
        self.assertTrue(sem_carencia, "seed não tem animal sem carência")
        a = sem_carencia[0]

        db.update_animal_status(a, "carencia")
        db.clear_cache()
        db.refresh_carencia_status()
        self.assertEqual(self._animal(a)["status"], "ativo")

    def test_refresh_carencia_nao_libera_quem_ainda_esta_em_carencia(self):
        """O outro lado da regra: carência no futuro segura o animal."""
        com_carencia = [a["id"] for a in db.get_all_animals(status="ativo")
                        if db.get_withdrawal_end(a["id"]) is not None]
        if not com_carencia:
            self.skipTest("seed não tem animal medicado")
        a = com_carencia[0]

        db.update_animal_status(a, "carencia")
        db.clear_cache()
        db.refresh_carencia_status()
        self.assertEqual(self._animal(a)["status"], "carencia",
                         "animal com carência vigente foi liberado")


class TestTransicaoSensivel(BaseIntegracao):
    """Sair de estado final é o que o §14.2 protege."""

    def _vender(self):
        a = self._qualquer_ativo()
        db.update_animal_status(a, "vendido")
        db.clear_cache()
        return a

    def test_vendido_para_ativo_e_recusado_sem_autorizacao(self):
        a = self._vender()
        r = db.update_animal_status(a, "ativo")
        self.assertFalse(r["ok"])
        self.assertTrue(r["exige_autorizacao"])
        self.assertEqual(self._animal(a)["status"], "vendido",
                         "status mudou apesar de a transição ter sido recusada")

    def test_vendido_para_ativo_e_recusado_com_autorizacao_mas_sem_justificativa(self):
        a = self._vender()
        r = db.update_animal_status(a, "ativo", tem_autorizacao=True)
        self.assertFalse(r["ok"])
        self.assertIn("justificativa", r["motivo"].casefold())
        self.assertEqual(self._animal(a)["status"], "vendido")

    def test_vendido_para_ativo_passa_com_autorizacao_e_justificativa(self):
        a = self._vender()
        r = db.update_animal_status(a, "ativo", tem_autorizacao=True,
                                    justificativa="venda cancelada pelo comprador",
                                    operador="admin")
        self.assertTrue(r["ok"], r)
        self.assertEqual(self._animal(a)["status"], "ativo")

    def test_justificativa_vai_para_a_trilha_de_auditoria(self):
        """Etapa B2: o destino é `audit_logs` (§14.1), não mais `animals.notes`."""
        a = self._vender()
        db.update_animal_status(a, "ativo", tem_autorizacao=True,
                                justificativa="venda cancelada pelo comprador",
                                operador="admin")

        trilha = db.eventos.trilha(entidade="animals", entidade_id=a)
        self.assertTrue(trilha, "nada foi registrado na trilha de auditoria")
        r = trilha[0]
        self.assertEqual(r["acao"], "mudanca_status_animal")
        self.assertEqual(r["usuario"], "admin")
        self.assertIn("venda cancelada pelo comprador", r["motivo"])
        self.assertEqual(r["registro_anterior"], {"status": "vendido"})
        self.assertEqual(r["registro_posterior"], {"status": "ativo"})
        self.assertEqual(r["autorizacao"], "admin",
                         "transição sensível tem de registrar quem autorizou")

    def test_mudanca_de_status_vira_evento_do_animal(self):
        """A mesma mudança também entra na linha do tempo do animal (§6)."""
        a = self._vender()
        uuid = self._animal(a)["uuid"]
        evs = db.eventos.do_animal(uuid)
        self.assertTrue(any(e["tipo"] == "venda" for e in evs),
                        f"nenhum evento de venda registrado: {[e['tipo'] for e in evs]}")

    def test_notas_do_animal_nao_sao_mais_tocadas(self):
        """A nota do usuário é dele. Depois do B2 o sistema não escreve mais lá."""
        a = self._vender()
        con = sqlite3.connect(db.DB_PATH)
        con.execute("UPDATE animals SET notes=? WHERE id=?", ("observação do dono", a))
        con.commit()
        con.close()
        db.clear_cache()

        db.update_animal_status(a, "ativo", tem_autorizacao=True,
                                justificativa="motivo novo", operador="admin")
        self.assertEqual(self._animal(a)["notes"], "observação do dono",
                         "o sistema voltou a escrever no campo de observações")

    def test_animal_inexistente_nao_estoura(self):
        r = db.update_animal_status("NAO_EXISTE", "ativo")
        self.assertFalse(r["ok"])


class TestImportacaoLigada(BaseIntegracao):
    """`parse_pesagens` reexportada por `database` e alimentada com o rebanho real."""

    def test_parse_pesagens_esta_acessivel_pelo_modulo_database(self):
        self.assertTrue(callable(db.parse_pesagens))

    def test_brinco_inexistente_e_rejeitado_com_o_rebanho_real(self):
        a = self._qualquer_ativo()
        ativos = {x["id"] for x in db.get_all_animals(status="ativo")}
        texto = f"{a};420;2026-01-15\nBOI_FANTASMA;430;2026-01-15"
        r = db.parse_pesagens(texto, ids_conhecidos=ativos)
        self.assertEqual(len(r["aceitas"]), 1)
        self.assertEqual(r["aceitas"][0]["animal_id"], a)
        self.assertEqual(len(r["rejeitadas"]), 1)
        self.assertIn("BOI_FANTASMA", r["rejeitadas"][0]["conteudo"])

    def test_linha_aceita_pode_ser_gravada_por_add_weighing(self):
        """O contrato entre o parser e a escrita: nomes e tipos têm de bater."""
        a = self._qualquer_ativo()
        ativos = {x["id"] for x in db.get_all_animals(status="ativo")}
        r = db.parse_pesagens(f"{a};433,5;15/01/2026", ids_conhecidos=ativos)
        self.assertEqual(len(r["aceitas"]), 1, r)

        linha = r["aceitas"][0]
        db.add_weighing(linha["animal_id"], linha["peso"], linha["data"],
                        operator="teste", notes="importado")
        db.clear_cache()

        pesagens = db.get_weighings(a)
        self.assertTrue(any(p["weight"] == 433.5 and p["weigh_date"] == "2026-01-15"
                            for p in pesagens),
                        f"pesagem importada não foi gravada: {pesagens}")


if __name__ == "__main__":
    unittest.main()
