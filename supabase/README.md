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
   **Tabela nova leva RLS na mesma migration** — ver a seção abaixo; não é opcional
   e não é para depois.
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

### 🔒 Tabela nova nasce com RLS ligado

Toda tabela criada no schema `public` fica **exposta ao PostgREST**, e o papel `anon`
recebe `SELECT/INSERT/UPDATE/DELETE/TRUNCATE` nela por padrão do Supabase. Sem RLS, a
única coisa entre um estranho e os dados é o sigilo de uma chave que foi **projetada para
ser pública**.

Toda migration que cria tabela termina com:

```sql
ALTER TABLE <tabela> ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON <tabela> FROM anon, authenticated;
```

**Sem política nenhuma, de propósito.** RLS ligado e zero políticas = negar tudo para quem
não tem `BYPASSRLS`. O app conecta como `postgres`, que tem, e não usa PostgREST — o
acesso é `_conn()` por `DATABASE_URL` (R1). Política só entra se um dia existir consumidor
que precise dela.

O `REVOKE` não é redundante: **`TRUNCATE` é privilégio de tabela e não passa por RLS**.

*Histórico: em 2026-08-05 o linter do Supabase acusou `rls_disabled_in_public` em **onze**
tabelas — exatamente as criadas pelas migrations 0002 a 0012. Nenhuma foi decisão; todas
foram o mesmo passo faltando, repetido onze vezes, porque não estava escrito aqui. A
migration 0013 quase fez a décima segunda. A dívida nº 10 do ROADMAP já dizia que o
baseline não cobre RLS — e o buraco abriu assim mesmo, porque documentar um risco não o
elimina; escrevê-lo no passo que a pessoa executa, sim.*

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

> **Leia esta seção antes de auditar schema.** Ela existe porque três análises
> independentes já chegaram, com semanas de diferença, às mesmas perguntas — e
> uma delas refez trabalho que já estava feito. Se a sua conclusão está aqui,
> ela já foi decidida: confirme a data e siga em frente.

- **Índices com `idx_scan = 0` não são candidatos a remoção neste banco**
  (decidido em 2026-08-31, reafirmado em 2026-09-01). O Performance Advisor do
  Supabase sinaliza ~50 índices sem uso em `public.*`, e vai continuar
  sinalizando. **Isso não prova que são inúteis** — prova que o banco tem 14
  animais e 42 pesagens, e abaixo desse volume o planner prefere seq scan quase
  sempre. Cada índice custa 8–16 kB.
  A `0028_remove_indices_nao_usados_grupo1.sql` **já removeu os dois únicos com
  evidência objetiva** (`idx_weighings_date` e `idx_pluvio_lote`: existe irmão
  composto na mesma tabela já em uso, e nenhum dos dois sustentava FK).
  **Não refaça essa auditoria** antes de haver volume real — sugestão: quando
  alguma das tabelas passar de ~1.000 linhas. Quatro índices sem FK
  (`idx_ident_animal`, `idx_medications_protocol`, `idx_insumo_trans_lote`,
  `idx_insumo_trans_reason`) ficaram em "revisar depois"; os três primeiros
  saíram dessa lista com a 0029, que declarou as FKs que eles sustentam.

  **A prova, medida em 2026-09-03** (4ª auditoria, arquivada). O contador
  `idx_scan` mede escolha do planner, não uso pelo código — e a diferença é
  demonstrável:

  | Índice | `idx_scan` | Consulta no código |
  |---|---:|---|
  | `idx_animals_status` | **0** | **sim** — `WHERE a.status='ativo'`; `get_all_animals(status=…)` é chamado 16× só no `app.py` |
  | `idx_contas_pagar_status` | 0 | só via `WHERE id=? AND status='aberto'` — quem resolve é a PK; o índice `(status, vencimento)` não atende |
  | `idx_contas_receber_status` | 0 | idem |
  | `idx_eventos_tipo` | 0 | nenhuma |
  | `idx_eventos_sincronizacao` | 0 | nenhuma |
  | `idx_audit_entidade` | 0 | nenhuma |
  | `idx_evsinc_situacao` | 0 | nenhuma |
  | `idx_insumo_trans_reason` | 0 | nenhuma |
  | `idx_regras_vigencia` | 0 | nenhuma |
  | `idx_regras_evento` | 0 | nenhuma |

  `idx_animals_status` é a demonstração: **zero scans apesar de sustentar o
  filtro mais quente do app**, que roda todo dia. Com 14 linhas o planner faz
  seq scan de qualquer jeito. Se `idx_scan = 0` fosse prova de inutilidade,
  esse índice seria o primeiro a cair — e é o que menos deve cair.

  Os três índices que sustentam as FKs da 0029 (`idx_ident_animal`,
  `idx_medications_protocol`, `idx_insumo_trans_lote`) também estão com
  `idx_scan = 0`. Continuam necessários: a verificação de integridade
  referencial vai usá-los quando houver volume.

  **Escala do "problema":** 67 índices com `idx_scan = 0`, **784 kB no total**.
  As estatísticas não foram zeradas (`stats_reset` = 2026-07-15, anterior ao
  projeto), então os contadores cobrem a vida inteira do banco.

  **Quando reavaliar de verdade:** não pelo lint. Rode `EXPLAIN ANALYZE` nas
  consultas reais — o levantamento de código acima já diz quais são — depois
  que alguma tabela passar de ~1.000 linhas.

