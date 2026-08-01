import 'package:agrotop_mobile/api_client.dart';

class MemoryTokenStore implements TokenStore {
  String? token;

  @override
  Future<void> clear() async => token = null;

  @override
  Future<String?> read() async => token;

  @override
  Future<void> write(String value) async => token = value;
}

Future<void> main(List<String> arguments) async {
  if (arguments.length != 3) {
    throw ArgumentError('uso: dart run tool/live_flow.dart URL USUARIO SENHA');
  }
  final api = ApiClient(tokenStore: MemoryTokenStore(), baseUrl: arguments[0]);
  final login = await api.login(arguments[1], arguments[2]);
  final animals = await api.listAnimals();
  if (animals.isEmpty) throw StateError('A API não devolveu animais ativos.');
  final detail = await api.getAnimal(animals.first.id);
  // Ferramenta de validação CLI: a saída é a evidência consumida pelo relatório.
  // ignore: avoid_print
  print(
    'login=${login.user.username}; animais=${animals.length}; '
    'ficha=${detail.id}; gmd_recente=${detail.gmdRecent}; gmd_total=${detail.gmdTotal}',
  );
}
