# AgroTop — Design System

> **Objetivo:** web e mobile parecerem o **mesmo produto**, e a paleta poder ser trocada
> em um lugar só. Leia junto do [ROADMAP.md](ROADMAP.md) (seção 2.3).

Última atualização: 2026-07-30 · Estado: **paleta documentada, extração pendente (Fase A2)**

---

## 1. Por que este documento existe

A identidade visual do web **já existe e é coerente** — o que faltava era estar escrita.
Duas evidências de que isso custa caro:

1. **As cores estão hardcoded em mais de 200 lugares** dentro de `app.py`. Trocar a paleta
   hoje é find-replace em 3.280 linhas.
2. **O app mobile abandonado divergiu completamente.** Ele tinha `app_colors.dart` próprio:

   | | Web (produção) | Mobile abandonado |
   |---|---|---|
   | Tema | **escuro** — fundo `#0f172a` | **claro** — fundo `#F4F6F5` |
   | Primária | `#4ade80` verde-limão | `#1B4D3E` verde floresta |
   | Acento | — | `#D4AF37` dourado |

   Eram produtos visualmente diferentes. Quem alternasse entre os dois não reconheceria
   o mesmo sistema. A Trilha 1 recria o mobile do zero — sem este documento, divergiria
   de novo.

---

## 2. Tokens semânticos

**Regra central: nomeie pela função, nunca pela cor.** `sucesso`, não `verde`. Isso é o que
permite que o mesmo componente funcione nos dois temas.

| Token | Uso | Escuro | Claro |
|---|---|---|---|
| `fundo` | fundo da página | `#0f172a` | `#f8fafc` |
| `superficie` | cards, painéis | `#1e293b` | `#ffffff` |
| `borda` | bordas, linhas de grade | `#334155` | `#e2e8f0` |
| `texto` | texto principal | `#f1f5f9` | `#0f172a` |
| `texto_secundario` | legendas, apoio | `#94a3b8` | `#475569` |
| `texto_terciario` | texto desabilitado | `#64748b` | `#64748b` |
| `primaria` | marca, ação principal | `#4ade80` | `#15803d` |
| `sucesso` | dentro da meta, lucro, saudável | `#4ade80` | `#15803d` |
| `atencao` | alerta, carência, estoque baixo | `#fbbf24` | `#b45309` |
| `perigo` | prejuízo, óbito, fora da meta | `#f87171` | `#b91c1c` |
| `info` | neutro informativo | `#22d3ee` | `#0e7490` |
| `destaque` | séries extras em gráficos | `#a78bfa` | `#6d28d9` |

### ⚠️ O tema claro não é a paleta invertida

`sucesso`, `atencao`, `perigo` e `info` são **deliberadamente mais escuros** no tema claro.
Verde-limão `#4ade80` sobre branco não atinge contraste de leitura — vira texto ilegível.
Ao ajustar qualquer token, verifique contraste de texto (alvo: WCAG AA, 4,5:1) contra
`fundo` e `superficie` do respectivo tema.

Em **área grande de gráfico** (barra, fatia) o contraste exigido é menor que em texto, mas
mantenha o matiz reconhecível: verde tem de continuar parecendo verde nos dois temas, ou a
convenção semântica se perde.

## 3. Quando usar cada cor

Convenção já praticada no web — agora obrigatória:

| Significado | Token | Exemplos reais |
|---|---|---|
| Está bom / dentro da meta / lucro | `sucesso` | GMD ≥ meta, margem positiva, animal pronto |
| Requer atenção, não é erro | `atencao` | carência ativa, estoque abaixo do mínimo, sem pesagem há +30 dias |
| Está ruim / perda | `perigo` | prejuízo, óbito, GMD abaixo da meta |
| Informação neutra | `info` | contagens, referências |

**Nunca use cor como único portador de informação.** No sol, com tela suja ou para quem tem
daltonismo, cor sozinha não comunica. Acompanhe sempre de ícone ou texto — como o app já faz
com 🔴 🟡 🟢 nos alertas.

---

## 4. Mecânica do tema (escolha do usuário)

Decisão: **o tema é opcional e escolhido pelo usuário**, no web e no mobile.

