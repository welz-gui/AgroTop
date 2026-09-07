"""Testes do pacote de evidências de vendas (spec 0080)."""

from datetime import date
import os
import re
import tempfile
import unittest
import zlib
from unittest.mock import patch

# O worktree não deve criar um banco ao lado do checkout; a suíte real já faz
# esse isolamento no pacote de testes, e aqui o import direto precisa repetir a
# mesma proteção antes de carregar o app (que chama init_db no topo).
import database as _database

_database.configurar_sqlite(os.path.join(tempfile.gettempdir(), "agrotop-test-evidencias.db"))
import app


def _texto_pdf(pdf_bytes: bytes) -> str:
    """Extrai o texto dos streams comprimidos gerados pelo fpdf2."""
    partes = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S):
        stream = match.group(1)
        try:
            stream = zlib.decompress(stream)
        except zlib.error:
            continue
        partes.append(stream.decode("latin-1", errors="replace"))
    return "\n".join(partes)


class _VendaSemFinanceiro(dict):
    """Falha se o gerador tentar ler qualquer campo financeiro interno."""

    _proibidos = {"cost_at_sale", "profit", "custo", "margem", "total_value"}

    def get(self, chave, padrao=None):
        if chave in self._proibidos:
            raise AssertionError(f"campo financeiro lido: {chave}")
        return super().get(chave, padrao)


class TestPacoteEvidencias(unittest.TestCase):
    def test_vendas_avulsas_nao_se_misturam(self):
        vendas = [
            {"id": 1, "animal_id": "A1", "lot_ref": None, "sale_date": "2026-09-03"},
            {"id": 2, "animal_id": "A2", "lot_ref": None, "sale_date": "2026-09-02"},
            {"id": 3, "animal_id": "A3", "lot_ref": "LV-1", "sale_date": "2026-09-01"},
            {"id": 4, "animal_id": "A4", "lot_ref": "LV-1", "sale_date": "2026-09-01"},
        ]

        grupos = app._vendas_para_evidencias(vendas)

        self.assertEqual(
            [[v["animal_id"] for v in grupo["vendas"]] for grupo in grupos],
            [["A1"], ["A2"], ["A3", "A4"]],
        )

    @patch.object(app, "get_animal")
    def test_pdf_tem_capa_secoes_dados_e_aviso_sem_financeiro(self, mock_get_animal):
        vendas = [
            _VendaSemFinanceiro({
                "id": 1, "animal_id": "A1", "lot_ref": "LV-42",
                "sale_date": "2026-09-03", "buyer": "Frigorífico Norte",
            }),
            _VendaSemFinanceiro({
                "id": 2, "animal_id": "A2", "lot_ref": "LV-42",
                "sale_date": "2026-09-03", "buyer": "Frigorífico Norte",
            }),
            _VendaSemFinanceiro({
                "id": 3, "animal_id": "A3", "lot_ref": "LV-42",
                "sale_date": "2026-09-03", "buyer": "Frigorífico Norte",
            }),
        ]
        mock_get_animal.side_effect = lambda animal_id: {
            "id": animal_id,
            "breed": f"Raça-{animal_id}",
            "sex": "M",
            "birth_date": "2024-01-01",
            "fornecedor_name": f"Fornecedor-{animal_id}",
            "nf_number": f"NF-{animal_id}",
            "gta_number": f"GTA-{animal_id}",
        }

        def pesagens(animal_id):
            return [{"weigh_date": "2026-08-01", "weight": 480, "method": "pesado", "operator": f"Op-{animal_id}"}]

        def medicamentos(animal_id):
            return [{
                "med_date": "2026-08-02", "medication_name": f"Med-{animal_id}",
                "dose": 5, "unit": "mL", "withdrawal_days": 7,
                "applied_by": f"Vet-{animal_id}",
            }]

        def carencia(animal_id):
            return date(2026, 9, 20) if animal_id == "A2" else None

        with patch.object(app.db, "get_age_category", return_value="Novilho"), \
             patch.object(app.db, "get_age_display", return_value="2 anos"), \
             patch.object(app.db, "get_weighings", side_effect=pesagens), \
             patch.object(app.db, "get_medications", side_effect=medicamentos), \
             patch.object(app.db, "get_withdrawal_end", side_effect=carencia), \
             patch.object(app.db, "get_photos", return_value=[]):
            pdf = app._gerar_pacote_evidencias(vendas)

        self.assertTrue(pdf.startswith(b"%PDF"))
        texto = _texto_pdf(pdf)
        self.assertIn("AgroTop - Pacote de", texto)
        self.assertIn("Aviso: este pacote", texto)
        self.assertIn("conformidade legal", texto)
        self.assertIn("certifica", texto)
        for animal_id in ("A1", "A2", "A3"):
            self.assertIn(animal_id, texto)
            self.assertIn(f"Med-{animal_id}", texto)
            self.assertIn(f"Op-{animal_id}", texto)
        self.assertIn("Livre", texto)
        self.assertIn("Em car", texto)
        self.assertIn("20/09/2026", texto)
        self.assertNotIn("cost_at_sale", texto)
        self.assertNotIn("profit", texto)


if __name__ == "__main__":
    unittest.main()
