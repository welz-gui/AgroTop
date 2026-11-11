"""Aceite offline: dez eventos feitos sem sinal aparecem uma única vez depois da reconexão.

Plano de 9 de novembro (seção 15.2 do plano corrigido). O app guarda cada evento com uma
Idempotency-Key e o reenvia com a MESMA chave até receber a confirmação. O que pode dar errado é
a resposta se perder: o servidor gravou, o app não soube e reenvia. Aqui a API real (SQLite)
recebe dez eventos nessas condições e o estado final é conferido linha a linha:

- cada evento existe uma vez, com o seu evento de rastreabilidade (`evento_id` 1 para 1);
- a data de OCORRÊNCIA é a que o operador informou no curral, não a do reenvio;
- o usuário é o de quem sincronizou, a origem é `app` e o aparelho é o que o app declarou;
- a aplicação retroativa guarda o piquete da DATA dela, mesmo com o animal já movido;
- a repetição devolve a mesma resposta e nenhuma chave fica presa em andamento.

O que este teste NÃO prova: a propriedade (os lotes do seed são todos da mesma), e que o autor é
quem registrou no curral e não quem sincronizou (é o dono do token da sincronização).
"""

import database as db
from repositories.conexao import _conn
from tests.test_backend_api import BackendApiTestCase

USUARIO = "testuser"
APARELHO = "a3f1c2d4-5b6e-4f70-8a9b-0c1d2e3f4a5b"
MARCA = "aceite-offline"
# Ocorreram em outubro; a sincronização é "agora". Se confundir as duas, o teste pega.
DATAS = {
    "pesagem": ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15"],
    "aplicacao": ["2026-10-16", "2026-10-17", "2026-10-18"],
    "mov": ["2026-10-25", "2026-10-26"],
    "aplicacao_retroativa": "2026-10-10",
}


