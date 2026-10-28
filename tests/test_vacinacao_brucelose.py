"""Vacinação contra brucelose e o registro oficial no SDA (plano, seção 14).

O AgroTop não registra nada no SDA: guarda o ato, a ficha dos animais e o ESTADO do registro
oficial, que só muda por confirmação humana. Para vacinação a partir de 01/01/2027 o lançamento
vale até o quinto dia do mês seguinte.
"""

import unittest
from datetime import date, timedelta

import database as db
from repositories import eventos, identificadores, vacinacao_brucelose as vb
from repositories.sanidade import get_medication_history
from repositories.vacinacao_brucelose import NovaVacinacao, VacinacaoInvalida
from services.recomendacoes import avaliar
from services.tratamento import TratamentoInvalido
from services.vacinacao_brucelose import (
    DadoInvalido, aviso_de_idade, exige_sda, normalizar_veterinario, prazo_sda, situacao_do_prazo,
)
from tests.test_regras_negocio import BaseRegras, HOJE


def _dia(n):
    return (HOJE + timedelta(days=n)).isoformat()


class TestPrazoDoSda(unittest.TestCase):
    def test_quinto_dia_do_mes_seguinte(self):
        self.assertEqual(prazo_sda("2027-01-15"), "2027-02-05")
        self.assertEqual(prazo_sda("2027-01-31"), "2027-02-05")
        self.assertEqual(prazo_sda("2027-01-01"), "2027-02-05", "o primeiro dia da exigência já conta")

    def test_vacinacao_de_dezembro_vence_em_janeiro_do_ano_seguinte(self):
        self.assertEqual(prazo_sda("2027-12-31"), "2028-01-05")

    def test_antes_de_2027_nao_ha_prazo(self):
        self.assertIsNone(prazo_sda("2026-12-31"))
        self.assertFalse(exige_sda("2026-12-31"))
        self.assertTrue(exige_sda("2027-01-01"))

    def test_data_invalida(self):
        for ruim in ("", "15/01/2027", "2027-13-01"):
            with self.assertRaises(DadoInvalido):
                prazo_sda(ruim)


class TestSituacaoDoPrazo(unittest.TestCase):
    def test_classifica(self):
        h = date(2027, 2, 1)
        self.assertEqual(situacao_do_prazo("pendente_sda", "2027-02-20", h), "no_prazo")
        self.assertEqual(situacao_do_prazo("pendente_sda", "2027-02-06", h), "vencendo")
        self.assertEqual(situacao_do_prazo("pendente_sda", "2027-02-05", h), "vencendo")
        self.assertEqual(situacao_do_prazo("pendente_sda", "2027-02-05", date(2027, 2, 5)), "vencendo",
                         "no dia ainda dá tempo")
        self.assertEqual(situacao_do_prazo("pendente_sda", "2027-02-05", date(2027, 2, 6)), "atrasado")
        self.assertEqual(situacao_do_prazo("pendente_sda", None, h), "sem_prazo")

    def test_registrada_ou_com_excecao_esta_cumprida_mesmo_atrasada(self):
        h = date(2027, 6, 1)
        self.assertEqual(situacao_do_prazo("registrado_sda", "2027-02-05", h), "cumprido")
        self.assertEqual(situacao_do_prazo("excecao", "2027-02-05", h), "cumprido")


class TestVeterinarioEAviso(unittest.TestCase):
    def test_nome_obrigatorio_e_uf_com_duas_letras(self):
        with self.assertRaises(DadoInvalido):
            normalizar_veterinario("  ")
        with self.assertRaises(DadoInvalido):
            normalizar_veterinario("Ana", uf="RIO")
        with self.assertRaises(DadoInvalido):
            normalizar_veterinario("Ana", uf="1S")
        r = normalizar_veterinario("  Ana   Souza ", " 12345 ", "rs")
        self.assertEqual(r, {"veterinario_nome": "Ana Souza", "veterinario_crmv": "12345",
                             "veterinario_uf": "RS"})

    def test_aviso_so_para_b19_fora_da_faixa(self):
        self.assertIsNone(aviso_de_idade("B19", 5))
        self.assertIsNone(aviso_de_idade("B19", 3))
        self.assertIsNone(aviso_de_idade("B19", 8))
        self.assertIn("fora da faixa", aviso_de_idade("Vacina B19", 14))
        self.assertIsNone(aviso_de_idade("RB51", 14))
        self.assertIsNone(aviso_de_idade("B19", None))


