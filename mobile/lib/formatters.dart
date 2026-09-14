String formatDecimalBr(double value, {int digits = 1}) =>
    value.toStringAsFixed(digits).replaceAll('.', ',');
