# Spec 0057 — API: importação de pesagens por CSV

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 2 dias
- **Branch:** `feat/api-importacao-de-pesagens-csv`
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

Você **estende** `backend_api/`. Zero lógica de negócio nova: `services/importacao.py::
parse_pesagens` (parser puro, testado desde a spec 0008), `services/qualidade.py::
avaliar_pesagem` (indícios de erro, usada em produção pelo web) e
`repositories/pesagens.py::add_weighing`/`get_weighings_batch` já existem e já fazem tudo
isso — inclusive já é o caminho exato que `app.py::_campo_importar` usa hoje. Você só
expõe, num único endpoint que faz **pré-visualização** e **gravação** com o mesmo parse.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), item 3 ("Importação CSV do indicador da balança") —
**explicitamente listado à parte das 5 fatias do mobile**, porque vale mesmo depois que
houver Bluetooth (pareamento falha no campo). Hoje só existe no web
(Modo Campo → 📥 Importar CSV); esta spec expõe pela API para o mobile ter a mesma
funcionalidade.

## Contexto que você precisa

- **`services/importacao.py::parse_pesagens(texto, *, ids_conhecidos=None)`** devolve
  `{"aceitas": [{"animal_id", "peso", "data"}, ...], "rejeitadas": [{"linha", "conteudo",
  "motivo"}, ...], "total_linhas": int}`. `ids_conhecidos` deve ser o conjunto de brincos
  de animais **ativos** — mesma fonte que `_campo_importar` usa
  (`{a["id"] for a in get_all_animals(status="ativo")}`).
- **Decodificação do arquivo:** tente `utf-8-sig` primeiro; se falhar, tente `latin-1`
  (indicadores de balança costumam exportar em cp1252/latin-1) — mesma lógica exata de
  `app.py::_campo_importar`, linha por linha idêntica, não invente uma terceira opção.
- **`services/qualidade.py::avaliar_pesagem(peso, data, historico)`** aponta indícios de
  erro (peso fora de faixa, data futura, etc.) sem bloquear — devolve uma lista de alertas
  com `severidade` (`"alta"` ou não). Só os de severidade `"alta"` interessam para o
  contrato (equivalente ao `altos` que `_campo_importar` calcula).
- **`historico` por animal** vem de `repositories.pesagens.get_weighings_batch(animal_ids)`
  (função criada nesta mesma sessão, já usada por `_campo_importar` desde a otimização de
  N+1) — **e**, dentro do próprio arquivo sendo importado: se duas linhas do mesmo CSV
  citam o mesmo animal, a pesagem da linha anterior (já processada) entra no histórico da
  próxima, na ordem `(animal_id, data)` — mesmo laço que `_campo_importar` já faz
  (`hist[linha["animal_id"]].insert(0, ...)`), não pule esse detalhe.
- **`repositories/pesagens.py::add_weighing(animal_id, weight, weigh_date, operator="",
  notes="", method="pesado")`** grava uma pesagem. `notes` deve registrar a origem, ex.
  `f"importado de {nome_do_arquivo}"` — mesma ideia do web.
- `operator` vem do usuário autenticado — **nunca** do corpo da requisição.

## Contrato obrigatório

```
POST /pesagens/importar-csv   (multipart/form-data)
     campos: arquivo=<arquivo CSV/TXT>, confirmar=<"true" | "false">
       ("confirmar" ausente equivale a "false" — só pré-visualiza, nunca escreve)
     -> 200 {
          "total_linhas": int,
          "aceitas": [{ "animal_id": str, "peso": float, "data": str,
                         "alertas": [str, ...] }, ...],
          "rejeitadas": [{ "linha": int, "conteudo": str, "motivo": str }, ...],
          "gravadas": int
             # 0 quando confirmar=false;
             # nº de linhas de "aceitas" realmente gravadas quando confirmar=true
        }
     arquivo maior que 1 MB -> 413
     arquivo vazio ou sem extensão .csv/.txt -> 422
```

Um único endpoint, chamado duas vezes pelo cliente com o **mesmo arquivo**: primeiro com
`confirmar=false` (prévia, nada é gravado), depois — se o operador confirmar visualmente —
com `confirmar=true` (grava). O parse roda os dois jeitos; a diferença é só se o laço de
gravação executa.

## Critério de aceite

1. `POST /pesagens/importar-csv` sem `Authorization` devolve `401`.
2. Com `confirmar=false` (ou ausente), **nada é gravado**: conte as linhas de `weighings`
   no banco antes e depois da chamada — devem ser iguais, mesmo que `aceitas` não esteja
   vazio.
3. Com `confirmar=true`, o número de linhas novas em `weighings` bate exatamente com
   `gravadas`, e `gravadas == len(aceitas)`.
4. `aceitas`/`rejeitadas`/`total_linhas` da resposta são idênticos ao que
   `services.importacao.parse_pesagens(texto, ids_conhecidos=ativos)` calcula para o mesmo
   arquivo — compare os dois, não hardcode um resultado esperado.
5. Os `alertas` de cada linha aceita batem com as mensagens de severidade `"alta"` que
   `services.qualidade.avaliar_pesagem` devolve para aquele peso/data/histórico — teste com
   pelo menos um caso que gera alerta (ex.: peso fora de faixa) e um que não gera.
6. Um arquivo com **duas linhas do mesmo animal** faz a segunda linha enxergar a primeira
   no histórico ao calcular o alerta — prova de que o acúmulo dentro do próprio arquivo
   funciona (mesmo comportamento do web).
7. `operator` gravado em `weighings` é o usuário do token, mesmo que o corpo tente mandar
   outro valor em algum campo.
8. Um arquivo em `latin-1` (não UTF-8) é decodificado e interpretado corretamente — não
   quebra nem devolve tudo como rejeitado por "encoding".
9. Arquivo acima de 1 MB devolve `413`. Arquivo vazio devolve `422`.
10. `git grep -n "INSERT INTO weighings\|UPDATE animals SET current_weight" backend_api/`
    não acha nada — prova de que a rota só chama `add_weighing`.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `services/`, `repositories/`, `poc/`.
- ❌ Não altere as rotas/testes que a 0044/0048/0050/0052/0054 já entregaram — só adicione.
- ❌ Não reimplemente `parse_pesagens` nem `avaliar_pesagem` — se notar um caso que parece
  errado, pare e reporte, não "corrija" com lógica nova na rota.
- ❌ Não aceite `operator` do corpo da requisição.
- ❌ Não invente um terceiro parâmetro de confirmação (ex. lista de linhas a excluir) — o
  fluxo é tudo-ou-nada, mesmo comportamento do botão único "Gravar N pesagem(ns)" do web.
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
