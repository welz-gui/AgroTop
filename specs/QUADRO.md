# Quadro de trabalho

Fila de tarefas disponíveis para agentes. **Pegue sempre a primeira livre de cima para
baixo** — a ordem é prioridade, não sugestão.

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

| 1 | [0024](0024-auditoria-de-cores.md) — auditoria de cores (destrava a 0007) | `feat/auditoria-de-cores` | 🟢 livre | — | — |
| 2 | [0018](0018-previsao-de-estoque.md) — previsão de ruptura de estoque 🏗️ | `feat/previsao-estoque` | 🟢 livre | — | — |
| 3 | [0019](0019-rateio-de-custo-de-lote.md) — rateio de custo de lote 🏗️ | `feat/rateio-custo-lote` | 🟢 livre | — | — |
| 4 | [0027](0027-projecao-de-abate.md) — projeção de abate e chuva × GMD 🏗️ | `feat/projecao-abate` | 🟢 livre | — | — |
| 5 | [0020](0020-custo-de-dieta.md) — custo de dieta multi-ingrediente 🏗️ | `feat/custo-dieta` | 🟢 livre | — | — |
| 6 | [0022](0022-validacao-de-genealogia.md) — validação de genealogia 🇧🇷 | `feat/validacao-genealogia` | 🟢 livre | — | — |
| 7 | [0023](0023-validacao-de-gta.md) — validação de GTA e trânsito 🇧🇷 | `feat/validacao-gta` | 🟢 livre | — | — |
| 8 | [0026](0026-controle-de-brincos.md) — controle de estoque de brincos 🇧🇷 | `feat/controle-de-brincos` | 🟢 livre | — | — |
| 9 | [0021](0021-competencia-e-caixa.md) — competência × caixa 🏗️ | `feat/competencia-caixa` | 🟢 livre | — | — |
| 10 | [0025](0025-postgres-no-ci.md) — Postgres no CI ⚙️ | `feat/postgres-no-ci` | 🟢 livre | — | — |

⚙️ = infraestrutura · 🇧🇷 = fundação regulatória PNIB · 🏗️ = avança trilha do roadmap

> ## 🛑 ANTES DE COMEÇAR: confirme que a tarefa não está feita
>
> **Não confie neste quadro.** Ele é mantido à mão e já ficou desatualizado — em 2026-08-02
> a spec 0015 foi implementada **duas vezes** ([#46](https://github.com/welz-gui/AgroTop/pull/46) e [#50](https://github.com/welz-gui/AgroTop/pull/50)) porque continuava marcada
> como livre depois de entregue. O segundo agente trabalhou dois dias para nada.
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

**Concluídas:** 0001 a 0006 e 0008 a 0014 — **198 testes** na suíte. Só a 0007 segue de
fora, bloqueada.

**Fase A concluída** (PR #24): `database.py` 2.224 → 1.604 linhas, com `repositories/`
(5 módulos), `services/` (11) e `ui/`.

### Integração das funções entregues — situação em 2026-08-01

Ligar à interface é do mantenedor (R31). Estado atual:

| Função | Situação |
|---|---|
| `services/qualidade.py` | ✅ ligada (pesagem no campo e prévia da importação) |
| `services/estoque.py` | ✅ ligada |
| `services/estados_animal.py` | ✅ ligada em `update_animal_status` ([#44](https://github.com/welz-gui/AgroTop/pull/44)) |
| `services/importacao.py` | ✅ ligada (aba "Importar CSV" no Modo Campo) |
| `services/identificadores.py` | ⏳ **não ligada** — depende da interface de troca de brinco |
| `services/validacao_regulatoria.py` | ⏳ **não ligada** |
| `services/recomendacoes.py` | ⏳ **não ligada** — motor de regras sem tela |

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
| 0007 — substituir os 198 hex por tokens de `ui/tema.py` | 🔴 **Continua bloqueada, mas o motivo mudou.** |

**Sobre a 0007:** o [#44](https://github.com/welz-gui/AgroTop/pull/44) introduziu
`streamlit.testing.v1.AppTest` (ver `tests/ui_estados_prova.py`), então **já existe** como
executar o app em teste. Isso não basta: o `AppTest` prova que um widget existe e qual é o
seu estado, **não qual cor ele tem**. As 198 substituições continuam verificáveis só a
olho, tela por tela.

**O que destravaria de verdade:** um teste que renderize as telas e compare com imagem de
referência (golden), ou uma extração dos hex de `app.py` comparada token a token com
`ui/tema.py`. A segunda é bem mais barata e pode virar spec — mas ainda não foi escrita.

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

Se o push falhar com referência já existente, a tarefa está tomada: **pegue a próxima e não
insista**. A operação é atômica, então dois agentes simultâneos não vencem os dois.

Mas note: isso protege contra colisão **no push**, não contra dois agentes trabalharem em
paralelo antes de empurrar. Só use com um agente ativo por vez.

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

O que continua proibido: inventar tarefa fora da fila, reordenar a fila, ou pegar a 0007.
