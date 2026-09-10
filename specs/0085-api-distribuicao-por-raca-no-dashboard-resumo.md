# Spec 0085 — API: distribuição por raça no `/dashboard/resumo`

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `feat/api-distribuicao-raca-dashboard`
- **Altere:** só `backend_api/` (`main.py`, `schemas.py`) e os testes correspondentes
- **Pré-requisito:** nenhum — `repositories/animais.py::get_all_animals()` já existe,
  testado, em produção; cada animal já traz o campo `breed`

---

## Regra de ouro desta spec

Mesma disciplina da spec 0075 (que criou este endpoint): **zero lógica nova.** Contar
quantos animais existem por raça é agregação simples sobre dado que já existe — não é
uma segunda implementação de nada, é só mais um campo no mesmo resumo.

## Objetivo

[ADR 0007 §5](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md) (emenda de
2026-09-10) libera **um** gráfico leve no dashboard resumo do mobile, para aproximar
usabilidade/design do padrão web — começando pela distribuição de animais por raça
(o gráfico de rosca que `app.py::_dash_chart_por_raca` já mostra no dashboard web). Esta
spec expõe o dado; a spec 0086 (mobile) desenha o gráfico.

## Contexto que você precisa

- **`repositories/animais.py::get_all_animals() -> list[dict]`** — já é chamado em outros
  pontos da API (`main.py`, `from repositories.animais import get_all_animals`), cada
  item tem a chave `"breed"`.
- **`app.py::_dash_chart_por_raca`** (linha ~946) já faz exatamente esta contagem no web:
  `pd.Series([a["breed"] for a in animals]).value_counts()`. **Não precisa de pandas
  aqui** — é a mesma conta com `collections.Counter`, sem trazer uma dependência nova
  pro `backend_api/requirements.txt`.
- **`backend_api/main.py::dashboard_resumo`** (linha ~141) é o handler a estender —
  já chama `get_rebanho_stats()`/`get_alert_animals()`; adicione a chamada a
  `get_all_animals()` e a contagem por raça ali, sem criar módulo novo (é uma linha de
  `Counter`, não justifica um `services/` novo).
- **Animal sem raça preenchida** — `breed` pode ser string vazia ou ausente dependendo do
  cadastro. Trate como uma categoria própria ("Não informada"), **não descarte o animal
  da contagem** — se descartar, `total_animais` do resumo não bate com a soma das
  quantidades por raça, e isso confunde quem for comparar os dois números na tela.

## Contrato obrigatório

Adicionar ao `DashboardResumoOutput` (`backend_api/schemas.py`):

```python
class RacaContagemOutput(BaseModel):
    raca: str
    quantidade: int

class DashboardResumoOutput(BaseModel):
    # ...campos existentes, sem alteração...
    distribuicao_por_raca: list[RacaContagemOutput]
```

- Ordenada por `quantidade` decrescente (maior raça primeiro — mesma ordem que fica mais
  legível num gráfico de rosca, maior fatia primeiro).
- Raça vazia/ausente vira `"Não informada"` — string fixa, não `None` (o mobile não
  precisa tratar nulo).
- Rebanho vazio → lista vazia, não erro (mesmo padrão do resto do endpoint, que já
  devolve `AnimalStats()` zerado sem animal nenhum).

## Critério de aceite

1. `GET /dashboard/resumo` sem token → 401 (comportamento já existente, sem mudança).
2. Fazenda com animais de raças diferentes → `distribuicao_por_raca` traz uma entrada por
   raça distinta, quantidade batendo com uma contagem manual no teste (prova real).
3. **A soma de todas as `quantidade` em `distribuicao_por_raca` é igual a
   `total_animais`** — teste explícito disso, é a garantia de que nenhum animal foi
   descartado por raça vazia.
4. Animal com `breed` vazio/nulo aparece agrupado em `"Não informada"`, não desaparece da
   contagem.
5. Fazenda sem nenhum animal → `distribuicao_por_raca` é lista vazia, resposta continua
   200 (não 500).
6. Ordenação decrescente por quantidade testada com pelo menos 3 raças de tamanhos
   diferentes.
7. `flake8`/`ruff` e a suíte inteira de `tests/test_backend_api.py` verde.

## Proibições

- ❌ Não crie um `services/` novo para uma contagem de uma linha — inline no handler,
  mesmo padrão de simplicidade que a spec 0075 já estabeleceu para este endpoint.
- ❌ Não adicione pandas (ou qualquer dependência nova) a `backend_api/requirements.txt`
  — `collections.Counter` (stdlib) já resolve.
- ❌ Não descarte animal sem raça da contagem.
- ❌ Não exponha nenhum outro dado novo além da distribuição por raça — GMD por animal,
  evolução de peso e conformidade continuam fora do escopo mobile (ADR 0007 §2.3/§5).
- ❌ Não altere `app.py`/`database.py`/`services/` — esta spec só lê o que já existe.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall backend_api tests
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo do PR o teste do critério 3 (soma
bate com `total_animais`) com a prova real colada.
