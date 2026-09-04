# Spec 0077 — API: relatórios de inventário do rebanho e pesagens

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/api-relatorios`
- **Altere:** só `backend_api/` (`main.py`, `schemas.py`) e os testes correspondentes
- **Pré-requisito:** nenhum — todas as funções que esta spec expõe já existem em
  `database.py`/`repositories/`/`services/zootecnia.py`, testadas, em produção via o app
  web. **Não precisa relocar nada de `app.py`**, diferente das specs 0071/0073.

---

## Regra de ouro desta spec

**Zero lógica nova.** Esta API só expõe, em JSON, as duas tabelas que
`app.py::page_relatorios` já monta nas abas "🐄 Inventário" e "⚖️ Pesagens" — orquestrando
funções que já existem, sem inventar campo nem conta nova.
[ADR 0007](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md) §2.3: **a aba
"💰 Financeiro" não entra** (é `page_financeiro`, fora de escopo do mobile por inteiro —
"digitação longa, decisão financeira, exige tela grande").

## Objetivo

Terceira e última spec de API do Tier 2. "Consulta pontual no campo" — ver o inventário
completo do rebanho ou o histórico de pesagens sem abrir o navegador; **exportar (CSV/
Excel/PDF) continua sendo tarefa de mesa**, não faz parte desta spec.

## Contexto que você precisa

- **Inventário** — `app.py::page_relatorios`, aba `rt1` (busque `"🐄 Inventário Completo do
  Rebanho"` em `app.py`), monta por animal:
  - `db.get_all_animals(status=None)` (todos os status, não só ativo)
  - `db.calculate_gmd_bulk(ids)` e `db.get_withdrawal_end_batch(ids)` (batch, já usadas em
    outras specs — 0063, por exemplo)
  - `db.get_age_category(a.get("birth_date"))` e `db.get_age_display(a)`
    (`services/zootecnia.py`, puras)
  - `db.AGE_SOURCES` (dict de tradução da origem da idade — **exponha o valor técnico da
    chave, a tradução é do cliente**, mesmo padrão de toda API deste projeto)
  - `db.kg_to_arrobas(a["current_weight"])`
  - Campos direto da linha do animal: `breed`, `sex`, `birth_date`, `birth_estimated`,
    `entry_date`, `entry_weight`, `current_weight`, `status`, `lote_id`, `fornecedor_name`,
    `nf_number`, `gta_number`.
- **Pesagens** — `app.py::page_relatorios`, aba `rt2`: `db.get_all_weighings()` (já usada
  por outras specs — devolve `animal_id`, `weigh_date`, `weight`, `method`, `lote_id`,
  `operator`, `notes`, `breed`). **`method` não é traduzido aqui** — o mobile já tem
  `WEIGH_METHODS` hardcoded desde a spec 0061, reaproveita.

## Contrato obrigatório

```
GET /relatorios/inventario
  -> 200: [
       { "id": str, "raca": str|null, "sexo": str|null, "categoria_idade": str,
         "idade_display": str, "data_nascimento": str|null,
         "nascimento_estimado": bool, "origem_idade": str,
         "data_entrada": str, "peso_entrada_kg": float, "peso_atual_kg": float,
         "ganho_kg": float, "arrobas_atuais": float, "gmd_kg_dia": float|null,
         "status": str, "lote_id": str|null, "fornecedor": str|null,
         "nf": str|null, "gta": str|null, "carencia_ate": str|null }
     ]

GET /relatorios/pesagens
  -> 200: [
       { "animal_id": str, "data": str, "peso_kg": float, "metodo": str,
         "lote_id": str|null, "operador": str|null, "observacoes": str|null }
     ]
```

- `categoria_idade` e `origem_idade` são os valores técnicos que
  `get_age_category`/`AGE_SOURCES` devolvem — **não traduza para português na API**.
- `metodo` é o código técnico (`pesado`, `estimado`, etc.) — mesmo padrão de `status` em
  `DispositivoOutput`, tradução é do cliente.
- `gmd_kg_dia` pode vir `null` (animal sem pesagens suficientes para calcular GMD) —
  **não é erro**, repasse como está.
- Autenticação igual às outras rotas de leitura (token válido, qualquer papel).
- **Sem paginação** — mesmo padrão de `GET /animais`/`GET /lotes`, que também devolvem a
  lista inteira; o rebanho deste projeto (~150-200 animais) não justifica paginar ainda.

## Critério de aceite

1. `GET /relatorios/inventario` sem token → 401.
2. `GET /relatorios/inventario` com pelo menos 3 animais (nascimento conhecido/estimado,
   com/sem carência, com/sem fornecedor) → 200, cada campo bate com uma chamada
   independente às mesmas funções (`get_age_category`, `get_age_display`,
   `calculate_gmd_bulk`, `get_withdrawal_end_batch`, `kg_to_arrobas`) montada no teste —
   prova real, não só "não deu erro".
3. `GET /relatorios/inventario` inclui animais de **todos os status**, não só `ativo`
   (confirme com um animal `vendido` ou `morto` aparecendo na resposta).
4. `GET /relatorios/pesagens` sem token → 401.
5. `GET /relatorios/pesagens` com pesagens de métodos diferentes → 200, `metodo` vem com o
   valor técnico (não traduzido), ordenado por data (mesma ordem de `get_all_weighings`).
6. `flake8`/`ruff` e a suíte inteira de `tests/test_backend_api.py` verde.

## Proibições

- ❌ Não exponha a aba "💰 Financeiro" — fora de escopo do mobile inteiro (ADR 0007 §2.4).
- ❌ Não traduza `categoria_idade`, `origem_idade` nem `metodo` para português — tradução é
  do cliente.
- ❌ Não implemente exportação (CSV/Excel/PDF) — é tarefa de mesa, fora de escopo (ADR 0007
  §2.3).
- ❌ Não recalcule nada fora das funções já existentes citadas em "Contexto" — se um campo
  parecer errado, o bug é na leitura, não em reimplementar a conta.
- ❌ Não altere `app.py`, `database.py`, `services/`, `repositories/` nem as specs
  anteriores.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall backend_api tests
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que os 6 critérios têm teste com
prova real — mesmo padrão das specs 0054/0063/0067/0075.
