# Spec 0084 — Mobile: menu de navegação lateral (Drawer) em vez de barra de ícones

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 2-3 dias
- **Branch:** `feat/mobile-menu-lateral`
- **Altere:** `mobile/lib/screens/animals_page.dart`, os testes que hoje tocam
  diretamente nos botões da AppBar (listados abaixo), e os goldens afetados
- **Pré-requisito:** nenhum

---

## Objetivo

Pedido do usuário: aproximar usabilidade e design do mobile do padrão web. Achado
concreto ao investigar: `AnimalsPage` (a tela inicial do app) tem **11 ícones
enfileirados na `AppBar`** sem nenhum rótulo — tema, resumo do dashboard, demarcar
perímetro, novo lote, brincos/dispositivos, estoque, relatórios, alertas, trato do dia,
importar CSV, fila de sincronização, sair. Isso viola a própria regra que
[DESIGN.md](../DESIGN.md) §6 já define pro Modo Campo — "alvo de toque grande", "nada
essencial escondido" — com 11 itens espremidos numa AppBar de celular, o alvo de toque
de cada um fica pequeno e sem rótulo, ao contrário da sidebar do web (`app.py::_sidebar`),
que lista cada seção com ícone **e** nome.

Esta spec substitui essa barra por um **Drawer** (menu lateral), mesma ideia da sidebar
web, sem mudar nenhuma tela de destino nem nenhuma regra de negócio — é reorganização de
navegação, não funcionalidade nova.

## Contexto que você precisa

- **Os 11 alvos de navegação atuais**, todos já funcionais, só precisam trocar de lugar
  (`mobile/lib/screens/animals_page.dart`, dentro do `build()` da `_AnimalsPageState`,
  por volta da linha 359-430):
  - Resumo do dashboard (`_openDashboardResumo`, ícone `dashboard_outlined`)
  - Demarcar perímetro (`_openPerimeterGps`, `location_on_outlined`)
  - Novo lote (`_openCreateLote`, `add_location_alt_outlined`)
  - Brincos e dispositivos (`_openDevices`, `sell_outlined`)
  - Estoque (`_openStock`, `inventory_2_outlined`)
  - Relatórios (`_openReports`, `description_outlined`)
  - Alertas operacionais (`_openAlerts`, com badge de contagem — `_AlertsButton`)
  - Trato do dia (`_openFeeding`, com badge de contagem — `_FeedingButton`)
  - Importar pesagens CSV (`_openCsvImport`, `upload_file_outlined`)
  - Fila offline (`_syncQueue(manual: true)`, com badge de contagem — `_SyncQueueButton`)
  - Sair (`_logout`)
- **Os três botões com badge** (`_AlertsButton`, `_FeedingButton`, `_SyncQueueButton`,
  linhas ~598-750) já implementam o padrão `Stack` + `Positioned` + contador — **reuse a
  mesma lógica de contagem** (`_alertCount`, `_pendingFeedings`, `_pendingQueueCount`),
  só mude o widget visual de ícone-com-badge-sobreposto para
  `ListTile` com um `Badge`/contador no `trailing` (Flutter tem o widget `Badge` nativo
  desde o Material 3, que já está ativo — `useMaterial3: true` em `app_colors.dart`).
- **`ThemePicker`** (`mobile/lib/app.dart`) fica **fora do Drawer**, continua como ação
  na `AppBar` — não faz parte da lista de "pra onde navegar", é controle de exibição da
  tela atual, mesma categoria de coisa em qualquer app.
- **`Scaffold` com `drawer:` definido mostra automaticamente o ícone de hambúrguer** na
  `AppBar` quando não há `leading` customizado — não precisa implementar isso à mão.
- **Chaves de teste (`ValueKey`) usadas fora deste arquivo** — `open-dashboard-resumo`,
  `open-perimeter-gps`, `open-create-lote`, `open-devices`, `open-stock`, `open-reports`,
  `open-alerts`, `open-feeding`, `open-csv-import`, `sync-queue-button` são procuradas
  por `find.byKey(...)` em `mobile/test/dashboard_resumo_page_test.dart`,
  `feeding_page_test.dart`, `flow_test.dart`, `offline_flow_test.dart`,
  `perimeter_gps_page_test.dart`, `reports_page_test.dart`, `stock_page_test.dart`.
  **Mantenha as mesmas chaves nos novos itens do Drawer** — `find.byKey` encontra o
  widget onde quer que ele esteja renderizado, então o teste só precisa de um passo a
  mais antes (abrir o Drawer), não trocar a chave.
