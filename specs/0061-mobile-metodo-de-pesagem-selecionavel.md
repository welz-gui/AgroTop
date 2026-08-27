# Spec 0061 — Mobile: método de pesagem selecionável (não mais texto livre)

- **Tipo:** ajuste de UX · **Risco:** baixo · **Esforço:** algumas horas
- **Branch:** `feat/mobile-metodo-de-pesagem`
- **Altere:** só `mobile/lib/screens/weighing_page.dart` (e o teste correspondente)
- **Pré-requisito:** nenhum — a tela de pesagem (spec 0047) já está em `main`.

---

## Regra de ouro desta spec

**Não mude o contrato da API.** O campo continua sendo `method: string` no `POST` de
pesagem (`backend_api/schemas.py:79` — livre, sem enum no servidor). A mudança é
**só de UI**: em vez de o operador digitar o método, ele escolhe de uma lista fixa. O texto
que é enviado ao servidor continua exatamente um dos três códigos já usados em produção.

## Objetivo

Achado testando o app de verdade (2026-08-26): digitar o método de pesagem manualmente
durante o manejo é contraintuitivo e sujeito a erro de digitação (o servidor aceita
qualquer string, então um typo vira um método novo e inconsistente nos relatórios). O app
web já resolve isso com uma lista fixa de 3 métodos — o mobile precisa da mesma.

## Contexto que você precisa

- **A lista de métodos já existe e é usada pelo app web**: `database.py::WEIGH_METHODS`
  (não exposta por nenhum endpoint hoje — são só 3 valores fixos, então **hardcode as
  mesmas 3 opções no Dart**, não crie endpoint novo pra isso):
  ```python
  WEIGH_METHODS = {
      "pesado":   "Pesado na balança",
      "estimado": "Estimado pelo operador",
      "medicao":  "Estimado por medição (fita/fórmula)",
  }
  ```
  O valor enviado ao `POST` continua sendo a **chave** (`"pesado"`, `"estimado"` ou
  `"medicao"`) — o rótulo (`"Pesado na balança"`, etc.) é só o que aparece na tela.
- **Campo atual**: `mobile/lib/screens/weighing_page.dart`, `TextFormField` com
  `key: const ValueKey('weighing-method')`, controlado por `_method` (default:
  `TextEditingController(text: 'pesado')`), validado como texto não vazio.
- **Troque por um `DropdownButtonFormField<String>`**, mesmo padrão já usado em
  `medication_page.dart` para o dropdown de protocolos — `initialValue: 'pesado'`
  (mantém o mesmo default atual), 3 `DropdownMenuItem` com os textos acima, sem opção de
  texto livre.
- **Mantenha a `key: const ValueKey('weighing-method')`** no novo widget — testes
  existentes (`flow_test.dart`, goldens) podem depender dela para localizar o campo.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde — inclui atualizar `flow_test.dart` onde ele hoje digita texto
   no campo de método, trocando para selecionar uma das 3 opções do dropdown.
3. O campo de método não aceita mais texto livre — é só seleção entre as 3 opções.
4. O valor enviado ao `POST /animais/{id}/pesagens` continua sendo `"pesado"`,
   `"estimado"` ou `"medicao"` (as chaves, não os rótulos em português) — confirme lendo
   o corpo da requisição no mock, não só a tela.
5. Golden test da tela de pesagem (já existe, `dark/light/system-04-pesagem.png`)
   **atualizado** para refletir o dropdown em vez do campo de texto — gere os PNGs de
   verdade (`flutter test --update-goldens`), commite só os arquivos que realmente mudam.
   Se não tiver Flutter disponível, **pare e reporte antes de abrir o PR** — não abra
   alegando o critério cumprido sem os `.png` no diff.

## Proibições

- ❌ Não crie endpoint novo para expor `WEIGH_METHODS` — são 3 valores fixos, hardcode.
- ❌ Não altere `backend_api/`, `app.py`, `database.py` nem nenhum arquivo fora de
  `mobile/`.
- ❌ Não mude o campo `method` do contrato (continua string) nem valide no servidor —
  fora de escopo desta spec.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
```

## Entrega

PR para `main`, pronto para revisão. Diff esperado: só `weighing_page.dart`,
`flow_test.dart`, `golden_screens_test.dart` (se precisar) e os PNGs de pesagem
atualizados.
