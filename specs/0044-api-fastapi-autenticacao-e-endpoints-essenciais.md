# Spec 0044 — API FastAPI de produção: autenticação e endpoints essenciais (v2)

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 3–5 dias
- **Branch:** `feat/api-fastapi-producao-v2`
- **Crie:** `backend_api/` (pasta nova) e `tests/test_backend_api.py` — **arquivos novos**

---

## ⚠️ O defeito da 1ª tentativa (leia antes de começar)

A [PR #169](https://github.com/welz-gui/AgroTop/pull/169) implementou a v1 desta spec e
foi **fechada sem merge** — o CI encontrou dois defeitos reais, nenhum deles culpa de quem
implementou: a própria spec tinha lacunas. O trabalho da v1 não foi perdido — está
preservado na tag `retrabalho/0044-api-fastapi-producao-v1-pr169`, reaproveitável como
referência.

**Defeito 1 — CI não instala as dependências novas.** `tests/test_backend_api.py` importa
`fastapi`/`jwt`/etc., mas `.github/workflows/ci.yml` só roda `pip install -r
requirements.txt` (a raiz) antes da suíte — `backend_api/requirements.txt` nunca é
instalado, então o teste quebra na importação (`ModuleNotFoundError: No module named
'jwt'`) antes mesmo de rodar. **Corrigido nesta v2:** você tem autorização explícita para
adicionar **um passo novo** em `.github/workflows/ci.yml`, logo depois do passo "Instalar
dependências" existente, instalando também `backend_api/requirements.txt` — e só isso, não
toque no resto do workflow (a etapa de Postgres, a suíte SQLite/Postgres em si, os nomes de
step existentes).

**Defeito 2 — tabela nova sem RLS+REVOKE na mesma migration.** `tests/test_rls_nas_migrations.py`
exige, desde a migration 0013, que toda tabela criada a partir dali ganhe `ENABLE ROW LEVEL
SECURITY` **e** `REVOKE ALL ... FROM anon, authenticated` **na mesma migration** que a cria
— não em uma migration separada depois. A v1 criou `api_refresh_tokens` sem o `REVOKE`,
quebrando o teste. **Modelo a seguir**, olhe
`supabase/migrations/0018_compras_e_contas_a_pagar.sql`: `ALTER TABLE ... ENABLE ROW LEVEL
SECURITY;` seguido de um bloco `DO $$ ... EXECUTE 'REVOKE ALL ON ... FROM anon,
authenticated'; ... END $$;` guardado por `IF EXISTS (SELECT 1 FROM pg_roles WHERE
rolname = 'anon')` (mesmo guard de portabilidade que a migration 0014 já usa) — copie
exatamente essa estrutura para a tabela de refresh tokens, se você criar uma.

## Regra de ouro desta spec

Você cria uma **pasta nova**, `backend_api/`. **Não altere nenhum arquivo existente** —
nem `app.py`, `database.py`, `repositories/`, `services/` nem `poc/api/`. Seu produto reusa
o que já existe por **import**, nunca por cópia (R8: cada regra vive em UM lugar).

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), etapa 1 — prioridade **alta** do mantenedor. A PoC
0005 (`poc/api/`) já provou a fronteira: Flutter → FastAPI → `services/`/`repositories/`
existentes, sem fórmula de negócio duplicada em Dart, sem Supabase Auth (ADR 0002 veta),
autenticando contra a mesma tabela `users` que o web usa.

**Esta spec não é a PoC evoluída — é a API de verdade, escrita do zero**, seguindo R30
("código de PoC não é mesclado como está — o produto da PoC é o aprendizado"). Leia
`poc/api/main.py` e `poc/api/README.md` como **referência de arquitetura já validada**, não
como base para copiar/colar. A PoC deixou registrado o que falta para produção — é
exatamente a lista de critérios de aceite abaixo.

## Contexto que você precisa

- `services/seguranca.py` já tem `_verify_password`, `_hash`, `_is_legacy_hash` (PBKDF2, com
  migração transparente do hash SHA-256 legado — mesma regra do login web, R8: não
  reimplemente).
- `repositories/conexao.py::_conn()` é o único ponto de acesso ao banco (R1). Use-o.
- A API **nunca** fala com Postgres via PostgREST nem usa `anon`/`authenticated` — conecta
  como o resto do sistema, via `_conn()`/`DATABASE_URL`.
- `AGROTOP_FORCE_SQLITE=1` é obrigatório para os testes (R16) — sem isso, testes podem
  conectar em produção. O worktree não tem `.streamlit/secrets.toml` (é gitignored), então
  isso é reforçado por construção, não só por variável de ambiente.

## Contrato obrigatório

### Autenticação (o que a PoC deixou como dívida — fechar aqui é o objetivo principal)

```
POST /auth/login      {username, password} -> {access_token, refresh_token, expires_in, user}
POST /auth/refresh     {refresh_token} -> {access_token, expires_in}
POST /auth/logout      {refresh_token} -> 204, revoga o refresh token
```

- **Rate limiting no login**: limite por IP e por `username` (ex.: 5 tentativas / 5 min);
  passar do limite devolve `429`, nunca `401` (não vaze se o usuário existe).
- **Access token de vida curta** (ex.: 15 min) + **refresh token de vida mais longa**
  (ex.: 7 dias), refresh token **revogável** — guarde os tokens ativos numa tabela nova
  (ver "O que você PODE criar" abaixo) para permitir revogação real, não só expiração.
- Falha de login não distingue "usuário não existe" de "senha errada" na mensagem.

