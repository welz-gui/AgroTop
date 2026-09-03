# Spec 0071 — API: expor as recomendações do motor de regras

- **Tipo:** implementação · **Risco:** médio (única spec de API desta trilha toda que
  precisa tocar `app.py` — leia "Regra de ouro" com atenção) · **Esforço:** 1 dia
- **Branch:** `feat/api-recomendacoes`
- **Altere:** `app.py` (só a relocação descrita abaixo), `database.py`, `backend_api/`
  (`main.py`, `schemas.py`) e os testes correspondentes
- **Pré-requisito:** nenhum — `services/recomendacoes.py::avaliar` existe desde a
  [spec 0011](0011-motor-de-regras.md), pura, testada, em produção no app web
  (`app.py::_alertas_operacionais`, aba "🔔 Operacionais" → "🧭 Recomendações").

---

## Regra de ouro desta spec

**Mover, não reescrever.** `app.py::_contexto_recomendacoes` (e as duas funções que ela usa,
`_custo_medio_por_arroba` e `_consumo_diario_por_insumo`) já montam exatamente o `contexto`
que `services/recomendacoes.py::avaliar` precisa — só que hoje moram em `app.py`, que o
`backend_api/` não pode importar (é a camada de UI Streamlit, não a de dados). Esta spec
**relocaliza essas três funções para `database.py`** — a mesma migração mecânica, sem mudar
uma linha de lógica, que toda outra função de `database.py` já passou. O motor de regras em
si (`services/recomendacoes.py`) **não muda nada** — continua puro, sem tocar banco.

**Por que isto é diferente de toda outra spec de API deste projeto:** a
[spec 0063](0063-api-alertas-operacionais.md) (que expôs os outros alertas) parou exatamente
aqui e registrou por quê: "expô-lo pela API exigiria mover esse contexto para um lugar
reutilizável primeiro (trabalho de outra spec, não desta)." Esta é essa spec. Por isso, e só
por isso, ela toca `app.py` — nenhuma outra proibição de spec anterior fica revogada.

## Objetivo

Última peça que falta do ROADMAP Trilha 4 já **entregue e em produção só no web**: "🧭
Recomendações" é a pergunta "o que eu deveria fazer agora, e por quê" — hoje só existe no
navegador. Esta spec expõe pela API; uma spec mobile seguinte (a escrever depois) consome.

## Contexto que você precisa

- **`app.py::_contexto_recomendacoes()`** (função sem argumentos, devolve o `dict` de
  contexto) — leia o corpo atual em `app.py` antes de mexer, é a fonte da verdade exata a
  copiar. Chama, nesta ordem: `_consumo_diario_por_insumo()`, `date.today()`,
  `db.get_all_animals(status="ativo")`, `db.get_withdrawal_end_batch(ids)`,
  `db.calculate_gmd_bulk(ids)`, `db.get_all_lotes()`, `db.get_all_insumos()`,
  `_to_float(db.get_setting("preco_arroba"))`, `_custo_medio_por_arroba()`.
- **`app.py::_custo_medio_por_arroba()`** — usa `db.get_all_animals(status="ativo")`,
  `db._costs_by_animal()` (já em `repositories/financeiro.py`, reexportado por
  `database.py`) e `db.kg_to_arrobas` (já em `services/zootecnia.py`, idem).
- **`app.py::_consumo_diario_por_insumo()`** — usa `db.get_all_insumos()`,
  `db.get_feeding_plans(active_only=True)` e
  `services/previsao_estoque_adaptador.py::consumo_diario_planejado` (spec 0039) — este
  import (`from services.previsao_estoque_adaptador import consumo_diario_planejado`)
  ainda não existe em `database.py`, adicione-o.
- **`_to_float(v)`** é um helper de duas linhas (`try: float(v) except: None`) — mova
  também, ou inline onde for usada; comportamento idêntico, não invente validação nova.
- **Nomes ao mover:** as três funções relocadas podem perder o `_` inicial só na que o
  `backend_api/` vai chamar (`contexto_recomendacoes()`, pública). As duas auxiliares
  (`_custo_medio_por_arroba`, `_consumo_diario_por_insumo`) continuam privadas dentro de
  `database.py` — mesmo padrão de `db._costs_by_animal` já existente lá.
- **Em `app.py`:** apague as três funções originais e o helper `_to_float` (se não usado em
  mais nenhum lugar — confira com um grep antes de apagar) e troque a única chamada em
  `_alertas_operacionais` de `_contexto_recomendacoes()` para
  `db.contexto_recomendacoes()`. **Não mude mais nada em `app.py`** — nem o texto, nem a
  ordenação por severidade, nem o tratamento de exceção que já existe ali.
