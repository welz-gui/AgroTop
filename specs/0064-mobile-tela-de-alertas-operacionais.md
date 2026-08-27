# Spec 0064 — Mobile: tela de alertas operacionais

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2 dias
- **Branch:** `feat/mobile-alertas-operacionais`
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

**Contrato travado na spec [0063](0063-api-alertas-operacionais.md) — não invente
endpoint, campo nem categoria diferente do que ela define.** Você não precisa esperar a
0063 mesclar — teste contra um **servidor mock**, mesmo padrão da 0047/0049/0051/0053/0055.
**Esta tela é só leitura** — nenhuma das 5 categorias tem ação de escrita, é puramente
consulta ("o que eu preciso fazer hoje").

## Objetivo

Primeira spec mobile do Tier 1 da [ADR 0007](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md).
No web, `page_alertas` (aba "🔔 Operacionais") responde "o que eu preciso fazer hoje" — a
pergunta mais natural de se fazer com o celular no curral. Esta spec traz a mesma resposta
pro mobile, contra a API da 0063.

## Contexto que você precisa

- **Ponto de entrada:** um `IconButton` novo no `AppBar` de `AnimalsPage`, mesmo padrão do
  botão de trato (0055) — ícone sugerido `Icons.notifications_outlined`, com badge de
  contagem (soma dos itens das 5 categorias) carregado quando `AnimalsPage` abre. Se a
  contagem der erro (API fora, sem rede), **não trave a lista de animais** — o botão
  continua acessível sem badge.
- **Cinco seções, uma por categoria**, cada uma com cabeçalho mostrando a contagem
  (`"🔴 Animais Sumidos (N)"`, mesmo texto/emoji do web) e mensagem de sucesso quando vazia
  (`"✅ Nenhum animal sumido."`, etc. — reaproveite o tom do web, não precisa ser
  caractere-por-caractere igual).
- **Sem ação nenhuma nos itens** — nem os botões "Ir para Campo/Estoque/Desempenho" do web
  (são atalhos de navegação do Streamlit, não fazem sentido aqui: o operador já está no
  mobile, "ir pra tela de estoque" não existe como conceito nesta spec).
- **"Recomendações" (motor de regras) não está nesta spec** — a 0063 não expõe isso, não
  invente uma seção pra ela.
- **Pull-to-refresh** — `RefreshIndicator` recarregando `GET /alertas`, mesmo padrão já
  usado em `AnimalsPage`.

## Contrato obrigatório

Contra a API da spec 0063:

```
GET /alertas
  -> { "sumidos": [...], "carencia": [...], "prontos_para_abate": [...],
        "estoque_baixo": [...], "baixo_desempenho": [...] }
```

Ver a spec 0063 para os campos exatos de cada item da lista.

## Servidor mock para teste

Estenda o mock já usado pelas specs anteriores, respondendo `GET /alertas` no formato
exato da 0063 — inclua ao menos um cenário com todas as categorias vazias (tela toda de
sucesso) e outro com pelo menos um item em cada uma das 5 categorias.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo: abrir a lista de animais → ver o badge com a contagem
   total → abrir a tela de alertas → as 5 seções aparecem com os itens do mock.
3. Categoria vazia mostra a mensagem de sucesso, não uma lista vazia sem contexto.
4. Pull-to-refresh recarrega os dados (mock devolvendo um cenário diferente na segunda
   chamada, tela reflete a mudança).
5. Badge não aparece (ou mostra vazio) se `GET /alertas` falhar ao carregar `AnimalsPage` —
   a lista de animais continua funcional, o botão de alertas continua acessível.
6. Testes visuais (golden) cobrem a tela de alertas com todas categorias vazias e com
   itens em todas, nos três temas. **Gere os PNGs de verdade** —
   `flutter test test/golden_screens_test.dart --update-goldens` — e **commite os arquivos
   `.png` resultantes em `mobile/test/goldens/`**. Um teste que só chama
   `expect(find.text(...))` sem `matchesGoldenFile` real não cumpre este critério — já
   aconteceu numa spec anterior (0051) e custou uma rodada extra de revisão. Se não tiver o
   toolchain Flutter disponível, **pare e reporte isso explicitamente antes de abrir o
   PR**, não abra alegando o critério cumprido sem os `.png` no diff.
7. `grep -rn "gmd_meta\|meta.*gmd\|30.*dias\|min_stock" mobile/lib/` não acha limiar/regra
   reimplementado — todo número (30 dias, meta de GMD, mínimo de estoque) já vem pronto do
   servidor, o app só exibe.

## Proibições

- ❌ Não altere `backend_api/`, `app.py`, `database.py`, `services/`, `repositories/`, nem
  os arquivos das specs anteriores.
- ❌ Não implemente "Recomendações" — a 0063 não expõe, fora de escopo.
- ❌ Não adicione botões de ação nos itens (nenhuma categoria tem escrita) nem atalhos de
  navegação tipo "Ir para X" — não existem no mobile.
- ❌ Não recalcule nenhum limiar (30 dias de "sumido", meta de GMD, mínimo de estoque) —
  são todos calculados no servidor.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, se testou contra servidor mock ou contra a API real (0063), e se os
golden PNGs foram gerados de verdade (cole a saída do `flutter test --update-goldens`).
