# 📱 AgroTop Mobile (Flutter Application)

Aplicativo nativo para **Android** e **iOS** de gestão de gado de corte, funcionando em paralelo com a versão web Streamlit e integrado com **Supabase** e **API Python FastAPI**.

---

## 🚀 Como Executar Localmente

### Pré-requisitos
- Flutter SDK `>=3.0.0`
- Dart SDK `>=3.0.0`
- Android Studio / Xcode

### Comandos de Execução
```bash
# Entrar no diretório do projeto
cd agrotop_mobile

# Obter dependências
flutter pub get

# Executar no Emulador Android ou dispositivo conectado
flutter run
```

---

## 🛠️ Estrutura do Projeto (Clean Architecture)

- `lib/core/`: Cores, tema Material Design 3, formatadores (R$, CPF, datas BR) e clientes Supabase/API HTTP.
- `lib/features/auth/`: Login, recuperação de senha e autenticação JWT Supabase.
- `lib/features/dashboard/`: Painel Home com estatísticas KPI, seletor de piquetes e ações rápidas.
- `lib/features/animal/`: Listagem de animais, busca inteligente, ficha do animal e cadastro.
- `lib/features/terminacao/`: Simulador de estratégias de terminação integrado com a API Python.
- `lib/shared/`: Widgets reutilizáveis (CustomButton, CustomTextField, SyncStatusBadge).
