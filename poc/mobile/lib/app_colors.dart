// GENERATED FILE — execute: python poc/mobile/tool/generate_app_colors.py
// Fonte: ui/tema.py. Não edite as cores manualmente.

import 'package:flutter/material.dart';

abstract final class AppColors {
  static const dark = <String, Color>{
    'fundo': Color(0xFF0F172A),
    'fundo_alt': Color(0xFF0A1628),
    'superficie': Color(0xFF1E293B),
    'borda': Color(0xFF334155),
    'borda_suave': Color(0xFF475569),
    'texto': Color(0xFFF1F5F9),
    'texto_secundario': Color(0xFF94A3B8),
    'texto_terciario': Color(0xFF64748B),
    'primaria': Color(0xFF4ADE80),
    'sucesso': Color(0xFF4ADE80),
    'sucesso_escuro': Color(0xFF166534),
    'sucesso_fundo': Color(0xFF14532D),
    'atencao': Color(0xFFFBBF24),
    'atencao_escuro': Color(0xFF854D0E),
    'atencao_fundo': Color(0xFF422006),
    'perigo': Color(0xFFF87171),
    'perigo_escuro': Color(0xFF7F1D1D),
    'perigo_fundo': Color(0xFF450A0A),
    'info': Color(0xFF22D3EE),
    'info_fundo': Color(0xFF1E3A5F),
    'destaque': Color(0xFFA78BFA),
  };

  static const light = <String, Color>{
    'fundo': Color(0xFFF8FAFC),
    'fundo_alt': Color(0xFFF1F5F9),
    'superficie': Color(0xFFFFFFFF),
    'borda': Color(0xFFE2E8F0),
    'borda_suave': Color(0xFFCBD5E1),
    'texto': Color(0xFF0F172A),
    'texto_secundario': Color(0xFF475569),
    'texto_terciario': Color(0xFF64748B),
    'primaria': Color(0xFF15803D),
    'sucesso': Color(0xFF15803D),
    'sucesso_escuro': Color(0xFF166534),
    'sucesso_fundo': Color(0xFFDCFCE7),
    'atencao': Color(0xFFB45309),
    'atencao_escuro': Color(0xFF854D0E),
    'atencao_fundo': Color(0xFFFEF3C7),
    'perigo': Color(0xFFB91C1C),
    'perigo_escuro': Color(0xFF7F1D1D),
    'perigo_fundo': Color(0xFFFEE2E2),
    'info': Color(0xFF0E7490),
    'info_fundo': Color(0xFFCFFAFE),
    'destaque': Color(0xFF6D28D9),
  };
}

abstract final class AppThemes {
  static ThemeData get dark => _build(AppColors.dark, Brightness.dark);
  static ThemeData get light => _build(AppColors.light, Brightness.light);

  static ThemeData _build(Map<String, Color> colors, Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
      seedColor: colors['primaria']!,
      brightness: brightness,
      primary: colors['primaria'],
      surface: colors['superficie'],
      error: colors['perigo'],
    );
    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: colors['fundo'],
      cardTheme: CardThemeData(
        color: colors['superficie'],
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: colors['borda']!),
        ),
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: colors['fundo'],
        foregroundColor: colors['texto'],
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: colors['superficie'],
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }
}
