-- ADR 0004 · etapa B7 — estoque de dispositivos de identificação (§5)
--
-- CONTEXTO
--   O brinco é um **bem antes de ser identidade**: é comprado em lote, fica em
--   estoque, pode ser perdido ou inutilizado. Nada disso cabia em
--   `animal_identifiers`, que registra o vínculo **já feito**.
--
--   As duas tabelas convivem e têm papéis distintos: `dispositivos` é o objeto
--   físico; `animal_identifiers` é a relação com o animal. Aplicar um brinco
--   escreve nas duas — separá-las deixaria brinco baixado sem vínculo, ou
--   vínculo sem baixa no estoque.
--
-- DOZE ESTADOS (§5.2)
--   A máquina vive em `services/estados_dispositivo.py`. A diferença entre eles
--   não é cosmética: `perdido` volta a `disponivel` se o brinco for encontrado,
--   mas `inutilizado` não volta — inutilizar é ato definitivo, e permitir o
--   retorno destruiria a garantia de que aquele número não será reaplicado.
--
--   `bloqueado_orgao` é o único que o sistema não desfaz sozinho: quem bloqueou
--   foi o órgão oficial, e só ele libera.
--
-- ÍNDICE PARCIAL
--   Um código não pode estar ativo em dois dispositivos (§4.2.1), mas pode ser
--   reaproveitado depois da baixa — mesma lógica de `animal_identifiers`.
--
-- ETAPA ADITIVA · ROLLBACK: DROP TABLE dispositivos;

BEGIN;

CREATE TABLE IF NOT EXISTS dispositivos (
    id                     text PRIMARY KEY,
    codigo_visual          text,
    codigo_eletronico      text,
    tipo                   text NOT NULL DEFAULT 'brinco_visual',
    tecnologia             text,
    fabricante             text,
    fornecedor             text,
    modelo                 text,
    lote                   text,
    data_fabricacao        text,
    data_aquisicao         text,
    proprietario_id        text REFERENCES produtores(id),
    propriedade_destino_id text REFERENCES properties(id),
    padrao_tecnico         text,
    status                 text NOT NULL DEFAULT 'disponivel',
    data_aplicacao         text,
    animal_uuid            text REFERENCES animals(uuid),
    aplicador              text,
    motivo_inutilizacao    text,
    data_baixa             text,
    divergencia            text,   -- §5.3: visual × eletrônico
    created_at             timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_disp_visual_ativo
    ON dispositivos USING btree (codigo_visual)
    WHERE codigo_visual IS NOT NULL
      AND status NOT IN ('inutilizado','devolvido','cancelado');

CREATE INDEX IF NOT EXISTS idx_disp_status ON dispositivos USING btree (status);
CREATE INDEX IF NOT EXISTS idx_disp_lote   ON dispositivos USING btree (lote);
CREATE INDEX IF NOT EXISTS idx_disp_animal ON dispositivos USING btree (animal_uuid);

COMMIT;
