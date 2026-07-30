# ADR 0002 — Fronteira de portabilidade: banco e framework de UI

- **Status:** Aceito
- **Data:** 2026-07-29
- **Relacionado:** [ADR 0001](0001-multi-fazenda-schema-por-tenant.md)

---

## Contexto

Pergunta levantada: como preparar o sistema para trocar de banco de dados e sair do
Streamlit, caso essas plataformas não dêem mais conta com o crescimento?

Levantamento feito no código (2026-07-29):

| Verificação | Resultado |
|---|---|
| Uso de bibliotecas proprietárias do Supabase (`supabase-py`, Storage, Realtime, Auth) | **0 ocorrências** em `app.py` e `database.py` |
| ORM | **Nenhum** — SQL cru com `psycopg2` |
| Ponto de acesso ao banco | `_conn()` — 82 usos, conexão criada em **um só lugar** |
| Destino do banco | `DATABASE_URL` via env var ou `st.secrets` |
| Fotos dos animais | `bytea` no próprio Postgres (sem dependência de storage externo) |
| `database.py` importa Streamlit no topo? | **Não** — import preguiçoso em `try/except` com fallback no-op |
| A camada de dados roda sem Streamlit? | **Sim — verificado empiricamente** bloqueando o import: o módulo carrega, as regras de negócio executam, o cache degrada para no-op |

Conclusão do levantamento: a portabilidade já existe em grande medida, mas era
**acidental** — nada no projeto a garantia. O risco real não está no código atual,
está nas escolhas futuras.

---

## Decisão

### 1. PostgreSQL é permanente; o provedor é substituível

Trocar Supabase por Neon, RDS, Cloud SQL ou Postgres self-hosted é: apontar
`DATABASE_URL` para o novo host + `pg_dump`/`pg_restore`. Nada mais.

**Não criar abstração para trocar de *engine* de banco** — nada de ORM, DAO genérico
ou "repositório agnóstico" para permitir um dia usar MySQL ou Mongo. Isso é custo
garantido contra benefício hipotético. O projeto não vai sair do Postgres.

(O suporte SQLite existente é para desenvolvimento e teste, não estratégia de troca
de banco — e cobra seu preço: ver o pré-requisito de migrations no ADR 0001.)

### 2. Regra de negócio nunca depende do framework de UI

`database.py` — e qualquer `services/` futuro — **não pode importar `streamlit` no
nível do módulo**. Onde o Streamlit for útil (cache, segredos), usar import preguiçoso
com fallback funcional, seguindo o padrão já existente em `_cache` e `_database_url()`.

Garantido por `tests/test_portabilidade.py`, que roda em subprocesso com o import de
`streamlit` bloqueado e falha se a regra for violada.

### 3. Evitar as dependências do Supabase que criam lock-in real

O lock-in perigoso não é o banco — é a identidade e os dados saindo do seu Postgres:

| Recurso | Decisão | Motivo |
|---|---|---|
| **Supabase Auth** | ❌ **Vetado** | As contas passariam a viver fora do seu banco. Migrar depois = migrar identidades e senhas de todos os clientes. Manter a tabela `users` própria (PBKDF2 já implementado) e autenticar pela própria aplicação/API. |
| **Supabase Storage** | ⚠️ Evitar enquanto `bytea` atender | Se um dia necessário, usar via API S3-compatível, não SDK proprietário. |
| **Realtime** | ⚠️ Evitar | Acoplaria o frontend ao broker do Supabase. |
| **Edge Functions / Cron** | ✅ Permitido | Isolados, pequenos e reescrevíveis em qualquer runtime. São a forma correta de rodar tarefas agendadas — o app Streamlit dorme (cold start de ~40s medido em 2026-07-29). |

Isto **contradiz deliberadamente** o `Plano_Implementacao_AgroTop_Web.md` seção 14.2,
que propõe Supabase Auth para o mobile. Motivo: com a tabela `users` própria no web e
Supabase Auth no mobile, haveria dois modelos de identidade incompatíveis — e o próprio
critério de aceite do plano ("permissões do web e do mobile produzem o mesmo resultado")
seria impossível de cumprir.

### 4. Caminho de saída do Streamlit (quando necessário)

Não é preciso um projeto de portabilidade separado: **"sair do Streamlit" e "modularizar
em serviços" são a mesma tarefa.**

```
Hoje:     Streamlit (app.py) ──► database.py ──► Postgres
Depois:   Streamlit ─┐
          Mobile ────┼──► API (FastAPI) ──► services/ ──► repositories/ ──► Postgres
          Cron/Job ──┘
```

Ao extrair `services/` conforme a Fase 0, a API vira uma casca fina sobre eles, e o
Streamlit passa a ser **um cliente entre outros** — não precisa ser substituído. Ele
pode seguir como painel administrativo indefinidamente.

O esqueleto de uma API já existe em `backend_api/` no branch arquivado
(`git show archive/app-mobile-obsoleto:backend_api/main.py`) — FastAPI com CORS e
routers. Aproveitar a estrutura, **não** a lógica: o `terminacao_service.py` de lá
duplica `simular_terminacao` do `database.py`, e regra de negócio duplicada é
exatamente o que esta decisão existe para evitar.

---

## Quando o Streamlit deixa de atender

Sinais concretos, para não trocar de plataforma por antecipação:

- **Não é escala.** Com 1 fazenda e 2 usuários, o modelo atual (cache + `@st.fragment`)
  atende com folga.
- **O que força a mudança é:** (a) o app mobile, que precisa de uma API de qualquer forma;
  (b) comercializar, que exige always-on e autenticação por tenant.
- **Limite conhecido do tier atual:** a instância dorme; cold start de ~40s. Resolve-se
  com plano pago ou outro host, sem trocar de framework.
- Ambos os gatilhos são resolvidos pela **camada de serviços** — não por substituir a UI.

---

## Consequências

- Custo hoje: praticamente zero. A portabilidade já existia; foi apenas travada por teste
  e documentada.
- Nenhuma abstração especulativa é adicionada ao código.
- A decisão sobre Supabase Auth precisa ser refletida no plano antes da fase do mobile.
- Revisitar se: aparecer requisito de tempo real (Realtime), ou se as fotos em `bytea`
  se tornarem um problema de custo/desempenho no Postgres.
