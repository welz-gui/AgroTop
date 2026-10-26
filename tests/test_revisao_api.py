"""Listar, corrigir e cancelar pesagem e movimentação pela API (plano de rastreabilidade, Fase 2).

Mesmo desenho do tratamento: o original nunca some. Motivo obrigatório (422); registro de outro
animal ou inexistente é 404; repetir o cancelamento é 409 com código; movimentação que não é a
última é 422; a mesma Idempotency-Key devolve a resposta guardada.
"""

from datetime import date, timedelta

import database as db
from repositories.animais import get_animal, get_movements
from repositories.pesagens import get_weighing_history
from tests.test_backend_api import BackendApiTestCase


def _dia(n):
    return (date.today() - timedelta(days=n)).isoformat()


class TestRevisaoApi(BackendApiTestCase):
    def _headers(self, chave=None):
        h = {"Authorization": f"Bearer {self._get_access_token()}"}
        if chave:
            h["Idempotency-Key"] = chave
        return h

    def _animais(self):
        ids = [a["id"] for a in db.get_all_animals() if a.get("lote_id")]
        return ids[0], ids[1]

    def _pesar(self, animal, peso, dias_atras):
        r = self.client.post(f"/animais/{animal}/pesagens", headers=self._headers(),
                             json={"peso": peso, "data": _dia(dias_atras)})
        self.assertEqual(r.status_code, 201, r.text)
        db.clear_cache()
        return [w for w in get_weighing_history(animal) if w["weight"] == peso][0]["id"]

    def _peso_atual(self, animal):
        db.clear_cache()
        return get_animal(animal)["current_weight"]

    # ── pesagem ──────────────────────────────────────────────────────────────
    def test_lista_de_pesagens_traz_id_e_marca_a_de_entrada_como_nao_revisavel(self):
        a, _ = self._animais()
        db.add_animal(db.AnimalData(animal_id="ZZ0001", breed="Nelore", sex="M", birth_date=None,
                                    entry_date=_dia(30), entry_weight=300.0, target_weight=None,
                                    purchase_price=None, lote_id=None, fornecedor_id=None))
        w = self._pesar("ZZ0001", 320.0, 5)
        r = self.client.get("/animais/ZZ0001/pesagens", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        itens = r.json()
        self.assertEqual([i["peso"] for i in itens], [320.0, 300.0], "mais recente primeiro")
        self.assertEqual({i["id"]: i["revisavel"] for i in itens}[w], True)
        self.assertEqual([i["revisavel"] for i in itens if i["peso"] == 300.0], [False])

    def test_animal_inexistente_e_404_nas_listas(self):
        for rota in ("pesagens", "movimentacoes"):
            r = self.client.get(f"/animais/NAO_EXISTE/{rota}", headers=self._headers())
            self.assertEqual(r.status_code, 404, rota)

    def test_cancelar_pesagem_devolve_o_peso_anterior_e_sai_da_lista(self):
        a, _ = self._animais()
        antes = self._peso_atual(a)
        w = self._pesar(a, 777.0, 0)
        self.assertEqual(self._peso_atual(a), 777.0)

        r = self.client.post(f"/animais/{a}/pesagens/{w}/cancelar", headers=self._headers(),
                             json={"motivo": "animal errado"})

        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["peso_atual"], antes)
        self.assertIsNone(r.json()["pesagem_id"])
        lista = self.client.get(f"/animais/{a}/pesagens", headers=self._headers()).json()
        self.assertNotIn(w, [i["id"] for i in lista])

    def test_corrigir_pesagem_devolve_o_novo_peso_atual_e_o_id(self):
        a, _ = self._animais()
        w = self._pesar(a, 777.0, 0)
        r = self.client.post(f"/animais/{a}/pesagens/{w}/corrigir", headers=self._headers(),
                             json={"peso": 477.0, "data": _dia(0), "motivo": "zero a mais"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["peso_atual"], 477.0)
        self.assertNotEqual(r.json()["pesagem_id"], w)

    def test_pesagem_sem_motivo_outra_de_outro_animal_e_repeticao(self):
        a, b = self._animais()
        w = self._pesar(a, 777.0, 0)
        url = f"/animais/{a}/pesagens/{w}/cancelar"
        self.assertEqual(self.client.post(url, headers=self._headers(), json={"motivo": "  "}).status_code, 422)
        self.assertEqual(self.client.post(f"/animais/{b}/pesagens/{w}/cancelar", headers=self._headers(),
                                          json={"motivo": "erro"}).status_code, 404)
        self.assertEqual(self.client.post(url, headers=self._headers(), json={"motivo": "erro"}).status_code, 200)
        r = self.client.post(url, headers=self._headers(), json={"motivo": "de novo"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["codigo"], "registro_ja_cancelado")

    def test_pesagem_de_entrada_nao_se_cancela(self):
        db.add_animal(db.AnimalData(animal_id="ZZ0002", breed="Nelore", sex="M", birth_date=None,
                                    entry_date=_dia(30), entry_weight=300.0, target_weight=None,
                                    purchase_price=None, lote_id=None, fornecedor_id=None))
        entrada = self.client.get("/animais/ZZ0002/pesagens", headers=self._headers()).json()[0]["id"]
        r = self.client.post(f"/animais/ZZ0002/pesagens/{entrada}/cancelar", headers=self._headers(),
                             json={"motivo": "erro"})
        self.assertEqual(r.status_code, 422)

    def test_mesma_chave_devolve_a_resposta_guardada(self):
        a, _ = self._animais()
        w = self._pesar(a, 777.0, 0)
        url = f"/animais/{a}/pesagens/{w}/corrigir"
        corpo = {"peso": 477.0, "data": _dia(0), "motivo": "erro"}
        r1 = self.client.post(url, headers=self._headers("rev-peso-1"), json=corpo)
        r2 = self.client.post(url, headers=self._headers("rev-peso-1"), json=corpo)
        self.assertEqual((r1.status_code, r2.status_code), (200, 200))
        self.assertEqual(r1.json(), r2.json())
        corrigidas = [x for x in get_weighing_history(a) if x["corrige_id"] == w]
        self.assertEqual(len(corrigidas), 1)

    # ── movimentação ─────────────────────────────────────────────────────────
    def _mover(self, animal, destino, dias_atras=0):
        r = self.client.post("/animais/movimentar", headers=self._headers(), json={
            "animal_ids": [animal], "to_lote_id": destino, "movement_date": _dia(dias_atras)})
        self.assertEqual(r.status_code, 200, r.text)
        db.clear_cache()

    def _lotes_distintos(self, animal):
        atual = get_animal(animal)["lote_id"]
        outros = [l["id"] for l in db.get_all_lotes() if l["id"] != atual]
        return atual, outros[0], outros[1]

    def test_lista_de_movimentacoes_marca_so_a_ultima_como_revisavel(self):
        a, _ = self._animais()
        origem, p2, p3 = self._lotes_distintos(a)
        self._mover(a, p2, 5)
        self._mover(a, p3, 1)
        itens = self.client.get(f"/animais/{a}/movimentacoes", headers=self._headers()).json()
        recentes = [i for i in itens if i["data"] in (_dia(1), _dia(5))]
        self.assertEqual([(i["de"], i["para"], i["revisavel"]) for i in recentes],
                         [(p2, p3, True), (origem, p2, False)])

    def test_cancelar_movimentacao_devolve_o_animal_a_origem(self):
        a, _ = self._animais()
        origem, p2, _p3 = self._lotes_distintos(a)
        self._mover(a, p2, 1)
        m = get_movements(a)[0]["id"]

        r = self.client.post(f"/animais/{a}/movimentacoes/{m}/cancelar", headers=self._headers(),
                             json={"motivo": "piquete errado"})

        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["lote_atual"], origem)
        db.clear_cache()
        self.assertEqual(get_animal(a)["lote_id"], origem)

    def test_corrigir_movimentacao_leva_ao_destino_certo(self):
        a, _ = self._animais()
        origem, p2, p3 = self._lotes_distintos(a)
        self._mover(a, p2, 1)
        m = get_movements(a)[0]["id"]

        r = self.client.post(f"/animais/{a}/movimentacoes/{m}/corrigir", headers=self._headers(), json={
            "to_lote_id": p3, "movement_date": _dia(1), "motivo": "era o outro"})

        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["lote_atual"], p3)
        self.assertNotEqual(r.json()["movimentacao_id"], m)
        db.clear_cache()
        self.assertEqual(get_animal(a)["lote_id"], p3)
        self.assertEqual(get_movements(a)[0]["corrige_id"], m)

    def test_movimentacao_que_nao_e_a_ultima_sem_motivo_e_destino_igual_a_origem(self):
        a, _ = self._animais()
        origem, p2, p3 = self._lotes_distintos(a)
        self._mover(a, p2, 5)
        primeira = get_movements(a)[0]["id"]
        self._mover(a, p3, 1)
        ultima = get_movements(a)[0]["id"]
        h = self._headers()
        # Não é a última: 422 e nada muda.
        r = self.client.post(f"/animais/{a}/movimentacoes/{primeira}/cancelar", headers=h, json={"motivo": "erro"})
        self.assertEqual(r.status_code, 422)
        # Sem motivo.
        r = self.client.post(f"/animais/{a}/movimentacoes/{ultima}/cancelar", headers=h, json={"motivo": " "})
        self.assertEqual(r.status_code, 422)
        # Destino igual à origem na correção: é cancelar.
        r = self.client.post(f"/animais/{a}/movimentacoes/{ultima}/corrigir", headers=h, json={
            "to_lote_id": p2, "movement_date": _dia(1), "motivo": "erro"})
        self.assertEqual(r.status_code, 422)
        db.clear_cache()
        self.assertEqual(get_animal(a)["lote_id"], p3)

    def test_movimentacao_de_outro_animal_e_404_e_repetir_o_cancelamento_e_409(self):
        a, b = self._animais()
        _origem, p2, _p3 = self._lotes_distintos(a)
        self._mover(a, p2, 1)
        m = get_movements(a)[0]["id"]
        h = self._headers()
        self.assertEqual(self.client.post(f"/animais/{b}/movimentacoes/{m}/cancelar", headers=h,
                                          json={"motivo": "erro"}).status_code, 404)
        self.assertEqual(self.client.post(f"/animais/{a}/movimentacoes/{m}/cancelar", headers=h,
                                          json={"motivo": "erro"}).status_code, 200)
        r = self.client.post(f"/animais/{a}/movimentacoes/{m}/cancelar", headers=h, json={"motivo": "de novo"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["codigo"], "registro_ja_cancelado")
