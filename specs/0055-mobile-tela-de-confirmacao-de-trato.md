# Spec 0055 — Mobile: tela de confirmação de trato/nutrição

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2–3 dias
- **Branch:** `feat/mobile-confirmacao-de-trato`
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

**Contrato travado na spec [0054](0054-api-confirmacao-de-trato.md) — não invente
endpoint, payload nem formato de erro diferente do que ela define.** Você não precisa
esperar a 0054 mesclar — teste contra um **servidor mock**, mesmo padrão da
0047/0049/0051/0053.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md) — a última tela do escopo de Mobile v1 online.
Confirmar trato/nutrição de piquete direto do celular: a mesma tela que já existe no web em
**Modo Campo → 🌾 Trato do Dia** (`app.py::_campo_trato`).

## Contexto que você precisa

- **Trato não é por animal, é por piquete.** Diferente de sanidade (0051) e foto (0053),
  que vivem dentro da ficha de UM animal, esta tela é independente da ficha — é uma lista
  de itens de trato agrupados por piquete. Ela precisa do próprio ponto de entrada na
  navegação, não um botão dentro de `AnimalDetailPage`.
- **Ponto de entrada:** um `IconButton` novo no `AppBar` de `AnimalsPage` (a lista de
  animais, tela inicial pós-login), ao lado do `ThemePicker` e do botão de sair — mesmo
  padrão dos `actions` que já existem lá. Ícone sugerido: `Icons.grass` ou
  `Icons.agriculture`. Ao tocar, abre a nova tela (`Navigator.push`, mesmo padrão de
  `_openMovement`/`_openMedication` já usado no app).
- **Indicador de pendências no próprio botão** — um badge pequeno com a contagem de itens
  não confirmados (mesma ideia do `🔴 {n}` no rótulo da aba do web), calculado a partir de
  `GET /trato/pendentes` carregado quando `AnimalsPage` abre. Se a contagem der erro (API
  fora, sem rede), **não trave a lista de animais** — o botão continua acessível sem badge,
  a tela de trato tenta carregar de novo ao abrir.
- **Quantidade aplicada pré-preenchida com a quantidade planejada** (campo `quantidade` do
  item, vindo pronto do servidor) — o operador edita se aplicou uma quantidade diferente.
  **Não calcule nada** a partir disso; é só o valor default de um campo editável.
- **Baixar do estoque só habilitado se o item tiver `insumo_id`** (mesma regra do web:
  `disabled=not p.get("insumo_id")` em `app.py::_campo_trato`) — se `insumo_id` vier
  `null`, o checkbox fica desabilitado (ou simplesmente não aparece), nunca marcável.

## Contrato obrigatório

Contra a API da spec 0054:

```
GET  /trato/pendentes
     -> lista de itens de trato de hoje, cada um com "confirmado_no_periodo" (bool) e
        "ultima_confirmacao" (data ou null)
POST /trato/{plano_id}/confirmar
     body: { "situacao": "feito" | "parcial" | "nao_feito",
              "quantidade_aplicada": float, "baixar_estoque": bool,
              "notas": str | null }
     -> confirma um item
```

Telas/fluxos obrigatórios:

1. **Lista agrupada por piquete** — cabeçalho com o nome/id do piquete, itens do piquete
   embaixo. Itens já confirmados (`confirmado_no_periodo: true`) aparecem marcados
   visualmente (ex.: ícone de check, opacidade reduzida) mas **continuam visíveis**, com a
   data da última confirmação — nunca some da lista.
2. **Contador de pendências no topo** — "N item(ns) pendente(s)" (ou "Tudo confirmado" se
   `N == 0`), mesma ideia do resumo que o web mostra antes da lista de piquetes.
3. **Confirmar um item** — formulário com: situação (feito/parcial/não feito — os três
   valores exatos de `FEEDING_CHECK_STATUS`, não invente um quarto), quantidade aplicada
   (pré-preenchida, editável), baixar do estoque (checkbox condicional — ver "Contexto").
   Confirmar chama `POST` e atualiza a lista **sem recarregar a tela inteira** (mesmo
   padrão de sanidade: só o item confirmado muda de estado, os outros continuam como
   estavam).
4. **Erro de rede não perde o que o operador já digitou** — se o `POST` falhar, o
   formulário do item continua preenchido com os valores que o operador informou, pronto
   para tentar de novo.

## Servidor mock para teste

Estenda o mock já usado pelas specs anteriores, respondendo `GET /trato/pendentes` e
`POST /trato/{plano_id}/confirmar` nos formatos exatos da 0054 — inclua pelo menos dois
piquetes diferentes e pelo menos um item já confirmado desde o início, para provar que a
lista agrupa corretamente e que "já confirmado" renderiza diferente de "pendente".

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo um fluxo completo: abrir a lista de animais → ver o
   badge de pendências → abrir a tela de trato → confirmar um item pendente → item muda
   para "confirmado" na tela, sem recarregar os outros itens (contra o mock).
3. Itens já confirmados (`confirmado_no_periodo: true` vindos do mock) aparecem marcados e
   com a data da última confirmação, sem exigir nenhuma ação do operador.
4. `baixar_estoque` só é marcável quando o item do mock tem `insumo_id` não nulo — teste os
   dois casos (com e sem `insumo_id`) e confirme que o checkbox reflete isso.
5. Erro de rede no `POST` (mock devolvendo erro) mantém os valores do formulário
   preenchidos, não limpa nem perde o que o operador digitou.
6. Testes visuais (golden) cobrem a tela de trato com piquetes pendentes e com tudo
   confirmado, nos três temas. **Gere os PNGs de verdade** —
   `CAPTURE_GOLDENS=1 flutter test test/golden_screens_test.dart --update-goldens` — e
   **commite os arquivos `.png` resultantes em `mobile/test/goldens/`**. Um teste que só
   chama `expect(find.text(...))`/`expect(find.byIcon(...))` sem nenhum `matchesGoldenFile`
   real, ou que roda sem `flutter test` de verdade tendo sido executado, **não cumpre este
   critério** — isso já aconteceu numa spec anterior (0051) e custou uma rodada extra de
   revisão. Se você não tem o toolchain Flutter disponível para gerar os PNGs, **pare e
   reporte isso explicitamente antes de abrir o PR**, não abra a PR alegando o critério
   cumprido sem os arquivos `.png` no diff.
7. `grep -rn "calculate_gmd\|regra de negócio\|fórmula\|período\|periodo" mobile/lib/`
   não acha cálculo de período (diário/semanal/mensal) reimplementado — `confirmado_no_periodo`
   vem pronto do servidor, o app só exibe.

## Proibições

- ❌ Não altere `backend_api/`, `poc/`, `app.py`, `database.py`, `services/`,
  `repositories/`, nem os arquivos das specs anteriores.
- ❌ Não implemente cadastro/edição/exclusão de plano de trato — a 0054 não expõe esses
  endpoints, é tela de administração fora de escopo.
- ❌ Não invente campo, endpoint ou formato de erro que a 0054 não define. Diverge → pare
  e reporte.
- ❌ Não calcule "confirmado no período" no Dart a partir de datas — o campo já vem pronto
  (`confirmado_no_periodo`). Reimplementar a regra de diário/semanal/mensal no app é
  duplicação de lógica de negócio proibida (mesmo veto da 0051 sobre `dose_sugerida`).
- ❌ Não aceite data manual para a confirmação — é sempre "hoje", a API decide, o app não
  manda campo de data no `POST`.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, e diga se testou contra servidor mock ou contra a API real (0054), e se
os golden PNGs foram gerados de verdade (cole a saída do `flutter test --update-goldens`).
