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

class OperationalAlerts {
  const OperationalAlerts({
    required this.sumidos,
    required this.carencia,
    required this.prontosParaAbate,
    required this.estoqueBaixo,
    required this.baixoDesempenho,
  });

  final List<MissingAnimalAlert> sumidos;
  final List<WithdrawalAlert> carencia;
  final List<SlaughterAlert> prontosParaAbate;
  final List<LowStockAlert> estoqueBaixo;
  final List<LowPerformanceAlert> baixoDesempenho;

  int get total =>
      sumidos.length +
      carencia.length +
      prontosParaAbate.length +
      estoqueBaixo.length +
      baixoDesempenho.length;

  factory OperationalAlerts.fromJson(
    Map<String, dynamic> json,
  ) => OperationalAlerts(
    sumidos: (json['sumidos'] as List<dynamic>? ?? const [])
        .map(
          (item) => MissingAnimalAlert.fromJson(item as Map<String, dynamic>),
        )
        .toList(growable: false),
    carencia: (json['carencia'] as List<dynamic>? ?? const [])
        .map((item) => WithdrawalAlert.fromJson(item as Map<String, dynamic>))
        .toList(growable: false),
    prontosParaAbate: (json['prontos_para_abate'] as List<dynamic>? ?? const [])
        .map((item) => SlaughterAlert.fromJson(item as Map<String, dynamic>))
        .toList(growable: false),
    estoqueBaixo: (json['estoque_baixo'] as List<dynamic>? ?? const [])
        .map((item) => LowStockAlert.fromJson(item as Map<String, dynamic>))
        .toList(growable: false),
    baixoDesempenho: (json['baixo_desempenho'] as List<dynamic>? ?? const [])
        .map(
          (item) => LowPerformanceAlert.fromJson(item as Map<String, dynamic>),
        )
        .toList(growable: false),
  );
}

class MissingAnimalAlert {
  const MissingAnimalAlert({
    required this.animalId,
    required this.breed,
    required this.pesoAtual,
    required this.diasSemPesagem,
    this.loteId,
  });

  final String animalId;
  final String breed;
  final String? loteId;
  final double pesoAtual;
  final int diasSemPesagem;

  factory MissingAnimalAlert.fromJson(Map<String, dynamic> json) =>
      MissingAnimalAlert(
        animalId: json['animal_id'] as String,
        breed: json['breed'] as String,
        loteId: json['lote_id'] as String?,
        pesoAtual: (json['peso_atual'] as num).toDouble(),
        diasSemPesagem: (json['dias_sem_pesagem'] as num).toInt(),
      );
}

class WithdrawalAlert {
  const WithdrawalAlert({
    required this.animalId,
    required this.breed,
    required this.carenciaAte,
    required this.diasRestantes,
  });

  final String animalId;
  final String breed;
  final String carenciaAte;
  final int diasRestantes;

  factory WithdrawalAlert.fromJson(Map<String, dynamic> json) =>
      WithdrawalAlert(
        animalId: json['animal_id'] as String,
        breed: json['breed'] as String,
        carenciaAte: json['carencia_ate'] as String,
        diasRestantes: (json['dias_restantes'] as num).toInt(),
      );
}

class SlaughterAlert {
  const SlaughterAlert({
    required this.animalId,
    required this.breed,
    required this.pesoAtual,
    required this.pesoAlvo,
    required this.arrobas,
  });

  final String animalId;
  final String breed;
  final double pesoAtual;
  final double pesoAlvo;
  final double arrobas;

  factory SlaughterAlert.fromJson(Map<String, dynamic> json) => SlaughterAlert(
    animalId: json['animal_id'] as String,
    breed: json['breed'] as String,
    pesoAtual: (json['peso_atual'] as num).toDouble(),
    pesoAlvo: (json['peso_alvo'] as num).toDouble(),
    arrobas: (json['arrobas'] as num).toDouble(),
  );
}

class LowStockAlert {
  const LowStockAlert({
    required this.insumoId,
    required this.nome,
    required this.estoqueAtual,
    required this.estoqueMinimo,
    required this.unidade,
  });

  final int insumoId;
  final String nome;
  final double estoqueAtual;
  final double estoqueMinimo;
  final String unidade;

  factory LowStockAlert.fromJson(Map<String, dynamic> json) => LowStockAlert(
    insumoId: (json['insumo_id'] as num).toInt(),
    nome: json['nome'] as String,
    estoqueAtual: (json['estoque_atual'] as num).toDouble(),
    estoqueMinimo: (json['estoque_minimo'] as num).toDouble(),
    unidade: json['unidade'] as String,
  );
}

class LowPerformanceAlert {
  const LowPerformanceAlert({
    required this.animalId,
    required this.breed,
    required this.pesoAtual,
    required this.gmd,
    required this.gmdReferencia,
    this.loteId,
  });

  final String animalId;
  final String breed;
  final String? loteId;
  final double pesoAtual;
  final double gmd;
  final double gmdReferencia;

  factory LowPerformanceAlert.fromJson(Map<String, dynamic> json) =>
      LowPerformanceAlert(
        animalId: json['animal_id'] as String,
        breed: json['breed'] as String,
        loteId: json['lote_id'] as String?,
        pesoAtual: (json['peso_atual'] as num).toDouble(),
        gmd: (json['gmd'] as num).toDouble(),
        gmdReferencia:
            (json['meta'
                        '_gmd']
                    as num)
                .toDouble(),
      );
}

class DeviceLookup {
  const DeviceLookup({
    required this.id,
    required this.codigoVisual,
    required this.tipo,
    required this.status,
    required this.transicoesPermitidas,
    this.lote,
  });

  final String id;
  final String codigoVisual;
  final String tipo;
  final String status;
  final String? lote;
  final List<DeviceTransition> transicoesPermitidas;

  factory DeviceLookup.fromJson(Map<String, dynamic> json) => DeviceLookup(
    id: json['id'] as String,
    codigoVisual: json['codigo_visual'] as String,
    tipo: json['tipo'] as String,
    status: json['status'] as String,
    lote: json['lote'] as String?,
    transicoesPermitidas:
        (json['transicoes_permitidas'] as List<dynamic>? ?? const [])
            .map(
              (item) => DeviceTransition.fromJson(item as Map<String, dynamic>),
            )
            .toList(growable: false),
  );
}

class DeviceTransition {
  const DeviceTransition({
    required this.para,
    required this.exigeMotivo,
    required this.exigeAutorizacao,
  });

  final String para;
  final bool exigeMotivo;
  final bool exigeAutorizacao;

  factory DeviceTransition.fromJson(Map<String, dynamic> json) =>
      DeviceTransition(
        para: json['para'] as String,
        exigeMotivo: json['exige_motivo'] as bool,
        exigeAutorizacao: json['exige_autorizacao'] as bool,
      );
}

class DeviceStatusUpdate {
  const DeviceStatusUpdate({required this.de, required this.para});

  final String de;
  final String para;

  factory DeviceStatusUpdate.fromJson(Map<String, dynamic> json) =>
      DeviceStatusUpdate(
        de: json['de'] as String,
        para: json['para'] as String,
      );
}
