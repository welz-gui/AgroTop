# Spec 0109 — Redesign: fechar lacunas de estados e acessibilidade

- **Tipo:** correção/auditoria · **Risco:** médio · **Esforço:** 1-2 dias (varia com o número
  de lacunas encontradas — ver Contrato)
- **Branch:** `fix/redesign-estados-e-acessibilidade`
- **Altere:** só as telas/componentes do redesign onde uma lacuna real for reproduzida — lista
  fechada durante a auditoria desta própria spec, não antes (ver Contexto)
- **Pré-requisito:** [spec 0105](0105-web-dashboard-hierarquia-e-acoes.md) (RD07),
  [spec 0106](0106-web-ficha-manejo-e-historico.md) (RD09),
  [spec 0107](0107-mobile-ficha-metricas-responsivas.md) (RD10),
  [spec 0108](0108-mobile-dashboard-compacto-e-grafico.md) (RD11) — **todas mescladas antes de
  começar**; esta spec audita o conjunto integrado, não faz sentido rodar contra telas
  parcialmente redesenhadas

---

## Objetivo

RD12 da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`).
Cada spec anterior do redesign (0091 em diante) já deveria entregar seus próprios estados e
acessibilidade — esta spec **não é uma licença para adiar isso até aqui**. É uma auditoria do
conjunto integrado, procurando por diferenças entre telas que só aparecem quando tudo está
junto (ex. uma tela trata "sem dado" com traço, outra com "N/A", outra com zero — inconsistente
mesmo que cada uma isoladamente "funcione").

## Contexto que você precisa

- **Esta spec não tem, ainda, uma lista fechada de arquivos** — a proposta original é explícita
  sobre isso: "lista fechada pelo mantenedor antes da atribuição". Isso significa: **antes de
  corrigir qualquer coisa, rode a auditoria completa** (matriz abaixo × todas as telas tocadas
  pelo redesign desde a spec 0091) e documente cada lacuna encontrada, com tela/estado/o que
  está errado — só depois corrija. Não é permitido pular direto para "melhorias" gerais sem a
  auditoria documentada primeiro.
- **Não é refatoração aberta** — corrija exatamente as lacunas encontradas e documentadas na
  auditoria. Se encontrar algo que exige mudança de arquitetura (não só de apresentação), pare
  e proponha spec separada em vez de expandir esta.
- **WCAG 2.2** (`https://www.w3.org/TR/WCAG22/`) é a referência — não declare "acessível"
  baseado só em contraste de paleta; contraste é uma dimensão entre várias (foco visível,
  navegação por teclado, rótulos, texto alternativo a cor).
- **Telas em escopo** (todas já tocadas pelo redesign): Dashboard web (spec 0105/0091),
  Rebanho web (spec 0095), Ficha web (spec 0106/0091), sidebar web (spec 0103), tema web
  (spec 0102), AlertsPage mobile (spec 0097/0093), Dashboard mobile (spec 0108/0101/0093/
  0086), Ficha mobile (spec 0107/0104/0096/0092), linguagem mobile (spec 0098).

## Contrato obrigatório

1. **Fase 1 — Auditoria** (produz uma tabela, não código): para cada tela em escopo, percorra
   a matriz obrigatória de estados — normal, vazio, carregando, erro recuperável, sessão
   expirada, desabilitado, foco, dado desatualizado (quando aplicável) — e registre: tela,
   estado, o que está errado ou inconsistente, captura se possível. Campos sem dado real nunca
   recebem zero de preenchimento (ex. "peso-alvo: 0 kg" quando não há meta definida é uma
   lacuna a registrar, não um estado válido).
2. **Fase 2 — Contraste e navegação**: conferir os pares de cor efetivamente usados nas telas
   em escopo (incluindo texto de apoio sobre superfícies, não só texto principal) — mínimo
   4,5:1 para texto normal, com as exceções corretas para texto grande e elementos inativos.
   Foco visível e navegação por teclado no web (Streamlit já cuida da maior parte
   nativamente — só corrija onde um teste real mostrar um caso sem contorno de foco). Rótulos
   acessíveis (`Semantics` no mobile, `aria`/rótulos nativos no web) e informação que não
   depende só de cor (ex. badge teria que ter texto, não só cor, para indicar status — audite
   se algum badge do redesign quebrou essa regra).
3. **Fase 3 — Correção**: para cada lacuna registrada na Fase 1/2, uma correção pontual na tela
   onde ela foi encontrada — sem tocar telas fora da lista da auditoria.
4. **Movimento reduzido**: confira se alguma transição/animação nova do redesign (CSS
   `transition`, animações Flutter) ignora preferência de movimento reduzido do sistema —
   remova as que não são essenciais à compreensão da interface.
5. **Gravações/idempotência**: confirme que o estado "salvando" existe visivelmente onde a
   spec original previa (Modo Campo, fila offline), que a UI impede duplo envio, e que a
   recuperação de erro já existente continua funcionando — qualquer defeito de backend
   encontrado aqui vira uma correção delimitada e documentada, não uma mudança de protocolo
   disfarçada de ajuste visual.

## Critério de aceite

1. Tabela de auditoria (Fase 1/2) entregue no PR antes ou junto da correção, com lacuna →
   correção → evidência para cada item corrigido.
2. Busca, seleção, ficha e manejo completáveis por teclado no web; zoom de 200% não esconde
   ações essenciais.
3. Mobile: texto ampliado e teclado aberto não cortam nenhum controle essencial (herdando a
   metodologia de larguras/escalas já usada nas specs 0096/0104/0107).
4. Estados com erro sempre oferecem uma ação de recuperação coerente (retry, voltar, ou
   explicação do que fazer).
5. Nenhum item da matriz obrigatória fica sem tratamento documentado em pelo menos uma tela em
   escopo — se uma tela já está correta num estado, isso também é registrado (não precisa
   virar código, só confirmação).
6. Nenhum bloqueio conhecido nos fluxos auditados fica mascarado por atualização de golden sem
   explicação.

## Proibições

- ❌ Não pule a Fase 1 (auditoria documentada) — corrigir sem registrar o que foi encontrado
  quebra a rastreabilidade que esta spec existe para garantir.
- ❌ Não expanda para telas fora da lista de escopo sem atualizar a lista e justificar.
- ❌ Não declare conformidade WCAG completa — o critério de aceite é sobre os itens auditados,
  não uma certificação formal.
- ❌ Não corrija defeito de backend/protocolo encontrado durante a auditoria dentro desta
  spec — documente e proponha spec própria.

## Como verificar antes de abrir o PR

```bash
$env:AGROTOP_FORCE_SQLITE = "1"
python -m unittest discover -s tests -t .
cd mobile && flutter analyze && flutter test
```

## Entrega

PR para `main`, pronto para revisão, com a tabela de auditoria completa (Fase 1/2) anexada ao
corpo do PR, cada correção referenciando a linha da tabela que a motivou.
