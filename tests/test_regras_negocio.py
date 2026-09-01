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
from repositories.animais import get_animal  # noqa: E402

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

    def test_gmd_total_chaves_ausentes(self):
        """Testa o comportamento de calculate_gmd_total quando faltam chaves (KeyError)."""
        a_sem_entry_date = {"entry_weight": 300.0, "current_weight": 400.0}
        self.assertIsNone(db.calculate_gmd_total(a_sem_entry_date))

        a_sem_entry_weight = {"entry_date": _dias_atras(100), "current_weight": 400.0}
        self.assertIsNone(db.calculate_gmd_total(a_sem_entry_weight))

        a_sem_current_weight = {"entry_date": _dias_atras(100), "entry_weight": 300.0}
        self.assertIsNone(db.calculate_gmd_total(a_sem_current_weight))

    def test_gmd_total_tipos_invalidos(self):
        """Testa o comportamento de calculate_gmd_total quando tipos são inválidos (TypeError)."""
        self.assertIsNone(db.calculate_gmd_total(None))

        a_tipos_invalidos_peso = {"entry_date": _dias_atras(100), "entry_weight": "texto", "current_weight": 400.0}
        self.assertIsNone(db.calculate_gmd_total(a_tipos_invalidos_peso))

        a_tipos_invalidos_data = {"entry_date": None, "entry_weight": 300.0, "current_weight": 400.0}
        self.assertIsNone(db.calculate_gmd_total(a_tipos_invalidos_data))


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

    def test_idade_com_data_invalida(self):
        self.assertIsNone(db.get_age_months("invalid-date"))
        self.assertIsNone(db.get_age_months("2024/01/01")) # Formato incorreto


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

    def test_custo_por_lote_soma_pelo_piquete_atual_do_animal(self):
        """Centro de custo (§5, Trilha 3): agrega animal_costs pelo
        `lote_id` de HOJE — não pelo piquete de quando o custo ocorreu."""
        a = self.animal("C3", lote="P1")
        b = self.animal("C4", lote="P1")
        z = self.animal("C5", lote="P2")
        self.custo(a, 100.0)
        self.custo(b, 50.0)
        self.custo(z, 30.0)

        por_lote = db.get_animal_costs_by_lote()
        self.assertEqual(por_lote["P1"], 150.0)
        self.assertEqual(por_lote["P2"], 30.0)

    def test_custo_por_lote_ignora_animal_sem_piquete(self):
        a = self.animal("C6", lote=None)
        self.custo(a, 999.0)
        self.assertEqual(db.get_animal_costs_by_lote(), {})

    def test_custo_fixo_com_lote_id_none_e_geral_da_fazenda(self):
        con = sqlite3.connect(db.DB_PATH)
        try:
            property_id = con.execute(
                "SELECT id FROM properties ORDER BY created_at LIMIT 1").fetchone()[0]
            con.execute("INSERT INTO lotes (id,name,property_id) VALUES(?,?,?)",
                       ("P1", "Piquete 1", property_id))
            con.commit()
        finally:
            con.close()

        db.add_fixed_cost("Salários", "Gerente", 5000.0, HOJE.isoformat())
        db.add_fixed_cost("Aluguel de pastagem", "Piquete 1", 1000.0,
                          HOJE.isoformat(), lote_id="P1")

        por_lote = db.get_fixed_costs_by_lote()
        self.assertEqual(por_lote[None], 5000.0)
        self.assertEqual(por_lote["P1"], 1000.0)


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
        r = db.projecao_abate(get_animal(a))
        self.assertEqual(r["falta"], 100.0)
        self.assertEqual(r["dias"], 100)
        self.assertEqual(r["data"], (HOJE + timedelta(days=100)).isoformat())

    def test_peso_alvo_padrao_e_500(self):
        """Sem target_weight, a projeção assume 500 kg."""
        a = self.animal("P2", peso=450.0, alvo=None)
        self.pesagem(a, 440.0, _dias_atras(11))
        self.pesagem(a, 450.0, _dias_atras(1))
        self.assertEqual(db.projecao_abate(get_animal(a))["falta"], 50.0)

    def test_alvo_ja_atingido_zera_os_dias(self):
        a = self.animal("P3", peso=520.0, alvo=500.0)
        r = db.projecao_abate(get_animal(a))
        self.assertEqual(r["dias"], 0)
        self.assertEqual(r["falta"], 0)
        self.assertEqual(r["data"], HOJE.isoformat())

    def test_sem_gmd_nao_estima_data(self):
        a = self.animal("P4", peso=400.0, alvo=500.0)  # sem pesagens
        r = db.projecao_abate(get_animal(a))
        self.assertIsNone(r["dias"])
        self.assertIsNone(r["data"])
        self.assertEqual(r["falta"], 100.0)

    def test_gmd_negativo_nao_estima_data(self):
        """QUIRK: perdendo peso, a projeção devolve None em vez de data infinita
        — mas `situacao` (spec 0040/services.projecao, ligado em 2026-08-14)
        diferencia isso de "sem dados nenhum", que `test_sem_gmd_nao_estima_data`
        cobre: ambos dão `dias=None`, só `situacao` muda."""
        a = self.animal("P5", peso=400.0, alvo=500.0)
        self.pesagem(a, 420.0, _dias_atras(11))
        self.pesagem(a, 400.0, _dias_atras(1))
        r = db.projecao_abate(get_animal(a))
        self.assertIsNone(r["dias"])
        self.assertEqual(r["situacao"], "perdendo_peso")

    def test_dias_fracionados_arredondam_para_cima(self):
        """O defeito corrigido ao ligar services.projecao (2026-08-14):
        `round()` podia arredondar dias PARA BAIXO — falta 100 kg a 3 kg/dia
        são 33,33 dias; `round` virava 33, o certo (`ceil`, dia fracionado
        não conta) é 34. Arredondar para baixo prometia abate um dia cedo
        demais."""
        a = self.animal("P6", peso=400.0, alvo=500.0)
        self.pesagem(a, 370.0, _dias_atras(11))
        self.pesagem(a, 400.0, _dias_atras(1))     # GMD = 3,0
        r = db.projecao_abate(get_animal(a))
        self.assertEqual(r["falta"], 100.0)
        self.assertEqual(r["dias"], 34, "arredondou para baixo (round) em vez de ceil")
        self.assertEqual(r["data"], (HOJE + timedelta(days=34)).isoformat())

    def test_bulk_concorda_com_a_versao_individual(self):
        """projecao_abate_bulk (usada pela tela, spec 0040) precisa devolver
        exatamente a mesma projeção que projecao_abate — mesma delegação a
        services.projecao.projetar_abate, caminhos de GMD diferentes
        (calculate_gmd_bulk vs calculate_gmd)."""
        a = self.animal("P7", peso=400.0, alvo=500.0)
        self.pesagem(a, 370.0, _dias_atras(11))
        self.pesagem(a, 400.0, _dias_atras(1))
        individual = db.projecao_abate(get_animal(a))
        bulk = db.projecao_abate_bulk([get_animal(a)])[a]["projecao"]
        self.assertEqual(individual, bulk)


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
        self.assertEqual(get_animal(a)["status"], "vendido")

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

    def test_venda_a_vista_nao_gera_conta_a_receber(self):
        """Padrão de sempre, preservado (ROADMAP §3): à vista não muda nada."""
        a = self.animal("V9", peso=400.0)
        r = db.register_sale([a], HOJE.isoformat(), "abate", "kg", 10.0)
        self.assertEqual(r["parcelas_a_receber"], 0)
        self.assertEqual(db.listar_contas_receber(), [])

    def test_venda_a_prazo_gera_parcelas_em_contas_a_receber(self):
        a = self.animal("V10", peso=400.0)
        venc = (HOJE + timedelta(days=30)).isoformat()
        r = db.register_sale([a], HOJE.isoformat(), "abate", "kg", 10.0,
                             buyer="Frigorífico Z", a_prazo=True, num_parcelas=3,
                             primeiro_vencimento=venc)
        self.assertEqual(r["parcelas_a_receber"], 3)
        contas = db.listar_contas_receber()
        self.assertEqual(len(contas), 3)
        self.assertEqual(round(sum(c["valor"] for c in contas), 2), r["receita"])
        self.assertTrue(all(c["status"] == "aberto" for c in contas))
        self.assertTrue(all(c["comprador"] == "Frigorífico Z" for c in contas))

    def test_venda_a_prazo_sem_vencimento_recusa(self):
        a = self.animal("V11", peso=400.0)
        with self.assertRaises(ValueError):
            db.register_sale([a], HOJE.isoformat(), "abate", "kg", 10.0, a_prazo=True)

    def test_a_prazo_fica_marcado_na_propria_venda(self):
        """A coluna que o fluxo de caixa usa para não contar a venda duas
        vezes (uma via `sales`, outra via `contas_receber`)."""
        venc = (HOJE + timedelta(days=30)).isoformat()
        a_vista = self.animal("V13", peso=400.0)
        a_prazo = self.animal("V14", peso=400.0)
        db.register_sale([a_vista], HOJE.isoformat(), "abate", "kg", 10.0)
        db.register_sale([a_prazo], HOJE.isoformat(), "abate", "kg", 10.0,
                         a_prazo=True, num_parcelas=1, primeiro_vencimento=venc)

        vendas = {v["animal_id"]: v["a_prazo"] for v in db.get_sales()}
        self.assertEqual(vendas["V13"], 0)
        self.assertEqual(vendas["V14"], 1)

    def test_marcar_recebido_fecha_a_conta_e_preserva_as_outras(self):
        a = self.animal("V12", peso=400.0)
        venc = (HOJE + timedelta(days=30)).isoformat()
        db.register_sale([a], HOJE.isoformat(), "abate", "kg", 10.0,
                         a_prazo=True, num_parcelas=2, primeiro_vencimento=venc)
        aberta1, aberta2 = db.listar_contas_receber("aberto")
        self.assertTrue(db.marcar_recebido(aberta1["id"], HOJE.isoformat(), "pix"))
        abertas = db.listar_contas_receber("aberto")
        self.assertEqual(len(abertas), 1)
        self.assertEqual(abertas[0]["id"], aberta2["id"])
        recebidas = db.listar_contas_receber("recebido")
        self.assertEqual(len(recebidas), 1)
        self.assertEqual(recebidas[0]["forma_recebimento"], "pix")