### Endpoints de dados (mínimo para destravar o Mobile v1 depois — não é a lista completa
do ROADMAP, é o suficiente para provar o padrão com autorização de verdade)

```
GET  /animais                    -> lista (rebanho ativo, paginada)
GET  /animais/{id}               -> ficha de um animal
POST /animais/{id}/pesagens      {peso, data, method} -> registra pesagem
```

Todos exigem `Authorization: Bearer <access_token>` válido. Nenhuma lógica de negócio nova:
`POST /animais/{id}/pesagens` chama a mesma função que o web usa para registrar pesagem —
ache-a em `repositories/pesagens.py` ou `database.py` (fachada) antes de escrever qualquer
SQL novo.

## O que você PODE criar

- Uma tabela nova para refresh tokens revogáveis (ex.: `api_refresh_tokens`), **seguindo
  R2/R4**: vai no `CREATE TABLE` de `init_db()` (`database.py`), não só num `ALTER`. Como
  isso é mudança de schema, e schema é sempre serializado pelo dono (R4), **não aplique em
  produção** — deixe a migration em `supabase/migrations/00NN_....sql` pronta, mas a
  aplicação real é do mantenedor.
- `backend_api/requirements.txt` próprio (FastAPI, `pyjwt`, `slowapi` ou equivalente para
  rate limit, `uvicorn`) — **nunca** no `requirements.txt` da raiz, que alimenta o deploy do
  Streamlit Cloud.
- **Um passo novo em `.github/workflows/ci.yml`** instalando
  `backend_api/requirements.txt` (Defeito 1 da v1, ver acima) — só isso, nenhuma outra
  linha do workflow.

## Critério de aceite

1. Login com credenciais válidas devolve os dois tokens; `access_token` expira em ~15 min
   (teste manipulando o relógio ou o `exp` do JWT, não dormindo 15 min de verdade).
2. Login errado 6 vezes seguidas no mesmo minuto devolve `429` na 6ª, não `401`.
3. `refresh` com token revogado (depois de um `logout`) devolve `401`, nunca emite novo
   access token.
4. Endpoint de dados sem `Authorization` devolve `401`; com token expirado, `401`; com token
   de outro usuário, os dados voltam corretos **daquele** usuário (não há cross-tenant hoje,
   mas o teste prova que o token é validado, não só decodificado).
5. `POST /animais/{id}/pesagens` grava exatamente a mesma linha que
   `db.add_weighing`/equivalente grava pelo web — teste comparando o registro no banco, não
   só o `200` da resposta.
6. `git grep -n "def calculate_gmd\|def register_sale\|def get_total_cost" backend_api/`
   não acha nada — prova de que nenhuma regra foi reimplementada (R8).

## Proibições

- ❌ Não toque em `app.py`, `database.py` (exceto o `CREATE TABLE` novo do item acima, se
  você criar a tabela de refresh tokens), `services/`, `repositories/`, `poc/`.
- ❌ Não aplique a migration em produção — ela fica pronta para revisão, a aplicação é do
  mantenedor (R4, R26 — rollback documentado no arquivo).
- ❌ Não hospede nem faça deploy. Decisão de provedor (Render/Railway/Fly) e conta paga são
  do mantenedor — ver ROADMAP, "Decisões operacionais pendentes".
- ❌ Não crie autorização por tenant/organização — não existe esse conceito no schema hoje
  (ver a migration 0024 desta mesma base, que documentou por quê). Fora de escopo.
- ❌ Não adicione Supabase Auth, Firebase Auth ou qualquer serviço de identidade externo —
  vetado pelo ADR 0002.
- ❌ Não escreva regra de negócio nova em `backend_api/` — se a validação de pesagem, por
  exemplo, ainda não existir em `services/`, **pare e reporte no PR**, não implemente ali.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 AGROTOP_API_SECRET=$(python -c "import secrets;print(secrets.token_hex(32))") \
  python -m unittest tests.test_backend_api -v
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
python -m compileall backend_api tests
git diff --stat origin/main
```

Use `unittest` + `httpx`/`fastapi.testclient.TestClient` (mesmo padrão de `poc/api/test_api.py`)
— este projeto usa um único executor de testes (R16), não introduza `pytest`.

O `-t .` não é opcional (R16). No `git diff --stat`, só `backend_api/`,
`tests/test_backend_api.py`, `.github/workflows/ci.yml` (só a linha nova de instalação), e
— se você criou a tabela de refresh tokens — `database.py` (só o `CREATE TABLE`) e o
arquivo de migration novo em `supabase/migrations/`.

**Confirme que o próprio CI da sua PR roda `tests.test_backend_api` de verdade** — abra o
log do job e confira que os testes da API aparecem na lista, não só que a suíte inteira
passou. Suíte verde com o arquivo pulado silenciosamente (por `ImportError`, por exemplo)
não é a mesma coisa que suíte verde com o arquivo executado — foi exatamente essa diferença
que a v1 não pegou a tempo.

## Entrega

PR para `main`, pronto para revisão. No corpo:
- Confirme que os 6 critérios de aceite passam, com a saída colada.
- Se criou a tabela de refresh tokens, aponte o número da migration, confirme que ela **não
  foi aplicada** em nenhum banco além do SQLite do worktree, e cole o trecho da migration
  com `ENABLE ROW LEVEL SECURITY` + `REVOKE` (Defeito 2 da v1).
- Cole o link do run de CI da sua própria PR e confirme que `tests.test_backend_api`
  aparece executado no log, não pulado (Defeito 1 da v1).
- Diga qual biblioteca de rate limiting escolheu e por quê.
