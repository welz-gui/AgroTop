"""Movimentação com origem esperada (D2 / ADR 0006).

Offline, o operador move animais do piquete em que os viu. Quando o pedido
chega, outro operador pode já tê-los mudado de lugar. Sem conferência, o
servidor usava o piquete que tinha como origem e gravava a movimentação mesmo
assim. Com `from_lote_esperado`, divergência recusa o lote inteiro e nada é
gravado: quem decide é o operador.
"""

import sqlite3
import unittest

import database as db
from repositories.animais import OrigemDivergente, get_animal, get_movements
from tests.test_regras_negocio import BaseRegras, HOJE


class TestOrigemEsperada(BaseRegras):
    def setUp(self):
        super().setUp()
        con = sqlite3.connect(db.DB_PATH)
        try:
            property_id = con.execute(
                "SELECT id FROM properties ORDER BY created_at LIMIT 1").fetchone()[0]
            for lid in ("P1", "P2", "P3"):
                con.execute("INSERT INTO lotes (id,name,property_id) VALUES(?,?,?)",
                            (lid, f"Piquete {lid}", property_id))
            con.commit()
        finally:
            con.close()

    def _params(self, destino="P2", esperado=None):
        return db.MovementParams(destino, HOJE.isoformat(), from_lote_esperado=esperado)

    def _lote(self, aid):
        db.clear_cache()
        return get_animal(aid)["lote_id"]

    def test_origem_confere_e_move(self):
        a = self.animal("O1", lote="P1")
        r = db.move_animals_bulk([a], self._params(esperado="P1"))
        self.assertEqual(r["movidos"], ["O1"])
        self.assertEqual(self._lote(a), "P2")

    def test_sem_origem_esperada_nada_muda(self):
        a = self.animal("O2", lote="P3")
        r = db.move_animals_bulk([a], self._params(esperado=None))
        self.assertEqual(r["movidos"], ["O2"])

    def test_animal_que_saiu_do_piquete_recusa_o_lote_inteiro_sem_gravar_nada(self):
        ok = self.animal("O3", lote="P1")
        saiu = self.animal("O4", lote="P3")   # alguém levou para P3 enquanto o app estava offline

        with self.assertRaises(OrigemDivergente) as ctx:
            db.move_animals_bulk([ok, saiu], self._params(esperado="P1"))

        self.assertEqual(ctx.exception.divergentes, {"O4": "P3"})
        self.assertEqual(ctx.exception.esperado, "P1")
        self.assertIsInstance(ctx.exception, ValueError)
        self.assertEqual(self._lote(ok), "P1", "o animal que conferia também não pode ter sido movido")
        self.assertEqual(self._lote(saiu), "P3")
        self.assertEqual(get_movements(ok), [])

    def test_animal_que_ja_esta_no_destino_nao_e_divergencia(self):
        """Pedido repetido cuja resposta se perdeu: o animal já chegou, não há o que decidir."""
        movido = self.animal("O5", lote="P2")
        ficou = self.animal("O6", lote="P1")

        r = db.move_animals_bulk([movido, ficou], self._params(destino="P2", esperado="P1"))

        self.assertEqual(r["ja_no_destino"], ["O5"])
        self.assertEqual(r["movidos"], ["O6"])

    def test_animal_sem_piquete_diverge_de_origem_esperada(self):
        a = self.animal("O7", lote=None)
        with self.assertRaises(OrigemDivergente) as ctx:
            db.move_animals_bulk([a], self._params(esperado="P1"))
        self.assertEqual(ctx.exception.divergentes, {"O7": None})

    def test_animal_inexistente_continua_sendo_erro_e_nao_divergencia(self):
        a = self.animal("O8", lote="P1")
        r = db.move_animals_bulk([a, "NAO_EXISTE"], self._params(esperado="P1"))
        self.assertEqual(r["erros"], ["NAO_EXISTE"])
        self.assertEqual(r["movidos"], ["O8"])

    def test_move_animal_individual_tambem_confere(self):
        a = self.animal("O9", lote="P3")
        with self.assertRaises(OrigemDivergente):
            db.move_animal(a, self._params(esperado="P1"))
        self.assertEqual(self._lote(a), "P3")

    # ── origem por animal (seleção com piquetes diferentes) ────────────────

    def _params_mapa(self, mapa, destino="P3", unico=None):
        return db.MovementParams(destino, HOJE.isoformat(), from_lote_esperado=unico,
                                 origens_esperadas=mapa)

    def test_mapa_com_origens_diferentes_confere_e_move_todos(self):
        a = self.animal("M1", lote="P1")
        b = self.animal("M2", lote="P2")
        r = db.move_animals_bulk([a, b], self._params_mapa({a: "P1", b: "P2"}))
        self.assertEqual(sorted(r["movidos"]), ["M1", "M2"])
        self.assertEqual(self._lote(a), "P3")
        self.assertEqual(self._lote(b), "P3")

    def test_mapa_divergente_recusa_o_lote_inteiro_e_informa_o_esperado_de_cada_um(self):
        a = self.animal("M3", lote="P1")
        b = self.animal("M4", lote="P1")   # visto em P2, mas alguém o levou para P1
        with self.assertRaises(OrigemDivergente) as ctx:
            db.move_animals_bulk([a, b], self._params_mapa({a: "P1", b: "P2"}))
        self.assertEqual(ctx.exception.divergentes, {"M4": "P1"})
        self.assertEqual(ctx.exception.esperados, {"M4": "P2"})
        self.assertEqual(ctx.exception.esperado, "P2", "um só divergente: o esperado dele")
        self.assertEqual(self._lote(a), "P1", "o que conferia também não pode ter sido movido")

    def test_mapa_diferente_para_dois_divergentes_deixa_esperado_none(self):
        a = self.animal("M7", lote="P3")
        b = self.animal("M8", lote="P3")
        with self.assertRaises(OrigemDivergente) as ctx:
            db.move_animals_bulk([a, b], self._params_mapa({a: "P1", b: "P2"}, destino="P1"))
        # destino P1: M7 (esperado P1, está em P3) diverge; M8 (esperado P2, em P3) diverge.
        self.assertEqual(set(ctx.exception.divergentes), {"M7", "M8"})
        self.assertIsNone(ctx.exception.esperado)
        self.assertIn("visto em P1", str(ctx.exception))
        self.assertIn("visto em P2", str(ctx.exception))

    def test_mapa_prevalece_sobre_o_esperado_unico_e_ausentes_caem_nele(self):
        a = self.animal("M9", lote="P2")
        b = self.animal("M10", lote="P1")
        # M9 está em P2: o mapa diz P2 (confere) mesmo com o único P1; M10 cai no único P1.
        r = db.move_animals_bulk([a, b], self._params_mapa({a: "P2"}, unico="P1"))
        self.assertEqual(sorted(r["movidos"]), ["M10", "M9"])

    def test_animal_fora_do_mapa_e_sem_unico_nao_e_conferido(self):
        a = self.animal("M11", lote="P1")
        b = self.animal("M12", lote="P2")   # sem piquete conhecido pelo app: não confere
        r = db.move_animals_bulk([a, b], self._params_mapa({a: "P1"}))
        self.assertEqual(sorted(r["movidos"]), ["M11", "M12"])


if __name__ == "__main__":
    unittest.main()
