# Spec 0087 — Mobile: cards de status coloridos (paridade com `.card-red`/`.card-yellow`)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/mobile-cards-status`
- **Altere:** `mobile/lib/screens/alerts_page.dart` e os testes/goldens correspondentes
- **Pré-requisito:** nenhum

---

## Objetivo

Terceiro e último item do pedido de aproximar usabilidade/design do mobile ao padrão
web (depois da spec 0084, navegação, e 0085/0086, gráfico de raça). Achado ao investigar
`mobile/lib/screens/alerts_page.dart` contra `app.py::page_alertas`:

| Seção | Web | Mobile hoje |
|---|---|---|
| 🔴 Animais Sumidos | `.card-red` (borda `perigo`) | `Card` liso, sem cor |
| 🟡 Em Carência | `.card-yellow` (borda `atencao`) | `Card` liso, sem cor |
| 🟢 Prontos para Abate | **sem cor** (tabela simples) | `Card` liso, sem cor — **já bate** |
| 📦 Estoque Abaixo do Mínimo | `.card-yellow` (borda `atencao`) | `Card` liso, sem cor |
| 📉 Baixo Desempenho | **sem cor** (tabela simples) | `Card` liso, sem cor — **já bate** |
| 🧭 Recomendações (motor de regras) | — (só existe no mobile) | `Card` com borda colorida, **mas com hex hardcoded** em vez de `AppColors` |

**Não adicione cor a "Prontos para Abate" nem a "Baixo Desempenho"** — apesar do emoji
verde/vermelho no título de cada seção, o próprio web não usa `.card-*` nelas (são
tabelas simples, `st.dataframe`). Aplicar cor aqui seria o mobile inventando uma
convenção que o web não tem — o oposto do pedido, que é *aproximar* dos dois.

## Contexto que você precisa

- **`_AlertCard`** (`alerts_page.dart`, linha ~254) é hoje `Card` + `ListTile`, sem
  parâmetro de cor. Precisa de um parâmetro opcional `Color? statusColor`.
- **As cinco seções de alerta** (linhas ~130-199) já sabem, por construção, qual cor
  cada uma precisa (é literal no código de qual `_AlertCard` cada uma instancia) —
  passe `AppColors.dark['perigo']`/`['atencao']` (resolvido pelo tema atual, igual ao
  padrão já usado em `_tokenColor` de `dashboard_resumo_page.dart`) só para Sumidos,
  Carência e Estoque Baixo. Prontos e Baixo Desempenho continuam sem `statusColor`
  (default nulo → visual de hoje, sem mudança).
- **`_RecomendacaoCard`** (linha ~314-330) já faz a coisa certa conceitualmente (borda
  colorida por severidade) mas com **hex hardcoded** (`0xFFFBBF24`/`0xFFB45309`) e
  `Theme.of(context).colorScheme.error`/`.primary` em vez de `AppColors` — troque as
  três branches por `AppColors[...]['perigo']`/`['atencao']`/`['sucesso']`, resolvido
  pelo tema atual (mesmo padrão de `_tokenColor`). Isso é uma correção, não mudança de
  comportamento visual esperado — os hex hardcoded já eram aproximadamente as mesmas
  cores, só não vinham da fonte única.
- **Como aplicar a cor no `Card`**: borda colorida (`shape: RoundedRectangleBorder(side:
  BorderSide(color: statusColor, width: 1.5))`), mesmo padrão que `_RecomendacaoCard` já
  usa — não pinte o fundo inteiro do card (o `.card-red` do web usa gradiente sutil de
  fundo + borda; borda sozinha já comunica sem pesar a leitura numa lista longa de
  alertas).

## Contrato obrigatório

```dart
class _AlertCard extends StatelessWidget {
  const _AlertCard({required this.title, required this.subtitle, this.statusColor});
  final String title;
  final String subtitle;
  final Color? statusColor;

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(bottom: 8),
    shape: statusColor == null
        ? null  // usa o CardTheme padrão (borda neutra), sem mudança de hoje
        : RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(color: statusColor!, width: 1.5),
          ),
    child: ListTile(title: Text(title), subtitle: Text(subtitle)),
  );
}
```

- Sumidos → `statusColor` = token `perigo`.
- Carência → `statusColor` = token `atencao`.
- Estoque Abaixo do Mínimo → `statusColor` = token `atencao`.
- Prontos e Baixo Desempenho → sem `statusColor` (omitido, fica `null`).
- `_RecomendacaoCard` → troca os três valores de `_severityColor` para vir de
  `AppColors` (tema atual), não de `colorScheme`/hex literal.

## Critério de aceite

1. Card de "Sumidos" com borda na cor `perigo` do tema atual — teste inspecionando o
   `RoundedRectangleBorder.side.color` do `Card` renderizado.
2. Card de "Carência" e "Estoque Abaixo do Mínimo" com borda `atencao`.
3. Card de "Prontos para Abate" e "Baixo Desempenho" **sem** borda colorida (mesmo
   visual de hoje) — teste confirmando que `shape` é `null`/padrão nesses dois.
4. `_RecomendacaoCard` com severidade alta/media/baixa usa exatamente
   `AppColors.dark['perigo']`/`['atencao']`/`['sucesso']` (ou `light`, conforme o tema
   ativo no teste) — não mais hex literal nem `colorScheme.error`/`.primary`.
5. Goldens de `alerts_page` (dentro de `golden_screens_test.dart` ou suite própria, com
   itens em pelo menos duas das três categorias coloridas) regenerados nos três temas.
6. `flutter analyze` limpo, nenhum hex literal novo introduzido.

## Proibições

- ❌ Não adicione cor às seções "Prontos para Abate" e "Baixo Desempenho" — o web não
  usa `.card-*` nelas, e o objetivo é aproximar, não inventar uma convenção nova.
- ❌ Não pinte o fundo inteiro do card — só a borda, mesmo padrão que `_RecomendacaoCard`
  já estabeleceu e que esta spec estende.
- ❌ Não deixe nenhum hex literal novo no arquivo — tudo via `AppColors`.
- ❌ Não altere a lógica de carregamento de dados, filtros ou ordenação desta tela — só
  o tratamento visual dos cards já existentes.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
CAPTURE_GOLDENS=1 flutter test --update-goldens
grep -n "0xFF" lib/screens/alerts_page.dart   # confirme: nenhuma ocorrência restante
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo do PR que "Prontos para Abate" e
"Baixo Desempenho" continuam sem cor (comparando print/golden antes×depois), e que o
`grep` de hex literal não encontrou nada.
