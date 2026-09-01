# Revisão — "Relatório Técnico: Evolução da Arquitetura, Hospedagem e Banco de Dados do AgroTop"

- **Data desta revisão:** 2026-08-27
- **Objeto revisado:** relatório externo datado de 2026-08-26
- **Método:** leitura do relatório, conferência contra o código em `main`, e **medição
  instrumentada** do app e do banco de produção
- **Veredicto:** recomendações majoritariamente **já implementadas**; a premissa central
  sobre o Supabase está **invertida**; três itens seguem válidos. O gargalo real de
  desempenho **não aparece no relatório** — está medido na seção 5 desta revisão.

---

## 1. Por que o relatório erra tanto

O próprio documento declara a causa, na seção 2:

> "Foi feita tentativa de acesso ao repositório conectado do GitHub, porém atualmente a
> integração não está retornando nenhum repositório acessível."

Ou seja: o relatório descreve um AgroTop **hipotético**, deduzido do que costuma acontecer
com aplicações Streamlit em geral. Boa parte do que ele propõe construir já existe, e a
parte que ele supõe sobre a camada de dados está factualmente errada.

Isso não desqualifica o autor — desqualifica o uso do documento como plano de execução.

---

## 2. Recomendações × estado real do código

| Recomendação do relatório | Estado real |
|---|---|
| Criar `services/` e `repositories/` (§29–33) | **Feito.** 14 repositórios, 47 serviços. Fase A concluída |
| Introduzir FastAPI progressivamente (§34, §57) | **Feito.** `backend_api/` com JWT, refresh token e rate limit; specs 0044–0063 |
| Aplicativo Flutter no futuro (§58) | **Existe.** `mobile/` com CI própria (`.github/workflows/mobile-ci.yml`) e 10+ telas entregues |
| Migrations versionadas (§44) | **26 migrations**, com rollback documentado e teste que barra tabela nova sem RLS (`tests/test_rls_nas_migrations.py`) |
| Preparar multi-fazenda (§45–46) | **Decidido e em execução.** [ADR 0001](adr/0001-multi-fazenda-schema-por-tenant.md) + [ADR 0004](adr/0004-conformidade-pnib.md): schema por organização + `property_id`, já `NOT NULL` desde a migration 0016 |
| Índices e RLS (§9–10) | 122 `CREATE INDEX`, 38 policies, negação explícita para `anon`/`authenticated` (migration 0024) |
| `st.cache_data` (§5) | Existe em `repositories/conexao.py` — 17 funções com `@_cache`, TTL 120 s |
| CI/CD (§42) | `.github/workflows/ci.yml`, testes verdes em SQLite **e** PostgreSQL |
| Não adotar Kubernetes/Redis/NoSQL agora (§67) | Concordância — nunca esteve em pauta |

Restam do documento inteiro **três** itens não implementados (seção 4).

---

## 3. A premissa invertida: o Supabase

O relatório assume que a aplicação usa o **SDK do Supabase**:

```python
supabase.table("animais").select("*").execute()     # §8 do relatório
```

**Não usa.** O [ADR 0002](adr/0002-fronteira-de-portabilidade.md) proibiu isso
deliberadamente. Verificação no código: **zero** ocorrências de `supabase-py`, Supabase
Auth, Storage ou Realtime. O acesso é `psycopg2` com SQL cru, ponto único em
`repositories/conexao.py::_conn()`. As fotos são `bytea` no próprio Postgres. A
autenticação é própria (PBKDF2/SHA-256 + JWT, em `backend_api/auth.py`).

Consequências diretas:

| Seção do relatório | Situação |
|---|---|
| §7 — problema N+1 do SDK | Descreve um padrão que não existe no código |
| §8 — `select("*")` baixando tudo | `grep` retorna **0 ocorrências** |
| §22, §23, §71 — "manter Supabase pelo Auth + Storage + Realtime + SDK Flutter" | Argumenta com os quatro recursos que o projeto **descartou de propósito** para evitar lock-in |
| §26 — Neon exigiria decidir Auth/Storage/Realtime à parte | Não exigiria: o projeto não usa nenhum dos três |
| §37 — nunca expor a `service role` | Não existe `service role` no projeto |