class TestAceiteOffline(BackendApiTestCase):
    def setUp(self):
        super().setUp()
        self.token = self._get_access_token()
        self.animais = [a["id"] for a in db.get_all_animals()]
        self.assertGreaterEqual(len(self.animais), 10)
        self.uuid_para_id = {a["uuid"]: a["id"] for a in db.get_all_animals()}
        self.fila = self._montar_fila()

    # -- a fila do curral, na ordem em que o operador registrou ---------------------------

    def _lote_do(self, animal_id):
        with _conn() as con:
            return con.execute("SELECT lote_id FROM animals WHERE id=?", (animal_id,)).fetchone()["lote_id"]

    def _montar_fila(self):
        a = self.animais
        fila = []

        def item(tipo, animal, url, corpo):
            n = len(fila)
            fila.append({"n": n, "tipo": tipo, "animal": animal, "url": url,
                         "chave": f"{MARCA}-chave-{n}", "corpo": corpo})

        for i, data in enumerate(DATAS["pesagem"]):
            item("pesagem", a[i], f"/animais/{a[i]}/pesagens",
                 {"peso": 380.0 + i, "data": data, "method": "pesado", "notes": f"{MARCA}-{len(fila)}"})
        for i, data in enumerate(DATAS["aplicacao"]):
            animal = a[4 + i]
            item("aplicacao", animal, f"/animais/{animal}/medicamentos",
                 {"medicamento": "Ivermectina 1%", "dose": 8.0, "unidade": "ml", "via": "Subcutânea",
                  "carencia_dias": 7, "data": data, "notas": f"{MARCA}-{len(fila)}"})
        # Dois animais trocam de piquete; o de índice 8 também ganha uma aplicação RETROATIVA,
        # registrada depois da movimentação mas com data anterior a ela.
        for i, (animal, destino) in enumerate([(a[8], "P04"), (a[9], "P02")]):
            origem = self._lote_do(animal)
            self.assertNotEqual(origem, destino)
            item("mov", animal, "/animais/movimentar",
                 {"animal_ids": [animal], "to_lote_id": destino, "movement_date": DATAS["mov"][i],
                  "reason": "manejo", "notes": f"{MARCA}-{len(fila)}", "lote_origem_esperado": origem})
            fila[-1]["origem"] = origem
            fila[-1]["destino"] = destino
        item("aplicacao_retroativa", a[8], f"/animais/{a[8]}/medicamentos",
             {"medicamento": "Aftosa", "dose": 2.0, "unidade": "ml", "via": "Subcutânea",
              "carencia_dias": 0, "data": DATAS["aplicacao_retroativa"], "notas": f"{MARCA}-{len(fila)}"})
        fila[-1]["origem_do_piquete"] = fila[7]["origem"]
        self.assertEqual(len(fila), 10)
        return fila

    def _enviar(self, it):
        h = {"Authorization": f"Bearer {self.token}", "Idempotency-Key": it["chave"], "X-Device-Id": APARELHO}
        r = self.client.post(it["url"], json=it["corpo"], headers=h)
        self.assertIn(r.status_code, (200, 201), f"{it['chave']}: {r.status_code} {r.text}")
        return r.status_code, r.json()

    def _contagens(self):
        with _conn() as con:
            return {t: con.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                    for t in ("weighings", "medications", "animal_movements", "animal_events")}

    def _linhas(self, tabela, campo_marca):
        with _conn() as con:
            return [dict(r) for r in con.execute(
                f"SELECT * FROM {tabela} WHERE {campo_marca} LIKE ? ORDER BY id", (f"{MARCA}-%",)).fetchall()]

    def _evento(self, evento_id):
        with _conn() as con:
            r = con.execute("SELECT * FROM animal_events WHERE id=?", (evento_id,)).fetchone()
        self.assertIsNotNone(r, f"evento {evento_id} não existe")
        return dict(r)

    # -- o cenário -------------------------------------------------------------------------

    def test_dez_eventos_offline_aparecem_uma_vez_depois_da_reconexao(self):
        antes = self._contagens()
        with _conn() as con:
            meds_antes = {a: con.execute(
                "SELECT COUNT(*) AS n FROM medications m JOIN animals x ON x.uuid=m.animal_uuid WHERE x.id=?",
                (a,)).fetchone()["n"] for a in self.animais}

        # 1) A conexão volta instável: chegam os seis primeiros e a resposta do 3º e do 5º se perde.
        perdidas = {2, 4}
        primeira = {}
        for it in self.fila[:6]:
            resposta = self._enviar(it)
            if it["n"] not in perdidas:
                primeira[it["n"]] = resposta

        # 2) Reconexão: o app reenvia o que não confirmou (os dois perdidos e os quatro restantes).
        segunda = {it["n"]: self._enviar(it) for it in self.fila if it["n"] not in primeira}
        self.assertEqual(sorted(segunda), [2, 4, 6, 7, 8, 9])

        # 3) O app fechou antes de esvaziar a fila: reenvia os dez.
        terceira = {it["n"]: self._enviar(it) for it in self.fila}

        # A repetição devolve exatamente a resposta guardada.
        for n, resposta in {**primeira, **segunda}.items():
            self.assertEqual(terceira[n], resposta, f"resposta do item {n} mudou no reenvio")

        # Nenhuma linha a mais: 4 pesagens + 4 aplicações + 2 movimentações, e um evento para cada.
        depois = self._contagens()
        self.assertEqual(depois["weighings"] - antes["weighings"], 4)
        self.assertEqual(depois["medications"] - antes["medications"], 4)
        self.assertEqual(depois["animal_movements"] - antes["animal_movements"], 2)
        self.assertEqual(depois["animal_events"] - antes["animal_events"], 10)

        pesagens = self._linhas("weighings", "notes")
        aplicacoes = self._linhas("medications", "notes")
        movimentos = self._linhas("animal_movements", "notes")
        self.assertEqual((len(pesagens), len(aplicacoes), len(movimentos)), (4, 4, 2))

        # Cada linha guarda a data de ocorrência informada, o usuário e o seu próprio evento.
        eventos_vistos = set()

        def confere(linha, campo_data, campo_usuario, it, tipo_evento=None):
            data = it["corpo"].get("data") or it["corpo"].get("movement_date")
            self.assertEqual(linha[campo_data], data, f"data de ocorrência do item {it['n']}")
            self.assertEqual(linha[campo_usuario], USUARIO)
            self.assertEqual(self.uuid_para_id[linha["animal_uuid"]], it["animal"])
            ev = self._evento(linha["evento_id"])
            self.assertNotIn(ev["id"], eventos_vistos, "dois registros apontam para o mesmo evento")
            eventos_vistos.add(ev["id"])
            self.assertEqual(ev["animal_uuid"], linha["animal_uuid"])
            self.assertTrue(ev["ocorrido_em"].startswith(data), f"{ev['ocorrido_em']} != {data}")
            self.assertGreater(ev["registrado_em"][:10], data, "registrado_em deve ser o da sincronização")
            self.assertEqual(ev["usuario_registro"], USUARIO)
            self.assertEqual((ev["origem_informacao"], ev["dispositivo"]), ("app", APARELHO))
            if tipo_evento:
                self.assertEqual(ev["tipo"], tipo_evento)
            return ev

        por_nota = lambda linhas, campo="notes": {int(l[campo].rsplit("-", 1)[1]): l for l in linhas}  # noqa: E731
        for n, linha in por_nota(pesagens).items():
            confere(linha, "weigh_date", "operator", self.fila[n], "pesagem")
            self.assertEqual(linha["weight"], self.fila[n]["corpo"]["peso"])
        apl = por_nota(aplicacoes)
        for n, linha in apl.items():
            confere(linha, "med_date", "applied_by", self.fila[n])
        mov = por_nota(movimentos)
        for n, linha in mov.items():
            confere(linha, "movement_date", "operator", self.fila[n], "mudanca_lote")
            self.assertEqual(linha["from_lote_id"], self.fila[n]["origem"])
            self.assertEqual(linha["to_lote_id"], self.fila[n]["destino"])
        self.assertEqual(len(eventos_vistos), 10)

        # O animal está no piquete de destino, e a aplicação retroativa guarda o da DATA dela
        # (a origem), não o de hoje.
        for n in (7, 8):
            self.assertEqual(self._lote_do(self.fila[n]["animal"]), self.fila[n]["destino"])
        retro = apl[9]
        self.assertEqual(retro["lote_id"], self.fila[9]["origem_do_piquete"])
        self.assertNotEqual(retro["lote_id"], self.fila[7]["destino"])

        # O que o web e o app leem: cada aplicação aparece uma vez no histórico do animal.
        db.clear_cache()
        h = {"Authorization": f"Bearer {self.token}"}
        for n in (4, 5, 6, 9):
            animal = self.fila[n]["animal"]
            lista = self.client.get(f"/animais/{animal}/medicamentos", headers=h).json()["aplicacoes"]
            novas = [x for x in lista if x["data"] == self.fila[n]["corpo"]["data"]
                     and x["medicamento"] == self.fila[n]["corpo"]["medicamento"]]
            self.assertEqual(len(novas), 1, f"item {n} aparece {len(novas)} vezes")
        retro_api = [x for x in self.client.get(
            f"/animais/{self.fila[9]['animal']}/medicamentos", headers=h).json()["aplicacoes"]
            if x["data"] == DATAS["aplicacao_retroativa"]]
        self.assertEqual(retro_api[0]["piquete_id"], self.fila[9]["origem_do_piquete"])

        # Nenhuma chave ficou presa: as dez estão concluídas.
        with _conn() as con:
            estados = [r["estado"] for r in con.execute(
                "SELECT estado FROM api_idempotency_keys WHERE idempotency_key LIKE ?", (f"{MARCA}-chave-%",)
            ).fetchall()]
        self.assertEqual(estados, ["concluida"] * 10)
