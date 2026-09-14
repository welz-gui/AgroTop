# Spec 0097 — Mobile: AlertsPage mostra qual filtro está ativo e permite ver todos

- **Tipo:** manutenção · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `feat/mobile-alertas-indicador-de-filtro`
- **Altere:** `mobile/lib/screens/alerts_page.dart`, `mobile/test/alerts_page_test.dart`,
  `mobile/test/dashboard_resumo_page_test.dart`, goldens correspondentes
- **Pré-requisito:** [spec 0093](0093-mobile-dashboard-alertas-antes-e-tocaveis.md) (já
  concluída, [PR #407](https://github.com/welz-gui/AgroTop/pull/407))

---

## Objetivo

Complemento apontado na revisão da proposta de redesign
(`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`, seção 7),
**confirmado por leitura direta do código**: quando `AlertsPage` abre com `focusCategoria`
(vindo de um toque no dashboard), o título da `AppBar` continua sempre "Alertas
operacionais" — nada na tela indica que só uma categoria está sendo mostrada, nem existe um
jeito de ver todas as outras sem voltar e reabrir pelo Drawer. Quem chega ali pelo toque pode
achar que é a lista inteira.

## Contexto que você precisa

- **`AlertsPage`** (`alerts_page.dart:7-20`) já tem `focusCategoria` (`AlertCategoria?`,
  spec 0093) e a `AppBar` fixa (`title: const Text('Alertas operacionais')`, linha ~109).
- **`AlertCategoria`** (enum, linha 6) tem três valores: `sumidos`, `carencia`,
  `prontosParaAbate` — mapeie cada um para o mesmo texto já usado nos títulos de seção
  (sem o emoji, que já é decorativo na seção): "Animais Sumidos", "Em Período de Carência",
  "Prontos para Abate".
- **Não crie estado mutável de filtro dentro de `_AlertsPageState`** — "ver todos" deve abrir
  uma nova instância de `AlertsPage` sem `focusCategoria` (mesmo padrão de navegação já usado
  pelo Drawer), não tentar limpar o filtro da página atual in-place.

## Contrato obrigatório

- **Título da `AppBar` dinâmico**: com `focusCategoria != null`, mostra o nome da categoria
  (ex. "Animais Sumidos") em vez de "Alertas operacionais". Sem `focusCategoria` (entrada
  pelo Drawer), título continua "Alertas operacionais", sem mudança.
- **Ação "Ver todos os alertas"** na `AppBar` (`TextButton`/`IconButton` com `tooltip`),
  visível **só quando `focusCategoria != null`**, que navega para uma nova `AlertsPage` sem
  filtro:
  ```dart
  Navigator.of(context).pushReplacement(
    MaterialPageRoute(
      builder: (_) => AlertsPage(api: widget.api, onUnauthorized: widget.onUnauthorized),
    ),
  );
  ```
  (`pushReplacement`, não `push` — "ver todos" substitui a tela filtrada, não empilha por
  cima dela; voltar a partir daí volta pro dashboard, não pra versão filtrada.)

## Critério de aceite

1. Abrir via toque em "Sumidos" no dashboard → `AppBar` mostra "Animais Sumidos", botão "Ver
   todos os alertas" visível.
2. O mesmo para "Em carência" → "Em Período de Carência", e "Prontos para abate" → "Prontos
   para Abate".
3. Tocar "Ver todos os alertas" abre a `AlertsPage` completa (5 categorias + recomendações),
   e voltar a partir dali retorna ao dashboard (não à versão filtrada — confirma
   `pushReplacement`, não `push`).
4. Entrada pelo Drawer (sem `focusCategoria`): título "Alertas operacionais", **sem** o botão
   "Ver todos os alertas" (não faz sentido quando já mostra tudo).
5. Goldens de `alerts_page` regenerados nos três temas, cobrindo pelo menos uma variante
   filtrada.

## Proibições

- ❌ Não crie um `Navigator.pop()` alternativo para "ver todos" — teria que reconstruir o
  dashboard sabendo que precisa mostrar tudo, mais frágil que simplesmente abrir uma
  `AlertsPage` nova sem filtro.
- ❌ Não mude a lógica de quais seções aparecem com `focusCategoria` setado — já correta
  desde a 0093 (só a categoria focada, sem Recomendações/outras seções).
- ❌ Não toque `dashboard_resumo_page.dart` além do necessário para os testes de integração —
  a navegação de lá pra cá já está correta, só o destino (`AlertsPage`) muda visualmente.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
CAPTURE_GOLDENS=1 flutter test --update-goldens
```

## Entrega

PR para `main`, pronto para revisão.
