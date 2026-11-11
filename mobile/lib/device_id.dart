import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

/// Onde o id deste aparelho fica guardado entre uma execução e outra.
abstract class DeviceIdStore {
  Future<String?> read();
  Future<void> write(String id);
}

class SecureDeviceIdStore implements DeviceIdStore {
  const SecureDeviceIdStore();

  static const _storage = FlutterSecureStorage();
  static const _key = 'agrotop_device_id';

  @override
  Future<String?> read() => _storage.read(key: _key);

  @override
  Future<void> write(String id) => _storage.write(key: _key, value: id);
}

/// O id deste aparelho: um UUID aleatório gerado na primeira vez e guardado. Não é número de
/// série nem dado do hardware; some se o app for desinstalado (e aí é outra instalação).
///
/// O servidor o grava em cada evento e na trilha de auditoria, para dizer de qual aparelho veio o
/// registro (PNIB §14.1). Se o armazenamento não responde, devolve `null` e a escrita segue sem
/// aparelho: registrar manejo no curral não pode depender disso. Se só a gravação falha, vale um
/// id novo até o app fechar.
Future<String?> obterIdDoAparelho(DeviceIdStore store) async {
  try {
    final salvo = await store.read();
    if (salvo != null && salvo.isNotEmpty) return salvo;
  } catch (_) {
    return null;
  }
  final novo = const Uuid().v4();
  try {
    await store.write(novo);
  } catch (_) {
    // Sem gravar, o id vale só nesta execução.
  }
  return novo;
}
