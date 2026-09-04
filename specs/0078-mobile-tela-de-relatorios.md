# Spec 0078 — Mobile: tela de relatórios (inventário e pesagens)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2 dias
- **Branch:** `feat/mobile-relatorios`
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

**Contrato travado na spec [0077](0077-api-relatorios-inventario-e-pesagens.md) — não
invente endpoint nem campo diferente do que ela define.** Você não precisa esperar a 0077
mesclar — teste contra um **servidor mock**, mesmo padrão de toda spec mobile. **Esta tela
é só consulta, sem exportação** ([ADR 0007](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md)
§2.3: "exportação é tarefa de mesa") — não implemente CSV/Excel/PDF.

## Objetivo

Última spec do Tier 2 da ADR 0007. "Consulta pontual no campo" — ver o inventário completo
do rebanho ou o histórico de pesagens sem precisar do navegador. Esta spec traz as duas
tabelas pro mobile, contra a API da 0077.

## Contexto que você precisa

- **Ponto de entrada:** um `IconButton` novo no `AppBar` de `AnimalsPage` — ícone sugerido
  `Icons.description_outlined`, tooltip "Relatórios", sem badge.
- **Duas abas (`TabBar`/`TabBarView`)**: "🐄 Inventário" e "⚖️ Pesagens" — mesma ordem do
  web (a aba "💰 Financeiro" não existe aqui, ver Proibições).
- **Aba Inventário:** lista de animais (não tabela densa de 19 colunas — tela pequena não
  comporta) — cada item um `Card`/`ListTile` expansível ou uma ficha resumida com pelo
  menos: ID, raça, categoria de idade, idade, peso atual, GMD, status, lote. Os campos
  restantes do contrato (fornecedor, NF, GTA, carência, peso de entrada/ganho, arrobas)
  podem ficar num detalhe expandido por item — não precisa mostrar os 19 campos lado a
  lado como no web, é reorganização de layout, não perda de dado (o contrato inteiro ainda
  chega ao app, só a apresentação muda).
- **Filtro por status (opcional, recomendado)** — a API devolve todos os status; um filtro
  simples (`ativo`/`vendido`/`morto`/`carencia`/todos) ajuda a não afogar a tela com o
  histórico inteiro. **Não é bloqueante** para o critério de aceite se ficar de fora.
- **Aba Pesagens:** lista simples, mais recente primeiro (ou a ordem que a API devolver —
  não inverta, a API já ordena por data), cada item mostrando animal, data, peso, método
  (traduzido — reaproveita `WEIGH_METHODS` já hardcoded desde a spec 0061, não invente
  tradução nova), lote, operador, observação se houver.
- **Sem paginação client-side obrigatória** — a API já não pagina (spec 0077); uma
  `ListView` simples com os itens que vierem já cumpre o critério. Se a lista ficar grande
  na prática, considere paginação/scroll infinito, mas isso não é critério de aceite desta
  spec.

## Contrato obrigatório

Contra a API da spec 0077:

```
GET /relatorios/inventario
  -> [ { "id": str, "raca": str|null, "sexo": str|null, "categoria_idade": str,
          "idade_display": str, "data_nascimento": str|null,
          "nascimento_estimado": bool, "origem_idade": str, "data_entrada": str,
          "peso_entrada_kg": float, "peso_atual_kg": float, "ganho_kg": float,
          "arrobas_atuais": float, "gmd_kg_dia": float|null, "status": str,
          "lote_id": str|null, "fornecedor": str|null, "nf": str|null,
          "gta": str|null, "carencia_ate": str|null } ]

GET /relatorios/pesagens
  -> [ { "animal_id": str, "data": str, "peso_kg": float, "metodo": str,
          "lote_id": str|null, "operador": str|null, "observacoes": str|null } ]
```

Ver a spec 0077 para os detalhes de cada campo. `categoria_idade`/`origem_idade` vêm sem
tradução — decida os rótulos em português no Dart (não precisam ser idênticos ao web,
que usa `services/zootecnia.py::AGE_BANDS`/`AGE_SOURCES`; se quiser copiar os textos
exatos, consulte esses dois no código-fonte antes de inventar rótulo diferente).

## Servidor mock para teste

Estenda o mock já usado pelas specs anteriores, respondendo `GET /relatorios/inventario` e
`GET /relatorios/pesagens` no formato exato da 0077 — inclua no inventário pelo menos um
animal com `gmd_kg_dia: null` e um com `nascimento_estimado: true`, e nas pesagens pelo
menos dois métodos diferentes.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo: abrir a tela de relatórios a partir de `AnimalsPage` →
   aba Inventário mostra os animais do mock → trocar para a aba Pesagens → mostra o
   histórico do mock com o método traduzido.
3. Animal com `gmd_kg_dia: null` mostra "—" ou equivalente, não "null" nem `0.0` (0 seria
   um dado falso, não ausência de dado).
4. `nascimento_estimado: true` mostra alguma indicação visual (mesmo espírito do "(est.)"
   do web) — não precisa ser o mesmo texto.
5. Testes visuais (golden) cobrem a aba Inventário e a aba Pesagens nos três temas. **Gere
   os PNGs de verdade** — `flutter test test/golden_screens_test.dart --update-goldens` —
   e **commite os `.png` resultantes em `mobile/test/goldens/`**. Se não tiver o toolchain
   Flutter disponível, **pare e reporte isso explicitamente antes de abrir o PR**.
6. `grep -rniE "AGE_BANDS|meses.*12|meses.*24|meses.*36" mobile/lib/` não acha a régua de
   faixa etária reimplementada — `categoria_idade` já vem calculada do servidor, o app só
   traduz o rótulo (que é texto fixo, não um novo cálculo de meses).

## Proibições

- ❌ Não altere `backend_api/`, `app.py`, `database.py`, `services/`, `repositories/`, nem
  os arquivos das specs anteriores.
- ❌ Não implemente a aba "💰 Financeiro" — fora de escopo do mobile inteiro (ADR 0007
  §2.4), a 0077 nem expõe isso.
- ❌ Não implemente exportação (CSV/Excel/PDF/compartilhar) — tarefa de mesa, fora de
  escopo (ADR 0007 §2.3).
- ❌ Não recalcule `categoria_idade`, `idade_display` nem `gmd_kg_dia` no Dart — vêm
  prontos do servidor.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, se testou contra servidor mock ou contra a API real (0077), e se os
golden PNGs foram gerados de verdade (cole a saída do `flutter test --update-goldens`).
