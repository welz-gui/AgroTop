-- Tabela para refresh tokens revogáveis da API (Spec 0044 — ROADMAP §5 Trilha 1)
--
-- CONTEXTO
--   A API de produção em FastAPI (backend_api) emite tokens JWT de curta
--   duração (15 min) para acesso e refresh tokens (7 dias) para renovação.
--   Para suportar logout e revogação imediata de sessões sem invalidar todos
--   os tokens de um usuário, os refresh tokens são persistidos nesta tabela.
--   Ao fazer logout (/auth/logout), o refresh token é marcado como revogado
--   (revoked = 1).
--
-- ESTRUTURA
--   api_refresh_tokens.token      — token de refresh (chave primária)
--   api_refresh_tokens.user_id    — FK para users(id)
--   api_refresh_tokens.expires_at — data/hora ISO de expiração
--   api_refresh_tokens.revoked    — flag 0 (válido) / 1 (revogado)
--   api_refresh_tokens.created_at — data/hora de emissão
--
-- SEGURANÇA
--   RLS habilitado e negação explícita via REVOKE de privilégios para anon e authenticated (R26).
--
-- ROLLBACK
--   DROP TABLE IF EXISTS api_refresh_tokens;
--   -- Depois: reverter o commit e regenerar baseline e retrato.

BEGIN;

CREATE TABLE IF NOT EXISTS api_refresh_tokens (
    token      text PRIMARY KEY,
    user_id    integer NOT NULL REFERENCES users(id),
    expires_at text NOT NULL,
    revoked    integer NOT NULL DEFAULT 0,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_refresh_tokens_user ON api_refresh_tokens (user_id);

ALTER TABLE api_refresh_tokens ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON api_refresh_tokens FROM anon, authenticated';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.api_refresh_tokens FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
    END IF;
END $$;

COMMIT;
