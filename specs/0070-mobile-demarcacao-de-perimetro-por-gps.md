# Spec 0070 — Mobile: demarcação de perímetro por GPS

- **Tipo:** implementação · **Risco:** médio (permissão de localização, hardware
  real de GPS) · **Esforço:** 2 dias
- **Branch:** `feat/mobile-perimetro-gps`
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

**Contrato travado na spec [0069](0069-api-perimetro-do-piquete-por-pontos.md) — não
invente endpoint nem campo diferente do que ela define.** Você não precisa esperar a
0069 mesclar — teste contra um **servidor mock**, mesmo padrão da
0047/0049/0051/0053/0055/0064/0066. **O app só coleta pontos e envia — nenhum
cálculo de área, perímetro ou validação de polígono acontece no cliente**, tudo isso
é do servidor (mesma regra de toda spec mobile deste projeto).

## Objetivo

Último item da Trilha 2 (ROADMAP §5, item 4): **demarcação por GPS caminhando o
perímetro**. O operador escolhe um piquete, caminha até cada canto da cerca e marca
um ponto — ao fechar, o app envia a lista de pontos pra API da 0069, que valida,
calcula a área de verdade e grava.

**Por que "marcar ponto a ponto" e não "gravar o caminho inteiro andando":** GPS de
celular tem erro de alguns metros, e andar ao longo de uma cerca reta produziria um
rastro serrilhado, não uma linha reta — pior que a área digitada que já existe hoje.
Marcar manualmente em cada canto (parar, apertar o botão) é o que apps de campo
profissionais fazem, e evita todo o problema de simplificar um rastro ruidoso depois.
**Não implemente rastreamento contínuo em segundo plano** — é escopo maior
(bateria, permissão de localização em segundo plano, simplificação de traço) que
esta spec não pede.

## Contexto que você precisa

- **Ponto de entrada:** um `IconButton` novo no `AppBar` de `AnimalsPage`, mesmo
  padrão dos botões já existentes (trato, alertas, brincos, criar lote) — ícone
  sugerido `Icons.location_on_outlined` ("Demarcar perímetro"), sem badge.
- **Escolher o piquete primeiro** — não existe tela de "lista de piquetes" no
  mobile ainda; reaproveite `ApiClient.listLotes()` (já existe, devolve
  `List<LoteSummary>`, usado em `movement_page.dart` como referência de padrão) num
  dropdown/seleção simples antes de abrir o mapa de marcação.
- **Marcar pontos:**
  - Botão "📍 Marcar vértice aqui" — lê a posição GPS atual **uma vez** por toque
    (não um stream contínuo) e adiciona à lista de vértices.
  - Mostra a contagem de pontos marcados e, a partir do 3º ponto, um preview do
    polígono (uma linha ligando os pontos já marcados é suficiente — não precisa
    de mapa completo com tiles, mas se usar `flutter_map`/similar por conveniência
    de exibição, tudo bem; **não é obrigatório mostrar mapa de fundo**, uma lista
    de coordenadas com um desenho simples do polígono já cumpre o critério).
  - Botão "↩️ Desfazer último ponto" — remove o último vértice marcado (dedo
    grosso, GPS ruim naquele instante, etc.).
  - Botão "🔄 Recomeçar" — limpa todos os pontos.
- **Permissão de localização:** solicite a permissão (`ACCESS_FINE_LOCATION`) na
  hora de abrir a tela, não no `AppDelegate`/inicialização do app. Três estados a
  tratar:
  1. Concedida → segue normal.
  2. Negada (o operador pode tentar de novo) → mensagem explicando por que a
     permissão é necessária, com botão para pedir de novo.
  3. Negada permanentemente ("não perguntar de novo") → mensagem indicando que é
     preciso liberar manualmente nas configurações do Android (não precisa abrir
     as configurações automaticamente, só orientar).
- **Dependência nova:** este projeto não tem pacote de geolocalização ainda —
  adicione `geolocator` (ou equivalente) ao `pubspec.yaml`, mesmo padrão de quando
  a spec 0056 (leitura de QR) adicionou `mobile_scanner`: é uma dependência que a
  funcionalidade genuinamente exige, não invenção.
