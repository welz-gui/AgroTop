# App Flutter da PoC

Aplicativo Android com três telas: login, animais ativos e ficha. Não há dados fictícios
nem cálculo de GMD no Dart. Falhas da API aparecem como erro visível.

## Executar

1. Inicie a API conforme `../api/README.md`.
2. Instale Flutter 3.44.8 (stable) e um Android SDK.
3. Na raiz do repositório:

```bash
cd poc/mobile
flutter pub get
flutter run --dart-define=AGROTOP_API_URL=http://10.0.2.2:8000
```

`10.0.2.2` aponta para a máquina host no emulador Android. Em aparelho físico, use o IP
da máquina na mesma rede. O HTTP sem TLS existe somente para esta PoC local; produção deve
usar HTTPS e remover `android:usesCleartextTraffic="true"`.

## Tema e token

- `lib/app_colors.dart` é gerado de `ui/tema.py` por
  `python poc/mobile/tool/generate_app_colors.py`.
- O menu oferece escuro, claro e seguir o sistema; a preferência visual usa
  `shared_preferences`.
- O JWT usa `flutter_secure_storage`: Android Keystore no Android e Keychain no iOS.
- Validade adotada: 8 horas, equilibrando um turno de trabalho e exposição de um token
  perdido. A renovação fica fora da PoC; expiração volta ao login.

## Verificação

```bash
python poc/mobile/tool/generate_app_colors.py
flutter pub get
flutter analyze
flutter test
flutter build apk --debug --dart-define=AGROTOP_API_URL=http://10.0.2.2:8000
```

O workflow arquivado não pode ser reutilizado sem alteração: fixa Flutter 3.19.6 e o
diretório antigo `agrotop_mobile`. A sequência ainda é válida com Flutter 3.44.8, Java 17,
`poc/mobile` e `actions/upload-artifact@v4`.
