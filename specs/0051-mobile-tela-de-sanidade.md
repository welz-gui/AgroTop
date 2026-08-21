# Spec 0051 — Mobile: tela de sanidade (registrar medicamento e ver carência)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2 dias
- **Branch:** `feat/mobile-sanidade`
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

**Contrato travado na spec [0050](0050-api-sanidade-medicamentos-e-carencia.md) — não
invente endpoint, payload nem formato de erro diferente do que ela define.** Você não
precisa esperar a 0050 mesclar — teste contra um **servidor mock**, mesmo padrão da 0047 e
da 0049.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), subtarefas 1.8/1.9. Na ficha do animal (já existente,
da 0047), mostrar a carência ativa e permitir registrar aplicação de medicamento — a ação
de sanidade mais comum feita no curral.

## Contexto que você precisa

O app já tem, da 0047: login, lista de animais, ficha do animal, refresh automático de
token, tema gerado de `ui/tema.py`. Você adiciona uma seção/aba na ficha, não recria nada
disso.

## Contrato obrigatório

Contra a API da spec 0050:

```
GET  /protocolos                         -> lista para o seletor de protocolo
GET  /animais/{id}/medicamentos          -> carência + histórico, ao abrir a ficha
POST /animais/{id}/medicamentos          -> registra aplicação
```

Telas/fluxos obrigatórios:

1. **Carência visível na ficha** — se `carencia_ate` não é nulo, um indicador visual claro
   (não só texto pequeno) mostrando até quando o animal está em carência. **Informação
   nunca depende só de cor** (ROADMAP R21) — ícone ou texto junto, nunca só uma faixa
   vermelha sem dizer o quê.
2. **Registrar aplicação** — formulário com: escolher um protocolo da lista (preenche
   medicamento/dose/via/carência automaticamente, editável) OU preencher manual; data
   (padrão hoje); confirmar chama `POST` e atualiza a carência mostrada na ficha sem
   precisar recarregar a tela inteira.
3. **Histórico de aplicações** — lista simples das aplicações anteriores (medicamento,
   dose, data), mais recente primeiro.

## Servidor mock para teste

Estenda o mock já usado pela 0047/0049, respondendo `GET /protocolos`,
`GET /animais/{id}/medicamentos` e `POST /animais/{id}/medicamentos` nos formatos exatos
da 0050.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo fluxo completo: abrir ficha → ver carência (ou "sem
   restrição") → escolher protocolo → confirmar → carência atualizada na tela (contra o
   mock).
3. Escolher um protocolo preenche dose/via/carência automaticamente — e o operador
   consegue editar antes de confirmar (não é campo travado).
4. Carência ativa é visível com ícone **e** texto, não só cor — teste que renderiza sem
   cor (ex.: modo alto contraste, se o Flutter test permitir) ainda comunica a informação
   pelo texto/ícone.
5. Testes visuais (golden) cobrem a seção de sanidade da ficha com e sem carência ativa,
   nos três temas.
6. `grep -rn "calculate_gmd\|regra de negócio\|fórmula" mobile/lib/` continua sem achar
   nada.

## Proibições

- ❌ Não altere `backend_api/`, `poc/`, `app.py`, `database.py`, `services/`,
  `repositories/`, nem os arquivos das specs 0044/0047/0048/0049/0050.
- ❌ Não implemente cadastro de protocolo nem campanha em lote — a 0050 não expõe esses
  endpoints.
- ❌ Não aponte para a API real nem tente subir `backend_api/` para testar.
- ❌ Não invente campo, endpoint ou formato de erro que a 0050 não define. Diverge → pare
  e reporte.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, e diga explicitamente: "testado contra servidor mock, não contra a 0050
real".
