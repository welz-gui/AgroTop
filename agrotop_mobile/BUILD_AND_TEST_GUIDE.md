# 📲 Guia Prático de Compilação do APK e Homologação (Android)

Este guia orienta o processo de geração do arquivo **APK de Homologação/Teste** do aplicativo **AgroTop Mobile** para instalação em celulares e tablets Android físicos.

---

## 🛠️ Passo a Passo para Gerar o APK de Teste

### 1. Requisitos
- [Flutter SDK instalado](https://docs.flutter.dev/get-started/install) (`>= 3.0.0`)
- Dispositivo Android com a opção **"Depuração USB"** e **"Fontes Desconhecidas"** ativadas.

### 2. Geração do APK no Terminal
Navegue até a pasta do aplicativo no terminal e execute:

```bash
# 1. Entrar na pasta do projeto Flutter
cd agrotop_mobile

# 2. Atualizar as dependências
flutter pub get

# 3. Gerar o APK de teste/homologação
flutter build apk --debug
```

O arquivo APK gerado estará disponível no caminho:
`agrotop_mobile/build/app/outputs/flutter-apk/app-debug.apk`

---

## 📦 Como Instalar o APK no Celular Físico

### Método 1: Envio por WhatsApp / Google Drive / Cabo USB
1. Copie o arquivo `app-debug.apk` para o celular.
2. Abra o gerenciador de arquivos do celular e toque no arquivo.
3. Autorize a instalação de fontes desconhecidas se solicitado pelo Android.
4. Abra o aplicativo **AgroTop Mobile**.

### Método 2: Instalação Direta via Cabo USB (ADB)
Conecte o celular ao computador com cabo USB e execute:
```bash
flutter run --release
```

---

## 🧪 Checklist de Testes de Homologação em Campo

1. **Login & Autenticação**: Testar login com usuário válido do Supabase.
2. **Coleta de Pesagem no Curral**: Digitar novos pesos e verificar o calculador automático de GMD diário.
3. **Câmera & Galeria**: Capturar foto do brinco e testar o envio com indicador de progresso.
4. **Simulador de Terminação**: Testar a resposta da API comparando pasto, semiconfinamento e confinamento.
5. **Comportamento Offline**: Ativar o "Modo Avião" no celular, preencher um cadastro/pesagem e reconectar à internet para verificar a sincronização sem duplicidade.