### Implementação
1. **Fonte única:** um dicionário `TEMAS = {"escuro": {...}, "claro": {...}}` com os tokens
   acima. Toda cor de CSS, componente e gráfico vem dele. Nenhum hex literal fora dele.
2. **Preferência por usuário, no servidor.** Guardar em coluna `users.theme`
   (mudança de schema → seguir R4 do ROADMAP). Motivo de ser no servidor e não só local:
   **a preferência acompanha o usuário para o celular**, mantendo a experiência consistente.
3. **Web:** a preferência gera o bloco `<style>` e o `PLOTLY`/`_layout()`. O `_layout()`
   **já centraliza** o estilo dos gráficos — é o ponto de entrada natural.
4. **Mobile:** `ThemeMode` do Flutter. O `app_colors.dart` é **gerado a partir** desta
   paleta, nunca escrito à mão. Ofereça também **"seguir o sistema"** — no celular
   costuma ser o melhor padrão.
5. **Padrão inicial: escuro**, que é o tema atual. Assim ninguém percebe mudança visual ao
   introduzir o recurso.

### Ordem de implantação
Extrair as constantes (Fase A2) → introduzir os dois temas com o escuro como padrão →
adicionar o seletor e a persistência → mobile já nasce com os dois.

**Custo contínuo a aceitar:** toda tela passa a precisar de conferência nos dois temas.
Isso dobra a revisão visual — é o preço da opção, e é justo, mas precisa ser sabido.

---

## 5. Componentes existentes

Inventário do que já existe no web. **Componente novo entra nesta tabela**, com equivalente
mobile — é o que impede a divergência.

| Classe CSS (web) | Uso | Equivalente Flutter |
|---|---|---|
| `.page-title` | título da página | `Text` com estilo `titleLarge` |
| `.card` | painel neutro | `Card` |
| `.card-green` / `.card-yellow` / `.card-red` | painel com status | `Card` + borda `sucesso`/`atencao`/`perigo` |
| `.badge-green` / `.badge-yellow` / `.badge-red` / `.badge-blue` / `.badge-gray` | etiqueta de status | `Chip` |
| `.hist-item` | linha de histórico | `ListTile` |
| `.keypad-display` | visor do teclado numérico | display do teclado |

Gráficos: sempre via `PLOTLY` + `_layout()` — nunca montar layout de gráfico à mão.

---

## 6. Regras de campo (requisito funcional, não estética)

O Modo Campo é usado **no sol, com luva, uma mão, tela suja e às vezes sem sinal**. Portanto:

- **Alvo de toque grande.** O `_teclado_numerico` é a referência do que funciona.
- **Poucos passos por operação.** Registrar pesagem não deve exigir navegação profunda.
- **Contraste alto** e hierarquia legível de relance — não de leitura atenta.
- **Nada essencial escondido** atrás de *hover* ou gesto: no campo, não existe mouse.
- **Confirmação explícita** em ação irreversível (óbito, venda) — errar de luva é fácil.
- **Estado visível.** Se algo não salvou, tem de aparecer. Vale ainda mais no mobile v2,
  com fila de sincronização.

### Questão em aberto: qual tema lê melhor sob sol direto?
Tema escuro é ótimo no escritório. Sob sol a pino, tema claro com brilho alto costuma ler
melhor — e talvez não seja coincidência que o app abandonado tenha ido para o claro. **Isso
se resolve no pasto ao meio-dia, não em discussão.** Como o tema virou opção do usuário, a
decisão deixa de ser travada: teste em campo e escolha o **padrão** do mobile com base nisso.

---

## 7. Checklist de mudança visual

- [ ] Nenhum hex literal fora do dicionário de temas
- [ ] Cor escolhida pelo **significado** (`sucesso`), não pela aparência (`verde`)
- [ ] Verificado nos **dois** temas
- [ ] Contraste de texto adequado nos dois (AA, 4,5:1)
- [ ] Informação não depende **só** de cor (tem ícone ou texto)
- [ ] Componente novo registrado na seção 5, com equivalente mobile
- [ ] Alvo de toque adequado se a tela for usada no campo
- [ ] Gráfico usando `PLOTLY`/`_layout()`, não layout manual
