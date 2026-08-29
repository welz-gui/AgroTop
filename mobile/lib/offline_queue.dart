import 'dart:convert';

import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';
import 'package:uuid/uuid.dart';

import 'api_client.dart';

class QueueItem {
  const QueueItem({
    this.id,
    required this.clientUuid,
    required this.endpoint,
    required this.metodo,
    required this.payloadJson,
    required this.criadoEm,
    this.tentativas = 0,
    this.ultimoErro,
  });

  final int? id;
  final String clientUuid;
  final String endpoint;
  final String metodo;
  final String payloadJson;
  final DateTime criadoEm;
  final int tentativas;
  final String? ultimoErro;

  Map<String, dynamic> toMap() => {
    if (id != null) 'id': id,
    'client_uuid': clientUuid,
    'endpoint': endpoint,
    'metodo': metodo,
    'payload_json': payloadJson,
    'criado_em': criadoEm.toIso8601String(),
    'tentativas': tentativas,
    'ultimo_erro': ultimoErro,
  };

  factory QueueItem.fromMap(Map<String, dynamic> map) => QueueItem(
    id: map['id'] as int?,
    clientUuid: map['client_uuid'] as String,
    endpoint: map['endpoint'] as String,
    metodo: map['metodo'] as String,
    payloadJson: map['payload_json'] as String,
    criadoEm: DateTime.parse(map['criado_em'] as String),
    tentativas: (map['tentativas'] as num?)?.toInt() ?? 0,
    ultimoErro: map['ultimo_erro'] as String?,
  );

  Map<String, dynamic> get payload {
    try {
      return jsonDecode(payloadJson) as Map<String, dynamic>;
    } catch (_) {
      return const {};
    }
  }

  String get description {
    final p = payload;
    if (endpoint.contains('/pesagens')) {
      final peso = p['peso'] ?? '';
      final animalId = p['animal_id'] ?? endpoint.split('/')[2];
      return 'Pesagem $peso kg ($animalId)';
    }
    if (endpoint.contains('/medicamentos')) {
      final med = p['medicamento'] ?? 'Medicamento';
      final animalId = p['animal_id'] ?? endpoint.split('/')[2];
      return 'Medicamento $med ($animalId)';
    }
    if (endpoint.contains('/movimentar')) {
      final lote = p['to_lote_id'] ?? '';
      final animals = (p['animal_ids'] as List<dynamic>?)?.length ?? 1;
      return 'Movimentação de $animals animal(is) para $lote';
    }
    return '$metodo $endpoint';
  }
}

abstract class OfflineQueueStorage {
  Future<void> insert(QueueItem item);
  Future<int> count();
  Future<List<QueueItem>> getAll();
  Future<void> delete(int id);
  Future<void> updateAttempt(int id, String error);
  Future<void> clear();
}

class SqfliteQueueStorage implements OfflineQueueStorage {
  SqfliteQueueStorage({Future<Database> Function()? databaseOpener})
      : _databaseOpener = databaseOpener ?? _defaultOpenDb;

  final Future<Database> Function() _databaseOpener;
  Database? _database;

