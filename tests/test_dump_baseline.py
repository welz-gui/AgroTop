"""O baseline gerado tem de reproduzir o schema, não só descrevê-lo.

Em 2026-08-29 a migration 0027 falhou no CI com "constraint animals_uuid_key
does not exist" — apesar de `0000_baseline_producao.sql` declarar exatamente
essa constraint. O diagnóstico contra um PG16 limpo mostrou a causa:

    CREATE TABLE animals (
        ...
        CONSTRAINT animals_pkey     PRIMARY KEY (uuid),
        CONSTRAINT animals_uuid_key UNIQUE (uuid)   -- mesma coluna da PK
    );

Declarada assim, **o PostgreSQL descarta a UNIQUE em silêncio** — sem erro, sem
aviso. A tabela nasce só com a PK, o replay deixa de reproduzir produção, e a
divergência só aparece quando alguma migration futura tenta mexer na constraint
que nunca existiu.

Por `ALTER TABLE ADD CONSTRAINT` separado o Postgres cria normalmente. Estes
testes travam essa separação em `tools/dump_schema_nuvem.py`.
"""

import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tools.dump_schema_nuvem import (            # noqa: E402
    _colunas_da_constraint,
    _redundante_com_a_pk,
)


def _con(nome, tipo, definicao):
    return {"nome": nome, "tipo": tipo, "definicao": definicao}


class TestColunasDaConstraint(unittest.TestCase):
    def test_extrai_coluna_unica(self):
        self.assertEqual(_colunas_da_constraint("PRIMARY KEY (uuid)"), "uuid")

    def test_normaliza_espacos_em_chave_composta(self):
        self.assertEqual(_colunas_da_constraint("UNIQUE (farm_id,  animal_id)"),
                         "farm_id,animal_id")

    def test_definicao_sem_parenteses_nao_quebra(self):
        self.assertEqual(_colunas_da_constraint("CHECK valido"), "")


class TestRedundanteComAPk(unittest.TestCase):
    PK = "PRIMARY KEY (uuid)"

    def test_unique_na_mesma_coluna_da_pk_e_redundante(self):
        """O caso real: animals_uuid_key ao lado de animals_pkey."""
        self.assertTrue(
            _redundante_com_a_pk(_con("animals_uuid_key", "u", "UNIQUE (uuid)"), self.PK))

    def test_unique_em_outra_coluna_fica_inline(self):
        """`animals_id_key UNIQUE (id)` não colide com a PK e é criada normalmente."""
        self.assertFalse(
            _redundante_com_a_pk(_con("animals_id_key", "u", "UNIQUE (id)"), self.PK))

    def test_chave_composta_so_e_redundante_se_bater_inteira(self):
        pk = "PRIMARY KEY (farm_id, animal_id)"
        self.assertTrue(_redundante_com_a_pk(
            _con("x", "u", "UNIQUE (farm_id, animal_id)"), pk))
        self.assertFalse(_redundante_com_a_pk(
            _con("x", "u", "UNIQUE (farm_id)"), pk))

    def test_tabela_sem_pk_nao_tem_redundancia(self):
        self.assertFalse(
            _redundante_com_a_pk(_con("x", "u", "UNIQUE (uuid)"), None))

    def test_so_vale_para_unique(self):
        """CHECK e FK seguem o caminho normal, mesmo cobrindo a coluna da PK."""
        for tipo in ("c", "f", "p"):
            with self.subTest(tipo=tipo):
                self.assertFalse(
                    _redundante_com_a_pk(_con("x", tipo, "UNIQUE (uuid)"), self.PK))


class TestBaselineAtual(unittest.TestCase):
    """O baseline em disco é o que o CI replaya. Se voltar a declarar uma UNIQUE
    redundante inline, o replay volta a divergir de produção em silêncio."""

    def test_nenhuma_unique_redundante_inline_no_baseline(self):
        caminho = os.path.join(RAIZ, "supabase", "migrations",
                               "0000_baseline_producao.sql")
        if not os.path.exists(caminho):
            self.skipTest("baseline ausente")

        with open(caminho, encoding="utf-8") as fh:
            linhas = fh.readlines()

        problemas = []
        pk_atual = None
        for linha in linhas:
            texto = linha.strip()
            if texto.startswith("CREATE TABLE"):
                pk_atual = None
            elif "PRIMARY KEY" in texto and texto.startswith("CONSTRAINT"):
                pk_atual = _colunas_da_constraint(texto)
            elif (texto.startswith("CONSTRAINT") and " UNIQUE " in f" {texto} "
                  and pk_atual is not None
                  and _colunas_da_constraint(texto) == pk_atual):
                problemas.append(texto.rstrip(","))

        self.assertEqual(
            problemas, [],
            "UNIQUE redundante com a PK declarada inline no baseline — o "
            "PostgreSQL descarta em silêncio. Regenere com "
            "tools/dump_schema_nuvem.py: " + "; ".join(problemas))


if __name__ == "__main__":
    unittest.main()