A conclusão do relatório ("manter o Supabase") continua **certa** — mas pelo motivo oposto
ao que ele apresenta. Aqui o Supabase é **Postgres gerenciado e nada mais**, e trocá-lo
seria apontar `DATABASE_URL` para outro host, exatamente como o ADR 0002 previu. Manter é
a escolha certa por não haver motivo para gastar a troca, não por dependência de
plataforma.

Correção factual adicional: o §12 supõe que a região do banco precisa ser verificada e
possivelmente migrada. Produção já está em **`aws-0-sa-east-1` (São Paulo)**, no
*transaction pooler* (porta 6543) — que é justamente o que o §25 recomenda.

---

## 4. Onde o relatório acerta

- **§11 — sair do Streamlit Community Cloud.** Procede. Recursos compartilhados,
  hospedagem nos EUA e hibernação após 12 h. A medição da seção 5.5 quantifica o custo
  da hibernação.
- **§41 — containerizar.** Não existe `Dockerfile` no repositório. É barato e destrava
  qualquer alvo de hospedagem.
- **§48 e §51 — medir antes de mexer.** O conselho mais útil do documento. Esta revisão
  executa esse pedido; o resultado está abaixo.
- **§43 — ambientes separados** e **§67 — não adotar Redis/Kubernetes agora.** Corretos,
  sem ressalvas.

---

## 5. Medição (o baseline que o §51 pede)

### 5.1 Método

- **Contagens** (conexões e queries por rerun): instrumentação de `sqlite3.connect`,
  rodando cada página pelo `AppTest` que a suíte já usa (`tests/ui_*_prova.py`).
- **Custo por operação:** `psycopg2` direto contra o Postgres **de produção**, somente
  leitura (`SELECT 1` e `count(*)`).
- **Perfil:** `cProfile` sobre o render, em processo frio e em processo quente.

### 5.2 Custo de rede — produção (`sa-east-1`, pooler 6543)

| Operação | Mediana | p95 |
|---|---:|---:|
| Conexão nova + `SELECT 1` (n=10) | **201,6 ms** | 1.753,8 ms |
| Query em conexão já aberta (n=20) | **24,4 ms** | 44,6 ms |

**Handshake ≈ 177 ms por conexão.** Cada `_conn()` custa o equivalente a ~8 queries.

### 5.3 Volume em produção

| Tabela | Registros |
|---|---:|
| `animals` | 14 |
| `weighings` | 42 |
| `animal_costs` | 28 |
| `medications` | 24 |
| `animal_movements` | 16 |

**Nada no sistema é limitado por volume de dados.** Toda a seção 7 do relatório (N+1 com
500 animais) trata de um regime que o AgroTop não alcançou.

### 5.4 Conexões e queries por rerun

Projeção = `conexões × 177 ms + queries × 24,4 ms`.

| Página | conex (frio) | conex (cache) | queries (cache) | **projeção produção** |
|---|---:|---:|---:|---:|
| **financeiro** | 37 | **29** | 51 | **6,38 s** |
| **dashboard** | 22 | **12** | 22 | **2,66 s** |
| desempenho | 14 | 8 | 18 | 1,86 s |
| alertas · sanitário · cadastrar | 11–15 | 4 | 14–16 | ~1,05 s |
| nutrição · relatórios · brincos · propriedades | 10–13 | 3 | 13 | ~0,85 s |
| campo · rebanho · lotes · estoque | 9–14 | 2 | 12 | **0,65 s** |

Contra as metas propostas no §49 do relatório (< 1 s para operações simples, < 2 s para
dashboards): **campo passa; dashboard e financeiro não.**

### 5.5 Cold start

Primeira execução do processo: **29,2 s apenas de import** — `pandas` sozinho 11,5 s, mais
plotly, opencv e pyproj. Não é custo por página (acontece uma vez por processo), mas é
exatamente o que o usuário paga **quando o app acorda da hibernação de 12 h**. É o
argumento medido a favor do §11 e do §18 do relatório.

### 5.6 Ressalvas

- Os tempos absolutos em milissegundos do `AppTest` estão inflados (ele materializa a
  árvore inteira de elementos). Por isso o que está reportado são **contagens**, que são
  exatas, projetadas pelo custo por operação medido contra produção.
- A medição de rede saiu de uma máquina no Brasil. Do Streamlit Cloud, nos EUA, para São
  Paulo, o handshake é **maior**, não menor. As projeções são otimistas.
