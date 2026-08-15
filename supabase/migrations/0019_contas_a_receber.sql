-- Contas a receber — parcelas de venda a prazo (Trilha 3 — ROADMAP §5)
--
-- CONTEXTO
--   Segunda fatia da Trilha 3, espelhando a migration 0018 (contas a pagar).
--   Até aqui `register_sale` sempre tratava a venda como recebida na hora: a
--   receita ia para `sales.total_value` no dia da venda, e não havia nenhum
--   jeito de registrar QUANDO o dinheiro chegaria — venda a prazo (comum em
--   pecuária: 30/60/90 dias) simplesmente não existia como conceito.
--
--   `services/compras.py::gerar_parcelas` é reaproveitada aqui, sem
--   duplicar (ROADMAP R8): venda a prazo e compra a prazo dividem o total do
--   mesmo jeito. `repositories/financeiro.py::register_sale` ganhou os
--   parâmetros opcionais `a_prazo`/`num_parcelas`/`primeiro_vencimento` —
--   venda à vista (o padrão, sempre foi) continua sem gerar nenhuma linha
--   aqui, comportamento preservado.
--
-- UMA TABELA NOVA
--   contas_receber — mesma forma de `contas_pagar`, espelhada:
--   `lot_ref` é texto livre (não FK) porque `sales.lot_ref`, a quem ela se
--   refere, também não é chave — só existe para venda de >1 animal ou modo
--   'lote' (ver comentário da própria tabela `sales`, migration 0000).
--
-- ADITIVA
--   Uma tabela nova. Nenhuma tabela existente é alterada; nenhuma linha é
--   lida, alterada ou apagada.
--
-- RLS
--   `supabase/README.md` § "Tabela nova nasce com RLS ligado": RLS habilitado
--   e ZERO políticas — nega tudo para quem não tem BYPASSRLS, mesmo padrão
--   da 0018.
--
-- ROLLBACK
--   DROP TABLE IF EXISTS contas_receber;
--   -- Depois: reverter o commit e regenerar baseline e retrato.

BEGIN;

CREATE TABLE IF NOT EXISTS contas_receber (
    id                BIGSERIAL PRIMARY KEY,
    lot_ref           TEXT,
    comprador         TEXT,
    descricao         TEXT,
    valor             NUMERIC NOT NULL,
    vencimento        TEXT NOT NULL,
    parcela_numero    INTEGER NOT NULL DEFAULT 1,
    parcela_total     INTEGER NOT NULL DEFAULT 1,
    status            TEXT NOT NULL DEFAULT 'aberto',
    data_recebimento  TEXT,
    forma_recebimento TEXT,
    operator          TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN contas_receber.lot_ref IS
    'Texto livre, não FK — espelha sales.lot_ref, que também não é chave.';
COMMENT ON COLUMN contas_receber.status IS 'aberto | recebido | cancelado';

CREATE INDEX IF NOT EXISTS idx_contas_receber_status ON contas_receber (status, vencimento);

ALTER TABLE contas_receber ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON contas_receber FROM anon, authenticated';
    END IF;
END $$;

COMMIT;
