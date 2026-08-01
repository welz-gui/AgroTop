"""Gera lib/app_colors.dart diretamente dos tokens de ui/tema.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "ui" / "tema.py"
TARGET = Path(__file__).resolve().parents[1] / "lib" / "app_colors.dart"


def _load_theme_module():
    spec = importlib.util.spec_from_file_location("agrotop_tema", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Não foi possível carregar {SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dart_color(value: str) -> str:
    return f"Color(0xFF{value.removeprefix('#').upper()})"


def _palette(name: str, values: dict[str, str]) -> str:
    fields = "\n".join(
        f"    '{token}': {_dart_color(value)}," for token, value in values.items()
    )
    return f"  static const {name} = <String, Color>{{\n{fields}\n  }};"


def main() -> None:
    theme = _load_theme_module()
    output = f"""// GENERATED FILE — execute: python poc/mobile/tool/generate_app_colors.py
// Fonte: ui/tema.py. Não edite as cores manualmente.

import 'package:flutter/material.dart';

abstract final class AppColors {{
{_palette('dark', theme.ESCURO)}

{_palette('light', theme.CLARO)}
}}

abstract final class AppThemes {{
  static ThemeData get dark => _build(AppColors.dark, Brightness.dark);
  static ThemeData get light => _build(AppColors.light, Brightness.light);

  static ThemeData _build(Map<String, Color> colors, Brightness brightness) {{
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
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
    );
  }}
}}
"""
    TARGET.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