- O volume de produção é pequeno. Se o rebanho crescer uma ordem de grandeza, o perfil
  muda e a medição precisa ser refeita.

---

## 6. O diagnóstico que o relatório não alcançou

**O gargalo é a quantidade de conexões abertas por rerun, não a quantidade nem o custo das
queries.** No financeiro, 5,1 s dos 6,4 s projetados são handshake puro.

Três achados concretos:

1. **`_conn()` abre uma conexão nova a cada uso** (`repositories/conexao.py`). Não há
   `cache_resource` nem pool do lado da aplicação. Com 177 ms de handshake, é o custo
   dominante de toda página.

2. **`init_db()` roda a cada rerun** (`app.py:78`). No Postgres o DDL é pulado, mas os
   seeds e backfills não: **1 conexão + 11 queries fixas** em toda interação, ~0,45 s.

3. **Qualquer gravação zera o cache inteiro.** As 65 funções com `@_writes` chamam
   `cache_data.clear()` global. Numa sessão de pesagem no curral, cada registro devolve a
   página seguinte à coluna "frio" — o financeiro vai a **8,0 s**.

Por que o financeiro é 3× pior que o resto: `page_financeiro` monta ~9 abas, e o
`st.tabs` renderiza **todos** os corpos a cada rerun, não apenas a aba aberta. Somado a
isso, `services/financeiro.py`, `caixa.py`, `dre.py`, `rentabilidade.py`, `rateio.py` e
`lancamentos.py` têm **zero** funções com `@_cache`.

---

## 7. Alterações recomendadas, em ordem

| # | Alteração | Onde | Ganho | Estado |
|---|---|---|---|---|
| 1 | Pool de conexões em vez de abrir uma por uso | `repositories/conexao.py::_conn()` | financeiro **−70%** de tempo de banco (medido) | ✅ **feito** |
| 2 | Guardar `init_db()` para rodar uma vez por processo | `database.py::init_db()` | −1 conexão e −11 queries por rerun (medido) | ✅ **feito** |
| 3 | Não fazer `commit()` em caminho de leitura | `repositories/conexao.py::_PGConn` | 49 dos 73 ms de cada `_conn()` (medido) | ✅ **feito** |
| 4 | `@_cache` nos seis serviços financeiros; revisar as abas do financeiro | `services/` + `app.py::page_financeiro` | ataca os 28 usos de `_conn()` do pior caso | pendente |
| 5 | `Dockerfile` | raiz | não muda latência; destrava a saída do Community Cloud | pendente |
| 6 | Sair do Streamlit Community Cloud | infraestrutura | elimina os 29,2 s de cold start pós-hibernação | pendente |

Os itens 1 e 2 estão implementados e medidos — ver seção 9. O item 3 **não existia** nesta
lista antes: só apareceu quando o pool tirou o handshake da frente e deixou ver o que havia
atrás. É a ilustração exata do §52 da Revisão 2 ("medir → alterar → medir de novo").

Os itens 1 a 3 são código, ficam em poucos arquivos e **valem mais, somados, do que a
migração de hospedagem**. O item 1 sozinho corta ~78% do tempo da pior página. Os itens 4
e 5 continuam justificados, mas por cold start e controle de recursos — não por latência
de página, que é o que o relatório sugere.

O item 1 é seguro precisamente por causa da regra R1 do ROADMAP: `_conn()` é o **ponto
único** de acesso ao banco em toda a aplicação. A mudança acontece em um lugar só.

---

## 8. O que fazer com o relatório

**Aproveitar:** §11 (sair do Community Cloud), §41 (Docker), §48/§51 (medir antes de mexer
— feito aqui), §43 (ambientes separados).

**Descartar:** §7, §8, §22, §23, §26 e §37, construídos sobre a premissa errada de uso do
SDK do Supabase; e §29–§34, §44–§46, §57–§58, porque descrevem trabalho já entregue.

A "arquitetura-alvo" do §38 e do §70 é, com pequenas diferenças de nomenclatura, **o estado
atual do projeto**. O relatório propõe chegar onde o AgroTop já está.

---

# 9. Fase 1 implementada — medição antes e depois

*Adicionado em 2026-08-29, depois da Revisão 2 do relatório externo.*

