-- Colunas para o fluxo de caixa não contar o mesmo evento duas vezes
-- (Trilha 3 — ROADMAP §5, "fluxo realizado e projetado")
--
-- CONTEXTO
--   `services/caixa.py::fluxo_de_caixa` e `em_aberto` (spec 0021) existiam
--   desde a etapa anterior e nunca tiveram consumidor: as duas funções
--   precisam de `vencimento`/`pagamento` reais para separar "em aberto" de
--   "já liquidado", e nenhuma fonte carregava um vencimento de verdade até
--   `contas_pagar`/`contas_receber` existirem (migrations 0018/0019).
--
--   Ligar isso expôs um problema novo: uma compra com nota fiscal e
--   parcelas aparece em `insumo_transactions` (reconhecimento por
--   competência, spec 0034) **e** em `contas_pagar` (cronograma de caixa,
--   0018) — mesma economia, duas linhas. Mesma coisa para venda a prazo:
--   `sales` (competência) e `contas_receber` (cronograma, 0019). Sem uma
--   forma de saber "esta linha já tem cronograma em outra tabela", o fluxo
--   de caixa contaria a mesma compra/venda duas vezes.
--
-- DUAS COLUNAS NOVAS, ADITIVAS
--   sales.a_prazo               — 1 quando a venda usou `register_sale(...,
--                                  a_prazo=True)`; o caixa dela mora em
--                                  `contas_receber`, não em `sales` direto.
--   insumo_transactions.compra_id — preenchido só quando a entrada veio de
--                                  `repositories.compras.registrar` (compra
--                                  com nota fiscal); o caixa dela mora em
--                                  `contas_pagar`. Entrada avulsa
--                                  (`add_insumo_entry`) continua NULL —
--                                  não tem parcela, é caixa imediato.
--
-- ADITIVA
--   Duas colunas novas em tabelas existentes, ambas com default seguro
--   (0 / NULL). Nenhuma linha existente muda de valor visível: toda venda e
--   toda entrada de estoque já gravada antes desta migration é,
--   corretamente, "sem parcela" (não tinha como ter — contas_pagar/
--   contas_receber não existiam ainda).
--
-- ROLLBACK
--   ALTER TABLE sales DROP COLUMN IF EXISTS a_prazo;
--   ALTER TABLE insumo_transactions DROP COLUMN IF EXISTS compra_id;
--   -- Depois: reverter o commit e regenerar baseline e retrato.

BEGIN;

ALTER TABLE sales ADD COLUMN IF NOT EXISTS a_prazo INTEGER NOT NULL DEFAULT 0;
COMMENT ON COLUMN sales.a_prazo IS
    '1 = receita rastreada via contas_receber, não contar de novo no fluxo de caixa.';

ALTER TABLE insumo_transactions ADD COLUMN IF NOT EXISTS compra_id TEXT
    REFERENCES compras(id);
COMMENT ON COLUMN insumo_transactions.compra_id IS
    'Preenchido só quando vem de repositories.compras.registrar — a despesa '
    'dessa entrada é rastreada via contas_pagar, não contar de novo no fluxo de caixa.';

COMMIT;
