-- Compra de insumo com documento fiscal e contas a pagar (Trilha 3 — ROADMAP §5)
--
-- CONTEXTO
--   "Compra atualiza estoque e financeiro na mesma operação" é o "Pronto quando"
--   da Trilha 3 (Estoque → Financeiro → Nutrição). Até aqui só existia entrada
--   avulsa de estoque (`add_insumo_entry`): 1 insumo por lançamento, sem
--   fornecedor, sem documento fiscal, sem parcelamento, e sem nenhum rastro no
--   financeiro — comprar gerava saldo de estoque, nunca uma conta a pagar.
--
--   `services/compras.py` (parcelamento e total da nota, puro) e
--   `repositories/compras.py::registrar` (a operação atômica de verdade) são a
--   ligação. O custo médio ponderado por item continua sendo o de sempre —
--   ver docs/adr/0003-custo-medio-ponderado.md — esta migration não muda essa
--   regra, só dá a ela um documento fiscal e um fornecedor para pendurar em.
--
-- TRÊS TABELAS NOVAS
--   compras       — cabeçalho da nota (fornecedor, documento, datas, total).
--   compra_itens  — 1 linha por insumo da nota, com custo unitário e subtotal.
--   contas_pagar  — parcelas geradas a partir do total da compra. `compra_id`
--                   é anulável de propósito: nem toda conta a pagar nasce de
--                   uma compra de insumo (aluguel, prestador — fora do escopo
--                   desta migration, mas a coluna já não bloqueia isso depois).
--
-- POR QUE NÃO REUTILIZAR `fornecedores`
--   `fornecedores` (migration 0000, baseline) é "Fornecedores / Origem" — a
--   origem do gado comprado, não um fornecedor de insumo. Misturar os dois
--   domínios numa tabela só criaria uma FK que mentiria sobre o que representa.
--   `compras.fornecedor_id` aponta para `fornecedores` como opção (mesmo
--   cadastro, quando fizer sentido: um fornecedor pode vender gado e ração),
--   mas `fornecedor_nome` (texto livre) é o caminho padrão — nem todo
--   fornecedor de insumo está cadastrado, e a compra não pode esperar isso.
--
-- ADITIVA
--   Três tabelas novas. Nenhuma tabela existente é alterada; nenhuma linha é
--   lida, alterada ou apagada.
--
-- RLS
--   `supabase/README.md` § "Tabela nova nasce com RLS ligado": RLS habilitado
--   e ZERO políticas nas três — nega tudo para quem não tem BYPASSRLS. O app
--   conecta como `postgres` (bypassa RLS); `anon`/`authenticated` não têm
--   consumidor e têm os grants revogados explicitamente (REVOKE não é
--   redundante com RLS: TRUNCATE é privilégio de tabela, não passa por RLS).
--
-- ROLLBACK
--   DROP TABLE IF EXISTS contas_pagar;
--   DROP TABLE IF EXISTS compra_itens;
--   DROP TABLE IF EXISTS compras;
--   -- Depois: reverter o commit e regenerar baseline e retrato.

BEGIN;

CREATE TABLE IF NOT EXISTS compras (
    id                TEXT PRIMARY KEY,
    fornecedor_id     INTEGER REFERENCES fornecedores(id),
    fornecedor_nome   TEXT,
    documento_numero  TEXT,
    documento_serie   TEXT,
    data_emissao      TEXT NOT NULL,
    data_recebimento  TEXT NOT NULL,
    valor_total       NUMERIC NOT NULL DEFAULT 0,
    operator          TEXT,
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE compras IS
    'Cabeçalho da compra de insumo com documento fiscal (Trilha 3, ROADMAP §5). '
    'fornecedor_id é opcional — fornecedor_nome (texto livre) é o caminho padrão.';

CREATE TABLE IF NOT EXISTS compra_itens (
    id             BIGSERIAL PRIMARY KEY,
    compra_id      TEXT NOT NULL REFERENCES compras(id),
    insumo_id      INTEGER NOT NULL REFERENCES insumos(id),
    quantidade     NUMERIC NOT NULL,
    custo_unitario NUMERIC NOT NULL,
    subtotal       NUMERIC NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_compra_itens_compra ON compra_itens (compra_id);

CREATE TABLE IF NOT EXISTS contas_pagar (
    id              BIGSERIAL PRIMARY KEY,
    compra_id       TEXT REFERENCES compras(id),
    fornecedor_nome TEXT,
    descricao       TEXT,
    valor           NUMERIC NOT NULL,
    vencimento      TEXT NOT NULL,
    parcela_numero  INTEGER NOT NULL DEFAULT 1,
    parcela_total   INTEGER NOT NULL DEFAULT 1,
    status          TEXT NOT NULL DEFAULT 'aberto',
    data_pagamento  TEXT,
    forma_pagamento TEXT,
    operator        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN contas_pagar.compra_id IS
    'Anulável: nem toda conta a pagar precisa nascer de uma compra de insumo.';
COMMENT ON COLUMN contas_pagar.status IS 'aberto | pago | cancelado';

CREATE INDEX IF NOT EXISTS idx_contas_pagar_status ON contas_pagar (status, vencimento);
CREATE INDEX IF NOT EXISTS idx_contas_pagar_compra ON contas_pagar (compra_id);

ALTER TABLE compras       ENABLE ROW LEVEL SECURITY;
ALTER TABLE compra_itens  ENABLE ROW LEVEL SECURITY;
ALTER TABLE contas_pagar  ENABLE ROW LEVEL SECURITY;

-- Uma revogação por tabela, para o teste estático de
-- tests/test_rls_nas_migrations.py reconhecer cada uma individualmente
-- (o bloco `ALL TABLES IN SCHEMA public` da 0014 cobriria tudo, mas essa
-- forma cobre só o que já existia *naquele momento* — para tabela nova a
-- própria migration precisa nomeá-la, ver a nota "a partir da 0013" no teste).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON compras FROM anon, authenticated';
        EXECUTE 'REVOKE ALL ON compra_itens FROM anon, authenticated';
        EXECUTE 'REVOKE ALL ON contas_pagar FROM anon, authenticated';
    END IF;
END $$;

COMMIT;
