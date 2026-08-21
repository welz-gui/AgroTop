# Spec 0052 — API: enviar e consultar foto do animal

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 2 dias
- **Branch:** `feat/api-foto-do-animal`
- **Altere:** `backend_api/` (adiciona rotas e testes ao que a spec 0044 entregou)
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

Você **estende** `backend_api/`. Zero lógica de negócio nova: `database.py::add_photo`,
`get_photos`, `get_photo_image` já existem e já são usados pelo web — você só expõe.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), subtarefa 1.10. Enviar foto do animal pelo celular —
hoje só é possível pela câmera do navegador no web.

## Contexto que você precisa

- **Fotos ficam em `bytea` no Postgres, nunca em storage externo** (ROADMAP, seção "Deve
  ser mantido": "não migrar para storage externo sem ADR"). Esta spec **não muda isso** —
  usa exatamente as mesmas funções que o web usa.
- `database.py::add_photo(animal_id, image_bytes, mime="image/jpeg", taken_date=None,
  operator="")` grava. `operator` vem do usuário autenticado, nunca do corpo.
- `database.py::get_photos(animal_id)` lista metadados (sem os bytes).
- `database.py::get_photo_image(photo_id)` devolve `(bytes, mime)` de uma foto.
- **A compressão da imagem é responsabilidade do app mobile, não desta API** (decisão
  abaixo) — o app já teria motivo de sobra pra reduzir antes de subir (economizar dados
  móveis no campo).

## Decisão: por que a API não comprime a imagem

O web tem `_compress_image` (`app.py`) que redimensiona/comprime antes de gravar — mas
essa função mora em `app.py`, que nenhuma spec pode tocar. Reimplementar a mesma lógica
aqui duplicaria regra (R8) sem um lugar comum para as duas viverem sem tocar em `app.py`.
Em vez disso: **a API aceita o que o cliente mandar, até um limite de tamanho, e recusa o
que passar disso** — o app mobile (spec 0053) já compensa comprimindo antes de enviar,
igual qualquer app de câmera faria por economia de dados.

## Contrato obrigatório

```
POST /animais/{id}/fotos
     multipart/form-data: campo "arquivo" (a imagem), campo opcional "taken_date"
     Limite: 5 MB. Acima disso, 413.
     Tipos aceitos: image/jpeg, image/png. Outro tipo, 415.
     -> 201 { "id": int }

GET  /animais/{id}/fotos
     -> 200 [{ "id": int, "taken_date": str, "mime": str }, ...]
     (metadados, SEM os bytes — mesmo formato de `get_photos`)

GET  /fotos/{id}
     -> 200, corpo é a imagem, `Content-Type` = o `mime` gravado
     -> 404 se não existir
```

## Critério de aceite

1. `POST /animais/{id}/fotos` sem `Authorization` devolve `401`.
2. Upload de uma imagem válida (jpeg pequeno de teste) grava de fato — confira a linha em
   `animal_photos` no banco, e que `GET /fotos/{id}` devolve os mesmos bytes que foram
   enviados (comparação byte a byte, não só tamanho).
3. Upload acima de 5 MB devolve `413`, **antes** de gravar qualquer coisa no banco (confira
   que não sobrou linha órfã).
4. Upload de um tipo não aceito (ex.: `application/pdf` disfarçado) devolve `415`.
5. `GET /animais/{id}/fotos` nunca inclui os bytes da imagem no JSON — só metadados
   (confira o tamanho da resposta, não deve escalar com o tamanho da foto).
6. `GET /fotos/{id}` de uma foto de outro animal ainda funciona (não há isolamento por
   dono hoje, mesmo comportamento do restante do sistema) — mas `GET /fotos/{id}`
   inexistente devolve `404`, nunca `500`.
7. `operator` gravado é o usuário do token.
8. `git grep -n "INSERT INTO animal_photos" backend_api/` não acha nada — só
   `database.add_photo`.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `services/`, `repositories/`, `poc/`.
- ❌ Não altere as rotas/testes que specs anteriores já entregaram — só adicione.
- ❌ Não implemente compressão/redimensionamento de imagem nesta API — ver a decisão
  acima. Só valide tamanho e tipo.
- ❌ Não use nenhum storage externo (S3, Supabase Storage, etc.) — ADR 0002 e a regra do
  ROADMAP sobre fotos em `bytea`.
- ❌ Não implemente `DELETE /fotos/{id}` — fora de escopo desta fatia.
- ❌ Não aceite `operator` do corpo da requisição.
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
0044 já mesclada.
