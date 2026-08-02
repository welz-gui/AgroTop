-- ADR 0004 · etapa B2 — `animal_events` e `audit_logs`
--
-- CONTEXTO
--   §6 do PNIB pede o histórico de eventos do animal; §14.1 pede a trilha de
--   auditoria. Nenhum dos dois existia.
--
--   Etapa **puramente aditiva**: duas tabelas novas, nada existente é tocado.
--   O rollback é um `DROP TABLE`, diferente da etapa 6.
--
-- ADOÇÃO INCREMENTAL (decisão do ADR 0004)
--   Por ora os eventos são REGISTRADOS junto das operações atuais. Derivar o
--   estado do animal a partir deles é passo posterior — fazer as duas coisas de
--   uma vez seria reescrever o sistema num salto.
--
-- APPEND-ONLY DE VERDADE (§6.3 e §14.1)
--   Os gatilhos abaixo recusam UPDATE e DELETE. Sem eles, "append-only" seria
--   uma convenção que o próximo `UPDATE` distraído quebra em silêncio — e a
--   auditoria é justamente o primeiro alvo de quem quer encobrir uma ação.
--
-- EMENDA À R5 (datas)
--   A R5 manda guardar data de NEGÓCIO como texto ISO, e continua valendo. Aqui
--   é diferente: `timestamptz`, com `ocorrido_em` e `registrado_em` separados
--   (§6.2). Em evento regulatório o momento da comunicação tem valor jurídico, e
--   o atraso entre o fato e o registro precisa ser auditável.
--
-- ROLLBACK
--   DROP TRIGGER trg_eventos_imutavel ON animal_events;
--   DROP TRIGGER trg_audit_imutavel   ON audit_logs;
--   DROP FUNCTION fn_recusa_alteracao();
--   DROP TABLE animal_events;
--   DROP TABLE audit_logs;

BEGIN;

CREATE TABLE IF NOT EXISTS animal_events (
    id                    bigserial PRIMARY KEY,
    animal_uuid           text NOT NULL REFERENCES animals(uuid),
    tipo                  text NOT NULL,
    ocorrido_em           timestamptz NOT NULL,
    registrado_em         timestamptz NOT NULL DEFAULT now(),
    propriedade_id        text,          -- chega na etapa B4
    local_interno         text,
    responsavel           text,
    usuario_registro      text,
    origem_informacao     text NOT NULL DEFAULT 'web',
    latitude              double precision,
    longitude             double precision,
    observacoes           text,
    documento             text,
    anexos                jsonb,
    status_sincronizacao  text NOT NULL DEFAULT 'pendente',
    identificador_oficial text,
    versao                integer NOT NULL DEFAULT 1,
    evento_anterior_id    bigint REFERENCES animal_events(id),
    justificativa         text,
    created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_eventos_animal
    ON animal_events USING btree (animal_uuid, ocorrido_em DESC);
CREATE INDEX IF NOT EXISTS idx_eventos_tipo
    ON animal_events USING btree (tipo, ocorrido_em DESC);
-- Índice parcial: a fila de sincronização é curta perto do histórico inteiro.
CREATE INDEX IF NOT EXISTS idx_eventos_sincronizacao
    ON animal_events USING btree (status_sincronizacao)
    WHERE status_sincronizacao <> 'sincronizado';

CREATE TABLE IF NOT EXISTS audit_logs (
    id                 bigserial PRIMARY KEY,
    usuario            text,
    ocorrido_em        timestamptz NOT NULL,
    dispositivo        text,
    ip                 text,
    acao               text NOT NULL,
    entidade           text,
    entidade_id        text,
    registro_anterior  jsonb,
    registro_posterior jsonb,
    motivo             text,
    autorizacao        text,
    origem             text NOT NULL DEFAULT 'web',
    protocolo_externo  text,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_ocorrido
    ON audit_logs USING btree (ocorrido_em DESC);
CREATE INDEX IF NOT EXISTS idx_audit_entidade
    ON audit_logs USING btree (entidade, entidade_id);

-- ─── Append-only imposto pelo banco ──────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_recusa_alteracao() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        '% e append-only (PNIB 6.3 / 14.1): registre uma correcao em vez de alterar',
        TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_eventos_imutavel ON animal_events;
CREATE TRIGGER trg_eventos_imutavel
    BEFORE UPDATE OR DELETE ON animal_events
    FOR EACH ROW EXECUTE FUNCTION fn_recusa_alteracao();

DROP TRIGGER IF EXISTS trg_audit_imutavel ON audit_logs;
CREATE TRIGGER trg_audit_imutavel
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION fn_recusa_alteracao();

COMMIT;
