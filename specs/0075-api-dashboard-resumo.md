# Spec 0075 — API: resumo do dashboard (KPIs)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `feat/api-dashboard-resumo`
- **Altere:** só `backend_api/` (`main.py`, `schemas.py`) e os testes correspondentes
- **Pré-requisito:** nenhum — `database.py::get_rebanho_stats` e `get_alert_animals` já
  existem, testados, em produção via o app web. **Diferente das specs 0071/0073, esta não
  precisa relocar nada de `app.py`** — as duas funções já moram em `database.py`.

---

## Regra de ouro desta spec

**Zero lógica nova.** Esta API só expõe, em JSON, os números que
`app.py::_dash_kpis`/`_dash_alerts` já mostram no topo de `page_dashboard` — chamando
`database.py::get_rebanho_stats()` (devolve o dataclass `AnimalStats`) e
`database.py::get_alert_animals()` (já usada pelo endpoint `/alertas`, spec 0063).
Nenhuma conta nova, nenhuma agregação diferente.

## Objetivo

Segunda spec do Tier 2 da [ADR 0007](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md)
(paridade admin no mobile, só leitura). "Visão geral rápida tem valor no bolso" (ADR 0007
§2.3) — os 7 KPIs do topo do dashboard (animais, peso médio, GMD médio, produção, lotação,
machos, fêmeas) mais a contagem resumida de alertas. **O dashboard completo (gráficos de
evolução de peso, pizza por raça, GMD por animal, tabela resumo, conformidade,
completude) fica de fora** — pede tela grande, ADR 0007 é explícita sobre isso
("resumo, não o completo").

## Contexto que você precisa

- **`database.py::get_rebanho_stats() -> AnimalStats`** — dataclass com `total`,
  `avg_weight`, `avg_gmd`, `total_kg`, `males`, `females`, `total_ua`, `total_area`,
  `lotacao_ua_ha`, `arrobas_prod`. Devolve `AnimalStats()` (todos os campos zerados) quando
  não há animal cadastrado — **não é erro**, repasse como está.
- **`database.py::get_alert_animals() -> dict`** com chaves `sumidos`, `carencia`,
  `prontos` (cada uma uma lista) — a API devolve só a **contagem** de cada uma
  (`len(...)`), mesmo dado que `app.py::_dash_alerts` mostra nos três cartões
  ("🔴 N Sumidos", "🟡 N Em Carência", "🟢 N Prontos para Abate"). **Não repita a lista
  completa aqui** — quem quiser o detalhe usa `GET /alertas` (spec 0063), já existente.
- **Sobre o par kg/arroba (`_use_arroba()` no web):** é uma preferência de sessão do
  navegador (`st.session_state["unit_pref"]`), não uma configuração do servidor — não existe
  "a unidade certa" para a API devolver. **Esta spec expõe só `arrobas_prod`** (já é o campo
  que `AnimalStats` calcula) — a decisão de qual unidade mostrar (ou se mostra as duas) é da
  spec mobile seguinte, não invente um segundo campo de "ganho em kg" que não existe em
  `AnimalStats`.

## Contrato obrigatório

```
GET /dashboard/resumo
  -> 200: {
       "total_animais": int,
       "peso_medio_kg": float,
       "gmd_medio_kg_dia": float,
       "arrobas_produzidas": float,
       "lotacao_ua_ha": float,
       "machos": int,
       "femeas": int,
       "alertas": {
         "sumidos": int,
         "carencia": int,
         "prontos_para_abate": int
       }
     }
```

- Nomes dos campos **não** são os mesmos atributos Python de `AnimalStats` (`avg_weight` →
  `peso_medio_kg`, etc.) — segue a mesma convenção de nomes em português/com unidade
  explícita que o resto da API já usa (compare com `AlertasOutput`/`DispositivoOutput`).
- `total_area`/`total_kg` de `AnimalStats` **não entram no contrato** — não aparecem nos
  KPIs do topo do web (`_dash_kpis` não os usa), não invente exibição para eles.
- Autenticação igual às outras rotas de leitura (token válido, qualquer papel).

## Critério de aceite

1. `GET /dashboard/resumo` sem token → 401.
2. Fazenda sem nenhum animal cadastrado → 200, todos os campos numéricos zerados (não
   500) — confirme que `AnimalStats()` vazio não quebra a serialização.
3. Fazenda com animais, alguns sumidos/em carência/prontos para abate → 200, os três
   campos de `alertas` batem com `len()` de cada lista que `get_alert_animals()` devolve
   (teste comparando contra uma chamada direta, prova real).
4. `peso_medio_kg`/`gmd_medio_kg_dia`/`arrobas_produzidas`/`lotacao_ua_ha` batem com os
   valores de `get_rebanho_stats()` chamado independentemente no teste com o mesmo estado
   de banco.
5. `flake8`/`ruff` e a suíte inteira de `tests/test_backend_api.py` verde.

## Proibições

- ❌ Não inclua as listas completas de `sumidos`/`carencia`/`prontos` — só contagem. O
  detalhe já existe em `GET /alertas`.
- ❌ Não invente endpoint para os gráficos do dashboard completo (evolução de peso, pizza
  por raça, GMD por animal, conformidade, completude) — fora de escopo desta spec e do
  Tier 2 inteiro (ADR 0007: "o dashboard completo tem gráficos que pedem tela grande").
- ❌ Não recalcule nada fora de `get_rebanho_stats()`/`get_alert_animals()` — são as únicas
  fontes desta spec.
- ❌ Não altere `app.py`, `database.py`, `services/`, `repositories/` nem as specs
  anteriores.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall backend_api tests
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que os 5 critérios têm teste com
prova real — mesmo padrão das specs 0054/0063/0067.
