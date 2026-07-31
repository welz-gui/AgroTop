# Especificações para agentes

Cada arquivo `NNNN-<slug>.md` aqui é uma **tarefa fechada**, escrita para ser entregue a
um agente que **não conhece o projeto**. Ele lê a spec, executa e abre um PR.

Ver [ROADMAP.md](../ROADMAP.md) seção 10 para o fluxo completo.

---

## Índice

> Para **pegar uma tarefa**, use o [QUADRO.md](QUADRO.md) — ele tem a fila em ordem de
> prioridade e o protocolo de reivindicação à prova de corrida. A tabela abaixo é o
> catálogo; o quadro é a fila.

| # | Tarefa | Tipo | Risco | Estado |
|---|---|---|---|---|
| [0001](0001-ci-actions-node24.md) | Atualizar actions do CI (Node 20 → 24) | manutenção | baixo | 🟢 disponível |
| [0002](0002-pwa-instalavel.md) | PWA: AgroTop instalável no celular | funcionalidade | baixo | 🟢 disponível |
| [0003](0003-poc-mapa-piquetes.md) | PoC: biblioteca de mapa para desenhar piquete | pesquisa | baixo | 🟢 disponível |
| [0004](0004-poc-ndvi-viabilidade.md) | PoC: NDVI é viável? (nuvem em MT) | pesquisa | baixo | 🟢 disponível |
| [0005](0005-poc-flutter-api.md) | PoC: esqueleto Flutter + API autenticada | pesquisa | médio | 🟢 disponível |
| [0006](0006-poc-dados-modelos-preditivos.md) | PoC: quanto histórico os modelos exigem | pesquisa | baixo | 🟢 disponível |
| 0007 | Substituir hex literais pelos tokens de `ui/tema.py` (A2b) | manutenção | **médio** | 🔴 bloqueada |

**0007 está bloqueada de propósito:** são 198 substituições em `app.py` (3.280 linhas) sem
nenhum teste de UI, e a verificação é visual, tela por tela. Não delegue enquanto não houver
como provar que nada mudou de aparência.

**Estados:** 🟢 disponível · 🟡 em andamento (anote quem pegou) · ✅ concluída (link do PR) ·
⚪ arquivada.

> **Reivindique no [QUADRO.md](QUADRO.md) antes de começar.** Foi a ausência desse controle
> que fez dois agentes escreverem testes para a mesma função `_num_br`, em arquivos
> diferentes (PRs #9 e #10, ambos descartados).

---

## Como iniciar um agente numa tarefa

Há dois caminhos. **O primeiro é o mais simples** e é o recomendado.

### Caminho A — o próprio agente cria o worktree (recomendado)

Inicie o agente **na pasta normal do projeto**. Ele mesmo cria o worktree e move a sessão
para dentro dele, usando a ferramenta `EnterWorktree` do Claude Code.

**Condição obrigatória:** a ferramenta só é acionada quando o pedido **menciona "worktree"
explicitamente**. Se o prompt não disser a palavra, o agente trabalhará na pasta principal.
O prompt da seção 4 já contempla isso.

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

### Prompt inicial (copie e ajuste a spec)

A primeira frase precisa conter a palavra **worktree** — é o que autoriza o agente a se
isolar. Sem ela, ele trabalha na pasta principal.

> Crie um **worktree** para esta tarefa e trabalhe dentro dele. Você vai atuar no projeto
> AgroTop.
>
> 1. Abra `specs/QUADRO.md`, pegue a **primeira tarefa livre** da fila e reivindique-a
>    seguindo o protocolo de lá. Se preferir atribuir uma tarefa específica, troque esta
>    linha por: "Leia `specs/<arquivo>.md` — é a sua tarefa".
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
