import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app_colors.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/screens/animals_page.dart';
import 'package:agrotop_mobile/screens/perimeter_gps_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _MemoryTokenStore implements TokenStore {
  StoredTokens? tokens = const StoredTokens(
    accessToken: 'access-ok',
    refreshToken: 'refresh-ok',
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

ApiClient _api(MockClient client) => ApiClient(
      tokenStore: _MemoryTokenStore(),
      baseUrl: 'http://mock.local',
      httpClient: client,
    );

void main() {
  final sampleLotes = [
    {'id': 'P01', 'nome': 'Piquete Central', 'animais_ativos': 10},
    {'id': 'P02', 'nome': 'Piquete da Represa', 'animais_ativos': 5},
  ];

  testWidgets(
      'Critério 4: botão salvar desabilitado com menos de 3 vértices e habilitado com 3+',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    int pointIndex = 0;
    final fixedPoints = [
      const PositionPoint(latitude: -23.550520, longitude: -46.633308),
      const PositionPoint(latitude: -23.551520, longitude: -46.633308),
      const PositionPoint(latitude: -23.551520, longitude: -46.634308),
      const PositionPoint(latitude: -23.550520, longitude: -46.634308),
    ];

    final api = _api(
      MockClient((request) async {
        if (request.url.path == '/lotes') {
          return _json(sampleLotes);
        }
        return _json({});
      }),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: PerimeterGpsPage(
          api: api,
          onUnauthorized: () {},
          permissionChecker: () async => LocationPermission.always,
          positionProvider: () async => fixedPoints[pointIndex++ % fixedPoints.length],
        ),
      ),
    );
    await tester.pumpAndSettle();

    final saveButton = find.byKey(const ValueKey('save-perimeter-button'));
    final markButton = find.byKey(const ValueKey('mark-point-button'));

    expect(saveButton, findsOneWidget);
    // Inicialmente sem pontos: botão desabilitado
    expect(tester.widget<FilledButton>(saveButton).onPressed, isNull);

    // Marca 1º ponto
    await tester.tap(markButton);
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('points-count')), findsOneWidget);
    expect(tester.widget<FilledButton>(saveButton).onPressed, isNull);

    // Marca 2º ponto
    await tester.tap(markButton);
    await tester.pumpAndSettle();
    expect(tester.widget<FilledButton>(saveButton).onPressed, isNull);

    // Marca 3º ponto -> botão habilitado e preview visível
    await tester.tap(markButton);
    await tester.pumpAndSettle();
    expect(tester.widget<FilledButton>(saveButton).onPressed, isNotNull);
    expect(find.byKey(const ValueKey('polygon-preview')), findsOneWidget);
  });

  testWidgets(
      'Critérios 2 e 3: fluxo completo marca 4 pontos, desfaz um, remarca, salva com POST na ordem [lon, lat] e recebe 200',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    int pointIndex = 0;
    final fixedPoints = [
      const PositionPoint(latitude: -20.1000, longitude: -48.1000),
      const PositionPoint(latitude: -20.2000, longitude: -48.1000),
      const PositionPoint(latitude: -20.2000, longitude: -48.2000),
      const PositionPoint(latitude: -20.9999, longitude: -48.9999), // ponto errado
      const PositionPoint(latitude: -20.1000, longitude: -48.2000), // ponto corrigido
    ];

    Map<String, dynamic>? receivedBody;
    String? receivedPath;

    final api = _api(
      MockClient((request) async {
        if (request.method == 'GET' && request.url.path == '/lotes') {
          return _json(sampleLotes);
        }
        if (request.method == 'POST' && request.url.path == '/lotes/P01/perimetro') {
          receivedPath = request.url.path;
          receivedBody = jsonDecode(request.body) as Map<String, dynamic>;
          return _json({
            'ok': true,
            'area_ha': 15.42,
            'perimetro_m': 1600.0,
          });
        }
        return _json({}, status: 404);
      }),
    );

    PerimetroResult? returnedResult;

    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: Builder(
          builder: (context) => Scaffold(
            body: ElevatedButton(
              onPressed: () async {
                final res = await Navigator.of(context).push<PerimetroResult>(
                  MaterialPageRoute(
                    builder: (_) => PerimeterGpsPage(
                      api: api,
                      onUnauthorized: () {},
                      permissionChecker: () async => LocationPermission.whileInUse,
                      positionProvider: () async =>
                          fixedPoints[pointIndex++ % fixedPoints.length],
                    ),
                  ),
                );
                returnedResult = res;
              },
              child: const Text('Abrir GPS'),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Abre a tela
    await tester.tap(find.text('Abrir GPS'));
    await tester.pumpAndSettle();

    final markButton = find.byKey(const ValueKey('mark-point-button'));
    final undoButton = find.byKey(const ValueKey('undo-point-button'));
    final saveButton = find.byKey(const ValueKey('save-perimeter-button'));

    // Marca 4 pontos (sendo o 4º errado)
    await tester.tap(markButton);
    await tester.pumpAndSettle();
    await tester.tap(markButton);
    await tester.pumpAndSettle();
    await tester.tap(markButton);
    await tester.pumpAndSettle();
    await tester.tap(markButton);
    await tester.pumpAndSettle();

    expect(find.text('Lat: -20.999900, Lon: -48.999900'), findsOneWidget);

    // Critério 3: Desfazer remove exatamente o último
    await tester.ensureVisible(undoButton);
    await tester.tap(undoButton);
    await tester.pumpAndSettle();
    expect(find.text('Lat: -20.999900, Lon: -48.999900'), findsNothing);
    expect(find.text('Lat: -20.200000, Lon: -48.200000'), findsOneWidget);

    // Marca o 4º ponto correto
    await tester.ensureVisible(markButton);
    await tester.tap(markButton);
    await tester.pumpAndSettle();
    expect(find.text('Lat: -20.100000, Lon: -48.200000'), findsOneWidget);

    // Salva o perímetro
    await tester.ensureVisible(saveButton);
    await tester.tap(saveButton);
    await tester.pumpAndSettle();

    expect(receivedPath, '/lotes/P01/perimetro');
    expect(receivedBody, isNotNull);
    final pontos = receivedBody!['pontos'] as List<dynamic>;
    expect(pontos.length, 4);

    // Prova que pontos foram enviados como [lon, lat]
    expect(pontos[0], [-48.1000, -20.1000]);
    expect(pontos[1], [-48.1000, -20.2000]);
    expect(pontos[2], [-48.2000, -20.2000]);
    expect(pontos[3], [-48.2000, -20.1000]);

    // Tela fechada com retorno do resultado
    expect(find.byType(PerimeterGpsPage), findsNothing);
    expect(returnedResult, isNotNull);
    expect(returnedResult!.areaHa, 15.42);
  });

  testWidgets('Critério 5: erro 422 mantém pontos marcados na tela', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    int pointIndex = 0;
    final fixedPoints = [
      const PositionPoint(latitude: -20.1000, longitude: -48.1000),
      const PositionPoint(latitude: -20.2000, longitude: -48.1000),
      const PositionPoint(latitude: -20.2000, longitude: -48.2000),
    ];

    final api = _api(
      MockClient((request) async {
        if (request.method == 'GET' && request.url.path == '/lotes') {
          return _json(sampleLotes);
        }
        if (request.method == 'POST' && request.url.path == '/lotes/P01/perimetro') {
          return _json({
            'detail': ['Polígono auto-interceptante.'],
          }, status: 422);
        }
        return _json({});
      }),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: PerimeterGpsPage(
          api: api,
          onUnauthorized: () {},
          permissionChecker: () async => LocationPermission.always,
          positionProvider: () async => fixedPoints[pointIndex++ % fixedPoints.length],
        ),
      ),
    );
    await tester.pumpAndSettle();

    final markButton = find.byKey(const ValueKey('mark-point-button'));
    await tester.tap(markButton);
    await tester.pumpAndSettle();
    await tester.tap(markButton);
    await tester.pumpAndSettle();
    await tester.tap(markButton);
    await tester.pumpAndSettle();

    final saveButton = find.byKey(const ValueKey('save-perimeter-button'));
    await tester.ensureVisible(saveButton);
    await tester.tap(saveButton);
    await tester.pumpAndSettle();

    // Permanece na tela
    expect(find.byType(PerimeterGpsPage), findsOneWidget);
    // Mostra mensagem de erro
    expect(find.byKey(const ValueKey('perimeter-error-message')), findsOneWidget);
    expect(find.textContaining('Polígono auto-interceptante'), findsOneWidget);
    // Pontos continuam na tela
    expect(find.text('Lat: -20.100000, Lon: -48.100000'), findsOneWidget);
    expect(find.text('Lat: -20.200000, Lon: -48.200000'), findsOneWidget);
  });

  testWidgets(
      'Critério 6: permissão negada exibe mensagem e botão para pedir novamente',
      (tester) async {
    int checkCount = 0;
    final api = _api(MockClient((_) async => _json([])));

    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: PerimeterGpsPage(
          api: api,
          onUnauthorized: () {},
          permissionChecker: () async => LocationPermission.denied,
          permissionRequester: () async {
            checkCount++;
            return LocationPermission.denied;
          },
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('permission-denied-message')), findsOneWidget);
    expect(find.textContaining('Permissão de localização é necessária'), findsOneWidget);

    final retryButton = find.byKey(const ValueKey('request-permission-button'));
    expect(retryButton, findsOneWidget);
    await tester.tap(retryButton);
    await tester.pumpAndSettle();

    expect(checkCount, 2);
  });

  testWidgets('abre PerimeterGpsPage a partir do botão no AppBar de AnimalsPage',
      (tester) async {
    final api = _api(
      MockClient((request) async {
        if (request.url.path == '/animais') return _json([]);
        if (request.url.path == '/trato/pendentes') return _json([]);
        if (request.url.path == '/lotes') return _json(sampleLotes);
        if (request.url.path == '/alertas') {
          return _json({
            'sumidos': [],
            'carencia': [],
            'prontos_para_abate': [],
            'estoque_baixo': [],
            'baixo_desempenho': [],
          });
        }
        return _json({});
      }),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: AnimalsPage(
          api: api,
          themeMode: ThemeMode.light,
          onThemeChanged: (_) {},
          onUnauthorized: () {},
          gpsPermissionChecker: () async => LocationPermission.always,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final openButton = find.byKey(const ValueKey('open-perimeter-gps'));
    expect(openButton, findsOneWidget);
    await tester.tap(openButton);
    await tester.pumpAndSettle();

    expect(find.byType(PerimeterGpsPage), findsOneWidget);
    expect(find.text('Demarcar perímetro por GPS'), findsOneWidget);
  });
}
