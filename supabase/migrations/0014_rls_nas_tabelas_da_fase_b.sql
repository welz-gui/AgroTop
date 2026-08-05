-- 0014 — RLS nas tabelas da Fase B + revogação dos grants públicos
--
-- POR QUE
-- O linter do Supabase acusou `rls_disabled_in_public` em 11 tabelas, e todas
-- as 11 nasceram nas migrations 0002–0012 (Fase B). As tabelas anteriores já
-- tinham RLS. Ou seja: não foi uma decisão, foi um passo que faltou no
-- checklist de `supabase/README.md` e que o `testar_baseline.py` não cobre —
-- a própria dívida nº 10 do ROADMAP dizia "o baseline não cobre RLS", e o
-- buraco abriu mesmo assim. Documentar um risco não o elimina.
--
-- O QUE ESTAVA EXPOSTO
-- O papel `anon` tem, por padrão do Supabase, SELECT/INSERT/UPDATE/DELETE em
-- tudo no schema `public`. Sem RLS, essas 11 tabelas ficam legíveis e
-- graváveis por qualquer portador de uma chave anon válida via PostgREST —
-- incluindo `produtores.documento` (CPF/CNPJ), a trilha `audit_logs` e os
-- eventos regulatórios de `animal_events`.
--
-- POR QUE NÃO QUEBRA A PRODUÇÃO
-- O app conecta como `postgres`, que tem `rolbypassrls = true`. RLS não se
-- aplica a ele. Quem passa a ser barrado é `anon`/`authenticated`, que este
-- app nunca usa: a autenticação é a tabela `users` com sessão em cookie, e o
-- ADR 0002 **vetou o Supabase Auth**.
--
-- ROLLBACK
--   ALTER TABLE <tabela> DISABLE ROW LEVEL SECURITY;
--   GRANT ALL ON <tabela> TO anon, authenticated;

BEGIN;

-- ── 1. RLS nas 11 tabelas da Fase B ──────────────────────────────────────────
-- Sem política nenhuma, de propósito: RLS ligado e zero políticas = negar tudo
-- para quem não tem BYPASSRLS. É o estado correto para um app que não usa
-- PostgREST. Política só entra quando existir consumidor que precise dela.
ALTER TABLE public.animal_identifiers   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.animal_events        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizacoes         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.produtores           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.properties           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.partos               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.movimentacoes        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.movimentacao_animais ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dispositivos         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.regras_regulatorias  ENABLE ROW LEVEL SECURITY;

-- ── 2. Revogar os grants de `anon` e `authenticated` ─────────────────────────
-- RLS sozinho não basta: TRUNCATE é privilégio de tabela e **não passa por
-- RLS**. Hoje o PostgREST não expõe TRUNCATE por HTTP, então isso é risco
-- latente e não porta aberta — mas manter o grant é confiar que a superfície
-- do PostgREST nunca vai crescer.
--
-- Revogar é seguro porque nada neste projeto usa PostgREST: o acesso é
-- `_conn()` por DATABASE_URL (regra R1), como `postgres`.
-- Guardado por existência do papel: `anon` e `authenticated` são do Supabase, e
-- o ADR 0002 diz que o provedor é substituível. Um Postgres puro não os tem.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM anon, authenticated';
        EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated';
        EXECUTE 'REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated';
        -- E o padrão para tabelas futuras, senão a próxima migration reabre o buraco.
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                'REVOKE ALL ON TABLES FROM anon, authenticated';
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                'REVOKE ALL ON SEQUENCES FROM anon, authenticated';
    END IF;
END $$;

-- ── 3. Remover a herança morta do Supabase Auth ──────────────────────────────
-- Estas políticas e funções pressupõem `auth.uid()` e o papel `authenticated`,
-- que o ADR 0002 vetou. Nunca foram exercidas: o app autentica pela tabela
-- `users`. Mantê-las é deixar código de segurança que ninguém testa parecendo
-- proteção que existe.
--
-- As duas funções são SECURITY DEFINER e executáveis por `anon` via
-- /rest/v1/rpc/ — dois avisos separados do linter.
--
-- Verificado antes de aplicar (2026-08-05): `get_current_user_role()` consulta
-- `public.profiles`, tabela que a migration 0001 já removeu. Não são apenas
-- "nunca exercidas" — chamá-las hoje devolve "relation public.profiles does
-- not exist". É função quebrada, exposta a `anon` por RPC.
DROP POLICY IF EXISTS "Permitir leitura de animais para autenticados"      ON public.animals;
DROP POLICY IF EXISTS "Permitir inserção de animais por operadores e gestores" ON public.animals;
DROP POLICY IF EXISTS "Permitir atualização de animais por admin e gestor" ON public.animals;
DROP POLICY IF EXISTS "Permitir exclusão de animais apenas por admin"      ON public.animals;
DROP POLICY IF EXISTS "Permitir leitura de pesagens"                       ON public.weighings;
DROP POLICY IF EXISTS "Permitir registro de pesagens por operador"         ON public.weighings;
DROP POLICY IF EXISTS "Permitir exclusão de pesagens apenas por admin"     ON public.weighings;
DROP POLICY IF EXISTS "Permitir leitura de medicamentos"                   ON public.medications;
DROP POLICY IF EXISTS "Permitir aplicar medicamento por operador"          ON public.medications;
DROP POLICY IF EXISTS "Restringir vendas para admin e gestor"              ON public.sales;
DROP POLICY IF EXISTS "Restringir custos fixos para admin e gestor"        ON public.fixed_costs;

-- `get_current_user_role()` também é usada por duas políticas em
-- `storage.objects`, do bucket `animal-photos` — descoberto ao tentar
-- dropar a função sem CASCADE, que o Postgres recusou por dependência.
--
-- Investigado antes de remover: as fotos do animal vão para a coluna
-- `image` (bytea) da própria tabela `animal_photos`, gravada via `_conn()`
-- (database.py). Não há `supabase-py` nas dependências do projeto — o
-- bucket nunca foi usado pelo código, é resíduo da mesma tentativa de
-- integração que criou `profiles` e as duas funções.
DROP POLICY IF EXISTS "Permitir leitura de fotos para usuários autenticados" ON storage.objects;
DROP POLICY IF EXISTS "Permitir envio de fotos por operador e admin"         ON storage.objects;

DROP FUNCTION IF EXISTS public.is_admin_or_gestor();
DROP FUNCTION IF EXISTS public.get_current_user_role();

-- ── 4. search_path fixo no gatilho append-only ───────────────────────────────
-- `fn_recusa_alteracao` roda em todo INSERT/UPDATE das tabelas append-only.
-- Sem `search_path` fixo, quem controlar o search_path da sessão pode
-- influenciar que objeto o corpo da função resolve. É a garantia do §6.3 que
-- está em jogo, então não é aviso cosmético.
ALTER FUNCTION public.fn_recusa_alteracao() SET search_path = pg_catalog, public;

COMMIT;