## 9.1 O que mudou no código

| Arquivo | Mudança |
|---|---|
| `repositories/conexao.py` | Pool de conexões Postgres. Cada `with _conn()` empresta uma conexão **só sua** e devolve ao sair. |
| `database.py` | `init_db()` roda uma vez por processo e por banco. `forcar=True` para os testes de idempotência. |
| `tests/test_pool_de_conexoes.py` | Novo. Trava a semântica de transação e a decisão de não agrupar SQLite. |
| `tools/medir_paginas.py` | Novo. Conta conexões e queries por página — o baseline versionado que o §39 da Revisão 2 pede. |
| `tools/medir_conexoes.py` | Novo. Mede o custo de conexão contra o Postgres real, com e sem pool. |

## 9.2 Correção à Revisão 2: pool, não conexão reutilizada

O §15 da Revisão 2 apresenta "conexão reutilizada" e "connection pool" como duas famílias
equivalentes, separadas por flexibilidade sob concorrência. **Não são equivalentes, e a
primeira é insegura neste código.**

`_conn()` é dono da transação: faz `commit()` ao sair e `rollback()` em erro. O Streamlit
atende cada sessão de navegador numa thread do mesmo processo. Uma conexão única
compartilhada faria o `rollback()` de uma sessão **abortar a gravação em voo de outra** —
perda de dado silenciosa com dois usuários simultâneos, que é o uso normal do AgroTop
(escritório e curral ao mesmo tempo).

Por isso a implementação empresta uma conexão por uso. `test_pool_de_conexoes.py::
test_rollback_de_uma_thread_nao_derruba_a_outra` é o teste que falha se alguém
"simplificar" para uma conexão compartilhada.

## 9.3 Decisão: só o Postgres é agrupado

A primeira versão da mudança agrupava também o SQLite. Foi revertido: uma conexão SQLite
ociosa mantém o arquivo aberto, e no Windows isso faz `os.remove()` levantar
`PermissionError` — quebrou `test_schema.py`, e quebraria `test_backend_api.py` no CI.

Abrir um SQLite é abrir arquivo local (~0,02 ms): não havia handshake nenhum a economizar.
Atrito garantido, ganho zero. `test_sqlite_nao_segura_o_arquivo` registra a decisão.

## 9.4 Medição direta contra produção

`tools/medir_conexoes.py`, contra `aws-0-sa-east-1` (pooler, 6543). Somente leitura,
mediana de 5 rodadas (3 nas linhas menores). Cada "ciclo" é um `with _conn()`:

| Forma da página | ciclos | sem pool | com pool | ganho |
|---|---:|---:|---:|---:|
| **financeiro** | 29 | 29 conexões · **7.395 ms** | 1 conexão · **2.179 ms** | **−71%** |
| **dashboard** | 12 | 12 conexões · 3.091 ms | 1 conexão · 1.004 ms | −68% |
| desempenho | 8 | 8 conexões · 1.886 ms | 1 conexão · 946 ms | −50% |
| páginas médias | 3 | 3 conexões · 681 ms | 1 conexão · 365 ms | −46% |
| campo · rebanho | 2 | 2 conexões · 493 ms | 1 conexão · 292 ms | −41% |

Isto é medição, não projeção: os dois lados rodaram contra o banco de produção.

## 9.5 Efeito da guarda do `init_db()`

`tools/medir_paginas.py`, antes e depois. O custo fixo por rerun:

```text
antes:   1 conexão + 11 queries
depois:  0 conexões + 0 queries
```

E toda página perdeu exatamente 1 uso de `_conn()` e 11 queries por rerun:

| Página (cache quente) | `_conn()` antes | `_conn()` depois | queries antes | queries depois |
|---|---:|---:|---:|---:|
| financeiro | 29 | 28 | 51 | 40 |
| dashboard | 12 | 11 | 22 | 11 |
| desempenho | 8 | 7 | 18 | 7 |
| mediana | 3 | 2 | 13 | 2 |

## 9.6 Resultado combinado

Somando o pool (medido) e a guarda (medida), o tempo de banco por rerun com cache quente:

