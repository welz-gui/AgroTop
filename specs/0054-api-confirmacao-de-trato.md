# Spec 0054 — API: confirmação de trato/nutrição por piquete

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 2 dias
- **Branch:** `feat/api-confirmacao-de-trato`
- **Altere:** `backend_api/` (adiciona rotas e testes ao que a spec 0044 entregou)
- **Pré-requisito obrigatório:** **a spec [0044](0044-api-fastapi-autenticacao-e-endpoints-essenciais.md)
  precisa estar mesclada em `main` antes de você começar.** Confirme:
  ```bash
  git fetch origin
  git cat-file -e origin/main:backend_api/main.py 2>/dev/null \
    && echo "0044 já mesclada — pode seguir" \
    || echo "0044 AINDA NÃO mesclada — pare e avise quem te instruiu"
  ```
  Mesmo motivo da 0048/0050/0052: esta spec adiciona rota ao mesmo app FastAPI da 0044,
  não dá pra mockar código que ainda não existe.

---

## Regra de ouro desta spec

Você **estende** `backend_api/`. Zero lógica de negócio nova: as funções que você vai
expor (`database.py::get_pending_feedings`, `database.py::add_feeding_check`) já existem,
já são usadas em produção pelo Modo Campo do web (`app.py::_campo_trato`), e já têm todas
as regras — período por frequência (diário/semanal/mensal), baixa de estoque condicional,
conversão de unidade. Você só expõe.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), a última subtarefa pendente do escopo de Mobile v1
online: confirmação de trato/nutrição — a mesma tela que já existe no web em
**Modo Campo → 🌾 Trato do Dia**, pela API.

## Contexto que você precisa

- **`feeding_plans`** é a programação: cada linha é um item de trato de um piquete (produto,
  quantidade planejada, unidade, frequência, opcionalmente vinculado a um insumo do estoque).
  Só planos com `active=1` interessam aqui.
- **`feeding_checks`** é a confirmação: o operador registra que aplicou (ou não) o trato de
  um plano numa data. `database.py::get_pending_feedings(ref_date)` já cruza as duas
  tabelas e devolve, para cada plano ativo, se ele **já foi confirmado no período atual**
  (o período depende da frequência: um plano diário reseta todo dia, um semanal reseta toda
  semana ISO, um mensal todo mês — a função já resolve isso, não reimplemente).
- **`database.py::add_feeding_check(plan_id, lote_id, check_date, status,
  actual_quantity=None, operator="", notes="", deduct_stock=False, insumo_id=None,
  quantity_unit="kg")`** já existe, pronta, e **já decide sozinha** se baixa estoque: só
  desconta `insumos.current_stock` quando `deduct_stock=True` **e** `insumo_id` não é nulo
  **e** `status != "nao_feito"`. Se o plano não tem insumo vinculado, passar
  `deduct_stock=True` não faz nada (a função ignora silenciosamente) — não precisa validar
  isso na rota, a função já é seguro por padrão.
- **`database.FEEDING_CHECK_STATUS`** = `{"feito": ..., "parcial": ..., "nao_feito": ...}` —
  são os três valores válidos de `status`. Qualquer outro valor deve ser rejeitado.
- Essas funções moram direto em `database.py` (não foram extraídas para `repositories/`
  ainda) — importe de lá, mesmo padrão que `backend_api/main.py` já usa para
  `add_photo`/`get_all_lotes`/`get_photo_image`/`get_photos`:
  ```python
  from database import add_feeding_check, get_pending_feedings, FEEDING_CHECK_STATUS
  ```
- `operator` do `add_feeding_check` vem do usuário autenticado (igual a `applied_by` na
  0050, `operator` na 0048) — **nunca** do corpo da requisição.
- `check_date` é sempre **hoje** (mesma simplicidade do web, que não tem seletor de data em
  Modo Campo) — a rota usa `date.today().isoformat()`, não aceita data no corpo.
- `lote_id`, `insumo_id` e `quantity_unit` do plano **a rota busca sozinha** a partir do
  `plan_id` (via `get_pending_feedings` ou uma consulta equivalente) — nunca aceite esses
  três do corpo da requisição. Evita que o cliente confirme um trato num piquete errado ou
  force a baixa de um insumo que não é o do plano.

## Contrato obrigatório

