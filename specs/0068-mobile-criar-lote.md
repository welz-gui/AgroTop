# Spec 0068 — Mobile: criar lote

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/mobile-criar-lote`
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

**Contrato travado na spec [0067](0067-api-criar-lote.md) — não invente endpoint nem campo
diferente do que ela define.** Você não precisa esperar a 0067 mesclar — teste contra um
**servidor mock**, mesmo padrão da 0047/0049/0051/0053/0055/0064/0066. **Escopo é só criar
lote** — a transferência de animais entre lotes já existe no mobile (spec 0049, tela de
movimentação) e **não faz parte desta spec**.

## Objetivo

Terceiro item mobile do Tier 1 da [ADR 0007](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md).
Criar um piquete novo é decisão tomada olhando o rebanho no pasto — o curral que acabou de
ser dividido, a área nova que entrou. Esta spec traz o formulário do web
(`page_lotes`, aba "➕ Novo Lote") pro mobile, contra a API da 0067.

## Contexto que você precisa

- **Ponto de entrada:** um `IconButton` novo no `AppBar` de `AnimalsPage`, mesmo padrão dos
  botões de trato (0055), alertas (0064) e brincos (0066) — ícone sugerido
  `Icons.add_location_alt_outlined`, sem badge (criar lote não tem uma "contagem"
  pendente).
- **Formulário com 4 campos**, mesmos do web (`app.py::page_lotes`, aba `lt2`):
  - ID do lote (texto curto, maiúsculo — mesmo padrão de `.toUpperCase()` já usado em
    outros campos de código do app)
  - Nome
  - Área (ha) — numérico
  - Capacidade (UA) — numérico
  - Observações (texto livre, opcional)
- **Validação client-side mínima**: ID e Nome obrigatórios, Área/Capacidade não-negativos
  — mesma validação que qualquer form numérico já existente no app (ver
  `weighing_page.dart` como referência de estilo, não os campos em si). **A validação de
  duplicidade é do servidor** (409) — não tente adivinhar se o ID já existe antes de
  enviar.
- **Depois de criar:** mostra confirmação e volta para a tela anterior (mesmo padrão de
  `medication_page.dart` e `weighing_page.dart` — `Navigator.pop` devolvendo o resultado).
- **ID duplicado (409 do servidor):** mostra a mensagem de erro no formulário, **sem**
  fechar a tela — o operador pode corrigir o ID e tentar de novo, sem perder o que já
  digitou nos outros campos.

## Contrato obrigatório

Contra a API da spec 0067:

```
POST /lotes
  body: { "id": str, "nome": str, "area_ha": float, "capacidade_ua": float,
          "observacoes": str = "" }
  -> 201: { "id": str, "nome": str, "capacidade_ua": float, "animais_ativos": 0 }
  -> 409: { "detail": "Lote {id} já existe." }
```

Ver a spec 0067 para os detalhes de cada campo.

## Servidor mock para teste

Estenda o mock já usado pelas specs anteriores, respondendo `POST /lotes` no formato exato
da 0067 — inclua um cenário de sucesso (201) e um de ID duplicado (409, mock devolvendo o
erro na segunda tentativa com o mesmo ID).

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo: preencher os 4 campos obrigatórios e submeter → POST
   com o corpo exato do contrato → sucesso fecha a tela; tentar submeter com ID já
   existente (mock devolve 409) → mensagem de erro aparece, tela **não** fecha, os campos
   preenchidos continuam lá.
3. Botão de salvar desabilitado enquanto ID ou Nome estiverem vazios, ou Área/Capacidade
   forem negativos.
4. Testes visuais (golden) cobrem o formulário vazio e com erro de duplicidade, nos três
   temas. **Gere os PNGs de verdade** — `flutter test test/golden_screens_test.dart
   --update-goldens` — e **commite os `.png` resultantes em `mobile/test/goldens/`**. Um
   teste que só chama `expect(find.text(...))` sem `matchesGoldenFile` real não cumpre este
   critério (já custou uma rodada extra de revisão na 0051). Se não tiver o toolchain
   Flutter disponível, **pare e reporte isso explicitamente antes de abrir o PR**.

## Proibições

- ❌ Não altere `backend_api/`, `app.py`, `database.py`, `services/`, `repositories/`, nem
  os arquivos das specs anteriores.
- ❌ Não implemente transferência de animais entre lotes — já existe (spec 0049).
- ❌ Não implemente visão geral de lotes (ocupação, perímetro) — fora de escopo desta
  fatia; perímetro é território da Trilha 2, não desta spec.
- ❌ Não valide duplicidade de ID no cliente — é responsabilidade do servidor (409), o
  cliente só exibe o erro.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, se testou contra servidor mock ou contra a API real (0067), e se os
golden PNGs foram gerados de verdade (cole a saída do `flutter test --update-goldens`).
