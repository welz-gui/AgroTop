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
| 1 | [0001](0001-ci-actions-node24.md) — actions do CI → Node 24 | `manutencao/ci-actions-node24` | 🟢 livre | — | — |
| 2 | [0010](0010-custo-medio-ponderado.md) — custo médio ponderado 🏗️ | `feat/custo-medio-ponderado` | 🟢 livre | — | — |
| 3 | [0009](0009-deteccao-peso-suspeito.md) — detecção de peso suspeito 🏗️ | `feat/qualidade-pesagem` | 🟢 livre | — | — |
| 4 | [0008](0008-importacao-pesagens-csv.md) — importação de pesagens CSV 🏗️ | `feat/importacao-pesagens` | 🟢 livre | — | — |
| 5 | [0003](0003-poc-mapa-piquetes.md) — PoC biblioteca de mapa | `poc/mapa-piquetes` | 🟢 livre | — | — |
| 6 | [0002](0002-pwa-instalavel.md) — PWA instalável | `feat/pwa-instalavel` | 🟢 livre | — | — |
| 7 | [0011](0011-motor-de-regras.md) — motor de regras 🏗️ | `feat/motor-de-regras` | 🟢 livre | — | — |
| 8 | [0004](0004-poc-ndvi-viabilidade.md) — PoC NDVI em MT | `poc/ndvi-viabilidade` | 🟢 livre | — | — |
| 9 | [0006](0006-poc-dados-modelos-preditivos.md) — PoC histórico p/ modelos | `poc/dados-modelos` | 🟢 livre | — | — |
| 10 | [0005](0005-poc-flutter-api.md) — PoC Flutter + API | `poc/flutter-api` | 🟢 livre | — | — |

🏗️ = **avança trilha do roadmap** (implementação, não pesquisa). As demais são PoC ou manutenção.

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

## Protocolo de reivindicação

### 1. Veja o que já está tomado — **esta é a fonte de verdade**

```bash
git ls-remote --heads origin
```

Se o branch da spec **já existe**, a tarefa está tomada. Vá para a próxima da fila.

### 2. Reivindique criando o branch no remoto

```bash
git push origin HEAD:refs/heads/<branch-da-spec>
```

Esta operação é **atômica**: se dois agentes tentarem ao mesmo tempo, apenas um vence. O
outro recebe erro de referência já existente — e nesse caso **não insista**: pegue a
próxima tarefa livre.

É isso que torna o protocolo à prova de corrida. Editar este arquivo, não.

### 3. Só então registre no quadro

Marque a linha como 🟡, preencha "Quem" (identifique-se de forma reconhecível) e a data.
Commit e push. Se der conflito aqui, resolva mantendo **as duas** reivindicações — a
autoridade é o branch, e o conflito é só de texto.

### 4. Ao concluir

Marque ✅ com o link do PR. Não apague a linha: o histórico da fila é útil.

### 5. Se desistir ou travar

Marque 🟢 de novo, explique em uma linha o motivo, e **apague o branch remoto**:

```bash
git push origin --delete <branch-da-spec>
```

Reivindicação abandonada sem liberar trava a fila para todo mundo.

---

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
