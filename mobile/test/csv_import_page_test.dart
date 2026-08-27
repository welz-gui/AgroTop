import 'dart:convert';
import 'dart:typed_data';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/screens/csv_import_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _TokenStore implements TokenStore {
  _TokenStore()
    : tokens = const StoredTokens(
        accessToken: 'access-live',
        refreshToken: 'refresh-live',
      );

  StoredTokens? tokens;

  @override
  Future<void> clear() async => tokens = null;

  @override
  Future<StoredTokens?> read() async => tokens;

  @override
  Future<void> write(StoredTokens value) async => tokens = value;
}

class _Picker implements CsvFilePicker {
  const _Picker(this.file);

  final SelectedCsvFile file;

  @override
  Future<SelectedCsvFile?> pick() async => file;
}

http.Response _json(Object body, {int status = 200}) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

Map<String, dynamic> _preview() => {
  'total_linhas': 3,
  'aceitas': [
    {
      'animal_id': 'BR0001',
      'peso': 412.5,
      'data': '2026-08-25',
      'alertas': ['Variação de peso exige conferência'],
    },
  ],
  'rejeitadas': [
    {
      'linha': 3,
      'conteudo': 'BR0002;sem-peso;2026-08-25',
      'motivo': 'Peso inválido',
    },
  ],
  'gravadas': 0,
};

List<int> _fileBytes(List<int> requestBody) {
  final body = latin1.decode(requestBody);
  final marker = body.indexOf('name="arquivo"');
  final start = body.indexOf('\r\n\r\n', marker) + 4;
  final end = body.indexOf('\r\n--', start);
  return latin1.encode(body.substring(start, end));
}

void main() {
  testWidgets('seleciona, pré-visualiza e confirma com os mesmos bytes', (
    tester,
  ) async {
    final file = SelectedCsvFile(
      name: 'pesagens.csv',
      bytes: Uint8List.fromList([66, 82, 48, 48, 48, 49, 59, 52, 49, 50]),
    );
    final uploads = <List<int>>[];
    final confirmations = <String>[];
    final api = ApiClient(
      tokenStore: _TokenStore(),
      baseUrl: 'http://mock.local',
      httpClient: MockClient((request) async {
        if (request.method == 'POST' &&
            request.url.path == '/pesagens/importar-csv') {
          final body = request.bodyBytes;
          uploads.add(body);
          final text = latin1.decode(body);
          confirmations.add(text.contains('\r\ntrue\r\n') ? 'true' : 'false');
          return _json(
            confirmations.last == 'true'
                ? {..._preview(), 'gravadas': 1}
                : _preview(),
          );
        }
        return _json({'detail': 'Não encontrado'}, status: 404);
      }),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: CsvImportPage(
          api: api,
          onUnauthorized: () {},
          filePicker: _Picker(file),
        ),
      ),
    );

    await tester.tap(find.byKey(const ValueKey('pick-csv-file')));
    await tester.pumpAndSettle();

    expect(find.text('pesagens.csv'), findsOneWidget);
    expect(find.text('Pré-visualização'), findsOneWidget);
    expect(find.text('Ainda não foi gravado.'), findsOneWidget);
    expect(find.text('Variação de peso exige conferência'), findsOneWidget);
    expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('Linha 3: Peso inválido'),
      300,
      scrollable: find.byType(Scrollable),
    );
    expect(find.text('Linha 3: Peso inválido'), findsOneWidget);
    expect(find.text('Gravar 1 pesagem(ns)'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('confirm-csv-import')));
    await tester.pumpAndSettle();

    expect(confirmations, ['false', 'true']);
    expect(uploads, hasLength(2));
    expect(_fileBytes(uploads.first), file.bytes);
    expect(_fileBytes(uploads[1]), file.bytes);
    expect(find.text('1 pesagem(ns) gravada(s).'), findsOneWidget);
  });

  testWidgets('mantém o arquivo selecionado quando a prévia falha', (
    tester,
  ) async {
    final file = SelectedCsvFile(
      name: 'tentativa.txt',
      bytes: Uint8List.fromList([65, 59, 52, 48, 48]),
    );
    var requests = 0;
    final api = ApiClient(
      tokenStore: _TokenStore(),
      baseUrl: 'http://mock.local',
      httpClient: MockClient((request) async {
        if (request.url.path == '/pesagens/importar-csv') {
          requests++;
          if (requests == 1) {
            return _json({'detail': 'Falha temporária'}, status: 500);
          }
          return _json(_preview());
        }
        return _json({'detail': 'Não encontrado'}, status: 404);
      }),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: CsvImportPage(
          api: api,
          onUnauthorized: () {},
          filePicker: _Picker(file),
        ),
      ),
    );

    await tester.tap(find.byKey(const ValueKey('pick-csv-file')));
    await tester.pumpAndSettle();

    expect(find.text('tentativa.txt'), findsOneWidget);
    expect(find.text('Falha temporária'), findsOneWidget);
    await tester.tap(find.text('Tentar novamente'));
    await tester.pumpAndSettle();

    expect(requests, 2);
    expect(find.text('tentativa.txt'), findsOneWidget);
    expect(find.text('Pré-visualização'), findsOneWidget);
  });
}