- **`mobile/test/golden_screens_test.dart`** — a tela `02-lista.png` (`AnimalsPage`) vai
  mudar visualmente (a `AppBar` fica limpa, sem a fileira de ícones). Regenere os
  goldens dos três temas para este arquivo especificamente
  (`CAPTURE_GOLDENS=1 flutter test --update-goldens`, mesmo processo já documentado nas
  specs mobile anteriores) — não regenere goldens de outras telas sem necessidade.

## Contrato obrigatório

1. **`Scaffold.drawer`** em `AnimalsPage`, com:
   - Cabeçalho (`DrawerHeader` ou equivalente) com a marca "🐄 AgroTop" — mesma ideia do
     topo da sidebar web (`app.py::_sidebar`, linhas ~740-750). **Não** mostre nome/papel
     do usuário logado — o app mobile não guarda essa informação depois de restaurar
     sessão (só existe transitoriamente no retorno do login); adicionar isso é escopo de
     outra spec, não invente.
   - Um `ListTile` por item de navegação, ícone + rótulo (mesmo texto que já está nos
     `tooltip` de hoje: "Resumo", "Demarcar perímetro", "Novo lote", "Brincos e
     dispositivos", "Estoque", "Relatórios", "Alertas operacionais", "Trato do dia",
     "Importar pesagens", "Fila offline").
   - Contagem pendente (alertas, trato, fila) como `trailing` no respectivo `ListTile` —
     mesma condição de exibição de hoje (só aparece quando `count > 0`).
   - "Sair" como último item, com separador visual antes dele (`Divider`).
   - Cada `onTap` fecha o Drawer (`Navigator.pop(context)`) **antes** de navegar pra tela
     de destino — abrir uma segunda tela em cima do Drawer ainda aberto é um erro comum.
2. **`AppBar.actions`** fica só com o `ThemePicker`.
3. **Nenhuma tela de destino muda** — `DashboardResumoPage`, `PerimeterGpsPage`, etc.
   continuam exatamente como estão. Esta spec é só sobre como se chega até elas.

## Critério de aceite

1. Os 11 itens de navegação (mais o `ThemePicker`) continuam **todos** acessíveis e
   levando à tela certa — teste automatizado abrindo o Drawer e navegando por cada um
   (pode reusar a estrutura dos testes já existentes, só adicionando o passo de abrir o
   Drawer antes do `tap`).
2. Os badges de contagem (alertas, trato, fila offline) aparecem só quando `count > 0`,
   mesma regra de hoje — teste com valor zero e com valor positivo pros três.
3. `mobile/test/dashboard_resumo_page_test.dart`, `feeding_page_test.dart`,
   `flow_test.dart`, `offline_flow_test.dart`, `perimeter_gps_page_test.dart`,
   `reports_page_test.dart`, `stock_page_test.dart` continuam passando (ajustados para
   abrir o Drawer antes de tocar no item, sem trocar nenhuma `ValueKey`).
4. Goldens de `02-lista.png` (`dark`/`light`/`system`, os três temas já cobertos pelo
   teste existente) regenerados de verdade — cole no PR a saída do
   `flutter test --update-goldens` confirmando que os três foram escritos.
5. `flutter analyze` limpo.

## Proibições

- ❌ Não mude nenhuma tela de destino (`DashboardResumoPage`, `AlertsPage`, etc.) — só a
  forma de navegar até elas.
- ❌ Não troque nenhuma `ValueKey` existente — quebra os 7 arquivos de teste listados
  acima sem necessidade.
- ❌ Não adicione nome/papel do usuário logado no cabeçalho do Drawer — a informação não
  está disponível de forma persistente hoje; é escopo de outra spec.
- ❌ Não mexa no `ThemePicker` nem no botão de trato/alertas/fila em si (a lógica de
  contagem) — só no widget que os exibe.
- ❌ Não regenere goldens de telas que esta spec não toca.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
CAPTURE_GOLDENS=1 flutter test --update-goldens test/golden_screens_test.dart
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo do PR que os 7 arquivos de teste
que dependiam da AppBar antiga foram ajustados (não reescritos do zero) e que os goldens
de `02-lista.png` foram gerados de verdade nos três temas.