| Página | antes | depois | ganho |
|---|---:|---:|---:|
| **financeiro** | 7,40 s | **2,23 s** | **−70%** |
| **dashboard** | 3,09 s | **0,98 s** | **−68%** |
| desempenho | 1,89 s | 0,69 s | −63% |
| mediana | 0,68 s | 0,32 s | −52% |
| campo · rebanho | 0,49 s | 0,25 s | −49% |

O "antes" é medido diretamente. O "depois" compõe dois valores medidos — um handshake por
processo (177 ms) mais o custo por uso de `_conn()` (73,4 ms) — com a contagem de usos que
o harness apurou. Para o financeiro e o dashboard há também medição pooled direta
(2.179 ms e 1.004 ms nas contagens pré-guarda), que confere com o modelo.

Contra as metas do §50 da Revisão 2: **dashboard passa** (P50 < 1 s). **Financeiro ainda
não** (meta P50 < 1,5 s, está em 2,23 s) — o item 3 da seção 7 é o caminho.

## 9.7 O gargalo seguinte, agora visível

Com o handshake fora do caminho, o custo de cada `with _conn()` passou a ser:

```text
query .................... 24,0 ms
commit ................... 49,4 ms
                           ────────
total por _conn() ........ 73,4 ms
```

**O `commit()` custa o dobro da query.** `_conn()` o dispara em todo uso, inclusive nos
puramente de leitura, que são a maioria absoluta de um rerun. Eliminar o commit no caminho
de leitura (ou abrir a conexão em `autocommit` para leitura) ataca 67% do que sobrou.

Isso não aparecia em nenhuma das duas versões do relatório externo, nem na primeira
medição desta revisão — estava escondido atrás dos 177 ms de handshake. É o argumento
concreto a favor do §52 da Revisão 2: medir de novo **depois** de cada alteração, porque
cada correção revela a próxima.

## 9.8 Verificação

- `tests/test_pool_de_conexoes.py`: 8 testes, verdes.
- Suíte completa: 702 testes. Os 3 erros restantes são de ambiente local, não da mudança
  — `jwt` e `hypothesis` não estão instalados neste `.venv` (constam de
  `backend_api/requirements.txt` e `requirements.txt`; o CI os instala). O terceiro erro,
  `test_schema.py::test_ddl_completo_sem_depender_do_migrate`, era regressão do pool de
  SQLite e **foi corrigido** pela decisão da seção 9.3.

---

# 10. Item 3 implementado — commit fora do caminho de leitura

*Adicionado em 2026-08-29, na sequência da seção 9.*

## 10.1 Por que não bastava "não dar commit"

A leitura ingênua do achado da seção 9.7 seria: se a maioria dos usos é leitura, pule o
`commit()`. Isso quebraria o sistema de um jeito difícil de enxergar.

No psycopg2 com `autocommit` desligado, **um `SELECT` já abre transação**. Sair sem commit
nem rollback devolveria ao pool uma conexão em `idle in transaction` — que, no *transaction
pooler* do Supabase, mantém presa a conexão de servidor até a transação encerrar. E trocar
o `COMMIT` por um `ROLLBACK` não economiza nada: é o mesmo ida-e-volta.

O único jeito de não pagar é **não abrir a transação**, o que precisa ser decidido *antes*
de executar o primeiro comando.

## 10.2 Como ficou

`_PGConn` nasce em `autocommit` e só sai dele quando aparece o primeiro comando de
escrita — aí volta ao modo transacional, e o `commit()` do `_conn()` passa a valer.

```text
SELECT, SELECT, SELECT          → autocommit o tempo todo, zero COMMIT
SELECT, UPDATE, SELECT, INSERT  → transação abre no UPDATE; tudo dali em diante
                                  confirma ou desfaz junto
```

A regra de classificação é conservadora: só `SELECT`, `EXPLAIN` e `SHOW` contam como
leitura. Qualquer outra coisa — DML, DDL, `SET`, `COPY`, CTE — abre transação. Classificar
escrita como leitura descartaria dado em silêncio; classificar leitura como escrita custa
49 ms. Os dois erros não são simétricos, e a regra erra para o lado barato.

