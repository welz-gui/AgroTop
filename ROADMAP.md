# AgroTop — Roadmap de Execução

> **Para quem chega agora (humano ou agente de IA):** leia as seções 1 a 3 antes de
> escrever qualquer linha de código. Elas contêm decisões já tomadas e regras que,
> se violadas, quebram produção ou desfazem trabalho feito.

Última atualização: 2026-08-05 · Estado: **Fases A, B e B-UI CONCLUÍDAS · Fase B 100% ligada à interface (7 de 7)** · fila de specs em 2

---

## 1. Onde o projeto está

Sistema de gestão de gado de corte. **Streamlit + PostgreSQL (Supabase)** em produção,
SQLite para desenvolvimento e teste.

| | |
|---|---|
| Produção | Streamlit Community Cloud, deploy automático a cada push na `main` |
| Banco | Supabase, projeto `mwjvulwglewoyeximgtv`, plano **free** (sem branches de banco) |
| Schema | **375 colunas / 33 tabelas**, paridade total entre DDL local e produção |
| Testes | **512**, verdes no CI em SQLite **e** PostgreSQL · ~9 min (7 provas de interface + testes de propriedade) |
| Código | `app.py` (~3.900) · `database.py` (~2.100, fachada) · `repositories/` (12) · `services/` (29) · `ui/` · `tools/` (6) |
| Integração | **18 de 29 services usados** (29 é novo: 3 chegaram desde ontem, ainda órfãos) · todos os 7 repositórios da Fase B com tela |
| Segurança | 🟢 nenhuma dívida aberta — RLS em 100% das tabelas, verificado em 2026-08-05 |
| Rebanho real | ~150–200 animais ativos + histórico (os 14 do banco atual são **dados fictícios de seed**) |

> ⚠️ **Esta tabela envelhece rápido.** Em 2026-08-03 ela ainda dizia "21 testes" e "Fase A em
> execução", meses depois de as duas coisas terem mudado. Se os números aqui não baterem com
> o que você vê, **confie no código** e corrija esta tabela (R32).

### Funcionalidades em produção
Cadastro (animais, lotes/piquetes, fornecedores, insumos) · pesagens, curva de peso,
GMD híbrido (recente + de vida) · ficha individual · movimentações · medicamentos,
protocolos, carência · planos de trato · custos individuais e fixos · vendas, resultado,
margem, breakeven · mortalidade · alertas · previsão do tempo e pluviometria ·
simulador de terminação · ranking de fornecedor · exportação CSV/Excel/PDF ·
login por cookie · câmera (QR + OCR de brinco + foto).

### Decisões de arquitetura já tomadas (não reabrir sem motivo novo)
- **[ADR 0004](docs/adr/0004-conformidade-pnib.md)** ⭐ — **conformidade com o PNIB**:
  chave surrogate em `animals`, identificadores separados, hierarquia
  Organização→Produtor→Propriedade e eventos imutáveis. **Reordena todo o roadmap.**
- **[ADR 0001](docs/adr/0001-multi-fazenda-schema-por-tenant.md)** — ⚠️ **parcialmente
  substituído pelo 0004**: tenancy passa a ser schema por **organização** + `property_id`,
  e o cancelamento de `roles`/`permissions` fica revogado.
- **[ADR 0002](docs/adr/0002-fronteira-de-portabilidade.md)** — Postgres é permanente,
  o provedor é substituível; **Supabase Auth vetado**.
- **[ADR 0005](docs/adr/0005-fila-de-sincronizacao.md)** — a fila de sincronização (§10.3)
  fica **fora** de `animal_events`, em `evento_sincronizacao`. Nenhuma exceção ao gatilho
  append-only: nada em `animal_events` muda, nunca.
- **[supabase/README.md](supabase/README.md)** — fluxo de alteração de schema.

---

## 2. Regras invioláveis

Violar qualquer uma destas quebra produção, desfaz decisão registrada, ou reintroduz
um bug que já custou tempo. Cada regra tem histórico.

> O número da regra é **identificador estável**, não ordem de leitura: regras novas recebem
> o próximo número livre e ficam na seção temática a que pertencem. Por isso a sequência
> aparece fora de ordem entre as seções. Nunca renumere — os números são citados em commits,
> em PRs e no [DESIGN.md](DESIGN.md).

### 2.1 Banco de dados

**R1. `_conn()` é o único ponto de acesso ao banco.** Nunca chamar `psycopg2.connect`
nem `sqlite3.connect` fora dele. São 82 usos e um único ponto de criação — é isso que
torna viável rotear por tenant no futuro (ADR 0001) e trocar de provedor (ADR 0002).

**R2. Toda coluna vai no `CREATE TABLE` do `init_db()`, não só no `_migrate()`.**
`_migrate()` existe **apenas** para atualizar bancos SQLite antigos.
*Histórico: `protocol_id`/`lote_id` só existiam como `ALTER` → `init_db()` quebrava em
banco novo e o CI ficou vermelho (`75dce18`). Depois `purchase_mode`/`purchase_lot_ref`
tinham o mesmo defeito.* Guardado por `test_ddl_completo_sem_depender_do_migrate`.

**R3. `CREATE TABLE` só dentro do DDL canônico de `init_db()`.** Nunca criar tabela sob
demanda dentro de função.
*Histórico: `sessions` era criada por três `CREATE TABLE IF NOT EXISTS` idênticos dentro
de funções — um banco novo ficava sem a tabela até o primeiro login (`599162a`).*
Guardado por `test_create_table_apenas_no_ddl_canonico`.

**R4. Ao alterar schema, seguir o fluxo de [supabase/README.md](supabase/README.md):**
migration na nuvem → ajustar o DDL de `init_db()` → `python tools/dump_schema_nuvem.py
--baseline` → `python tools/testar_baseline.py` → rodar os testes.
Pular o passo 2 faz `test_schema_local_nao_divergiu_da_producao` falhar.

**R5. Datas de negócio são TEXT ISO (`YYYY-MM-DD`)** nos dois bancos. Não introduzir tipo
`date`/`timestamp` em coluna nova de data de negócio — quebraria a compatibilidade dupla.

⚠️ **Exceção (ADR 0004):** `animal_events` e `audit_logs` usam **`timestamptz`**, com
`ocorrido_em` e `registrado_em` separados. Em evento regulatório o momento da comunicação
tem valor jurídico, e a diferença entre o fato e o registro é auditável (§6.2 do PNIB).

**R6.** ~~Não adicionar `farm_id` a nenhuma tabela.~~ ⚠️ **REVOGADA** pelo
[ADR 0004](docs/adr/0004-conformidade-pnib.md). O PNIB exige hierarquia com múltiplas
propriedades por titular (§3.1) e movimentação entre elas (§8.1). O modelo passa a ser
**schema por organização + `property_id`** nas tabelas de negócio.

**R7. `INSERT OR REPLACE` precisa de ramo `ON CONFLICT ... DO UPDATE` para Postgres.**
Ver `create_session`, `set_category_price`, `set_setting`.

### 2.2 Regra de negócio

**R8. Cada regra vive em UM lugar.** Nunca reimplementar cálculo que já existe.
*Histórico: `simular_terminacao` chegou a existir em três cópias — `database.py`,
`backend_api/services/terminacao_service.py` e `simulador_terminacao_page.dart`.*
Quando a API for criada, ela **importa** os services; não recopia.

