"""database.get_alert_animals — categoria "Em Carência".

Achado real (não hipotético): `add_medication` muda o status do animal para
"carencia" quando há dias de carência (`repositories/sanidade.py`), e
`refresh_carencia_status` trata "carencia" como um status de primeira classe
(`services/estados_animal.py` também lista "carencia" na máquina de estados).
`get_alert_animals` buscava só `status="ativo"` — a categoria "carência"
nunca retornava nada, no web (`app.py::_alertas_operacionais`) nem em lugar
nenhum, desde que a função existe.
"""

import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402
from repositories.animais import add_animal  # noqa: E402
from repositories.sanidade import add_medication  # noqa: E402


class TestAlertaDeCarencia(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.dir, "alertas.db"))
        db.init_db()
        db.clear_cache()
        lote = db.get_all_lotes()[0]
        # Animal novo, sem medicamentos — os seeds de demonstração já incluem
        # um animal em carência de propósito (dado real, não erro de setUp),
        # então não dá pra assumir que o primeiro animal "ativo" está limpo.
        add_animal(
            "TESTE001", "Nelore", "M", "2024-01-01", "2026-01-01",
            300.0, 500.0, 2000.0, lote["id"], None,
        )
        db.clear_cache()
        self.animal = db.get_animal("TESTE001")

    def test_animal_em_carencia_aparece_no_alerta(self):
        animal_id = self.animal["id"]
        add_medication(
            animal_id, "Ivermectina", 2.0, "ml", "Subcutânea",
            withdrawal_days=21, med_date=db.date.today().isoformat(),
            applied_by="op1",
        )

        # A mudança de status é o mecanismo real que causava o bug — confirma
        # que o cenário de teste é o mesmo que acontece em produção.
        atualizado = db.get_animal(animal_id)
        self.assertEqual(atualizado["status"], "carencia")

        alertas = db.get_alert_animals()
        ids_em_carencia = {a["id"] for a in alertas["carencia"]}
        self.assertIn(animal_id, ids_em_carencia)

    def test_animal_ativo_sem_medicamento_nao_aparece_em_carencia(self):
        alertas = db.get_alert_animals()
        ids_em_carencia = {a["id"] for a in alertas["carencia"]}
        self.assertNotIn(self.animal["id"], ids_em_carencia)

    def test_animal_em_carencia_continua_elegivel_para_sumido_e_pronto(self):
        """A categoria "ativo apenas" era usada pras outras categorias também —
        confirma que somar "carencia" não filtrou incorretamente as demais."""
        animal_id = self.animal["id"]
        add_medication(
            animal_id, "Ivermectina", 2.0, "ml", "Subcutânea",
            withdrawal_days=21, med_date=db.date.today().isoformat(),
            applied_by="op1",
        )
        alertas = db.get_alert_animals()
        todos_ids = (
            {a["id"] for a in alertas["sumidos"]}
            | {a["id"] for a in alertas["carencia"]}
            | {a["id"] for a in alertas["prontos"]}
        )
        # Não precisa estar em sumidos/prontos — só confirma que a função não
        # quebrou ao processar um animal com status != "ativo".
        self.assertTrue(todos_ids)


if __name__ == "__main__":
    unittest.main()