class BaseVacina(BaseRegras):
    def setUp(self):
        super().setUp()
        self.animal("F1", sexo="F", nascimento=_dia(-180))      # ~6 meses
        self.animal("F2", sexo="F", nascimento=_dia(-200))
        self.animal("M1", sexo="M")
        self.prop = self._sql_um("SELECT id FROM properties ORDER BY created_at LIMIT 1")["id"]

    def _sql_um(self, sql, args=()):
        with db._conn() as con:
            r = con.execute(sql, args).fetchone()
        return dict(r) if r else None

    def _nova(self, **kw):
        base = dict(property_id=self.prop, vacinado_em=_dia(0), animal_ids=["F1", "F2"],
                    produto="B19", veterinario_nome="Dra. Ana", veterinario_crmv="1234",
                    veterinario_uf="RS", lote_produto="L-77", validade_produto=_dia(200),
                    operator="op")
        base.update(kw)
        return NovaVacinacao(**base)

    def _eventos(self, aid):
        return [e for e in eventos.do_animal(self._uuid(aid)) if e["tipo"] == "vacinacao_brucelose"]

    def _contagem(self, tabela):
        return self._sql_um(f"SELECT COUNT(*) AS n FROM {tabela}")["n"]


class TestRegistrarVacinacao(BaseVacina):
    def test_registra_o_ato_as_aplicacoes_e_os_eventos_na_mesma_transacao(self):
        r = vb.registrar(self._nova())

        self.assertTrue(r["ok"])
        self.assertEqual(r["n"], 2)
        self.assertEqual(r["prazo_sda"], prazo_sda(_dia(0)))
        atos = vb.listar()
        self.assertEqual(len(atos), 1)
        self.assertEqual((atos[0]["status_oficial"], atos[0]["n_animais"], atos[0]["produto"]),
                         ("pendente_sda", 2, "B19"))
        self.assertEqual((atos[0]["veterinario_nome"], atos[0]["veterinario_crmv"], atos[0]["veterinario_uf"]),
                         ("Dra. Ana", "1234", "RS"))
        for aid in ("F1", "F2"):
            self.assertEqual(len(self._eventos(aid)), 1, aid)
            ap = get_medication_history(aid)[0]
            self.assertEqual((ap["medication_name"], ap["lote_produto"], ap["validade_produto"],
                              ap["withdrawal_days"]), ("Vacina brucelose B19", "L-77", _dia(200), 0))
            self.assertEqual(ap["evento_id"], self._eventos(aid)[0]["id"])

    def test_a_ficha_fotografa_brinco_identificador_oficial_e_registro_genealogico(self):
        identificadores.aplicar(self._uuid("F1"), "sisbov", "105123456789012")
        identificadores.aplicar(self._uuid("F1"), "registro_genealogico", "RGD-998")
        vb.registrar(self._nova())
        ficha = {x["brinco"]: x for x in vb.animais_da_vacinacao(vb.listar()[0]["id"])}
        self.assertEqual((ficha["F1"]["identificador_oficial"], ficha["F1"]["registro_genealogico"]),
                         ("105123456789012", "RGD-998"))
        self.assertEqual((ficha["F2"]["identificador_oficial"], ficha["F2"]["registro_genealogico"]),
                         (None, None))

    def test_baixa_o_estoque_uma_dose_por_animal(self):
        db.add_new_insumo(db.InsumoCreate("Vacina B19", "vacina", "ml", 100.0, 10.0, 1.0))
        insumo = self._sql_um("SELECT id FROM insumos WHERE name='Vacina B19'")["id"]
        vb.registrar(self._nova(insumo_id=insumo, dose=2.0))
        self.assertEqual(self._sql_um("SELECT current_stock FROM insumos WHERE id=?", (insumo,))["current_stock"],
                         96.0)

    def test_idade_fora_da_faixa_da_b19_avisa_mas_registra(self):
        self.animal("F3", sexo="F", nascimento=_dia(-600))
        r = vb.registrar(self._nova(animal_ids=["F3"]))
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["avisos"]), 1)
        self.assertIn("F3", r["avisos"][0])

    def test_recusas_nao_gravam_nada(self):
        antes = (self._contagem("vacinacoes_brucelose"), self._contagem("medications"))
        casos = [
            ("macho", dict(animal_ids=["F1", "M1"]), "fêmeas"),
            ("inexistente", dict(animal_ids=["F1", "XX"]), "não encontrado"),
            ("sem animais", dict(animal_ids=[]), "ao menos um"),
            ("data futura", dict(vacinado_em=_dia(3)), "futura"),
            ("sem veterinario", dict(veterinario_nome=" "), "veterinário"),
            ("dose zero", dict(dose=0), "dose"),
            ("propriedade inexistente", dict(property_id="nada"), "Propriedade"),
        ]
        for rotulo, kw, trecho in casos:
            with self.assertRaises(VacinacaoInvalida, msg=rotulo) as ctx:
                vb.registrar(self._nova(**kw))
            self.assertIn(trecho, str(ctx.exception), rotulo)
        # produto vencido: mesma regra do tratamento
        with self.assertRaises(TratamentoInvalido):
            vb.registrar(self._nova(validade_produto=_dia(-1)))
        self.assertEqual((self._contagem("vacinacoes_brucelose"), self._contagem("medications")), antes)

    def test_animal_de_outra_propriedade_e_animal_vendido_sao_recusados(self):
        self.animal("F4", sexo="F", status="vendido")
        with self.assertRaisesRegex(VacinacaoInvalida, "fora do rebanho"):
            vb.registrar(self._nova(animal_ids=["F4"]))
        with db._conn() as con:
            produtor = con.execute("SELECT produtor_id FROM properties WHERE id=?", (self.prop,)).fetchone()[0]
            con.execute("INSERT INTO properties (id, produtor_id, nome) VALUES('prop-outra', ?, 'Outra fazenda')",
                        (produtor,))
            con.execute("UPDATE animals SET property_id='prop-outra' WHERE id='F2'")
        with self.assertRaisesRegex(VacinacaoInvalida, "outra propriedade"):
            vb.registrar(self._nova(animal_ids=["F1", "F2"]))