```
GET  /trato/pendentes
     -> 200 [{ "plano_id": int, "lote_id": str, "lote_nome": str, "produto": str,
                "quantidade": float, "unidade": str, "frequencia": str,
                "insumo_id": int | null,
                "confirmado_no_periodo": bool, "ultima_confirmacao": str | null }, ...]
     (só planos com active=1; "confirmado_no_periodo" e "ultima_confirmacao" vêm de
     get_pending_feedings(date.today()) — done_this_period e last_check, renomeados)

POST /trato/{plano_id}/confirmar
     body: { "situacao": "feito" | "parcial" | "nao_feito",
              "quantidade_aplicada": float,
              "baixar_estoque": bool,
              "notas": str | null }
     -> 201 { "ok": true }
     plano_id inexistente ou com active=0 -> 404
     "situacao" fora dos três valores válidos -> 422 (deixe o Pydantic validar com um
     Literal["feito", "parcial", "nao_feito"], não compare string à mão)
```

## Critério de aceite

1. `GET /trato/pendentes` sem `Authorization` devolve `401`.
2. `GET /trato/pendentes` devolve só planos ativos — crie um inativo no teste (`active=0`)
   e confirme que ele não aparece.
3. `GET /trato/pendentes` devolve `confirmado_no_periodo`/`ultima_confirmacao` iguais ao
   que `database.get_pending_feedings(date.today())` calcula no mesmo banco (`done_this_period`/
   `last_check`) — compare os dois, não hardcode um valor esperado.
4. `POST /trato/{plano_id}/confirmar` grava de fato: confira a linha nova em
   `feeding_checks` no banco, não só o `201`.
5. Depois de um `POST` num plano pendente, um `GET /trato/pendentes` seguinte devolve
   `confirmado_no_periodo: true` para aquele plano — prova de ponta a ponta que os dois
   endpoints concordam.
6. `operator` gravado em `feeding_checks` é o usuário do token, mesmo que o corpo tente
   mandar outro valor em algum campo (mesmo teste da 0048/0050).
7. `baixar_estoque: true` **baixa** `insumos.current_stock` quando o plano tem `insumo_id`
   vinculado — teste com números reais (estoque antes/depois), não só o `201`.
8. `baixar_estoque: true` **não altera** `insumos.current_stock` de nenhum insumo quando o
   plano **não** tem `insumo_id` vinculado — os dois casos (7 e 8), não só um.
9. `POST /trato/{plano_id}/confirmar` com `plano_id` inexistente devolve `404`, e com
   `plano_id` de um plano **inativo** (`active=0`) também devolve `404` — inativo não é
   confirmável.
10. `POST` com `"situacao": "invalido"` (fora dos três valores) devolve `422`.
11. `git grep -n "INSERT INTO feeding_checks\|UPDATE insumos SET current_stock" backend_api/`
    não acha nada — prova de que a rota só chama `add_feeding_check`.
12. `git grep -n "lote_id\|insumo_id\|quantity_unit" backend_api/schemas.py` no schema de
    **entrada** (`ConfirmarTratoInput` ou nome equivalente) não acha nenhum desses três
    campos — prova de que a rota busca isso sozinha, não confia no corpo.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `services/`, `repositories/`, `poc/`.
- ❌ Não altere as rotas/testes que a 0044/0048/0050/0052 já entregaram — só adicione.
- ❌ Não aceite `operator`, `lote_id`, `insumo_id` nem `check_date`/`data` do corpo da
  requisição — todos vêm do servidor (usuário autenticado, plano buscado por `plano_id`,
  data de hoje).
- ❌ Não implemente `POST /trato/planos` (cadastrar item de trato) nem edição/exclusão de
  plano — isso é tela de administração (`page_trato` no web), fora de escopo. Esta spec só
  cobre a **confirmação** de um plano já cadastrado pelo admin.
- ❌ Não reimplemente o cálculo de período (diário/semanal/mensal) — `get_pending_feedings`
  já faz isso; se você notar um caso que parece errado, pare e reporte, não "corrija" com
  lógica nova na rota.
- ❌ Não hospede nem faça deploy.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 AGROTOP_API_SECRET=$(python -c "import secrets;print(secrets.token_hex(32))") \
  python -m unittest tests.test_backend_api -v
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
python -m compileall backend_api tests
git diff --stat origin/main
```

No diff, só arquivos dentro de `backend_api/` e `tests/test_backend_api.py`.

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0044 já mesclada (cole a saída do comando de verificação).
