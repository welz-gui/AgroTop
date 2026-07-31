# Especificações para agentes

Cada arquivo `NNNN-<slug>.md` aqui é uma **tarefa fechada**, escrita para ser entregue a
um agente que **não conhece o projeto**. Ele lê a spec, executa e abre um PR.

Ver [ROADMAP.md](../ROADMAP.md) seção 10 para o fluxo completo.

---

## Índice

| # | Tarefa | Tipo | Risco | Estado |
|---|---|---|---|---|
| [0001](0001-ci-actions-node24.md) | Atualizar actions do CI (Node 20 → 24) | manutenção | baixo | 🟢 disponível |
| [0002](0002-pwa-instalavel.md) | PWA: AgroTop instalável no celular | funcionalidade | baixo | 🟢 disponível |
| 0003 | PoC: biblioteca de mapa para desenhar piquete no Streamlit | pesquisa | baixo | ⚪ a escrever |
| 0004 | PoC: NDVI é viável? (cobertura de nuvem em MT) | pesquisa | baixo | ⚪ a escrever |
| 0005 | PoC: esqueleto Flutter + API autenticada | pesquisa | médio | ⚪ a escrever |
| 0006 | PoC: quanto histórico os modelos preditivos exigem | pesquisa | baixo | ⚪ a escrever |
| 0007 | Substituir hex literais pelos tokens de `ui/tema.py` (A2b) | manutenção | **médio** | 🔴 bloqueada |

**0007 está bloqueada de propósito:** são 198 substituições em `app.py` (3.280 linhas) sem
nenhum teste de UI, e a verificação é visual, tela por tela. Não delegue enquanto não houver
como provar que nada mudou de aparência.

**Estados:** 🟢 disponível · 🟡 em andamento (anote quem pegou) · ✅ concluída (link do PR) ·
⚪ arquivada.

> **Atualize a tabela ao pegar uma tarefa.** Foi a ausência desse controle que fez dois
> agentes escreverem testes para a mesma função `_num_br`, em arquivos diferentes
> (PRs #9 e #10, ambos descartados).

---

## Como iniciar um agente numa tarefa

### 1. Você cria o worktree (não o agente)

A partir da pasta do projeto principal:

```bash
git worktree add ../AgroTop-pwa -b feat/pwa-instalavel
```

Isso cria a pasta irmã `AgroTop-pwa/` com um checkout próprio no branch novo.
**Crie você, não peça ao agente** — se ele começar na pasta principal, pode alterá-la antes
de se isolar.

### 2. Abra a sessão do agente **dentro** da pasta do worktree

O diretório de trabalho é definido ao iniciar a sessão. Comece em `AgroTop-pwa/`, nunca na
pasta principal.

### 3. O que o agente NÃO recebe (e é proposital)

`.streamlit/secrets.toml`, `agrotop.db` e `backups/` são gitignored, então **não vão para o
worktree**. Consequência: o agente **não alcança o banco de produção** — ele roda em SQLite
local, criado do zero com dados de demonstração pelo `init_db()`.

Também não vai ambiente Python: o projeto usa o Python do sistema, então as dependências já
instaladas valem. Se a tarefa precisar de biblioteca nova, ela vai em
`poc/<nome>/requirements.txt` — **nunca** no `requirements.txt` da raiz, que alimenta o
deploy do Streamlit Cloud.

### 4. Prompt inicial (copie e ajuste a spec)

> Você vai trabalhar no projeto AgroTop, num worktree isolado. **Não escolha sua própria
> tarefa.**
>
> 1. Leia `specs/0002-pwa-instalavel.md` — é a sua tarefa, e o escopo dela é fechado.
> 2. Leia `ROADMAP.md` seções 2 (regras invioláveis) e 3 (o que pode mudar). Elas contêm
>    decisões já tomadas; violar qualquer regra ali quebra produção ou desfaz trabalho.
> 3. Leia `DESIGN.md` se a tarefa tocar interface.
>
> Faça **apenas** o que a spec pede. Se identificar outro problema, **anote no PR em vez de
> corrigir** — mudança fora de escopo é rejeitada.
>
> Antes de abrir o PR, rode e cole o resultado:
> ```
> python -m unittest discover -s tests -t . -v
> python -m compileall app.py database.py repositories services ui tests tools
> ```
> O `-t .` não é opcional (ROADMAP R16).
>
> Abra o PR para `main` seguindo o formato de entrega descrito na spec.

### 5. Ao terminar

```bash
git worktree remove ../AgroTop-pwa     # depois do PR mesclado
git worktree list                      # conferir
```

### O agente descobre sozinho o que fazer?

**Não, e não deve.** Um agente novo não conhece o histórico do projeto: ele exploraria,
tiraria conclusões erradas e "consertaria" coisas fora de escopo — foi exatamente assim que
surgiram os onze PRs de 2026-07-30. Ele **lê o estado** (ROADMAP + este índice) para se
situar, mas **a tarefa é atribuída por você**, sempre.

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

- Qualquer coisa que toque `database.py`, `services/`, `repositories/` enquanto a Fase A
  estiver em andamento — é onde o refactor trabalha, e conflito ali custa caro.
- Mudança de schema (R4) — passa pelo dono do schema, sempre serializada.
- Alteração de regra de negócio com efeito numérico (GMD, custo, carência, venda).
- Qualquer coisa que exija credencial de produção.
