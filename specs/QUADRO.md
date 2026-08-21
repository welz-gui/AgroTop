# Quadro de trabalho

Fila de tarefas disponíveis para agentes. **Pegue sempre a primeira livre de cima para
baixo** — a ordem é prioridade, não sugestão.

**Estado em 2026-08-21:** Fases A e B **e** Trilha 3 (Estoque → Financeiro → Nutrição) do
[ROADMAP](../ROADMAP.md) concluídas · 669 testes · 37 tabelas em produção, todas com RLS
(políticas explícitas de negação para `anon`/`authenticated` desde a migration 0024) ·
**Fase B 100% ligada à interface** (7 de 7 telas) · **10 specs na fila, 4 pegáveis agora
e 6 bloqueadas por sequenciamento** — 0044 (API FastAPI, Trilha 1), 0045 (importar
perímetro de arquivo, Trilha 2), 0046 (localização por propriedade na previsão do tempo,
Trilha 2) e 0047 (Mobile v1a, Trilha 1 — em paralelo com a 0044, travada no contrato
dela) disponíveis já; 0048/0050/0052 (endpoints de movimentação, sanidade e foto) esperam
a 0044 mesclar, 0049/0051/0053 (telas correspondentes) esperam a 0047 mesclar — ver
abaixo.

> ### 🆕 11 specs novas em 2026-08-06 — a fila deixou de ser "adaptador de tela"
>
> Depois da Fase B, restam **11 services em `services/` que nunca foram chamados por
> nada**: `arquivo_dispositivos`, `caixa`, `completude`, `conformidade`, `dieta`, `gta`,
> `lotacao`, `previsao_estoque`, `projecao`, `rateio`, `rentabilidade`. Todos são funções
> puras, testadas, prontas — o problema é só a **entrada**: cada um espera um formato de
> dado que não existe pronto em lugar nenhum do sistema.
>
> **Estas 13 specs (0033–0043) pedem a função-ponte, não a integração.** Cada uma monta,
> a partir de listas cruas (que a spec descreve com o nome real da tabela e das colunas),
> exatamente o dict/lista que o service órfão espera — sem tocar `app.py`, sem consultar
> banco, sem alterar o service em si. É o R31 aplicado ao pé da letra: "a spec fixa a
> assinatura exata da função; o agente entrega o módulo novo mais os testes; o mantenedor
> liga à interface depois."
>
> Duas specs (**0038** e **0037**/**0039**) avisam, no próprio texto, sobre uma coluna que
> ainda não existe no schema (validade de GTA, matéria seca, prazo de reposição). Não é
> erro de quem escreveu a spec — é limitação real dos dados, e a spec já diz o que fazer:
> tratar como ausente, nunca inventar o valor.
>
> **Atualização de 2026-08-06:** a migration **0015** acrescentou `lotes.poligono`, e o
> mantenedor já ligou `sobrepostos()` direto em `page_lotes` — não sobrou trabalho de
> adaptador para ele. A **0043** foi revisada: continua valendo só para `lotacao`,
> `capacidade` e `avaliar_lotacao`, que usam peso de animal, não polígono.

> ### ✅ A Fase B fechou — a fila agora é o que resta de verdade delegável
>
> Até 2026-08-05 a maior pendência do projeto não estava nesta fila: os módulos
> regulatórios da Fase B existiam e não tinham interface. **Isso acabou.** Nenhum
> repositório da Fase B segue sem tela — a última foi a linha do tempo do animal (§6) com
> o painel de sincronização (§10.4).
>
> ⚠️ **`app.py` ainda pode estar em mudança ativa.** Se a sua spec toca `app.py`, confira
> `git diff --stat origin/main` antes de abrir o PR — várias PRs desta semana precisaram
> de rebase por terem ficado atrás da `main`, que andou rápido nos últimos dois dias.

> ⚠️ **Este arquivo é visibilidade, não autoridade.** Um arquivo em git **não é um lock**:
> dois agentes podem lê-lo ao mesmo tempo, ambos verem a mesma tarefa livre e ambos
> reivindicá-la. Quem manda é o **branch no remoto** — ver o protocolo abaixo.

---

## Fila

| Ordem | Spec | Branch | Estado | Quem | Desde |
|---|---|---|---|---|---|
| — | [0001](0001-ci-actions-node24.md) — actions do CI → Node 24 | — | ✅ [#15](https://github.com/welz-gui/AgroTop/pull/15) | | 2026-07-31 |
| — | [0010](0010-custo-medio-ponderado.md) — custo médio ponderado 🏗️ | — | ✅ [#16](https://github.com/welz-gui/AgroTop/pull/16) | | 2026-07-31 |
| — | [0009](0009-deteccao-peso-suspeito.md) — detecção de peso suspeito 🏗️ | — | ✅ [#17](https://github.com/welz-gui/AgroTop/pull/17) | | 2026-07-31 |
| — | [0012](0012-maquina-estados-animal.md) — máquina de estados do animal 🇧🇷 | — | ✅ [#23](https://github.com/welz-gui/AgroTop/pull/23) | | 2026-07-31 |
| — | [0013](0013-validacoes-consistencia-regulatoria.md) — validações de consistência 🇧🇷 | — | ✅ [#25](https://github.com/welz-gui/AgroTop/pull/25) | | 2026-07-31 |
| — | [0014](0014-validador-identificadores.md) — validador de identificadores 🇧🇷 | — | ✅ [#26](https://github.com/welz-gui/AgroTop/pull/26) | | 2026-07-31 |
| — | [0008](0008-importacao-pesagens-csv.md) — importação de pesagens CSV 🏗️ | — | ✅ [#19](https://github.com/welz-gui/AgroTop/pull/19) | | 2026-07-31 |
| — | [0003](0003-poc-mapa-piquetes.md) — PoC biblioteca de mapa | — | ✅ [#20](https://github.com/welz-gui/AgroTop/pull/20) | | 2026-07-31 |
| — | [0002](0002-pwa-instalavel.md) — PWA instalável | — | ✅ [#31](https://github.com/welz-gui/AgroTop/pull/31) | | 2026-07-31 |
| — | [0011](0011-motor-de-regras.md) — motor de regras 🏗️ | — | ✅ [#29](https://github.com/welz-gui/AgroTop/pull/29) | | 2026-07-31 |
| — | [0004](0004-poc-ndvi-viabilidade.md) — PoC NDVI em MT (2ª tentativa) | — | ✅ [#43](https://github.com/welz-gui/AgroTop/pull/43) ⚠️ | | 2026-08-01 |
| — | [0006](0006-poc-dados-modelos-preditivos.md) — PoC histórico p/ modelos | — | ✅ [#35](https://github.com/welz-gui/AgroTop/pull/35) | | 2026-08-01 |
| — | [0005](0005-poc-flutter-api.md) — PoC Flutter + API | — | ✅ [#40](https://github.com/welz-gui/AgroTop/pull/40) | | 2026-08-01 |
| — | [0015](0015-geometria-piquetes.md) — área do piquete pelo polígono 🏗️ | — | ✅ [#46](https://github.com/welz-gui/AgroTop/pull/46) | | 2026-08-01 |
| — | [0016](0016-indicador-completude-dados.md) — indicador de completude 🏗️ | — | ✅ [#52](https://github.com/welz-gui/AgroTop/pull/52) | | 2026-08-02 |
| — | [0017](0017-lucro-por-raca.md) — lucro por raça e cruzamento 🏗️ | — | ✅ [#55](https://github.com/welz-gui/AgroTop/pull/55) | | 2026-08-03 |

| — | [0024](0024-auditoria-de-cores.md) — auditoria de cores (destrava a 0007) | — | ✅ [#62](https://github.com/welz-gui/AgroTop/pull/62) | | 2026-08-03 |
| — | [0018](0018-previsao-de-estoque.md) — previsão de ruptura de estoque 🏗️ | — | ✅ [#65](https://github.com/welz-gui/AgroTop/pull/65) | | 2026-08-03 |
| — | [0019](0019-rateio-de-custo-de-lote.md) — rateio de custo de lote 🏗️ | — | ✅ [#63](https://github.com/welz-gui/AgroTop/pull/63) | | 2026-08-03 |
| — | [0027](0027-projecao-de-abate.md) — projeção de abate e chuva × GMD 🏗️ | — | ✅ [#68](https://github.com/welz-gui/AgroTop/pull/68) | | 2026-08-03 |
| — | [0020](0020-custo-de-dieta.md) — custo de dieta multi-ingrediente 🏗️ | — | ✅ [#66](https://github.com/welz-gui/AgroTop/pull/66) | | 2026-08-03 |
| — | [0022](0022-validacao-de-genealogia.md) — validação de genealogia 🇧🇷 | — | ✅ [#67](https://github.com/welz-gui/AgroTop/pull/67) | | 2026-08-03 |
| — | [0023](0023-validacao-de-gta.md) — validação de GTA e trânsito 🇧🇷 | — | ✅ [#71](https://github.com/welz-gui/AgroTop/pull/71) | | 2026-08-03 |
| — | [0026](0026-controle-de-brincos.md) — controle de estoque de brincos 🇧🇷 | — | ✅ [#70](https://github.com/welz-gui/AgroTop/pull/70) | | 2026-08-03 |
| — | [0021](0021-competencia-e-caixa.md) — competência × caixa 🏗️ | — | ✅ [#73](https://github.com/welz-gui/AgroTop/pull/73) | | 2026-08-03 |
| — | [0025](0025-postgres-no-ci.md) — Postgres no CI ⚙️ | — | ✅ [#76](https://github.com/welz-gui/AgroTop/pull/76) | | 2026-08-03 |

⚙️ = infraestrutura · 🇧🇷 = fundação regulatória PNIB · 🏗️ = avança trilha do roadmap

| — | [0029](0029-escore-de-conformidade.md) — escore de conformidade PNIB 🇧🇷 | — | ✅ [#95](https://github.com/welz-gui/AgroTop/pull/95) | | 2026-08-05 |
| — | [0028](0028-geometria-lotacao-e-sobreposicao.md) — lotação e sobreposição 🏗️ | — | ✅ [#94](https://github.com/welz-gui/AgroTop/pull/94) | | 2026-08-05 |
| — | [0030](0030-importacao-de-lote-de-brincos.md) — leitura de arquivo de brincos 🇧🇷 | — | ✅ [#90](https://github.com/welz-gui/AgroTop/pull/90) | | 2026-08-05 |
| — | [0032](0032-mapa-de-conformidade.md) — mapa de conformidade §-por-§ 🇧🇷 | — | ✅ [#96](https://github.com/welz-gui/AgroTop/pull/96) | | 2026-08-05 |
| — | [0031](0031-testes-de-propriedade.md) — testes de propriedade ⚙️ | — | ✅ [#93](https://github.com/welz-gui/AgroTop/pull/93) | | 2026-08-05 |
| — | [0007](0007-hex-para-tokens.md) — hex → tokens de tema 🔁 | — | ✅ [#100](https://github.com/welz-gui/AgroTop/pull/100) | | 2026-08-06 |
| — | [0036](0036-montar-rebanho-para-escore-de-conformidade.md) — rebanho p/ escore de conformidade 🇧🇷 | — | ✅ [#102](https://github.com/welz-gui/AgroTop/pull/102) | | 2026-08-06 |
| — | [0043](0043-montar-lotes-para-lotacao.md) — lotes p/ cálculo de lotação 🏗️ | — | ✅ [#103](https://github.com/welz-gui/AgroTop/pull/103) | | 2026-08-06 |
| — | [0039](0039-montar-insumos-para-previsao-de-estoque.md) — previsão de ruptura de estoque 🔁 | — | ✅ [#105](https://github.com/welz-gui/AgroTop/pull/105) | | 2026-08-06 |
| — | [0033](0033-reconciliar-lote-de-brincos-com-estoque.md) — reconciliar lote de brincos com estoque 🇧🇷 | — | ✅ [#106](https://github.com/welz-gui/AgroTop/pull/106) | | 2026-08-06 |
| — | [0034](0034-normalizar-lancamentos-financeiros.md) — normalizar lançamentos financeiros 🏗️ | — | ✅ [#109](https://github.com/welz-gui/AgroTop/pull/109) | | 2026-08-06 |
| — | [0042](0042-montar-ciclos-para-rentabilidade-por-raca.md) — ciclos p/ rentabilidade por raça 🏗️ | — | ✅ [#110](https://github.com/welz-gui/AgroTop/pull/110) | | 2026-08-06 |
| — | [0038](0038-montar-contexto-de-gta.md) — contexto de GTA para validação 🇧🇷 | — | ✅ [#111](https://github.com/welz-gui/AgroTop/pull/111) | | 2026-08-06 |
| — | [0035](0035-adaptar-indicadores-de-completude.md) — indicadores de completude de dados ⚙️ | — | ✅ [#112](https://github.com/welz-gui/AgroTop/pull/112) | | 2026-08-06 |
| — | [0037](0037-montar-ingredientes-do-trato.md) — ingredientes do trato p/ custo de dieta 🏗️ | — | ✅ [#116](https://github.com/welz-gui/AgroTop/pull/116) | | 2026-08-07 |
| — | [0040](0040-agrupar-chuva-e-gmd-por-periodo.md) — correlação chuva × GMD ⚙️ | — | ✅ [#117](https://github.com/welz-gui/AgroTop/pull/117) | | 2026-08-07 |
| — | [0041](0041-calcular-dias-no-lote-para-rateio.md) — dias no lote p/ rateio de custo ⚙️ | — | ✅ [#118](https://github.com/welz-gui/AgroTop/pull/118) | | 2026-08-07 |

> ### 🎉 Fila zerada em 2026-08-07 — reaberta em 2026-08-21
>
> As 13 specs de adaptador (0033–0043) fecharam todas. Os 11 services órfãos do
> ROADMAP ganharam ponte de entrada — falta só o mantenedor ligar cada um à
> interface (R31: a spec entrega o módulo puro, a integração é trabalho à parte).
>
> Entre 2026-08-07 e 2026-08-21 a fila ficou vazia de propósito: a Trilha 3
> (Estoque → Financeiro → Nutrição) foi fechada por inteiro por trabalho direto do
> mantenedor (schema, integração — não delegável). Com a Trilha 3 encerrada, **quatro
> specs novas destravam as trilhas prioritárias que faltam** (ROADMAP §5, Trilha 1 e
> Trilha 2, ambas prioridade alta do usuário):

| Ordem | Spec | Branch | Estado | Quem | Desde |
|---|---|---|---|---|---|
| 1 | [0044](0044-api-fastapi-autenticacao-e-endpoints-essenciais.md) — API FastAPI de produção: autenticação e endpoints essenciais 🔁v2 ⚠️médio | — | 🟢 disponível | | 2026-08-21 |
| 2 | [0045](0045-importar-perimetro-de-arquivo.md) — importar perímetro de piquete de arquivo GeoJSON/KML 🏗️ | — | 🟢 disponível | | 2026-08-21 |
| 3 | [0046](0046-localizacao-por-propriedade-na-previsao-do-tempo.md) — localização por propriedade na previsão do tempo 🏗️ | — | 🟢 disponível | | 2026-08-21 |
| 4 | [0047](0047-mobile-v1a-login-animais-e-pesagem.md) — Mobile v1a: login, animais e pesagem 🏗️ ⚠️médio | — | 🟢 disponível | | 2026-08-21 |

**Bloqueadas por sequenciamento — não pegue ainda, confira o pré-requisito na própria spec
antes de reivindicar:**

| Ordem | Spec | Branch | Estado | Quem | Desde |
|---|---|---|---|---|---|
| 5 | [0048](0048-api-movimentacao-entre-lotes.md) — API: movimentação de animais entre piquetes 🏗️ ⚠️médio | — | 🔴 bloqueada — espera **0044 mesclada** | | 2026-08-21 |
| 6 | [0049](0049-mobile-tela-de-movimentacao-entre-lotes.md) — Mobile: tela de movimentação entre piquetes 🏗️ | — | 🔴 bloqueada — espera **0047 mesclada** | | 2026-08-21 |
| 7 | [0050](0050-api-sanidade-medicamentos-e-carencia.md) — API: registrar medicamento e consultar carência 🏗️ ⚠️médio | — | 🔴 bloqueada — espera **0044 mesclada** | | 2026-08-21 |
| 8 | [0051](0051-mobile-tela-de-sanidade.md) — Mobile: tela de sanidade 🏗️ | — | 🔴 bloqueada — espera **0047 mesclada** | | 2026-08-21 |
| 9 | [0052](0052-api-foto-do-animal.md) — API: enviar e consultar foto do animal 🏗️ ⚠️médio | — | 🔴 bloqueada — espera **0044 mesclada** | | 2026-08-21 |
| 10 | [0053](0053-mobile-tela-de-foto.md) — Mobile: tela de foto do animal 🏗️ | — | 🔴 bloqueada — espera **0047 mesclada** | | 2026-08-21 |

> **0050/0051 e 0052/0053 seguem exatamente o mesmo par de motivos que 0048/0049** —
> cada endpoint estende o mesmo app FastAPI da 0044, cada tela estende o mesmo app Flutter
> da 0047. Uma vez a 0044 mesclada, 0048/0050/0052 podem correr em paralelo entre si (são
> rotas independentes, arquivos diferentes dentro de `backend_api/` — confira
> `git diff --stat origin/main` antes de abrir o PR pra não pegar rota de outra spec por
> engano). O mesmo vale para 0049/0051/0053 depois da 0047 mesclar.

> **Por que 0048/0049 não são mais uma exceção como a 0047 foi:** a 0047 pôde ignorar a
> ordem porque ela só precisava do **contrato escrito** da 0044, nunca do código dela — as
> duas vivem em pastas diferentes (`backend_api/` × `mobile/`). A 0048 e a 0049 **estendem
> código que ainda não existe** (rotas novas no mesmo app FastAPI da 0044; tela nova no
> mesmo app Flutter da 0047) — não têm como começar antes de esse código existir de
> verdade. A 0049, uma vez que a 0047 esteja mesclada, volta a poder rodar em paralelo com
> a 0048 pelo mesmo truque de contrato travado + servidor mock.

> **A 0047 é a exceção à regra "espera a 0044 mesclar" que este quadro registrava antes.**
> Reconsiderado a pedido do mantenedor (2026-08-21): a 0044 já **define o contrato por
> escrito** (endpoints, payloads) — o que faltava não era o contrato, era a implementação
> dos dois lados. A 0047 trava nesse contrato escrito e testa contra um **servidor mock**
> local, não contra a 0044 real — os dois lados podem avançar em paralelo sem colidir.
> Se um agente notar que precisa de algo que a 0044 não define, a spec manda **parar e
> reportar**, nunca inventar um contrato por conta própria. Continua valendo: a 0047 só
> cobre o que a 0044 expõe (login + animais + pesagem) — movimentação (0048/0049),
> sanidade (0050/0051) e foto (0052/0053) já ganharam suas próprias specs de endpoint +
> tela, no mesmo padrão. Confirmação de trato continua sem spec.

> **Por que só estas dez, e não o resto das duas trilhas:**
>
> - **Bluetooth** (Trilha 1, etapa 4) só é possível com o equipamento físico em
>   mãos — não delegável por definição.
> - **Mobile v2 offline** (Trilha 1, etapa 5) é deixada para o fim de propósito
>   (ROADMAP): idempotência e resolução de conflito são a parte mais cara, e não
>   deve bloquear o resto.
> - **"Desenhar no mapa"** (Trilha 2, item 1 — a outra metade do item que a 0045
>   cobre só a metade "importar arquivo") é integração de componente de UI
>   (`streamlit-folium` + plugin de desenho) direto em `app.py` — cai em "Ligar
>   módulo à interface", que é sempre do mantenedor (R31), não uma função pura para
>   delegar.
>
> **A 0046 fecha a pendência que faltava decisão** (Trilha 2, item 3): a previsão do
> tempo passa a ser **por propriedade**, não por piquete — não é limite de custo de
> API (Open-Meteo é gratuito e sem chave), é que piquetes da mesma propriedade ficam
> perto demais para uma previsão distinta valer a pena, enquanto propriedades
> diferentes (um produtor pode ter mais de uma, ADR 0004) podem ficar longe de
> verdade. Decisão e razão completas na própria spec e no ROADMAP §5.

> ## 🛑 ANTES DE COMEÇAR: confirme que a tarefa não está feita
>
> **Não confie neste quadro.** Ele é mantido à mão e já ficou desatualizado — em 2026-08-02
> a spec 0015 foi implementada **duas vezes** ([#46](https://github.com/welz-gui/AgroTop/pull/46) e [#50](https://github.com/welz-gui/AgroTop/pull/50)) porque continuava marcada
> como livre depois de entregue. O segundo agente trabalhou dois dias para nada.
>
> **Aconteceu de novo em 2026-08-06, do jeito bom e do jeito ruim ao mesmo tempo.** Um
> agente pegou a fila, viu 0031 marcada livre (já tinha sido entregue pela PR #93, dois dias
> antes) e 0007-v2 marcada livre (já tinha branch com PR aberta). Ele **fez a coisa certa**:
> checou os dois, confirmou que estavam tomados, não escreveu uma linha, removeu o próprio
> worktree e voltou. **Zero trabalho perdido, exatamente como este guia pede.** Mas gastou
> 8h46min da própria sessão só para chegar a essa conclusão, porque o quadro mentia sobre
> as duas primeiras posições da fila. **Confirme SEMPRE a linha inteira** — branch, PR,
> arquivo — antes de gastar uma sessão inteira só para descobrir que não havia tarefa.
>
> A spec diz qual arquivo criar. **Se ele já existe na `origin/main`, a tarefa está feita:**
>
> ```bash
> git fetch origin
> git cat-file -e origin/main:services/<modulo>.py 2>/dev/null >   && echo "JA EXISTE — pare e avise" >   || echo "nao existe — pode seguir"
> ```
>
> Isso não depende de ninguém lembrar de atualizar nada. **O código é a fonte da verdade;
> o quadro é só a fila de prioridade.**

⚠️ **A 0004 foi entregue, mas o PR #43 foi fechado sem merge** — o conteúdo já estava na
`main`, carregado por engano dentro do [#44](https://github.com/welz-gui/AgroTop/pull/44).
O agente trabalhou no checkout do mantenedor em vez de um worktree, e o mantenedor não
rodou `git diff --stat origin/main` antes de abrir o próprio PR. **A autoria de
`poc/ndvi/` no commit `e980367` é do agente da 0004.**

🇧🇷 = **fundação regulatória PNIB** (Fase B) · 🏗️ = avança trilha do roadmap ·
demais = PoC ou manutenção.

### ⚠️ A maior parte da Fase B NÃO é delegável

O [ADR 0004](../docs/adr/0004-conformidade-pnib.md) criou a Fase B (B1–B7). Dela, **só as
partes puras entram nesta fila**. B1, B2, B3, B4, B6 e B7 são **mudança de schema** — e a R4
manda serializar schema pelo mantenedor. A migração que troca a PK de 8 tabelas em produção
é o item de maior risco da história do projeto; não vai para agente.

As três specs 🇧🇷 acima são as **funções puras** que a Fase B precisa, e podem ser feitas em
paralelo à migração:

| Spec | Serve a | Por que é pura |
|---|---|---|
| 0012 estados | B1, B2 | recebe estado atual e novo, devolve se pode |
| 0013 consistência | B3 | recebe animal e contexto, devolve problemas |
| 0014 identificadores | B1 | recebe valor e regra, devolve se é válido |

Assim o agente entrega a regra testada enquanto o mantenedor faz a migração — e a
integração depois é ligar função pronta.

**Concluídas:** 26 das 32 specs — **430 testes** na suíte. A 0007, bloqueada desde o início
do projeto, foi **destravada** em 2026-08-03 pelo mapa de cores da spec 0024.

**Fase A concluída** (PR #24): `database.py` 2.224 → 1.604 linhas, com `repositories/`
(5 módulos), `services/` (11) e `ui/`.

### Integração das funções entregues — situação em 2026-08-03

Ligar à interface é do mantenedor (R31). Estado atual:

**11 de 25 services chegam ao app.** Cinco alimentam repositórios que também não têm tela.
E **nove estão órfãos** — entregues, testados, sem nenhum consumidor:

| Situação | Módulos |
|---|---|
| ✅ **na interface** (11) | `constantes` · `estados_animal` · `estoque` · `identificadores` · `importacao` · `qualidade` · `recomendacoes` · `seguranca` · `terminacao` · `validacao_regulatoria` · `zootecnia` |
| 🟡 **usados por repositório sem tela** (5) | `dispositivos` · `estados_dispositivo` · `genealogia` · `movimentacao` · `regras_regulatorias` |
| 🔴 **órfãos — sem nenhum consumidor** (9) | `caixa` · `completude` · `dieta` · `geometria` · `gta` · `previsao_estoque` · `projecao` · `rateio` · `rentabilidade` |

Os nove órfãos são o custo real de delegar mais rápido do que se integra. Cada um custou
dias de trabalho de agente e ainda não entregou nada ao usuário. **É o motivo de a fila ter
encolhido de propósito.**

A PoC 0003 recomendou **`streamlit-folium` + `shapely` + `pyproj`**, com ressalva de
usabilidade de toque no celular — é o que a **spec 0015** começa a destravar.

**Estados:** 🟢 livre · 🟡 em andamento · ✅ concluída (link do PR) · 🔴 bloqueada

### Cobertura das trilhas

| Trilha do [ROADMAP](../ROADMAP.md) | Specs | Tipo |
|---|---|---|
| 1 — API + Mobile | 0005, 0002 | pesquisa + ganho rápido |
| 2 — Geometria e qualidade de dado | 0003, 0008, 0009 | pesquisa + **implementação** |
| 3 — Estoque → Financeiro → Nutrição | **0010** | **implementação** |
| 4 — Regras, NDVI, modelos | 0011, 0004, 0006 | **implementação** + pesquisa |

**Como as tarefas de implementação avançam trilha sem colidir com a Fase A:** elas entregam
**função pura em módulo novo** de `services/`, com contrato fixado na spec. O mantenedor liga
à interface e ao banco depois. Nenhum arquivo existente é tocado.

### ✅ Resultado do NDVI (spec 0004, 2ª tentativa) — **agora é decisão-grade**

**Seguir com ressalvas.** Em MT há imagem utilizável a cada ~5 dias na seca e a cada 53 na
chuva; **o maior vão é de 105 dias** no limiar de 20 % (205 dias no de 10 %).

Os dois defeitos da 1ª tentativa foram corrigidos, e os números foram **conferidos por
recálculo independente a partir dos CSVs commitados** — batem em todas as casas decimais:

| | 10 % | 20 % | 40 % |
|---|---:|---:|---:|
| Cenas utilizáveis (de 99) | 30 | 36 | 46 |
| Maior vão | 205 d | 105 d | 95 d |

O vão agora **responde ao limiar** (205 ≥ 105 ≥ 95). A causa do "12 dias para os três":
a função media só o intervalo *entre* cenas e ignorava as bordas do período.

**O NDVI foi calculado de verdade** — B04/B08 dos COGs, recorte pelo polígono, máscara SCL
descartando nuvem, cirrus, sombra e neve. Amplitude de **0,3535 a 0,8055**, com queda
coerente ao longo de agosto–setembro. É sinal, não ruído.

**Achado que ninguém tinha visto:** a 1ª tentativa usava o Earth Search **v0, depreciado**,
que devolvia 56 cenas parando em dezembro/2025 apesar do período pedido ir até abril/2026.
Boa parte da inconsistência original vinha da **fonte**, não do cálculo.

**Efeito no plano:** satélite é ferramenta de **seca (mai–set)**, não monitoramento
contínuo. Novembro, dezembro, fevereiro e março não tiveram nenhuma cena utilizável — e é
justamente quando a chuva acelera a mudança do pasto. NDVI segue **não equivalendo** a
matéria seca sem calibração de campo.

### ✅ Resultado do Flutter + API (spec 0005, PR #40)

**Seguir com ressalvas.** A fronteira arquitetural está provada: Flutter → FastAPI →
`services/` e `repositories/` existentes, **sem fórmula de GMD no Dart** e sem criar um
segundo modelo de identidade — a API usa a tabela `users` e o PBKDF2 de
`services/seguranca.py`, confirmando o veto a Supabase Auth do [ADR 0002](../docs/adr/0002-fronteira-de-portabilidade.md).

A PoC **se recusa a iniciar sem `AGROTOP_FORCE_SQLITE=1`** e exige `AGROTOP_API_SECRET`
com 32+ caracteres, falhando fechado — não há segredo padrão.

**Custo:** ~US$ 5/mês (Railway Hobby) ou US$ 7 (Render Starter). iOS exige **US$ 99/ano**.

**Falta antes de produção** (integração, não PoC): rate limiting no login, revogação e
renovação de token, HTTPS obrigatório, configuração PostgreSQL, autorização por tenant e
pipeline de release assinado. O `build_apk.yml` está em `poc/mobile/` e **não** está ligado
ao CI — ligar é decisão do mantenedor.

**Dívida anotada:** `_login()` da PoC faz SQL cru porque **não existe
`repositories/usuarios.py`** — o SQL de `users` ainda mora em `database.py`, que a spec
proibia tocar. Se a API virar produção, extrair esse repositório primeiro (R1/R9).

### ⚠️ Pendência do PWA (spec 0002, PR #31)

O agente validou a persistência do cookie `agrotop_sid` **no contexto web** (fechar e reabrir
a aba mantém a sessão), mas **não conseguiu testar o fluxo do ícone instalado** — exige
HTTPS. Ele declarou isso explicitamente, em vez de afirmar o que não verificou.

**Falta confirmar no deploy:** instalar pela tela inicial, fechar, reabrir pelo ícone e
verificar que a sessão persiste. Um PWA instalado tem contexto de armazenamento próprio.

### Fora da fila

| Spec | Motivo |
|---|---|
| — | *(nenhuma)* |

**Sobre a 0007:** o [#44](https://github.com/welz-gui/AgroTop/pull/44) introduziu
`streamlit.testing.v1.AppTest` (ver `tests/ui_estados_prova.py`), então **já existe** como
executar o app em teste. Isso não basta: o `AppTest` prova que um widget existe e qual é o
seu estado, **não qual cor ele tem**. As 198 substituições continuam verificáveis só a
olho, tela por tela.

**O que destravaria de verdade:** um teste que renderize as telas e compare com imagem de
referência (golden), ou uma extração dos hex de `app.py` comparada token a token com
`ui/tema.py`. A segunda é bem mais barata e pode virar spec — mas ainda não foi escrita.

### 🔁 O que significa "retrabalho"

Seis specs passaram por isto até agora (a mais recente em 2026-08-21): a PR foi **fechada com defeito
confirmado**, e a spec voltou à fila com o defeito escrito dentro dela — em vez de
simplesmente reabrir a tarefa como se fosse nova.

| Spec | 1ª tentativa | Defeito | 2ª tentativa |
|---|---|---|---|
| [0028](0028-geometria-lotacao-e-sobreposicao.md) | #82, fechada | CRS por polígono, não por conjunto — 578 km reportados como sobrepostos | ✅ [#94](https://github.com/welz-gui/AgroTop/pull/94), corrigido e verificado |
| [0029](0029-escore-de-conformidade.md) | #83, fechada | escore 100 com pendência crítica na mesma resposta; faixa chamava a si mesma de "conforme" | ✅ [#95](https://github.com/welz-gui/AgroTop/pull/95), corrigido e verificado |
| [0032](0032-mapa-de-conformidade.md) | #89, fechada | §6 marcado ✅ sem ter tela | 🔁 v2 **travou sem commitar nada** (ver abaixo) → retomada → [#96](https://github.com/welz-gui/AgroTop/pull/96), que corrigiu §6 **e achou um segundo erro do mesmo tipo em §11** antes do merge |
| [0007](0007-hex-para-tokens.md) | #97, fechada | teste media "todo hex tem token", não "hex virou token" — 136 de 198 hex ficaram literais | ✅ [#100](https://github.com/welz-gui/AgroTop/pull/100), corrigido e verificado (33 restantes, todos no bloco CSS estático) |
| [0039](0039-montar-insumos-para-previsao-de-estoque.md) | #101, fechada | frequência de trato desconhecida (`"quinzenal"`) virava 1×/dia — 14 kg quinzenais lidos como 14 kg/dia | ✅ [#105](https://github.com/welz-gui/AgroTop/pull/105), corrigido e verificado (reprodução exata do defeito testada e confirmada corrigida antes do merge) |
| [0044](0044-api-fastapi-autenticacao-e-endpoints-essenciais.md) | #169, fechada | dois defeitos: CI não instalava `backend_api/requirements.txt` (`tests.test_backend_api` quebrava na importação, `ModuleNotFoundError: jwt`); tabela `api_refresh_tokens` sem `REVOKE ... FROM anon` na mesma migration (quebra `test_rls_nas_migrations`) | 🟢 v2 disponível — trabalho da v1 preservado na tag `retrabalho/0044-api-fastapi-producao-v1-pr169` |

**A 0039 tem uma nuance:** parte do defeito era da própria spec — o docstring do contrato
citava a regra certa, mas nenhum critério de aceite cobrava um teste para ela. Corrigido
na spec: agora há um critério numerado só para isso.

**Não trate uma spec com histórico de retrabalho como tarefa nova.** Cada uma ganhou uma
seção **"O defeito da primeira tentativa"** com a reprodução exata do erro e o teste que
passa a ser obrigatório. Começar sem ler essa seção é repetir o mesmo trabalho e chegar ao
mesmo defeito.

**O nome da branch muda para `-v2`** de propósito — se a spec ainda apontasse para o nome
antigo, o protocolo de "branch existe = tarefa tomada" acusaria a tarefa como ocupada e
ninguém a pegaria nunca.

**A branch da 1ª tentativa não fica no remoto para sempre.** Ela cumpria o papel de "o
histórico não pode sumir" enquanto existia — mas isso o próprio PR fechado já garante (o
GitHub mantém o diff de uma PR acessível mesmo depois que a branch de origem é apagada).
Deixar a branch ali só acumulava lixo na lista. Desde 2026-08-14, a branch da 1ª
tentativa vira uma **tag anotada** (`retrabalho/<spec>-<assunto>-v1-pr<N>`, ex.:
`retrabalho/0028-geometria-lotacao-v1-pr82`) e é apagada do remoto — mesmo commit,
mesmo histórico, sem poluir a lista de branches ativas.

**A lição que se repete em todas as quatro, e não é sobre nenhum assunto específico:**
toda entrega fechada **passou em todos os critérios de aceite** e ainda assim estava
errada. O critério de aceite prova o que alguém pensou em perguntar. Quando você
terminar, procure o caso que a spec **não** menciona — e se achar, escreva o teste antes
de abrir o PR.

A 0032 rendeu a lição mais afiada, duas vezes seguidas: o defeito original era
**exatamente o que a spec avisava em letras garrafais** que não podia acontecer, e o
defeito da correção (#96, §11) era **o mesmo erro em outra seção** — parcial sem checar
`app.py`, agora ao contrário. Ler a proibição não basta; é preciso conferir a própria
entrega contra ela, seção por seção, antes de abrir o PR.

### ⚠️ A 0032-v2 travou sem produzir nada, e foi liberada de novo em 2026-08-05

Um agente reivindicou `feat/mapa-de-conformidade-v2`, abriu o worktree e parou — **zero
commits, zero diff**, sem PR. O worktree ficou parado num commit antigo (`fbf3a0a`) e a
branch remota continuou existindo, o que — pelo protocolo desta seção — faria qualquer
outro agente que checasse o GitHub achar a tarefa ocupada e desistir dela para sempre.

O mantenedor removeu o worktree órfão e a branch remota; **não havia código para
reverter**, porque nada tinha sido escrito. A tarefa está livre outra vez, com o mesmo
defeito registrado que motivou o retrabalho — leia a seção do defeito antes de começar,
como qualquer outro agente pegando esta spec.

**Se você é um agente e travar de verdade** (erro que não consegue contornar, ambiente
quebrado, o que for): não deixe o worktree parado. Avise no PR, se conseguir abrir um
rascunho, ou simplesmente pare — um worktree sem commit é inofensivo para o código, mas
o nome da branch some da vista de quem decide se a tarefa está livre.

---

## Como uma tarefa é atribuída

### Regra prática: depende de quantos agentes você inicia

| Situação | Modo | Prompt |
|---|---|---|
| **Um agente por vez** ⭐ padrão | ele pega a próxima livre, reivindicando o branch **antes** de começar | **Variante A** |
| **Vários em paralelo** | **você atribui** a spec no prompt | Variante B (obrigatória) |

A fila abaixo é lida pelo agente: ele pega a **primeira com número de ordem** (as concluídas
estão marcadas ✅ e sem número).

A colisão de 2026-07-31 aconteceu com **dois agentes iniciados em paralelo**. Sequencialmente
o autoatendimento funciona, porque não há dois lendo a fila ao mesmo tempo.

Prompts em [README.md](README.md).

### Quando atribuir explicitamente ⭐

Diga a spec no prompt do agente:

> `Leia specs/0010-custo-medio-ponderado.md — é a sua tarefa.`

**Zero corrida, zero coordenação, zero dependência de o agente lembrar de um passo.**
A fila abaixo é a sua lista de prioridade, não um balcão de autoatendimento.

> ⚠️ **Por que este virou o modo padrão.** A primeira versão deste quadro deixava o agente
> escolher e "reivindicar" empurrando um branch vazio antes de começar. **Não funcionou:**
> em 2026-07-31, dois agentes começaram a mesma spec 0001 e nenhum marcou o quadro.
>
> O motivo é estrutural, não de capacidade: reivindicar exige um passo **fora do fluxo
> natural** do agente (empurrar branch vazio *antes* de trabalhar), e marcar o quadro exige
> um terceiro. Agente otimiza para começar a tarefa. Qualquer protocolo que dependa de
> adesão voluntária a passo não óbvio falha — e falhou.

### Modo alternativo: autoatendimento (só com um agente por vez)

Se ainda assim quiser que o agente escolha, o **primeiro comando** dele deve ser este,
literalmente, antes de qualquer outra coisa:

```bash
git ls-remote --heads origin        # ver o que já está tomado
git push origin HEAD:refs/heads/<branch-da-spec>   # reivindicar — ATÔMICO
```

Se o push falhar com referência já existente, a tarefa está tomada. **Se você ainda não
trabalhou, pule para a próxima da fila** — é grátis. **Se já trabalhou, PARE e avise**;
nunca comece uma segunda tarefa na mesma sessão.

> ### 🛑 Por que "pegue a próxima" era a instrução errada
>
> Este documento mandava, até 2026-08-03, *"pegue a próxima e não insista"* — e isso
> **causava** o desperdício que pretendia evitar.
>
> O que acontecia: o agente lia o quadro, escolhia uma tarefa, **executava o trabalho
> inteiro** e só ao tentar publicar descobria que outro agente já a tinha. Obedecendo à
> instrução, pegava outra e fazia tudo de novo — **duas tarefas numa sessão, uma jogada
> fora**, dois PRs para revisar, e a colisão invisível para quem coordena.
>
> Parar é melhor por quatro razões:
>
> 1. o contexto do agente já está contaminado pela tarefa abandonada;
> 2. duas entregas numa sessão são mais difíceis de revisar que duas sessões;
> 3. quem coordena pode **não querer** a próxima tarefa feita agora;
> 4. se o agente segue sozinho, a colisão nunca chega ao humano — e o processo não aprende.

A reivindicação é atômica, então dois agentes simultâneos não vencem os dois. Mas ela
protege contra colisão **no push**, não contra dois agentes trabalharem em paralelo antes de
empurrar — e é por isso que **reivindicar tem de ser o PRIMEIRO comando**, antes de ler a
spec, antes de qualquer trabalho. Reivindicar no fim não protege nada.

## Reivindicações paradas

Se um branch reivindicado ficar **7 dias sem commit novo**, considere-o abandonado. O
mantenedor pode liberar:

```bash
git log -1 --format='%ci' origin/<branch>    # último commit
git push origin --delete <branch>            # liberar
```

---

## Pode o agente escolher a própria tarefa?

**Desta fila, sim — e só desta fila, em ordem.**

Isso refina a regra R28 do [ROADMAP.md](../ROADMAP.md). A proibição original ("não escolha
sua própria tarefa") existia porque agentes sem contexto escolhem mal: em 2026-07-30, onze
PRs foram abertos por automação sem especificação, e apenas quatro tinham valor — com
duplicação, premissa obsoleta e um PR que removia uma dívida de segurança ainda aberta.

A fila resolve o problema pela raiz: **a curadoria já foi feita** ao escrever as specs e ao
ordená-las. Escolher a primeira livre não é decidir prioridade — é seguir a que já está
decidida.

O que continua proibido: inventar tarefa fora da fila ou reordenar a fila. (A proibição de
pegar a 0007 valia só enquanto ela estava bloqueada — destravou em 2026-08-03 pela 0024, e
está na fila normal desde então.)
