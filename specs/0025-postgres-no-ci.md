# Spec 0025 — Rodar a suíte também contra Postgres no CI

- **Tipo:** infraestrutura · **Risco:** **médio** · **Esforço:** 1–2 dias
- **Branch:** `feat/postgres-no-ci`
- **Altere:** `.github/workflows/ci.yml` · **Crie:** `tests/test_dialeto_postgres.py`

---

## ⚠️ Esta spec é exceção à regra de ouro

As outras specs proíbem tocar arquivo existente. Esta **precisa** alterar o workflow do CI —
é o objeto do trabalho. Mas continua valendo: **não toque em `app.py`, `database.py`,
`repositories/`, `services/` nem `ui/`.**

## Por que isto existe

Em **2026-08-02 a produção caiu** com `psycopg2.errors.SyntaxError`. A causa foi um
`PRAGMA table_info` — sintaxe exclusiva do SQLite — numa função que roda com `USE_PG=True`.

O defeito atravessou **225 testes verdes, revisão e merge**. O motivo é estrutural: a suíte
inteira roda com `AGROTOP_FORCE_SQLITE=1`, o que está correto e existe para impedir que os
testes toquem produção (R16/R18) — mas significa que **nenhum teste enxerga o caminho
Postgres**.

`tests/test_dialeto_duplo.py` cobre o padrão específico lendo o código, e teria pego aquele
caso. Não substitui rodar de verdade.

## O que fazer

1. **Adicione um serviço `postgres` ao job do CI** (`services:` no `ci.yml`, imagem oficial,
   healthcheck). Não use banco externo — o CI não pode depender de rede nem de credencial.
2. **Rode a suíte duas vezes:** uma com `AGROTOP_FORCE_SQLITE=1` (como hoje) e outra com
   `DATABASE_URL` apontando para o Postgres do serviço. Use `matrix` ou dois steps — o que
   deixar o resultado mais legível quando um dos dois falhar.
3. **Crie o schema no Postgres** a partir de `supabase/migrations/0000_baseline_producao.sql`.
   Ele já é replay-validado por `tools/testar_baseline.py`; **não escreva DDL novo.**
4. **`tests/test_dialeto_postgres.py`** — pelo menos: `init_db()` completa, um ciclo de
   escrita e leitura (cadastrar animal, pesar, ler de volta), e os gatilhos append-only de
   `animal_events` recusando `UPDATE` e `DELETE`.

## Critério de aceite

1. O CI fica verde nos dois modos.
2. **Prove que pega o defeito real:** reintroduza `PRAGMA table_info` em alguma função que
   roda com `USE_PG=True`, mostre o CI vermelho, e reverta. Cole a evidência no PR.
   Guarda que não pega o caso que motivou sua criação não é guarda.
3. O modo SQLite continua sendo o padrão para quem roda local — ninguém deve precisar de
   Postgres na máquina para rodar `python -m unittest`.
4. O tempo total do CI não passa de ~4 minutos. Se passar, diga no PR quanto ficou.

## Proibições

- ❌ **Nunca coloque credencial real no workflow.** O Postgres é efêmero, do serviço do CI,
  com senha de teste. A do Supabase não entra aqui em nenhuma hipótese (R18/R19).
- ❌ Não aponte o CI para o banco de produção. Nem para leitura.
- ❌ Não altere `app.py`, `database.py`, `repositories/`, `services/`, `ui/`.
- ❌ Não altere as migrations existentes.
- ❌ Não remova nem enfraqueça `tests/test_isolamento.py` — ele existe para garantir que a
  suíte não alcance produção, e continua valendo.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
```

E, com um Postgres local (Docker):

```bash
DATABASE_URL=postgresql://... python -m unittest discover -s tests -t .
```

## Entrega

PR para `main`, pronto para revisão. No corpo: o tempo do CI antes e depois, e a **evidência
do defeito reintroduzido sendo pego**.