- **`UNIQUE` sobre as mesmas colunas da PRIMARY KEY nunca vai inline num
  `CREATE TABLE`** (2026-08-31, [PR #263](https://github.com/welz-gui/AgroTop/pull/263)).
  O PostgreSQL **descarta a constraint em silêncio** — sem erro, sem aviso. Foi
  a causa raiz da falha da `0027` no replay: o baseline declarava
  `animals_uuid_key UNIQUE (uuid)` ao lado de `animals_pkey PRIMARY KEY (uuid)`,
  a constraint nunca nascia, e o `DROP CONSTRAINT` reclamava de algo inexistente.
  Sintoma tapado com `IF EXISTS` no [#258](https://github.com/welz-gui/AgroTop/pull/258);
  causa corrigida no `tools/dump_schema_nuvem.py`, que agora emite essas
  constraints como `ALTER TABLE ADD CONSTRAINT` separado.
  **Ao regenerar o baseline (passo 3 do checklist acima), rode
  `tests/test_dump_baseline.py`** — é o guarda que pega a reincidência.
  O `test_schema_local_nao_divergiu_da_producao` não pega: ele compara colunas,
  não constraints.

- **`animals_uuid_key` foi removida de produção em 2026-08-28**
  (`migrations/0027_remove_indice_duplicado_animals.sql`). Era `UNIQUE (uuid)`
  redundante com `animals_pkey PRIMARY KEY (uuid)`, remanescente de antes da
  0017. A remoção exigiu derrubar e recriar 14 FKs, porque todas dependiam dela.
  Houve uma decisão anterior de **não** fazer isso (não valia recriar 14 FKs por
  um índice redundante) — **essa decisão foi revertida** e a migration aplicada.
  Não reabra sem motivo novo.

- **Três FKs declaradas** (`migrations/0029_fks_faltantes.sql`, 2026-09-01):
  `animal_identifiers.animal_uuid → animals(uuid)`,
  `medications.protocol_id → health_protocols(id)` e
  `insumo_transactions.lote_id → lotes(id)`. As três colunas apontavam para
  outra tabela só por convenção do código. A primeira é a que importa: o AgroTop
  existe para rastreabilidade PNIB, e identificador apontando para animal
  inexistente é a classe de erro que o sistema deveria tornar impossível.
  Verificado sem órfãos antes de aplicar (14/0, 24/0, 2/0 linhas/órfãos).
  Sem `ON DELETE`, igual às FKs irmãs: apagar animal com identificador passa a
  ser recusado, que é o correto num sistema onde histórico não some.

- **RLS nas 11 tabelas da Fase B + limpeza de heranças do Supabase Auth**
  (`migrations/0014_rls_nas_tabelas_da_fase_b.sql`, aplicada em 2026-08-05). O linter
  do Supabase acusou `rls_disabled_in_public` em `animal_identifiers`, `animal_events`,
  `audit_logs`, `organizacoes`, `produtores`, `properties`, `partos`, `movimentacoes`,
  `movimentacao_animais`, `dispositivos` e `regras_regulatorias` — as 11 tabelas das
  migrations 0002 a 0012, todas sem o passo que este README não pedia até então. Ver
  a dívida nº 10 do [ROADMAP](../ROADMAP.md) para o incidente completo.
  Na mesma migration: duas políticas mortas em `storage.objects` (bucket
  `animal-photos`, nunca usado — as fotos vão para `animal_photos.image`) e as
  funções `is_admin_or_gestor()`/`get_current_user_role()` foram **removidas**, não
  só desligadas — a segunda consultava `public.profiles`, já apagada pela 0001, e
  as duas eram `SECURITY DEFINER` executáveis por `anon` via RPC.
  `fn_recusa_alteracao()` ganhou `search_path` fixo.

- **`evento_sincronizacao` criada** (`migrations/0013_fila_de_sincronizacao.sql`,
  [ADR 0005](../docs/adr/0005-fila-de-sincronizacao.md), aplicada em 2026-08-05). Aditiva:
  uma tabela nova, nenhuma linha existente tocada. Tira a fila de sincronização (§10.3) de
  dentro de `animal_events`, que continua **estritamente** append-only —
  `status_sincronizacao` e `identificador_oficial` viram colunas legadas, congeladas
  no nascimento do evento. Nasce com RLS e grants revogados na própria migration —
  ver a nota de rigor em `tests/test_rls_nas_migrations.py`.

- **`profiles` removida** de produção em 2026-07-30
  (`migrations/0001_drop_profiles.sql`). Era resíduo do app mobile obsoleto, com PK
  referenciando `auth.users` — o padrão do Supabase Auth que o
  [ADR 0002](../docs/adr/0002-fronteira-de-portabilidade.md) vetou. Estava vazia e
  sem dependências. Com isso, o DDL local e a produção passaram a ter
  **paridade total**: 194 colunas / 21 tabelas em ambos.
