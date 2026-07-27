# 🛡️ Guia de Aplicação da Segurança e RLS no Supabase

Este repositório contém as políticas de **Row Level Security (RLS)** e configuração de permissões por perfil para o banco de dados PostgreSQL do **AgroTop** no Supabase.

---

## 📋 Perfis de Acesso Definidos

| Perfil | Ver Animais / Pesagens | Inserir Dados no Curral | Editar Registros | Excluir Dados | Acessar Vendas / Financeiro |
|---|:---:|:---:|:---:|:---:|:---:|
| **Admin** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Gestor** | ✅ | ✅ | ✅ | ❌ | ✅ |
| **Operador** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Usuário** | ✅ (Apenas leitura) | ❌ | ❌ | ❌ | ❌ |

---

## 🚀 Como Aplicar no Supabase Dashboard

1. Acesse o [Painel do Supabase](https://supabase.com/dashboard).
2. Selecione o projeto **AgroTop**.
3. No menu lateral esquerdo, clique em **SQL Editor**.
4. Abra o arquivo `supabase/migrations/supabase_security_rls.sql`.
5. Cole todo o conteúdo no editor e clique no botão **Run**.
6. O Supabase confirmará a habilitação das políticas RLS e a criação do bucket `animal-photos`.
