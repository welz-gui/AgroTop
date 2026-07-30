# AgroTop — Roadmap de Execução

> **Para quem chega agora (humano ou agente de IA):** leia as seções 1 a 3 antes de
> escrever qualquer linha de código. Elas contêm decisões já tomadas e regras que,
> se violadas, quebram produção ou desfazem trabalho feito.

Última atualização: 2026-07-30 · Estado: **Fase A em execução**

---

## 1. Onde o projeto está

Sistema de gestão de gado de corte. **Streamlit + PostgreSQL (Supabase)** em produção,
SQLite para desenvolvimento e teste.

| | |
|---|---|
| Produção | Streamlit Community Cloud, deploy automático a cada push na `main` |
| Banco | Supabase, projeto `mwjvulwglewoyeximgtv`, plano **free** (sem branches de banco) |
| Schema | **194 colunas / 21 tabelas**, paridade total entre DDL local e produção |
| Testes | 21, verdes no CI |
| Código | `app.py` (~3.280 linhas) + `database.py` (~2.430 linhas) — monolítico |
| Rebanho real | ~150–200 animais ativos + histórico (os 12 do banco atual são **dados fictícios de seed**) |

### Funcionalidades em produção
Cadastro (animais, lotes/piquetes, fornecedores, insumos) · pesagens, curva de peso,
GMD híbrido (recente + de vida) · ficha individual · movimentações · medicamentos,
protocolos, carência · planos de trato · custos individuais e fixos · vendas, resultado,
margem, breakeven · mortalidade · alertas · previsão do tempo e pluviometria ·
simulador de terminação · ranking de fornecedor · exportação CSV/Excel/PDF ·
login por cookie · câmera (QR + OCR de brinco + foto).

### Decisões de arquitetura já tomadas (não reabrir sem motivo novo)
- **[ADR 0001](docs/adr/0001-multi-fazenda-schema-por-tenant.md)** — multi-fazenda por
  **schema**, não por `farm_id`.
- **[ADR 0002](docs/adr/0002-fronteira-de-portabilidade.md)** — Postgres é permanente,
  o provedor é substituível; **Supabase Auth vetado**.
- **[supabase/README.md](supabase/README.md)** — fluxo de alteração de schema.

---

## 2. Regras invioláveis

Violar qualquer uma destas quebra produção, desfaz decisão registrada, ou reintroduz
um bug que já custou tempo. Cada regra tem histórico.

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

**R5. Datas são TEXT ISO (`YYYY-MM-DD`)** nos dois bancos. Não introduzir tipo `date`/
`timestamp` em coluna nova de data de negócio — quebraria a compatibilidade dupla.

**R6. Não adicionar `farm_id` a nenhuma tabela** (ADR 0001). Nem "só por precaução".

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

**R13. Preservar o guard de perfil.** `OPERATOR_PAGES = {"campo","cadastrar","estoque"}` e
a checagem em `main()`. Qualquer nova página restrita precisa passar por ali.

**R14. Escapar `R\$` em markdown.** Dois `$` na mesma string viram fórmula LaTeX e o
Streamlit engole os cifrões. Em f-string: `R\\$`. `column_config` com
`format="R$ %.2f"` **não** é afetado.
*Histórico: commit `d91b66e`.*

**R15. Câmera só sob demanda.** `st.camera_input` apenas depois de clicar "Abrir câmera".
O Streamlit renderiza todas as abas, então instanciar direto liga a câmera em aba de fundo.

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

## 4. Fase A — fundação (em execução, sequencial, um agente)

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

### A3 — Auditoria

`audit_logs` + `created_by`/`updated_by` nos registros relevantes. Aditivo, baixo risco.
Seguir R4 para o schema.

---

## 5. Trilhas paralelas (abrem só depois da Fase A)

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

## 8. Dívidas conhecidas

1. **Rotacionar a senha do Postgres** — ela já apareceu em texto claro duas vezes.
   Supabase → Settings → Database → reset, e atualizar `secrets.toml` + Secrets do
   Streamlit Cloud. *(Adiada por decisão do usuário.)*
2. **Trocar as senhas padrão** `admin/admin123` e `op1/op1234` — o app é público.
   Use `tools/gerar_hash_senha.py`. *(Adiada por decisão do usuário.)*
3. **Actions do CI em Node 20** (deprecado) — bump de `actions/checkout` e `setup-python`.
4. **Reboot no deploy:** ao adicionar função nova em `database.py`, o Streamlit Cloud pode
   servir o módulo antigo em cache → `AttributeError`. Solução: Manage app → Reboot app.
5. **OCR do brinco** é *best-effort* e impreciso no campo; QR é confiável. Sempre confirmar
   manualmente. Um leitor nativo (Trilha 1) resolve isso de verdade.
