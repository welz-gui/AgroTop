class AnimalModel {
  final String id;
  final String breed;
  final String sex;
  final String? birthDate;
  final String entryDate;
  final String? loteId;
  final String status;
  final String? category;
  final String? origin;
  final String? notes;
  final double? currentWeight;
  final double? gmd;

  AnimalModel({
    required this.id,
    required this.breed,
    required this.sex,
    this.birthDate,
    required this.entryDate,
    this.loteId,
    required this.status,
    this.category,
    this.origin,
    this.notes,
    this.currentWeight,
    this.gmd,
  });

  factory AnimalModel.fromJson(Map<String, dynamic> json) {
    return AnimalModel(
      id: json['animal_id'] ?? json['id'] ?? '',
      breed: json['breed'] ?? 'Nelore',
      sex: json['sex'] ?? 'M',
      birthDate: json['birth_date'],
      entryDate: json['entry_date'] ?? '',
      loteId: json['lote_id'],
      status: json['status'] ?? 'ativo',
      category: json['category'],
      origin: json['fornecedor_id'] ?? json['origin'],
      notes: json['notes'],
      currentWeight: (json['current_weight'] as num?)?.toDouble(),
      gmd: (json['gmd'] as num?)?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'animal_id': id,
      'breed': breed,
      'sex': sex,
      'birth_date': birthDate,
      'entry_date': entryDate,
      'lote_id': loteId,
      'status': status,
      'category': category,
      'notes': notes,
    };
  }
}
