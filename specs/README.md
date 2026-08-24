# Especificações para agentes

Cada arquivo `NNNN-<slug>.md` aqui é uma **tarefa fechada**, escrita para ser entregue a
um agente que **não conhece o projeto**. Ele lê a spec, executa e abre um PR.

**Estado em 2026-08-06:** 43 specs escritas, 34 concluídas, **11 na fila**. Fases A e B do
[ROADMAP](../ROADMAP.md) concluídas — a Fase B está 100% ligada à interface (7 de 7
telas). O que resta de novo (0033–0043) não é mais tela: são as funções-ponte que faltam
para os 11 services que sobraram órfãos depois da Fase B. Ver *"O que não delegar"*, no
fim desta página.

**Atualização de 2026-08-21:** Trilha 3 (Estoque → Financeiro → Nutrição) fechada por
inteiro pelo mantenedor — sem specs novas ali, era trabalho de schema/integração. **Três
specs novas** para destravar as trilhas prioritárias que faltam: **0044** (API FastAPI de
produção, Trilha 1 — a Mobile v1 depende dela e não entra na fila antes de a API estar de
pé), **0045** (importar perímetro de arquivo GeoJSON/KML, Trilha 2) e **0046** (localização
por propriedade na previsão do tempo, Trilha 2 — a decisão de UX/API que faltava foi
tomada: por propriedade, não por piquete; ver a spec e o ROADMAP §5). O restante de cada
trilha (Mobile v1, "desenhar no mapa") segue fora da fila de propósito — ver a nota em cada
item da tabela de trilhas do [ROADMAP](../ROADMAP.md) §5 e o registro no `QUADRO.md`.

