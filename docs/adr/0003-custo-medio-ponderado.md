# ADR 0003 — Custo médio ponderado de insumo e não-retroatividade

- **Status:** Aceito
- **Data:** 2026-07-31
- **Decisores:** Antigravity (agente), mantenedor (AgroTop)
- **Relacionado:** Spec 0010, Trilha 3 (Estoque → Financeiro → Nutrição)

---

## Contexto

Atualmente no AgroTop, o custo unitário de um insumo é **sobrescrito** a cada nova entrada de estoque:

```sql
UPDATE insumos SET current_stock = current_stock + ?, cost_per_unit = ? WHERE id = ?
```

Este comportamento está documentado e caracterizado em `tests/test_regras_negocio.py` (`test_entrada_soma_estoque_e_atualiza_custo`, marcado como `QUIRK:`).

### O problema

Ao comprar 10 kg de ração a R$ 5,00/kg em uma fazenda que já possuía 1.000 kg estocados a R$ 2,00/kg, a consulta atual faz **todo** o saldo de 1.010 kg passar a valer R$ 5,00/kg. Consequentemente:
- O custo do trato diário e o custo acumulado por animal inflam artificialmente;
- Os relatórios de margem e breakeven apresentam distorções graves em relação ao gasto real efetuado.

---

## Decisão

Adotar a função pura `custo_medio_ponderado` (disponibilizada em `services/estoque.py`) para calcular o novo custo unitário de insumos após cada entrada de estoque, ponderando o saldo atual e a quantidade da nova entrada:

$$\text{Novo Custo} = \frac{(\text{saldo\_atual} \times \text{custo\_atual}) + (\text{quantidade\_entrada} \times \text{custo\_entrada})}{\text{saldo\_atual} + \text{quantidade\_entrada}}$$

E adotar as seguintes diretrizes operacionais de transição:

1. **Aplicação NÃO-RETROATIVA (apenas para entradas futuras):**
   A média ponderada passará a ser aplicada a partir da integração da nova função nas operações de entrada de estoque. Entradas anteriores e custos de abate/venda já encerrados **não serão recalculados**.
   *Justificativa:* O `ROADMAP.md` (seção 3) estabelece que resultados numéricos já entregues ao usuário são comportamentos a preservar. Recalcular retroativamente alteraria margens e relatórios históricos que o produtor já utilizou para decisões de venda e gestão.

2. **Gestão do Histórico Misto:**
   No ponto de transição, a primeira entrada utilizará o `cost_per_unit` cadastrado como `custo_atual` e recalculará o novo custo ponderado. O histórico de movimentações anteriores permanece intacto, mantendo a explicabilidade dos relatórios antigos.

3. **Efeito sobre `animal_costs` já gravados:**
   Os registros na tabela `animal_costs` guardam o valor monetário absoluto alocado no momento do lançamento (`cost_value`), e não uma referência dinâmica ao insumo. Portanto, os lançamentos de custos por animal já realizados **não são afetados**.

4. **Tratamento de Estoque Negativo:**
   Caso ocorra `saldo_atual <= 0` (situação real decorrente de lançamentos de baixa efetuados no sistema antes da digitação da nota de compra), assume-se que o lote físico anterior se esgotou antes da reposição. Para evitar artefatos matemáticos (divisão por zero ou custo negativo), o saldo anterior é tratado como base zero para a ponderação, fazendo com que o novo custo unitário assuma `custo_entrada` (se `quantidade_entrada > 0`).

---

## Consequências

### Positivas
- Margens de lucro, breakeven e custo por cabeça/dia passam a refletir com exatidão o valor médio real pago pelos insumos estocados.
- Preservação da integridade e previsibilidade de relatórios históricos emitidos anteriormente.
- Eliminação de picos artificiais de custo causados por compras de pequeno volume a preços pontuais mais altos.

### Negativas / Limitações
- Durante a fase de transição, insumos com estoques antigos mantêm como base de partida o último `cost_per_unit` sobrescrito até que ocorram novas entradas.

---

## Alternativas consideradas

**A. Recálculo retroativo de todo o histórico de entradas e `animal_costs`.**
*Rejeitada:* Alteraria o resultado de relatórios e decisões tomadas no passado pelo produtor, violando as premissas de estabilidade do ROADMAP.md (seção 3).

**B. Manutenção da sobrescrita simples de custo (`QUIRK`).**
*Rejeitada:* Mantém picos irrealistas de custos no sistema, inviabilizando a acurácia necessária para o módulo de Nutrição e Financeiro da Trilha 3.
