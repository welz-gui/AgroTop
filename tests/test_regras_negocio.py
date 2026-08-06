"""Testes de CARACTERIZAÇÃO das regras de negócio.

Propósito (ROADMAP.md, Fase A1): congelar o comportamento atual **antes** de mover
código para `repositories/` e `services/`. Se o refactor mudar qualquer número aqui,
estes testes acusam.

REGRA DE OURO: caracterizar, não corrigir. Cada teste documenta o que o código faz
HOJE, inclusive esquisitices. Achou bug? Relate — não altere. Mudar um número em
silêncio altera relatórios que o usuário já usa para decidir venda e compra.

Onde o comportamento atual é discutível, há um comentário `QUIRK:` explicando.
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

HOJE = date.today()


def _dias_atras(n: int) -> str:
    return (HOJE - timedelta(days=n)).isoformat()


class BaseRegras(unittest.TestCase):
    """Banco SQLite limpo, sem os dados de seed, para números previsíveis."""

    @classmethod
    def setUpClass(cls):
        assert not db.USE_PG, ("os testes precisam rodar em SQLite — use "
                              "`python -m unittest discover -s tests -t .`")

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "regras.db"))

        # Neutraliza os seeds: queremos um rebanho controlado, não os dados de demo.
        seeds = ["_seed_users", "_seed_fornecedores", "_seed_lotes",
                 "_seed_animals", "_seed_insumos"]
        self._originais = {n: getattr(db, n) for n in seeds}
        for n in seeds:
            # `_seed_lotes`/`_seed_animals` recebem `property_id` desde a B4.3
            # (init_db chama as duas com dois argumentos); as demais continuam
            # de um só. Aceitar `*a` cobre as duas formas sem duplicar a lista.
            setattr(db, n, lambda *a: None)
        try:
            db.init_db()
        finally:
            for n, fn in self._originais.items():
                setattr(db, n, fn)
        db.clear_cache()

    def tearDown(self):
        db.clear_cache()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _sql(self, sql, args=()):
        con = sqlite3.connect(db.DB_PATH)
        try:
            con.execute(sql, args)
            con.commit()
        finally:
            con.close()
        db.clear_cache()

    def animal(self, aid="A1", *, peso=400.0, entrada=None, peso_entrada=300.0,
               nascimento=None, sexo="M", alvo=None, lote=None, status="ativo"):
        # O uuid é obrigatório desde a etapa B1.6: as filhas só se ligam por ele.
        # `property_id` é NOT NULL desde a B4.3 — `_seed_hierarquia` roda no
        # `init_db()` deste setUp mesmo com os outros seeds neutralizados
        # (ela não está na lista `seeds` acima), então sempre há uma
        # propriedade padrão para apontar.
        con = sqlite3.connect(db.DB_PATH)
        try:
            row = con.execute(
                "SELECT id FROM properties ORDER BY created_at LIMIT 1").fetchone()
        finally:
            con.close()
        property_id = row[0] if row else None

        self._sql(
            "INSERT INTO animals (id,uuid,breed,sex,birth_date,entry_date,entry_weight,"
            "current_weight,target_weight,status,lote_id,property_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, f"uuid-{aid}", "Nelore", sexo, nascimento,
             entrada or _dias_atras(100),
             peso_entrada, peso, alvo, status, lote, property_id))
        return aid

    def _uuid(self, aid):
        con = sqlite3.connect(db.DB_PATH)
        try:
            r = con.execute("SELECT uuid FROM animals WHERE id=?", (aid,)).fetchone()
        finally:
            con.close()
        return r[0]

    def pesagem(self, aid, peso, data):
        self._sql("INSERT INTO weighings (animal_uuid,weight,weigh_date) VALUES(?,?,?)",
                  (self._uuid(aid), peso, data))

    def custo(self, aid, valor, tipo="operacional"):
        self._sql("INSERT INTO animal_costs (animal_uuid,cost_type,amount,cost_date) "
                  "VALUES(?,?,?,?)", (self._uuid(aid), tipo, valor, HOJE.isoformat()))

    def medicacao(self, aid, med_date, carencia):
        self._sql("INSERT INTO medications (animal_uuid,medication_name,med_date,"
                  "withdrawal_days) VALUES(?,?,?,?)", (self._uuid(aid), "Ivermectina",
                                                       med_date, carencia))


# ══════════════════════════════════════════════════════════════════════════════
class TestGMD(BaseRegras):
    def test_gmd_recente_usa_as_duas_ultimas_pesagens(self):
        a = self.animal("G1")
        self.pesagem(a, 300.0, _dias_atras(62))
        self.pesagem(a, 320.0, _dias_atras(31))
        self.pesagem(a, 350.0, _dias_atras(1))   # +30 kg em 30 dias
        self.assertEqual(db.calculate_gmd(a), 1.0)

    def test_gmd_recente_arredonda_em_3_casas(self):
        a = self.animal("G2")
        self.pesagem(a, 300.0, _dias_atras(31))
        self.pesagem(a, 330.0, HOJE.isoformat())  # 30 kg / 31 dias
        self.assertEqual(db.calculate_gmd(a), 0.968)

    def test_gmd_recente_exige_duas_pesagens(self):
        a = self.animal("G3")
        self.assertIsNone(db.calculate_gmd(a))
        self.pesagem(a, 300.0, _dias_atras(10))
        self.assertIsNone(db.calculate_gmd(a))

    def test_gmd_recente_pode_ser_negativo(self):
        """Perda de peso vira GMD negativo — não é zerado nem tratado."""
        a = self.animal("G4")
        self.pesagem(a, 320.0, _dias_atras(20))
        self.pesagem(a, 300.0, _dias_atras(10))  # −20 kg em 10 dias
        self.assertEqual(db.calculate_gmd(a), -2.0)

    def test_gmd_recente_duas_pesagens_no_mesmo_dia(self):
        """QUIRK: mesma data ⇒ divisão por zero evitada devolvendo None."""
        a = self.animal("G5")
        d = _dias_atras(5)
        self.pesagem(a, 300.0, d)
        self.pesagem(a, 310.0, d)
        self.assertIsNone(db.calculate_gmd(a))

    def test_gmd_total_de_vida(self):
        a = {"entry_date": _dias_atras(100), "entry_weight": 300.0,
             "current_weight": 400.0}
        self.assertEqual(db.calculate_gmd_total(a), 1.0)

    def test_gmd_total_sem_dias_decorridos(self):
        a = {"entry_date": HOJE.isoformat(), "entry_weight": 300.0,
             "current_weight": 300.0}
        self.assertIsNone(db.calculate_gmd_total(a))

    def test_gmd_total_data_invalida(self):
        self.assertIsNone(db.calculate_gmd_total(
            {"entry_date": "31/12/2025", "entry_weight": 300.0,
             "current_weight": 400.0}))


# ══════════════════════════════════════════════════════════════════════════════
class TestArrobaEIdade(BaseRegras):
    def test_kg_para_arroba_com_rendimento_padrao(self):
        # 450 kg × 0,52 ÷ 15 = 15,6 @
        self.assertEqual(db.kg_to_arrobas(450), 15.6)
        self.assertEqual(db.CARCASS_YIELD, 0.52)
        self.assertEqual(db.KG_PER_ARROBA, 15.0)

    def test_kg_para_arroba_com_rendimento_informado(self):
        self.assertEqual(db.kg_to_arrobas(500, 0.55), round(500 * 0.55 / 15, 2))

    def test_faixas_de_idade(self):
        casos = [(6, "Até 12 meses"), (12, "Até 12 meses"),
                 (13, "13 a 24 meses"), (24, "13 a 24 meses"),
                 (25, "25 a 36 meses"), (36, "25 a 36 meses"),
                 (37, "+ de 36 meses")]
        for meses, esperado in casos:
            nasc = (HOJE - timedelta(days=int(meses * 30.44) + 2)).isoformat()
            with self.subTest(meses=meses):
                self.assertEqual(db.get_age_category(nasc), esperado)

    def test_sem_data_de_nascimento(self):
        self.assertEqual(db.get_age_category(None), "Sem idade")


# ══════════════════════════════════════════════════════════════════════════════
class TestCustos(BaseRegras):
    def test_custo_total_soma_e_arredonda(self):
        a = self.animal("C1")
        self.custo(a, 100.10)
        self.custo(a, 50.05)
        self.custo(a, 25.00)
        self.assertEqual(db.get_total_cost(a), 175.15)

    def test_custo_de_animal_sem_lancamento_e_zero(self):
        self.assertEqual(db.get_total_cost(self.animal("C2")), 0.0)

    def test_custo_de_animal_inexistente_e_zero(self):
        self.assertEqual(db.get_total_cost("NAO_EXISTE"), 0.0)


# ══════════════════════════════════════════════════════════════════════════════
class TestCarencia(BaseRegras):
    def test_carencia_futura_e_retornada(self):
        a = self.animal("W1")
        self.medicacao(a, _dias_atras(5), 10)      # termina em hoje+5
        self.assertEqual(db.get_withdrawal_end(a), HOJE + timedelta(days=5))

    def test_carencia_vencida_e_ignorada(self):
        a = self.animal("W2")
        self.medicacao(a, _dias_atras(30), 10)     # terminou em hoje−20
        self.assertIsNone(db.get_withdrawal_end(a))

    def test_prevalece_a_carencia_mais_longa(self):
        a = self.animal("W3")
        self.medicacao(a, _dias_atras(1), 5)       # hoje+4
        self.medicacao(a, _dias_atras(1), 20)      # hoje+19
        self.assertEqual(db.get_withdrawal_end(a), HOJE + timedelta(days=19))

    def test_medicacao_sem_carencia_nao_conta(self):
        a = self.animal("W4")
        self.medicacao(a, _dias_atras(1), 0)
        self.assertIsNone(db.get_withdrawal_end(a))


# ══════════════════════════════════════════════════════════════════════════════
class TestProjecaoAbate(BaseRegras):
    def test_projecao_com_gmd_conhecido(self):
        a = self.animal("P1", peso=400.0, alvo=500.0)
        self.pesagem(a, 390.0, _dias_atras(11))
        self.pesagem(a, 400.0, _dias_atras(1))     # GMD = 1,0
        r = db.projecao_abate(db.get_animal(a))
        self.assertEqual(r["falta"], 100.0)
        self.assertEqual(r["dias"], 100)
        self.assertEqual(r["data"], (HOJE + timedelta(days=100)).isoformat())

    def test_peso_alvo_padrao_e_500(self):
        """Sem target_weight, a projeção assume 500 kg."""
        a = self.animal("P2", peso=450.0, alvo=None)
        self.pesagem(a, 440.0, _dias_atras(11))
        self.pesagem(a, 450.0, _dias_atras(1))
        self.assertEqual(db.projecao_abate(db.get_animal(a))["falta"], 50.0)

    def test_alvo_ja_atingido_zera_os_dias(self):
        a = self.animal("P3", peso=520.0, alvo=500.0)
        r = db.projecao_abate(db.get_animal(a))
        self.assertEqual(r["dias"], 0)
        self.assertEqual(r["falta"], 0)
        self.assertEqual(r["data"], HOJE.isoformat())

    def test_sem_gmd_nao_estima_data(self):
        a = self.animal("P4", peso=400.0, alvo=500.0)  # sem pesagens
        r = db.projecao_abate(db.get_animal(a))
        self.assertIsNone(r["dias"])
        self.assertIsNone(r["data"])
        self.assertEqual(r["falta"], 100.0)

    def test_gmd_negativo_nao_estima_data(self):
        """QUIRK: perdendo peso, a projeção devolve None em vez de data infinita."""
        a = self.animal("P5", peso=400.0, alvo=500.0)
        self.pesagem(a, 420.0, _dias_atras(11))
        self.pesagem(a, 400.0, _dias_atras(1))
        self.assertIsNone(db.projecao_abate(db.get_animal(a))["dias"])


# ══════════════════════════════════════════════════════════════════════════════
class TestVenda(BaseRegras):
    def test_venda_por_kg(self):
        a = self.animal("V1", peso=400.0)
        self.custo(a, 1000.0)
        r = db.register_sale([a], HOJE.isoformat(), "abate", "kg", 10.0)
        self.assertEqual(r["receita"], 4000.0)      # 400 kg × R$ 10
        self.assertEqual(r["custo"], 1000.0)
        self.assertEqual(r["lucro"], 3000.0)
        self.assertEqual(r["n"], 1)
        self.assertEqual(db.get_animal(a)["status"], "vendido")

    def test_venda_por_cabeca_ignora_o_peso(self):
        a = self.animal("V2", peso=400.0)
        b = self.animal("V3", peso=600.0)
        r = db.register_sale([a, b], HOJE.isoformat(), "abate", "cabeca", 5000.0)
        self.assertEqual(r["receita"], 10000.0)     # 2 × R$ 5.000
        self.assertEqual(r["n"], 2)

    def test_venda_de_lote_rateia_pelo_peso(self):
        a = self.animal("V4", peso=400.0)
        b = self.animal("V5", peso=600.0)           # total 1.000 kg
        r = db.register_sale([a, b], HOJE.isoformat(), "abate", "lote", 10000.0)
        self.assertEqual(r["receita"], 10000.0)
        vendas = {v["animal_id"]: v["total_value"] for v in db.get_sales()}
        self.assertEqual(vendas["V4"], 4000.0)      # 400/1000 do total
        self.assertEqual(vendas["V5"], 6000.0)

    def test_lote_ref_e_criado_para_venda_multipla(self):
        a = self.animal("V6"); b = self.animal("V7")
        self.assertIsNotNone(
            db.register_sale([a, b], HOJE.isoformat(), "abate", "kg", 10.0)["lot_ref"])

    def test_sem_lote_ref_para_venda_individual_por_kg(self):
        a = self.animal("V8")
        self.assertIsNone(
            db.register_sale([a], HOJE.isoformat(), "abate", "kg", 10.0)["lot_ref"])

    def test_venda_sem_animais_valido(self):
        """QUIRK: o retorno de lista vazia NÃO traz a chave 'lot_ref'."""
        r = db.register_sale(["INEXISTENTE"], HOJE.isoformat(), "abate", "kg", 10.0)
        self.assertEqual(r, {"receita": 0, "custo": 0, "lucro": 0, "n": 0})
        self.assertNotIn("lot_ref", r)


# ══════════════════════════════════════════════════════════════════════════════
class TestObito(BaseRegras):
    def test_obito_contabiliza_custo_como_perda(self):
        a = self.animal("M1", peso=380.0)
        self.custo(a, 1500.50)
        r = db.register_death(a, HOJE.isoformat(), "Cobra")
        self.assertTrue(r["ok"])
        self.assertEqual(r["perda"], 1500.50)
        self.assertEqual(db.get_animal(a)["status"], "morto")

    def test_obito_guarda_o_peso_do_momento(self):
        a = self.animal("M2", peso=377.0)
        db.register_death(a, HOJE.isoformat(), "Timpanismo")
        obito = db.get_deaths()[0]
        self.assertEqual(obito["weight_at_death"], 377.0)
        self.assertEqual(obito["cause"], "Timpanismo")

    def test_obito_de_animal_inexistente(self):
        self.assertEqual(db.register_death("NAO_EXISTE", HOJE.isoformat(), "x"),
                         {"ok": False})


# ══════════════════════════════════════════════════════════════════════════════
class TestValorEsperadoDeVenda(BaseRegras):
    def test_valor_esperado_usa_preco_da_categoria(self):
        nasc = (HOJE - timedelta(days=int(18 * 30.44))).isoformat()   # 13–24 meses
        a = self.animal("E1", peso=400.0, nascimento=nasc, sexo="M")
        db.set_category_price("13 a 24 meses", "M", 12.50)
        db.clear_cache()
        self.assertEqual(db.expected_sale_value(db.get_animal(a)), 5000.0)

    def test_sem_preco_cadastrado_o_valor_e_zero(self):
        a = self.animal("E2", peso=400.0, nascimento=None)
        self.assertEqual(db.expected_sale_value(db.get_animal(a)), 0.0)


# ══════════════════════════════════════════════════════════════════════════════
class TestEstoque(BaseRegras):
    def _insumo(self):
        self._sql("INSERT INTO insumos (name,category,unit,current_stock,min_stock,"
                  "cost_per_unit) VALUES(?,?,?,?,?,?)",
                  ("Ração", "racao", "kg", 100.0, 20.0, 2.0))
        return db.get_all_insumos()[0]["id"]

    def test_entrada_soma_estoque_e_usa_media_ponderada(self):
        """COMPORTAMENTO ALTERADO em 2026-07-31 — mudança deliberada.

        Antes, o custo unitário era **sobrescrito** pelo da última entrada (o
        `QUIRK` que este teste documentava). Comprar 10 kg a R$ 5 com 1.000 kg a
        R$ 2 em estoque fazia todo o saldo valer R$ 5/kg, inflando custo de trato
        e margem.

        Agora usa **média ponderada** (`services.estoque.custo_medio_ponderado`),
        conforme docs/adr/0003-custo-medio-ponderado.md. A decisão é
        **não-retroativa**: vale para entradas novas; o histórico já lançado
        permanece como estava.
        """
        iid = self._insumo()
        db.add_insumo_entry(iid, 50.0, 2.50)
        i = [x for x in db.get_all_insumos() if x["id"] == iid][0]
        self.assertEqual(i["current_stock"], 150.0)
        # (100 × 2,00 + 50 × 2,50) ÷ 150 = 2,1666… → 2,17
        self.assertEqual(i["cost_per_unit"], 2.17)

    def test_entrada_registra_movimentacao(self):
        iid = self._insumo()
        db.add_insumo_entry(iid, 50.0, 2.50, operator="op1")
        con = sqlite3.connect(db.DB_PATH); con.row_factory = sqlite3.Row
        try:
            t = con.execute("SELECT * FROM insumo_transactions "
                            "WHERE insumo_id=?", (iid,)).fetchone()
        finally:
            con.close()
        self.assertEqual((t["type"], t["reason"], t["quantity"]),
                         ("entrada", "compra", 50.0))

    def test_estoque_baixo_e_detectado(self):
        self._sql("INSERT INTO insumos (name,category,unit,current_stock,min_stock,"
                  "cost_per_unit) VALUES(?,?,?,?,?,?)",
                  ("Vacina", "vacina", "dose", 5.0, 10.0, 3.0))
        nomes = {i["name"] for i in db.check_low_stock()}
        self.assertIn("Vacina", nomes)
        self.assertNotIn("Ração", nomes)


# ══════════════════════════════════════════════════════════════════════════════
class TestEstatisticasDoRebanho(BaseRegras):
    def test_stats_consideram_apenas_ativos(self):
        self.animal("S1", peso=400.0, peso_entrada=300.0, sexo="M")
        self.animal("S2", peso=500.0, peso_entrada=400.0, sexo="F")
        self.animal("S3", peso=600.0, peso_entrada=500.0, status="vendido")
        db.clear_cache()
        s = db.get_rebanho_stats()

        self.assertEqual(s["total"], 2)              # o vendido não entra
        self.assertEqual(s["avg_weight"], 450.0)
        self.assertEqual(s["total_kg"], 900)
        self.assertEqual(s["males"], 1)
        self.assertEqual(s["females"], 1)
        # UA = peso ÷ 450: (400+500)/450 = 2,0
        self.assertEqual(s["total_ua"], 2.0)
        # @ produzidas: ganho de 100 kg cada → 100×0,52÷15 = 3,47 @ → 6,94 → 6,9
        self.assertEqual(s["arrobas_prod"], 6.9)
        # sem pesagens não há GMD; o campo vira 0, não None
        self.assertEqual(s["avg_gmd"], 0)

    def test_sem_piquete_com_area_a_lotacao_e_zero(self):
        self.animal("S4", peso=450.0)
        db.clear_cache()
        s = db.get_rebanho_stats()
        self.assertEqual(s["total_area"], 0)
        self.assertEqual(s["lotacao_ua_ha"], 0)

    def test_rebanho_vazio_devolve_dicionario_vazio(self):
        """QUIRK: sem animais ativos, o retorno é `{}` — não um dict com zeros.

        Contrato frágil: um `stats["total"]` direto estoura KeyError. **Não é bug
        ativo** — os dois chamadores atuais protegem (`if stats:` na barra lateral,
        `if not animals: return` no dashboard). Mas quem for consumir em código novo
        (API, mobile) precisa checar antes.
        """
        self.assertEqual(db.get_rebanho_stats(), {})


# ══════════════════════════════════════════════════════════════════════════════
class TestEstimativaPesoPorMedicao(unittest.TestCase):
    def test_estimativa_peso_com_medidas_validas(self):
        # 200² * 150 / 10838 = 553.6076... -> 553.6
        self.assertEqual(db.estimate_weight_by_measurement(200.0, 150.0), 553.6)

    def test_estimativa_peso_com_medida_zero(self):
        self.assertEqual(db.estimate_weight_by_measurement(0.0, 150.0), 0.0)
        self.assertEqual(db.estimate_weight_by_measurement(200.0, 0.0), 0.0)
        self.assertEqual(db.estimate_weight_by_measurement(0.0, 0.0), 0.0)

    def test_estimativa_peso_com_medida_negativa(self):
        self.assertEqual(db.estimate_weight_by_measurement(-10.0, 150.0), 0.0)
        self.assertEqual(db.estimate_weight_by_measurement(200.0, -5.0), 0.0)
        self.assertEqual(db.estimate_weight_by_measurement(-10.0, -5.0), 0.0)


if __name__ == "__main__":
    unittest.main()