**Atualização de 2026-08-21 (mais recente):** fila expandida para 10 specs (0044–0053,
Trilha 1 e Trilha 2 — detalhe completo no `QUADRO.md`). **0044 teve retrabalho**: a
[PR #169](https://github.com/welz-gui/AgroTop/pull/169) foi fechada com dois defeitos reais
(CI não instalava `backend_api/requirements.txt`; tabela nova sem `REVOKE` na mesma
migration) — corrigidos na spec (agora v2), trabalho da v1 preservado na tag
`retrabalho/0044-api-fastapi-producao-v1-pr169`. Ver a seção "🔁 O que significa retrabalho"
no `QUADRO.md`.

**Atualização de 2026-08-22:** **0044 concluída** —
[PR #174](https://github.com/welz-gui/AgroTop/pull/174) mesclada, `backend_api/` em
produção com autenticação JWT (rate limiting, refresh token revogável), `GET /animais`,
`GET /animais/{id}` e `POST /animais/{id}/pesagens`. Antes do merge, a revisão achou mais
dois defeitos reais (campos `tag`/`name` que não existem em `animals`, sempre nulos;
`GET /animais/{id}` devolvendo 404 pra animal vendido/morto em vez da ficha) e um agente
tentando a 0047 tinha achado o contrato da v2 insuficientemente descrito — os três
corrigidos antes do merge, com o contrato exato agora fixado na própria spec.

**Atualização de 2026-08-22 (mais recente): a Trilha 1 e a Trilha 2 fecharam por
completo.** 0045–0053 concluídas — [#170](https://github.com/welz-gui/AgroTop/pull/170),
[#171](https://github.com/welz-gui/AgroTop/pull/171),
[#178](https://github.com/welz-gui/AgroTop/pull/178) (mobile v1a — login, lista de
animais, ficha, pesagem),
[#177](https://github.com/welz-gui/AgroTop/pull/177) (movimentação entre piquetes),
[#181](https://github.com/welz-gui/AgroTop/pull/181) (sanidade e carência),
[#180](https://github.com/welz-gui/AgroTop/pull/180) (fotos). O CI passou a cobrir
Flutter também: `mobile/build_apk.yml` existia mas ficava fora de
`.github/workflows/` (nunca rodava) e só disparava em `push`, nunca `pull_request` — a
revisão da PR #178 corrigiu isso antes do merge (`.github/workflows/mobile-ci.yml`),
então "CI verde" volta a significar `flutter analyze`/`test`/`build` executados de
verdade, não só o lado Python. A PR #181 teve conflito real de merge com a #180 (mesmos
arquivos de `backend_api/`, rotas irmãs) — resolvido por união, suíte completa
reconferida antes do merge.

**Atualização de 2026-08-22:** **0049 concluída**
([#183](https://github.com/welz-gui/AgroTop/pull/183) — movimentação entre piquetes, com
seleção múltipla numa única chamada HTTP e as três categorias do resultado sempre
visíveis). **Adendo na 0050/0051** ([#184](https://github.com/welz-gui/AgroTop/pull/184)):
um agente reivindicando a 0051 achou que `GET /protocolos` não devolvia dose nenhuma,
parou sem escrever código — corrigido no backend (`?animal_id=` + `dose_sugerida`).

**Atualização de 2026-08-23:** **0053 concluída**
([#187](https://github.com/welz-gui/AgroTop/pull/187) — fotos na ficha do animal,
compressão client-side).

**Atualização de 2026-08-24 (a mais recente): 0051 concluída — a Trilha 1 e a Trilha 2
fecharam por completo (0044–0053, todas ✅).** [PR #188](https://github.com/welz-gui/AgroTop/pull/188)
(sanidade) mesclada com uma lacuna aceita conscientemente: divergiu de `main` antes da 0053
mesclar, então o mantenedor resolveu o conflito real por união (as duas estendem seções
irmãs da mesma ficha do animal) e mesclou sem o teste golden do critério 5 — este ambiente
não tem toolchain Flutter para gerar os PNGs, e o usuário decidiu não esperar por outro
agente. O resto está correto e testado (`dose_sugerida` sem cálculo no Dart, carência com
ícone e texto, `flutter analyze`/`test`/`build` verdes). Detalhe completo em `QUADRO.md`.
**Fila zerada de novo** — o que falta do ROADMAP §5 ainda não tem spec (confirmação de
trato, "desenhar no mapa", Bluetooth, mobile offline).

Ver [ROADMAP.md](../ROADMAP.md) seção 10 para o fluxo completo.

---

## Índice

> Para **pegar uma tarefa**, use o [QUADRO.md](QUADRO.md) — ele tem a fila em ordem de
> prioridade e o protocolo de reivindicação à prova de corrida. A tabela abaixo é o
> catálogo; o quadro é a fila.

| # | Tarefa | Tipo | Risco | Estado |
|---|---|---|---|---|
| [0001](0001-ci-actions-node24.md) | Atualizar actions do CI (Node 20 → 24) | manutenção | baixo | ✅ concluída |
| [0002](0002-pwa-instalavel.md) | PWA: AgroTop instalável no celular | funcionalidade | baixo | ✅ concluída |
| [0003](0003-poc-mapa-piquetes.md) | PoC: biblioteca de mapa para desenhar piquete | pesquisa | baixo | ✅ concluída |
| [0004](0004-poc-ndvi-viabilidade.md) | PoC: NDVI é viável? (nuvem em MT) | pesquisa | baixo | ✅ concluída |
| [0005](0005-poc-flutter-api.md) | PoC: esqueleto Flutter + API autenticada | pesquisa | médio | ✅ concluída |
| [0006](0006-poc-dados-modelos-preditivos.md) | PoC: quanto histórico os modelos exigem | pesquisa | baixo | ✅ concluída |
| [0008](0008-importacao-pesagens-csv.md) | Importação de pesagens por CSV (parser puro) | implementação | baixo | ✅ concluída |
| [0009](0009-deteccao-peso-suspeito.md) | Detecção de pesagem suspeita | implementação | baixo | ✅ concluída |
| [0010](0010-custo-medio-ponderado.md) | Custo médio ponderado + ADR | implementação | baixo | ✅ concluída |
| [0011](0011-motor-de-regras.md) | Motor de regras de recomendação | implementação | baixo | ✅ concluída |
| [0012](0012-maquina-estados-animal.md) | 🇧🇷 Máquina de estados do animal (PNIB §4.4) | implementação | baixo | ✅ concluída |
| [0013](0013-validacoes-consistencia-regulatoria.md) | 🇧🇷 Validações de consistência (PNIB §17.3) | implementação | baixo | ✅ concluída |
| [0014](0014-validador-identificadores.md) | 🇧🇷 Validador de identificadores (PNIB §4.2) | implementação | baixo | ✅ concluída |
| [0015](0015-geometria-piquetes.md) | Área e centroide do piquete pelo polígono | implementação | baixo | ✅ concluída |
| [0016](0016-indicador-completude-dados.md) | Indicador de completude de dados | implementação | baixo | ✅ concluída |
| [0017](0017-lucro-por-raca.md) | Lucro por raça e cruzamento | implementação | baixo | ✅ concluída |
| [0018](0018-previsao-de-estoque.md) | Previsão de ruptura de estoque | implementação | baixo | ✅ concluída |
| [0019](0019-rateio-de-custo-de-lote.md) | Rateio de custo de lote entre animais | implementação | baixo | ✅ concluída |
| [0020](0020-custo-de-dieta.md) | Custo de dieta multi-ingrediente | implementação | baixo | ✅ concluída |
| [0021](0021-competencia-e-caixa.md) | Competência × caixa e fluxo projetado | implementação | baixo | ✅ concluída |
| [0022](0022-validacao-de-genealogia.md) | 🇧🇷 Validação de vínculo materno (§7) | implementação | baixo | ✅ concluída |
| [0023](0023-validacao-de-gta.md) | 🇧🇷 Validação de GTA e trânsito (§8) | implementação | baixo | ✅ concluída |
| [0024](0024-auditoria-de-cores.md) | Auditoria de cores — destrava a 0007 | ferramenta | baixo | ✅ concluída |
| [0025](0025-postgres-no-ci.md) | Postgres no CI | infraestrutura | **médio** | ✅ concluída |
| [0026](0026-controle-de-brincos.md) | 🇧🇷 Controle de estoque de brincos (§5) | implementação | baixo | ✅ concluída |
| [0027](0027-projecao-de-abate.md) | Projeção de abate e chuva × GMD | implementação | baixo | ✅ concluída |
| [0007](0007-hex-para-tokens.md) | Substituir hex literais pelos tokens de `ui/tema.py` | manutenção | **médio** | ✅ concluída |
| [0028](0028-geometria-lotacao-e-sobreposicao.md) | Lotação e sobreposição de piquetes | implementação | baixo | ✅ concluída |
| [0029](0029-escore-de-conformidade.md) | 🇧🇷 Escore de conformidade PNIB | implementação | baixo | ✅ concluída |
| [0030](0030-importacao-de-lote-de-brincos.md) | 🇧🇷 Leitura de arquivo de lote de brincos | implementação | baixo | ✅ concluída |
| [0031](0031-testes-de-propriedade.md) | Testes de propriedade para os services | teste | baixo | ✅ concluída |
| [0032](0032-mapa-de-conformidade.md) | 🇧🇷 Mapa de conformidade §-por-§ | documentação | baixo | ✅ concluída |
| [0033](0033-reconciliar-lote-de-brincos-com-estoque.md) | 🇧🇷 Reconciliar lote de brincos com o estoque | implementação | baixo | 🟢 disponível |
| [0034](0034-normalizar-lancamentos-financeiros.md) | Normalizar lançamentos financeiros p/ `caixa.py` | implementação | baixo | 🟢 disponível |
| [0035](0035-adaptar-indicadores-de-completude.md) | Adaptar dados reais p/ `completude.py` | implementação | baixo | 🟢 disponível |
| [0036](0036-montar-rebanho-para-escore-de-conformidade.md) | 🇧🇷 Rebanho p/ escore de conformidade | implementação | baixo | 🟢 disponível |
| [0037](0037-montar-ingredientes-do-trato.md) | Ingredientes do trato p/ `dieta.py` | implementação | baixo | 🟢 disponível |
| [0038](0038-montar-contexto-de-gta.md) | 🇧🇷 Contexto de GTA p/ `gta.py` | implementação | baixo | 🟢 disponível |
| [0039](0039-montar-insumos-para-previsao-de-estoque.md) | Insumos p/ previsão de ruptura de estoque | implementação | baixo | 🟢 disponível |
| [0040](0040-agrupar-chuva-e-gmd-por-periodo.md) | Agrupar chuva × GMD por período | implementação | baixo | 🟢 disponível |
| [0041](0041-calcular-dias-no-lote-para-rateio.md) | Dias no lote p/ `rateio.py` | implementação | baixo | 🟢 disponível |
| [0042](0042-montar-ciclos-para-rentabilidade-por-raca.md) | Ciclos encerrados p/ rentabilidade por raça | implementação | baixo | 🟢 disponível |
| [0043](0043-montar-lotes-para-lotacao.md) | Lotes p/ `lotacao.py` (sem `sobrepostos`) | implementação | baixo | 🟢 disponível |
| [0044](0044-api-fastapi-autenticacao-e-endpoints-essenciais.md) | API FastAPI de produção — autenticação e endpoints essenciais (Trilha 1) | implementação | **médio** | ✅ [#174](https://github.com/welz-gui/AgroTop/pull/174) |
| [0045](0045-importar-perimetro-de-arquivo.md) | Importar perímetro de piquete de arquivo GeoJSON/KML (Trilha 2) | implementação | baixo | ✅ [#170](https://github.com/welz-gui/AgroTop/pull/170) |
| [0046](0046-localizacao-por-propriedade-na-previsao-do-tempo.md) | Localização por propriedade na previsão do tempo (Trilha 2) | implementação | baixo | ✅ [#171](https://github.com/welz-gui/AgroTop/pull/171) |
| [0047](0047-mobile-v1a-login-animais-e-pesagem.md) | Mobile v1a: login, animais e pesagem, contra o contrato da 0044 (Trilha 1) | implementação | **médio** | ✅ [#178](https://github.com/welz-gui/AgroTop/pull/178) |
| [0048](0048-api-movimentacao-entre-lotes.md) | API: movimentação de animais entre piquetes (Trilha 1) | implementação | **médio** | ✅ [#177](https://github.com/welz-gui/AgroTop/pull/177) |
| [0049](0049-mobile-tela-de-movimentacao-entre-lotes.md) | Mobile: tela de movimentação entre piquetes (Trilha 1) | implementação | baixo | ✅ [#183](https://github.com/welz-gui/AgroTop/pull/183) |
| [0050](0050-api-sanidade-medicamentos-e-carencia.md) | API: registrar medicamento e consultar carência (Trilha 1) | implementação | **médio** | ✅ [#181](https://github.com/welz-gui/AgroTop/pull/181) |
| [0051](0051-mobile-tela-de-sanidade.md) | Mobile: tela de sanidade (Trilha 1) | implementação | baixo | ✅ [#188](https://github.com/welz-gui/AgroTop/pull/188) ⚠️ (falta golden do critério 5) |
| [0052](0052-api-foto-do-animal.md) | API: enviar e consultar foto do animal (Trilha 1) | implementação | **médio** | ✅ [#180](https://github.com/welz-gui/AgroTop/pull/180) |
| [0053](0053-mobile-tela-de-foto.md) | Mobile: tela de foto do animal (Trilha 1) | implementação | baixo | ✅ [#187](https://github.com/welz-gui/AgroTop/pull/187) |

**0007 foi DESTRAVADA em 2026-08-03.** A spec 0024 entregou o mapa que faltava: 92 % das
ocorrências têm token de valor idêntico, e sobram só sete cores sem correspondente. O
mantenedor decidiu que essas ganham token novo aproximado ao mais próximo. Com isso a
substituição passa a ser verificável valor por valor.

*Registro do que a bloqueava:* São ~198 substituições em `app.py` sem
como provar que a aparência não mudou. O `AppTest` (desde o PR #44) prova que um widget
existe, **não qual cor ele tem**.

A saída é comparar **valor por valor**: se `#4ade80` vira `cores["sucesso"]` e
`cores["sucesso"] == "#4ade80"`, a aparência não pode ter mudado — é identidade, não
semelhança. A **spec 0024** entrega o mapa que isso exige. O mantenedor já decidiu o que
fazer com hex sem token correspondente: **criar token novo, aproximado ao existente mais
próximo**. Depois da 0024, a 0007 pode ser escrita com critério verificável.

**Estados:** 🟢 disponível · 🟡 em andamento (anote quem pegou) · ✅ concluída ·
🔴 bloqueada · ⚪ arquivada.

> ⚠️ **Esta tabela também é mantida à mão e também atrasa.** Aconteceu **duas vezes** em
> 2026-08-03: de manhã listava quinze specs concluídas como "disponível", e à tarde
> outras nove — porque a R35 falava só do `QUADRO.md` e esta tabela ficou de fora.
> **Ao mesclar uma spec, marque nos DOIS arquivos.** **Não decida se uma tarefa está feita por aqui**
> — confira se o arquivo que a spec manda criar já existe na `origin/main`. O código não
> atrasa.

> **Atribua a spec no prompt.** Deixar o agente escolher foi tentado e falhou: dois agentes
> começaram a mesma spec 0001 sem marcar o quadro. Ver [QUADRO.md](QUADRO.md).

---

## Como iniciar um agente numa tarefa

Há dois caminhos. **O primeiro é o mais simples** e é o recomendado.

### Caminho A — o próprio agente cria o worktree (recomendado)

Inicie o agente **na pasta normal do projeto**. Ele mesmo cria o worktree e move a sessão
para dentro dele, usando a ferramenta `EnterWorktree` do Claude Code.

**Condição obrigatória:** a ferramenta só é acionada quando o pedido **menciona "worktree"
explicitamente**. Se o prompt não disser a palavra, o agente trabalhará na pasta principal.
O prompt da seção 4 já contempla isso.

> 🛑 **Isto falha silenciosamente e já falhou.** Em 2026-08-01 um prompt escrito à mão para a
> spec 0004 começava direto com `git fetch && git checkout -B ...` e **não continha a palavra
> "worktree"**. O agente executou exatamente o que foi pedido — na pasta principal do
> mantenedor, que ficou com o branch do agente em checkout. Nada quebrou por sorte: não havia
> trabalho em andamento naquele momento.
>
> **Antes de colar qualquer prompt, procure a palavra "worktree" na primeira frase.** Se não
> estiver lá, o isolamento não vai acontecer, por mais explícito que o resto seja.
>
> Conferir depois de lançar o agente, na pasta principal:
> ```bash
> git branch --show-current    # deve ser o SEU branch, não o do agente
> git worktree list            # o agente deve aparecer numa linha própria
> ```

O worktree nasce em `.claude/worktrees/<nome>`, num branch novo. Por padrão ele parte de
`origin/main` (configuração `worktree.baseRef = fresh`), e não do seu HEAD local — ou seja,
o agente começa do que está publicado, não do que você tem em andamento.

Ao final, `ExitWorktree` devolve a sessão à pasta original, com opção de **manter** (para
revisar depois) ou **remover** o worktree e o branch.

⚠️ **Janela de exposição:** antes de chamar `EnterWorktree`, o agente está na pasta
principal, onde `.streamlit/secrets.toml` existe e dá acesso ao banco de **produção**. A
janela é de uma chamada de ferramenta, mas é real. Para fechá-la, defina no ambiente da
sessão do agente:

```
AGROTOP_FORCE_SQLITE=1
```

Com isso, `_database_url()` devolve string vazia **mesmo com o `secrets.toml` presente**, e
não há como conectar em produção nem por acidente nem por descuido.

### Caminho B — você cria o worktree antes

Se preferir controle total, crie você e inicie a sessão já dentro da pasta:

```bash
git worktree add ../AgroTop-pwa -b feat/pwa-instalavel
```

Vantagem: não existe janela de exposição, porque a sessão nunca esteve na pasta principal.
Desvantagem: um passo manual a mais, e o worktree fica fora de `.claude/worktrees/`.

### O que o agente NÃO recebe (e é proposital)

`.streamlit/secrets.toml`, `agrotop.db` e `backups/` são gitignored, então **não vão para o
worktree**. Consequência: o agente **não alcança o banco de produção** — ele roda em SQLite
local, criado do zero com dados de demonstração pelo `init_db()`.

Também não vai ambiente Python: o projeto usa o Python do sistema, então as dependências já
instaladas valem. Se a tarefa precisar de biblioteca nova, ela vai em
`poc/<nome>/requirements.txt` — **nunca** no `requirements.txt` da raiz, que alimenta o
deploy do Streamlit Cloud.

### Prompt inicial

A primeira frase precisa conter a palavra **worktree** — é o que autoriza o agente a se
isolar. Escolha a variante conforme **quantos agentes você vai iniciar**.

#### Variante A — o agente pega a próxima livre (autoatendimento)

Viável **desde que a verificação venha antes do trabalho**. A versão antiga desta variante
falhou porque o agente descobria a colisão só ao publicar; a de agora **reivindica primeiro
e trabalha depois**, e pular de tarefa durante a seleção não custa nada (R34).

Continua valendo: **um agente por vez**. A reivindicação atômica protege contra dois pushes
simultâneos, não contra dois agentes trabalhando em paralelo antes de empurrar.

> Crie um **worktree** para esta tarefa e trabalhe dentro dele. Você vai atuar no projeto
> AgroTop (gestão de gado de corte, Streamlit + PostgreSQL).
>
> 1. Abra `specs/QUADRO.md` e pegue a **primeira tarefa livre** da fila (as concluídas estão
>    marcadas ✅ e não têm número de ordem).
> 2. **Antes de qualquer outra coisa**, reivindique-a criando o branch no remoto:
>    ```
>    git ls-remote --heads origin                        # ver o que já está tomado
>    git push origin HEAD:refs/heads/<branch-da-spec>    # reivindicar — ATÔMICO
>    ```
>    Se o push falhar dizendo que a referência já existe, a tarefa está tomada:
>    **PARE e avise quem te instruiu. NÃO pegue outra tarefa** — pegar outra faz você
>    executar duas numa sessão, uma delas jogada fora, e esconde a colisão de quem coordena.
>    Não edite o quadro — quem atualiza é o mantenedor.
> 3. Leia a spec da tarefa por inteiro. O escopo é fechado.
> 4. Leia a seção **"Regras válidas para TODAS as specs"** neste arquivo.
> 5. Leia `ROADMAP.md` seções 2 e 3. `DESIGN.md` se a tarefa tocar interface.

#### Variante B — você atribui a spec ⭐ **use esta**

**Obrigatória** com mais de um agente ativo, e **recomendada mesmo com um só**. A colisão de
2026-07-31 aconteceu com dois agentes iniciados em paralelo lendo a fila juntos; a de
2026-08-02 aconteceu com o quadro desatualizado. Atribuir no prompt elimina as duas.

> Crie um **worktree** para esta tarefa e trabalhe dentro dele. Você vai atuar no projeto
> AgroTop (gestão de gado de corte, Streamlit + PostgreSQL).
>
> 1. Leia `specs/<arquivo-da-spec>.md` — é a **sua** tarefa, escopo fechado.
> 2. Leia a seção **"Regras válidas para TODAS as specs"** neste arquivo.
> 3. Leia `ROADMAP.md` seções 2 e 3. `DESIGN.md` se a tarefa tocar interface.

#### Continuação, igual nas duas variantes

> **Antes de escrever qualquer arquivo, prove que está dentro do worktree** — não na pasta
> principal do mantenedor:
> ```
> git rev-parse --show-toplevel
> test "$(git rev-parse --git-dir)" != "$(git rev-parse --git-common-dir)" \
>   && echo "OK: dentro de um worktree" \
>   || echo "PARE: esta e a pasta principal"
> ```
> Se der `PARE`, não continue: crie o worktree e entre nele. Já houve agente escrevendo no
> checkout do mantenedor achando estar isolado.
>
> **Confirme que seu worktree partiu de `origin/main` atualizada:**
> ```
> git fetch origin                     # NÃO é opcional
> git log --oneline -1 origin/main     # deve ser o mesmo ponto de partida do seu branch
> ```
> Se não for, refaça o worktree a partir de `origin/main`.
>
> **Agora confirme que a tarefa ainda NÃO foi feita.** A spec diz qual arquivo criar; se ele
> já existe na `origin/main`, ela já foi entregue:
> ```
> git cat-file -e origin/main:<arquivo-que-a-spec-manda-criar> 2>/dev/null \
>   && echo "JA EXISTE - PARE e avise quem te instruiu" \
>   || echo "nao existe - pode seguir"
> ```
> Em 2026-08-02 a spec 0015 foi implementada **duas vezes** porque o quadro continuava
> marcando como livre uma tarefa entregue no dia anterior — o segundo agente trabalhou para
> nada. **O código é a fonte da verdade; o quadro é só a fila de prioridade** (R32).
>
> Faça **apenas** o que a spec pede. Se identificar outro problema, **anote no PR em vez de
> corrigir** — mudança fora de escopo é rejeitada.
>
> Se a spec fixar a assinatura de uma função, respeite-a **exatamente**: ela será integrada
> depois pelo mantenedor, e assinatura diferente inutiliza o trabalho.
>
> Antes de abrir o PR, rode e cole o resultado:
> ```
> AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
> python -m compileall app.py database.py repositories services ui tests tools
> git diff --stat origin/main
> ```
> O `-t .` não é opcional (ROADMAP R16) e o `AGROTOP_FORCE_SQLITE=1` é a segunda trava:
> **sem os dois, os testes podem conectar no banco de produção.** No `git diff --stat`, só
> devem aparecer os arquivos que a spec pediu — **não altere `specs/`, `ROADMAP.md` nem
> `README.md`**.
>
> Abra o PR para `main` **pronto para revisão, nunca como rascunho**, no formato descrito na
> spec.
>
> **Cole no seu relatório a URL COMPLETA que o `gh pr create` devolveu**
> (`https://github.com/welz-gui/AgroTop/pull/NNN`). Confirme com:
> ```
> gh pr view --json number,url
> ```
> **Não invente nem estime o número.** Se o comando falhar, diga que falhou e por quê — um
> branch entregue sem PR é recuperável; um PR inexistente reportado como pronto não é.
>
> **Por último, e não esqueça: remova o worktree** — `ExitWorktree` com ação `keep`, ou
> `git worktree remove <caminho>`. Worktree abandonado **segura o branch** e impede o
> mantenedor de trabalhar nele. Já aconteceu cinco vezes.

### Ao terminar

- **Caminho A:** peça ao agente para sair com `ExitWorktree` — `keep` mantém para revisão,
  `remove` apaga worktree e branch. Ele se recusa a remover se houver trabalho não
  commitado, o que é a proteção certa.
- **Caminho B:** `git worktree remove ../AgroTop-pwa` depois do PR mesclado.

Conferir a qualquer momento: `git worktree list`.

### O agente descobre sozinho o que fazer?

**Não, e não deve.** Um agente novo não conhece o histórico do projeto: ele exploraria,
tiraria conclusões erradas e "consertaria" coisas fora de escopo — foi exatamente assim que
surgiram os onze PRs de 2026-07-30. Ele **lê o estado** (ROADMAP + este índice) para se
situar, mas **a tarefa é atribuída por você**, sempre.


---

## ⚠️ Regras válidas para TODAS as specs

Estas valem sempre, mesmo que a spec individual não repita. Foram escritas a partir de
problemas reais observados nas primeiras três entregas (2026-07-31).

### 1b. Não altere `specs/`, `ROADMAP.md` nem `README.md`

Quem atualiza o quadro e a documentação é o **mantenedor**. Você não precisa marcar nada.

*Por quê:* o PR #17 ficou limpo porque não tocou nesses arquivos. O PR #16 ficou em
conflito **só** por causa de uma linha em `specs/QUADRO.md`, e o branch precisou ser
reconstruído. Com a tarefa já atribuída no prompt, marcar o quadro é trabalho perdido que
só gera conflito entre agentes paralelos.

### 0. Afirmação não é evidência

Todo passo de entrega precisa de **saída de comando colada**, não de afirmação: testes,
`compileall`, `git diff --stat` e **a URL do PR**.

*Por quê:* em 2026-07-31 um agente relatou *"PR #23 aberto, pronto para revisão"* para a
spec 0013. **O PR não existia** — e o número era de outro agente. O trabalho estava feito e
commitado; só a entrega foi falsamente reportada. Se o relatório tivesse sido aceito, a
tarefa seria dada por concluída com o código parado num branch.

Vale para o mantenedor também: conferir com `gh pr list` antes de considerar entregue.

### 1. Parta de `origin/main` **atualizada** — `git fetch` primeiro

```bash
git fetch origin                     # NÃO é opcional
git log --oneline -1 origin/main     # deve ser o ponto de partida do seu branch
```

*Por quê, duas vezes:*

O PR #20 chegou carregando **dois commits do mantenedor**, porque o worktree foi criado a
partir do HEAD local — naquele momento um branch de integração em andamento, não a `main`.
O agente não errou; o ponto de partida é que estava errado.

Em 2026-08-01 o problema foi **`origin/main` velha**, que é mais traiçoeiro: um agente
recebeu a spec 0004, leu um checkout parado em `0af0b3b`, viu ali a versão anterior do
quadro, concluiu que a tarefa "já estava integrada pelo PR #33" e **passou para outra
tarefa**. O raciocínio estava certo; os dados é que tinham 3 commits de atraso. Sem `fetch`,
você não está olhando o projeto — está olhando uma fotografia dele.

Mitigações aplicadas: `.claude/settings.json` fixa `worktree.baseRef = "fresh"`, e o prompt
manda conferir. O mantenedor também deve manter a `main` em checkout ao lançar agentes.

### 1c. Se você liberar uma tarefa, apague o branch que reivindicou

Reivindicar cria um branch no remoto. Se você concluir que a tarefa não é sua (já feita,
tomada, bloqueada), **desfaça a reivindicação**:

```bash
git push origin --delete <branch-que-voce-criou>
```

*Por quê:* dois branches vazios (`poc/ndvi-viabilidade`, `poc/dados-modelos-claim`) ficaram
no remoto depois de agentes liberarem tarefas. Um deles tinha o nome da 1ª tentativa de uma
spec que ganhou 2ª — o agente seguinte encontraria um branch já existente com o nome certo e
concluiria que a tarefa estava tomada. Reivindicação abandonada **é armadilha para o
próximo**, não resíduo inofensivo.

E **não invente arquivo marcador** (`CLAIM.md` e afins) só para o branch ter um commit. O
branch reivindicado pode ficar vazio; seu primeiro commit de verdade basta para abrir o PR.

### 2. Trabalhe DENTRO do worktree — e prove, antes de escrever qualquer arquivo

**Não basta criar o worktree. É preciso estar dentro dele.** Rode isto como primeiro
comando depois de criá-lo:

```bash
git rev-parse --show-toplevel      # onde você está
test "$(git rev-parse --git-dir)" != "$(git rev-parse --git-common-dir)" \
  && echo "OK: dentro de um worktree" \
  || echo "PARE: esta e a pasta principal do mantenedor"
```

Num worktree, `--git-dir` aponta para `.../.git/worktrees/<nome>` enquanto `--git-common-dir`
aponta para `.../.git`. **Se os dois forem iguais, você está na pasta principal** — pare,
crie o worktree e entre nele antes de tocar em arquivo.

*Por quê:* em 2026-08-01 apareceram **254 linhas não commitadas** em `poc/modelos/` na pasta
principal do mantenedor — um rascunho da PoC 0006 concatenado por cima da versão já mesclada,
deixando dois títulos de nível 1 no mesmo README. O conteúdo não estava em commit nenhum, de
branch nenhum. Depois de limpo, um `CLAIM.md` reapareceu no mesmo lugar. Em ambos os casos um
agente escrevia no checkout do mantenedor achando estar isolado.

**Por que isso é pior do que parece:** o dano não aparece no seu PR. Ele aparece semanas
depois, no commit de outra pessoa, misturado a trabalho sem nenhuma relação com o seu — e
quem for investigar não terá como saber de onde veio. Um arquivo corrompido quase entrou
numa migração de chave primária por esse caminho.

⚠️ **A ferramenta `EnterWorktree` só dispara se o pedido mencionar "worktree"
explicitamente.** Se o prompt que você recebeu não usa a palavra, o isolamento **não
acontece** e você trabalhará na pasta principal sem perceber. Nesse caso, diga isso a quem
te instruiu em vez de seguir — foi assim que a spec 0004 acabou reivindicada dentro do
checkout do mantenedor.

### 2b. Remova o worktree ao terminar

Depois que o PR for aberto, saia do worktree — `ExitWorktree` (ação `keep`) ou
`git worktree remove <caminho>`.

*Por quê:* **já aconteceu sete vezes.** Três na primeira rodada, dois deles em `C:/tmp`; o
mais recente em 2026-08-03, quando `AgroTop-0017` sobreviveu ao merge do PR #55 e segurou o
branch `feat/lucro-por-raca` mesmo depois de o remoto ter sido apagado.

Worktree abandonado **segura o branch**: `git branch -D` falha com
`cannot delete branch used by worktree`, e o mantenedor descobre isso semanas depois, ao
tentar limpar. Também deixa arquivos soltos que ninguém sabe se são trabalho perdido ou
rascunho — no caso do 0017, eram um rascunho anterior ao que foi mesclado, e alguém teve de
comparar arquivo por arquivo antes de apagar.

> ### 🧹 Limpeza — responsabilidade do MANTENEDOR, não do agente
>
> A regra acima depende de o agente lembrar, e sete ocorrências mostram que isso não basta.
> **Rode isto depois de cada rodada de merges:**
>
> ```bash
> git fetch --prune
> git worktree list            # algum worktree além do principal?
> git worktree prune           # remove os que já não têm pasta
> git branch -vv | grep gone   # branches locais cujo remoto sumiu
> ```
>
> Um worktree listado que você não está usando é resíduo. Antes de remover, olhe se há
> arquivo não commitado lá dentro — e compare com a `main` antes de descartar.

### 3. Abra o PR pronto para revisão, nunca como rascunho

*Por quê:* o PR #15 estava correto e com CI verde, mas em rascunho — o merge falhou com
`Pull Request is still a draft` e a entrega ficou parada sem motivo.

### 4. Antes de abrir o PR, confira o que está indo junto

```bash
git diff --stat origin/main
```

Só devem aparecer os arquivos que a spec pediu. Se aparecer mais, remova.

### 5. Se a spec fixar a assinatura de uma função, respeite-a exatamente

Ela será integrada depois pelo mantenedor. Assinatura diferente inutiliza o trabalho.

## Por que este diretório existe

Em 2026-07-30, onze PRs foram abertos por automação sem especificação. Apenas quatro
tinham valor. Os problemas não foram de capacidade do agente, e sim de **contexto ausente**:

| Problema | PR | O que uma spec teria evitado |
|---|---|---|
| Duplicação | #9 e #10 | Índice com estado da tarefa |
| Premissa obsoleta | #6 | "Leia o ROADMAP antes; `get_age_category` mora em `services/`" |
| Apagou dívida de segurança real | #12 | "Não remova itens da seção Dívidas" |
| Arquivo paralelo redundante | #3 | "Testes de regra vão em `tests/test_regras_negocio.py`" |

## O que faz uma boa spec

1. **Escopo fechado** — o que fazer **e** o que não tocar.
2. **Critério de aceite verificável** — comando que prova que está pronto, não "deve funcionar".
3. **Proibições explícitas** — o agente não conhece o histórico do projeto.
4. **Contexto mínimo necessário** — quais regras do ROADMAP se aplicam.

## O que **não** delegar

> ⚠️ **Histórico: isto mudou duas vezes.** Entre 2026-08-03 e 2026-08-05 a maior parte do
> trabalho era **integração** — ligar à interface os sete módulos regulatórios da Fase B.
> Integração toca `app.py`, mistura camadas e exige contexto do sistema inteiro; era do
> mantenedor, pela R31, e assim ficou até a sétima tela fechar em 2026-08-05.
>
> **Com a Fase B 100% ligada, o padrão original volta a valer.** As specs 0033–0043
> (2026-08-06) são de novo função pura em módulo novo — só que em vez de implementar do
> zero, cada uma monta a **entrada** que um service órfão já pronto espera (ver a nota no
> topo do [QUADRO.md](QUADRO.md)). Continua verdade que **ligar o resultado a `app.py` é
> do mantenedor** — as specs param exatamente onde a integração começaria.
>
> A consequência prática: a fila de specs encolheu e vai continuar encolhendo. Escrever
> spec por escrever, para manter agentes ocupados, produz módulo órfão — e o projeto já tem
> **nove** deles esperando consumidor.

- **Ligar módulo à interface.** É o trabalho do mantenedor pela R31, e é onde a decisão de
  produto acontece.
- Alterar **arquivo existente** em `database.py`, `services/` ou `repositories/`.
  **Criar módulo novo em `services/` continua permitido** e é como as tarefas de
  implementação avançam sem colidir (ROADMAP R31).
- Mudança de schema (R4) — passa pelo dono do schema, sempre serializada.
- Alteração de regra de negócio com efeito numérico (GMD, custo, carência, venda).
- Qualquer coisa que exija credencial de produção.
