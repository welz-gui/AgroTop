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

class ProtocoloSummary {
  const ProtocoloSummary({
    required this.id,
    required this.nome,
    required this.via,
    required this.carenciaDias,
    required this.unidadeDose,
    this.doseSugerida,
  });

  final int id;
  final String nome;
  final String via;
  final int carenciaDias;
  final String unidadeDose;
  final double? doseSugerida;

  factory ProtocoloSummary.fromJson(Map<String, dynamic> json) =>
      ProtocoloSummary(
        id: json['id'] as int,
        nome: json['nome'] as String,
        via: (json['via'] as String?) ?? '',
        carenciaDias: (json['carencia_dias'] as num?)?.toInt() ?? 0,
        unidadeDose: (json['unidade_dose'] as String?) ?? '',
        doseSugerida: (json['dose_sugerida'] as num?)?.toDouble(),
      );
}

class MedicationApplication {
  const MedicationApplication({
    required this.medicamento,
    required this.dose,
    required this.unidade,
    required this.via,
    required this.carenciaDias,
    required this.data,
    this.protocoloId,
  });

  final String medicamento;
  final double dose;
  final String unidade;
  final String via;
  final int carenciaDias;
  final String data;
  final int? protocoloId;

  factory MedicationApplication.fromJson(Map<String, dynamic> json) =>
      MedicationApplication(
        medicamento: json['medicamento'] as String,
        dose: (json['dose'] as num).toDouble(),
        unidade: (json['unidade'] as String?) ?? '',
        via: (json['via'] as String?) ?? '',
        carenciaDias: (json['carencia_dias'] as num?)?.toInt() ?? 0,
        data: json['data'] as String,
        protocoloId: json['protocolo_id'] as int?,
      );
}

class AnimalMedications {
  const AnimalMedications({this.carenciaAte, required this.aplicacoes});

  final String? carenciaAte;
  final List<MedicationApplication> aplicacoes;

  factory AnimalMedications.fromJson(Map<String, dynamic> json) =>
      AnimalMedications(
        carenciaAte: json['carencia_ate'] as String?,
        aplicacoes:
            (json['aplicacoes'] as List<dynamic>?)
                ?.map(
                  (e) =>
                      MedicationApplication.fromJson(e as Map<String, dynamic>),
                )
                .toList(growable: false) ??
            const [],
      );
}

class AnimalPhoto {
  const AnimalPhoto({
    required this.id,
    required this.takenDate,
    required this.mime,
  });

  final int id;
  final String takenDate;
  final String mime;

  factory AnimalPhoto.fromJson(Map<String, dynamic> json) => AnimalPhoto(
    id: json['id'] as int,
    takenDate: json['taken_date'] as String,
    mime: json['mime'] as String,
  );
}

class CsvImportAccepted {
  const CsvImportAccepted({
    required this.animalId,
    required this.peso,
    required this.data,
    required this.alertas,
  });

  final String animalId;
  final double peso;
  final String data;
  final List<String> alertas;

  factory CsvImportAccepted.fromJson(Map<String, dynamic> json) =>
      CsvImportAccepted(
        animalId: json['animal_id'] as String,
        peso: (json['peso'] as num).toDouble(),
        data: json['data'] as String,
        alertas: List<String>.from(
          json['alertas'] as List<dynamic>? ?? const [],
        ),
      );
}

class CsvImportRejected {
  const CsvImportRejected({
    required this.linha,
    required this.conteudo,
    required this.motivo,
  });

  final int linha;
  final String conteudo;
  final String motivo;

  factory CsvImportRejected.fromJson(Map<String, dynamic> json) =>
      CsvImportRejected(
        linha: (json['linha'] as num).toInt(),
        conteudo: json['conteudo'] as String,
        motivo: json['motivo'] as String,
      );
}

class CsvImportResult {
  const CsvImportResult({
    required this.totalLinhas,
    required this.aceitas,
    required this.rejeitadas,
    required this.gravadas,
  });

  final int totalLinhas;
  final List<CsvImportAccepted> aceitas;
  final List<CsvImportRejected> rejeitadas;
  final int gravadas;

  factory CsvImportResult.fromJson(
    Map<String, dynamic> json,
  ) => CsvImportResult(
    totalLinhas: (json['total_linhas'] as num).toInt(),
    aceitas: (json['aceitas'] as List<dynamic>? ?? const [])
        .map((item) => CsvImportAccepted.fromJson(item as Map<String, dynamic>))
        .toList(growable: false),
    rejeitadas: (json['rejeitadas'] as List<dynamic>? ?? const [])
        .map((item) => CsvImportRejected.fromJson(item as Map<String, dynamic>))
        .toList(growable: false),
    gravadas: (json['gravadas'] as num).toInt(),
  );
}

class PendingFeeding {
  const PendingFeeding({
    required this.planId,
    required this.loteId,
    required this.loteNome,
    required this.produto,
    required this.quantidade,
    required this.unidade,
    required this.frequencia,
    required this.confirmadoNoPeriodo,
    this.insumoId,
    this.ultimaConfirmacao,
  });

  final int planId;
  final String loteId;
  final String loteNome;
  final String produto;
  final double quantidade;
  final String unidade;
  final String frequencia;
  final int? insumoId;
  final bool confirmadoNoPeriodo;
  final String? ultimaConfirmacao;

  factory PendingFeeding.fromJson(Map<String, dynamic> json) => PendingFeeding(
    planId: (json['plano_id'] as num).toInt(),
    loteId: json['lote_id'].toString(),
    loteNome: json['lote_nome'] as String,
    produto: json['produto'] as String,
    quantidade: (json['quantidade'] as num).toDouble(),
    unidade: json['unidade'] as String,
    frequencia: json['frequencia'] as String,
    insumoId: (json['insumo_id'] as num?)?.toInt(),
    confirmadoNoPeriodo: json['confirmado_no_periodo'] as bool,
    ultimaConfirmacao: json['ultima_confirmacao'] as String?,
  );

  PendingFeeding confirmedNow() => PendingFeeding(
    planId: planId,
    loteId: loteId,
    loteNome: loteNome,
    produto: produto,
    quantidade: quantidade,
    unidade: unidade,
    frequencia: frequencia,
    insumoId: insumoId,
    confirmadoNoPeriodo: true,
    ultimaConfirmacao: ultimaConfirmacao,
  );
}
