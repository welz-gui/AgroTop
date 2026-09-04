# Spec 0074 — Mobile: tela de estoque (inventário e previsão de ruptura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2 dias
- **Branch:** `feat/mobile-estoque`
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

**Contrato travado na spec [0073](0073-api-estoque-inventario-e-previsao.md) — não invente
endpoint nem campo diferente do que ela define.** Você não precisa esperar a 0073 mesclar —
teste contra um **servidor mock**, mesmo padrão de toda spec mobile. **Esta tela é só
leitura** ([ADR 0007](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md) Tier 2) —
nenhuma ação de escrita, é puramente consulta ("tenho insumo suficiente?").

## Objetivo

Primeira spec mobile do Tier 2 da ADR 0007. No web, `page_estoque` responde "tem insumo
suficiente?" — pergunta natural com o celular no paiol. Esta spec traz a mesma resposta pro
mobile, contra a API da 0073: duas seções (ou abas), inventário atual e previsão de ruptura.

## Contexto que você precisa

- **Ponto de entrada:** um `IconButton` novo no `AppBar` de `AnimalsPage`, mesmo padrão dos
  botões já existentes — ícone sugerido `Icons.inventory_2_outlined`, tooltip "Estoque", sem
  badge (a contagem de itens críticos já existe em `AlertsPage` via `/alertas`, não duplique
  aqui).
- **Duas abas (`TabBar`/`TabBarView`)**: "📋 Inventário" e "📈 Previsão de Ruptura" — mesmos
  nomes/emoji do web, mesma ordem.
- **Aba Inventário:** lista de insumos, cada item mostrando nome, categoria (traduzida —
  ver "Rótulos fixos" abaixo), estoque atual + unidade, mínimo, e um indicador visual de
  `status` (cor/ícone por `critico`/`baixo`/`ok`, mesmo espírito do 🔴/🟡/🟢 do web). Mostre
  também o valor total do insumo (`valor_total`) — não precisa somar um total geral na tela
  se isso complicar o layout, é opcional.
- **Aba Previsão:** lista de insumos com `dias_restantes`, `data_ruptura`, `comprar_ate` e
  `urgencia` — item com `urgencia: "sem_dados"` mostra "Sem plano de trato ativo" em vez de
  datas vazias sem contexto (mesmo princípio do critério 3 da 0064: nada vazio sem
  explicação).
- **Filtro por categoria (opcional, mas recomendado)** — mesmo padrão do
  `st.selectbox("Filtrar por categoria")` do web, se der para encaixar sem complicar o
  layout; **não é bloqueante** para o critério de aceite se ficar de fora.
- **Rótulos fixos** — mesmo padrão da spec 0066 (`_TIPO_BRINCO`)/0061 (`WEIGH_METHODS`): as
  seis categorias e seus rótulos em português vêm de `app.py::_render_tab_inventario`
  (`CAT_LABELS`), hardcode no Dart:
  ```python
  CAT_LABELS = {"racao": "Ração", "trato": "Trato (volumoso)",
                "medicamento": "Medicamento", "vacina": "Vacina",
                "mineral": "Mineral", "outro": "Outro"}
  ```
  `status` (`critico`/`baixo`/`ok`) e `urgencia` (`critica`/`atencao`/`ok`/`sem_dados`) têm
  rótulo livre à sua escolha (o web usa "🔴 Crítico"/"🟡 Baixo"/"🟢 OK" e "🔴 Crítica"/"🟡
  Atenção"/"🟢 OK"/"⚪ Sem dados" — reaproveite o tom, não precisa ser idêntico).
- **Pull-to-refresh** — `RefreshIndicator` recarregando as duas listas, mesmo padrão já
  usado em `AlertsPage`/`AnimalsPage`.

## Contrato obrigatório

Contra a API da spec 0073:

```
GET /estoque
  -> [ { "id": int, "nome": str, "categoria": str, "estoque_atual": float,
          "estoque_minimo": float, "unidade": str, "custo_unitario": float,
          "valor_total": float, "status": "critico"|"baixo"|"ok" } ]

GET /estoque/previsao
  -> [ { "insumo_id": int, "nome": str, "dias_restantes": float|null,
          "data_ruptura": str|null, "comprar_ate": str|null,
          "urgencia": "critica"|"atencao"|"ok"|"sem_dados" } ]
```

Ver a spec 0073 para os detalhes de cada campo.

## Servidor mock para teste

Estenda o mock já usado pelas specs anteriores, respondendo `GET /estoque` e
`GET /estoque/previsao` no formato exato da 0073 — inclua cenários com insumos nas três
faixas de `status`, e na previsão pelo menos um item `sem_dados` e um `critica`.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo: abrir a tela de estoque a partir de `AnimalsPage` →
   aba Inventário mostra os insumos do mock com o `status` correto → trocar para a aba
   Previsão → mostra os dados da previsão, incluindo o item `sem_dados`.
3. Item com `urgencia: "sem_dados"` mostra a mensagem explicativa, não datas vazias.
4. Pull-to-refresh recarrega as duas abas (mock devolvendo cenário diferente na segunda
   chamada).
5. Testes visuais (golden) cobrem a aba Inventário e a aba Previsão, cada uma com itens nas
   diferentes faixas de status/urgência, nos três temas. **Gere os PNGs de verdade** —
   `flutter test test/golden_screens_test.dart --update-goldens` — e **commite os `.png`
   resultantes em `mobile/test/goldens/`**. Se não tiver o toolchain Flutter disponível,
   **pare e reporte isso explicitamente antes de abrir o PR**.
6. `grep -rniE "min_stock|critico.*baixo.*ok|50%|100%" mobile/lib/` não acha o limiar de
   status (50%/100% do mínimo) reimplementado — o app só exibe o `status` que a API já
   calculou.

## Proibições

- ❌ Não altere `backend_api/`, `app.py`, `database.py`, `services/`, `repositories/`, nem
  os arquivos das specs anteriores.
- ❌ Não implemente "Entrada de Estoque", "Novo Insumo" nem "Compra com Nota Fiscal" — são
  ações de escrita, fora de escopo do Tier 2 (ADR 0007 §2.3).
- ❌ Não recalcule `status` nem `urgencia` no Dart — vêm prontos do servidor.
- ❌ Não invente gráfico (o web tem um gráfico de barras "% do Mínimo" na aba Inventário) —
  não é obrigatório para o critério de aceite; se quiser incluir um resumo visual simples,
  fique à vontade, mas a lista com indicador de status já cumpre o critério.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, se testou contra servidor mock ou contra a API real (0073), e se os
golden PNGs foram gerados de verdade (cole a saída do `flutter test --update-goldens`).