**R9. `database.py` e os futuros `services/` não importam `streamlit` no topo do módulo.**
Use import preguiçoso com fallback (padrão em `_cache` e `_database_url`). É o que permite
que a regra de negócio sirva à API, ao mobile e a jobs agendados.
Guardado por `tests/test_portabilidade.py`.

**R10. Toda função de gravação leva `@_writes`** (limpa o cache após gravar). Sem isso o
usuário não vê a própria alteração por até 120 s.

**R11. Não quebrar os bulk loaders cacheados** (`_weighings_by_animal`,
`_medications_by_animal`, `_costs_by_animal`). Eles levaram o dashboard de ~40 s
(timeout) para ~2 s. Ler desses dicts, não consultar por animal em laço.

### 2.3 Interface

**R12. NUNCA criar um diretório `pages/`.** O Streamlit tem convenção nativa para esse
nome: geraria navegação automática e **cada arquivo ficaria acessível por URL direta, sem
passar pelo `main()`** — furando o guard de perfil de [app.py:3251](app.py:3251) e dando a
um operador acesso ao Financeiro. Use **`views/`**. Se um dia quiser multipage nativo, use
`st.navigation`/`st.Page` com a lista filtrada por perfil.

**R13. Preservar o guard de perfil.** `OPERATOR_PAGES` e a checagem em `main()`. Qualquer
página nova precisa passar por ali, e a decisão de incluir ou não é de conteúdo, não de
conveniência: `brincos` entrou em 2026-08-04 porque aplicar brinco é trabalho de curral;
`movimentacao` ficou de fora porque liberar GTA é ato administrativo.

**R14. Escapar `R\$` em markdown.** Dois `$` na mesma string viram fórmula LaTeX e o
Streamlit engole os cifrões. Em f-string: `R\\$`. `column_config` com
`format="R$ %.2f"` **não** é afetado.
*Histórico: commit `d91b66e`.*

**R15. Câmera só sob demanda.** `st.camera_input` apenas depois de clicar "Abrir câmera".
O Streamlit renderiza todas as abas, então instanciar direto liga a câmera em aba de fundo.

**R20. Cor vem do dicionário de temas, nunca hex literal.** Ver [DESIGN.md](DESIGN.md).
Escolher pelo significado (`sucesso`, `atencao`, `perigo`), não pela aparência. Hoje há
200+ hex hardcoded em `app.py` — a extração acontece na Fase A2, e depois dela a regra vale
sem exceção. **O tema é escolha do usuário (escuro/claro), no web e no mobile**, o que torna
a extração pré-requisito: hex literal não responde à troca de tema.