class TestEstadoDoRegistroOficial(BaseVacina):
    def setUp(self):
        super().setUp()
        self.vid = vb.registrar(self._nova())["id"]

    def _ato(self):
        return [x for x in vb.listar(incluir_canceladas=True) if x["id"] == self.vid][0]

    def test_confirmar_exige_referencia_e_so_vale_uma_vez(self):
        with self.assertRaisesRegex(VacinacaoInvalida, "referência"):
            vb.confirmar_registro_sda(self.vid, "  ", "ana")
        self.assertEqual(self._ato()["status_oficial"], "pendente_sda")

        vb.confirmar_registro_sda(self.vid, " SDA-2027/00123 ", "ana")

        a = self._ato()
        self.assertEqual((a["status_oficial"], a["referencia_atestado"], a["confirmado_por"]),
                         ("registrado_sda", "SDA-2027/00123", "ana"))
        self.assertTrue(a["confirmado_em"])
        with self.assertRaisesRegex(VacinacaoInvalida, "já está"):
            vb.confirmar_registro_sda(self.vid, "outra", "ana")

    def test_excecao_exige_justificativa(self):
        with self.assertRaises(VacinacaoInvalida):
            vb.registrar_excecao(self.vid, "", "ana")
        vb.registrar_excecao(self.vid, "Vacinação anterior à exigência do SDA", "ana")
        a = self._ato()
        self.assertEqual((a["status_oficial"], a["justificativa_excecao"]),
                         ("excecao", "Vacinação anterior à exigência do SDA"))
        self.assertEqual(a["situacao_prazo"], "cumprido")

    def test_estado_muda_so_por_acao_e_deixa_trilha(self):
        vb.confirmar_registro_sda(self.vid, "REF-1", "ana")
        t = [x for x in eventos.trilha(entidade="vacinacoes_brucelose", entidade_id=self.vid)
             if x["acao"] == "confirmar_registro_sda"]
        self.assertEqual((len(t), t[0]["usuario"]), (1, "ana"))
        self.assertEqual(t[0]["registro_posterior"]["referencia_atestado"], "REF-1")

    def test_cancelar_desfaz_as_aplicacoes_e_devolve_o_estoque(self):
        db.add_new_insumo(db.InsumoCreate("Vacina B19", "vacina", "ml", 100.0, 10.0, 1.0))
        insumo = self._sql_um("SELECT id FROM insumos WHERE name='Vacina B19'")["id"]
        vid = vb.registrar(self._nova(insumo_id=insumo, animal_ids=["F1"]))["id"]
        self.assertEqual(self._sql_um("SELECT current_stock FROM insumos WHERE id=?", (insumo,))["current_stock"], 98.0)

        vb.cancelar(vid, "vacinei a vaca errada", "ana")

        self.assertEqual(self._sql_um("SELECT current_stock FROM insumos WHERE id=?", (insumo,))["current_stock"], 100.0)
        ap = [m for m in get_medication_history("F1") if m["insumo_id"] == insumo][0]
        self.assertTrue(ap["cancelada_em"])
        self.assertNotIn(vid, [x["id"] for x in vb.listar()])
        self.assertIn(vid, [x["id"] for x in vb.listar(incluir_canceladas=True)])
        with self.assertRaisesRegex(VacinacaoInvalida, "já foi cancelada"):
            vb.cancelar(vid, "de novo", "ana")

    def test_cancelar_exige_motivo_e_nao_cancela_registro_ja_confirmado_no_sda(self):
        with self.assertRaises(ValueError):
            vb.cancelar(self.vid, " ", "ana")
        vb.confirmar_registro_sda(self.vid, "REF-1", "ana")
        with self.assertRaisesRegex(VacinacaoInvalida, "no SDA"):
            vb.cancelar(self.vid, "erro", "ana")

    def test_nao_confirma_vacinacao_cancelada(self):
        vb.cancelar(self.vid, "erro", "ana")
        with self.assertRaisesRegex(VacinacaoInvalida, "cancelada"):
            vb.confirmar_registro_sda(self.vid, "REF", "ana")


