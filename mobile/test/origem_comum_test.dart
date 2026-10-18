import 'package:agrotop_mobile/screens/movement_page.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('origemComum', () {
    test('todos no mesmo piquete devolve esse piquete', () {
      expect(origemComum(['P01', 'P01']), 'P01');
    });

    test('aceita id numérico vindo do JSON', () {
      expect(origemComum([7, '7']), '7');
    });

    test('piquetes diferentes não conferem', () {
      expect(origemComum(['P01', 'P02']), isNull);
    });

    test('animal sem piquete conhecido não confere', () {
      expect(origemComum(['P01', null]), isNull);
      expect(origemComum(['']), isNull);
    });

    test('lista vazia não confere', () {
      expect(origemComum(const []), isNull);
    });
  });

  group('origensPorAnimal', () {
    test('mapeia cada animal para o piquete em que foi visto', () {
      expect(
        origensPorAnimal(['A', 'B', 'C'], {'A': 'P01', 'B': 'P02', 'C': 'P01'}),
        {'A': 'P01', 'B': 'P02', 'C': 'P01'},
      );
    });

    test('aceita id numérico vindo do JSON', () {
      expect(origensPorAnimal(['A'], {'A': 7}), {'A': '7'});
    });

    test('animal sem piquete conhecido fica de fora do mapa', () {
      expect(
        origensPorAnimal(['A', 'B', 'C'], {'A': 'P01', 'B': null, 'C': ''}),
        {'A': 'P01'},
      );
    });

    test('nenhum piquete conhecido devolve null, para o campo não ir no pedido', () {
      expect(origensPorAnimal(['A'], {'A': null}), isNull);
      expect(origensPorAnimal(const [], const {}), isNull);
    });
  });
}
