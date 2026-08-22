# AgroTop Mobile v1a

Aplicativo Flutter para login, consulta de animais ativos, ficha do animal e registro de
pesagem. O app consome somente o contrato HTTP definido pela spec 0044; regras e
indicadores de negócio continuam no servidor.

## Executar

Instale Flutter 3.44.8 (stable) e um Android SDK. Na raiz do repositório:

```bash
cd mobile
flutter pub get
flutter run --dart-define=AGROTOP_API_URL=https://endereco-da-api
```

O endereço não fica gravado no código de produção: informe-o com
`AGROTOP_API_URL`. O valor local padrão (`http://10.0.2.2:8000`) aponta do emulador
Android para a máquina host e existe somente para desenvolvimento.

## Autenticação e tema

- Access token e refresh token ficam no Android Keystore/Keychain por
  `flutter_secure_storage`.
- Uma resposta `401` nos endpoints protegidos dispara `POST /auth/refresh` e repete a
  requisição uma vez. O app volta ao login somente quando o refresh também é recusado.
- O menu oferece escuro, claro e seguir o sistema; a preferência visual usa
  `shared_preferences`.
- `lib/app_colors.dart` é gerado de `ui/tema.py` por
  `python mobile/tool/generate_app_colors.py` e não deve ser editado à mão.

## Verificação

```bash
cd mobile
flutter analyze
flutter test
python tool/generate_app_colors.py
git diff --exit-code -- lib/app_colors.dart
flutter build apk --debug
```

O fluxo de integração usa um servidor HTTP mock local com os payloads exatos da spec 0044.
Ele cobre login, refresh automático, lista, ficha, registro da pesagem e recarga da ficha.
Isso não substitui uma futura conferência ponta a ponta contra a API real.

As capturas das quatro telas nos temas escuro, claro e seguir o sistema podem ser
regeneradas com:

```bash
CAPTURE_GOLDENS=1 flutter test test/golden_screens_test.dart --update-goldens
```
