# Spec 0059 — API: chave de idempotência nos endpoints de escrita

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 2 dias
- **Branch:** `feat/api-idempotency-key`
- **Altere:** `backend_api/` (novo módulo + rotas existentes), `database.py` (schema
  SQLite), `supabase/migrations/` (nova migration)
- **Pré-requisito obrigatório:** **a spec [0044](0044-api-fastapi-autenticacao-e-endpoints-essenciais.md)
  precisa estar mesclada em `main` antes de você começar.** Confirme:
  ```bash
  git fetch origin
  git cat-file -e origin/main:backend_api/main.py 2>/dev/null \
    && echo "0044 já mesclada — pode seguir" \
    || echo "0044 AINDA NÃO mesclada — pare e avise quem te instruiu"
  ```

---

## Regra de ouro desta spec

Base para o mobile offline ([ADR 0006](../docs/adr/0006-mobile-offline-fila-de-escrita.md)):
sem isto, uma ação enfileirada no celular que é reenviada porque a resposta se perdeu no
meio do caminho grava **duas vezes**. O mecanismo é genérico — **um módulo novo, usado
pelos quatro endpoints de escrita que já existem**, não quatro implementações separadas
(R8: cada regra vive em UM lugar).

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), etapa 5 (mobile offline) — a metade que é API,
decidida na [ADR 0006](../docs/adr/0006-mobile-offline-fila-de-escrita.md). Sem lógica de
negócio nova: só uma tabela de deduplicação e um header opcional.

## Contexto que você precisa

- **Mecanismo:** header HTTP `Idempotency-Key` (opcional, string). Quando presente:
  - Se a mesma chave **já foi vista com sucesso** para aquele endpoint, a rota **não
    executa a escrita de novo** — devolve a resposta gravada da primeira vez (mesmo
    `status_code`, mesmo corpo), como se tivesse acabado de processar.
  - Se a chave é nova, a rota executa normalmente e, **só se der certo** (2xx), grava a
    chave e a resposta antes de devolver ao cliente.
  - **Nunca cacheie uma resposta de erro** (4xx/5xx) — se a escrita falhar, a chave não é
    gravada, e uma nova tentativa com a mesma chave tenta de novo do zero. O problema que
    isto resolve é duplicar uma escrita que **deu certo**, não lembrar de erros.
- **Sem header, nada muda** — os quatro endpoints continuam funcionando exatamente como
  hoje. Isto é aditivo, não é breaking change.
- **Só os quatro endpoints de escrita que já existem em produção:**
  `POST /animais/{id}/pesagens`, `POST /animais/{id}/medicamentos`,
  `POST /animais/movimentar`, `POST /animais/{id}/fotos`. **Não mexa em `/auth/*`** — login
  não tem o mesmo risco de duplicação (não cria registro por tentativa) e não faz parte do
  escopo desta ADR.
  As specs 0054 (trato) e 0057 (importação CSV) **ainda não estão mescladas** — quando
  mesclarem, seus endpoints de escrita (`POST /trato/{id}/confirmar`,
  `POST /pesagens/importar-csv`) precisarão do mesmo tratamento numa spec/PR futura; não é
  desta spec, porque o código deles não existe em `main` ainda.
- **Padrão a seguir:** `backend_api/auth.py::create_refresh_token`/`verify_refresh_token`
  já fazem exatamente este tipo de coisa — SQL cru contra `_conn()` de
  `repositories.conexao`, sem passar por `database.py`/`repositories/`, porque é
  infraestrutura da API, não dado de domínio. **Crie `backend_api/idempotency.py`** seguindo
  o mesmo padrão, com duas funções:
  ```python
  def get_cached_response(key: str) -> Optional[dict]:
      """None se a chave não foi vista. Senão, {"status_code": int, "response_body": <dict decodificado>}."""

  def store_response(key: str, endpoint: str, status_code: int, response_body: dict) -> None:
      """Grava a chave. Chame só depois de confirmar que a escrita deu certo."""
  ```
- **Para devolver o `status_code` original numa resposta cacheada**, a rota precisa
  aceitar `response: Response` (de `fastapi`) como parâmetro e setar
  `response.status_code = cached["status_code"]` antes de devolver `cached["response_body"]`
  — é assim que se sobrescreve o `status_code` fixo do decorator numa rota FastAPI.

## Migration nova (schema)

**Tabela nova, mesmo padrão exato de `api_refresh_tokens` (spec 0044,
`supabase/migrations/0025_api_refresh_tokens.sql`)** — copie a estrutura da migration
(RLS + `REVOKE ALL FROM anon, authenticated` **na mesma migration**, é obrigatório desde a
migration 0013):

