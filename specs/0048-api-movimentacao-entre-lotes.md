# Spec 0048 — API: movimentação de animais entre piquetes

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 2 dias
- **Branch:** `feat/api-movimentacao-entre-lotes`
- **Altere:** `backend_api/` (adiciona rotas e testes ao que a spec 0044 entregou)
- **Pré-requisito obrigatório:** **a spec [0044](0044-api-fastapi-autenticacao-e-endpoints-essenciais.md)
  precisa estar mesclada em `main` antes de você começar.** Confirme:
  ```bash
  git fetch origin
  git cat-file -e origin/main:backend_api/main.py 2>/dev/null \
    && echo "0044 já mesclada — pode seguir" \
    || echo "0044 AINDA NÃO mesclada — pare e avise quem te instruiu"
  ```
  Diferente da 0047 (mobile), esta spec **não** pode rodar contra um mock: ela adiciona
  rota ao mesmo app FastAPI que a 0044 criou, então o código dela precisa existir de
  verdade primeiro.

---

## Regra de ouro desta spec

Você **estende** `backend_api/`, criado pela 0044 — não recria a autenticação, não toca no
que já existe além de adicionar as rotas novas. Zero lógica de negócio nova: a movimentação
já existe pronta em `repositories/animais.py::move_animals_bulk`, você só expõe.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), subtarefa 1.5 (ver a lista que o mantenedor
publicou). Endpoint que faltava para o Mobile (spec 0049) oferecer "mover animal(is) de
piquete" no campo — o mesmo recurso que a aba "🔀 Transferir Animais" já oferece na web
(Trilha 3, fechada), agora pela API.

## Contexto que você precisa

- `repositories/animais.py::move_animals_bulk(animal_ids, to_lote_id, movement_date,
  reason="manejo", operator="", notes="") -> dict` já existe, já testado
  (`tests/test_regras_negocio.py` e a prova de UI da Trilha 3). Devolve
  `{"movidos": [...], "ja_no_destino": [...], "erros": [...]}`. **Não reimplemente nada
  disso** — importe e chame.
- `database.py::get_all_lotes()` devolve os piquetes (`id`, `name`, `capacity_ua`,
  `animal_count`, entre outros) — é o que alimenta o seletor de destino na tela.
- Animal que já está no piquete de destino não gera evento novo (comportamento de
  `move_animals_bulk`, preservado — não filtre isso você mesmo, a função já faz).
- Todos os endpoints exigem `Authorization: Bearer <access_token>`, igual aos da 0044.

## Contrato obrigatório

```
GET  /lotes
     -> 200 [{ "id": str, "nome": str, "capacidade_ua": float | null,
                "animais_ativos": int }, ...]

POST /animais/movimentar
     body: { "animal_ids": [str, ...], "to_lote_id": str,
              "movement_date": str,          # "AAAA-MM-DD"
              "reason": str | null,          # default "manejo" se omitido
              "notes": str | null }
     -> 200 { "movidos": [str, ...], "ja_no_destino": [str, ...], "erros": [str, ...] }
```

`reason` sem valor usa o mesmo default de `move_animals_bulk` ("manejo") — não invente
outro. `operator` do `move_animals_bulk` vem do usuário autenticado (o `name`/`username`
decodificado do token), nunca do corpo da requisição — o cliente não pode dizer "fui eu"
por outra pessoa.

## Critério de aceite

1. `GET /lotes` sem `Authorization` devolve `401`.
2. `GET /lotes` com token válido devolve exatamente os piquetes que
   `database.get_all_lotes()` devolve no mesmo banco — teste comparando os dois, não um
   valor fixo.
3. `POST /animais/movimentar` move de fato: compare `animals.lote_id` no banco antes e
   depois da chamada, não só o corpo da resposta.
4. Um `animal_id` inexistente na lista aparece em `"erros"`, e os outros animais válidos da
   mesma chamada são movidos mesmo assim (mesma regra de `move_animals_bulk` — não
   derruba a operação toda por causa de um item ruim).
5. Um animal já no piquete de destino aparece em `"ja_no_destino"` e **não** gera linha
   nova em `animal_movements` para ele (confira no banco).
6. `operator` gravado em `animal_movements` é o usuário do token, mesmo que o corpo da
   requisição tente mandar outro nome em algum campo — teste enviando um `operator` falso
   no body (se você aceitar esse campo por engano) e confirmando que foi ignorado.
7. `git grep -n "UPDATE animals SET lote_id\|INSERT INTO animal_movements" backend_api/`
   não acha nada — prova de que a rota só chama `move_animals_bulk`, não replica o SQL.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `services/`, `repositories/`, `poc/`.
- ❌ Não altere as rotas/testes que a 0044 já entregou — só adicione.
- ❌ Não aceite `operator` do corpo da requisição para gravar como autor do evento — vem
  sempre do token.
- ❌ Não implemente `GET /animais/{id}/historico-movimentacoes` nem qualquer outra rota
  fora das duas do contrato — fora de escopo desta fatia.
- ❌ Não hospede nem faça deploy.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 AGROTOP_API_SECRET=$(python -c "import secrets;print(secrets.token_hex(32))") \
  python -m unittest tests.test_backend_api -v
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
python -m compileall backend_api tests
git diff --stat origin/main
```

No diff, só arquivos dentro de `backend_api/` e `tests/test_backend_api.py` (extensão, não
substituição do que a 0044 já tem).

## Entrega

PR para `main`, pronto para revisão. No corpo, confirme explicitamente que partiu de
`origin/main` com a 0044 já mesclada (cole a saída do comando de verificação da seção
"Pré-requisito obrigatório").
