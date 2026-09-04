# Spec 0073 — API: inventário de estoque e previsão de ruptura

- **Tipo:** implementação · **Risco:** médio (depende de outra spec já ter relocado uma
  função de `app.py` — leia "Pré-requisito" com atenção) · **Esforço:** 1 dia
- **Branch:** `feat/api-estoque-inventario`
- **Altere:** `app.py` (só a relocação descrita abaixo), `database.py`, `backend_api/`
  (`main.py`, `schemas.py`) e os testes correspondentes
- **Pré-requisito obrigatório:** **a spec [0071](0071-api-recomendacoes-motor-de-regras.md)
  precisa estar mesclada em `main`.** Ela já relocaliza `app.py::_consumo_diario_por_insumo`
  para `database.py` — esta spec reaproveita a função relocada, não duplica o trabalho.
  Confirme:
  ```bash
  git fetch origin
  git grep -q "def _consumo_diario_por_insumo" origin/main -- database.py \
    && echo "0071 já mesclada — pode seguir" \
    || echo "0071 AINDA NÃO mesclada — pare e avise quem te instruiu"
  ```

---

## Regra de ouro desta spec

**Zero lógica nova, mesma relocação mecânica da 0071.** `app.py::_previsao_estoque()` monta
exatamente a previsão que `services/previsao_estoque.py::prever` calcula — só que mora em
`app.py`. Esta spec **relocaliza `_previsao_estoque` para `database.py`** (chamando a versão
já relocada de `_consumo_diario_por_insumo`, da spec 0071) e expõe dois endpoints de leitura:
inventário (estoque atual por insumo) e previsão de ruptura. Nenhuma conta nova — tudo já
existe em `_render_tab_inventario`/`_render_tab_previsao_ruptura`
([ADR 0007](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md) Tier 2, primeiro item).

## Objetivo

"Tem insumo suficiente?" é a pergunta mais natural de se fazer olhando o paiol/depósito com
o celular na mão. No web, `page_estoque` responde isso em duas abas (📋 Inventário e 📈
Previsão de Ruptura) — só leitura, mesa é quem ajusta estoque ou compra (ADR 0007 §2.3).
Esta spec cria a API; a spec mobile seguinte (0074) consome.

## Contexto que você precisa

- **Inventário** — `app.py::_render_tab_inventario` (busque `def _render_tab_inventario` em
  `app.py`) monta, por insumo, a partir de `db.get_all_insumos()`:
  `pct = current_stock/min_stock*100 if min_stock else 100`, e
  `status = "critico" if pct<50 else "baixo" if pct<100 else "ok"` (os rótulos em português
  — 🔴/🟡/🟢 — ficam para a spec mobile, mesmo padrão da 0061/0066; aqui é só o identificador
  técnico). `valor_total = current_stock * cost_per_unit`. Isto é **lógica nova a extrair**,
  não uma função pura já existente — copie exatamente essa conta (é aritmética de duas
  linhas, não regra de negócio nova) direto no endpoint ou num helper pequeno em
  `database.py`, à sua escolha, contanto que o resultado bata com o que o web mostra.
- **Previsão de ruptura** — `app.py::_previsao_estoque()` (função sem argumentos): chama
  `db.get_all_insumos()`, `_consumo_diario_por_insumo()` (**já em `database.py` desde a
  0071** — importe/chame de lá), `services/previsao_estoque_adaptador.py::montar_insumos` e
  `services/previsao_estoque.py::prever(montados, date.today().isoformat())`. Relocalize
  esta função para `database.py::previsao_estoque()` (pública, mesmo padrão de
  `contexto_recomendacoes()` da 0071) — mecânico, sem mudar lógica.
- **Em `app.py`:** apague `_previsao_estoque()` e troque a única chamada em
  `_render_tab_previsao_ruptura` para `db.previsao_estoque()`. **Não mude mais nada em
  `app.py`** — nenhuma outra linha da página de estoque muda.
