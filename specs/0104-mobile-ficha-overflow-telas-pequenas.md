# Spec 0104 — Mobile: corrige overflow da ficha em telas pequenas/fonte ampliada

- **Tipo:** correção · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `fix/mobile-ficha-overflow-telas-pequenas`
- **Altere:** `mobile/lib/screens/animals_page.dart`, `mobile/test/flow_test.dart`
  (reativar a asserção estrita)
- **Pré-requisito:** [spec 0096](0096-mobile-ficha-validar-telas-pequenas.md) —
  [PR #417](https://github.com/welz-gui/AgroTop/pull/417) já prova o defeito, não repita a
  investigação, só corrija.

---

## Objetivo

Corrigir dois achados reais que o teste da spec 0096 (`mobile/test/flow_test.dart`, teste
`'ficha em carência mantém ações acessíveis em telas pequenas'`) encontrou no layout que a
spec 0092 introduziu — a spec 0096 foi proibida de corrigir, só documentar; esta spec faz a
correção.

## Contexto que você precisa

- **Achado 1 (definitivo, corrija diretamente)**: a `Row` em
  `animals_page.dart:917-926` (ícone `Icons.pets` + `SizedBox(width: 12)` +
  `Text(animal.id, style: headlineSmall)`, dentro do primeiro `Card` da ficha) não envolve o
  `Text` em `Expanded`/`Flexible` — em escala de texto 2.0 e largura 320/360/390 px, o texto do
  ID do animal estoura horizontalmente (84px/44px/14px de overflow, medido pelo teste da
  0096). Envolva o `Text` em `Expanded` com `overflow: TextOverflow.ellipsis` (ou `Flexible` +
  `softWrap`, à sua escolha — o objetivo é nunca estourar, IDs de animal não costumam ser
  longos então elipse é aceitável).
- **Achado 2 (investigue antes de decidir a correção)**: no teste, em 320×693 px / escala 2.0,
  depois de `tester.ensureVisible(carencia)`, o `Rect` do card de carência
  (`carencia-status-card`, `ListTile` dentro de `Card`, `animals_page.dart:939-976`) tem
  `bottom` 27px além da altura do viewport. **Antes de escrever código**, determine se isso é
  um defeito real ou uma limitação inerente e aceitável de conteúdo alto em tela pequena:
  - Se, mesmo depois de scroll completo até o fim da lista, o **topo** do card também fica
    fora da área visível (ou seja, não há nenhuma posição de scroll em que o conteúdo inteiro
    do card seja alcançável, mesmo em partes através de scroll) — isso é um defeito real:
    considere `dense: true` no `ListTile`, reduzir o `size` do ícone em escalas grandes, ou
    substituir o `ListTile` por um `Column` customizado com paddings menores para caber mais
    em telas pequenas.
  - Se o card, mesmo mais alto que a tela numa única posição, é totalmente alcançável rolando
    (o que é comportamento normal de qualquer item alto num `ListView`) — isso **não é um
    defeito**, é só a asserção do teste da 0096 sendo estrita demais. Neste caso, ajuste a
    asserção (ver Contrato item 3) em vez de mudar o layout de produção.
- **Não toque o resto da ficha** — os três botões de ação, `MetricCard`s, etc. já passam no
  teste da 0096 (só a `Row` do cabeçalho e o card de carência têm achados).

## Contrato obrigatório

1. `Text(animal.id, ...)` na `Row` de `animals_page.dart:917` envolvido em `Expanded` (ou
   `Flexible`) com `overflow: TextOverflow.ellipsis` — zero `RenderFlex overflowed` nas 12
   combinações do teste da 0096.
2. Resolva o achado 2 conforme a investigação acima — corrija o layout OU ajuste o teste,
   documentando no PR qual dos dois cenários foi confirmado e por quê.
3. Em `mobile/test/flow_test.dart`, troque o `print('Achados de layout — ver spec 0104: ...')`
   (adicionado no PR #417 para não bloquear CI) de volta para
   `expect(layoutErrors, isEmpty, reason: ...)` — a spec 0096 preservou o teste exatamente para
   isto: uma vez corrigido, ele deve voltar a falhar se regredir.
4. As 12 combinações (4 larguras × 3 escalas) da spec 0096 passam sem nenhum achado em
   `layoutErrors`.

## Critério de aceite

1. `flutter test test/flow_test.dart` passa com a asserção estrita reativada (item 3 do
   contrato) — sem achados.
2. `flutter analyze` limpo.
3. Nenhum outro golden ou teste existente quebra (rode a suíte completa do mobile).
4. PR documenta a decisão tomada para o achado 2 (corrigido no layout vs. teste ajustado por
   ser scroll normal).

## Proibições

- ❌ Não mude o texto/conteúdo do card de carência ou dos botões — só o layout que os contém.
- ❌ Não amplie escopo para outras telas — só `AnimalDetailPage`/`animals_page.dart`, ficha do
  animal.
- ❌ Não regenere goldens de outras specs sem necessidade — só se a mudança de layout afetar
  algum golden existente da ficha.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test test/flow_test.dart
flutter test
```

## Entrega

PR para `main`, pronto para revisão.
