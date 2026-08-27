import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/shallow_cache.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('ShallowCache', () {
    late SharedPreferences prefs;
    late ShallowCache cache;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      prefs = await SharedPreferences.getInstance();
      cache = ShallowCache(prefs);
    });

    test('salva e recupera lista de animais com timestamp', () async {
      expect(cache.getAnimals(), isNull);

      final animals = [
        const AnimalSummary(
          id: 'BR0001',
          breed: 'Nelore',
          sex: 'M',
          currentWeight: 450.0,
          loteId: 'P01',
        ),
        const AnimalSummary(
          id: 'BR0002',
          breed: 'Angus',
          sex: 'F',
          currentWeight: 380.0,
          loteId: 'P02',
        ),
      ];

      await cache.saveAnimals(animals);

      final cached = cache.getAnimals();
      expect(cached, isNotNull);
      expect(cached!.data.length, equals(2));
      expect(cached.data[0].id, equals('BR0001'));
      expect(cached.data[0].currentWeight, equals(450.0));
      expect(cached.data[1].id, equals('BR0002'));
      expect(cached.formattedTime, isNotEmpty);
    });

    test('salva e recupera ficha detalhada de animal por ID', () async {
      expect(cache.getAnimalDetail('BR0001'), isNull);

      const detail = AnimalDetail(
        id: 'BR0001',
        breed: 'Nelore',
        sex: 'M',
        currentWeight: 450.0,
        lotName: 'Piquete Central',
        entryDate: '2026-01-10',
        fornecedorName: 'Fazenda Boa Vista',
        gmdRecent: 0.75,
        gmdTotal: 0.62,
      );

      await cache.saveAnimalDetail(detail);

      final cached = cache.getAnimalDetail('BR0001');
      expect(cached, isNotNull);
      expect(cached!.data.id, equals('BR0001'));
      expect(cached.data.lotName, equals('Piquete Central'));
      expect(cached.data.gmdRecent, equals(0.75));
      expect(cached.formattedTime, isNotEmpty);

      expect(cache.getAnimalDetail('OUTRO'), isNull);
    });

    test('salva e recupera lista de piquetes/lotes', () async {
      expect(cache.getLotes(), isNull);

      final lotes = [
        const LoteSummary(
          id: 'P01',
          nome: 'Piquete Central',
          capacidadeUa: 30.0,
          animaisAtivos: 15,
        ),
        const LoteSummary(
          id: 'P02',
          nome: 'Piquete Norte',
          capacidadeUa: 25.0,
          animaisAtivos: 8,
        ),
      ];

      await cache.saveLotes(lotes);

      final cached = cache.getLotes();
      expect(cached, isNotNull);
      expect(cached!.data.length, equals(2));
      expect(cached.data[0].id, equals('P01'));
      expect(cached.data[0].animaisAtivos, equals(15));
      expect(cached.formattedTime, isNotEmpty);
    });
  });
}
