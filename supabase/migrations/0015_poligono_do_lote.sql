-- Perímetro do piquete (`lotes.poligono`) — destrava sobrepostos() (spec 0028/0043)
--
-- CONTEXTO
--   `services/lotacao.py::sobrepostos()` existe desde a spec 0028 (retrabalhada e
--   corrigida na PR #94) e nunca teve como ser chamado de verdade: `lotes` não tinha
--   coluna de polígono. Só `properties.poligono` existia, desde a spec 0032/PR #87,
--   e propriedade não é piquete — a hierarquia é Organização → Produtor →
--   Propriedade → **Lotes/piquetes**, e é nesse último nível que faz sentido
--   perguntar "dois piquetes se sobrepõem?".
--
--   Isso já estava registrado como limitação conhecida na dívida nº 1 do ROADMAP
--   ("a geometria saiu na propriedade, não no piquete") e na spec 0043
--   ("sobrepostos() fica de fora — depende de migration que não existe").
--
-- FORMATO
--   Mesmo formato de `properties.poligono`: GeoJSON como texto, para as duas tabelas
--   falarem a mesma língua e `app.py` reaproveitar os mesmos helpers de leitura/
--   validação (`_ler_poligono`, `geometria_validar`, `geometria_area_ha`, etc.) que já
--   existem para a tela de propriedades.
--
-- POR QUE NÃO LATITUDE/LONGITUDE TAMBÉM
--   `properties` ganhou lat/lon porque a propriedade não tinha NENHUMA localização
--   até então. `lotes` já tem `area_ha`, que cobre o que os cálculos de lotação
--   precisam; o centroide de um piquete, quando for exibido, é derivado do polígono
--   na hora (services.geometria.centroide), não precisa de coluna própria — a
--   mesma escolha que `sobrepostos()` já faz internamente.
--
-- ADITIVA
--   Uma coluna nova, anulável, em tabela existente. Nenhuma linha é lida, alterada
--   ou apagada. `lotes` já tem RLS habilitado (não é tabela nova) — nada a ligar.
--
-- ROLLBACK
--   ALTER TABLE lotes DROP COLUMN IF EXISTS poligono;
--   -- Depois: reverter o commit e regenerar baseline e retrato.

BEGIN;

ALTER TABLE lotes ADD COLUMN IF NOT EXISTS poligono TEXT;
COMMENT ON COLUMN lotes.poligono IS
    'GeoJSON do perímetro do piquete. Alimenta services.lotacao.sobrepostos() '
    '(spec 0028/0043) e a área calculada, no mesmo padrão de properties.poligono.';

COMMIT;
