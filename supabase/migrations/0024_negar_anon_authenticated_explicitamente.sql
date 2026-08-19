-- Políticas explícitas de negação para anon/authenticated, nas 37 tabelas
-- de `public` (RLS já ligado, zero políticas até aqui)
--
-- CONTEXTO
--   `supabase/README.md` § "Tabela nova nasce com RLS ligado" documenta a
--   decisão desde a migration 0014: RLS ligado e ZERO políticas = nega
--   tudo para quem não tem BYPASSRLS. O app conecta como `postgres`
--   (bypassa RLS) via `_conn()`/`DATABASE_URL` (R1) — nunca fala com o
--   Postgres por PostgREST, nunca usa `anon`/`authenticated`. O ADR 0002
--   veta Supabase Auth explicitamente; a Trilha 1 (API + mobile, ROADMAP
--   §5, ainda não construída) já está desenhada como "casca fina sobre os
--   services" — herda o mesmo `_conn()` como `postgres`, não expõe
--   PostgREST a um cliente externo. Não há hoje, nem no que está planejado,
--   nenhum vínculo entre um usuário autenticado e uma organização
--   (`users` — a tabela de autenticação real do sistema — não tem
--   `organizacao_id`; não é a mesma coisa que `auth.users` do Supabase).
--   Por isso esta migration não anexa política nenhuma a um vínculo de
--   organização: não existe vínculo para ancorar.
--
--   O que ela faz é fechar a única lacuna real que ainda existe: hoje
--   "zero políticas" só nega acesso *enquanto* os grants de
--   `anon`/`authenticated` continuarem revogados (migration 0014). Se um
--   grant for restaurado por engano no futuro — copiar um snippet de
--   quickstart, ligar PostgREST numa sessão de debug — não há hoje
--   segunda barreira. Com política explícita de negação, há: mesmo com
--   grant restaurado, a política ainda bloqueia toda linha, para todo
--   comando. É a mesma classe de erro que a própria migration 0014 já
--   corrigiu uma vez neste projeto (política órfã da era Supabase Auth)
--   — só que esta é escrita de propósito, documentada, e não presa a uma
--   suposição sobre identidade que o schema não sustenta.
--
--   Isto NÃO é preparação para multi-tenant. Se a AgroTop um dia vender
--   para um segundo produtor, o padrão que o resto do código já usa para
--   isolar dados — `property_id`, `lote_id`, sempre filtrado explícito em
--   `repositories/`, nunca por RLS — é o caminho natural para isso, não
--   este arquivo.
--
-- FORMATO
--   Uma política por tabela, `FOR ALL` (cobre SELECT/INSERT/UPDATE/DELETE
--   num só lugar), `USING (false) WITH CHECK (false)` — nunca avalia
--   verdadeiro para nenhuma linha, em nenhuma direção. `postgres`
--   (BYPASSRLS) continua imune, como sempre foi.
--
-- PORTABILIDADE (ADR 0002 — provedor substituível)
--   `anon`/`authenticated` são papéis do Supabase; um Postgres puro não os
--   tem. Todo o corpo roda dentro do mesmo guard de existência que a
--   migration 0014 já usa para o REVOKE, então aplicar isto num Postgres
--   sem esses papéis é inofensivo (a migration não faz nada, em vez de
--   falhar).
--
-- ROLLBACK
--   DO $$
--   DECLARE r RECORD;
--   BEGIN
--       FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
--           EXECUTE format('DROP POLICY IF EXISTS negar_anon_authenticated ON public.%I', r.tablename);
--       END LOOP;
--   END $$;
--   -- Depois: reverter o commit e regenerar baseline e retrato.

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.animal_costs FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.animal_events FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.animal_identifiers FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.animal_movements FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.animal_photos FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.animals FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.audit_logs FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.category_prices FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.compra_itens FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.compras FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.contas_pagar FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.contas_receber FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.deaths FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.dispositivos FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.evento_sincronizacao FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.feeding_checks FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.feeding_plans FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.fixed_costs FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.fornecedores FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.health_protocols FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.insumo_transactions FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.insumos FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.lotes FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.medications FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.movimentacao_animais FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.movimentacoes FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.organizacoes FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.partos FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.pluviometria FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.produtores FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.properties FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.regras_regulatorias FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.sales FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.sessions FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.settings FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.users FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.weighings FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
    END IF;
END $$;

COMMIT;
