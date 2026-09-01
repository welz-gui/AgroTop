# Spec 0067 — API: criar lote

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `feat/api-criar-lote`
- **Altere:** só `backend_api/` (`main.py`, `schemas.py`) e os testes correspondentes
- **Pré-requisito:** nenhum — `database.py::add_lote` já existe, testada, em produção via
  o app web.

---

## Regra de ouro desta spec

**Zero lógica nova.** Esta API só expõe, em JSON, o formulário "➕ Novo Lote" que
`app.py::page_lotes` (aba `lt2`) já usa chamando `database.py::add_lote`. A **transferência**
de animais entre lotes **já está coberta** pela API/mobile de movimentação (specs
0048/0049, `POST /animais/movimentar`) — esta spec cobre só a metade que falta: criar o
lote em si (ADR 0007 §2.2: "page_lotes (além da movimentação já coberta)").

## Objetivo

Terceiro item do Tier 1 da [ADR 0007](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md)
(paridade admin no mobile). "Criar lote... é decisão tomada olhando o rebanho no pasto" —
um piquete novo, um curral, uma divisão que só faz sentido percebida no campo. Esta spec
cria a API; a spec mobile seguinte ([0068](0068-mobile-criar-lote.md)) consome.

## Contexto que você precisa

- **Criação** — `database.py::add_lote(data: LoteData) -> None`, onde:
  ```python
  @dataclass
  class LoteData:
      lote_id: str
      name: str
      area_ha: float
      capacity_ua: float
      notes: str = ""
      property_id: Optional[int] = None
  ```
  Sem `property_id`, `add_lote` já assume a propriedade padrão sozinha (comentário na
  própria função: "Assumir é aceitável enquanto existe uma propriedade só") — **não informe
  `property_id` no endpoint**, deixe o default cuidar disso, mesmo comportamento do web.
- **`add_lote` não valida duplicidade sozinha** — quem chama (`app.py`) confere antes:
  ```python
  elif db.get_lote(lid):
      st.error(f"Lote {lid} já existe.")
  ```
  Sem essa checagem, inserir um `lote_id` repetido estoura erro de `PRIMARY KEY` cru do
  banco. **Repita essa checagem no endpoint** — não é regra nova, é mover uma validação que
  já existe da UI para a API, mesmo princípio de toda API deste projeto.
- **Listagem** — `GET /lotes` já existe (`backend_api/main.py`), devolve
  `LoteSummary { id, nome, capacidade_ua, animais_ativos }` via `get_all_lotes()`. Devolva
  o lote recém-criado no **mesmo formato**, para o cliente não precisar de um schema
  diferente para "acabei de criar" vs "está na lista".

## Contrato obrigatório

```
POST /lotes
  body: {
    "id": str,              # o "brinco" do piquete — ex. "P07"
    "nome": str,
    "area_ha": float,
    "capacidade_ua": float,
    "observacoes": str = ""
  }
  -> 201: { "id": str, "nome": str, "capacidade_ua": float, "animais_ativos": 0 }
  -> 409: já existe um lote com esse `id` — detail: "Lote {id} já existe."
  -> 422: validação de schema (Pydantic já cobre isso — `id`/`nome` não vazios,
     `area_ha`/`capacidade_ua` não negativos)
```

- Autenticação igual às outras rotas (token válido, qualquer papel — o web não restringe
  `page_lotes` a admin).
- **Sem `Idempotency-Key`** — mesmo padrão do endpoint `/trato/{plano_id}/confirmar`
  (spec 0054): fora do escopo da fila offline (ADR 0006 cobre só
  pesagem/medicamento/movimentação, spec 0060). Um duplo-toque acidental sem rede vira um
  409 óbvio, não uma duplicata silenciosa — o `id` do lote já é a chave que impede isso.

## Critério de aceite

1. `POST /lotes` sem token → 401.
2. Corpo válido → 201, lote aparece depois em `GET /lotes`.
3. `id` repetido de um lote já existente → 409, **não** cria nem altera o lote existente.
4. `id`/`nome` vazio, ou `area_ha`/`capacidade_ua` negativo → 422 (deixe o Pydantic
   recusar, não escreva validação manual para isso).
5. Lote criado sem `property_id` explícito (não faz parte do body) recebe a propriedade
   padrão — confirme consultando a tabela `lotes` depois, mesmo comportamento do web.
6. `flake8`/`ruff` e a suíte inteira de `tests/test_backend_api.py` verde.

## Proibições

- ❌ Não implemente transferência de animais entre lotes — já coberta pela 0048/0049
  (`POST /animais/movimentar`).
- ❌ Não exponha `property_id` no corpo do request — deixe `add_lote` assumir o default,
  mesmo comportamento do web.
- ❌ Não calcule nada no `backend_api/` — a criação já existe em `database.py::add_lote`;
  a única lógica desta spec (checar duplicidade antes) é mover validação de UI existente,
  não inventar regra.
- ❌ Não altere `app.py`, `database.py`, `services/`, `repositories/` nem as specs
  anteriores.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall backend_api tests
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que os 6 critérios têm teste com
prova real (não só "não deu erro") — mesmo padrão das specs 0054/0050/0063/0065.
