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
| [0008](0008-importacao-pesagens-csv.md) | Importação de pesagens por CSV (parser puro) | implementação | baixo | 🟢 disponível |
| [0009](0009-deteccao-peso-suspeito.md) | Detecção de pesagem suspeita | implementação | baixo | 🟢 disponível |
| [0010](0010-custo-medio-ponderado.md) | Custo médio ponderado + ADR | implementação | baixo | 🟢 disponível |
| [0011](0011-motor-de-regras.md) | Motor de regras de recomendação | implementação | baixo | 🟢 disponível |
| [0012](0012-maquina-estados-animal.md) | 🇧🇷 Máquina de estados do animal (PNIB §4.4) | implementação | baixo | 🟢 disponível |
| [0013](0013-validacoes-consistencia-regulatoria.md) | 🇧🇷 Validações de consistência (PNIB §17.3) | implementação | baixo | 🟢 disponível |
| [0014](0014-validador-identificadores.md) | 🇧🇷 Validador de identificadores (PNIB §4.2) | implementação | baixo | 🟢 disponível |
| 0007 | Substituir hex literais pelos tokens de `ui/tema.py` (A2b) | manutenção | **médio** | 🔴 bloqueada |

**0007 está bloqueada de propósito:** são 198 substituições em `app.py` (3.280 linhas) sem
nenhum teste de UI, e a verificação é visual, tela por tela. Não delegue enquanto não houver
como provar que nada mudou de aparência.

**Estados:** 🟢 disponível · 🟡 em andamento (anote quem pegou) · ✅ concluída (link do PR) ·
⚪ arquivada.

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

#### Variante A — um agente por vez (ele pega a próxima livre)

Cômoda: você não precisa escolher a spec. **Só use lançando um agente de cada vez** — a
colisão de 2026-07-31 aconteceu com dois iniciados em paralelo.

> Crie um **worktree** para esta tarefa e trabalhe dentro dele. Você vai atuar no projeto
> AgroTop (gestão de gado de corte, Streamlit + PostgreSQL).
>
> 1. Abra `specs/QUADRO.md` e pegue a **primeira tarefa livre** da fila.
> 2. **Antes de qualquer outra coisa**, reivindique-a criando o branch no remoto:
>    `git push origin HEAD:refs/heads/<branch-da-spec>`.
>    Se falhar dizendo que a referência já existe, a tarefa está tomada: pegue a próxima e
>    **não insista**. Não edite o quadro — quem atualiza é o mantenedor.
> 3. Leia a spec da tarefa por inteiro. O escopo é fechado.
> 4. Leia a seção **"Regras válidas para TODAS as specs"** neste arquivo.
> 5. Leia `ROADMAP.md` seções 2 e 3. `DESIGN.md` se a tarefa tocar interface.

#### Variante B — vários agentes em paralelo (você atribui)

**Obrigatória** quando houver mais de um agente ativo. Elimina a corrida por completo.

> Crie um **worktree** para esta tarefa e trabalhe dentro dele. Você vai atuar no projeto
> AgroTop (gestão de gado de corte, Streamlit + PostgreSQL).
>
> 1. Leia `specs/0008-importacao-pesagens-csv.md` — é a **sua** tarefa, escopo fechado.
>    *(Troque pelo arquivo da spec que está atribuindo. Fila em `specs/QUADRO.md`.)*
> 2. Leia a seção **"Regras válidas para TODAS as specs"** neste arquivo.
> 3. Leia `ROADMAP.md` seções 2 e 3. `DESIGN.md` se a tarefa tocar interface.

#### Continuação, igual nas duas variantes

> **Confirme que seu worktree partiu de `origin/main`**, e não de um branch local em
> andamento:
> ```
> git log --oneline -1 origin/main     # deve ser o mesmo ponto de partida do seu branch
> ```
> Se não for, refaça o worktree a partir de `origin/main`.
>
> Faça **apenas** o que a spec pede. Se identificar outro problema, **anote no PR em vez de
> corrigir** — mudança fora de escopo é rejeitada.
>
> Se a spec fixar a assinatura de uma função, respeite-a **exatamente**: ela será integrada
> depois pelo mantenedor, e assinatura diferente inutiliza o trabalho.
>
> Antes de abrir o PR, rode e cole o resultado:
> ```
> python -m unittest discover -s tests -t . -v
> python -m compileall app.py database.py repositories services ui tests tools
> git diff --stat origin/main
> ```
> O `-t .` não é opcional (ROADMAP R16). No `git diff --stat`, só devem aparecer os arquivos
> que a spec pediu — **não altere `specs/`, `ROADMAP.md` nem `README.md`**.
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

### 1. Parta de `origin/main`, não de um branch local

*Por quê:* o PR #20 chegou carregando **dois commits do mantenedor**, porque o worktree foi
criado a partir do HEAD local — que naquele momento era um branch de integração em
andamento, não a `main`. O agente não errou; o ponto de partida é que estava errado.

Mitigações aplicadas: `.claude/settings.json` fixa `worktree.baseRef = "fresh"`, e o prompt
manda conferir. O mantenedor também deve manter a `main` em checkout ao lançar agentes.

### 2b. Remova o worktree ao terminar

Depois que o PR for aberto, saia do worktree — `ExitWorktree` (ação `keep`) ou
`git worktree remove <caminho>`.

*Por quê:* três worktrees ficaram órfãos na primeira rodada, dois deles em `C:/tmp`. Eles
**seguram o branch** e impedem o mantenedor de trabalhar nele: um `git checkout` falhou com
`branch is already used by worktree`.

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

- Alterar **arquivo existente** em `database.py`, `services/` ou `repositories/` enquanto a
  Fase A estiver em andamento — é onde o refactor trabalha, e conflito ali custa caro.
  **Criar módulo novo em `services/` é permitido** e é como as tarefas de implementação
  avançam trilha sem colidir (ROADMAP R31).
- Mudança de schema (R4) — passa pelo dono do schema, sempre serializada.
- Alteração de regra de negócio com efeito numérico (GMD, custo, carência, venda).
- Qualquer coisa que exija credencial de produção.
