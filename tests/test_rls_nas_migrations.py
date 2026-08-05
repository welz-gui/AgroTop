"""Toda tabela nova nasce com RLS ligado?

Em 2026-08-05 o linter do Supabase acusou `rls_disabled_in_public` em **onze**
tabelas — exatamente as criadas pelas migrations 0002 a 0012. Nenhuma delas foi
decisão: foi o mesmo passo faltando, repetido onze vezes, porque não estava no
checklist de `supabase/README.md`. A migration 0013 quase fez a décima segunda
— corrigida antes do merge. A migration 0014 fechou a dívida das onze.

A dívida nº 10 do ROADMAP já registrava que *"o baseline não cobre RLS"*. O
registro não impediu nada. Este teste impede, e é a diferença entre documentar
um risco e fechá-lo.

É análise estática do SQL: não conecta em banco nenhum, então roda no CI em
SQLite igual roda em qualquer lugar.

## Por que a regra muda de rigor a partir da 0013

Para migration nova, a exigência é **atômica**: RLS e REVOKE na mesma
migration que cria a tabela. Foi a falta disso, na própria 0013, que motivou
este arquivo.

Para as 11 legadas (0002–0012), exigir isso retroativamente reescreveria
migrations já aplicadas em produção — e uma migration aplicada não se edita
(mesma razão de `animal_events` ser append-only). A dívida existiu de verdade;
o que se cobra delas é diferente: que **em algum lugar do histórico** a tabela
tenha sido protegida. Foi a 0014 que fez isso, numa migration à parte, meses
depois — histórico honesto, não retroescrita.
"""

import os
import re
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATIONS = os.path.join(RAIZ, "supabase", "migrations")

# A partir daqui, uma migration que cria tabela sem protegê-la NA MESMA
# migration quebra o teste. Foi o nome da migration que corrigiu a própria
# atomicidade que faltou (ver docstring) — não é coincidência ela ser o corte.
_A_PARTIR_DE = "0013"

_CRIA_TABELA = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?([a-zA-Z_][\w]*)",
    re.IGNORECASE)
_LIGA_RLS = re.compile(
    r"ALTER\s+TABLE\s+(?:public\.)?([a-zA-Z_][\w]*)\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
    re.IGNORECASE)
_REVOKE_TABELA = re.compile(
    r"REVOKE\s+ALL\s+ON\s+(?:public\.)?([a-zA-Z_][\w]*)\b[^;]*FROM[^;]*anon",
    re.IGNORECASE)
# `REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon` — cobre, na hora em que
# roda, toda tabela que já existe no schema. É como a 0014 fechou as 11 de uma
# vez, em vez de onze linhas repetidas.
_REVOKE_EM_BLOCO = re.compile(
    r"REVOKE\s+ALL\s+ON\s+ALL\s+TABLES\s+IN\s+SCHEMA\s+public[^;]*FROM[^;]*anon",
    re.IGNORECASE)


def _sem_comentarios(sql: str) -> str:
    """Remove comentários `--`.

    Sem isto, a 0001 seria acusada de criar `profiles`: ela guarda a definição
    da tabela removida dentro de um comentário, "para o registro". SQL comentado
    é documentação, não schema.
    """
    return "\n".join(re.sub(r"--.*$", "", linha) for linha in sql.splitlines())


def _migrations():
    """(nome, sql sem comentários) de cada migration versionada, exceto o baseline.

    O baseline é **gerado** por `tools/dump_schema_nuvem.py` a partir da nuvem:
    cobrá-lo aqui seria cobrar do gerador, e o lugar disso é o próprio gerador.
    """
    arquivos = sorted(f for f in os.listdir(MIGRATIONS)
                      if f.endswith(".sql") and not f.startswith("0000_"))
    for nome in arquivos:
        with open(os.path.join(MIGRATIONS, nome), encoding="utf-8") as fh:
            yield nome, _sem_comentarios(fh.read())


class TestRLSNasMigrations(unittest.TestCase):
    def test_toda_tabela_criada_ganha_rls_em_algum_lugar_do_historico(self):
        """Mínimo absoluto: nenhuma tabela fica exposta para sempre.

        O papel `anon` recebe SELECT/INSERT/UPDATE/DELETE em tudo no schema
        `public` por padrão do Supabase. Sem RLS, o que separa um estranho dos
        dados é o sigilo de uma chave projetada para ser pública.
        """
        criadas = {}      # tabela -> primeira migration que a criou
        protegidas = set()
        for nome, sql in _migrations():
            for tabela in _CRIA_TABELA.findall(sql):
                criadas.setdefault(tabela, nome)
            protegidas |= set(_LIGA_RLS.findall(sql))

        faltando = sorted(f"{criadas[t]}: {t}" for t in criadas if t not in protegidas)
        self.assertEqual(
            faltando, [],
            "tabela criada e NUNCA protegida por RLS em nenhuma migration:\n  "
            + "\n  ".join(faltando)
            + "\n\nVer 'Tabela nova nasce com RLS ligado' em supabase/README.md.")

    def test_toda_tabela_criada_tem_os_grants_publicos_revogados(self):
        """Mesmo cobrança que o teste acima, mas para os grants.

        RLS não cobre TRUNCATE — é privilégio de tabela e passa por cima dele.
        Hoje o PostgREST não expõe TRUNCATE por HTTP, então isto é risco latente,
        não porta aberta — mas manter o grant é apostar que essa superfície
        nunca vai crescer.
        """
        criadas = {}
        revogadas = set()
        houve_revoke_em_bloco = False
        for nome, sql in _migrations():
            for tabela in _CRIA_TABELA.findall(sql):
                criadas.setdefault(tabela, nome)
            revogadas |= set(_REVOKE_TABELA.findall(sql))
            if _REVOKE_EM_BLOCO.search(sql):
                houve_revoke_em_bloco = True

        if houve_revoke_em_bloco:
            return  # cobre toda tabela existente até aquele ponto do histórico

        faltando = sorted(f"{criadas[t]}: {t}" for t in criadas if t not in revogadas)
        self.assertEqual(
            faltando, [],
            "tabela criada sem REVOKE ALL ... FROM anon em nenhuma migration:\n  "
            + "\n  ".join(faltando))

    def test_migration_a_partir_da_0013_protege_na_propria_migration(self):
        """A regra fica atômica dali em diante: RLS e REVOKE na mesma migration
        que cria a tabela, sem depender de uma correção posterior.

        Foi a ausência disto, na própria 0013 antes de ser corrigida, que criou
        este arquivo de teste. Não se repete para trás — ver a docstring do
        módulo — mas se repete para a frente, sempre.
        """
        faltando = []
        for nome, sql in _migrations():
            if nome < _A_PARTIR_DE:
                continue
            criadas = set(_CRIA_TABELA.findall(sql))
            if not criadas:
                continue
            protegidas = set(_LIGA_RLS.findall(sql))
            tem_revoke_bloco = bool(_REVOKE_EM_BLOCO.search(sql))
            revogadas = set(_REVOKE_TABELA.findall(sql))
            for tabela in sorted(criadas):
                if tabela not in protegidas:
                    faltando.append(f"{nome}: {tabela} sem ENABLE ROW LEVEL SECURITY")
                if tabela not in revogadas and not tem_revoke_bloco:
                    faltando.append(f"{nome}: {tabela} sem REVOKE ... FROM anon")

        self.assertEqual(
            faltando, [],
            f"migration >= {_A_PARTIR_DE} criou tabela sem protegê-la na mesma "
            "migration:\n  " + "\n  ".join(faltando))


if __name__ == "__main__":
    unittest.main()
