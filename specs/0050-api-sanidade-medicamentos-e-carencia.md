# Spec 0050 — API: registrar medicamento e consultar carência

> ✅ **Concluída** ([PR #181](https://github.com/welz-gui/AgroTop/pull/181)) — este
> arquivo já não é uma tarefa para pegar, é o registro do que foi entregue. **Atualização
> de 2026-08-22:** a revisão da spec 0051 (mobile) achou uma contradição real — 0051 exige
> preencher a dose automaticamente ao escolher um protocolo, mas `GET /protocolos` não
> devolvia dose nenhuma, e a fórmula que calcula a dose por animal
> (`repositories/sanidade.py::dose_for_animal`, fixa ou proporcional ao peso conforme o
> protocolo) não podia ser duplicada no mobile (ROADMAP: nenhuma fórmula de negócio em
> Dart). Corrigido pelo mantenedor: `GET /protocolos` ganhou o parâmetro opcional
> `?animal_id=` e o campo `dose_sugerida` (ver contrato abaixo, já atualizado). A função
> interna que fazia o cálculo perdeu o `_` do nome (`_dose_for_animal` →
> `dose_for_animal`) por ganhar um consumidor fora de `repositories/sanidade.py`.

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 2 dias
- **Branch:** `feat/api-sanidade-medicamentos`
- **Altere:** `backend_api/` (adiciona rotas e testes ao que a spec 0044 entregou)
- **Pré-requisito obrigatório:** **a spec [0044](0044-api-fastapi-autenticacao-e-endpoints-essenciais.md)
  precisa estar mesclada em `main` antes de você começar.** Confirme:
  ```bash
  git fetch origin
  git cat-file -e origin/main:backend_api/main.py 2>/dev/null \
    && echo "0044 já mesclada — pode seguir" \
    || echo "0044 AINDA NÃO mesclada — pare e avise quem te instruiu"
  ```
  Mesmo motivo da 0048: esta spec adiciona rota ao mesmo app FastAPI da 0044, não dá pra
  mockar código que ainda não existe.

---

## Regra de ouro desta spec

Você **estende** `backend_api/`. Zero lógica de negócio nova: `repositories/sanidade.py`
já tem tudo — `add_medication`, `get_medications`, `get_withdrawal_end`, `get_protocols`.
Você só expõe.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), subtarefas 1.7/1.9. Sanidade (registrar aplicação de
medicamento) e consulta de carência — a mesma informação que a ficha do animal já mostra no
web, pela API.

## Contexto que você precisa

- `repositories/sanidade.py::add_medication(animal_id, medication_name, dose, unit,
  application_route, withdrawal_days, med_date, applied_by="", insumo_id=None, notes="",
  protocol_id=None)` já existe. **Nesta fatia, `insumo_id` fica sempre `None`** — sem baixa
  de estoque pela API ainda (decisão abaixo, "O que fica fora").
- `repositories/sanidade.py::get_medications(animal_id, limit=None)` e
  `get_withdrawal_end(animal_id)` já existem, prontos.
- `repositories/sanidade.py::get_protocols(active_only=True)` já existe — protocolos
  sanitários cadastrados (nome, espécie-alvo, dose, via, carência), para o operador
  escolher em vez de digitar um nome de medicamento à mão.
- `applied_by` do `add_medication` vem do usuário autenticado (igual ao `operator` da
  0048) — nunca do corpo da requisição.

## O que fica fora desta fatia (decisão registrada, não esquecimento)

**Sem baixa de estoque pela API.** `add_medication` só desconta `insumos.current_stock`
quando `insumo_id` é passado — e vincular medicamento a insumo exige o operador escolher de
uma lista de insumos, que não tem endpoint ainda. Ligar isso é trabalho de uma spec futura
(endpoint de insumos), quando fizer sentido pelo volume de uso real do app. Por ora, a
aplicação é registrada sem afetar estoque — mesmo comportamento de quando o web registra sem
selecionar insumo.

## Contrato obrigatório

```
GET  /protocolos?animal_id=<opcional>
     -> 200 [{ "id": int, "nome": str, "via": str, "carencia_dias": int,
                "unidade_dose": str, "dose_sugerida": float | null }, ...]
     (protocolos ATIVOS — active_only=True, sempre)

     Sem `animal_id`: "dose_sugerida" vem `null` em todos os itens — a dose de um
     protocolo com `dose_ref_kg` é proporcional ao peso do animal, não existe um valor
     único sem saber de quem. Com `animal_id` válido: "dose_sugerida" é
     `dose_for_animal(protocolo, animal)` (fixa ou proporcional, a mesma conta que
     `apply_protocol_campaign` já usa). `animal_id` inexistente devolve `404`.

GET  /animais/{id}/medicamentos
     -> 200 { "carencia_ate": str | null,       # "AAAA-MM-DD", de get_withdrawal_end
              "aplicacoes": [{ "medicamento": str, "dose": float, "unidade": str,
                                "via": str, "carencia_dias": int, "data": str,
                                "protocolo_id": int | null }, ...] }

POST /animais/{id}/medicamentos
     body: { "medicamento": str, "dose": float, "unidade": str, "via": str,
              "carencia_dias": int, "data": str,        # "AAAA-MM-DD"
              "protocolo_id": int | null, "notas": str | null }
     -> 201 { "carencia_ate": str | null }   # recalculada após a aplicação
```

## Critério de aceite

1. `GET /protocolos` sem `Authorization` devolve `401`.
2. `GET /protocolos` devolve só protocolos ativos — crie um inativo no teste e confirme
   que ele não aparece.
3. `GET /animais/{id}/medicamentos` devolve `carencia_ate` igual ao que
   `repositories.sanidade.get_withdrawal_end(id)` calcula no mesmo banco — compare os dois,
   não um valor fixo.
4. `POST /animais/{id}/medicamentos` grava de fato: confira a linha nova em `medications`
   no banco, não só o `201`.
5. Depois de um `POST` com `carencia_dias > 0`, um `GET /animais/{id}/medicamentos`
   seguinte devolve `carencia_ate` no futuro — prova de ponta a ponta que os dois endpoints
   concordam.
6. `applied_by`/`operator` gravado é o usuário do token, mesmo que o corpo tente mandar
   outro valor em algum campo (mesmo teste da 0048, item 6).
7. `insumo_id` nunca é passado a `add_medication` por esta rota — confira que
   `insumos.current_stock` não muda depois do `POST` (prova de que a fatia realmente não
   baixa estoque, não é só documentação).
8. `git grep -n "INSERT INTO medications\|UPDATE animals SET status='carencia'" backend_api/`
   não acha nada — prova de que a rota só chama `add_medication`.
9. **(Adicionado 2026-08-22)** `GET /protocolos?animal_id=<id>` devolve `dose_sugerida`
   igual ao que `repositories.sanidade.dose_for_animal(protocolo, animal)` calcula no
   mesmo banco, para um protocolo de dose fixa e para um de dose proporcional ao peso
   (`dose_ref_kg > 0`) — os dois casos, não só um.
10. **(Adicionado 2026-08-22)** `GET /protocolos` sem `animal_id` devolve `dose_sugerida:
    null` em todos os itens; com `animal_id` inexistente, `404`.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `services/`, `repositories/`, `poc/`.
- ❌ Não altere as rotas/testes que a 0044 ou a 0048 já entregaram — só adicione.
- ❌ Não passe `insumo_id` para `add_medication` — ver "O que fica fora".
- ❌ Não implemente `POST /protocolos` (cadastrar protocolo) nem
  `POST /protocolos/{id}/aplicar-campanha` (campanha em lote) — fora de escopo, o mobile
  de campo aplica um animal de cada vez.
- ❌ Não aceite `applied_by`/`operator` do corpo da requisição.
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
