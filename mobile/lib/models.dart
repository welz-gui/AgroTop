class SessionUser {
  const SessionUser({
    required this.id,
    required this.username,
    required this.name,
    required this.role,
  });

  final int id;
  final String username;
  final String name;
  final String role;

  factory SessionUser.fromJson(Map<String, dynamic> json) => SessionUser(
    id: json['id'] as int,
    username: json['username'] as String,
    name: json['name'] as String,
    role: json['role'] as String,
  );
}

class AnimalSummary {
  const AnimalSummary({
    required this.id,
    this.breed,
    this.sex,
    this.birthDate,
    this.entryWeight,
    this.currentWeight,
    this.targetWeight,
    this.status,
    this.loteId,
    this.lotName,
    this.animalUuid,
  });

  final String id;
  final String? breed;
  final String? sex;
  final String? birthDate;
  final double? entryWeight;
  final double? currentWeight;
  final double? targetWeight;
  final String? status;
  final Object? loteId;
  final String? lotName;
  final String? animalUuid;

  factory AnimalSummary.fromJson(Map<String, dynamic> json) => AnimalSummary(
    id: json['id'] as String,
    breed: json['breed'] as String?,
    sex: json['sex'] as String?,
    birthDate: json['birth_date'] as String?,
    entryWeight: (json['entry_weight'] as num?)?.toDouble(),
    currentWeight: (json['current_weight'] as num?)?.toDouble(),
    targetWeight: (json['target_weight'] as num?)?.toDouble(),
    status: json['status'] as String?,
    loteId: json['lote_id'],
    lotName: json['lot_name'] as String?,
    animalUuid: json['animal_uuid'] as String?,
  );
}

class AnimalDetail extends AnimalSummary {
  const AnimalDetail({
    required super.id,
    super.breed,
    super.sex,
    super.birthDate,
    super.entryWeight,
    super.currentWeight,
    super.targetWeight,
    super.status,
    super.loteId,
    super.lotName,
    super.animalUuid,
    this.entryDate,
    this.fornecedorId,
    this.fornecedorName,
    this.gmdRecent,
    this.gmdTotal,
  });

  final String? entryDate;
  final int? fornecedorId;
  final String? fornecedorName;
  final double? gmdRecent;
  final double? gmdTotal;

  factory AnimalDetail.fromJson(Map<String, dynamic> json) => AnimalDetail(
    id: json['id'] as String,
    breed: json['breed'] as String?,
    sex: json['sex'] as String?,
    birthDate: json['birth_date'] as String?,
    entryWeight: (json['entry_weight'] as num?)?.toDouble(),
    currentWeight: (json['current_weight'] as num?)?.toDouble(),
    targetWeight: (json['target_weight'] as num?)?.toDouble(),
    status: json['status'] as String?,
    loteId: json['lote_id'],
    lotName: json['lot_name'] as String?,
    animalUuid: json['animal_uuid'] as String?,
    entryDate: json['entry_date'] as String?,
    fornecedorId: json['fornecedor_id'] as int?,
    fornecedorName: json['fornecedor_name'] as String?,
    gmdRecent: (json['gmd_recent_kg_day'] as num?)?.toDouble(),
    gmdTotal: (json['gmd_total_kg_day'] as num?)?.toDouble(),
  );
}

class WeighingResult {
  const WeighingResult({
    required this.status,
    required this.message,
    required this.animalId,
    required this.peso,
    required this.data,
  });

  final String status;
  final String message;
  final String animalId;
  final double peso;
  final String data;

  factory WeighingResult.fromJson(Map<String, dynamic> json) => WeighingResult(
    status: json['status'] as String,
    message: json['message'] as String,
    animalId: json['animal_id'] as String,
    peso: (json['peso'] as num).toDouble(),
    data: json['data'] as String,
  );
}

class LoteSummary {
  const LoteSummary({
    required this.id,
    required this.nome,
    required this.animaisAtivos,
    this.capacidadeUa,
  });

  final String id;
  final String nome;
  final double? capacidadeUa;
  final int animaisAtivos;

  factory LoteSummary.fromJson(Map<String, dynamic> json) => LoteSummary(
    id: json['id'] as String,
    nome: json['nome'] as String,
    capacidadeUa: (json['capacidade_ua'] as num?)?.toDouble(),
    animaisAtivos: json['animais_ativos'] as int,
  );
}

class MovementResult {
  const MovementResult({
    required this.movidos,
    required this.jaNoDestino,
    required this.erros,
  });

  final List<String> movidos;
  final List<String> jaNoDestino;
  final List<String> erros;

  factory MovementResult.fromJson(Map<String, dynamic> json) => MovementResult(
    movidos: List<String>.from(json['movidos'] as List<dynamic>),
    jaNoDestino: List<String>.from(json['ja_no_destino'] as List<dynamic>),
    erros: List<String>.from(json['erros'] as List<dynamic>),
  );
}
