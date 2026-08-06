-- B4.3: property_id passa a ser obrigatório em animals e lotes.
--
-- Produção já tinha 0 linhas NULL nas duas colunas (conferido antes de
-- aplicar) — a escrita (add_animal/add_lote) já preenchia desde o B4, faltava
-- só a restrição. `init_db()` foi reordenado para que a hierarquia de
-- propriedades nasça antes dos seeds de lotes/animais, então bancos novos já
-- não dependem de backfill condicional.
--
-- NOTA: aplicada em produção em 2026-08-06 via MCP (nome "property_id_not_null",
-- versão 20260806144941) antes deste arquivo existir — este arquivo fecha a
-- lacuna retroativamente, para o histórico local ficar completo.
ALTER TABLE animals ALTER COLUMN property_id SET NOT NULL;
ALTER TABLE lotes ALTER COLUMN property_id SET NOT NULL;