class TestPendenciaERecomendacao(BaseVacina):
    def setUp(self):
        super().setUp()
        self.vid = vb.registrar(self._nova())["id"]

    def _prazo(self, dias_a_partir_de_hoje):
        with db._conn() as con:
            con.execute("UPDATE vacinacoes_brucelose SET prazo_sda=? WHERE id=?",
                        (_dia(dias_a_partir_de_hoje), self.vid))
        db.clear_cache()

    def _recs(self):
        return [r for r in avaliar(db.contexto_recomendacoes()) if r["regra"] == "vacinacao_sda_pendente"]

    def test_atrasada_e_alerta_alto(self):
        self._prazo(-3)
        recs = self._recs()
        self.assertEqual((len(recs), recs[0]["severidade"], recs[0]["dados"]["dias"]), (1, "alta", -3))
        self.assertIn("SDA", recs[0]["titulo"])
        self.assertEqual(vb.listar()[0]["situacao_prazo"], "atrasado")

    def test_perto_do_prazo_e_alerta_medio_e_longe_nao_alerta(self):
        self._prazo(4)
        self.assertEqual([r["severidade"] for r in self._recs()], ["media"])
        self._prazo(20)
        self.assertEqual(self._recs(), [])

    def test_confirmada_ou_sem_prazo_nao_alerta(self):
        self._prazo(-3)
        vb.confirmar_registro_sda(self.vid, "REF", "ana")
        db.clear_cache()
        self.assertEqual(self._recs(), [])
        self.assertEqual(vb.pendencias_sda(), [])

    def test_pendencias_listam_so_o_que_tem_prazo_e_esta_pendente(self):
        with db._conn() as con:
            con.execute("UPDATE vacinacoes_brucelose SET prazo_sda=NULL WHERE id=?", (self.vid,))
        self.assertEqual(vb.pendencias_sda(), [], "vacinação sem prazo (anterior à exigência) não pende")
        self._prazo(2)
        p = vb.pendencias_sda()
        self.assertEqual((len(p), p[0]["dias"], p[0]["n_animais"]), (1, 2, 2))

    def test_regra_com_contexto_sem_a_chave_nao_quebra(self):
        self.assertEqual([r for r in avaliar({"hoje": _dia(0)}) if r["regra"] == "vacinacao_sda_pendente"], [])
        self.assertEqual([r for r in avaliar({"vacinacoes_sda": "x"}) if r["regra"] == "vacinacao_sda_pendente"], [])


if __name__ == "__main__":
    unittest.main()
