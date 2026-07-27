import 'package:supabase_flutter/supabase_flutter.dart';

class SupabaseConfig {
  static const String url = 'https://mwjvulwglewoyeximgtv.supabase.co';
  static const String anonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im13anZ1bHdnbGV3b3lleGltZ3R2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjE5MzgxNTksImV4cCI6MjAzNzUxNDE1OX0.placeholder_anon_key'; // Chave pública Anon

  static Future<void> initialize() async {
    await Supabase.initialize(
      url: url,
      anonKey: anonKey,
      authOptions: const FlutterAuthClientOptions(
        authFlowType: AuthFlowType.pkce,
      ),
    );
  }

  static SupabaseClient get client => Supabase.instance.client;
}