- **`check_low_stock()`** já existe (`database.py`, usada pelo `/alertas` da spec 0063) —
  **não a reaproveite para o inventário completo**: ela só devolve os insumos abaixo do
  mínimo, o inventário desta spec devolve **todos**.

## Contrato obrigatório

```
GET /estoque
  -> 200: [
       { "id": int, "nome": str, "categoria": str, "estoque_atual": float,
         "estoque_minimo": float, "unidade": str, "custo_unitario": float,
         "valor_total": float, "status": "critico" | "baixo" | "ok" }
     ]

GET /estoque/previsao
  -> 200: [
       { "insumo_id": int, "nome": str, "dias_restantes": float | null,
         "data_ruptura": str | null, "comprar_ate": str | null,
         "urgencia": "critica" | "atencao" | "ok" | "sem_dados" }
     ]
```

- `categoria` é o valor técnico da coluna (`racao`, `trato`, `medicamento`, `vacina`,
  `mineral`, `outro`) — **não traduza para português aqui**, mesmo padrão de toda API deste
  projeto (a tradução é hardcoded no cliente, ver spec 0066/0061 sobre `_TIPO_BRINCO`/
  `WEIGH_METHODS`).
- `dias_restantes`/`data_ruptura`/`comprar_ate` vêm `null` quando `services.previsao_estoque`
  devolve "sem dados" (nenhum plano de trato ativo para o insumo) — **não é erro**, repasse
  como está.
- Autenticação igual às outras rotas de leitura (token válido, qualquer papel).

## Critério de aceite

1. `GET /estoque` sem token → 401.
2. `GET /estoque` com insumos em situação crítica, baixa e ok → 200, `status` de cada um
   bate com a mesma conta que `_render_tab_inventario` faz (teste com um insumo em cada
   faixa, confirmando o limiar de 50%/100% do mínimo).
3. `GET /estoque` com `min_stock=0` num insumo → `status` não quebra (mesma regra do web:
   `pct=100` quando não há mínimo cadastrado, vira `"ok"`).
4. `GET /estoque/previsao` sem plano de trato ativo para um insumo → aquele item vem com
   `urgencia: "sem_dados"` e os três campos de data/dias `null`.
5. `GET /estoque/previsao` com plano de trato ativo → valores batem com uma chamada direta
   a `services.previsao_estoque.prever` montada independentemente no teste (prova real).
6. `database.previsao_estoque()` chamada isolada devolve o mesmo formato que
   `services.previsao_estoque.prever` espera — teste direto, sem subir a API.
7. `app.py` não tem mais `_previsao_estoque` definida — só a chamada a
   `db.previsao_estoque()` em `_render_tab_previsao_ruptura`. Rode
   `AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v` (nada quebra) e
   confirme manualmente pelo app web que a aba "📈 Previsão de Ruptura" continua idêntica.
8. `flake8`/`ruff` e a suíte inteira verde.

## Proibições

- ❌ Não altere `services/previsao_estoque.py`, `services/previsao_estoque_adaptador.py`
  nem `database.py::_consumo_diario_por_insumo`/`contexto_recomendacoes` (da spec 0071).
- ❌ Não traduza `categoria`/`status`/`urgencia` para português na API — são valores
  técnicos, tradução é do cliente.
- ❌ Não exponha as abas de escrita de `page_estoque` ("📥 Entrada de Estoque", "➕ Novo
  Insumo", "🛒 Compra com Nota Fiscal") — fora de escopo (ADR 0007 §2.3: Tier 2 é só
  leitura; compra/ajuste de estoque é decisão de mesa).
- ❌ Não mude nada em `app.py` além de apagar `_previsao_estoque` e trocar a chamada.
- ❌ Não altere `app.py`, `database.py`, `services/`, `repositories/` além do descrito, nem
  as specs anteriores.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall app.py database.py backend_api tests
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que os 8 critérios têm teste com
prova real, que partiu de `origin/main` com a 0071 já mesclada, e que a página de estoque
web continua idêntica após a relocação.
