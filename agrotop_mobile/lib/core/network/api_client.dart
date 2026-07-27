import 'dart:convert';
import 'package:http/http.dart' as http;
import 'supabase_client.dart';

class ApiClient {
  // URL base da API Python FastAPI (configurável para local/homolog/prod)
  static const String baseUrl = 'http://10.0.2.2:8000/api/v1'; // 10.0.2.2 acessa o localhost da máquina no Android Emulator

  static Future<Map<String, String>> _getHeaders() async {
    final session = SupabaseConfig.client.auth.currentSession;
    final token = session?.accessToken ?? '';
    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $token',
    };
  }

  static Future<dynamic> post(String endpoint, Map<String, dynamic> body) async {
    final headers = await _getHeaders();
    final response = await http.post(
      Uri.parse('$baseUrl$endpoint'),
      headers: headers,
      body: jsonEncode(body),
    );

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Erro na API Python [${response.statusCode}]: ${response.body}');
    }
  }

  static Future<dynamic> get(String endpoint) async {
    final headers = await _getHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl$endpoint'),
      headers: headers,
    );

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Erro na API Python [${response.statusCode}]: ${response.body}');
    }
  }
}