# ══════════════════════════════════════════════════════════════════════════════
class TestObito(BaseRegras):
    def test_obito_contabiliza_custo_como_perda(self):
        a = self.animal("M1", peso=380.0)
        self.custo(a, 1500.50)
        r = db.register_death(a, HOJE.isoformat(), "Cobra")
        self.assertTrue(r["ok"])
        self.assertEqual(r["perda"], 1500.50)
        self.assertEqual(get_animal(a)["status"], "morto")

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
        self.assertEqual(db.expected_sale_value(get_animal(a)), 5000.0)

    def test_sem_preco_cadastrado_o_valor_e_zero(self):
        a = self.animal("E2", peso=400.0, nascimento=None)
        self.assertEqual(db.expected_sale_value(get_animal(a)), 0.0)


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

    def test_compra_id_distingue_entrada_avulsa_de_compra_com_nota(self):
        """A coluna que o fluxo de caixa usa para não contar a mesma compra
        duas vezes (uma via insumo_transactions/competência, outra via
        contas_pagar/caixa)."""
        iid = self._insumo()
        db.add_insumo_entry(iid, 10.0, 2.0)  # avulsa, sem nota
        r = db.compras.registrar(
            data_emissao=HOJE.isoformat(), data_recebimento=HOJE.isoformat(),
            itens=[{"insumo_id": iid, "quantidade": 5.0, "custo_unitario": 3.0}],
            primeiro_vencimento=(HOJE + timedelta(days=10)).isoformat(),
            num_parcelas=1)
        self.assertTrue(r["ok"])

        db.clear_cache()
        compras = db.get_insumo_compras()
        com_nota = [c for c in compras if c.get("compra_id")]
        avulsas = [c for c in compras if not c.get("compra_id")]
        self.assertEqual(len(com_nota), 1)
        self.assertEqual(com_nota[0]["compra_id"], r["compra_id"])
        self.assertEqual(len(avulsas), 1)


