-- ADR 0005 — a fila de sincronização sai de `animal_events`
--
-- CONTEXTO
--   `animal_events.status_sincronizacao` nascia 'pendente' e não havia como
--   mudá-la: o repositório só lia a fila e o gatilho append-only da etapa B2
--   aborta qualquer UPDATE na tabela. O mesmo valia para `identificador_oficial`,
--   que o §6.2 descreve como devolvido pelo sistema oficial — e portanto só pode
--   ser preenchida DEPOIS do registro.
--
--   Efeito prático: o contador nunca zerava, então toda liberação de saída
--   passava a exigir justificativa (§8.4) por um alerta que não informava nada.
--
-- DECISÃO (ADR 0005)
--   Tabela de controle separada, em vez de exceção no gatilho. `animal_events`
--   continua ESTRITAMENTE imutável — nenhum UPDATE, nenhuma exceção. O §10.2 é
--   explícito em manter a camada de integração fora do núcleo, o §10.3 pede
--   catorze situações (não uma bandeira) e o §10.4 pede protocolo, comprovante e
--   dupla conferência enquanto não houver API oficial.
--
--   A alternativa (exceção no gatilho) foi recusada principalmente porque no
--   SQLite ela só se escreve como `BEFORE UPDATE OF <as outras dezenove colunas>`
--   — lista de permissão por omissão, em que toda coluna futura nasce mutável até
--   alguém lembrar de incluí-la.
--
-- APPEND-ONLY TAMBÉM AQUI
--   Tentativa de envio que aconteceu não desacontece. A situação vigente de um
--   par (evento, sistema) é a ÚLTIMA linha — não há coluna "atual" para divergir
--   do histórico. Reusa `fn_recusa_alteracao()`, criada na 0007.
--
-- COLUNAS LEGADAS
--   `animal_events.status_sincronizacao` e `animal_events.identificador_oficial`
--   NÃO são removidas: o §6.2 as prevê e removê-las seria destrutivo sem ganho.
--   Passam a significar o estado de NASCIMENTO do evento, congelado — coerente
--   com a linha ser imutável. Quem responde "já foi comunicado?" é esta tabela.
--
--   Consequência colateral aceita: o índice parcial `idx_eventos_sincronizacao`
--   (WHERE status_sincronizacao <> 'sincronizado') passa a cobrir a tabela
--   inteira, porque a coluna é constante. Fica como está — removê-lo é mudança
--   à parte e sem urgência.
--
-- ADITIVA
--   Uma tabela nova. Nenhuma linha existente é lida, alterada ou apagada.
--
-- ROLLBACK
--   DROP TRIGGER IF EXISTS trg_evsinc_imutavel ON evento_sincronizacao;
--   DROP TABLE IF EXISTS evento_sincronizacao;
--   -- `fn_recusa_alteracao()` NÃO deve ser removida: ela é da 0007 e continua
--   -- servindo `animal_events` e `audit_logs`.
--   -- Depois: reverter o commit e regenerar baseline e retrato.

BEGIN;

CREATE TABLE IF NOT EXISTS evento_sincronizacao (
    id             bigserial PRIMARY KEY,
    evento_id      bigint NOT NULL REFERENCES animal_events(id),
    -- §10.1 prevê vários destinos e o mesmo evento pode ir para mais de um.
    -- Enquanto não há API (§23), 'oficial' é nome neutro de propósito: não
    -- presume qual sistema virá primeiro.
    sistema        text NOT NULL DEFAULT 'oficial',
    -- §10.3 — as catorze situações. Validada em services/sincronizacao.py: a
    -- lista é fechada na norma, ao contrário de `sistema`.
    situacao       text NOT NULL,
    -- §10.4 "registro manual de protocolo" / §6.2 "identificador retornado pelo
    -- sistema oficial".
    protocolo      text,
    mensagem       text,          -- retorno do sistema: erro técnico, ressalva
    observacoes    text,          -- texto de quem operou (reconciliação manual)
    anexos         jsonb,         -- §10.4 "anexação de comprovantes"
    usuario        text,
    conferido_por  text,          -- §10.4 "dupla conferência"
    -- Mesmo par do §6.2: quando a transição ocorreu × quando foi registrada.
    ocorrido_em    timestamptz NOT NULL,
    registrado_em  timestamptz NOT NULL DEFAULT now(),
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- A consulta quente é "última linha deste par (evento, sistema)".
CREATE INDEX IF NOT EXISTS idx_evsinc_evento
    ON evento_sincronizacao USING btree (evento_id, sistema, id DESC);
CREATE INDEX IF NOT EXISTS idx_evsinc_situacao
    ON evento_sincronizacao USING btree (situacao);

-- Mesmo gatilho das outras duas tabelas append-only (§6.3 e §14.1). A mensagem
-- de `fn_recusa_alteracao()` usa TG_TABLE_NAME, então serve a qualquer tabela.
DROP TRIGGER IF EXISTS trg_evsinc_imutavel ON evento_sincronizacao;
CREATE TRIGGER trg_evsinc_imutavel
    BEFORE UPDATE OR DELETE ON evento_sincronizacao
    FOR EACH ROW EXECUTE FUNCTION fn_recusa_alteracao();

COMMIT;
