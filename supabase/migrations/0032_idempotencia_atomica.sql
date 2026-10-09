-- Idempotência atômica da API (Spec 0059 / ADR 0006 — D2 do plano de rastreabilidade)
--
-- CONTEXTO
--   Antes: o endpoint lia a chave, executava a escrita e só então gravava a chave
--   (check-then-act). Duas requisições simultâneas com a mesma chave passavam
--   ambas pela leitura e duplicavam o evento. A chave também não guardava o que
--   foi enviado: reutilizar a chave com outro corpo devolvia a resposta antiga
--   como se a nova escrita tivesse sido feita.
--
--   Agora a chave é reservada (INSERT ... ON CONFLICT DO NOTHING) ANTES da
--   escrita, com o hash do pedido, e só depois recebe a resposta final.
--
-- ESTRUTURA (colunas novas em api_idempotency_keys)
--   request_hash — SHA-256 de endpoint + corpo; mesma chave com hash diferente → 422
--   estado       — 'em_andamento' (reservada, escrita em curso) | 'concluida'
--   reservada_em — instante UTC (ISO 8601, texto) da reserva; reserva 'em_andamento'
--                  mais antiga que o prazo é considerada abandonada e pode ser retomada
--
--   Linhas já existentes ficam 'concluida' e sem hash: continuam respondendo do
--   cache, sem checagem de corpo.
--
-- ROLLBACK
--   ALTER TABLE public.api_idempotency_keys
--       DROP COLUMN IF EXISTS request_hash,
--       DROP COLUMN IF EXISTS estado,
--       DROP COLUMN IF EXISTS reservada_em;

BEGIN;

ALTER TABLE public.api_idempotency_keys ADD COLUMN IF NOT EXISTS request_hash text;
ALTER TABLE public.api_idempotency_keys ADD COLUMN IF NOT EXISTS estado text NOT NULL DEFAULT 'concluida';
ALTER TABLE public.api_idempotency_keys ADD COLUMN IF NOT EXISTS reservada_em text;

COMMIT;
