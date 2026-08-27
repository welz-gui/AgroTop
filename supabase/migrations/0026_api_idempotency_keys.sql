-- Tabela para chaves de idempotência da API (Spec 0059 — ROADMAP §5 Trilha 1 / ADR 0006)
--
-- CONTEXTO
--   Base para o mobile offline (ADR 0006): evita duplicidade em reenvio de
--   escritas (pesagem, medicamento, movimentação, foto) causados por queda
--   de rede ou timeout.
--
-- ESTRUTURA
--   api_idempotency_keys.idempotency_key — chave única fornecida pelo cliente (PK)
--   api_idempotency_keys.endpoint        — caminho da rota acionada
--   api_idempotency_keys.status_code     — código de status HTTP retornado (ex.: 200, 201)
--   api_idempotency_keys.response_body   — JSON serializado da resposta original
--   api_idempotency_keys.created_at      — timestamp de registro
--
-- SEGURANÇA
--   RLS habilitado e negação explícita via REVOKE de privilégios para anon e authenticated (R26).
--
-- ROLLBACK
--   DROP TABLE IF EXISTS api_idempotency_keys;

BEGIN;

CREATE TABLE IF NOT EXISTS api_idempotency_keys (
    idempotency_key text PRIMARY KEY,
    endpoint        text NOT NULL,
    status_code     integer NOT NULL,
    response_body   text NOT NULL,
    created_at      timestamptz DEFAULT now()
);

ALTER TABLE api_idempotency_keys ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON api_idempotency_keys FROM anon, authenticated';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.api_idempotency_keys FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
    END IF;
END $$;

COMMIT;
