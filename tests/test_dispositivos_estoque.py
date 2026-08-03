"""Estoque de dispositivos (ADR 0004 · B7 · PNIB §5).

A regra de faixas é `services/dispositivos.py` (spec 0026) e a máquina de doze
estados é `services/estados_dispositivo.py` — ambas puras e testadas à parte.
Aqui é a **ligação**: que a máquina é chamada antes de gravar, que aplicar baixa
o estoque **e** cria o identificador, e que reimportar não duplica.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402
from repositories import dispositivos, eventos, identificadores  # noqa: E402


class BaseB7(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "b7.db"))
        db.init_db()
        db.clear_cache()
        dispositivos.importar_lote("BR1001", "BR1010", lote="L1",
                                   fabricante="Allflex", usuario="op1")
        db.clear_cache()
        self.animal = db.get_all_animals(status="ativo")[0]

    def _disp(self, codigo="BR1001"):
        return dispositivos.por_codigo(codigo)

    _seq = 0

    def _animal_sem_manejo(self):
        """Um animal sem brinco vigente.

        O seed migra o brinco de TODOS os animais para `animal_identifiers`
        (etapa B1.3), então não existe animal sem `manejo` — é preciso criar um
        e encerrar o vínculo. Sem isso, toda aplicação seria troca de brinco.
        """
        BaseB7._seq += 1
        brinco = f"NOVO{BaseB7._seq}"
        db.add_animal(brinco, "Nelore", "M", None, "2026-01-01",
                      300.0, 500.0, 1000.0, None, None)
        db.clear_cache()
        uuid = [a for a in db.get_all_animals(status=None)
                if a["id"] == brinco][0]["uuid"]
        if identificadores.get_ativo(uuid, "manejo"):
            identificadores.remover(uuid, "manejo", "preparo de teste")
            db.clear_cache()
        return uuid

    def _linhas(self, sql, args=()):
        con = sqlite3.connect(db.DB_PATH)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args).fetchall()]
        finally:
            con.close()


class TestImportacaoDeLote(BaseB7):
    def test_importa_a_faixa_inteira(self):
        self.assertEqual(len(self._linhas("SELECT id FROM dispositivos")), 10)

    def test_reimportar_nao_duplica(self):
        """Reimportar o mesmo arquivo é acidente comum — não pode duplicar."""
        r = dispositivos.importar_lote("BR1001", "BR1010", lote="L1", usuario="op1")
        self.assertEqual(r["criados"], 0)
        self.assertEqual(r["pulados"], 10)
        self.assertEqual(len(self._linhas("SELECT id FROM dispositivos")), 10)

    def test_faixa_invalida_e_recusada(self):
        r = dispositivos.importar_lote("BR1001", "MT1010", lote="L2")
        self.assertFalse(r["ok"])

    def test_importacao_e_auditada(self):
        t = eventos.trilha(entidade="dispositivos", entidade_id="L1")
        self.assertTrue(t, "importação de lote não foi auditada")


class TestMaquinaDeEstadosLigada(BaseB7):
    """§5.2 — a máquina é mesmo chamada antes de gravar?"""

    def test_transicao_valida_passa(self):
        d = self._disp()
        r = dispositivos.mudar_status(d["id"], "reservado", usuario="op1")
        self.assertTrue(r["ok"], r)
        self.assertEqual(self._disp()["status"], "reservado")

    def test_transicao_invalida_e_recusada_e_nao_grava(self):
        d = self._disp()
        dispositivos.mudar_status(d["id"], "inutilizado",
                                  motivo="brinco quebrou na aplicação", usuario="op1")
        db.clear_cache()
        # `inutilizado` é definitivo — não volta para disponível.
        r = dispositivos.mudar_status(d["id"], "disponivel", usuario="op1")
        self.assertFalse(r["ok"])
        atual = self._linhas("SELECT status FROM dispositivos WHERE id=?",
                             (d["id"],))[0]["status"]
        self.assertEqual(atual, "inutilizado",
                         "estado mudou apesar de a transição ser recusada")

    def test_inutilizar_exige_motivo(self):
        d = self._disp()
        r = dispositivos.mudar_status(d["id"], "inutilizado", usuario="op1")
        self.assertFalse(r["ok"])
        self.assertTrue(r["exige_motivo"])
        self.assertEqual(self._disp()["status"], "disponivel")

    def test_bloqueado_pelo_orgao_so_sai_com_autorizacao(self):
        d = self._disp()
        dispositivos.mudar_status(d["id"], "bloqueado_orgao",
                                  motivo="bloqueio recebido do órgão", usuario="op1")
        db.clear_cache()
        sem = dispositivos.mudar_status(d["id"], "disponivel", usuario="op1")
        self.assertFalse(sem["ok"])
        self.assertTrue(sem["exige_autorizacao"])

        com = dispositivos.mudar_status(d["id"], "disponivel", usuario="admin",
                                        tem_autorizacao=True)
        self.assertTrue(com["ok"], com)

    def test_mudanca_e_auditada_com_antes_e_depois(self):
        d = self._disp()
        dispositivos.mudar_status(d["id"], "perdido",
                                  motivo="caiu no pasto", usuario="op1")
        t = eventos.trilha(entidade="dispositivos", entidade_id=d["id"])
        self.assertTrue(t)
        self.assertEqual(t[0]["registro_anterior"], {"status": "disponivel"})
        self.assertEqual(t[0]["registro_posterior"], {"status": "perdido"})
        self.assertIn("caiu no pasto", t[0]["motivo"])


class TestAplicacao(BaseB7):
    """Aplicar faz DUAS coisas que precisam andar juntas."""

    def test_baixa_o_estoque_e_cria_o_identificador(self):
        """Primeira aplicação: animal sem brinco de manejo vigente."""
        d = self._disp()
        sem_brinco = self._animal_sem_manejo()
        r = dispositivos.aplicar(d["id"], sem_brinco, aplicador="op1")
        self.assertTrue(r["ok"], r)

        self.assertEqual(self._linhas(
            "SELECT status FROM dispositivos WHERE id=?", (d["id"],))[0]["status"],
            "aplicado")
        ident = identificadores.get_ativo(sem_brinco, "manejo")
        self.assertIsNotNone(ident, "dispositivo aplicado sem identificador no animal")
        self.assertEqual(ident["valor"], "BR1001")

    def test_animal_que_ja_tem_brinco_exige_motivo_de_troca(self):
        """§4.2.3: trocar brinco é encerrar o anterior, não somar um segundo.

        Sem isto o animal ficaria com dois `manejo` vigentes e ninguém saberia
        qual vale.
        """
        d = self._disp()
        r = dispositivos.aplicar(d["id"], self.animal["uuid"], aplicador="op1")
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("exige_motivo_substituicao"))
        self.assertEqual(self._disp()["status"], "disponivel",
                         "estoque baixado sem o identificador ter sido criado")

    def test_troca_com_motivo_encerra_o_anterior(self):
        d = self._disp()
        antigo = identificadores.get_ativo(self.animal["uuid"], "manejo")["valor"]
        r = dispositivos.aplicar(d["id"], self.animal["uuid"], aplicador="op1",
                                 motivo_substituicao="brinco anterior ilegível")
        self.assertTrue(r["ok"], r)

        vigente = identificadores.get_ativo(self.animal["uuid"], "manejo")
        self.assertEqual(vigente["valor"], "BR1001")
        historico = [i["valor"] for i in
                     identificadores.get_identificadores(self.animal["uuid"])]
        self.assertIn(antigo, historico, "o brinco anterior sumiu do histórico")

    def test_gera_evento_no_animal(self):
        d = self._disp()
        alvo = self._animal_sem_manejo()
        dispositivos.aplicar(d["id"], alvo, aplicador="op1")
        self.assertIn("aplicacao_dispositivo",
                      [e["tipo"] for e in eventos.do_animal(alvo)])

    def test_animal_inexistente_nao_baixa_o_estoque(self):
        d = self._disp()
        r = dispositivos.aplicar(d["id"], "uuid-que-nao-existe")
        self.assertFalse(r["ok"])
        self.assertEqual(self._disp()["status"], "disponivel",
                         "estoque foi baixado para um animal que não existe")

    def test_dispositivo_ja_aplicado_nao_reaplica(self):
        d = self._disp()
        dispositivos.aplicar(d["id"], self.animal["uuid"], aplicador="op1")
        db.clear_cache()
        outro = db.get_all_animals(status="ativo")[1]
        r = dispositivos.aplicar(d["id"], outro["uuid"])
        self.assertFalse(r["ok"])

    def test_divergencia_registra_mas_nao_bloqueia(self):
        """§5.3: divergência é alerta. Recusar travaria o trabalho no curral."""
        d = self._disp()
        r = dispositivos.aplicar(d["id"], self._animal_sem_manejo(),
                                 aplicador="op1", eletronico_lido="999999")
        self.assertTrue(r["ok"], "divergência virou bloqueio")
        self.assertTrue(r["alerta"])
        self.assertEqual(self._linhas("SELECT divergencia FROM dispositivos "
                                      "WHERE id=?", (d["id"],))[0]["divergencia"],
                         "codigos_divergentes")

    def test_codigos_iguais_nao_geram_divergencia(self):
        d = self._disp()
        r = dispositivos.aplicar(d["id"], self._animal_sem_manejo(),
                                 aplicador="op1", eletronico_lido="BR1001")
        self.assertTrue(r["ok"])
        self.assertIsNone(r["divergencia"])


class TestInventario(BaseB7):
    def test_conta_por_estado(self):
        d = self._disp()
        dispositivos.aplicar(d["id"], self._animal_sem_manejo(), aplicador="op1")
        db.clear_cache()
        inv = dispositivos.inventario()
        self.assertEqual(inv["aplicados"], 1)
        self.assertEqual(inv["em_estoque"], 9)

    def test_conta_perdidos_e_danificados_juntos(self):
        for cod, novo in (("BR1002", "perdido"), ("BR1003", "danificado")):
            dispositivos.mudar_status(self._disp(cod)["id"], novo,
                                      motivo="ocorrência de campo", usuario="op1")
            db.clear_cache()
        self.assertEqual(dispositivos.inventario()["perdidos_ou_danificados"], 2)

    def test_lista_divergencias(self):
        d = self._disp()
        dispositivos.aplicar(d["id"], self._animal_sem_manejo(),
                             eletronico_lido="000")
        db.clear_cache()
        self.assertEqual(len(dispositivos.inventario()["divergencias"]), 1)

    def test_agrupa_por_lote(self):
        inv = dispositivos.inventario()
        l1 = [x for x in inv["por_lote"] if x["lote"] == "L1"][0]
        self.assertEqual(l1["total"], 10)
        self.assertEqual(l1["em_estoque"], 10)


if __name__ == "__main__":
    unittest.main()
