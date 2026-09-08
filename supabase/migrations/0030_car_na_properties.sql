-- Spec 0082 — perímetro e identificador do imóvel no CAR.
ALTER TABLE public.properties ADD COLUMN IF NOT EXISTS car_numero TEXT;
ALTER TABLE public.properties ADD COLUMN IF NOT EXISTS poligono_car TEXT;
ALTER TABLE public.properties ADD COLUMN IF NOT EXISTS car_area_ha DOUBLE PRECISION;
