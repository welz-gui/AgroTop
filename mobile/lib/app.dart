import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';
import 'app_colors.dart';
import 'screens/animals_page.dart';
import 'screens/login_page.dart';
import 'secure_token_store.dart';

class AgroTopApp extends StatefulWidget {
  const AgroTopApp({super.key, required this.preferences, this.apiClient});

  final SharedPreferences preferences;
  final ApiClient? apiClient;

  @override
  State<AgroTopApp> createState() => _AgroTopAppState();
}

class _AgroTopAppState extends State<AgroTopApp> {
  static const _themeKey = 'theme_mode';
  late final ApiClient _api;
  late ThemeMode _themeMode;
  bool _restoring = true;
  bool _hasSession = false;

  @override
  void initState() {
    super.initState();
    _api = widget.apiClient ?? ApiClient(tokenStore: const SecureTokenStore());
    _themeMode = switch (widget.preferences.getString(_themeKey)) {
      'light' => ThemeMode.light,
      'system' => ThemeMode.system,
      _ => ThemeMode.dark,
    };
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    final restored = await _api.restoreSession();
    if (!mounted) return;
    setState(() {
      _hasSession = restored;
      _restoring = false;
    });
  }

  Future<void> _setTheme(ThemeMode mode) async {
    setState(() => _themeMode = mode);
    await widget.preferences.setString(_themeKey, mode.name);
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'AgroTop',
    debugShowCheckedModeBanner: false,
    theme: AppThemes.light,
    darkTheme: AppThemes.dark,
    themeMode: _themeMode,
    home: _restoring
        ? const Scaffold(body: Center(child: CircularProgressIndicator()))
        : _hasSession
        ? AnimalsPage(
            api: _api,
            themeMode: _themeMode,
            onThemeChanged: _setTheme,
            onUnauthorized: () => setState(() => _hasSession = false),
          )
        : LoginPage(
            api: _api,
            themeMode: _themeMode,
            onThemeChanged: _setTheme,
            onLoggedIn: () => setState(() => _hasSession = true),
          ),
  );
}

class ThemePicker extends StatelessWidget {
  const ThemePicker({super.key, required this.value, required this.onChanged});

  final ThemeMode value;
  final ValueChanged<ThemeMode> onChanged;

  @override
  Widget build(BuildContext context) => PopupMenuButton<ThemeMode>(
    tooltip: 'Escolher tema',
    initialValue: value,
    onSelected: onChanged,
    icon: const Icon(Icons.brightness_6_outlined),
    itemBuilder: (_) => const [
      PopupMenuItem(
        value: ThemeMode.dark,
        child: ListTile(
          leading: Icon(Icons.dark_mode_outlined),
          title: Text('Escuro'),
        ),
      ),
      PopupMenuItem(
        value: ThemeMode.light,
        child: ListTile(
          leading: Icon(Icons.light_mode_outlined),
          title: Text('Claro'),
        ),
      ),
      PopupMenuItem(
        value: ThemeMode.system,
        child: ListTile(
          leading: Icon(Icons.settings_brightness_outlined),
          title: Text('Seguir o sistema'),
        ),
      ),
    ],
  );
}
