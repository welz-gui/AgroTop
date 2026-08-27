# Spec 0062 — Mobile: confirmação rápida de trato (baixa de estoque por padrão)

- **Tipo:** ajuste de UX · **Risco:** baixo · **Esforço:** algumas horas
- **Branch:** `feat/mobile-trato-confirmacao-rapida`
- **Altere:** só `mobile/lib/screens/feeding_page.dart` (e o teste correspondente)
- **Pré-requisito:** nenhum — a spec 0055 (tela de trato) já está em `main`.

---

## Regra de ouro desta spec

**Não mude o contrato da API** (spec 0054) — `baixar_estoque` continua um `bool` no
`POST /trato/{plano_id}/confirmar`. A mudança é só o **default** e a **fricção da tela**,
alinhando o mobile ao comportamento que **o app web já tem** — não é feature nova, é
consistência entre as duas interfaces.

## Objetivo

Achado testando o app de verdade (2026-08-26): confirmar um trato no mobile pede 4 decisões
(situação, quantidade, baixar estoque, observações) quando o caso comum é só "sim, foi feito
como planejado, baixa do estoque normalmente". O app web (`app.py::_campo_trato`) já resolve
isso: o checkbox de baixar estoque vem **marcado por padrão** quando o item tem `insumo_id`
(`value=bool(p.get("insumo_id"))`) — o mobile hoje faz o oposto (`_deductStock = false`,
desmarcado por padrão), forçando o operador a marcar toda vez.

## Contexto que você precisa

- **Arquivo:** `mobile/lib/screens/feeding_page.dart`, classe
  `_FeedingConfirmationSheetState`. O campo `var _deductStock = false;` é o bug de
  consistência — troque para nascer marcado quando o item tem `insumo_id` (mesma regra já
  usada para decidir se o checkbox aparece: `widget.feeding.insumoId != null`).
- **Confirmação de um toque para o caso comum**: hoje, confirmar exige abrir a folha
  (`_FeedingConfirmationSheet`), digitar comentar, escolher situação (já vem `'feito'` por
  padrão) e tocar em "Confirmar trato". Adicione uma ação rápida **na própria linha do item
  pendente** na lista (`FeedingPage`) — um botão/ícone de check que confirma direto com os
  valores padrão (`situacao: 'feito'`, `quantidade_aplicada: quantidade planejada`,
  `baixar_estoque: insumoId != null`, sem observações), **sem abrir a folha**. Tocar no
  corpo do item (fora do botão rápido) continua abrindo a folha detalhada, para os casos de
  "parcial", "não feito" ou quantidade diferente da planejada.
- **Não remova a folha detalhada** — ela continua necessária para os casos que não são o
  caminho feliz. Você está adicionando um atalho, não substituindo o fluxo existente.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo um teste novo: tocar o botão de confirmação rápida num
   item com `insumo_id` não nulo dispara `POST` com `baixar_estoque: true` **sem abrir a
   folha** — confirme lendo o corpo da requisição no mock.
3. Abrir a folha detalhada (toque no corpo do item) num item com `insumo_id` não nulo
   mostra o checkbox de baixar estoque **já marcado** (era desmarcado antes desta spec).
4. Item sem `insumo_id`: nem o atalho rápido nem a folha marcam/enviam baixa de estoque —
   comportamento inalterado (checkbox continua não aparecendo/desabilitado).
5. Confirmação rápida num item que já está `confirmado_no_periodo: true` não é possível
   (não deve haver botão de atalho em item já confirmado — mesma regra visual que já existe
   hoje para itens confirmados).
6. Golden tests da tela de trato (`dark/light/system-11-trato-pendentes.png` e
   `...-12-trato-confirmado.png`, da spec 0055) **atualizados** se o novo botão de atalho
   mudar visualmente a linha do item pendente — gere os PNGs de verdade
   (`flutter test --update-goldens`). Se não tiver Flutter disponível, **pare e reporte
   antes de abrir o PR**, não alegue o critério cumprido sem os `.png` no diff.

## Proibições

- ❌ Não altere `backend_api/`, `app.py`, `database.py` nem nenhum arquivo fora de
  `mobile/`.
- ❌ Não remova a folha detalhada (`_FeedingConfirmationSheet`) — ela continua o caminho
  para situação ≠ "feito" ou quantidade diferente da planejada.
- ❌ Não invente um quarto valor de `situacao` nem mude o formato do `POST` além do default
  do checkbox.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
```

## Entrega

PR para `main`, pronto para revisão. Diff esperado: `feeding_page.dart`,
`feeding_page_test.dart`, `golden_screens_test.dart` (se necessário) e os PNGs de trato
atualizados (se mudarem visualmente).
