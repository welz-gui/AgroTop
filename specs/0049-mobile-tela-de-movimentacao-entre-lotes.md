# Spec 0049 — Mobile: tela de movimentação entre piquetes

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2 dias
- **Branch:** `feat/mobile-movimentacao-entre-lotes`
- **Altere:** `mobile/` (a pasta que a spec 0047 criou)
- **Pré-requisito obrigatório:** **a spec [0047](0047-mobile-v1a-login-animais-e-pesagem.md)
  precisa estar mesclada em `main` antes de você começar** — esta spec estende o app
  Flutter dela, não existe `mobile/` sem isso. Confirme:
  ```bash
  git fetch origin
  git cat-file -e origin/main:mobile/lib/app.dart 2>/dev/null \
    && echo "0047 já mesclada — pode seguir" \
    || echo "0047 AINDA NÃO mesclada — pare e avise quem te instruiu"
  ```

---

## Regra de ouro desta spec

**Contrato travado na spec [0048](0048-api-movimentacao-entre-lotes.md) — não invente
endpoint, payload nem formato de erro diferente do que ela define.** Igual à 0047 em
relação à 0044: você **não precisa esperar a 0048 mesclar**, só a 0047. Teste contra um
**servidor mock** que implementa o contrato da 0048, não contra a API real.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), subtarefa 1.6. Segunda fatia do Mobile v1 — depois de
login/animais/pesagem (0047), a próxima ação de campo mais comum: mover um ou mais animais
de piquete (rodízio de pasto, separação de lote) sem precisar abrir o app pra cada um.

## Contexto que você precisa

- O app já tem, da 0047: login, lista de animais ativos com busca, ficha do animal,
  autenticação com refresh automático, tema gerado de `ui/tema.py`. Você **reusa** essa
  base — não recria login nem navegação principal.
- `poc/mobile/` (a PoC original) tinha só três telas e não cobria movimentação — não há
  código de referência pra isso nela, a tela é nova de verdade.

## Contrato obrigatório

Contra a API da spec 0048:

```
GET  /lotes                        -> lista de piquetes (destino do seletor)
POST /animais/movimentar           -> resultado da movimentação
```

Telas/fluxos obrigatórios:

1. **A partir da ficha do animal** (já existente, da 0047): botão "Mover de piquete", abre
   seleção de piquete de destino (lista vinda de `GET /lotes`) e confirma com
   `POST /animais/movimentar` com só aquele `animal_id`.
2. **Seleção múltipla na lista de animais** (já existente, da 0047): modo de seleção
   (long-press ou botão "Selecionar vários"), escolhe N animais, um piquete de destino, e
   confirma numa chamada só — não uma chamada por animal.
3. **Resultado visível e diferenciado**: animais efetivamente movidos, animais que já
   estavam no destino (não é erro, mostre como informativo, não como falha) e animais que
   deram erro (mostre qual e por quê) — três categorias, nunca um "sucesso" genérico que
   esconde as outras duas.

## Servidor mock para teste

Estenda (ou reescreva, sua escolha) o mock que a 0047 já usa, agora também respondendo
`GET /lotes` e `POST /animais/movimentar` com os formatos exatos do contrato da 0048.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo um fluxo completo: abrir ficha → mover animal → volta
   pra ficha/lista já refletindo o novo piquete (contra o mock).
3. Fluxo de seleção múltipla move N animais numa única chamada HTTP (confira no teste que
   o mock recebeu **uma** requisição com `N` ids, não `N` requisições).
4. A resposta com `"ja_no_destino"` não vazio aparece na tela como aviso informativo
   (ex.: "2 já estavam nesse piquete"), não como erro em vermelho.
5. A resposta com `"erros"` não vazio aparece destacada, nomeando quais animais falharam —
   e os que foram movidos com sucesso na mesma chamada continuam confirmados como movidos
   (a tela não pode fingir que a chamada toda falhou).
6. Testes visuais (golden) cobrem a tela de seleção de destino e o resultado com as três
   categorias, nos três temas.
7. `grep -rn "calculate_gmd\|regra de negócio\|fórmula" mobile/lib/` continua sem achar
   nada — nenhum cálculo de negócio novo no Dart.

## Proibições

- ❌ Não altere `backend_api/`, `poc/`, `app.py`, `database.py`, `services/`,
  `repositories/`, nem os arquivos das specs 0044/0047/0048.
- ❌ Não implemente histórico de movimentações na tela — fora de escopo desta fatia (a
  0048 não expõe esse endpoint).
- ❌ Não aponte para a API real nem tente subir `backend_api/` para testar.
- ❌ Não invente campo, endpoint ou formato de erro que a 0048 não define. Diverge → pare
  e reporte, não implemente por cima de uma suposição.
- ❌ Não adicione leitura de brinco por câmera aqui — é subtarefa separada (1.14 na lista
  do mantenedor), ainda sem spec.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. No corpo, confirme que partiu de `origin/main` com a
0047 já mesclada, e diga explicitamente: "testado contra servidor mock, não contra a 0048
real" — a integração ponta a ponta espera as duas (0048 e esta) estarem mescladas.