# ══════════════════════════════════════════════════════════════════════════════
class TestDietaVigencia(BaseRegras):
    """Nova versão de item de trato (§5, Trilha 3) — mesmo princípio de
    `regras.nova_versao()`: editar no lugar reescreveria o histórico de
    custo já calculado com a versão anterior."""

    def _lote(self, lid="P1"):
        con = sqlite3.connect(db.DB_PATH)
        try:
            property_id = con.execute(
                "SELECT id FROM properties ORDER BY created_at LIMIT 1").fetchone()[0]
            con.execute("INSERT INTO lotes (id,name,property_id) VALUES(?,?,?)",
                       (lid, f"Piquete {lid}", property_id))
            con.commit()
        finally:
            con.close()
        return lid

    def test_novo_item_nasce_com_vigencia_aberta_hoje(self):
        lid = self._lote()
        db.add_feeding_plan(lid, "Ração", 10.0, "kg", "diario")
        p = db.get_feeding_plans(lote_id=lid, active_only=True)[0]
        self.assertEqual(p["vigente_de"], HOJE.isoformat())
        self.assertIsNone(p["vigente_ate"])

    def test_nova_versao_encerra_a_antiga_e_cria_outra(self):
        lid = self._lote()
        db.add_feeding_plan(lid, "Ração", 10.0, "kg", "diario")
        antiga = db.get_feeding_plans(lote_id=lid, active_only=True)[0]

        r = db.nova_versao_feeding_plan(antiga["id"], quantity=15.0, frequency="semanal")
        self.assertTrue(r["ok"])

        historico = db.get_feeding_plan_historico(lid)
        self.assertEqual(len(historico), 2)

        nova = [h for h in historico if h["vigente_ate"] is None][0]
        fechada = [h for h in historico if h["vigente_ate"] is not None][0]
        self.assertEqual(nova["quantity"], 15.0)
        self.assertEqual(nova["frequency"], "semanal")
        self.assertEqual(fechada["id"], antiga["id"])
        self.assertEqual(fechada["quantity"], 10.0, "versão antiga não pode mudar de valor")
        self.assertEqual(fechada["vigente_ate"],
                         (HOJE - timedelta(days=1)).isoformat())
        self.assertEqual(fechada["active"], 0)

    def test_nova_versao_herda_campos_nao_informados(self):
        lid = self._lote()
        db.add_feeding_plan(lid, "Ração", 10.0, "kg", "diario", notes="obs original")
        antiga = db.get_feeding_plans(lote_id=lid, active_only=True)[0]

        db.nova_versao_feeding_plan(antiga["id"], quantity=20.0)  # só a quantidade muda
        nova = [h for h in db.get_feeding_plan_historico(lid) if h["vigente_ate"] is None][0]
        self.assertEqual(nova["quantity"], 20.0)
        self.assertEqual(nova["frequency"], "diario")
        self.assertEqual(nova["notes"], "obs original")

    def test_nao_versiona_item_ja_encerrado(self):
        lid = self._lote()
        db.add_feeding_plan(lid, "Ração", 10.0, "kg", "diario")
        p = db.get_feeding_plans(lote_id=lid, active_only=True)[0]
        db.encerrar_feeding_plan(p["id"])

        r = db.nova_versao_feeding_plan(p["id"], quantity=99.0)
        self.assertFalse(r["ok"])

    def test_encerrar_fecha_vigencia_sem_apagar_a_linha(self):
        lid = self._lote()
        db.add_feeding_plan(lid, "Ração", 10.0, "kg", "diario")
        p = db.get_feeding_plans(lote_id=lid, active_only=True)[0]

        r = db.encerrar_feeding_plan(p["id"])
        self.assertTrue(r["ok"])

        historico = db.get_feeding_plan_historico(lid)
        self.assertEqual(len(historico), 1, "encerrar não pode apagar o registro")
        self.assertEqual(historico[0]["vigente_ate"], HOJE.isoformat())
        self.assertEqual(historico[0]["active"], 0)

    def test_encerrar_duas_vezes_falha_na_segunda(self):
        lid = self._lote()
        db.add_feeding_plan(lid, "Ração", 10.0, "kg", "diario")
        p = db.get_feeding_plans(lote_id=lid, active_only=True)[0]
        self.assertTrue(db.encerrar_feeding_plan(p["id"])["ok"])
        self.assertFalse(db.encerrar_feeding_plan(p["id"])["ok"])

    def test_pausar_nao_mexe_na_vigencia(self):
        """Pausar/reativar (aba Planos Ativos) é reversível e não é 'mudança
        de dieta' — continua sendo a mesma versão, só liga/desliga."""
        lid = self._lote()
        db.add_feeding_plan(lid, "Ração", 10.0, "kg", "diario")
        p = db.get_feeding_plans(lote_id=lid, active_only=True)[0]

        db.set_feeding_plan_active(p["id"], 0)
        depois = db.get_feeding_plan_historico(lid)[0]
        self.assertEqual(depois["active"], 0)
        self.assertIsNone(depois["vigente_ate"], "pausar não é encerrar a vigência")


