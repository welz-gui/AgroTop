# Spec 0096 — Mobile: validar ações da ficha em telas pequenas e fonte ampliada

- **Tipo:** teste · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `test/mobile-ficha-telas-pequenas`
- **Altere:** `mobile/test/flow_test.dart` (novo teste) ou arquivo de teste próprio, sem
  tocar `mobile/lib/`
- **Pré-requisito:** [spec 0092](0092-mobile-acoes-da-ficha-no-topo.md) (já concluída,
  [PR #408](https://github.com/welz-gui/AgroTop/pull/408))

---

## Objetivo

Complemento apontado na revisão da proposta de redesign
(`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`, seção 6): a 0092
promoveu os botões de ação da ficha para logo após o card de carência, mas só foi verificada
nos três temas com o tamanho de tela padrão dos testes (390×844). Não há prova de que os
botões continuam acessíveis — sem serem forçados a caber encobrindo um aviso de carência
longo — em telas pequenas de verdade ou com fonte ampliada de acessibilidade.

## Contexto que você precisa

- Esta spec **não muda layout nenhum** — só adiciona cobertura de teste que hoje não existe.
  Se o teste encontrar um problema real (corte de texto, botão inacessível, sobreposição),
  **pare e relate no PR em vez de corrigir** — uma correção de layout pertence a uma spec à
  parte (ver 0104/RD10 na proposta original, que trata largura de métricas e redução de
  repetição — mas não é sobre isto).
- Larguras de referência já usadas noutras pro“provas” de tamanho no projeto: 320, 360, 390,
  430 px (celulares reais pequeno/médio/grande) — use o mesmo conjunto.
- Escala de texto do sistema: `MediaQuery(textScaler: TextScaler.linear(x))` envolvendo o
  `MaterialApp` de teste é o padrão Flutter para simular fonte ampliada — não precisa mexer em
  configuração do aparelho.
- `AnimalDetailPage` já expõe os `ValueKey`s dos três botões (`open-weighing`,
  `open-medication`, `open-movement`) e do card de carência
  (`carencia-status-card`) — use-os para localizar e verificar sobreposição/visibilidade.

## Contrato obrigatório

Novo teste (ou grupo de testes) que, para cada combinação de:
- largura: 320, 360, 390, 430 px (altura proporcional, ex. 320×693, 844 fixo para as demais)
- escala de texto: 1.0, 1.3, 2.0

1. Monta a ficha com um animal **em carência** (texto de aviso mais longo que o caso comum).
2. Confirma que os três botões de ação (`open-weighing`/`open-medication`/`open-movement`)
   estão presentes na árvore (`findsOneWidget`), sem `Overflow`/erro de layout no console de
   teste (`tester.takeException()` deve ser `null` depois de `pumpAndSettle`).
3. Confirma que o card de carência (`carencia-status-card`) continua totalmente visível (sem
   corte) mesmo se isso empurrar os botões mais abaixo — nenhuma seção pode se sobrepor à
   outra.

## Critério de aceite

1. Todas as 12 combinações (4 larguras × 3 escalas) passam sem exceção de layout.
2. Se qualquer combinação falhar, o PR **não corrige** — documenta o achado (largura/escala,
   o que quebrou, captura se possível) e propõe a spec de correção separada.
3. `flutter analyze` limpo.

## Proibições

- ❌ Não altere `mobile/lib/screens/animals_page.dart` nem qualquer outro arquivo de
  produção — esta spec é só teste.
- ❌ Não regenere goldens — não é sobre aparência pixel-perfeita, é sobre não haver erro de
  layout/overflow.
- ❌ Não amplie o escopo para outras telas (dashboard, alertas) — só a ficha do animal.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test test/flow_test.dart
```

## Entrega

PR para `main`, pronto para revisão. Se algo quebrar em alguma combinação, o PR deve conter
o teste que prova o problema (mesmo falhando, ou marcado como achado) e uma recomendação
clara de próxima spec — não uma correção improvisada.