```sql
CREATE TABLE IF NOT EXISTS api_idempotency_keys (
    idempotency_key text PRIMARY KEY,
    endpoint        text NOT NULL,
    status_code     integer NOT NULL,
    response_body   text NOT NULL,   -- JSON serializado
    created_at      timestamptz DEFAULT now()
);
```

Nome do arquivo: `supabase/migrations/00XX_api_idempotency_keys.sql` (confira o próximo
número livre — não assuma 0026, `ls supabase/migrations/ | tail -3` antes de nomear).

**Espelhe também no SQLite** — `database.py` tem uma constante `_SCHEMA_SQL` com o DDL de
desenvolvimento/teste; `CREATE TABLE api_refresh_tokens` está lá (linha ~947) como
template exato de tipos (`TEXT`/`INTEGER` em vez de `text`/`integer`,
`DEFAULT (datetime('now','localtime'))` em vez de `DEFAULT now()`). As duas versões do
schema (SQLite e Postgres) **precisam existir juntas nesta PR** — `tests/test_schema.py`
compara as duas.

## Contrato obrigatório

```
Header opcional em POST /animais/{id}/pesagens, POST /animais/{id}/medicamentos,
POST /animais/movimentar, POST /animais/{id}/fotos:

  Idempotency-Key: <string qualquer, tipicamente um UUID>

Comportamento:
  - Sem o header: idêntico ao que já existe hoje.
  - Header novo (nunca visto): executa normalmente; se der 2xx, grava a chave.
  - Header repetido (já visto com sucesso): NÃO executa de novo, devolve a resposta
    gravada (mesmo status_code, mesmo corpo).
```

## Critério de aceite

1. Sem `Idempotency-Key`, os quatro endpoints se comportam **exatamente** como antes —
   rode a suíte existente de `tests/test_backend_api.py` sem tocar nela e confirme que
   nada quebrou.
2. `POST /animais/{id}/pesagens` chamado duas vezes com o **mesmo** `Idempotency-Key`:
   confira em `weighings` que existe **uma linha só**, e que as duas respostas HTTP são
   idênticas (status e corpo).
3. Mesmo teste do item 2 para `POST /animais/{id}/medicamentos` (confira `medications`),
   `POST /animais/movimentar` (confira o resultado da movimentação) e
   `POST /animais/{id}/fotos` (confira `animal_photos` — só uma foto gravada, não duas).
4. Duas chamadas com chaves **diferentes** fazem duas escritas normais — a deduplicação
   não pode ser mais agressiva do que deveria.
5. Uma chamada que **falha** (ex.: `animal_id` inexistente, `404`) **não** grava a chave —
   confirme repetindo a mesma chamada com dados corrigidos e a mesma chave: ela executa
   normalmente, não devolve o erro antigo cacheado.
6. `tests/test_rls_nas_migrations.py` passa com a tabela nova (RLS + REVOKE presentes na
   mesma migration).
7. `tests/test_schema.py` passa — schema SQLite e Postgres da tabela nova batem em tipo e
   coluna.
8. `git grep -n "idempotency" backend_api/main.py` mostra uso do módulo novo nos quatro
   endpoints — não uma cópia da lógica de dedupe em cada rota.

## Proibições

- ❌ Não toque em `app.py`, `services/`, `repositories/`, `poc/`.
- ❌ Não altere as rotas/testes que a 0044/0048/0050/0052 já entregaram além do necessário
  para adicionar o parâmetro do header e a chamada ao módulo novo — sem reescrever lógica
  existente.
- ❌ Não mexa em `/auth/login`, `/auth/refresh`, `/auth/logout`.
- ❌ Não adicione o mecanismo às rotas da 0054/0057 — elas não estão mescladas.
- ❌ Não cacheie resposta de erro (4xx/5xx) — ver "Contexto".
- ❌ Não invente expiração/limpeza automática das chaves nesta fatia — a tabela cresce sem
  limite por ora; se isso virar problema real de volume, é spec futura (decisão registrada,
  não esquecimento).
- ❌ Não hospede nem faça deploy.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 AGROTOP_API_SECRET=$(python -c "import secrets;print(secrets.token_hex(32))") \
  python -m unittest tests.test_backend_api tests.test_rls_nas_migrations tests.test_schema -v
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
python -m compileall backend_api tests
git diff --stat origin/main
```

No diff: arquivos em `backend_api/`, `tests/test_backend_api.py`, `database.py` (só a
constante de schema), e a migration nova em `supabase/migrations/`.

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0044 já mesclada, e cole o nome exato da migration criada.