⚠️ **Exceção — ativos estáticos.** Arquivos que não executam Python (`manifest.json`,
`favicon`, ícones) **não conseguem** importar a paleta, então repetem o valor. É duplicação
inevitável, mas precisa ser **declarada**: ao alterar `primaria` ou `fundo` em
`ui/tema.py`, atualize também `static/manifest.json`. *(Surgiu no PR #31, o PWA.)*

**R21. Informação nunca depende só de cor.** Sempre com ícone ou texto. No sol, com tela
suja ou para quem tem daltonismo, cor sozinha não comunica.

**R22. Componente visual novo entra no inventário do [DESIGN.md](DESIGN.md)** (seção 5), com
o equivalente mobile. É o que impede web e app de virarem dois produtos diferentes — o app
abandonado divergiu exatamente assim (tema claro e paleta própria).

### 2.4 Testes e segurança

**R16. Rodar os testes SEMPRE com `-t .`:**
```bash
python -m unittest discover -s tests -t . -v
```
Sem `-t .`, `tests/__init__.py` não é importado, `AGROTOP_FORCE_SQLITE` não é definida e —
com `.streamlit/secrets.toml` presente — os testes conectam em **PRODUÇÃO**.
`tests/test_isolamento.py` falha de propósito nesse caso.

**R17. Todo teste que chame `init_db()` roda em SQLite.** A proteção do item R16 cobre isso;
não a contorne.

**R18. Nunca logar, imprimir ou colocar em mensagem de erro o valor de `DATABASE_URL`.**
Ela contém a senha do banco.
*Histórico: aconteceu duas vezes; a senha está pendente de rotação.*

**R19. Segredos só em `secrets.toml` (gitignored) ou env var.** Nunca no código, nunca em
commit.

---

## 3. O que pode mudar, o que deve ser mantido

### Pode mudar livremente
- Organização de arquivos (é justamente o objetivo da Fase A/B).
- Nomes internos de funções privadas (prefixo `_`), desde que os chamadores acompanhem.
- Layout, textos e componentes de UI.
- Adicionar tabelas e colunas novas — seguindo R4.
- Adicionar dependências, se justificadas no PR.

### Deve ser mantido (comportamento observável)
- **Resultados numéricos das regras atuais.** GMD híbrido (recente e de vida), custo total,
  breakeven, valor esperado de venda, carência, projeção de abate, simulador de terminação,
  ranking de fornecedor. A Fase A congela esses números em testes; depois dela, qualquer
  mudança de resultado é **quebra de contrato** e precisa ser intencional e declarada.
- **Constantes de negócio:** `KG_PER_ARROBA = 15.0`, `CARCASS_YIELD = 0.52` (default),
  `UA_WEIGHT = 450.0`. Alterar muda todo o histórico calculado.
- **Autenticação:** tabela `users` própria com PBKDF2 + aceitação de hash legado SHA-256 e
  migração no login. Login persistente por cookie (`agrotop_sid`, 7 dias).
- **Perfis** `admin` / `operator`.
- **Backup xlsx não inclui `animal_photos`** (bytea) — de propósito.
- **Fotos em `bytea` no Postgres** — não migrar para storage externo sem ADR (R: ADR 0002).

### Não fazer (decidido)
- `farm_id`, `farms`, `farm_users`, `roles`, `permissions`, `role_permissions`, os 7 perfis,
  seletor de propriedade — cancelados pelo ADR 0001.
- Supabase Auth, Storage, Realtime — vetados pelo ADR 0002.
- Módulo de reprodução/IATF — descartado pelo usuário.
- ORM ou camada de abstração para "trocar de banco" — ADR 0002.
- Integração Bluetooth pelo navegador — impossível; é do app nativo (Trilha 1).
- Modelos estatísticos antes de haver dados reais — ver Trilha 4.

---

## 4. Fase A — fundação ✅ CONCLUÍDA

**Por que sequencial:** as etapas A1 e A2 reescrevem os mesmos dois arquivos de 5.700
linhas. Paralelizar aqui gera conflito de merge que custa mais do que economiza.
**O refactor é o que habilita o paralelismo** — as trilhas da seção 5 só abrem depois dele.

### A1 — Testes de caracterização

**Objetivo:** congelar o comportamento atual das regras de negócio **antes** de mover código.
Hoje, dos 21 testes, nenhum cobre GMD, custo, carência, estoque ou venda.

**Regra de ouro:** caracterizar, não corrigir. O teste documenta o que o código faz **hoje**,
inclusive comportamentos estranhos. Se encontrar um bug, **relate ao usuário e não altere** —
mudar o número silenciosamente altera relatórios que ele já usa.

Cobertura mínima: `calculate_gmd`, `calculate_gmd_total`, `get_total_cost`,
`expected_sale_value`, `get_withdrawal_end`, `projecao_abate`, `register_sale` (os três
modos de precificação), `register_death`, baixa de estoque, `kg_to_arrobas`,
`get_age_category`, `get_rebanho_stats`.

**Pronto quando:** cada regra acima tem teste com valores esperados explícitos; suíte verde
no CI; nenhum comportamento alterado.

### A2 — `database.py` → repositórios e serviços

Estrutura alvo:
```
repositories/   consultas SQL, uma por agregado (animals, weighings, insumos, finance…)
services/       regra de negócio, sem SQL e sem Streamlit
database.py     mantido como fachada fina durante a transição
```

**Método:** mover em fatias pequenas, rodando a suíte a cada fatia. `database.py` continua
exportando os mesmos nomes (re-export) até o fim, para `app.py` não quebrar de uma vez.

**Pronto quando:** nenhuma regra de negócio contém SQL; nenhum repositório importa
`streamlit`; os testes de A1 passam sem alteração; `test_portabilidade` continua verde.

### A2b — Extrair a paleta de cores

Junto do refactor, porque os mesmos arquivos já estão sendo tocados: trocar os 200+ hex
literais de `app.py` pelo dicionário de temas do [DESIGN.md](DESIGN.md). Sem alteração
visual — o tema escuro atual passa a ser o padrão do dicionário.

Habilita o **seletor de tema (escuro/claro) pelo usuário**, que é decisão de produto já
tomada. Fazer depois custa muito mais: hex literal não responde a troca de tema.

### A3 — Auditoria

`audit_logs` + `created_by`/`updated_by` nos registros relevantes. Aditivo, baixo risco.
Seguir R4 para o schema.

---

## 4.1 ⚠️ Reordenação pelo ADR 0004 (PNIB)

A decisão de conformidade com o PNIB **antecede** as trilhas 1–4. Construir Financeiro,
Nutrição ou Mobile antes da chave surrogate é erguer sobre fundação que será trocada.

**Nova Fase B — fundação regulatória**, na ordem:

| # | Etapa | Por que aqui |
|---|---|---|
| B1 | ✅ **Chave surrogate + `animal_identifiers`** | concluída em 2026-08-02, seis etapas |
| B2 | ✅ **`animal_events` + auditoria** | concluída em 2026-08-02, append-only por gatilho |
| B3 | ✅ **Genealogia e nascimentos** | concluída em 2026-08-03 — `partos`, vínculo materno auditado, pendências do §7.3 |
| B4 | ✅ **Hierarquia de propriedades** | concluída em 2026-08-03 — `properties` + `property_id`; falta só a B4.3 (NOT NULL) |
| B5 | ✅ **Motor de regras regulatórias** | concluída em 2026-08-03 — regras como dado, com vigência, versionamento e simulação |
| B6 | ✅ **Movimentações entre propriedades + GTA** | concluída em 2026-08-03 — três níveis do §8.4, divergência de recepção |
| B7 | ✅ **Módulo de dispositivos (brincos)** | concluída em 2026-08-03 — 12 estados, conferência visual×eletrônico, inventário |
| — | **Integrações oficiais** | ⛔ **Bloqueado**: as APIs não existem, e o §23 lista 19 pontos não confirmados |

### ✅ Fase B CONCLUÍDA em 2026-08-03

Todas as sete etapas (B1 a B7) estão em produção. O AgroTop tem agora a fundação
regulatória que o PNIB exige: identidade imutável separada do brinco, eventos e
auditoria append-only, genealogia, hierarquia de propriedades, movimentação com
GTA, estoque de dispositivos e motor de regras configurável com vigência.

**O que a Fase B NÃO fez, e é proposital:** nada disso estava ligado à interface
quando ela terminou. As tabelas existem, as regras existem, os repositórios
existem — faltava a tela. É o trabalho que veio a seguir, e é o que transforma
conformidade de arquitetura em conformidade de uso. **A integração começou em
2026-08-04, pelo nascimento (§7), pelos brincos (§5) e pela movimentação com GTA
(§8)**; ver a dívida nº 1 na seção 11 para o que falta.

### ⚠️ Revisão de 2026-08-01 — o gate é B1+B2, não B1–B7

O ADR 0004 disse que a Fase B inteira antecede as trilhas. **Revisando com o que as PoCs
mostraram, isso é conservador demais** e cria um risco maior que o que evita.

**Só B1, B2 e B4 são fundacionais** — mudam identidade, como o estado é derivado, e o
escopo de toda tabela. **B3, B5, B6 e B7 são módulos aditivos**: genealogia, regras
regulatórias, movimentações e dispositivos não invalidam trabalho feito em Financeiro ou
Nutrição. Podem intercalar com as trilhas.

**O risco de não corrigir isso:** modo fundação permanente. Numa sessão inteira, o que
chegou ao usuário foi custo médio ponderado, detecção de peso suspeito, importação CSV e
PWA — todo o resto foi encanamento. Projetos não morrem por falha técnica; morrem por
passar tempo demais sem entregar nada visível.

**Regra prática:** depois de B1, entregar **uma coisa visível** antes de seguir para B2.

**Cumprida em 2026-08-01** ([#44](https://github.com/welz-gui/AgroTop/pull/44)): importação
de pesagens por CSV e máquina de estados chegaram à interface. Eram funções puras entregues
por agentes que estavam prontas e ligadas a nada — o sintoma exato do modo fundação.
**Três ainda estão nessa situação:** `identificadores`, `validacao_regulatoria` e
`recomendacoes` (ver `specs/QUADRO.md`).

**Efeito colateral que vale registrar:** o teste de interface criado para provar a máquina
de estados foi a **primeira coisa a importar `app.py` num teste** — e achou na hora um
defeito que tornava o app inimportável em Python ≤ 3.13 (`Optional` usado sem import,
mascarado pela PEP 649 no 3.14). Nenhum dos 197 testes anteriores tocava `app.py`.

### O que as PoCs mudaram

| Achado | Efeito no plano |
|---|---|
| **NDVI é sazonal em MT** — 2ª tentativa: **maior vão de 105 dias** a 20 % de nuvem, 205 a 10 % | Satélite vira ferramenta de **seca (mai–set)**, não monitoramento contínuo. **10b rebaixado**; 10a (geometria) **não** é afetada e se paga sozinha pela área calculada |
| **O NDVI tem sinal real** — amplitude 0,3535–0,8055 com queda coerente em ago–set | Vale construir o módulo **para tendência e conferência periódica**; não prometer alerta rápido na chuva. Segue **não equivalendo** a matéria seca sem calibração de campo |
| **Modelos batem a linha de base com 3 meses**; 12 meses para piloto sazonal | Corrige minha estimativa anterior de "2–3 anos". Mas o gate real **não é tempo, é a Trilha 3** — as features de custo e nutrição vêm dela |
| **`streamlit-folium` + `shapely` + `pyproj`** recomendados | Trilha 2 destravada tecnicamente |
| `services/` e `repositories/` existem | **A API da Trilha 1 está destravada** — é casca fina sobre o que já há |

**A Fase A vira pré-requisito, não higiene:** a etapa 5 da migração do ADR 0004 depende de
as consultas estarem concentradas em `repositories/`. Sem isso, a troca da chave espalha-se
por todo o `database.py`.

As trilhas 1–4 abaixo continuam válidas, mas **depois** de B1–B4.

## 5. Trilhas paralelas — **abertas** (Fase A e B concluídas)

> ⚠️ **Antes de abrir trilha nova, leia a dívida nº 1 da seção 11.** Sete módulos da Fase B
> existem e não têm tela. Começar trilha antes de ligá-los aumenta a distância entre o que o
> sistema faz e o que ele mostra — que já é a maior da história do projeto.

Regras gerais para trabalho paralelo:

- **Um dono por trilha.** Não editar arquivo que é núcleo de outra trilha.
- **Cada trilha em seu branch** (e, idealmente, git worktree próprio).
- **Banco de produção é único** (plano free, sem branches). Desenvolva contra **SQLite**;
  toda migration passa pelo dono do schema, serializada. Nunca duas migrations concorrentes.
- **Antes de abrir PR:** `python -m unittest discover -s tests -t . -v` verde +
  `python -m compileall app.py database.py tests tools` + se tocou schema,
  `tools/dump_schema_nuvem.py --baseline` e `tools/testar_baseline.py`.
- **Leia as seções 2 e 3 deste arquivo.** Elas valem para todas as trilhas.

---

### Trilha 1 — API + Aplicativo mobile nativo

**Prioridade do usuário: alta.** Não deixar para o fim.

**Pré-requisito:** Fase A completa (a API é uma casca sobre `services/`).

**Etapas**
1. **API (FastAPI)** sobre os `services/`. Aproveitar a *estrutura* de
   `backend_api/` do branch arquivado: `git show archive/app-mobile-obsoleto:backend_api/main.py`.
   **Não aproveitar a lógica** — o `terminacao_service.py` de lá duplica regra (R8).
2. **Mobile v1 — online.** Flutter. Escopo limitado ao que o web **já faz**: consulta e
   busca de animais, leitura de brinco (QR/câmera nativa), pesagem, movimentação entre lotes,
   sanidade, consulta de carência, foto, confirmação de trato.
3. **Importação CSV do indicador da balança.** Caminho universal, funciona em qualquer
   plataforma. Fazer junto da v1 — será necessário mesmo com Bluetooth, porque pareamento
   falha no campo.
4. **Bluetooth (balança e leitor de brinco).** Somente com o equipamento em mãos: **não
   existe protocolo padrão**, cada marca tem seu formato. Implementar como **um driver por
   modelo**, parseando linha → `(peso, brinco)`, atrás de uma interface — assim uma segunda
   marca depois fica contida.
5. **Mobile v2 — offline + fila de sincronização.** Deixado para o fim de propósito: é a
   parte caríssima (idempotência, conflitos, ordem de dependência) e não deve bloquear a
   Trilha 3.

**Regras específicas**
- **Autenticação pela própria API**, contra a tabela `users`. **Supabase Auth é vetado**
  (ADR 0002): as identidades sairiam do seu banco e criariam dois modelos incompatíveis
  com o web.
- **O app nunca fala direto com o Postgres nem com PostgREST**, e nunca usa credencial
  administrativa. Regra de negócio fica no backend.
- **iOS fica em aberto.** Mantenha o código Flutter buildável para os dois. Atenção: muitos
  equipamentos de pecuária usam **Bluetooth Classic (SPP)**, que o **iOS não permite** a apps
  de terceiros (só BLE ou acessório MFi). Portanto o recurso de Bluetooth pode ser
  Android-only — projete para **degradar com elegância**, não para assumir Android.
- **Não** copiar tela, repositório ou fluxo do app obsoleto. Ele tinha login simulado,
  consultava colunas inexistentes (`animal_id`, `gmd`, `category`, `origin`) e devolvia
  **3 animais fictícios** num `catch` silencioso.
- **Design espelha o [DESIGN.md](DESIGN.md).** O `app_colors.dart` é **gerado** a partir da
  mesma paleta semântica, nunca escrito à mão — foi assim que o app abandonado virou um
  produto visualmente diferente (tema claro, verde floresta, acento dourado).
  Suportar **escuro, claro e "seguir o sistema"** desde a v1: retrofitar tema depois custa
  mais que nascer com os dois. Ver também as regras de campo (DESIGN.md seção 6).

**Decisões operacionais pendentes:** hospedar a API (não roda no Streamlit Cloud —
Render/Fly/Railway); build iOS exige Mac ou serviço em nuvem; contas de loja (Apple
US$ 99/ano, Google US$ 25 único). Recomendação: **Android primeiro, APK direto**, sem loja.

**Pronto quando:** o operador executa pesagem, movimentação e sanidade pelo celular, com
autoria e horário registrados, e o resultado aparece no web.

---

### Trilha 2 — Geometria dos piquetes e GPS

**Prioridade do usuário: alta.** Menor colisão entre as trilhas — boa primeira candidata.

**Pré-requisito:** Fase A completa. Independe da Trilha 1 (mas o GPS depende do mobile v1).

**Escopo**
1. Mapa da propriedade; desenhar ou importar o polígono de cada piquete; guardar a geometria.
2. **Área calculada a partir do polígono.** Hoje `area_ha` é **digitada à mão**
   ([app.py:1390](app.py:1390)) — e ela alimenta `capacity_ua` e a lotação UA/ha do dashboard,
   que herda qualquer erro de digitação. **Este item se paga sozinho, sem satélite nenhum.**
3. Localização do piquete (centroide) — útil também para a previsão do tempo, hoje presa a
   uma coordenada única da fazenda (`farm_lat`/`farm_lon`).
4. Demarcação por **GPS caminhando o perímetro** — no mobile (depende da Trilha 1, etapa 2).

**Técnico:** **PostGIS 3.3.7 está disponível** no projeto (não instalado). É extensão padrão
do Postgres, compatível com o ADR 0002. Cálculo de área em projeção geográfica é traiçoeiro
de fazer à mão — vale a extensão. Alternativa mais simples: GeoJSON em `JSONB`.
Instalar extensão é mudança de schema: seguir R4.

**Regras específicas**
- Não remover `lotes.area_ha`; passe a **derivá-la** do polígono e mantenha a digitação
  manual como fallback para piquete sem geometria.
- NDVI **não** entra nesta trilha (ver Trilha 4).

**Pronto quando:** cada piquete tem polígono, a área exibida vem da geometria, e piquete sem
polígono continua funcionando como hoje.

---

### Trilha 3 — Estoque → Financeiro → Nutrição

**A trilha que gera as features dos modelos preditivos.** Não a deixe morrer: sem ela, a
Trilha 4 nunca se torna possível.

**Pré-requisito:** Fase A completa. É a trilha com **mais mudança de schema** — o dono desta
trilha deve ser o **dono do schema** durante o trabalho paralelo.

**Ordem obrigatória:** Estoque **antes** de Financeiro (compra gera conta a pagar), e
Financeiro antes de Nutrição (a dieta precisa apropriar custo).

**Escopo resumido:** pedido e compra, documento fiscal, entrada automática, lotes de
fabricação e validade, custo médio ponderado, transferências, inventário e ajuste, previsão
de dias restantes · contas a pagar/receber, parcelas, caixa, centros de custo, competência ×
caixa, fluxo realizado e projetado, DRE gerencial, custo por kg e por arroba · alimentos e
composição, dietas multi-ingrediente com vigência, ordem de trato, previsto × realizado,
custo por cabeça/dia e por arroba produzida.

**Cuidados que definem o sucesso**
- **Custo médio ponderado altera custo histórico já lançado.** Decidir e documentar: recalcula
  retroativo ou vale só para entradas novas? Sem essa decisão explícita, os números de margem
  mudam sem ninguém entender por quê.
- **Nunca misturar competência, vencimento e data de caixa** — é onde nascem os bugs de DRE.
- Saldo de estoque deve ser **reconstruível pelas movimentações**; nenhuma movimentação sem
  origem identificada.
- Mudança de dieta **preserva histórico** (vigência, não sobrescrita).

**Pronto quando:** compra atualiza estoque e financeiro na mesma operação; resultado por lote
fecha com a soma dos animais; DRE e fluxo de caixa não se contradizem.

---

### Trilha 4 — Inteligência: relatórios, regras e (depois) modelos

**Escopo imediato (baixo custo, baixa colisão)**
- **PWA:** `manifest.json` + ícone → AgroTop com ícone na tela inicial do celular, em tela
  cheia. ~1 dia. Não dá offline nem câmera nativa, mas dá ganho de campo imediato.
- **Importação CSV de pesagens** e **detecção de valor suspeito** (peso muito acima/abaixo do
  anterior, GMD implausível, duplicidade na mesma data). Funções puras, fáceis de testar.
- **Relatórios**: tratar como atividade **contínua**, não como fase. Cada módulo entrega seus
  2–3 relatórios junto. Concentrar 20 relatórios no fim significa meses sem conseguir ver se
  os módulos funcionam.
- **Lucro por raça/cruzamento** — extensão direta de `get_fornecedor_ranking`.
- **Correlação chuva × GMD** — o dado já existe (`pluviometria` + pesagens).

**Motor de regras** (o passo que importa)
Regras explícitas com motivo e dados à vista: NDVI em queda + pouca chuva + alta lotação →
risco de escassez; estoque abaixo do consumo previsto de 15 dias → recomendar compra; GMD
abaixo da meta após troca de dieta → revisar adaptação; custo por arroba acima do preço
esperado → alerta de margem; carência ultrapassando data de embarque → bloquear.

**Isto não é prêmio de consolação do machine learning.** É barato, explicável, dá valor
agora — **e força a definir exatamente as features que um modelo usaria depois.** É
engenharia de features feita antes da hora.

**Modelos estatísticos — gatilho de dados, não de calendário**
O limitante não é número de linhas: com 150–200 animais pesados a cada 30–60 dias são
~1.200–2.400 pesagens/ano. O que falta é:
1. **ciclos completos com desfecho conhecido** (entrada → venda com carcaça, receita, custo).
   Um ciclo de terminação leva 12–24 meses; para variar estação, dieta e piquete, ~2–3 anos;
2. **as features**, que só existem depois da Trilha 3 (consumo, custo) e do NDVI.

**A base já está sendo construída certo** — vale preservar: `current_weight` é atualizado em
um único lugar, sempre junto do `INSERT` em `weighings`, então o histórico **nunca se perde**;
`weighings` guarda o `lote_id` do momento da pesagem; `method` distingue pesado de estimado;
`animal_movements` dá lotação histórica; `pluviometria` dá chuva. **Não quebre nada disso** —
é o alicerce dos modelos futuros.

Implementar cedo o **indicador de completude de dados**: mostra, mês a mês, se a base está
ficando treinável.

**NDVI (satélite)** entra aqui, e **depois** da Trilha 2 (precisa dos polígonos):
cena mais recente, cobertura de nuvem, NDVI médio por piquete, histórico, comparação.
Fontes: Copernicus Data Space / Sentinel-2. **NDVI não equivale a kg de matéria seca** —
nenhum alerta deve afirmar disponibilidade de forragem sem calibração de campo.

---

## 6. Comandos

```bash
python -m streamlit run app.py                      # rodar o app
python -m unittest discover -s tests -t . -v        # testes (o -t . é obrigatório, R16)
python -m compileall app.py database.py tests tools # verificação de compilação
python tools/dump_schema_nuvem.py --baseline        # regenerar baseline + retrato
python tools/testar_baseline.py                     # validar que o baseline recria o schema
python tools/gerar_hash_senha.py --usuario admin    # recuperar acesso perdido
python tools/backup_banco.py                        # backup local do banco
python tools/restaurar_banco.py <arquivo.zip>       # restaurar (schema de conferência)
```

Forçar SQLite localmente: `AGROTOP_FORCE_SQLITE=1`.

## 7. Checklist antes de abrir PR

- [ ] `python -m unittest discover -s tests -t . -v` verde
- [ ] `python -m compileall app.py database.py tests tools` sem erro
- [ ] Se tocou schema: DDL do `init_db()` atualizado (R2), baseline e retrato regenerados,
      `testar_baseline.py` verde
- [ ] Nenhuma regra de negócio duplicada (R8)
- [ ] Nenhum `import streamlit` no topo de módulo de dados/serviço (R9)
- [ ] Nenhum diretório `pages/` criado (R12)
- [ ] Nenhum segredo ou `DATABASE_URL` em código, log ou mensagem (R18, R19)
- [ ] Comportamento numérico das regras inalterado — ou mudança declarada no PR
- [ ] Se criou migration: rollback documentado no próprio arquivo (R26)
- [ ] Veio de um branch, não de push direto na `main` (R23)

## 8. Segurança de mudanças e reversão

**O Git já é o sistema de versões.** Cada commit é um ponto de restauração; não é preciso
criar cópias, pastas `_old` ou arquivos `v2`. O que protege de verdade não é *poder
reverter*, é **impedir que a quebra chegue em produção** — porque a `main` faz deploy
automático no Streamlit Cloud.

### R23. Trabalho de agente vai em branch e PR, nunca direto na `main`

Um push direto na `main` publica em produção **antes de qualquer verificação**. Com mais de
um agente, isso vira colisão e quebra silenciosa.

```bash
git checkout -b trilha-2/geometria-piquetes
# ... trabalho, commits pequenos ...
git push -u origin trilha-2/geometria-piquetes
gh pr create --fill
```

Mesclar só com **CI verde**. Recomendado ativar no GitHub: *Settings → Branches → Branch
protection* na `main`, exigindo PR e checks aprovados. Sem isso, a regra depende de
disciplina; com isso, é imposta.

### R24. Commits pequenos e coerentes

Reversão só funciona bem se cada commit fizer **uma coisa**. Um commit "vários ajustes"
não dá para reverter sem levar junto o que estava certo. Se um commit mistura correção e
funcionalidade nova, separe.

### R25. Tag antes de mudança arriscada

Ponto de restauração com nome, mais fácil de achar depois que um SHA:

```bash
git tag estavel-antes-refactor-services && git push origin estavel-antes-refactor-services
```

Usar antes de: refactor grande, migration destrutiva, troca de dependência.

### R26. Toda migration precisa de rollback documentado

**Esta é a lacuna que o Git não cobre: `git revert` desfaz código, não schema.** Reverter o
commit de uma migration deixa o banco no estado novo e o código no antigo — pior que antes.

Portanto, cada arquivo em `supabase/migrations/` deve trazer, em comentário, **como
desfazer**. O exemplo já feito é `0001_drop_profiles.sql`: ele guarda o `CREATE TABLE`
completo da tabela removida, justamente para permitir recriá-la.

Antes de migration **destrutiva** (`DROP`, `ALTER ... DROP COLUMN`, mudança de tipo):
1. verificar o alvo (linhas, FKs, triggers, views dependentes — como foi feito com `profiles`);
2. **rodar `python tools/backup_banco.py`**;
3. registrar no arquivo da migration o que foi verificado e como reverter.

### R27. Backup local do banco

O plano free do Supabase **não tem point-in-time recovery**. A rede de proteção é local:

```bash
python tools/backup_banco.py                    # backup completo + verificação
python tools/restaurar_banco.py <arquivo.zip>   # restaura em schema de conferência
```

O backup é lido numa transação `REPEATABLE READ` (retrato coerente mesmo com o sistema
em uso) e inclui **tudo**, até as fotos em `bytea` — diferente do backup em Excel do app,
que as omite de propósito. Todo backup é verificado logo após ser gerado.

A restauração cai por padrão num **schema de conferência descartável**, nunca por cima dos
dados vivos. Testar a recuperação de tempos em tempos:
`python tools/restaurar_banco.py <arquivo> --apagar-depois`.

⚠️ O arquivo contém todos os dados, **inclusive hashes de senha**. `backups/` está no
`.gitignore` — mantenha assim e guarde uma cópia fora desta máquina.

⚠️ **Confirme a situação de backup do seu plano Supabase.** O projeto está no plano **free**,
que não oferece point-in-time recovery. Não assuma que existe backup automático suficiente —
verifique, e para dados críticos use exportação própria.

### Como reverter, na prática

| Situação | O que fazer |
|---|---|
| Commit ruim já na `main` | `git revert <sha> && git push` — o Streamlit Cloud redeploya sozinho |
| Vários commits ruins | `git revert <sha_antigo>..<sha_novo>` |
| Voltar a um ponto conhecido | `git checkout <tag>` para inspecionar; `git revert` para desfazer de fato |
| Branch de trabalho bagunçado | descartar o branch; a `main` nunca foi tocada |
| Schema quebrado | aplicar o rollback documentado na migration — **não** basta reverter o commit |
| App fora do ar após deploy | Manage app → Reboot; se persistir, `git revert` e push |

**Preferir `git revert` a `git reset --hard`** em branch compartilhado: `revert` cria um
commit novo desfazendo, preservando o histórico; `reset` reescreve o histórico e quebra o
repositório de quem já tinha puxado.

## 10. Delegando trabalho a outros agentes

Agentes podem tocar **manutenção de baixo risco** e **funcionalidades específicas**, desde
que recebam uma **especificação fechada** em [`specs/`](specs/README.md). Sem spec, o
resultado é previsivelmente ruim — e isso não é teoria:

> Em 2026-07-30, onze PRs foram abertos por automação sem especificação. Apenas quatro
> tinham valor. Dois testavam a **mesma função** em arquivos diferentes (#9/#10); um
> mockava `database.get_age_months`, que o refactor havia movido para `services/` (#6);
> e um **removia do ROADMAP uma dívida de segurança ainda aberta** (#12). Nenhuma dessas
> falhas foi de capacidade — todas foram de **contexto ausente**.

### R28. Trabalho delegado exige spec em `specs/`

Uma spec fecha: escopo, o que **não** tocar, critério de aceite verificável, proibições
explícitas e formato de entrega.

A fila fica em [`specs/QUADRO.md`](specs/QUADRO.md), em ordem de prioridade. Ela é a lista
de prioridade **do mantenedor**, não um balcão de autoatendimento.

**Atribua a spec explicitamente no prompt do agente.** Uma linha —
`Leia specs/0010-....md — é a sua tarefa` — elimina corrida, coordenação e dependência de o
agente lembrar de um passo extra.

⚠️ **Autoatendimento por agente foi tentado e falhou.** A primeira versão deixava o agente
escolher e "reivindicar" empurrando um branch vazio antes de começar. Em 2026-07-31, **dois
agentes começaram a mesma spec 0001, e nenhum marcou o quadro**.

A causa é estrutural, não de capacidade do agente: reivindicar exige um passo **fora do
fluxo natural** (empurrar branch vazio *antes* de trabalhar) e marcar o quadro exige um
terceiro. Agente otimiza para começar a tarefa. **Protocolo que depende de adesão voluntária
a passo não óbvio falha** — e falhou.

Lição geral: prefira mecanismo que torna o erro **impossível** (worktree sem `secrets.toml`,
branch protection, teste-guarda no CI) a mecanismo que depende de alguém lembrar.

### R29. Agente trabalha em worktree próprio

```bash
git worktree add ../AgroTop-<tarefa> -b <tipo>/<slug>
```

O worktree dá isolamento **por construção**, não por disciplina: como
`.streamlit/secrets.toml`, `agrotop.db` e `backups/` são gitignored, eles **não vão junto**
— o agente fica fisicamente incapaz de alcançar o banco de produção. Com
`AGROTOP_FORCE_SQLITE=1`, ele roda num SQLite local descartável.

Dependências novas de PoC ficam em `poc/<nome>/requirements.txt`, **nunca** no
`requirements.txt` da raiz, que alimenta o deploy do Streamlit Cloud.

### R30. Código de PoC não é mesclado como está

**O produto de uma PoC é o aprendizado, não o código.** PoC é escrita para responder uma
pergunta rápido: sem testes, sem tratamento de erro, com atalhos. O que se mescla é a
**decisão** (um ADR: "é viável, custa X, seguimos assim"); o código fica no branch como
evidência, e a implementação de verdade é feita depois seguindo este roadmap.

*Histórico: o app mobile arquivado era exatamente código de PoC — login simulado, `catch`
devolvendo três animais fictícios, `sqflite` declarado e nunca importado — e quase virou a
fundação do produto.*

### R31. Implementação delegada entrega função pura em módulo novo

A restrição "não toque em `services/`" vale para **arquivos existentes**. **Criar módulo
novo em `services/` é permitido e é o caminho recomendado** para delegar implementação sem
colidir com a Fase A.

O padrão: a spec fixa a **assinatura exata** da função; o agente entrega o módulo novo mais
os testes; o mantenedor liga à interface e ao banco depois. Assim a trilha avança em
paralelo ao refactor, e a integração fica barata — é ligar função pronta e testada.

### R32. O código é a fonte da verdade sobre o que já foi feito — nunca o quadro

Antes de começar qualquer spec, confira se o arquivo que ela manda criar **já existe na
`origin/main`**:

```bash
git fetch origin
git cat-file -e origin/main:services/<modulo>.py 2>/dev/null && echo "JA EXISTE"
```

*Histórico: em 2026-08-02 a spec 0015 foi implementada **duas vezes** — PR #46 e PR #50 —
porque `specs/QUADRO.md` continuava marcando como livre uma tarefa entregue no dia anterior.
Os dois módulos eram funcionalmente idênticos, com erro de 0,045 % contra o padrão
geodésico nos dois casos. Um agente trabalhou para nada.*

Quadro e índice são mantidos à mão e **sempre atrasam**. Marcar a conclusão no mesmo dia
ajuda, mas depende de alguém lembrar; a conferência no código não depende de ninguém.

### R33. Worktree abandonado é resíduo do mantenedor, não do agente

Depois de cada rodada de merges:

```bash
git fetch --prune
git worktree list && git worktree prune
git branch -vv | grep gone
```

*Histórico: **sete ocorrências**. A mais recente em 2026-08-03, quando `AgroTop-0017`
sobreviveu ao merge do PR #55 e segurou `feat/lucro-por-raca` mesmo com o branch remoto já
apagado — `git branch -D` falhava com `cannot delete branch used by worktree`.*

A regra de o agente remover o próprio worktree existe desde a primeira rodada e continua
valendo. Mas sete falhas mostram que **regra que depende de o agente lembrar não é
suficiente**: a limpeza precisa de um dono, e o dono é quem faz o merge.

### R34. Colisão de tarefa: o que importa é QUANDO ela é descoberta

| Momento da descoberta | O que fazer |
|---|---|
| **Antes de qualquer trabalho** (na seleção) | pular para a próxima da fila — é grátis |
| **Depois de já ter trabalhado** | **PARAR e avisar.** Nunca pegar outra |

A diferença é o custo já pago. Pular durante a seleção não desperdiça nada e é o que torna
o autoatendimento viável. Pular depois de trabalhar significa **fazer duas tarefas numa
sessão, uma delas jogada fora**.

Por isso a verificação tem de vir **antes**: reivindicar é o primeiro comando, não o último.

*Histórico: até 2026-08-03 o `specs/QUADRO.md` mandava o contrário — "pegue a próxima e não
insista". O efeito era o oposto do pretendido: o agente executava a tarefa inteira, descobria
a colisão só ao publicar, e então fazia **outra tarefa completa** na mesma sessão. Duas
entregas, uma jogada fora, dois PRs para revisar — e a colisão nunca chegava a quem coordena.*

Corolário que vale mais que a regra: **reivindicar tem de ser o primeiro comando**, antes de
ler a spec e antes de qualquer trabalho. Reivindicação feita no fim não protege nada — só
descobre o desperdício depois de pagá-lo.

### R35. Marcar o quadro é parte do merge, não tarefa separada

Ao mesclar um PR que veio de spec, **atualize `specs/QUADRO.md` E o índice de
`specs/README.md` no mesmo movimento** — marque ✅ com o link do PR e a data. Não deixe
para depois.

⚠️ **São dois arquivos.** A primeira versão desta regra citava só o quadro, e o índice
ficou de fora: em 2026-08-03, nove specs mescladas continuaram listadas como "disponível"
lá. Corrigir um e esquecer o outro é o mesmo defeito com outro nome.

*Histórico: a R32 mandava o agente conferir no código porque o quadro atrasa. Isso resolve o
sintoma; a causa é o merge não atualizar o quadro. Em 2026-08-03, cinco specs foram mescladas
e o quadro continuou marcando todas como livres — um agente iniciado naquele intervalo teria
pegado tarefa já feita, exatamente como aconteceu com a 0015 no dia anterior.*

As duas regras se somam: **R35 impede o quadro de mentir; R32 protege quando ele mentir
mesmo assim.** Nenhuma substitui a outra.

⚠️ Antes de remover um worktree, veja se há arquivo não commitado dentro dele e **compare
com a `main`**. No caso do 0017 havia dois arquivos que pareciam trabalho perdido e eram
rascunho anterior ao que já fora mesclado — só a comparação revelou isso.

Sem assinatura fixada na spec, o resultado não encaixa e o trabalho se perde.

### Não delegue

- Alterar **arquivo existente** em `database.py`, `services/` ou `repositories/` enquanto a
  Fase A rodar. (Criar módulo **novo** em `services/` é permitido — ver R31.)
- Mudança de schema (R4) — sempre serializada pelo dono do schema.
- Regra de negócio com efeito numérico (GMD, custo, carência, venda).
- Nada que exija credencial de produção.
- **Remover itens da seção 9 (Dívidas).** Quem fecha dívida é o mantenedor, na revisão.

## 11. Dívidas conhecidas

Revisada em **2026-08-03**, com a Fase B concluída. Fechada só sai daqui pela mão do
mantenedor, na revisão.

### 🟢 A dívida nº 1 — a Fase B na interface (7 de 7 ligados) — FECHADA em 2026-08-05

**Era a maior pendência do projeto.** Sete telas ligadas entre 2026-08-04 e 2026-08-05,
uma por repositório. Nenhum repositório da Fase B segue sem interface.

`eventos` foi a última e a diferente das outras seis: ele **já era usado** — toda operação
grava evento desde o B2. O que faltava não era ligar o repositório, era **mostrar** o que
ele já grava. Duas telas: a linha do tempo na ficha do animal (§6) e o painel de
sincronização (§10.4) — e a segunda também fechou a dívida nº 4.

Restam **dez services órfãos** (eram onze — `lotacao` saiu da lista em 2026-08-06, ver
abaixo), entregues por agentes e sem nenhum consumidor: `caixa`, `completude`,
`conformidade`, `dieta`, `gta`, `previsao_estoque`, `projecao`, `rateio`, `rentabilidade`,
`arquivo_dispositivos`. Nenhum é Fase B, então ficam fora do escopo desta dívida, mas
contam para o total: 29 services no diretório, 19 usados. Onze specs (0033–0043) já
pedem a função-ponte de cada um — ver `specs/QUADRO.md`.

**Por que era a dívida nº 1:** conformidade de arquitetura não é conformidade de uso.
Fiscalização não aceita "o repositório tem o método".

**Ordem de integração, executada:** ~~nascimento~~ ✅ → ~~estoque de brincos~~ ✅ →
~~movimentação com GTA~~ ✅ → ~~painel de pendências (§7.3)~~ ✅ → ~~geometria~~ ✅
(na propriedade, §3) → ~~regras configuráveis~~ ✅ → ~~linha do tempo + sincronização~~ ✅
(§6 + §10.4).

~~⚠️ A geometria saiu na propriedade, não no piquete.~~ 🟢 **Fechado em 2026-08-06.**
`properties.poligono` cobria a propriedade desde a spec 0032; `lotes` não tinha coluna de
polígono, e `services.lotacao.sobrepostos()` — pronto e testado desde a spec 0028 — nunca
teve como ser chamado. A migration **0015** acrescentou `lotes.poligono` (mesmo formato
GeoJSON), e `page_lotes` ganhou desenho de perímetro por piquete, área calculada e aviso
de sobreposição — reaproveitando os mesmos helpers da tela de Propriedades, sem duplicar
nada (R8). `sobrepostos()` deixou de ser um service órfão.

#### O que as sete telas ensinaram

**O trabalho não é "chamar o repositório na tela".** É decidir o que a norma exige da
**interface** — e essa decisão nunca estava no repositório, nem caberia lá:

| Tela | A decisão que a norma impôs |
|---|---|
| nascimento (§7.2) | bloqueio para o fluxo **antes** do preenchimento; alerta pede confirmação |
| brincos (§5.2) | situação definitiva não oferece saída; `bloqueado_orgao` diz **quem** libera |
| GTA (§8.3–8.4) | bloqueio não ganha botão cinza, ganha **ausência** de botão; alerta pede justificativa **escrita** |
| pendências (§7.3) | prazo futuro (2033) não pode parecer irregularidade, e fica **fora** do contador |
| propriedades (§3) | titular não é editável — mudá-lo é transferência (§8); área é **calculada**, nunca digitada |
| regras (§11) | não existe "editar": só nova versão; simulação **antes** do botão de salvar |
| eventos (§6.3) | não existe "editar" um evento: só "registrar correção", que aponta para o original sem apagá-lo |
| sincronização (§10.3–10.4) | ação em lote só oferece o que **fecha** a pendência; a trilha individual aceita **qualquer** situação, inclusive as que não resolvem |

**Um padrão apareceu quatro vezes e virou regra prática:** *contador que nunca zera é
contador que ninguém lê.* Apareceu como acidente na fila de sincronização (dívida nº 4,
fechada junto com esta), e como escolha evitada nas pendências de 2033, no alerta de GTA e
na separação entre "acompanhar" e "fechar" no painel de sincronização.

⚠️ **Custo medido:** a suíte foi de 193 s (antes da rodada) para ~282 s no runner externo
(`test_ui.py` roda as sete provas de interface num subprocesso só, então o tempo delas some
da contagem externa — 512 testes visíveis, mais as provas dentro do subprocesso). Se passar
de ~10 min, o caminho é paralelizar os subprocessos, não apagar provas.

### 🔴 Segurança

Nenhuma dívida aberta. As duas anteriores foram fechadas em 2026-08-03: as senhas dos
usuários de produção e a rotação da senha do Postgres.

### 🟠 Técnicas

2. **`animals.id` ainda é a PK.** A etapa B1.6 removeu a coluna legada das oito filhas, mas
   a chave primária de `animals` continua sendo o brinco. **Não é urgente:** o vínculo já é
   o `uuid` em todo lugar, que é o que o §4.1 exige. Trocar a PK é trabalho à parte.

3. **B4.3 pendente** — `property_id` continua **anulável** em `animals` e `lotes`. As
   escritas já preenchem; falta o `NOT NULL`. Mesma ordem que funcionou no B1: escrita
   primeiro, restrição depois.

4. ~~**A fila de sincronização não drena.**~~ 🟢 **Fechada em 2026-08-05**, com a tela do
   §10.4. Descoberta em 2026-08-04 ao ligar a tela do §8: `animal_events.status_sincronizacao`
   nascia `pendente` e não havia como marcá-la como enviada — o gatilho append-only do
   §6.3 aborta qualquer `UPDATE`. O contador nunca zerava, então toda liberação de saída
   passava a exigir justificativa (§8.4) por um alerta que não informava nada.

   [ADR 0005](docs/adr/0005-fila-de-sincronizacao.md) decidiu tabela de controle à parte
   (`evento_sincronizacao`). Faltava a tela — sem ela, o mecanismo existia e ninguém
   conseguia usá-lo, o mesmo problema de sempre nesta rodada. `page_sincronizacao` (§10.4)
   fechou: registro manual de protocolo, dupla conferência opcional (`conferido_por` fica
   em branco se ninguém conferiu, e a ausência é auditável — não é erro de preenchimento),
   e duas ações deliberadamente separadas — **acompanhar** (qualquer situação do §10.3,
   inclusive as que não resolvem, para o log técnico do §10.2) e **fechar em lote** (só as
   que encerram a pendência, porque oferecer 'rejeitado' ali esconderia uma obrigação que
   continua de pé).

   ⚠️ **O que ainda não existe é a comunicação automática** — as APIs do §10.1. Esta tela
   é o "enquanto não houver API" que o §23 prevê, não a integração final.

5. **A adoção de eventos é incremental, por decisão do ADR 0004.** Os eventos são
   *registrados* junto das operações, mas o estado do animal **não é derivado deles**.
   Fazer as duas coisas de uma vez seria reescrever o sistema num salto.

6. **`expected_sale_value` é regra de negócio em `repositories/financeiro.py`.** Anotada no
   próprio arquivo; mover para `services/` é trabalho posterior e sem urgência.

7. **PWA: validar num aparelho** que a sessão persiste ao reabrir pelo ícone instalado. O
   deploy fica atrás do portão de autenticação do Streamlit Cloud, e o PWA instalado precisa
   passar por ele antes do login do AgroTop, com cofre de cookies próprio. **Só um celular
   responde** — não dá para verificar por navegador comum nem por script.

8. **Bancos SQLite antigos não recebem as FKs** — o `ALTER TABLE` do SQLite não adiciona
   constraint; só bancos criados do zero as têm. Aceitável, porque SQLite é dev/teste.

9. **Reboot no deploy:** ao adicionar função nova em `database.py`, o Streamlit Cloud pode
   servir o módulo antigo em cache → `AttributeError`. Solução: Manage app → Reboot app.

9. **OCR do brinco** é *best-effort* e impreciso no campo; QR é confiável. Sempre confirmar
   manualmente. Um leitor nativo (Trilha 1) resolve de verdade.

### 🔵 Cobertura e ferramentas

10. ~~**O baseline não cobre RLS, grants nem extensões.**~~ 🟢 **Fechada em 2026-08-05.**
    Funções e triggers **passaram a ser cobertos** em 2026-08-03 — antes disso o baseline
    recriava `animal_events` e `audit_logs` **sem os gatilhos append-only**, e o
    `testar_baseline` dizia "OK" porque comparava só colunas. *A limitação estava
    documentada e ninguém reviu o aviso quando os gatilhos entraram: documentar um risco
    não o elimina.*

    🔴 **E o risco se realizou em 2026-08-05.** O linter do Supabase acusou
    `rls_disabled_in_public` em **onze tabelas** — exatamente as criadas pelas migrations
    0002 a 0012, a Fase B inteira. Nenhuma foi decisão: foi o mesmo passo faltando,
    repetido onze vezes, porque não estava no checklist de
    [supabase/README.md](supabase/README.md). Com `anon` recebendo todos os privilégios
    por padrão do Supabase, o que separava um estranho de `produtores.documento`
    (CPF/CNPJ), da trilha `audit_logs` e dos eventos do §6 era o sigilo de uma chave
    **projetada para ser pública**. A chave não vazou — verificado —, mas essa é a forma
    errada de defesa.

    **O que foi feito, no mesmo dia:**
    - O checklist ganhou *"Tabela nova nasce com RLS ligado"*, e
      `tests/test_rls_nas_migrations.py` passou a **quebrar o CI**. Foi assim que a 0013
      (fila de sincronização) não virou a décima segunda tabela exposta — pega antes do
      merge.
    - A migration **0014** ligou RLS nas onze e revogou os grants de `anon`/`authenticated`
      em bloco, com `ALTER DEFAULT PRIVILEGES` para o que vier depois.
    - Ao tentar dropar `get_current_user_role()` (item seguinte), o Postgres recusou por
      dependência: duas políticas em `storage.objects`, do bucket `animal-photos`,
      **nunca usadas** — as fotos vão para a coluna `image` da própria tabela
      `animal_photos`, e o projeto não tem `supabase-py` nas dependências. Removidas
      também.
    - `is_admin_or_gestor()` e `get_current_user_role()` — heranças do Supabase Auth que o
      ADR 0002 vetou — foram **removidas**, não só desligadas. Verificado antes: a segunda
      consultava `public.profiles`, tabela que a migration 0001 já tinha apagado. Não eram
      "nunca exercidas": chamá-las devolvia erro. Estavam expostas a `anon` via
      `/rest/v1/rpc/`.
    - `fn_recusa_alteracao()` ganhou `search_path` fixo — sem ele, quem controla o
      search_path da sessão pode influenciar que objeto o corpo da função resolve, e é a
      garantia do §6.3 que está em jogo.
    - Baseline regenerado, `testar_baseline.py` confirma paridade (375 colunas / 33
      tabelas), suíte com 492 testes.

    O teste guarda dois níveis de rigor, e a diferença é deliberada: para migration nova
    (a partir da 0013), RLS e REVOKE são exigidos **na mesma migration** que cria a
    tabela — foi a falta disso ali que originou o teste. Para as 11 legadas, exigir isso
    retroativamente reescreveria migration já aplicada em produção; o que se cobra delas é
    terem sido protegidas **em algum lugar do histórico**, o que a 0014 fez.

11. **A suíte roda Postgres no CI desde 2026-08-03** (spec 0025), o que fecha a dívida
    aberta pela queda do `PRAGMA table_info`. `tests/test_dialeto_duplo.py` continua
    valendo como guarda de leitura de código.

### 🔵 Processo

12. **Fila de specs com duas tarefas** (`specs/QUADRO.md`): 0031 e 0007-v2. O que resta de
    delegável é mais escasso que antes: o trabalho principal virou integração, e
    integração é do mantenedor pela R31. Das seis que estavam na fila em 2026-08-04,
    quatro fecharam em 2026-08-05 (0030, 0028-v2, 0029-v2, 0032-v2 — esta na segunda
    tentativa, depois de a primeira travar sem produzir nada, ver a nota no quadro); a
    0007 fechou com defeito e voltou como 0007-v2.
