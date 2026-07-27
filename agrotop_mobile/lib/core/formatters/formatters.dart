import 'package:intl/intl.dart';

class AppFormatters {
  static final NumberFormat _currencyFormatter = NumberFormat.currency(
    locale: 'pt_BR',
    symbol: 'R\$',
    decimalDigits: 2,
  );

  static final DateFormat _dateFormat = DateFormat('dd/MM/yyyy');
  static final DateFormat _dateTimeFormat = DateFormat('dd/MM/yyyy HH:mm');

  /// Formatador de valor monetário (ex: R$ 1.250,50)
  static String formatCurrency(double value) {
    return _currencyFormatter.format(value);
  }

  /// Formatador de data brasileira (ex: 27/07/2026)
  static String formatDate(DateTime date) {
    return _dateFormat.format(date);
  }

  /// Converte texto ISO (YYYY-MM-DD) para formato BR
  static String formatIsoDateStr(String? isoStr) {
    if (isoStr == null || isoStr.isEmpty) return '—';
    try {
      final dt = DateTime.parse(isoStr);
      return _dateFormat.format(dt);
    } catch (_) {
      return isoStr;
    }
  }

  /// Formatador de peso com unidade (ex: 420.5 kg)
  static String formatWeight(double weightKg) {
    return '${weightKg.toStringAsFixed(1)} kg';
  }

  /// Converte kg para Arrobas (@) considerando rendimento padrão de 54%
  static String formatArrobas(double weightKg, {double yieldFraction = 0.54}) {
    final @prod = (weightKg * yieldFraction) / 15.0;
    return '${@prod.toStringAsFixed(2)} @';
  }
}