- **`AndroidManifest.xml`** precisa da permissão de localização — hoje só declara
  `INTERNET` e `CAMERA` (`mobile/android/app/src/main/AndroidManifest.xml`).
  Adicione `android.permission.ACCESS_FINE_LOCATION` (e `ACCESS_COARSE_LOCATION`
  como fallback, padrão do `geolocator`).
- **Enviar e confirmar:** com 3+ pontos marcados, botão "💾 Salvar perímetro" chama
  `POST /lotes/{id}/perimetro`. Sucesso mostra a área calculada (`area_ha` da
  resposta) e volta pra tela anterior. Erro 422 (polígono inválido) mostra a(s)
  mensagem(ns) que o servidor devolveu, **sem** fechar a tela — o operador pode
  desfazer/remarcar pontos e tentar de novo.

## Contrato obrigatório

Contra a API da spec 0069:

```
POST /lotes/{lote_id}/perimetro
  body: { "pontos": [[lon, lat], [lon, lat], [lon, lat], ...] }
  -> 200: { "ok": true, "area_ha": float, "perimetro_m": float }
  -> 404: piquete não encontrado
  -> 422: polígono inválido (detail = lista de mensagens)
```

`pontos` é `[longitude, latitude]` por item — mesma ordem de todo o resto do
projeto. `Geolocator.getCurrentPosition()` (ou equivalente) devolve
latitude/longitude separados — **inverta a ordem ao montar o par**, é o erro mais
fácil de cometer aqui.

## Servidor mock para teste

Estenda o mock já usado pelas specs anteriores: `GET /lotes` (já existe, reuse o
mock existente de `movement_page`) e `POST /lotes/{id}/perimetro` no formato exato
da 0069 — inclua um cenário de sucesso (200 com área) e um de polígono inválido
(422, mock devolvendo a mensagem de erro).

**GPS em teste automatizado:** `flutter test` não tem acesso a hardware de
localização real. Abstraia a leitura de posição atrás de uma interface simples
(ex. `Future<Point> Function()` injetável no widget/estado, mesmo espírito de como
`ApiClient` já é injetado nas telas) para que o teste possa fornecer coordenadas
fixas sem depender do `geolocator` de verdade.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo: escolher um piquete → marcar 4 pontos (mock de
   posição) → preview mostra 4 vértices → salvar → `POST` recebido com os 4 pontos
   na ordem certa → sucesso mostra a área devolvida pelo mock.
3. "Desfazer último ponto" remove exatamente o último, não todos.
4. Botão "Salvar" desabilitado com menos de 3 pontos.
5. Erro 422 do mock mantém os pontos marcados na tela (não reseta o progresso).
6. Permissão negada mostra mensagem clara e não trava o resto do app (o operador
   consegue voltar e usar as outras telas normalmente).
7. Testes visuais (golden) cobrem: nenhum ponto marcado, com pontos marcados
   (preview), e o erro de polígono inválido — nos três temas. **Gere os PNGs de
   verdade** — `flutter test test/golden_screens_test.dart --update-goldens` — e
   **commite os `.png` resultantes em `mobile/test/goldens/`**. Se não tiver o
   toolchain Flutter disponível, **pare e reporte isso explicitamente antes de
   abrir o PR**.
8. `grep -rn "shoelace\|area_hectares\|calcular.*area\|centroide" mobile/lib/` não
   acha cálculo de área/perímetro/centroide reimplementado — todo número vem da
   resposta do servidor.

## Proibições

- ❌ Não altere `backend_api/`, `app.py`, `database.py`, `services/`,
  `repositories/`, nem os arquivos das specs anteriores.
- ❌ Não calcule área, perímetro nem valide o polígono no Dart — é tudo do
  servidor (spec 0069).
- ❌ Não implemente rastreamento contínuo em segundo plano — ver "Objetivo".
- ❌ Não crie uma tela de "lista/edição de piquetes" além do necessário pra
  escolher qual demarcar — está fora de escopo (a criação de piquete é a spec
  0068, a visão geral com ocupação é território de mesa, não desta spec).

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main`
com a 0047 já mesclada, se testou contra servidor mock ou contra a API real
(0069), e se os golden PNGs foram gerados de verdade (cole a saída do
`flutter test --update-goldens`).
