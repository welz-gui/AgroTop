"""Protocolos sanitários de ponta a ponta: plano, campanha e ciclo de repetição.

Achado real: `repositories/sanidade.py` usava `_FREQ_DAYS`, `_protocol_eligible` e
`get_age_months` sem importá-los (ficaram em `database.py` quando as funções
migraram para o repositório). `get_protocol_plan` e `apply_protocol_campaign` —
chamadas por `app.py` na aba de protocolos — levantavam NameError, e nenhum teste
as exercitava. Estes testes travam o caminho inteiro.
"""

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402
from repositories.animais import add_animal  # noqa: E402
from repositories.sanidade import (  # noqa: E402
    ProtocolData, add_protocol, apply_protocol_campaign, get_medications,
    get_protocol_plan, get_protocols,
)

HOJE = date.today()


def _iso(dias_atras: int) -> str:
    return (HOJE - timedelta(days=dias_atras)).isoformat()


class TestProtocoloSanitario(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "protocolo.db"))
        db.init_db()
        db.clear_cache()
        lote = db.get_all_lotes()[0]["id"]
        # Os seeds de demonstração também entram no plano; os testes olham só
        # para os animais criados aqui.
        for aid, sexo, nasc in [
            ("PRT_M_JOVEM", "M", _iso(300)),        # ~10 meses: elegível
            ("PRT_F_JOVEM", "F", _iso(300)),        # fêmea: fora do sex_target
            ("PRT_M_VELHO", "M", _iso(365 * 5)),    # ~60 meses: acima do age_max
            ("PRT_M_SEM_IDADE", "M", None),         # sem nascimento
        ]:
            add_animal(db.AnimalData(aid, "Nelore", sexo, nasc, _iso(30),
                                     300.0, 500.0, 2000.0, lote, None))
        db.clear_cache()

    def _protocolo(self, frequencia="anual"):
        add_protocol(ProtocolData(
            name=f"Aftosa {frequencia}", sex_target="M", age_min=6, age_max=24,
            dose_value=2.0, dose_ref_kg=0, dose_unit="ml", insumo_id=None,
            frequency=frequencia, withdrawal_days=0))
        db.clear_cache()
        return next(p for p in get_protocols(active_only=False)
                    if p["name"] == f"Aftosa {frequencia}")

    def _pendentes(self, plano):
        return {a["id"] for a in plano["pending"]}

    def test_plano_filtra_por_sexo_e_idade(self):
        plano = get_protocol_plan(self._protocolo())

        pend = self._pendentes(plano)
        self.assertIn("PRT_M_JOVEM", pend)
        self.assertNotIn("PRT_F_JOVEM", pend)
        self.assertNotIn("PRT_M_VELHO", pend)
        self.assertNotIn("PRT_M_SEM_IDADE", pend)
        self.assertGreaterEqual(plano["idade_desconhecida"], 1)
        self.assertGreaterEqual(plano["n_eligible"], plano["n_pending"])
        self.assertEqual(plano["doses_needed"], round(2.0 * plano["n_pending"], 2))

    def test_campanha_aplica_e_zera_a_pendencia(self):
        prot = self._protocolo()

        r = apply_protocol_campaign(prot["id"], HOJE.isoformat(), operator="op1")
        db.clear_cache()

        self.assertGreaterEqual(r["n"], 1)
        aplicadas = [m for m in get_medications("PRT_M_JOVEM")
                     if m["protocol_id"] == prot["id"]]
        self.assertEqual(len(aplicadas), 1)
        self.assertEqual(aplicadas[0]["med_date"], HOJE.isoformat())
        self.assertNotIn("PRT_M_JOVEM", self._pendentes(get_protocol_plan(prot)))

    def test_ciclo_anual_vencido_volta_a_ficar_pendente(self):
        prot = self._protocolo("anual")
        apply_protocol_campaign(prot["id"], _iso(400))
        db.clear_cache()

        self.assertIn("PRT_M_JOVEM", self._pendentes(get_protocol_plan(prot)))

    def test_ciclo_anual_dentro_do_prazo_nao_repete(self):
        prot = self._protocolo("anual")
        apply_protocol_campaign(prot["id"], _iso(100))
        db.clear_cache()

        self.assertNotIn("PRT_M_JOVEM", self._pendentes(get_protocol_plan(prot)))

    def test_dose_unica_nunca_volta_a_ficar_pendente(self):
        prot = self._protocolo("unica")
        apply_protocol_campaign(prot["id"], _iso(2000))
        db.clear_cache()

        self.assertNotIn("PRT_M_JOVEM", self._pendentes(get_protocol_plan(prot)))


if __name__ == "__main__":
    unittest.main()