**A atomicidade da escrita não muda.** Assim que o primeiro `INSERT`/`UPDATE` aparece,
todos os comandos seguintes — leituras inclusive — ficam na mesma transação. O que fica de
fora são as leituras *anteriores* à primeira escrita, e essas não dependem de nada que
ainda não aconteceu. O levantamento confirmou que não há `SELECT ... FOR UPDATE` nem
isolamento acima de READ COMMITTED no código do app: não havia trava nem *snapshot* a
preservar. (`tools/backup_banco.py` usa REPEATABLE READ, mas em conexão própria, fora do
`_conn()`.)

## 10.3 Medição

`tools/medir_conexoes.py`, contra produção, mediana de 5 rodadas. "Sem pool" é o
comportamento original; "com pool" é o estado atual, já com as três mudanças:

| Forma da página | ciclos | sem pool | seção 9 (só pool) | **agora** | ganho total |
|---|---:|---:|---:|---:|---:|
| **financeiro** | 29 | 6.669 ms | 2.179 ms | **902 ms** | **−86%** |
| **dashboard** | 12 | 2.830 ms | 1.004 ms | **453 ms** | **−84%** |
| desempenho | 8 | 1.909 ms | 946 ms | **351 ms** | −82% |
| campo · rebanho | 2 | 498 ms | 292 ms | **221 ms** | −56% |

Custo por `with _conn()` de leitura:

```text
antes do pool ......... 255,0 ms   (handshake + query + commit)
seção 9 (só pool) ......  73,4 ms   (query + commit)
agora ..................  25,0 ms   (query)
```

Os 25 ms batem com os 24,0 ms medidos para uma query pura em conexão aberta (seção 9.7):
não sobrou custo de transação nenhum no caminho de leitura.

## 10.4 Contra as metas

As metas do §50 da Revisão 2, que na seção 9.6 ainda não fechavam:

| Meta | Alvo | Antes | Agora |
|---|---|---:|---:|
| Dashboard P50 | < 1 s | 3,09 s ❌ | **0,45 s** ✅ |
| Financeiro P50 | < 1,5 s | 7,40 s ❌ | **0,90 s** ✅ |
| Páginas simples P50 | < 750 ms | 0,49 s ✅ | **0,22 s** ✅ |

As três passam. Os números de "agora" são conservadores: foram medidos na contagem de
ciclos *anterior* à guarda do `init_db()`, que tirou mais um uso de `_conn()` por página.

## 10.5 O que isso muda no plano

Os itens 4 e 5 da seção 7 (cache nos serviços financeiros, revisar `st.tabs`) perdem
urgência: o financeiro sai de 6,67 s para 0,90 s **sem tocar em uma linha de regra de
negócio**. Faz sentido re-medir antes de investir ali — pode não haver mais problema para
resolver.

O que sobra da lista é infraestrutura, e por motivo próprio, não por latência de página:
`Dockerfile` e saída do Community Cloud, para resolver os 29,2 s de cold start
pós-hibernação (seção 5.5). Esse número não mudou e nenhuma das três correções o toca.

## 10.6 Verificação

- `tests/test_pool_de_conexoes.py`: 16 testes, verdes. Os 9 novos exercitam `_PGConn`
  direto, com conexão falsa — a suíte roda em SQLite, que já não abre transação para
  `SELECT` e portanto não exercitaria esta lógica.
- Leitura real contra produção conferida pelos dois acessos que o código usa
  (`row[0]` e `row['coluna']`), com `autocommit` confirmado ativo e nenhuma transação
  aberta.
- A validação do caminho de **escrita** em Postgres cabe ao CI, que roda a suíte inteira
  contra um Postgres efêmero. Não foi exercitada localmente: só há Postgres de produção
  aqui, e nenhuma medição justifica escrever nele.

---

# 11. Causa raiz da falha da migration 0027

*Adicionado em 2026-08-31. Não estava no escopo dos relatórios externos — apareceu porque
o CI do PR desta revisão foi o primeiro a rodar depois que a cadeia de migrations passou a
ser replayada por inteiro.*

## 11.1 Como apareceu

O CI do PR #256 (seções 9 e 10) morreu **antes de qualquer teste rodar**, no passo que
aplica as migrations num Postgres efêmero:

```text
psql:supabase/migrations/0027_remove_indice_duplicado_animals.sql:86:
ERROR:  constraint "animals_uuid_key" of relation "animals" does not exist
```

Não era do PR: a `main` já estava vermelha pelo mesmo motivo. O commit que expôs o
problema foi justamente o que passou a **aplicar todas as migrations** no Postgres
efêmero — antes disso, a divergência existia e ficava invisível.

