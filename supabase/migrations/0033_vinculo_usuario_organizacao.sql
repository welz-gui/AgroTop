-- Vínculo do usuário com organização e propriedade (D1 do plano de rastreabilidade)
--
-- CONTEXTO
--   A identidade fica na tabela `users` (ADR 0002) e o modelo-alvo de tenancy é
--   organização → produtor → propriedade (ADR 0004). Mas `users` não dizia a que
--   organização nem a que propriedade a pessoa pertence, então nada na sessão, no
--   JWT ou na auditoria sabia "quem é de quem". Esta migration só cria o vínculo:
--   o isolamento por organização continua sendo instância separada no piloto.
--
-- ESTRUTURA
--   users.organizacao_id — organização do usuário. NULL = ainda não vinculado.
--   users.property_id    — propriedade de atuação. NULL = todas as da organização.
--   audit_logs.organizacao_id / property_id — vínculo do autor no momento da ação
--     (sem FK de propósito: a trilha é histórica e append-only).
--
--   Backfill: se existe EXATAMENTE uma organização, os usuários sem vínculo ficam
--   com ela. Com várias, adivinhar seria inventar pertencimento: ficam NULL.
--
-- ROLLBACK
--   DROP INDEX IF EXISTS idx_users_organizacao, idx_users_property;
--   ALTER TABLE public.users DROP COLUMN IF EXISTS organizacao_id, DROP COLUMN IF EXISTS property_id;
--   ALTER TABLE public.audit_logs DROP COLUMN IF EXISTS organizacao_id, DROP COLUMN IF EXISTS property_id;

BEGIN;

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS organizacao_id text REFERENCES public.organizacoes(id);
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS property_id text REFERENCES public.properties(id);

CREATE INDEX IF NOT EXISTS idx_users_organizacao ON public.users (organizacao_id);
CREATE INDEX IF NOT EXISTS idx_users_property ON public.users (property_id);

ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS organizacao_id text;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS property_id text;

UPDATE public.users
   SET organizacao_id = (SELECT id FROM public.organizacoes)
 WHERE organizacao_id IS NULL
   AND (SELECT count(*) FROM public.organizacoes) = 1;

COMMIT;
