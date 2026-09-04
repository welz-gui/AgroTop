# Spec 0076 — Mobile: resumo do dashboard

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/mobile-dashboard-resumo`
- **Altere:** `mobile/` (a pasta que a spec 0047 criou)
- **Pré-requisito obrigatório:** **a spec [0047](0047-mobile-v1a-login-animais-e-pesagem.md)
  precisa estar mesclada em `main`.** Confirme:
  ```bash
  git fetch origin
  git cat-file -e origin/main:mobile/lib/app.dart 2>/dev/null \
    && echo "0047 já mesclada — pode seguir" \
    || echo "0047 AINDA NÃO mesclada — pare e avise quem te instruiu"
  ```

---

## Regra de ouro desta spec

**Contrato travado na spec [0075](0075-api-dashboard-resumo.md) — não invente campo nem
gráfico diferente do que ela define.** Você não precisa esperar a 0075 mesclar — teste
contra um **servidor mock**, mesmo padrão de toda spec mobile. **Esta tela é só números,
sem gráfico nenhum** — o dashboard completo (com gráficos) fica só no web, de propósito
([ADR 0007](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md) §2.3). Não tente
recriar `_dash_chart_evolucao_peso`/`_dash_chart_por_raca`/`_dash_chart_gmd` — não é o
escopo, e não há biblioteca de gráficos no `pubspec.yaml` para isso hoje.

## Objetivo

Terceira spec do Tier 2 da ADR 0007. "Visão geral rápida tem valor no bolso" — um punhado
de números que respondem "como está o rebanho hoje", sem precisar abrir o navegador. Esta
spec traz o resumo pro mobile, contra a API da 0075.

## Contexto que você precisa

- **Ponto de entrada:** um `IconButton` novo no `AppBar` de `AnimalsPage` — ícone sugerido
  `Icons.dashboard_outlined`, tooltip "Resumo", sem badge.
- **Layout simples:** uma grade ou coluna de cartões (`Card`/`GridView`), um por KPI —
  mesmo espírito visual dos `st.metric` do web, sem precisar ser pixel-igual. Sete números:
  total de animais, peso médio, GMD médio, arrobas produzidas, lotação (UA/ha), machos,
  fêmeas.
- **Seção de alertas resumidos** abaixo dos KPIs — três números com indicador de cor (mesmo
  espírito dos cartões vermelho/amarelo/verde do web): sumidos, em carência, prontos para
  abate. **Sem lista de itens** — só contagem; se o operador quiser o detalhe, a tela de
  alertas (spec 0064) já existe e tem o "abrir" natural a partir daqui **não é obrigatório**
  (pode adicionar um botão "Ver alertas" navegando para `AlertsPage` se fizer sentido no
  layout, mas não é critério de aceite).
- **Fazenda sem nenhum animal:** mostre uma mensagem equivalente ao
  `"Nenhum animal cadastrado..."` do web em vez de uma tela de zeros sem contexto (mesmo
  princípio de toda spec anterior: nada vazio sem explicação).
- **Pull-to-refresh** — `RefreshIndicator`, mesmo padrão já usado nas outras telas.

## Contrato obrigatório

Contra a API da spec 0075:

```
GET /dashboard/resumo
  -> { "total_animais": int, "peso_medio_kg": float, "gmd_medio_kg_dia": float,
        "arrobas_produzidas": float, "lotacao_ua_ha": float, "machos": int,
        "femeas": int,
        "alertas": { "sumidos": int, "carencia": int, "prontos_para_abate": int } }
```

Ver a spec 0075 para os detalhes de cada campo.

## Servidor mock para teste

Estenda o mock já usado pelas specs anteriores, respondendo `GET /dashboard/resumo` no
formato exato da 0075 — inclua um cenário com `total_animais: 0` (todos os outros campos
zerados) e outro com dados reais nos 7 KPIs e nos 3 alertas.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo: abrir a tela de resumo a partir de `AnimalsPage` → os 7
   KPIs e os 3 números de alerta aparecem com os valores do mock.
3. `total_animais: 0` mostra a mensagem de "nenhum animal", não uma grade de zeros.
4. Pull-to-refresh recarrega os dados (mock devolvendo cenário diferente na segunda
   chamada, tela reflete a mudança).
5. Testes visuais (golden) cobrem a tela vazia (sem animal) e com dados nos três temas.
   **Gere os PNGs de verdade** — `flutter test test/golden_screens_test.dart
   --update-goldens` — e **commite os `.png` resultantes em `mobile/test/goldens/`**. Se
   não tiver o toolchain Flutter disponível, **pare e reporte isso explicitamente antes de
   abrir o PR**.

## Proibições

- ❌ Não altere `backend_api/`, `app.py`, `database.py`, `services/`, `repositories/`, nem
  os arquivos das specs anteriores.
- ❌ Não implemente nenhum gráfico (evolução de peso, pizza por raça, GMD por animal) — o
  dashboard completo fica só no web, de propósito (ADR 0007 §2.3).
- ❌ Não implemente conformidade nem completude de dados — não fazem parte do "resumo",
  são seções separadas do dashboard completo (`_dash_conformidade`/`_dash_completude`),
  fora de escopo desta spec.
- ❌ Não adicione biblioteca de gráficos nova ao `pubspec.yaml` — esta spec não precisa,
  não invente necessidade.
- ❌ Não mostre a lista de animais sumidos/em carência/prontos — só contagem (a lista já
  existe na tela de alertas, spec 0064).

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, se testou contra servidor mock ou contra a API real (0075), e se os
golden PNGs foram gerados de verdade (cole a saída do `flutter test --update-goldens`).
