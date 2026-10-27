-- Lote e validade por entrada de estoque (plano de rastreabilidade, Fase 2)
--
-- CONTEXTO
--   A 0034 fez o tratamento registrar princípio ativo, lote e validade do produto APLICADO.
--   Faltava o outro lado: de qual lote e com que validade o produto ENTROU no estoque. Sem isso
--   o sistema não sabe que há medicamento vencido (ou vencendo) na prateleira, que é o dado do
--   alerta "medicamento próximo da validade".
--
-- ESTRUTURA
--   insumo_transactions.lote_produto     — lote da embalagem que entrou (opcional).
--   insumo_transactions.validade_produto — validade, AAAA-MM-DD (opcional).
--     Só faz sentido nas linhas `type = 'entrada'`; nas demais fica nulo.
--     A entrada recusa validade anterior à data de entrada (regra na camada de serviço,
--     `services/validade_estoque.py`; o banco só guarda).
--
--   `insumo_transactions.lote_id` é o PIQUETE (trato por lote); estas colunas são o lote do
--   PRODUTO. Sem backfill: as entradas antigas ficam com NULL ("não informado").
--
-- ROLLBACK
--   ALTER TABLE public.insumo_transactions
--       DROP COLUMN IF EXISTS lote_produto,
--       DROP COLUMN IF EXISTS validade_produto;

BEGIN;

ALTER TABLE public.insumo_transactions ADD COLUMN IF NOT EXISTS lote_produto text;
ALTER TABLE public.insumo_transactions ADD COLUMN IF NOT EXISTS validade_produto text;

COMMIT;
