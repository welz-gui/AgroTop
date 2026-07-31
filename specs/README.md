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

**Estados:** 🟢 disponível · 🟡 em andamento (anote quem pegou) · ✅ concluída (link do PR) ·
⚪ arquivada.

> **Atualize a tabela ao pegar uma tarefa.** Foi a ausência desse controle que fez dois
> agentes escreverem testes para a mesma função `_num_br`, em arquivos diferentes
> (PRs #9 e #10, ambos descartados).

---

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
