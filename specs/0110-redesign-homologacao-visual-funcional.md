# Spec 0110 — Redesign: homologação da versão e evidências de conclusão

- **Tipo:** validação/integração · **Risco:** baixo (não altera código de produção) ·
  **Esforço:** 1 dia
- **Branch:** `docs/redesign-homologacao`
- **Altere:** nenhum arquivo de produção — só o relatório de homologação (novo documento em
  `docs/` ou anexo ao PR, à sua escolha) e testes de ponta a ponta adicionais, se necessário
  para cobrir um cenário que hoje não tem prova automatizada
- **Pré-requisito:** todas as specs do redesign na versão candidata —
  [0091](0091-web-contraste-de-badges-e-css-em-tokens.md) a
  [0109](0109-redesign-estados-e-acessibilidade.md) — mescladas

---

## Objetivo

RD13 da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`).
Provar que o **conjunto** do redesign cumpre o que as três imagens aprovadas
(`DESIGN-IS-2026-09-10/propostas-web/`) e as specs 0091-0109 pediram — não que cada PR passou
em seus próprios testes isoladamente. Esta spec **não autoriza deploy** — é um relatório de
evidências e pendências classificadas para o mantenedor decidir.

## Contexto que você precisa

- **Não é uma spec de implementação** — não crie nem edite componentes de produção aqui. Se a
  homologação encontrar um defeito, ele vira um item classificado no relatório, não uma
  correção improvisada nesta spec.
- **Use o mesmo conjunto de dados das capturas de referência** já usadas nas specs anteriores
  (ou documente exatamente qual massa de dados usou, se precisar recriar) — comparação só faz
  sentido com dados equivalentes.
- **As três imagens são guia de composição, não dado a copiar** — números, datas e ícones
  ilustrativos das imagens não são o que se testa; o que se testa é se a composição/hierarquia
  real bate com o que elas mostram.

## Contrato obrigatório

Execute e documente evidência para cada um dos 8 cenários ponta a ponta:

1. Administrador: dashboard → alerta → lista filtrada → limpar filtro (spec 0105/RD07).
2. Rebanho: pesquisar → filtrar → ordenar → selecionar → ficha → operação do mesmo animal →
   retorno com contexto (specs 0095, 0106).
3. Operador: os 4 destinos preservados; rota administrativa continua protegida (guard central,
   sem mudança nesta versão).
4. Mobile: pesquisa fora da primeira página → offline → outra consulta → reconexão (spec
   0089/0094).
5. Dashboard mobile: sucesso → falha → aviso persistente → nova tentativa bem-sucedida (specs
   0090, 0101).
6. Sanidade: carregando → carência ativa/ausência verificada/erro, sem confundir estados
   (regressão, sem spec específica desta rodada — comportamento pré-existente).
7. Registro offline: confirmação local → fila → sincronizado ou rejeitado com mensagem correta;
   uma ação não cria registros duplicados (idempotência, spec 0059/0060).
8. Temas e unidade: claro/escuro (spec 0102), kg/@ no escopo existente, navegação (spec 0103)
   e filtros preservados.

**Evidência por plataforma:**
- Web: 1366×768, 1440×900, janela estreita e zoom 200%.
- Mobile: 320/360/390/430px, 600px (tablet) para composição adaptativa, fonte ampliada e
  teclado aberto.
- Compare as três telas web finais (Dashboard/Rebanho/Ficha) contra as três imagens aprovadas,
  registrando e justificando qualquer diferença funcional (não é preciso bater pixel a pixel).

## Critério de aceite

1. Testes relevantes e CI passam no commit candidato usado para a homologação.
2. Evidência (capturas/gravação/log) corresponde exatamente ao commit candidato referenciado —
   não a uma versão anterior ou posterior.
3. Nenhum defeito aberto encontrado troca o animal de uma ação, mascara falha como sucesso, ou
   perde navegação/permissão — se algum for encontrado, classifique como bloqueante e não
   recomende publicação até resolver.
4. Desvios visuais relevantes em relação às 3 imagens aprovadas têm decisão registrada
   (aceito como está / vira spec de ajuste / não se aplica e por quê).
5. Relatório final lista: cenários com evidência completa, desvios visuais e decisão, defeitos
   encontrados classificados por severidade, e uma recomendação explícita (pronta para
   publicação / pendências bloqueantes listadas).

## Proibições

- ❌ Não corrija defeitos encontrados dentro desta spec — classifique e reporte.
- ❌ Não trate "PR mesclado" como prova de deploy nem "APK gerado" como prova de instalação —
  a homologação é sobre o comportamento do software, não sobre o pipeline de entrega.
- ❌ Não inclua nem recomende migração destrutiva de schema como parte desta entrega visual.
- ❌ Não aprove publicação automaticamente por causa desta spec — a aprovação final é decisão
  do mantenedor, fora do escopo do relatório.

## Como verificar antes de abrir o PR

```bash
$env:AGROTOP_FORCE_SQLITE = "1"
python -m unittest discover -s tests -t .
cd mobile && flutter analyze && flutter test
```

## Entrega

PR para `main` com o relatório de homologação completo (8 cenários + evidência por
plataforma + comparação com as 3 imagens + lista de defeitos classificados + recomendação).
Esta spec não inclui autorização de deploy — isso é decisão separada do mantenedor após ler o
relatório.