- **O motor em si** (`services/recomendacoes.py::avaliar`) é importado **direto pelo
  `backend_api/main.py`**, não via `database.py` — mesmo padrão da
  [spec 0069](0069-api-perimetro-do-piquete-por-pontos.md), que chama
  `services.geometria.validar` direto: `database.py` monta o contexto (dado), o serviço
  puro aplica a regra (lógica), o endpoint só liga os dois.

## Contrato obrigatório

```
GET /recomendacoes
  -> 200: [
       {
         "regra": str,
         "severidade": "alta" | "media" | "baixa",
         "titulo": str,
         "motivo": str,
         "dados": dict,
         "acao": str
       },
       ...
     ]
```

- Devolve exatamente o que `services.recomendacoes.avaliar(contexto)` devolve — **não
  filtre, não reordene, não traduza campo nenhum**. A ordenação por severidade que existe
  no web (`_alertas_operacionais`) é decisão de **exibição**, não da API; se a spec mobile
  quiser essa ordem, ela ordena no cliente ou você decide isso lá, não aqui.
- `dados` é um dict de formato livre (cada regra tem os seus campos) — modele como
  `dict[str, Any]`, não crie um schema rígido para o conteúdo.
- Se `avaliar(contexto)` levantar exceção com um dado faltando de verdade (não deveria,
  R31: regra dependente de chave ausente é pulada, não quebra) — **não capture a exceção
  aqui**; deixe subir como 500. Mascarar isso pela API esconderia um bug real do motor.
- Autenticação igual às outras rotas de leitura (token válido, qualquer papel).

## Critério de aceite

1. `GET /recomendacoes` sem token → 401.
2. Contexto onde nenhuma regra dispara (fazenda "limpa": sem animal, sem lote, sem insumo)
   → 200, lista vazia — **não é erro**, é o dia sem pendência.
3. Contexto que dispara pelo menos duas regras diferentes (ex. `estoque_insuficiente` e
   `gmd_abaixo_da_meta`, construídos via `database.configurar_sqlite`/inserts diretos no
   teste) → 200, ambas presentes na resposta, com `motivo`/`dados`/`acao` preenchidos —
   comparando contra uma chamada direta a `services.recomendacoes.avaliar` com o mesmo
   contexto montado independentemente no teste (prova real, não só "não deu erro").
4. `database.contexto_recomendacoes()` chamada isolada (sem subir a API) devolve o mesmo
   formato de dict que `services.recomendacoes.avaliar` espera — teste direto da função
   relocada, sem precisar do FastAPI de permeio.
5. `app.py` não tem mais `_contexto_recomendacoes`, `_custo_medio_por_arroba` nem
   `_consumo_diario_por_insumo` definidas — só a chamada a `db.contexto_recomendacoes()`
   em `_alertas_operacionais`. **Não existe hoje uma prova automatizada da renderização de
   `page_alertas`** (`tests/test_alertas.py` testa `get_alert_animals`, não a página) — não
   precisa criar uma nesta spec, mas rode `AGROTOP_FORCE_SQLITE=1 python -m unittest
   discover -s tests -t . -v` (nada pode quebrar) e confirme manualmente pelo app web
   (`streamlit run app.py` → "🔔 Alertas Ativos" → "🧭 Recomendações") que a seção continua
   idêntica.
6. `flake8`/`ruff` e a suíte inteira verde.

## Proibições

- ❌ Não mude o texto, a severidade, o motivo ou a ação de nenhuma regra existente —
  `services/recomendacoes.py` **não muda nesta spec**.
- ❌ Não reordene nem filtre a lista na API — a API devolve exatamente o que `avaliar`
  devolve.
- ❌ Não mude nada em `app.py` além de apagar as três funções relocadas, o helper
  `_to_float` (se órfão) e trocar a única chamada — nenhuma outra linha da página de
  alertas muda.
- ❌ Não invente schema rígido para `dados` — é formato livre por regra, de propósito
  (ver contrato da spec 0011).
- ❌ Não altere `services/recomendacoes.py`, `services/previsao_estoque_adaptador.py` nem
  nenhuma outra spec anterior.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall app.py database.py backend_api tests
```

Rode também o app web localmente (`streamlit run app.py`) e confira a página "🔔 Alertas
Ativos → 🧭 Recomendações" — precisa continuar idêntica ao que era antes da relocação.

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que os 6 critérios têm teste com
prova real, que a relocação foi mecânica (sem alterar lógica), e cole a saída de rodar a
página de alertas manualmente confirmando que nada mudou visualmente.
