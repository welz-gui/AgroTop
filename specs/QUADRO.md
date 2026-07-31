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
| 1 | [0002](0002-pwa-instalavel.md) — PWA instalável | `feat/pwa-instalavel` | 🟢 livre | — | — |
| 2 | [0011](0011-motor-de-regras.md) — motor de regras 🏗️ | `feat/motor-de-regras` | 🟢 livre | — | — |
| 3 | [0004](0004-poc-ndvi-viabilidade.md) — PoC NDVI em MT | `poc/ndvi-viabilidade` | 🟢 livre | — | — |
| 4 | [0006](0006-poc-dados-modelos-preditivos.md) — PoC histórico p/ modelos | `poc/dados-modelos` | 🟢 livre | — | — |
| 5 | [0005](0005-poc-flutter-api.md) — PoC Flutter + API | `poc/flutter-api` | 🟢 livre | — | — |

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

**Concluídas em 2026-07-31:** 0001, 0009, 0010, 0008, 0003, **0012, 0013 e 0014** — **145
testes** na suíte. As três últimas são a fundação regulatória pura da Fase B.

**Fase A concluída** (PR #24): `database.py` 2.224 → 1.604 linhas, com `repositories/`
(5 módulos), `services/` (10) e `ui/`.
A PoC 0003 recomendou **`streamlit-folium` + `shapely` + `pyproj`**, com ressalva de
usabilidade de toque no celular — isso destrava a Trilha 2 (geometria dos piquetes). As duas funções novas (`services/qualidade.py` e `services/estoque.py`) estão
entregues e testadas, mas **ainda não ligadas à interface**: isso é integração, e cabe ao
mantenedor (R31).

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

### Fora da fila

| Spec | Motivo |
|---|---|
| 0007 — substituir os 198 hex por tokens de `ui/tema.py` | 🔴 **Bloqueada.** São 198 substituições em `app.py` (3.280 linhas) sem nenhum teste de UI; a verificação é visual, tela por tela. Não delegue enquanto não houver como provar que a aparência não mudou. |

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
