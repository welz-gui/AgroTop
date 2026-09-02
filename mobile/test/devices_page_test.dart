import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/screens/devices_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _TokenStore implements TokenStore {
  _TokenStore()
    : _tokens = const StoredTokens(
        accessToken: 'access',
        refreshToken: 'refresh',
      );

  StoredTokens? _tokens;

  @override
  Future<void> clear() async => _tokens = null;

  @override
  Future<StoredTokens?> read() async => _tokens;

  @override
  Future<void> write(StoredTokens tokens) async => _tokens = tokens;
}

http.Response _json(Object body, {int status = 200}) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json'},
);

Map<String, dynamic> _device({
  String status = 'recebido',
  List<Map<String, dynamic>> transitions = const [],
}) => {
  'id': 'device-1',
  'codigo_visual': 'BR-100',
  'tipo': 'brinco_visual',
  'status': status,
  'lote': 'Lote Norte',
  'transicoes_permitidas': transitions,
};

ApiClient _api(http.Client client) => ApiClient(
  tokenStore: _TokenStore(),
  httpClient: client,
  baseUrl: 'http://mock.local',
);

Future<void> _open(WidgetTester tester, ApiClient api) async {
  await tester.pumpWidget(
    MaterialApp(
      home: DevicesPage(api: api, onUnauthorized: () {}),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _search(WidgetTester tester, String code) async {
  await tester.enterText(find.byKey(const ValueKey('device-code-field')), code);
  await tester.tap(find.byKey(const ValueKey('search-device')));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('código inexistente mostra mensagem clara', (tester) async {
    await _open(
      tester,
      _api(MockClient((_) async => _json({'detail': 'Ausente'}, status: 404))),
    );

    await _search(tester, 'BR-404');

    expect(
      find.text('Nenhum dispositivo ativo com esse código.'),
      findsOneWidget,
    );
  });

  testWidgets('busca e confirma transição sem motivo', (tester) async {
    var status = 'recebido';
    final api = _api(
      MockClient((request) async {
        if (request.method == 'GET') {
          return _json(
            _device(
              status: status,
              transitions: status == 'recebido'
                  ? [
                      {
                        'para': 'disponivel',
                        'exige_motivo': false,
                        'exige_autorizacao': false,
                      },
                    ]
                  : const [],
            ),
          );
        }
        expect(request.method, 'POST');
        expect(jsonDecode(request.body), {
          'novo_status': 'disponivel',
          'motivo': null,
        });
        status = 'disponivel';
        return _json({'ok': true, 'de': 'recebido', 'para': 'disponivel'});
      }),
    );
    await _open(tester, api);

    await _search(tester, 'BR-100');
    expect(find.textContaining('Recebido, a conferir'), findsOneWidget);
    await tester.tap(
      find.byKey(const ValueKey('device-transition-disponivel')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('confirm-device-status')));
    await tester.pumpAndSettle();

    expect(find.text('Situação: Disponível'), findsOneWidget);
    expect(
      find.text('Esta situação é definitiva ou bloqueada.'),
      findsOneWidget,
    );
  });

  testWidgets('motivo obrigatório bloqueia confirmação até ser preenchido', (
    tester,
  ) async {
    final api = _api(
      MockClient((request) async {
        if (request.method == 'GET') {
          return _json(
            _device(
              transitions: [
                {
                  'para': 'danificado',
                  'exige_motivo': true,
                  'exige_autorizacao': false,
                },
              ],
            ),
          );
        }
        expect(jsonDecode(request.body), {
          'novo_status': 'danificado',
          'motivo': 'Quebrado no manejo',
        });
        return _json({'ok': true, 'de': 'recebido', 'para': 'danificado'});
      }),
    );
    await _open(tester, api);

    await _search(tester, 'BR-100');
    await tester.tap(
      find.byKey(const ValueKey('device-transition-danificado')),
    );
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const ValueKey('confirm-device-status')),
          )
          .onPressed,
      isNull,
    );
    await tester.enterText(
      find.byKey(const ValueKey('device-status-reason')),
      'Quebrado no manejo',
    );
    await tester.pump();
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const ValueKey('confirm-device-status')),
          )
          .onPressed,
      isNotNull,
    );
  });

  testWidgets('estado terminal e autorização obrigatória são explicados', (
    tester,
  ) async {
    final terminal = _api(
      MockClient((_) async => _json(_device(status: 'inutilizado'))),
    );
    await _open(tester, terminal);
    await _search(tester, 'BR-100');
    expect(
      find.text('Esta situação é definitiva ou bloqueada.'),
      findsOneWidget,
    );

    await _open(
      tester,
      _api(
        MockClient(
          (_) async => _json(
            _device(
              status: 'bloqueado_orgao',
              transitions: [
                {
                  'para': 'disponivel',
                  'exige_motivo': false,
                  'exige_autorizacao': true,
                },
              ],
            ),
          ),
        ),
      ),
    );
    await _search(tester, 'BR-100');
    expect(find.text('Só o órgão libera.'), findsOneWidget);
    expect(
      tester
          .widget<ListTile>(
            find.byKey(const ValueKey('device-transition-disponivel')),
          )
          .enabled,
      isFalse,
    );
  });
}
