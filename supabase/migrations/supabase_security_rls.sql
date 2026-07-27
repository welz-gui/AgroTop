-- ============================================================================
-- SCRIPT DE SEGURANÇA E ROW LEVEL SECURITY (RLS) — AGROTOP MOBILE
-- ============================================================================
-- Este script configura o controle de acesso granular no PostgreSQL do Supabase,
-- definindo os perfis de acesso (admin, gestor, operador, usuario) e garantindo
-- que os usuários acessem e modifiquem somente os dados permitidos.
-- ============================================================================

-- 1. TABELA DE PERFIS DE USUÁRIO (VINCULADA AO SUPABASE AUTH)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operador' CHECK (role IN ('admin', 'gestor', 'operador', 'usuario')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- 2. FUNÇÕES AUXILIARES DE VERIFICAÇÃO DE PERMISSÃO
CREATE OR REPLACE FUNCTION public.get_current_user_role()
RETURNS TEXT AS $$
DECLARE
    user_role TEXT;
BEGIN
    SELECT role INTO user_role
    FROM public.profiles
    WHERE id = auth.uid();
    
    RETURN COALESCE(user_role, 'usuario');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.is_admin_or_gestor()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN public.get_current_user_role() IN ('admin', 'gestor');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 3. HABILITAÇÃO DE RLS NAS TABELAS DO AGROTOP
ALTER TABLE IF EXISTS public.animals ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.weighings ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.medications ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.sales ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.deaths ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.pluviometria ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.insumos ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.fixed_costs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.animal_costs ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- POLÍTICAS DE RLS PARA TABELA: ANIMALS
-- ============================================================================

-- Leitura: Todos os usuários autenticados podem visualizar os animais
DROP POLICY IF EXISTS "Permitir leitura de animais para autenticados" ON public.animals;
CREATE POLICY "Permitir leitura de animais para autenticados"
ON public.animals FOR SELECT
TO authenticated
USING (true);

-- Inserção: Admin, Gestor e Operador podem cadastrar animais
DROP POLICY IF EXISTS "Permitir inserção de animais por operadores e gestores" ON public.animals;
CREATE POLICY "Permitir inserção de animais por operadores e gestores"
ON public.animals FOR INSERT
TO authenticated
WITH CHECK (public.get_current_user_role() IN ('admin', 'gestor', 'operador'));

-- Edição: Apenas Admin e Gestor podem alterar dados de animais existentes
DROP POLICY IF EXISTS "Permitir atualização de animais por admin e gestor" ON public.animals;
CREATE POLICY "Permitir atualização de animais por admin e gestor"
ON public.animals FOR UPDATE
TO authenticated
USING (public.is_admin_or_gestor())
WITH CHECK (public.is_admin_or_gestor());

-- Exclusão: Estritamente restrito a Administradores
DROP POLICY IF EXISTS "Permitir exclusão de animais apenas por admin" ON public.animals;
CREATE POLICY "Permitir exclusão de animais apenas por admin"
ON public.animals FOR DELETE
TO authenticated
USING (public.get_current_user_role() = 'admin');

-- ============================================================================
-- POLÍTICAS DE RLS PARA TABELA: WEIGHINGS (PESAGENS DE CURRAL)
-- ============================================================================

DROP POLICY IF EXISTS "Permitir leitura de pesagens" ON public.weighings;
CREATE POLICY "Permitir leitura de pesagens"
ON public.weighings FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Permitir registro de pesagens por operador" ON public.weighings;
CREATE POLICY "Permitir registro de pesagens por operador"
ON public.weighings FOR INSERT TO authenticated
WITH CHECK (public.get_current_user_role() IN ('admin', 'gestor', 'operador'));

DROP POLICY IF EXISTS "Permitir exclusão de pesagens apenas por admin" ON public.weighings;
CREATE POLICY "Permitir exclusão de pesagens apenas por admin"
ON public.weighings FOR DELETE TO authenticated
USING (public.get_current_user_role() = 'admin');

-- ============================================================================
-- POLÍTICAS DE RLS PARA TABELA: MEDICATIONS (SANIDADE)
-- ============================================================================

DROP POLICY IF EXISTS "Permitir leitura de medicamentos" ON public.medications;
CREATE POLICY "Permitir leitura de medicamentos"
ON public.medications FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Permitir aplicar medicamento por operador" ON public.medications;
CREATE POLICY "Permitir aplicar medicamento por operador"
ON public.medications FOR INSERT TO authenticated
WITH CHECK (public.get_current_user_role() IN ('admin', 'gestor', 'operador'));

-- ============================================================================
-- POLÍTICAS DE RLS PARA TABELAS FINANCEIRAS (SALES & COSTS)
-- ============================================================================

-- Vendas e Custos Fixos: Restrito para leitura e gravação por Admin e Gestor
DROP POLICY IF EXISTS "Restringir vendas para admin e gestor" ON public.sales;
CREATE POLICY "Restringir vendas para admin e gestor"
ON public.sales FOR ALL TO authenticated
USING (public.is_admin_or_gestor());

DROP POLICY IF EXISTS "Restringir custos fixos para admin e gestor" ON public.fixed_costs;
CREATE POLICY "Restringir custos fixos para admin e gestor"
ON public.fixed_costs FOR ALL TO authenticated
USING (public.is_admin_or_gestor());

-- ============================================================================
-- 4. CONFIGURAÇÃO DE BUCKET E POLÍTICAS DO SUPABASE STORAGE (FOTOS DE ANIMAIS)
-- ============================================================================

INSERT INTO storage.buckets (id, name, public)
VALUES ('animal-photos', 'animal-photos', true)
ON CONFLICT (id) DO NOTHING;

-- Leitura pública das fotos dos animais
DROP POLICY IF EXISTS "Permitir leitura de fotos para usuários autenticados" ON storage.objects;
CREATE POLICY "Permitir leitura de fotos para usuários autenticados"
ON storage.objects FOR SELECT TO authenticated
USING (bucket_id = 'animal-photos');

-- Envio de fotos por Operadores, Gestores e Admin
DROP POLICY IF EXISTS "Permitir envio de fotos por operador e admin" ON storage.objects;
CREATE POLICY "Permitir envio de fotos por operador e admin"
ON storage.objects FOR INSERT TO authenticated
WITH CHECK (
    bucket_id = 'animal-photos' AND
    public.get_current_user_role() IN ('admin', 'gestor', 'operador')
);
