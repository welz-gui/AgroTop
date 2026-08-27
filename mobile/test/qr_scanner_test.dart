import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/screens/animals_page.dart';
import 'package:agrotop_mobile/screens/qr_scanner_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class MemoryTokenStore implements TokenStore {
  StoredTokens? tokens = const StoredTokens(
    accessToken: 'access-live',
    refreshToken: 'refresh-valid',
  );

  @override
  Future<void> clear() async => tokens = null;

  @override
  Future<StoredTokens?> read() async => tokens;

  @override
  Future<void> write(StoredTokens value) async => tokens = value;
}

http.Response _json(Object body, {int status = 200}) => http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late ApiClient api;
  late MemoryTokenStore tokenStore;
  final animalRequests = <String>[];

  setUp(() {
    animalRequests.clear();
    tokenStore = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path == '/animais' && request.method == 'GET') {
        return _json([
          {
            'id': 'BR0001',
            'breed': 'Nelore',
            'current_weight': 382.4,
            'lote_id': 'P01',
          },
          {
            'id': 'BR0002',
            'breed': 'Angus',
            'current_weight': 410.0,
            'lote_id': 'P02',
          },
        ]);
      }

      if (request.url.path.startsWith('/animais/') &&
          request.method == 'GET' &&
          !request.url.path.contains('/medicamentos') &&
          !request.url.path.contains('/fotos')) {
        final id = Uri.decodeComponent(
          request.url.path.substring('/animais/'.length),
        );
        animalRequests.add(id);

        if (id == 'BR0001') {
          return _json({
            'id': 'BR0001',
            'breed': 'Nelore',
            'current_weight': 382.4,
            'lote_id': 'P01',
            'entry_date': '2026-01-10',
            'fornecedor_id': 7,
            'fornecedor_name': 'Fazenda Boa Vista',
            'gmd_recent_kg_day': 0.742,
            'gmd_total_kg_day': 0.513,
          });
        }
        if (id == 'BR0099') {
          return _json({
            'id': 'BR0099',
            'breed': 'Brahman',
            'current_weight': 520.0,
            'lote_id': 'P03',
            'entry_date': '2026-02-01',
            'fornecedor_id': 3,
            'fornecedor_name': 'Fazenda Primavera',
            'gmd_recent_kg_day': 0.810,
            'gmd_total_kg_day': 0.620,
          });
        }
        if (id == 'NET_ERROR') {
          return http.Response('Network Error', 500);
        }
        return _json({'detail': 'Animal não encontrado'}, status: 404);
      }

      if (request.url.path.endsWith('/medicamentos')) {
        return _json({
          'carencia_ate': null,
          'aplicacoes': <Map<String, dynamic>>[],
        });
      }

      if (request.url.path.endsWith('/fotos')) {
        return _json(<Map<String, dynamic>>[]);
      }

      return _json({'detail': 'Not found'}, status: 404);
    });

    api = ApiClient(
      baseUrl: 'http://localhost:8000',
      tokenStore: tokenStore,
      httpClient: client,
    );
  });

  testWidgets('QR Scanner: fluxo com leitura válida navega para ficha do animal',
      (tester) async {
    ValueChanged<String>? onScannedCallback;

    await tester.pumpWidget(
      MaterialApp(
        home: QrScannerPage(
          api: api,
          onUnauthorized: () {},
          scannerBuilder: (context, {required onScanned, required onError}) {
            onScannedCallback = onScanned;
            return Container(
              key: const ValueKey('mock-scanner-view'),
              color: Colors.black,
              child: const Center(child: Text('Câmera Simulada')),
            );
          },
        ),
      ),
    );

    expect(find.byKey(const ValueKey('mock-scanner-view')), findsOneWidget);
    expect(
      find.text('Aponte a câmera para o QR Code do brinco.'),
      findsOneWidget,
    );

    // Simula leitura de BR0001
    expect(onScannedCallback, isNotNull);
    onScannedCallback!('BR0001');

    await tester.pumpAndSettle();

    // Deve navegar para a ficha do animal BR0001
    expect(find.byType(AnimalDetailPage), findsOneWidget);
    expect(find.text('BR0001'), findsWidgets);
    expect(find.text('Ficha BR0001'), findsOneWidget);
    expect(animalRequests, contains('BR0001'));
  });

  testWidgets('QR Scanner: animal não encontrado (404) exibe erro e permite tentar de novo',
      (tester) async {
    ValueChanged<String>? onScannedCallback;

    await tester.pumpWidget(
      MaterialApp(
        home: QrScannerPage(
          api: api,
          onUnauthorized: () {},
          scannerBuilder: (context, {required onScanned, required onError}) {
            onScannedCallback = onScanned;
            return const SizedBox();
          },
        ),
      ),
    );

    // Simula leitura de código inexistente
    onScannedCallback!('BR9999');

    await tester.pumpAndSettle();

    // Mensagem de erro clara
    expect(find.text('Animal "BR9999" não encontrado.'), findsOneWidget);
    expect(find.byKey(const ValueKey('qr-retry-button')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('qr-manual-search-button')),
      findsOneWidget,
    );

    // Tenta novamente -> limpa erro e volta a escanear
    await tester.tap(find.byKey(const ValueKey('qr-retry-button')));
    await tester.pump();

    expect(find.text('Animal "BR9999" não encontrado.'), findsNothing);
    expect(
      find.text('Aponte a câmera para o QR Code do brinco.'),
      findsOneWidget,
    );
  });

  testWidgets('QR Scanner: erro de rede exibe mensagem e permite repetir consulta',
      (tester) async {
    ValueChanged<String>? onScannedCallback;

    await tester.pumpWidget(
      MaterialApp(
        home: QrScannerPage(
          api: api,
          onUnauthorized: () {},
          scannerBuilder: (context, {required onScanned, required onError}) {
            onScannedCallback = onScanned;
            return const SizedBox();
          },
        ),
      ),
    );

    onScannedCallback!('NET_ERROR');
    await tester.pumpAndSettle();

    expect(find.textContaining('Erro'), findsOneWidget);
    expect(find.byKey(const ValueKey('qr-recheck-button')), findsOneWidget);

    // Repetir consulta
    await tester.tap(find.byKey(const ValueKey('qr-recheck-button')));
    await tester.pumpAndSettle();
  });

  testWidgets('QR Scanner: leitura vazia ou ilegível exibe aviso', (tester) async {
    ValueChanged<String>? onScannedCallback;

    await tester.pumpWidget(
      MaterialApp(
        home: QrScannerPage(
          api: api,
          onUnauthorized: () {},
          scannerBuilder: (context, {required onScanned, required onError}) {
            onScannedCallback = onScanned;
            return const SizedBox();
          },
        ),
      ),
    );

    onScannedCallback!('   ');
    await tester.pump();

    expect(
      find.text('QR Code ilegível. Reposicione o brinco e tente novamente.'),
      findsOneWidget,
    );
  });

  testWidgets('AnimalsPage: botão de QR existe e leitura busca direto na API ignorando filtro local _query',
      (tester) async {
    ValueChanged<String>? onScannedCallback;

    await tester.pumpWidget(
      MaterialApp(
        home: AnimalsPage(
          api: api,
          themeMode: ThemeMode.system,
          onThemeChanged: (_) {},
          onUnauthorized: () {},
          qrScannerBuilder: (context, {required onScanned, required onError}) {
            onScannedCallback = onScanned;
            return const SizedBox();
          },
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Confirma que a lista inicial tem BR0001 e BR0002
    expect(find.widgetWithText(ListTile, 'BR0001'), findsOneWidget);
    expect(find.widgetWithText(ListTile, 'BR0002'), findsOneWidget);

    // Digita no filtro local algo que esconde BR0099 e BR0001
    await tester.enterText(
      find.byKey(const ValueKey('animal-search')),
      'BR0002',
    );
    await tester.pump();

    expect(find.widgetWithText(ListTile, 'BR0001'), findsNothing);
    expect(find.widgetWithText(ListTile, 'BR0002'), findsOneWidget);

    // Clica no botão de QR code scanner (suffixIcon da busca)
    expect(find.byKey(const ValueKey('scan-qr-button')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('scan-qr-button')));
    await tester.pumpAndSettle();

    // Estamos na tela de QR Scanner
    expect(find.byType(QrScannerPage), findsOneWidget);

    // Escaneia BR0099 (animal que NEM ESTAVA na lista inicial da página)
    expect(onScannedCallback, isNotNull);
    onScannedCallback!('BR0099');

    await tester.pumpAndSettle();

    // Navegou com sucesso para a ficha de BR0099 direto da API!
    expect(find.byType(AnimalDetailPage), findsOneWidget);
    expect(find.text('BR0099'), findsWidgets);
    expect(find.text('Ficha BR0099'), findsOneWidget);
    expect(animalRequests, contains('BR0099'));
  });
}
