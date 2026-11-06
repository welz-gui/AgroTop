"""Vacinação contra brucelose pela API (plano de rastreabilidade, seção 14).

O ato nasce `pendente_sda`; só uma pessoa o confirma, com a referência do atestado. Recusa não
grava nada (422); id inexistente é 404; ação que o estado não permite é 409 com código; a mesma
Idempotency-Key devolve a resposta guardada e não duplica o ato.
"""

from datetime import date, timedelta

import database as db
from repositories.sanidade import get_medications
from tests.test_backend_api import BackendApiTestCase


def _dia(n):
    return (date.today() - timedelta(days=n)).isoformat()


class TestVacinacaoBruceloseApi(BackendApiTestCase):
    def _headers(self, chave=None):
        # O login tem limite de 5 por 5 minutos: um token por teste.
        if not hasattr(self, "_token"):
            self._token = self._get_access_token()
        h = {"Authorization": f"Bearer {self._token}"}
        if chave:
            h["Idempotency-Key"] = chave
        return h

    def _femeas(self, n=2):
        return [a["id"] for a in db.get_all_animals() if a.get("sex") == "F"][:n]

    def _corpo(self, animais=None, **extra):
        corpo = {"animal_ids": animais if animais is not None else self._femeas(),
                 "data": _dia(1), "produto": "B19", "veterinario_nome": "Dra. Ana",
                 "veterinario_crmv": "12345", "veterinario_uf": "RS", "lote": "L-77"}
        corpo.update(extra)
        return corpo

    def _registrar(self, chave=None, **extra):
        r = self.client.post("/vacinacoes-brucelose", headers=self._headers(chave), json=self._corpo(**extra))
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def _lista(self, **params):
        r = self.client.get("/vacinacoes-brucelose", headers=self._headers(), params=params)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    # ── registrar ────────────────────────────────────────────────────────────
    def test_registrar_grava_o_ato_pendente_e_a_aplicacao_de_cada_animal(self):
        femeas = self._femeas()
        r = self._registrar()
        self.assertEqual(r["n"], len(femeas))
        self.assertIsNone(r["prazo_sda"], "antes de 01/01/2027 não há prazo exigido")

        ato = self._lista()[0]
        self.assertEqual(ato["id"], r["id"])
        self.assertEqual(ato["status_oficial"], "pendente_sda")
        self.assertEqual(ato["situacao_prazo"], "sem_prazo")
        self.assertEqual(ato["n_animais"], len(femeas))
        self.assertEqual((ato["produto"], ato["lote"], ato["veterinario_nome"], ato["veterinario_crmv"]),
                         ("B19", "L-77", "Dra. Ana", "12345"))
        self.assertEqual(ato["data"], _dia(1))
        db.clear_cache()
        for a in femeas:
            nomes = [m["medication_name"] for m in get_medications(a)]
            self.assertIn("Vacina brucelose B19", nomes, a)

    def test_a_data_do_ato_e_a_do_curral_e_nao_a_da_sincronizacao(self):
        self._registrar(data=_dia(9))
        self.assertEqual(self._lista()[0]["data"], _dia(9))

    def test_propriedade_vem_do_primeiro_animal_quando_nao_informada(self):
        self._registrar()
        animal = db.get_all_animals()[0]
        self.assertEqual(self._lista()[0]["property_id"], str(animal["property_id"]))

    def test_macho_na_selecao_recusa_tudo_e_nao_grava_nada(self):
        macho = [a["id"] for a in db.get_all_animals() if a.get("sex") == "M"][0]
        r = self.client.post("/vacinacoes-brucelose", headers=self._headers(),
                             json=self._corpo(animais=self._femeas(1) + [macho]))
        self.assertEqual(r.status_code, 422)
        self.assertIn("fêmeas", r.json()["detail"])
        self.assertEqual(self._lista(), [])

    def test_recusas_do_dado_sao_422(self):
        casos = {
            "sem animal": self._corpo(animais=[]),
            "animal inexistente": self._corpo(animais=["NAO_EXISTE"]),
            "sem veterinário": self._corpo(veterinario_nome=""),
            "data futura": self._corpo(data=(date.today() + timedelta(days=2)).isoformat()),
            "dose zero": self._corpo(dose=0),
            "vacina vencida": self._corpo(validade=_dia(30)),
            "propriedade que não é a dos animais": self._corpo(property_id="outra"),
        }
        for rotulo, corpo in casos.items():
            r = self.client.post("/vacinacoes-brucelose", headers=self._headers(), json=corpo)
            self.assertEqual(r.status_code, 422, f"{rotulo}: {r.text}")
        self.assertEqual(self._lista(), [], "nenhuma recusa grava algo")

    def test_sem_token_e_401(self):
        self.assertEqual(self.client.post("/vacinacoes-brucelose", json=self._corpo()).status_code, 401)
        self.assertEqual(self.client.get("/vacinacoes-brucelose").status_code, 401)

    def test_mesma_chave_nao_duplica_o_ato_e_devolve_a_mesma_resposta(self):
        a = self._registrar(chave="bru-1")
        b = self._registrar(chave="bru-1")
        self.assertEqual(a, b)
        self.assertEqual(len(self._lista()), 1)

    def test_mesma_chave_com_outro_conteudo_e_422(self):
        self._registrar(chave="bru-2")
        r = self.client.post("/vacinacoes-brucelose", headers=self._headers("bru-2"),
                             json=self._corpo(produto="RB51"))
        self.assertEqual(r.status_code, 422)
        self.assertEqual(len(self._lista()), 1)

    def test_b19_fora_da_idade_so_avisa(self):
        # Os animais do seed têm mais de 8 meses: o ato é aceito e o aviso volta no corpo.
        r = self._registrar()
        self.assertTrue(r["avisos"])

    # ── ler ──────────────────────────────────────────────────────────────────
    def test_detalhe_traz_a_ficha_dos_animais(self):
        femeas = self._femeas()
        vid = self._registrar()["id"]
        r = self.client.get(f"/vacinacoes-brucelose/{vid}", headers=self._headers())
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(sorted(a["brinco"] for a in r.json()["animais"]), sorted(femeas))
        self.assertEqual(r.json()["id"], vid)

    def test_detalhe_de_id_inexistente_e_404(self):
        r = self.client.get("/vacinacoes-brucelose/nao-existe", headers=self._headers())
        self.assertEqual(r.status_code, 404)

    # ── confirmar, exceção e cancelar ────────────────────────────────────────
    def test_confirmar_exige_a_referencia_e_so_uma_vez(self):
        vid = self._registrar()["id"]
        url = f"/vacinacoes-brucelose/{vid}/confirmar-sda"
        self.assertEqual(self.client.post(url, headers=self._headers(), json={"referencia": "  "}).status_code, 422)
        self.assertEqual(self._lista()[0]["status_oficial"], "pendente_sda", "sem referência nada muda")

        r = self.client.post(url, headers=self._headers(), json={"referencia": "SDA-2027-0042"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"status_oficial": "registrado_sda"})
        ato = self._lista()[0]
        self.assertEqual((ato["status_oficial"], ato["referencia_atestado"], ato["situacao_prazo"]),
                         ("registrado_sda", "SDA-2027-0042", "cumprido"))

        de_novo = self.client.post(url, headers=self._headers(), json={"referencia": "OUTRA"})
        self.assertEqual(de_novo.status_code, 409)
        self.assertEqual(de_novo.json()["detail"]["codigo"], "estado_da_vacinacao")

    def test_confirmar_com_a_mesma_chave_devolve_o_mesmo_resultado(self):
        vid = self._registrar()["id"]
        url = f"/vacinacoes-brucelose/{vid}/confirmar-sda"
        a = self.client.post(url, headers=self._headers("conf-1"), json={"referencia": "R1"})
        b = self.client.post(url, headers=self._headers("conf-1"), json={"referencia": "R1"})
        self.assertEqual((a.status_code, b.status_code), (200, 200))
        self.assertEqual(a.json(), b.json())

    def test_excecao_exige_justificativa(self):
        vid = self._registrar()["id"]
        url = f"/vacinacoes-brucelose/{vid}/excecao-sda"
        self.assertEqual(self.client.post(url, headers=self._headers(), json={"justificativa": ""}).status_code, 422)
        r = self.client.post(url, headers=self._headers(), json={"justificativa": "Vacinação anterior à exigência"})
        self.assertEqual(r.status_code, 200, r.text)
        ato = self._lista()[0]
        self.assertEqual((ato["status_oficial"], ato["justificativa_excecao"]),
                         ("excecao", "Vacinação anterior à exigência"))

    def test_cancelar_exige_motivo_tira_da_lista_e_devolve_a_aplicacao(self):
        femeas = self._femeas()
        vid = self._registrar()["id"]
        url = f"/vacinacoes-brucelose/{vid}/cancelar"
        self.assertEqual(self.client.post(url, headers=self._headers(), json={"motivo": ""}).status_code, 422)
        self.assertEqual(len(self._lista()), 1)

        r = self.client.post(url, headers=self._headers(), json={"motivo": "lançado em duplicidade"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"ok": True})
        self.assertEqual(self._lista(), [])
        canceladas = self._lista(incluir_canceladas="true")
        self.assertEqual([(c["cancelada"], c["situacao_prazo"], c["motivo_cancelamento"]) for c in canceladas],
                         [(True, "cancelada", "lançado em duplicidade")])
        db.clear_cache()
        for a in femeas:
            self.assertEqual([m for m in get_medications(a) if "brucelose" in m["medication_name"]], [], a)

        de_novo = self.client.post(url, headers=self._headers(), json={"motivo": "outra vez"})
        self.assertEqual(de_novo.status_code, 409)

    def test_depois_de_registrada_no_sda_o_cancelamento_e_409(self):
        vid = self._registrar()["id"]
        self.client.post(f"/vacinacoes-brucelose/{vid}/confirmar-sda", headers=self._headers(),
                         json={"referencia": "R1"})
        r = self.client.post(f"/vacinacoes-brucelose/{vid}/cancelar", headers=self._headers(),
                             json={"motivo": "engano"})
        self.assertEqual(r.status_code, 409)
        self.assertIn("SDA", r.json()["detail"]["mensagem"])
        self.assertEqual(len(self._lista()), 1)

    def test_acoes_em_id_inexistente_sao_404(self):
        for rota, corpo in (("confirmar-sda", {"referencia": "R"}), ("excecao-sda", {"justificativa": "j"}),
                            ("cancelar", {"motivo": "m"})):
            r = self.client.post(f"/vacinacoes-brucelose/nao-existe/{rota}", headers=self._headers(), json=corpo)
            self.assertEqual(r.status_code, 404, rota)
