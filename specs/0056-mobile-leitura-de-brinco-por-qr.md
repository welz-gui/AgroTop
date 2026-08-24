# Spec 0056 — Mobile: leitura de brinco por QR Code (câmera nativa)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2 dias
- **Branch:** `feat/mobile-leitura-de-brinco-qr`
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

**Sem endpoint novo.** Esta spec não toca `backend_api/` nem espera nenhuma outra spec
mesclar — o único endpoint que ela usa (`GET /animais/{id}`) já existe desde a spec 0044 e
o mobile já o consome (`ApiClient.getAnimal`). Você só adiciona uma forma nova de preencher
esse `id`: lendo um QR Code pela câmera, em vez de digitar.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md) — a última peça do escopo original de Mobile v1
online que ainda faltava: "leitura de brinco (QR/câmera nativa)". O web já tem uma versão
disso (`app.py::_campo_animal`, aba "📷 Câmera") que tira uma foto e decodifica no
**servidor** (`_decode_qr`, com OCR de fallback). **No mobile, o certo é fazer isso
nativamente no aparelho** — mais rápido, funciona sem round-trip de rede, e é o padrão de
qualquer app de captura de QR.

## Contexto que você precisa

- **Ponto de entrada:** um ícone de câmera/QR (`suffixIcon` no campo de busca "Buscar por
  ID ou brinco" de `AnimalsPage`, ou um `IconButton` ao lado — sua escolha, contanto que
  fique óbvio e não exija scroll) que abre a tela/diálogo de leitura.
- **A leitura NÃO deve alimentar o filtro local `_query`.** O filtro atual de `AnimalsPage`
  é só um `.where(...)` em memória sobre os animais **já carregados** na página (até
  `_pageSize` = 50, mais o que o scroll infinito já trouxe) — um animal fora dessa janela
  simplesmente não aparece, mesmo existindo. Isso é aceitável para busca por substring
  (o operador digita e vê sugestões), mas **não** para leitura de QR: quem lê o brinco quer
  o animal exato, exista ele carregado ou não. Depois de decodificar o texto do QR, chame
  `widget.api.getAnimal(codigo)` **diretamente** e navegue para `AnimalDetailPage` se
  encontrar — não passe pelo filtro local.
- **Câmera só sob demanda (ROADMAP R15)** — mesma regra do resto do app: a câmera não pode
  ser instanciada (nem a permissão pedida) antes de o operador tocar em "Ler QR do brinco".
  Fechar a tela de leitura libera a câmera.
- **`AndroidManifest.xml` ainda não declara `android.permission.CAMERA`** — diferente de
  `image_picker` (spec 0053), que abre o app de câmera do sistema via intent e não precisa
  da permissão declarada, uma biblioteca de leitura de QR embutida (ex.: `mobile_scanner`)
  usa a câmera **dentro do app** e exige a permissão declarada e solicitada em runtime.
  Adicione a linha em `mobile/android/app/src/main/AndroidManifest.xml`.
- **Sem OCR de fallback nesta fatia** (decisão registrada, não esquecimento). O web tem um
  fallback de OCR do número do brinco quando não acha QR — é "melhor esforço", o próprio
  código o descreve como impreciso. Reproduzir isso no mobile exigiria outra dependência
  (reconhecimento de texto) só para uma rede de segurança de baixo valor: se o QR não for
  lido, o operador **sempre pode digitar o ID manualmente** no campo que já existe. Fica
  para uma spec futura, se o uso real mostrar que falta.
- **Dependência nova a adicionar:** um pacote de leitura de QR/barcode do ecossistema
  Flutter (ex.: `mobile_scanner`, ativamente mantido, usa CameraX no Android). Escolha um
  pacote publicado, com suporte a Android (não precisa suportar iOS/web para esta fatia,
  mas não quebre se rodar lá). Documente no PR qual pacote escolheu e por quê, se não for
  o sugerido.

## Contrato obrigatório

Nenhum endpoint novo. Reaproveita:

```
GET /animais/{id}   -> já existe (ApiClient.getAnimal), usado hoje na ficha
```

Telas/fluxos obrigatórios:

1. **Botão/ícone "Ler QR do brinco"** em `AnimalsPage`, abre a câmera só ao tocar.
2. **QR decodificado com sucesso** → chama `getAnimal(codigo)` diretamente:
   - Encontrado → navega para `AnimalDetailPage` do animal (fecha a câmera).
   - Não encontrado (404) → mensagem clara ("Animal {codigo} não encontrado"), oferece
     tentar ler de novo ou fechar e buscar manualmente. **Não trava a tela.**
3. **QR ilegível ou nenhum QR na imagem** → nunca deixe a tela travada ou sem feedback;
   mostre instrução de reposicionar/tentar de novo, sem crash.
4. **Erro de rede na consulta** (`getAnimal` falha por conexão, não por 404) → mensagem
   clara, permite tentar de novo sem reabrir a câmera do zero.
5. **Fechar a tela de leitura libera a câmera** — sem vazamento de recurso, sem câmera
   continuando ativa em segundo plano.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde. Como a pré-visualização de câmera ao vivo é uma view nativa de
   plataforma (não renderiza de forma determinística em teste de widget), **isole a lógica
   de decodificação atrás de uma abstração testável** — mesmo padrão do `PhotoCapture` da
   spec 0053: um callback/typedef injetável que o teste substitui por um resultado
   simulado (`'BR0001'`, `null` para "não decodificado", etc.), sem precisar de câmera de
   verdade.
3. Teste prova o fluxo completo com um código simulado válido: decodifica → chama
   `getAnimal` → navega para a ficha certa (contra o mock).
4. Teste prova o caso de animal não encontrado: código simulado que o mock devolve `404`
   → mensagem de erro visível, tela não trava, oferece novo intento.
5. Teste prova que a leitura bem-sucedida **não** passa pelo filtro local `_query` de
   `AnimalsPage` — ex.: simule um `id` que não está entre os animais já carregados na
   lista e confirme que a navegação para a ficha acontece mesmo assim (prova de que é
   busca direta na API, não filtro em memória).
6. `AndroidManifest.xml` contém `<uses-permission android:name="android.permission.CAMERA"/>`.
7. Teste ou inspeção manual documentada no PR prova que a câmera não é aberta/instanciada
   antes do toque no botão de leitura (R15) — mesmo critério já usado nas specs de foto e
   pesagem.
8. `grep -rn "pytesseract\|OCR\|ocr" mobile/lib/` não acha nada — confirma que o fallback
   de OCR não foi implementado nesta fatia (fora de escopo, ver "Contexto").
9. **Testes golden NÃO são exigidos nesta spec** — a tela de leitura é dominada por uma
   view de câmera nativa, que não pinta de forma estável num teste de widget offline.
   (Diferente da spec 0051/0055: ali a lacuna seria um problema real; aqui, exigir golden
   da câmera ao vivo seria pedir o impossível — não confunda as duas situações.)

## Proibições

- ❌ Não altere `backend_api/`, `poc/`, `app.py`, `database.py`, `services/`,
  `repositories/`, nem os arquivos das specs anteriores.
- ❌ Não implemente o fallback de OCR — ver "Contexto que você precisa".
- ❌ Não alimente o resultado da leitura no filtro local `_query` — é busca direta na API
  (ver "Contexto"), essa é a razão de existir desta spec.
- ❌ Não peça permissão de câmera fora do fluxo de toque no botão de leitura.
- ❌ Não invente um endpoint novo — `GET /animais/{id}` já resolve tudo que esta tela
  precisa.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, qual pacote de leitura de QR você escolheu, e cole a saída dos comandos
de verificação.