## 11.2 Os dois fatos que não fechavam

A leitura do repositório dizia que a constraint deveria existir:

- `0000_baseline_producao.sql` **declara** `CONSTRAINT animals_uuid_key UNIQUE (uuid)`;
- nenhuma migration entre a 0007 e a 0026 a remove;
- e o log mostrava as **14 FKs para `animals(uuid)` sendo removidas sem erro** nas linhas
  imediatamente anteriores — ou seja, havia FKs apontando para aquela coluna.

Três leituras estáticas seguidas não resolveram. O que resolveu foi medir.

## 11.3 O diagnóstico

Docker estava indisponível na máquina, mas **o CI já é o Postgres efêmero** — é a
reprodução, de graça e configurada. Uma branch descartável instrumentou o workflow para
tirar um retrato de `pg_constraint` e `pg_indexes` logo depois do baseline.

Resultado, num PG16 limpo:

```text
animals_id_key | u | UNIQUE (id)
animals_pkey   | p | PRIMARY KEY (uuid)
```

**`animals_uuid_key` não existe** — apesar de o baseline declará-la. Os índices confirmam:
nenhum com esse nome.

## 11.4 A causa

Quando um `CREATE TABLE` declara `PRIMARY KEY (uuid)` e `UNIQUE (uuid)` sobre a **mesma
coluna**, o PostgreSQL descarta a segunda **em silêncio** — sem erro, sem aviso:

```sql
CREATE TABLE animals (
    ...
    CONSTRAINT animals_pkey     PRIMARY KEY (uuid),
    CONSTRAINT animals_uuid_key UNIQUE (uuid)   -- nunca nasce
);
```

Isso explica os dois fatos de uma vez: o `DROP CONSTRAINT` reclamava de algo que nunca
chegou a existir, e as 14 FKs saíram sem erro porque existiam — amarradas a
`animals_pkey`.

Em produção a constraint existe porque foi construída **em passos**: a 0002 criou
`idx_animals_uuid`, a 0005 promoveu o índice a UNIQUE com `ADD CONSTRAINT ... USING
INDEX`, e só a 0017 tornou `uuid` a chave primária. Por `ALTER TABLE` separado o Postgres
cria normalmente; é a declaração inline junto da PK que ele engole.

## 11.5 O problema real não era a 0027

> **O baseline descrevia um schema que não reproduzia.**

Qualquer migration futura que dependesse de uma constraint redundante com a PK divergiria
do mesmo jeito, em silêncio. E o guarda que deveria pegar isso não pega:
`test_schema_local_nao_divergiu_da_producao` compara **colunas**, não constraints.

A 0027 não foi o defeito — foi o primeiro lugar onde o defeito encostou.

## 11.6 Correções

| PR | O quê | Estado |
|---|---|---|
| #258 | `DROP CONSTRAINT IF EXISTS` na 0027 | mesclado — trata o sintoma |
| #263 | UNIQUE redundante com a PK sai do `CREATE TABLE`, no gerador e no baseline; `tests/test_dump_baseline.py` trava os dois | mesclado |

O `IF EXISTS` continua valendo como guarda barata. A correção de fundo é a segunda:
`tools/dump_schema_nuvem.py` passa a emitir essas constraints como `ALTER TABLE ADD
CONSTRAINT` separado, e o baseline em disco foi corrigido cirurgicamente — o snapshot de
2026-08-19 continua representando o mesmo estado de produção, agora replayável.

## 11.7 O que isto reforça

O §52 da Revisão 2 propõe **medir → identificar → alterar → medir de novo**. Esta seção é
o mesmo princípio aplicado a schema, e com a mesma lição da seção 10.5: a leitura atenta
do código deu três explicações plausíveis e nenhuma correta. O que fechou foi consultar o
catálogo do banco.

Vale registrar também o custo de não medir: a hipótese inicial anotada no commit do #258
(as FKs nascerem amarradas a `animals_pkey`) estava **certa no fato e errada na
consequência** — concluía que a constraint ficaria sem referências, quando na verdade ela
não é criada. Uma hipótese quase certa produziu a correção certa pelo motivo errado, e o
motivo errado é o que teria deixado o problema de fundo passar.
