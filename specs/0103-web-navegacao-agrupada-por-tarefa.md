# Spec 0103 — Web: sidebar agrupada por tarefa, sem perder nenhum destino

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 1 dia
- **Branch:** `feat/web-sidebar-grupos-e-contexto`
- **Altere:** `app.py::_sidebar`, prova de UI de navegação por perfil
- **Pré-requisito:** [spec 0100](0100-web-base-visual-componentes.md) (RD04) e
  [spec 0102](0102-web-tema-coerente-com-widgets-nativos.md) (RD05)

---

## Objetivo

RD06 da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`)
e imagem 1 (`DESIGN-IS-2026-09-10/propostas-web/01-dashboard-web-escuro.png`). A sidebar hoje
(`app.py::_sidebar`, confirmado em `docs/redesign-web-contratos-e-decisoes.md` §3) lista 20
destinos administrativos em fila reta, sem agrupamento — o operador continua com só 4.

## Contexto que você precisa

- **Inventário real já confirmado** (não presuma, use este, já conferido contra o código):

  | Grupo | Destinos (chave interna) |
  |---|---|
  | Visão geral | `dashboard`, `desempenho`, `alertas` |
  | Operação | `campo`, `rebanho`, `cadastrar`, `lotes`, `nutricao`, `sanitario`, `clima` |
  | Gestão | `financeiro`, `estoque`, `relatorios` |
  | Rastreabilidade | `brincos`, `movimentacao`, `propriedades`, `regras`, `sincronizacao` |
  | Apoio e administração | `assistente`, `admin` |

  20 destinos, nenhum a mais nem a menos — confira que os 20 do `pages` atual
  (`app.py::_sidebar`) aparecem em exatamente um grupo cada.
- **Não crie collapse/expand por grupo.** A proposta original permitia, mas o próprio
  critério dela ("grupo recolhido não deve tornar imperceptível a localização atual") é mais
  simples de cumprir **nunca escondendo nada** — cabeçalho de grupo como texto estático
  (`st.caption` ou `st.markdown` em negrito, sem interação), seguido dos botões do grupo,
  sempre visíveis. Menos estado para gerenciar, zero risco de esconder a página ativa.
- **`_go(key)`/`st.session_state.page`** continuam exatamente como são — só a organização
  visual dos botões muda, não o mecanismo de navegação.
- **Badges dinâmicos** (`f" 🔴{len(low_stk)}"` em Estoque, `f" 🔴{n_alerts}"` em Alertas) — mantenha
  exatamente como estão, só reposicionados dentro do grupo certo.
- **Operador**: continua vendo só `campo`, `cadastrar`, `estoque`, `brincos` — mas agora
  dentro da MESMA estrutura de grupos que o admin vê (não precisa de 4 grupos completos, só
  os grupos que contêm pelo menos um destino liberado para operador aparecem, com só os
  destinos que ele tem).

## Contrato obrigatório

1. Sidebar organizada nos 5 grupos da tabela acima, cada grupo com um cabeçalho de texto
   (não botão, não clicável) seguido dos botões de destino daquele grupo, na mesma ordem que
   já existe hoje dentro de cada grupo.
2. Página ativa continua destacada (`type="primary" if active else "secondary"`, já existente
   — sem mudança de mecanismo).
3. Operador: só os grupos com pelo menos 1 destino seu aparecem, com só esses destinos.
4. Nome/perfil do usuário, seletor de unidade (kg/@) e resumo do rebanho no rodapé da
   sidebar continuam exatamente onde estão — fora do escopo desta spec.

## Critério de aceite

1. Admin: todos os 20 destinos alcançáveis, cada um em exatamente um grupo, com o mesmo
   `_go(key)` de antes — nenhuma rota quebrada.
2. Operador: só os 4 destinos de sempre, dentro da estrutura de grupos.
3. Tentar acessar uma rota administrativa como operador continua bloqueado (guard central do
   `main`, inalterado — teste de regressão).
4. Badges de Estoque/Alertas continuam corretos e no lugar certo (dentro do grupo
   Gestão/Visão geral respectivamente).
5. Trocar de página, voltar, atualizar (F5) — destaque da página ativa continua correto.
6. Logout continua limpando sessão sem mudança.

## Proibições

- ❌ Não crie `pages/` nativo do Streamlit — vedado por R12.
- ❌ Não crie collapse/expand de grupo — cabeçalhos são estáticos, conforme decidido acima.
- ❌ Não adicione busca global, notificações ou qualquer controle decorativo não pedido —
  fora do escopo desta spec.
- ❌ Não toque `OPERATOR_PAGES` nem o guard central de `main` além do necessário para os
  grupos — a lista de rotas autorizadas por perfil não muda, só a apresentação visual.
- ❌ Não migre todo o roteador do app só para esta mudança visual.

## Como verificar antes de abrir o PR

```bash
$env:AGROTOP_FORCE_SQLITE = "1"
python -m unittest discover -s tests -t .
```

## Entrega

PR para `main`, pronto para revisão. Cole no corpo do PR a lista dos 20 destinos e o grupo
de cada um, confirmando que nenhum sumiu.
