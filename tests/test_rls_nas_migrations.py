"""Toda tabela nova nasce com RLS ligado?

Em 2026-08-05 o linter do Supabase acusou `rls_disabled_in_public` em **onze**
tabelas — exatamente as criadas pelas migrations 0002 a 0012. Nenhuma delas foi
decisão: foi o mesmo passo faltando, repetido onze vezes, porque não estava no
checklist de `supabase/README.md`. A migration 0013 quase fez a décima segunda.

A dívida nº 10 do ROADMAP já registrava que *"o baseline não cobre RLS"*. O
registro não impediu nada. Este teste impede, e é a diferença entre documentar um
risco e fechá-lo.

É análise estática do SQL: não conecta em banco nenhum, então roda no CI em
SQLite igual roda em qualquer lugar.
"""

import os
import re
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATIONS = os.path.join(RAIZ, "supabase", "migrations")

_CRIA_TABELA = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?([a-zA-Z_][\w]*)",
    re.IGNORECASE)
_LIGA_RLS = re.compile(
    r"ALTER\s+TABLE\s+(?:public\.)?([a-zA-Z_][\w]*)\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
    re.IGNORECASE)

# As onze do incidente de 2026-08-05, criadas antes de a regra existir.
#
# **Esta lista não deve crescer.** Ela encolhe até zero quando a migration que
# liga RLS nelas for aplicada — e aí este bloco inteiro sai do arquivo. Enquanto
# existir, ela é a dívida escrita em código executável, e não em prosa que
# ninguém relê.
_DIVIDA_2026_08_05 = frozenset({
    "animal_identifiers", "animal_events", "audit_logs", "organizacoes",
    "produtores", "properties", "partos", "movimentacoes",
    "movimentacao_animais", "dispositivos", "regras_regulatorias",
})


def _sem_comentarios(sql: str) -> str:
    """Remove comentários `--`.

    Sem isto, a 0001 seria acusada de criar `profiles`: ela guarda a definição
    da tabela removida dentro de um comentário, "para o registro". SQL comentado
    é documentação, não schema.
    """
    return "\n".join(re.sub(r"--.*$", "", linha) for linha in sql.splitlines())


def _sql_das_migrations():
    """Cada migration versionada, exceto o baseline.

    O baseline é **gerado** por `tools/dump_schema_nuvem.py` a partir da nuvem:
    cobrá-lo aqui seria cobrar do gerador, e o lugar disso é o próprio gerador.
    """
    arquivos = sorted(f for f in os.listdir(MIGRATIONS)
                      if f.endswith(".sql") and not f.startswith("0000_"))
    for nome in arquivos:
        with open(os.path.join(MIGRATIONS, nome), encoding="utf-8") as fh:
            yield nome, _sem_comentarios(fh.read())


class TestRLSNasMigrations(unittest.TestCase):
    def test_toda_tabela_criada_liga_rls(self):
        """Sem isto, a tabela entra em produção legível e gravável por `anon`.

        O papel `anon` recebe SELECT/INSERT/UPDATE/DELETE em tudo no schema
        `public` por padrão do Supabase. Sem RLS, o que separa um estranho dos
        dados é o sigilo de uma chave projetada para ser pública.
        """
        faltando = []
        for nome, sql in _sql_das_migrations():
            criadas = set(_CRIA_TABELA.findall(sql))
            protegidas = set(_LIGA_RLS.findall(sql))
            for tabela in sorted(criadas - protegidas):
                if tabela in _DIVIDA_2026_08_05:
                    continue
                faltando.append(f"{nome}: {tabela}")

        self.assertEqual(
            faltando, [],
            "tabela criada sem ENABLE ROW LEVEL SECURITY na mesma migration:\n  "
            + "\n  ".join(faltando)
            + "\n\nVer 'Tabela nova nasce com RLS ligado' em supabase/README.md.")

    def test_toda_tabela_criada_revoga_os_grants_publicos(self):
        """RLS não cobre TRUNCATE — é privilégio de tabela, e passa por cima.

        Hoje o PostgREST não expõe TRUNCATE por HTTP, então o grant é risco
        latente e não porta aberta. Mantê-lo é apostar que essa superfície nunca
        vai crescer.
        """
        faltando = []
        for nome, sql in _sql_das_migrations():
            for tabela in sorted(set(_CRIA_TABELA.findall(sql))):
                if tabela in _DIVIDA_2026_08_05:
                    continue
                revoga = re.search(
                    r"REVOKE\s+ALL\s+ON\s+(?:public\.)?" + re.escape(tabela)
                    + r"\b[^;]*FROM[^;]*anon", sql, re.IGNORECASE)
                if not revoga:
                    faltando.append(f"{nome}: {tabela}")

        self.assertEqual(
            faltando, [],
            "tabela criada sem REVOKE ALL ... FROM anon na mesma migration:\n  "
            + "\n  ".join(faltando))

    def test_a_lista_de_divida_nao_esconde_tabela_que_ja_foi_corrigida(self):
        """A dívida precisa encolher, não virar mobília.

        Se uma tabela da lista já ganhou RLS em alguma migration, ela sai da
        lista. Sem esta cobrança, a exceção sobrevive à própria correção e passa
        a acobertar o erro seguinte.
        """
        ja_protegidas = set()
        for _, sql in _sql_das_migrations():
            ja_protegidas |= set(_LIGA_RLS.findall(sql))

        obsoletas = sorted(_DIVIDA_2026_08_05 & ja_protegidas)
        self.assertEqual(
            obsoletas, [],
            "estas tabelas já ligam RLS numa migration e devem sair de "
            f"_DIVIDA_2026_08_05: {obsoletas}")


if __name__ == "__main__":
    unittest.main()