  static Future<Database> _defaultOpenDb() async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, 'agrotop_offline.db');
    return openDatabase(
      path,
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE fila_pendente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_uuid TEXT NOT NULL UNIQUE,
            endpoint TEXT NOT NULL,
            metodo TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            tentativas INTEGER NOT NULL DEFAULT 0,
            ultimo_erro TEXT
          )
        ''');
      },
    );
  }

  Future<Database> get _db async => _database ??= await _databaseOpener();

  @override
  Future<void> insert(QueueItem item) async {
    final db = await _db;
    await db.insert('fila_pendente', item.toMap());
  }

  @override
  Future<int> count() async {
    final db = await _db;
    final res = await db.rawQuery('SELECT COUNT(*) as total FROM fila_pendente');
    return Sqflite.firstIntValue(res) ?? 0;
  }

  @override
  Future<List<QueueItem>> getAll() async {
    final db = await _db;
    final rows = await db.query('fila_pendente', orderBy: 'id ASC');
    return rows.map(QueueItem.fromMap).toList(growable: false);
  }

  @override
  Future<void> delete(int id) async {
    final db = await _db;
    await db.delete('fila_pendente', where: 'id = ?', whereArgs: [id]);
  }

  @override
  Future<void> updateAttempt(int id, String error) async {
    final db = await _db;
    await db.rawUpdate(
      'UPDATE fila_pendente SET tentativas = tentativas + 1, ultimo_erro = ? WHERE id = ?',
      [error, id],
    );
  }

  @override
  Future<void> clear() async {
    final db = await _db;
    await db.delete('fila_pendente');
  }
}

class MemoryQueueStorage implements OfflineQueueStorage {
  int _nextId = 1;
  final List<QueueItem> _items = [];

  @override
  Future<void> insert(QueueItem item) async {
    final withId = item.id != null
        ? item
        : QueueItem(
            id: _nextId++,
            clientUuid: item.clientUuid,
            endpoint: item.endpoint,
            metodo: item.metodo,
            payloadJson: item.payloadJson,
            criadoEm: item.criadoEm,
            tentativas: item.tentativas,
            ultimoErro: item.ultimoErro,
          );
    _items.add(withId);
  }

  @override
  Future<int> count() async => _items.length;

  @override
  Future<List<QueueItem>> getAll() async => List.unmodifiable(_items);

  @override
  Future<void> delete(int id) async {
    _items.removeWhere((item) => item.id == id);
  }

  @override
  Future<void> updateAttempt(int id, String error) async {
    final index = _items.indexWhere((item) => item.id == id);
    if (index >= 0) {
      final old = _items[index];
      _items[index] = QueueItem(
        id: old.id,
        clientUuid: old.clientUuid,
        endpoint: old.endpoint,
        metodo: old.metodo,
        payloadJson: old.payloadJson,
        criadoEm: old.criadoEm,
        tentativas: old.tentativas + 1,
        ultimoErro: error,
      );
    }
  }

  @override
  Future<void> clear() async {
    _items.clear();
  }
}

class SyncItemSuccess {
  const SyncItemSuccess({required this.item, required this.description});

  final QueueItem item;
  final String description;
}

class SyncItemPending {
  const SyncItemPending({
    required this.item,
    required this.description,
    this.reason,
  });

  final QueueItem item;
  final String description;
  final String? reason;
}

class SyncItemRejected {
  const SyncItemRejected({
    required this.item,
    required this.description,
    required this.reason,
  });

  final QueueItem item;
  final String description;
  final String reason;
}

class SyncReport {
  const SyncReport({
    required this.sincronizados,
    required this.pendentes,
    required this.rejeitados,
  });

  final List<SyncItemSuccess> sincronizados;
  final List<SyncItemPending> pendentes;
  final List<SyncItemRejected> rejeitados;

  bool get isClean => pendentes.isEmpty && rejeitados.isEmpty;
  int get total => sincronizados.length + pendentes.length + rejeitados.length;
}

class OfflineQueue {
  OfflineQueue({
    OfflineQueueStorage? storage,
    Future<Database> Function()? databaseOpener,
  }) : _storage = storage ??
            SqfliteQueueStorage(databaseOpener: databaseOpener);

  final OfflineQueueStorage _storage;
  bool _isSyncing = false;
  static const _uuid = Uuid();

  Future<String> enqueueWeighing({
    required String animalId,
    required double peso,
    required String data,
    String method = 'pesado',
    String notes = '',
  }) async {
    final clientUuid = _uuid.v4();
    final payload = {
      'animal_id': animalId,
      'peso': peso,
      'data': data,
      'method': method,
      'notes': notes,
    };
    final item = QueueItem(
      clientUuid: clientUuid,
      endpoint: '/animais/$animalId/pesagens',
      metodo: 'POST',
      payloadJson: jsonEncode(payload),
      criadoEm: DateTime.now(),
    );
    await _storage.insert(item);
    return clientUuid;
  }

  Future<String> enqueueMedication({
    required String animalId,
    required String medicamento,
    required double dose,
    required String unidade,
    required String via,
    required int carenciaDias,
    required String data,
    int? protocoloId,
    String? notas,
  }) async {
    final clientUuid = _uuid.v4();
    final payload = {
      'animal_id': animalId,
      'medicamento': medicamento,
      'dose': dose,
      'unidade': unidade,
      'via': via,
      'carencia_dias': carenciaDias,
      'data': data,
      'protocolo_id': protocoloId,
      'notas': notas,
    };
    final item = QueueItem(
      clientUuid: clientUuid,
      endpoint: '/animais/$animalId/medicamentos',
      metodo: 'POST',
      payloadJson: jsonEncode(payload),
      criadoEm: DateTime.now(),
    );
    await _storage.insert(item);
    return clientUuid;
  }

  Future<String> enqueueMovement({
    required List<String> animalIds,
    required String toLoteId,
    required String movementDate,
    String? reason = 'manejo',
    String? notes,
  }) async {
    final clientUuid = _uuid.v4();
    final payload = {
      'animal_ids': animalIds,
      'to_lote_id': toLoteId,
      'movement_date': movementDate,
      'reason': reason,
      'notes': notes,
    };
    final item = QueueItem(
      clientUuid: clientUuid,
      endpoint: '/animais/movimentar',
      metodo: 'POST',
      payloadJson: jsonEncode(payload),
      criadoEm: DateTime.now(),
    );
    await _storage.insert(item);
    return clientUuid;
  }

  Future<int> countPending() => _storage.count();

  Future<List<QueueItem>> getPendingItems() => _storage.getAll();

  Future<void> deleteItem(int id) => _storage.delete(id);

  Future<void> recordAttempt(int id, String error) =>
      _storage.updateAttempt(id, error);

  Future<void> clear() => _storage.clear();

  Future<SyncReport> sync(ApiClient api) async {
    if (_isSyncing) {
      return const SyncReport(
        sincronizados: [],
        pendentes: [],
        rejeitados: [],
      );
    }
    _isSyncing = true;
    try {
      final items = await getPendingItems();
      final sincronizados = <SyncItemSuccess>[];
      final pendentes = <SyncItemPending>[];
      final rejeitados = <SyncItemRejected>[];

      bool networkFailed = false;

      for (var i = 0; i < items.length; i++) {
        final item = items[i];
        if (networkFailed) {
          pendentes.add(
            SyncItemPending(
              item: item,
              description: item.description,
              reason: 'Falha de rede na fila.',
            ),
          );
          continue;
        }

        try {
          final p = item.payload;
          if (item.endpoint.contains('/pesagens')) {
            final animalId =
                p['animal_id']?.toString() ?? item.endpoint.split('/')[2];
            await api.registerWeighing(
              animalId,
              peso: (p['peso'] as num).toDouble(),
              data: p['data'] as String,
              method: (p['method'] as String?) ?? 'pesado',
              notes: (p['notes'] as String?) ?? '',
              idempotencyKey: item.clientUuid,
            );
          } else if (item.endpoint.contains('/medicamentos')) {
            final animalId =
                p['animal_id']?.toString() ?? item.endpoint.split('/')[2];
            await api.registerMedication(
              animalId,
              medicamento: p['medicamento'] as String,
              dose: (p['dose'] as num).toDouble(),
              unidade: p['unidade'] as String,
              via: p['via'] as String,
              carenciaDias: (p['carencia_dias'] as num).toInt(),
              data: p['data'] as String,
              protocoloId: (p['protocolo_id'] as num?)?.toInt(),
              notas: p['notas'] as String?,
              idempotencyKey: item.clientUuid,
            );
          } else if (item.endpoint.contains('/movimentar')) {
            final animalIds = (p['animal_ids'] as List<dynamic>)
                .map((e) => e.toString())
                .toList(growable: false);
            await api.moveAnimals(
              animalIds: animalIds,
              toLoteId: p['to_lote_id'].toString(),
              movementDate: p['movement_date'] as String,
              reason: p['reason'] as String?,
              notes: p['notes'] as String?,
              idempotencyKey: item.clientUuid,
            );
          }

          if (item.id != null) await deleteItem(item.id!);
          sincronizados.add(
            SyncItemSuccess(item: item, description: item.description),
          );
        } on ApiException catch (e) {
          if (item.id != null) await deleteItem(item.id!);
          rejeitados.add(
            SyncItemRejected(
              item: item,
              description: item.description,
              reason: e.message,
            ),
          );
        } catch (e) {
          networkFailed = true;
          if (item.id != null) {
            await recordAttempt(item.id!, e.toString());
          }
          pendentes.add(
            SyncItemPending(
              item: item,
              description: item.description,
              reason: 'Sem conexão.',
            ),
          );
        }
      }

      return SyncReport(
        sincronizados: sincronizados,
        pendentes: pendentes,
        rejeitados: rejeitados,
      );
    } finally {
      _isSyncing = false;
    }
  }
}
