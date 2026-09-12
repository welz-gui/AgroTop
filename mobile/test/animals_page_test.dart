import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app_colors.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/offline_queue.dart';
import 'package:agrotop_mobile/screens/animals_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class _TokenStore implements TokenStore {
  @override
  Future<void> clear() async {}

  @override
  Future<StoredTokens?> read() async => null;

  @override
  Future<void> write(StoredTokens value) async {}
}

class _AnimalRequest {
  const _AnimalRequest({required this.skip, required this.limit, this.q});

  final int skip;
  final int limit;
  final String? q;
}

class _RecordingApi extends ApiClient {
  _RecordingApi(this.animals) : super(tokenStore: _TokenStore());

  final List<AnimalSummary> animals;
  final requests = <_AnimalRequest>[];

  @override
  Future<List<AnimalSummary>> listAnimals({
    int skip = 0,
    int limit = 50,
    String status = 'ativo',
    String? q,
  }) async {
    requests.add(_AnimalRequest(skip: skip, limit: limit, q: q));
    final filtered = q == null || q.isEmpty
        ? animals
        : animals
              .where(
                (animal) => animal.id.toLowerCase().contains(q.toLowerCase()),
              )
              .toList(growable: false);
    return filtered.skip(skip).take(limit).toList(growable: false);
  }

  @override
  Future<List<PendingFeeding>> listPendingFeedings() async => const [];

  @override
  Future<OperationalAlerts> getOperationalAlerts() async =>
      const OperationalAlerts(
        sumidos: [],
        carencia: [],
        prontosParaAbate: [],
        estoqueBaixo: [],
        baixoDesempenho: [],
      );
}

List<AnimalSummary> _animals(String prefix) => List.generate(
  60,
  (index) => AnimalSummary(
    id: '$prefix${(index + 1).toString().padLeft(4, '0')}',
    breed: 'Nelore',
    currentWeight: 360,
    status: 'ativo',
  ),
);

Widget _page(ApiClient api) => MaterialApp(
  theme: AppThemes.light,
  darkTheme: AppThemes.dark,
  home: AnimalsPage(
    api: api,
    themeMode: ThemeMode.light,
    onThemeChanged: (_) {},
    onUnauthorized: () {},
    offlineQueue: OfflineQueue(storage: MemoryQueueStorage()),
  ),
);

void main() {
  testWidgets(
    'busca no servidor encontra animal fora da primeira página após debounce',
    (tester) async {
      final api = _RecordingApi(_animals('BR'));
      await tester.pumpWidget(_page(api));
      await tester.pumpAndSettle();

      expect(api.requests, hasLength(1));
      expect(find.text('BR0001'), findsOneWidget);
      expect(find.text('BR0060'), findsNothing);

      await tester.enterText(
        find.byKey(const ValueKey('animal-search')),
        'BR0060',
      );
      await tester.pump(const Duration(milliseconds: 399));
      expect(api.requests, hasLength(1));

      await tester.pump(const Duration(milliseconds: 1));
      await tester.pumpAndSettle();

      expect(api.requests, hasLength(2));
      expect(api.requests.last.q, 'BR0060');
      expect(find.widgetWithText(ListTile, 'BR0060'), findsOneWidget);
      expect(find.text('BR0001'), findsNothing);
    },
  );

  testWidgets('limpar a busca volta à paginação e carregar mais preserva q', (
    tester,
  ) async {
    final api = _RecordingApi(_animals('BUSCA'));
    await tester.pumpWidget(_page(api));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const ValueKey('animal-search')),
      'BUSCA',
    );
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();

    final loadMore = find.text('Carregar mais');
    await tester.scrollUntilVisible(
      loadMore,
      500,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(loadMore);
    await tester.pumpAndSettle();

    expect(api.requests.last.q, 'BUSCA');
    expect(api.requests.last.skip, 50);
    await tester.scrollUntilVisible(
      find.widgetWithText(ListTile, 'BUSCA0060'),
      500,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.widgetWithText(ListTile, 'BUSCA0060'), findsOneWidget);

    await tester.scrollUntilVisible(
      find.byKey(const ValueKey('animal-search')),
      -500,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.enterText(find.byKey(const ValueKey('animal-search')), '');
    await tester.pumpAndSettle();

    expect(api.requests.last.q, isNull);
    expect(api.requests.last.skip, 0);
    expect(find.text('BUSCA0001'), findsOneWidget);
  });
}
