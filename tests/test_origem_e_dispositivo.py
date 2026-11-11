"""Origem da informação e aparelho de origem dos eventos gravados pela API (PNIB §6.2 e §14.1).

O evento tem de dizer de onde veio (§6.2: "origem da informação") e, na trilha, de qual aparelho
(§14.1). A API é o canal do app: toda escrita que passa por ela é origem `app`, com o aparelho
que o app declara em `X-Device-Id` (um UUID aleatório gerado na instalação). O web grava direto
pelos repositórios e continua `web`, sem aparelho.

O contexto é uma variável de contexto definida por requisição (`repositories/contexto.py`); o
teste de vazamento garante que o que vale para uma requisição não passa para a seguinte nem
para a escrita feita pelo web depois dela.
"""

import database as db
from repositories import eventos
from repositories.animais import get_animal
from repositories.conexao import _conn
from repositories.pesagens import WeighingCreate, add_weighing, get_weighing_history
from tests.test_backend_api import BackendApiTestCase

APARELHO = "a3f1c2d4-5b6e-4f70-8a9b-0c1d2e3f4a5b"
OUTRO_APARELHO = "0f9e8d7c-6b5a-4c3d-9e2f-1a0b9c8d7e6f"


class TestOrigemEDispositivo(BackendApiTestCase):
    def setUp(self):
        super().setUp()
        self.token = self._get_access_token()
        self.a1, self.a2 = [a["id"] for a in db.get_all_animals()[:2]]

    def _h(self, aparelho=APARELHO, chave=None):
        h = {"Authorization": f"Bearer {self.token}"}
        if aparelho is not None:
            h["X-Device-Id"] = aparelho
        if chave:
            h["Idempotency-Key"] = chave
        return h

    def _pesar(self, animal=None, aparelho=APARELHO, chave=None, peso=401.0):
        r = self.client.post(f"/animais/{animal or self.a1}/pesagens", headers=self._h(aparelho, chave),
                             json={"peso": peso, "data": "2026-10-20", "method": "pesado", "notes": "ctx"})
        self.assertEqual(r.status_code, 201, r.text)

    def _ultimo_evento(self, tipo):
        with _conn() as con:
            r = con.execute("SELECT * FROM animal_events WHERE tipo=? ORDER BY id DESC LIMIT 1", (tipo,)).fetchone()
        self.assertIsNotNone(r, f"nenhum evento '{tipo}'")
        return dict(r)

    def _eventos(self, tipo):
        with _conn() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM animal_events WHERE tipo=? ORDER BY id", (tipo,)).fetchall()]

    # -- o que a API grava ----------------------------------------------------------------

    def test_pesagem_pelo_app_grava_origem_app_e_o_aparelho(self):
        self._pesar()
        ev = self._ultimo_evento("pesagem")
        self.assertEqual((ev["origem_informacao"], ev["dispositivo"]), ("app", APARELHO))

    def test_aplicacao_e_movimentacao_pelo_app_tambem(self):
        r = self.client.post(f"/animais/{self.a1}/medicamentos", headers=self._h(), json={
            "medicamento": "Ivermectina", "dose": 5.0, "unidade": "ml", "via": "Subcutânea",
            "carencia_dias": 0, "data": "2026-10-20"})
        self.assertEqual(r.status_code, 201, r.text)
        lotes = [l["id"] for l in db.get_all_lotes()]
        origem = get_animal(self.a2)["lote_id"]
        destino = next(l for l in lotes if l != origem)
        r = self.client.post("/animais/movimentar", headers=self._h(), json={
            "animal_ids": [self.a2], "to_lote_id": str(destino), "movement_date": "2026-10-21"})
        self.assertEqual(r.status_code, 200, r.text)

        for tipo in ("manejo_sanitario", "mudanca_lote"):
            ev = self._ultimo_evento(tipo)
            self.assertEqual((ev["origem_informacao"], ev["dispositivo"]), ("app", APARELHO), tipo)

    def test_sem_o_cabecalho_a_origem_e_app_e_o_aparelho_fica_nulo(self):
        self._pesar(aparelho=None)
        ev = self._ultimo_evento("pesagem")
        self.assertEqual((ev["origem_informacao"], ev["dispositivo"]), ("app", None))

    def test_cabecalho_malformado_e_ignorado_e_a_escrita_segue(self):
        for ruim in ("curto", "tem espaco no meio do valor", "x" * 65, "<script>alert(1)</script>"):
            self._pesar(aparelho=ruim)
            ev = self._ultimo_evento("pesagem")
            self.assertIsNone(ev["dispositivo"], f"aceitou {ruim!r}")
            self.assertEqual(ev["origem_informacao"], "app")

    # -- o que não pode vazar -------------------------------------------------------------

    def test_o_contexto_nao_vaza_para_a_requisicao_seguinte_nem_para_o_web(self):
        self._pesar(aparelho=APARELHO)
        self._pesar(aparelho=None, peso=402.0)
        com, sem = self._eventos("pesagem")[-2:]
        self.assertEqual((com["dispositivo"], sem["dispositivo"]), (APARELHO, None))

        # O web grava direto pelo repositório, na mesma thread de teste, depois das requisições.
        add_weighing(WeighingCreate(animal_id=self.a2, weight=410.0, weigh_date="2026-10-22",
                                    operator="op", method="pesado", notes="web"))
        web = self._ultimo_evento("pesagem")
        self.assertEqual((web["origem_informacao"], web["dispositivo"]), ("web", None))

    # -- trilha de auditoria --------------------------------------------------------------

    def test_cancelar_pesagem_pelo_app_grava_origem_e_aparelho_na_auditoria(self):
        self._pesar()
        db.clear_cache()
        pesagem = [w for w in get_weighing_history(self.a1) if w["notes"] == "ctx"][0]
        r = self.client.post(f"/animais/{self.a1}/pesagens/{pesagem['id']}/cancelar", headers=self._h(),
                             json={"motivo": "animal errado"})
        self.assertEqual(r.status_code, 200, r.text)

        (linha,) = [t for t in eventos.trilha(entidade="weighings", entidade_id=str(pesagem["id"]))
                    if t["acao"] == "cancelar_pesagem"]
        self.assertEqual((linha["origem"], linha["dispositivo"]), ("app", APARELHO))
        # O evento de estorno que o cancelamento grava também sabe de onde veio.
        estorno = self._ultimo_evento("estorno")
        self.assertEqual((estorno["origem_informacao"], estorno["dispositivo"]), ("app", APARELHO))

    # -- reenvio --------------------------------------------------------------------------

    def test_reenvio_com_a_mesma_chave_nao_cria_outro_evento_e_guarda_o_primeiro_aparelho(self):
        self._pesar(chave="ctx-chave-1", aparelho=APARELHO)
        antes = len(self._eventos("pesagem"))
        self._pesar(chave="ctx-chave-1", aparelho=OUTRO_APARELHO)

        eventos_depois = self._eventos("pesagem")
        self.assertEqual(len(eventos_depois), antes)
        self.assertEqual(eventos_depois[-1]["dispositivo"], APARELHO)