# ══════════════════════════════════════════════════════════════════════════════
class TestTransferenciaDeAnimais(BaseRegras):
    """`move_animals_bulk` (§5, Trilha 3) — a versão em lote de `move_animal`:
    mover um piquete inteiro sem abrir a ficha de cada animal."""

    def setUp(self):
        super().setUp()
        con = sqlite3.connect(db.DB_PATH)
        try:
            property_id = con.execute(
                "SELECT id FROM properties ORDER BY created_at LIMIT 1").fetchone()[0]
            for lid in ("P1", "P2"):
                con.execute("INSERT INTO lotes (id,name,property_id) VALUES(?,?,?)",
                           (lid, f"Piquete {lid}", property_id))
            con.commit()
        finally:
            con.close()

    def test_move_varios_animais_de_uma_vez(self):
        a = self.animal("T1", lote="P1")
        b = self.animal("T2", lote="P1")
        r = db.move_animals_bulk([a, b], "P2", HOJE.isoformat())
        self.assertEqual(sorted(r["movidos"]), ["T1", "T2"])
        self.assertEqual(r["ja_no_destino"], [])
        self.assertEqual(r["erros"], [])
        self.assertEqual(get_animal(a)["lote_id"], "P2")
        self.assertEqual(get_animal(b)["lote_id"], "P2")

    def test_animal_ja_no_destino_e_pulado_sem_erro(self):
        a = self.animal("T3", lote="P2")
        r = db.move_animals_bulk([a], "P2", HOJE.isoformat())
        self.assertEqual(r["movidos"], [])
        self.assertEqual(r["ja_no_destino"], ["T3"])

    def test_animal_inexistente_vira_erro_sem_derrubar_o_resto(self):
        a = self.animal("T4", lote="P1")
        r = db.move_animals_bulk([a, "NAO_EXISTE"], "P2", HOJE.isoformat())
        self.assertEqual(r["movidos"], ["T4"])
        self.assertEqual(r["erros"], ["NAO_EXISTE"])
        self.assertEqual(get_animal(a)["lote_id"], "P2")

    def test_cada_transferencia_grava_animal_movements(self):
        a = self.animal("T5", lote="P1")
        b = self.animal("T6", lote="P1")
        db.move_animals_bulk([a, b], "P2", HOJE.isoformat(), reason="separação",
                             operator="op1", notes="rodízio de pasto")
        movs_a = db.get_movements(a)
        self.assertEqual(len(movs_a), 1)
        self.assertEqual(movs_a[0]["from_lote_id"], "P1")
        self.assertEqual(movs_a[0]["to_lote_id"], "P2")
        self.assertEqual(movs_a[0]["reason"], "separação")


