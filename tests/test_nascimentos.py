"""Nascimentos e vínculo materno (ADR 0004 · B3 · PNIB §7).

A regra biológica é `services/genealogia.py`, entregue pela spec 0022 e já
testada lá. Estes testes travam a **ligação**: que a regra é de fato chamada
antes de gravar, que gêmeos ficam no mesmo parto, e que alterar o vínculo
materno deixa rastro.
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
from repositories import eventos, nascimentos  # noqa: E402

HOJE = date.today()


def _dias_atras(n):
    return (HOJE - timedelta(days=n)).isoformat()


class BaseB3(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "b3.db"))
        db.init_db()
        db.clear_cache()
        # Uma fêmea adulta para servir de mãe.
        self.mae = self._criar_femea_adulta("MAE1")

    def _criar_femea_adulta(self, brinco):
        db.add_animal(brinco, "Nelore", "F", _dias_atras(1800), _dias_atras(400),
                      400.0, 500.0, 3000.0, None, None)
        db.clear_cache()
        return [a for a in db.get_all_animals(status=None)
                if a["id"] == brinco][0]["uuid"]

    def _linhas(self, sql, args=()):
        con = sqlite3.connect(db.DB_PATH)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args).fetchall()]
        finally:
            con.close()


class TestPartoSimples(BaseB3):
    def test_registra_cria_e_parto(self):
        r = nascimentos.registrar(
            self.mae, _dias_atras(10),
            [{"id": "C1", "sexo": "M", "raca": "Nelore", "peso": 32.0}],
            responsavel="op1")
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(r["crias"]), 1)

        cria = self._linhas("SELECT * FROM animals WHERE id='C1'")[0]
        self.assertEqual(cria["mae_uuid"], self.mae)
        self.assertEqual(cria["origem"], "nascido")
        self.assertEqual(cria["peso_nascimento"], 32.0)
        self.assertEqual(cria["birth_date"], _dias_atras(10))

    def test_propriedade_de_nascimento_e_preenchida(self):
        """§4.3: onde nasceu é diferente de onde está — e não muda depois."""
        nascimentos.registrar(self.mae, _dias_atras(10),
                              [{"id": "C2", "sexo": "F", "raca": "Nelore"}])
        c = self._linhas("SELECT * FROM animals WHERE id='C2'")[0]
        self.assertTrue(c["propriedade_nascimento_id"])
        self.assertEqual(c["propriedade_nascimento_id"], c["property_id"])

    def test_nascimento_gera_evento(self):
        r = nascimentos.registrar(self.mae, _dias_atras(10),
                                  [{"id": "C3", "sexo": "M", "raca": "Nelore"}])
        tipos = [e["tipo"] for e in eventos.do_animal(r["crias"][0])]
        self.assertIn("nascimento", tipos)

    def test_data_futura_e_recusada(self):
        amanha = (HOJE + timedelta(days=1)).isoformat()
        r = nascimentos.registrar(self.mae, amanha,
                                  [{"id": "CF", "sexo": "M", "raca": "Nelore"}])
        self.assertFalse(r["ok"])
        self.assertEqual(self._linhas("SELECT id FROM animals WHERE id='CF'"), [])

    def test_sem_cria_e_recusado(self):
        self.assertFalse(nascimentos.registrar(self.mae, _dias_atras(5), [])["ok"])


class TestGemeos(BaseB3):
    """§7.2: gêmeos devem gerar animais distintos ligados ao MESMO parto."""

    def test_duas_crias_ficam_no_mesmo_parto(self):
        r = nascimentos.registrar(
            self.mae, _dias_atras(10),
            [{"id": "G1", "sexo": "M", "raca": "Nelore"},
             {"id": "G2", "sexo": "F", "raca": "Nelore"}],
            responsavel="op1")
        self.assertTrue(r["ok"], r)

        crias = self._linhas("SELECT id, parto_id FROM animals WHERE id IN ('G1','G2')")
        self.assertEqual(len(crias), 2, "gêmeos não geraram dois animais distintos")
        self.assertEqual(crias[0]["parto_id"], crias[1]["parto_id"],
                         "gêmeos ficaram em partos diferentes")

    def test_so_existe_um_parto_para_os_gemeos(self):
        nascimentos.registrar(self.mae, _dias_atras(10),
                              [{"id": "G3", "sexo": "M", "raca": "Nelore"},
                               {"id": "G4", "sexo": "F", "raca": "Nelore"}])
        self.assertEqual(len(nascimentos.partos_da_mae(self.mae)), 1)

    def test_crias_do_parto_devolve_os_dois(self):
        r = nascimentos.registrar(self.mae, _dias_atras(10),
                                  [{"id": "G5", "sexo": "M", "raca": "Nelore"},
                                   {"id": "G6", "sexo": "F", "raca": "Nelore"}])
        self.assertEqual(len(nascimentos.crias_do_parto(r["parto_id"])), 2)


class TestValidacaoLigada(BaseB3):
    """A regra pura da spec 0022 é mesmo chamada antes de gravar?"""

    def test_mae_macho_bloqueia(self):
        macho = self._criar_femea_adulta("MACHO")  # cria e depois vira macho
        con = sqlite3.connect(db.DB_PATH)
        con.execute("UPDATE animals SET sex='M' WHERE uuid=?", (macho,))
        con.commit(); con.close()
        db.clear_cache()

        r = nascimentos.registrar(macho, _dias_atras(10),
                                  [{"id": "CX", "sexo": "M", "raca": "Nelore"}])
        self.assertFalse(r["ok"])
        self.assertEqual(self._linhas("SELECT id FROM animals WHERE id='CX'"), [],
                         "cria foi gravada apesar do bloqueio")

    def test_mae_jovem_demais_bloqueia(self):
        jovem = self._criar_femea_adulta("JOVEM")
        con = sqlite3.connect(db.DB_PATH)
        con.execute("UPDATE animals SET birth_date=? WHERE uuid=?",
                    (_dias_atras(300), jovem))
        con.commit(); con.close()
        db.clear_cache()

        r = nascimentos.registrar(jovem, _dias_atras(1),
                                  [{"id": "CY", "sexo": "M", "raca": "Nelore"}])
        self.assertFalse(r["ok"])

    def test_alerta_pede_confirmacao_mas_nao_bloqueia(self):
        """§7.2: alerta 'sem substituir a avaliação técnica'."""
        nascimentos.registrar(self.mae, _dias_atras(200),
                              [{"id": "P1", "sexo": "M", "raca": "Nelore"}])
        db.clear_cache()

        # Segundo parto cedo demais — intervalo curto é ALERTA, não bloqueio.
        r = nascimentos.registrar(self.mae, _dias_atras(20),
                                  [{"id": "P2", "sexo": "F", "raca": "Nelore"}])
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("exige_confirmacao"),
                        f"alerta virou bloqueio: {r}")

        r2 = nascimentos.registrar(self.mae, _dias_atras(20),
                                   [{"id": "P2", "sexo": "F", "raca": "Nelore"}],
                                   ignorar_alertas=True)
        self.assertTrue(r2["ok"], "confirmação não liberou o registro")

    def test_avaliar_nao_grava_nada(self):
        antes = len(self._linhas("SELECT id FROM animals"))
        nascimentos.avaliar(self.mae, _dias_atras(10))
        self.assertEqual(len(self._linhas("SELECT id FROM animals")), antes)


class TestVinculoMaternoAuditado(BaseB3):
    """§7.2: alterações no vínculo materno devem ser auditadas."""

    def test_alteracao_exige_motivo(self):
        r = nascimentos.registrar(self.mae, _dias_atras(10),
                                  [{"id": "V1", "sexo": "M", "raca": "Nelore"}])
        cria = r["crias"][0]
        self.assertFalse(nascimentos.vincular_mae(
            cria, None, motivo="  ", usuario="admin")["ok"])

    def test_alteracao_fica_na_trilha_com_antes_e_depois(self):
        r = nascimentos.registrar(self.mae, _dias_atras(10),
                                  [{"id": "V2", "sexo": "M", "raca": "Nelore"}])
        cria = r["crias"][0]
        outra = self._criar_femea_adulta("MAE2")

        ok = nascimentos.vincular_mae(cria, outra,
                                      motivo="vínculo trocado por conferência de campo",
                                      usuario="admin")
        self.assertTrue(ok["ok"], ok)

        trilha = eventos.trilha(entidade="animals", entidade_id=cria)
        registro = [t for t in trilha
                    if t["acao"] == "alteracao_de_vinculo_materno"]
        self.assertTrue(registro, "alteração de vínculo não foi auditada")
        self.assertEqual(registro[0]["registro_anterior"], {"mae_uuid": self.mae})
        self.assertEqual(registro[0]["registro_posterior"], {"mae_uuid": outra})
        self.assertIn("conferência de campo", registro[0]["motivo"])


class TestPendencias(BaseB3):
    """§7.3: o sistema precisa saber o que falta, não só registrar certo."""

    def test_lista_animal_nascido_sem_mae(self):
        db.add_animal("SM", "Nelore", "M", _dias_atras(100), _dias_atras(100),
                      40.0, 500.0, 0.0, None, None)
        con = sqlite3.connect(db.DB_PATH)
        con.execute("UPDATE animals SET origem='nascido' WHERE id='SM'")
        con.commit(); con.close()
        db.clear_cache()
        self.assertIn("SM", nascimentos.pendencias()["sem_mae_vinculada"])

    def test_lista_nascimento_estimado(self):
        p = nascimentos.pendencias()["nascimento_estimado"]
        self.assertIsInstance(p, list)

    def test_todo_animal_sem_identificador_oficial_aparece(self):
        """Hoje nenhum tem — o formato do PNIB ainda não foi publicado (§23)."""
        p = nascimentos.pendencias()["sem_identificacao_oficial"]
        ativos = [a["id"] for a in db.get_all_animals(status="ativo")]
        self.assertEqual(sorted(p), sorted(ativos))


if __name__ == "__main__":
    unittest.main()
