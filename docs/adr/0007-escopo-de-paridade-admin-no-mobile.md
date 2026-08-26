# ADR 0007 — Paridade admin no mobile: quais páginas do web entram, e em que forma

- **Status:** Aceito
- **Data:** 2026-08-26
- **Decisor:** proprietário do produto (welz-gui)
- **Relacionado:** [ADR 0006](0006-mobile-offline-fila-de-escrita.md) (arquitetura offline —
  não afetada por esta ADR, continua valendo para tudo que entrar aqui),
  [ROADMAP](../../ROADMAP.md) Trilha 1

---

## 1. Contexto

O Mobile v1 (specs 0044–0062, quase todas fechadas) tem um escopo que, embora nunca tenha
sido declarado explicitamente dessa forma, **é um espelho 1:1 de uma única página do web:
`app.py::page_campo`** ("📱 Modo Campo"). Essa página já existia no web como o "modo de
campo" — três abas: 🌾 Trato do Dia, 🐄 Manejo do Animal (pesagem/movimentação/sanidade/foto)
e 📥 Importar CSV. O mobile recriou nativamente exatamente essas três abas, spec por spec.

Testando o app em aparelho real (2026-08-26), o feedback foi: *"o perfil de administrador
deveria ter acesso a praticamente todas as ações que podem ser feitas no sistema web"* — ou
seja, ir além do espelho de `page_campo` e cobrir o resto do app web para o usuário admin.

**O web tem 21 páginas de nível superior** (`page_*` em `app.py`). Cobrir "quase tudo" sem
critério viraria uma reimplementação completa do app web em Flutter — meses de trabalho, boa
parte dele para telas que não fazem sentido em tela pequena (tabelas financeiras densas,
formulários de cadastro de 15 campos, ferramentas de administração de banco). Esta ADR
resolve **o que entra, o que não entra, e em que forma**, antes de qualquer spec nova ser
escrita.

---

## 2. Inventário e critério

Cada página foi classificada por um critério simples: **é uma ação que faz sentido tomar no
curral/pasto, com o celular na mão, sem teclado físico?** Não é sobre o cargo de quem usa
(admin vs operador) — é sobre o contexto físico da ação.

### 2.1 Já coberto (espelho de `page_campo`, Mobile v1)

`_campo_trato` (0054/0055), `_campo_animal` → pesagem/movimentação/sanidade/foto
(0047–0053), `_campo_importar` (0057/0058, na fila). Sem mudança aqui.

### 2.2 Tier 1 — bom encaixe, forma completa (mesmas ações do web, tela própria)

| Página web | Por quê é campo, não mesa |
|---|---|
| `page_lotes` (além da movimentação já coberta) | Criar lote e transferir animais entre lotes são decisões tomadas olhando o rebanho no pasto, não uma planilha |
| `page_brincos` | Reconciliar estoque de brinco é conferência física — bate o número físico com o sistema ali na hora |
| `page_alertas`, aba **Operacionais** | "O que eu preciso fazer hoje" é exatamente o tipo de pergunta que se faz no celular, não na mesa |

### 2.3 Tier 2 — bom encaixe, só leitura (consultar no campo, não editar)

| Página web | Por quê só leitura |
|---|---|
| `page_estoque` | Conferir "tem insumo suficiente?" é útil no campo; comprar/ajustar estoque é decisão de mesa |
| `page_dashboard` (resumo, não o completo) | Visão geral rápida tem valor no bolso; o dashboard completo tem gráficos que pedem tela grande |
| `page_relatorios`, abas Inventário/Pesagens | Consulta pontual no campo; exportação é tarefa de mesa |

### 2.4 Fora de escopo do mobile (fica só no web)

| Página web | Por quê é mesa, não campo |
|---|---|
| `page_financeiro`, `page_cadastrar` (compras/contas a pagar/receber) | Digitação longa, decisão financeira — exige atenção e tela grande |
| `page_regras`, `page_propriedades` | Configuração estrutural, rara, feita uma vez, não durante manejo |
| `page_sincronizacao` | Operação de infraestrutura (fila 0005), não ação de campo |
| `page_admin` (usuários/status/banco) | Administração de sistema — nunca deveria ser feita no celular, admin ou não |
| `page_desempenho`, `page_nutricao` (autoria de plano), `page_alertas` aba **Conformidade** | Análise/planejamento que exige revisar dados com calma — a *confirmação* do plano de trato já é campo (0055); *criar* o plano é mesa, como cadastrar um protocolo (`page_sanitario`, já mesa hoje e continua) |
| `page_movimentacao` (property→property, com GTA) | GTA, titular e transportador são um formulário de compliance denso — diferente do trânsito piquete→piquete (já mobile). Pode ser revisitado depois se o uso real mostrar necessidade, mas não entra agora |

---

## 3. Decisão

**Tier 1 entra como spec mobile completa, mesma UX das telas já existentes (screens
próprias, formulários nativos). Tier 2 entra como visualização — sem formulário de edição,
só leitura com pull-to-refresh, reaproveitando o cache raso da [ADR 0006](0006-mobile-offline-fila-de-escrita.md)
onde fizer sentido. O bloco "fora de escopo" não ganha spec — nem versão simplificada.**

Ordem de prioridade dentro do Tier 1 (a decidir em specs futuras, nesta ordem):
1. `page_alertas` (Operacionais) — menor esforço, maior valor imediato de "o que fazer hoje"
2. `page_brincos` — escopo fechado, PNIB já modela isso bem no backend
3. `page_lotes` (criar/transferir) — maior, mas reaproveita padrões já existentes (0048/0049)

Tier 2 fica para depois do Tier 1 fechar — é valor menor por spec (só leitura) e cada uma
compete pelo mesmo cache raso que a ADR 0006 já timou pequeno de propósito.

**Continua valendo:** nenhuma lógica de negócio nova nasce no mobile (R8/ADR 0002) — toda
tela nova só chama endpoints que já existem ou specs de API que os criam antes da spec
mobile correspondente, mesmo padrão de todo o Mobile v1.

---

## 4. Consequências

- O ROADMAP ganha uma continuação explícita da Trilha 1 (ou uma Trilha nova) listando as
  specs do Tier 1/2 na ordem acima — a escrever conforme a fila mobile atual (0056–0062)
  for fechando, para não competir por revisão ao mesmo tempo.
- **Custo hoje:** nenhum — é só a decisão registrada. Nenhuma spec nova nasce desta ADR
  diretamente.
- O bloco "fora de escopo" (§2.4) não é permanente — se o uso real do app mostrar que uma
  dessas páginas é necessária no campo (ex.: GTA sendo preenchido na fazenda mesmo), volta a
  ser avaliada. Não é uma proibição arquitetural como o ADR 0002, é uma leitura do valor
  hoje.
