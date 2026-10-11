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
}
