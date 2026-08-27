import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

class CachedData<T> {
  const CachedData({required this.data, required this.timestamp});

  final T data;
  final DateTime timestamp;

  String get formattedTime {
    final h = timestamp.hour.toString().padLeft(2, '0');
    final m = timestamp.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }
}

class ShallowCache {
  const ShallowCache(this._prefs);

  final SharedPreferences _prefs;

  static const _animalsKey = 'cache_animais_list';
  static const _animalsTimeKey = 'cache_animais_list_time';
  static const _lotesKey = 'cache_lotes_list';
  static const _lotesTimeKey = 'cache_lotes_list_time';
  static const _animalDetailKeyPrefix = 'cache_animal_detail_';
  static const _animalDetailTimeKeyPrefix = 'cache_animal_detail_time_';

  Future<void> saveAnimals(List<AnimalSummary> animals) async {
    final jsonList = animals
        .map(
          (a) => {
            'id': a.id,
            'breed': a.breed,
            'sex': a.sex,
            'birth_date': a.birthDate,
            'entry_weight': a.entryWeight,
            'current_weight': a.currentWeight,
            'target_weight': a.targetWeight,
            'status': a.status,
            'lote_id': a.loteId,
            'lot_name': a.lotName,
            'animal_uuid': a.animalUuid,
          },
        )
        .toList(growable: false);
    await _prefs.setString(_animalsKey, jsonEncode(jsonList));
    await _prefs.setString(_animalsTimeKey, DateTime.now().toIso8601String());
  }

  CachedData<List<AnimalSummary>>? getAnimals() {
    final raw = _prefs.getString(_animalsKey);
    final timeStr = _prefs.getString(_animalsTimeKey);
    if (raw == null || timeStr == null) return null;
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      final animals = list
          .map((e) => AnimalSummary.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
      final time = DateTime.parse(timeStr);
      return CachedData(data: animals, timestamp: time);
    } catch (_) {
      return null;
    }
  }

  Future<void> saveAnimalDetail(AnimalDetail detail) async {
    final map = {
      'id': detail.id,
      'breed': detail.breed,
      'sex': detail.sex,
      'birth_date': detail.birthDate,
      'entry_weight': detail.entryWeight,
      'current_weight': detail.currentWeight,
      'target_weight': detail.targetWeight,
      'status': detail.status,
      'lote_id': detail.loteId,
      'lot_name': detail.lotName,
      'animal_uuid': detail.animalUuid,
      'entry_date': detail.entryDate,
      'fornecedor_id': detail.fornecedorId,
      'fornecedor_name': detail.fornecedorName,
      'gmd_recent_kg_day': detail.gmdRecent,
      'gmd_total_kg_day': detail.gmdTotal,
    };
    await _prefs.setString(
      '$_animalDetailKeyPrefix${detail.id}',
      jsonEncode(map),
    );
    await _prefs.setString(
      '$_animalDetailTimeKeyPrefix${detail.id}',
      DateTime.now().toIso8601String(),
    );
  }

  CachedData<AnimalDetail>? getAnimalDetail(String animalId) {
    final raw = _prefs.getString('$_animalDetailKeyPrefix$animalId');
    final timeStr = _prefs.getString('$_animalDetailTimeKeyPrefix$animalId');
    if (raw == null || timeStr == null) return null;
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      final detail = AnimalDetail.fromJson(map);
      final time = DateTime.parse(timeStr);
      return CachedData(data: detail, timestamp: time);
    } catch (_) {
      return null;
    }
  }

  Future<void> saveLotes(List<LoteSummary> lotes) async {
    final jsonList = lotes
        .map(
          (l) => {
            'id': l.id,
            'nome': l.nome,
            'capacidade_ua': l.capacidadeUa,
            'animais_ativos': l.animaisAtivos,
          },
        )
        .toList(growable: false);
    await _prefs.setString(_lotesKey, jsonEncode(jsonList));
    await _prefs.setString(_lotesTimeKey, DateTime.now().toIso8601String());
  }

  CachedData<List<LoteSummary>>? getLotes() {
    final raw = _prefs.getString(_lotesKey);
    final timeStr = _prefs.getString(_lotesTimeKey);
    if (raw == null || timeStr == null) return null;
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      final lotes = list
          .map((e) => LoteSummary.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
      final time = DateTime.parse(timeStr);
      return CachedData(data: lotes, timestamp: time);
    } catch (_) {
      return null;
    }
  }
}
