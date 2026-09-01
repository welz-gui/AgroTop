-- Declara três foreign keys que existiam só como convenção no código.
--
-- Aplicada em produção em 2026-09-01 via MCP `apply_migration` (nome
-- `fks_faltantes`), com a `main` em 11cc0a9. Este arquivo fecha a lacuna
-- retroativamente, mesmo padrão das migrations 0027 e 0028.
--
-- Conferido depois de aplicar, por consulta a pg_constraint:
--   animal_identifiers_animal_uuid_fkey  FOREIGN KEY (animal_uuid) REFERENCES animals(uuid)
--   medications_protocol_id_fkey         FOREIGN KEY (protocol_id) REFERENCES health_protocols(id)
--   insumo_transactions_lote_id_fkey     FOREIGN KEY (lote_id) REFERENCES lotes(id)
--
-- CONTEXTO
--   A auditoria de índices sem uso de 2026-09-01 encontrou, de passagem, três
--   colunas que apontam para outra tabela sem FK declarada. O relatório tratou
--   isso como nota de rodapé de uma seção sobre remover índice; é o contrário:
--   índice sem uso custa 8 kB, integridade referencial ausente custa dado
--   inconsistente que ninguém detecta.
--
--   `animal_identifiers.animal_uuid` é o caso sério. O AgroTop existe para
--   rastreabilidade PNIB: identificador apontando para animal inexistente é
--   exatamente a classe de erro que o sistema deveria tornar impossível, e o
--   banco não estava impedindo.
--
-- VERIFICADO ANTES DE ESCREVER (consulta somente leitura em produção,
-- 2026-09-01):
--
--   animal_identifiers.animal_uuid -> animals.uuid
--       14 linhas · 0 nulos · 0 órfãos · coluna já NOT NULL
--   medications.protocol_id -> health_protocols.id
--       24 linhas · 24 nulos · 0 órfãos · anulável
--   insumo_transactions.lote_id -> lotes.id
--        2 linhas ·  2 nulos · 0 órfãos · anulável
--
--   Os três lados referenciados têm PK/UNIQUE (requisito da FK). Nenhuma linha
--   bloqueia a criação das constraints.
--
-- SEM ON DELETE
--   Mesma escolha das FKs existentes (`fk_animal_costs_animal_uuid` e irmãs):
--   sem cláusula, ou seja, NO ACTION. Apagar um animal que tem identificador
--   passa a ser recusado — que é o comportamento correto num sistema de
--   rastreabilidade, onde o histórico não some.
--
-- NULOS CONTINUAM PERMITIDOS
--   FK não restringe NULL. `medications.protocol_id` e
--   `insumo_transactions.lote_id` seguem anuláveis: nem todo medicamento vem de
--   protocolo, nem toda transação de insumo é de um lote.

BEGIN;

ALTER TABLE public.animal_identifiers
    ADD CONSTRAINT animal_identifiers_animal_uuid_fkey
    FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);

ALTER TABLE public.medications
    ADD CONSTRAINT medications_protocol_id_fkey
    FOREIGN KEY (protocol_id) REFERENCES public.health_protocols(id);

ALTER TABLE public.insumo_transactions
    ADD CONSTRAINT insumo_transactions_lote_id_fkey
    FOREIGN KEY (lote_id) REFERENCES public.lotes(id);

COMMIT;

-- ROLLBACK
--   BEGIN;
--   ALTER TABLE public.animal_identifiers  DROP CONSTRAINT animal_identifiers_animal_uuid_fkey;
--   ALTER TABLE public.medications         DROP CONSTRAINT medications_protocol_id_fkey;
--   ALTER TABLE public.insumo_transactions DROP CONSTRAINT insumo_transactions_lote_id_fkey;
--   COMMIT;
--
-- ÍNDICES
--   As três colunas já têm índice (`idx_ident_animal`, `idx_medications_protocol`,
--   `idx_insumo_trans_lote`) — os mesmos que a auditoria de 2026-09-01 cogitou
--   remover por `idx_scan = 0`. Com a FK declarada eles deixam de ser
--   candidatos: passam a sustentar a verificação de integridade referencial.
