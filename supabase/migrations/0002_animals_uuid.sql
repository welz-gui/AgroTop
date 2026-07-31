-- ADR 0004 · etapa B1.1 — chave surrogate em `animals`
--
-- CONTEXTO
--   O PNIB (§4.1) exige identificador interno **imutável e separado do brinco**:
--   trocar o brinco não pode trocar a identidade do animal. Hoje `animals.id` É
--   o número do brinco e é PK referenciada por 8 tabelas.
--
--   Esta é a primeira de seis etapas, todas reversíveis. Aqui apenas se ACRESCENTA
--   a coluna: nada é removido, nenhuma FK muda, e o sistema segue funcionando
--   exatamente como antes.
--
-- POR QUE O UUID É GERADO NA APLICAÇÃO, E NÃO PELO BANCO
--   `gen_random_uuid()` não existe no SQLite, e a compatibilidade dupla é
--   requisito do projeto (ROADMAP R5 e ADR 0002). A geração fica em
--   `repositories.animais.novo_uuid()`, e o preenchimento de linhas antigas em
--   `database._backfill_uuids()`, que é idempotente.
--
-- VERIFICADO ANTES DE APLICAR (2026-07-31)
--   backup completo tirado e conferido: backups/agrotop_20260731_204544.zip
--   14 animais em produção, todos passarão a ter uuid
--
-- ROLLBACK
--   ALTER TABLE animals DROP COLUMN uuid;
--   (seguro nesta etapa: nada referencia a coluna ainda)

ALTER TABLE animals ADD COLUMN IF NOT EXISTS uuid TEXT;

-- Unicidade sem impedir NULL: linhas antigas ficam nulas até o backfill rodar.
CREATE UNIQUE INDEX IF NOT EXISTS idx_animals_uuid ON animals (uuid);
