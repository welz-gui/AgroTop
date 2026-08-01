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
    required this.breed,
    required this.sex,
    required this.currentWeight,
    required this.targetWeight,
    this.loteId,
  });

  final String id;
  final String breed;
  final String sex;
  final double currentWeight;
  final double targetWeight;
  final String? loteId;

  factory AnimalSummary.fromJson(Map<String, dynamic> json) => AnimalSummary(
    id: json['id'] as String,
    breed: json['breed'] as String,
    sex: json['sex'] as String,
    currentWeight: (json['current_weight'] as num).toDouble(),
    targetWeight: (json['target_weight'] as num).toDouble(),
    loteId: json['lote_id'] as String?,
  );
}

class AnimalDetail extends AnimalSummary {
  const AnimalDetail({
    required super.id,
    required super.breed,
    required super.sex,
    required super.currentWeight,
    required super.targetWeight,
    super.loteId,
    this.loteName,
    this.birthDate,
    this.entryDate,
    this.entryWeight,
    this.gmdRecent,
    this.gmdTotal,
  });

  final String? loteName;
  final String? birthDate;
  final String? entryDate;
  final double? entryWeight;
  final double? gmdRecent;
  final double? gmdTotal;

  factory AnimalDetail.fromJson(Map<String, dynamic> json) => AnimalDetail(
    id: json['id'] as String,
    breed: json['breed'] as String,
    sex: json['sex'] as String,
    currentWeight: (json['current_weight'] as num).toDouble(),
    targetWeight: (json['target_weight'] as num).toDouble(),
    loteId: json['lote_id'] as String?,
    loteName: json['lote_name'] as String?,
    birthDate: json['birth_date'] as String?,
    entryDate: json['entry_date'] as String?,
    entryWeight: (json['entry_weight'] as num?)?.toDouble(),
    gmdRecent: (json['gmd_recent_kg_day'] as num?)?.toDouble(),
    gmdTotal: (json['gmd_total_kg_day'] as num?)?.toDouble(),
  );
}
