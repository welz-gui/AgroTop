# Schema e migrations do AgroTop

Este diretório é a **fonte de verdade versionada** do schema do Postgres.

Antes disso existir, o schema vivia em quatro lugares mantidos à mão ao mesmo tempo
(DDL do `init_db`, migrations aplicadas só no servidor, `CREATE TABLE` dentro de
funções, e `ALTER TABLE` em `_migrate`). A divergência entre eles causou dois bugs
reais: `init_db()` quebrando em banco novo (`75dce18`) e a tabela `sessions`
inexistente até o primeiro login (`599162a`).

Ver [ADR 0001](../docs/adr/0001-multi-fazenda-schema-por-tenant.md).

---

## Arquivos

| Arquivo | O que é |
|---|---|
| `migrations/0000_baseline_producao.sql` | DDL completo de produção, **sem qualificação de schema** (nomes resolvidos pelo `search_path`), para poder ser aplicado em qualquer tenant. Valida recriar 200 colunas / 22 tabelas do zero. |
| `../docs/schema-nuvem.txt` | Retrato simples (`tabela.coluna`) do schema de produção. Faz a divergência aparecer em diff de git e serve de referência para `tests/test_schema.py`. |

### Histórico anterior ao baseline

Nove migrations foram aplicadas direto no Supabase antes deste diretório existir e
**não estão** no repositório: `agrotop_initial_schema`, `enable_rls_all_tables`,
`phase1_sales_and_category_prices`, `phase2_deaths`,
`phase3_settings_and_lote_in_transactions`, `phase4_health_protocols`,
`phase5_animal_photos`, `perf_indexes`, `blocoC_pluviometria`.

O baseline representa o **estado acumulado** delas. Para provisionar um banco novo,
use apenas o baseline — não é preciso reproduzir a sequência histórica.

---

## Ao alterar o schema

1. Crie a migration na nuvem (Supabase → SQL Editor, ou MCP `apply_migration`).
2. Ajuste o DDL de `init_db()` em `database.py` para refletir a mesma mudança —
   **as duas pontas precisam andar juntas**, é exatamente aí que a divergência nasce.
3. Regenere o baseline e o retrato:
   ```bash
   python tools/dump_schema_nuvem.py --baseline
   ```
4. Valide que o baseline ainda recria o schema do zero:
   ```bash
   python tools/testar_baseline.py
   ```
5. Rode os testes e confira o diff:
   ```bash
   python -m unittest discover -s tests -t . && git diff supabase/ docs/
   ```
   O `-t .` **não é opcional**: ele faz `tests` ser importado como pacote, o que
   executa `tests/__init__.py` e isola a suíte do banco de produção. Sem ele,
   `tests/test_isolamento.py` falha de propósito.

O passo 5 falha se você esquecer o passo 2 — é para isso que os guardas de
`tests/test_schema.py` existem.

### Coluna nova: no `CREATE TABLE`, não só no `_migrate`

`_migrate()` existe **apenas** para atualizar bancos SQLite antigos. Toda coluna
precisa também estar no `CREATE TABLE`, senão uma instalação nova nasce incompleta.
O teste `test_ddl_completo_sem_depender_do_migrate` bloqueia esse erro.

---

## Provisionar uma fazenda nova (quando o gatilho do ADR 0001 disparar)

```sql
CREATE SCHEMA fazenda_2;
SET search_path TO fazenda_2;
-- aplicar migrations/0000_baseline_producao.sql
```

Depois, rotear a conexão por tenant em `_conn()` (`database.py`) — que é o ponto
único de acesso ao banco. Nada de `farm_id`: ver o ADR.

**Não coberto pelo baseline:** triggers, funções, políticas de RLS, grants e
extensões. Em produção o RLS está habilitado em todas as tabelas; ao criar um tenant
novo, habilite-o também. Quando houver Supabase CLI ou `pg_dump` disponível, um
`supabase db dump` é mais fiel que o gerador do repositório.

---

## Isolamento dos testes

Com `.streamlit/secrets.toml` presente, `_database_url()` cai no `st.secrets` e o
backend padrão passa a ser o **Postgres de produção** — um teste que chamasse
`init_db()` gravaria lá.

A proteção é `tests/__init__.py`, que define `AGROTOP_FORCE_SQLITE=1` antes de
qualquer import de `database`. Por isso os testes precisam rodar com `-t .`
(ver passo 5 acima), e `tests/test_isolamento.py` verifica que a proteção
continua ativa — inclusive que a flag vence uma `DATABASE_URL` presente.

Não inclua `DATABASE_URL` em mensagens de teste ou log: ela contém a senha do banco.

## Histórico de decisões aplicadas

- **`profiles` removida** de produção em 2026-07-30
  (`migrations/0001_drop_profiles.sql`). Era resíduo do app mobile obsoleto, com PK
  referenciando `auth.users` — o padrão do Supabase Auth que o
  [ADR 0002](../docs/adr/0002-fronteira-de-portabilidade.md) vetou. Estava vazia e
  sem dependências. Com isso, o DDL local e a produção passaram a ter
  **paridade total**: 194 colunas / 21 tabelas em ambos.
