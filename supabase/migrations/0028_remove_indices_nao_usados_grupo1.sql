-- Remove os 2 índices sem uso com evidência objetiva de redundância
-- (aplicada em produção em 2026-08-31; este arquivo fecha a lacuna
-- retroativamente, mesmo padrão da migration 0027).
--
-- CONTEXTO
--   O advisor de performance do Supabase (lint unused_index, nível INFO)
--   apontava 52 índices sem uso. A maioria não tem evidência suficiente
--   para remover ainda (tabela nova, feature em construção, sem tráfego
--   real) — só 2 têm evidência objetiva: existe um índice irmão na mesma
--   tabela já em uso cobrindo o padrão de acesso real, e nenhum dos dois
--   sustenta foreign key (confirmado via pg_constraint antes de aplicar).
--
-- ESTRUTURA
--   weighings.idx_weighings_date (weigh_date DESC)
--     Irmão idx_weighings_animal_date (animal_uuid, weigh_date DESC) já
--     tinha 60 scans — atende o histórico de pesagem por animal (ficha,
--     curva de peso). Índice só por data não corresponde a nenhuma
--     consulta identificada.
--   pluviometria.idx_pluvio_lote (lote_id)
--     lote_id nesta tabela não tem FK declarada. Irmão idx_pluvio_date
--     (read_date) já tinha 31 scans — atende a consulta real (leituras
--     por data).
--
-- ROLLBACK
--   CREATE INDEX CONCURRENTLY idx_weighings_date ON weighings (weigh_date DESC);
--   CREATE INDEX CONCURRENTLY idx_pluvio_lote ON pluviometria (lote_id);

DROP INDEX CONCURRENTLY IF EXISTS public.idx_weighings_date;
DROP INDEX CONCURRENTLY IF EXISTS public.idx_pluvio_lote;
