"""A tela de Rebanho respeita os filtros aplicados no seletor de detalhamento? (Spec 0095)

Critérios de aceite:
1. Filtrar a tabela a um subconjunto pequeno (ex.: uma raça específica) -> o seletor mostra
   só os IDs desse subconjunto, nunca um ID fora dele.
2. Filtro sem nenhum resultado -> seletor vazio/desabilitado, "Abrir Ficha" não abre um animal aleatório.
3. Selecionar um animal, depois trocar o filtro de forma que ele some da lista -> seleção não
   persiste apontando para um ID que não está mais nas opções.
4. calculate_gmd_bulk / get_withdrawal_end_batch continuam sendo chamadas em lote, uma vez
   por carregamento da página — não uma vez por linha.
5. Sem nenhum filtro aplicado, comportamento idêntico ao original (todos os animais disponíveis no seletor).

⚠️ Não começa com test_ de propósito — ver tests/test_ui.py.
Quem executa isto é tests/test_ui.py num subprocesso isolado.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestTelaRebanho(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_rebanho.db"))
        db.init_db()
        db.clear_cache()

    def _tela(self, **estado):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {
            "id": 1,
            "username": "admin",
            "name": "Admin",
            "role": "admin",
        }
        at.session_state["page"] = "rebanho"
        for k, v in estado.items():
            at.session_state[k] = v
        at.run()
        self.assertEqual(
            list(at.exception),
            [],
            f"app levantou exceção: {[e.value for e in at.exception]}",
        )
        return at

    def _seletor_animal(self, at):
        alvos = [s for s in at.selectbox if s.label == "Animal para detalhar"]
        self.assertEqual(len(alvos), 1, "seletor 'Animal para detalhar' não encontrado")
        return alvos[0]

    def _seletor_raca(self, at):
        alvos = [s for s in at.selectbox if s.label == "Raça"]
        self.assertEqual(len(alvos), 1, "seletor 'Raça' não encontrado")
        return alvos[0]

    def _campo_busca(self, at):
        alvos = [t for t in at.text_input if "ID / Raça / Lote" in (t.label or "")]
        self.assertEqual(len(alvos), 1, "campo de busca não encontrado")
        return alvos[0]

    def _botao_abrir_ficha(self, at):
        alvos = [b for b in at.button if "Abrir Ficha" in (b.label or "")]
        self.assertEqual(len(alvos), 1, "botão 'Abrir Ficha' não encontrado")
        return alvos[0]

    def test_sem_filtro_lista_todos_animais(self):
        """Critério 5: sem filtro, todos os animais do rebanho estão no seletor na mesma ordem."""
        at = self._tela()
        todos = [a["id"] for a in db.get_all_animals(status=None)]
        self.assertGreater(len(todos), 0, "banco de teste deve conter animais cadastrados")
        seletor = self._seletor_animal(at)
        self.assertEqual(seletor.options, todos)

    def test_filtro_raca_mostra_apenas_subconjunto(self):
        """Critério 1: filtrar por raça restringe o seletor aos IDs daquela raça."""
        at = self._tela()
        todos = db.get_all_animals(status=None)
        racas = {a["breed"] for a in todos}
        self.assertIn("Nelore", racas)
        esperados_nelore = [a["id"] for a in todos if a["breed"] == "Nelore"]
        outros_ids = [a["id"] for a in todos if a["breed"] != "Nelore"]
        self.assertTrue(len(esperados_nelore) > 0)
        self.assertTrue(len(outros_ids) > 0)

        sel_raca = self._seletor_raca(at)
        sel_raca.set_value("Nelore")
        at.run()
        self.assertEqual(list(at.exception), [])

        seletor = self._seletor_animal(at)
        self.assertEqual(seletor.options, esperados_nelore)
        for outro_id in outros_ids:
            self.assertNotIn(outro_id, seletor.options)

    def test_filtro_sem_resultado_desabilita_seletor_e_nao_abre_ficha(self):
        """Critério 2: filtro sem resultados deixa seletor vazio/desabilitado e 'Abrir Ficha' não abre animal."""
        at = self._tela()
        busca = self._campo_busca(at)
        busca.set_value("INEXISTENTE_999999")
        at.run()
        self.assertEqual(list(at.exception), [])

        seletor = self._seletor_animal(at)
        self.assertEqual(seletor.options, [])
        self.assertIsNone(seletor.value)

        # 'Abrir Ficha' fica desabilitado — um usuário real não consegue
        # clicar nele. AppTest recusa até simular o clique num widget
        # desabilitado (AppTestError), então a prova aqui é o estado do
        # widget, não uma tentativa de clique que o próprio framework proíbe.
        btn = self._botao_abrir_ficha(at)
        self.assertTrue(btn.disabled, "botão 'Abrir Ficha' deveria estar desabilitado sem resultados")
        # Continua na página rebanho, sem definir animal_detail
        self.assertEqual(at.session_state["page"], "rebanho")
        self.assertTrue("animal_detail" not in at.session_state or at.session_state["animal_detail"] is None)

    def test_troca_de_filtro_invalida_selecao(self):
        """Critério 3: trocar filtro para excluir o animal selecionado invalida a seleção anterior."""
        at = self._tela()
        todos = db.get_all_animals(status=None)
        angus = next(a for a in todos if a["breed"] == "Angus")
        nelores = [a["id"] for a in todos if a["breed"] == "Nelore"]
        self.assertNotIn(angus["id"], nelores)

        # Seleciona o Angus com filtro 'Todas'
        seletor = self._seletor_animal(at)
        seletor.set_value(angus["id"])
        at.run()
        self.assertEqual(self._seletor_animal(at).value, angus["id"])

        # Agora troca o filtro para Nelore (Angus deixa de existir na lista filtrada)
        sel_raca = self._seletor_raca(at)
        sel_raca.set_value("Nelore")
        at.run()
        self.assertEqual(list(at.exception), [])

        seletor_depois = self._seletor_animal(at)
        self.assertNotEqual(seletor_depois.value, angus["id"])
        self.assertNotIn(angus["id"], seletor_depois.options)
        self.assertIn(seletor_depois.value, nelores)

        # Clicar em Abrir Ficha abre o animal atualmente válido, nunca o Angus excluído
        btn = self._botao_abrir_ficha(at)
        btn.click()
        at.run()
        self.assertEqual(list(at.exception), [])
        self.assertEqual(at.session_state["page"], "animal")
        self.assertNotEqual(at.session_state["animal_detail"], angus["id"])
        self.assertIn(at.session_state["animal_detail"], nelores)

    def test_consultas_em_lote_chamadas_uma_vez(self):
        """Critério 4: calculate_gmd_bulk e get_withdrawal_end_batch continuam em lote (1 chamada por tela)."""
        with patch.object(db, "calculate_gmd_bulk", wraps=db.calculate_gmd_bulk) as mock_gmd, \
             patch.object(db, "get_withdrawal_end_batch", wraps=db.get_withdrawal_end_batch) as mock_wd:
            self._tela()
            self.assertEqual(
                mock_gmd.call_count,
                1,
                f"calculate_gmd_bulk deveria ser chamada exatamente 1 vez, foi {mock_gmd.call_count}",
            )
            self.assertEqual(
                mock_wd.call_count,
                1,
                f"get_withdrawal_end_batch deveria ser chamada exatamente 1 vez, foi {mock_wd.call_count}",
            )
            # Garante que a chamada recebeu todos os IDs do rebanho em lote
            args_gmd, _ = mock_gmd.call_args
            todos_ids = [a["id"] for a in db.get_all_animals(status=None)]
            self.assertEqual(set(args_gmd[0]), set(todos_ids))


if __name__ == "__main__":
    unittest.main()