# ══════════════════════════════════════════════════════════════════════════════
class TestEstatisticasDoRebanho(BaseRegras):
    def test_stats_consideram_apenas_ativos(self):
        self.animal("S1", peso=400.0, peso_entrada=300.0, sexo="M")
        self.animal("S2", peso=500.0, peso_entrada=400.0, sexo="F")
        self.animal("S3", peso=600.0, peso_entrada=500.0, status="vendido")
        db.clear_cache()
        s = db.get_rebanho_stats()

        self.assertEqual(s.total, 2)              # o vendido não entra
        self.assertEqual(s.avg_weight, 450.0)
        self.assertEqual(s.total_kg, 900)
        self.assertEqual(s.males, 1)
        self.assertEqual(s.females, 1)
        # UA = peso ÷ 450: (400+500)/450 = 2,0
        self.assertEqual(s.total_ua, 2.0)
        # @ produzidas: ganho de 100 kg cada → 100×0,52÷15 = 3,47 @ → 6,94 → 6,9
        self.assertEqual(s.arrobas_prod, 6.9)
        # sem pesagens não há GMD; o campo vira 0, não None
        self.assertEqual(s.avg_gmd, 0)

    def test_sem_piquete_com_area_a_lotacao_e_zero(self):
        self.animal("S4", peso=450.0)
        db.clear_cache()
        s = db.get_rebanho_stats()
        self.assertEqual(s.total_area, 0)
        self.assertEqual(s.lotacao_ua_ha, 0)

    def test_rebanho_vazio_devolve_dicionario_vazio(self):
        """O contrato frágil (retornar {} que estourava KeyError) foi corrigido
        com a introdução da dataclass AnimalStats. Agora, rebanho vazio retorna
        um objeto com zeros.
        """
        s = db.get_rebanho_stats()
        self.assertEqual(s.total, 0)
        self.assertEqual(s.avg_weight, 0.0)
        self.assertEqual(s.arrobas_prod, 0.0)


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
