import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../api_client.dart';
import '../copy.dart';
import '../models.dart';
import '../offline_queue.dart';

const _uuid = Uuid();

String _formatDate(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-'
    '${value.month.toString().padLeft(2, '0')}-'
    '${value.day.toString().padLeft(2, '0')}';

String? _validateDate(String? value, {bool obrigatoria = true}) {
  final texto = value?.trim() ?? '';
  if (texto.isEmpty) return obrigatoria ? 'Informe a data.' : null;
  if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(texto)) {
    return 'Use o formato AAAA-MM-DD.';
  }
  final parsed = DateTime.tryParse(texto);
  if (parsed == null || _formatDate(parsed) != texto) {
    return 'Informe uma data válida.';
  }
  return null;
}

/// 'AAAA-MM-DD' → 'DD/MM/AAAA'. Qualquer outra coisa volta como veio.
String dataBr(String iso) {
  final partes = iso.split('-');
  if (partes.length != 3) return iso;
  return '${partes[2]}/${partes[1]}/${partes[0]}';
}

String _animais(int n) => n == 1 ? '1 animal' : '$n animais';

/// O estado do registro oficial no SDA, em uma linha. O AgroTop não registra nada no SDA:
/// "registrada" só aparece depois de uma pessoa confirmar, com a referência do atestado.
String rotuloRegistroSda(BruceloseVaccination v) {
  if (v.cancelada) return 'Cancelada';
  if (v.statusOficial == 'registrado_sda') {
    return 'Registrada no SDA · atestado ${v.referenciaAtestado ?? '—'}';
  }
  if (v.statusOficial == 'excecao') return 'Exceção justificada';
  final prazo = v.prazoSda == null ? '' : dataBr(v.prazoSda!);
  switch (v.situacaoPrazo) {
    case 'atrasado':
      return 'Atrasada: o prazo no SDA era $prazo';
    case 'vencendo':
      return 'Perto do prazo no SDA: até $prazo';
    case 'no_prazo':
      return 'Pendente no SDA: até $prazo';
    default:
      return 'Pendente no SDA (sem prazo exigido)';
  }
}

IconData _iconeDoEstado(BruceloseVaccination v) {
  if (v.cancelada) return Icons.cancel_outlined;
  if (v.statusOficial == 'registrado_sda') return Icons.check_circle_outline;
  if (v.statusOficial == 'excecao') return Icons.rule_outlined;
  if (v.situacaoPrazo == 'atrasado') return Icons.error_outline;
  return Icons.schedule_outlined;
}

String? _opcional(TextEditingController controller) {
  final texto = controller.text.trim();
  return texto.isEmpty ? null : texto;
}

/// Registra a vacinação contra brucelose das fêmeas selecionadas. Com internet, grava na hora;
/// sem ela, o pedido fica na fila com a mesma chave de idempotência, então um reenvio nunca
/// duplica o ato. Volta com `true` quando algo foi registrado ou enfileirado.
class BruceloseVaccinationPage extends StatefulWidget {
  const BruceloseVaccinationPage({
    super.key,
    required this.api,
    required this.animalIds,
    required this.onUnauthorized,
    this.excluidos = 0,
    this.initialDate,
    this.offlineQueue,
  });

  final ApiClient api;
  final List<String> animalIds;
  final VoidCallback onUnauthorized;

  /// Quantos animais da seleção ficaram de fora por não serem fêmeas.
  final int excluidos;
  final DateTime? initialDate;
  final OfflineQueue? offlineQueue;

  @override
  State<BruceloseVaccinationPage> createState() =>
      _BruceloseVaccinationPageState();
}

class _BruceloseVaccinationPageState extends State<BruceloseVaccinationPage> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _date;
  late final OfflineQueue _offlineQueue;
  final _produto = TextEditingController(text: 'B19');
  final _lote = TextEditingController();
  final _validade = TextEditingController();
  final _dose = TextEditingController(text: '2.0');
  final _vet = TextEditingController();
  final _crmv = TextEditingController();
  final _uf = TextEditingController(text: 'RS');
  final _notas = TextEditingController();
  bool _saving = false;
  String? _error;
  BruceloseRegistered? _result;

  @override
  void initState() {
    super.initState();
    _offlineQueue = widget.offlineQueue ?? OfflineQueue();
    _date = TextEditingController(
      text: _formatDate(widget.initialDate ?? DateTime.now()),
    );
  }

  @override
  void dispose() {
    for (final c in [
      _date,
      _produto,
      _lote,
      _validade,
      _dose,
      _vet,
      _crmv,
      _uf,
      _notas,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _pickDate() async {
    final current = DateTime.tryParse(_date.text) ?? DateTime.now();
    final selected = await showDatePicker(
      context: context,
      initialDate: current,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
    );
    if (selected != null) setState(() => _date.text = _formatDate(selected));
  }

  double? _doseValue() =>
      double.tryParse(_dose.text.trim().replaceAll(',', '.'));

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    // A mesma chave vai na tentativa online e, se ela falhar sem resposta, na fila: o servidor
    // reconhece o reenvio de uma tentativa que talvez tenha chegado.
    final chave = _uuid.v4();
    final data = _date.text.trim();
    final produto = _produto.text.trim();
    final vet = _vet.text.trim();
    final dose = _doseValue()!;
    final crmv = _opcional(_crmv);
    final uf = _opcional(_uf);
    final lote = _opcional(_lote);
    final validade = _opcional(_validade);
    final notas = _opcional(_notas);
    try {
      final result = await widget.api.registerBruceloseVaccination(
        animalIds: widget.animalIds,
        data: data,
        produto: produto,
        veterinarioNome: vet,
        veterinarioCrmv: crmv,
        veterinarioUf: uf,
        lote: lote,
        validade: validade,
        dose: dose,
        notas: notas,
        idempotencyKey: chave,
      );
      if (mounted) setState(() => _result = result);
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        Navigator.of(context).popUntil((route) => route.isFirst);
        widget.onUnauthorized();
      } else {
        setState(() => _error = error.message);
      }
    } catch (_) {
      await _offlineQueue.enqueueBruceloseVaccination(
        animalIds: widget.animalIds,
        data: data,
        produto: produto,
        veterinarioNome: vet,
        veterinarioCrmv: crmv,
        veterinarioUf: uf,
        lote: lote,
        validade: validade,
        dose: dose,
        notas: notas,
        clientUuid: chave,
      );
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(kOfflineEnfileirado)));
        Navigator.of(context).pop(true);
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final result = _result;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          result == null ? 'Vacinar contra brucelose' : 'Vacinação registrada',
        ),
      ),
      body: result == null
          ? _buildForm()
          : _BruceloseResultView(
              result: result,
              onDone: () => Navigator.of(context).pop(true),
            ),
    );
  }

  Widget _buildForm() => SafeArea(
    child: Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            widget.animalIds.length == 1
                ? 'Fêmea selecionada: ${widget.animalIds.single}'
                : '${widget.animalIds.length} fêmeas selecionadas',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (widget.excluidos > 0) ...[
            const SizedBox(height: 8),
            Text(
              widget.excluidos == 1
                  ? '1 animal da seleção ficou de fora: a vacinação é só de fêmeas.'
                  : '${widget.excluidos} animais da seleção ficaram de fora: a vacinação é só de fêmeas.',
              key: const ValueKey('brucelose-excluidos'),
            ),
          ],
          const SizedBox(height: 8),
          const Text(
            'O AgroTop guarda o ato e a ficha dos animais para o veterinário '
            'lançar no SDA. Ele não registra nada no SDA.',
          ),
          const SizedBox(height: 16),
          TextFormField(
            key: const ValueKey('brucelose-date'),
            controller: _date,
            decoration: InputDecoration(
              labelText: 'Data da vacinação',
              prefixIcon: const Icon(Icons.calendar_today_outlined),
              suffixIcon: IconButton(
                tooltip: 'Escolher data',
                onPressed: _pickDate,
                icon: const Icon(Icons.edit_calendar_outlined),
              ),
            ),
            validator: _validateDate,
          ),
          const SizedBox(height: 12),
          TextFormField(
            key: const ValueKey('brucelose-produto'),
            controller: _produto,
            decoration: const InputDecoration(
              labelText: 'Vacina',
              prefixIcon: Icon(Icons.medical_services_outlined),
              helperText: 'Ex.: B19 (3 a 8 meses) ou RB51.',
            ),
            validator: (value) => (value == null || value.trim().isEmpty)
                ? 'Informe a vacina.'
                : null,
          ),
          const SizedBox(height: 12),
          TextFormField(
            key: const ValueKey('brucelose-lote'),
            controller: _lote,
            decoration: const InputDecoration(
              labelText: 'Lote da vacina (opcional)',
              prefixIcon: Icon(Icons.qr_code_2_outlined),
            ),
          ),
          const SizedBox(height: 12),
          TextFormField(
            key: const ValueKey('brucelose-validade'),
            controller: _validade,
            decoration: const InputDecoration(
              labelText: 'Validade da vacina (opcional, AAAA-MM-DD)',
              prefixIcon: Icon(Icons.event_busy_outlined),
            ),
            validator: (value) => _validateDate(value, obrigatoria: false),
          ),
          const SizedBox(height: 12),
          TextFormField(
            key: const ValueKey('brucelose-dose'),
            controller: _dose,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Dose (ml)',
              prefixIcon: Icon(Icons.water_drop_outlined),
            ),
            validator: (value) {
              final dose = double.tryParse(
                (value ?? '').trim().replaceAll(',', '.'),
              );
              return dose == null || dose <= 0
                  ? 'A dose deve ser maior que zero.'
                  : null;
            },
          ),
          const SizedBox(height: 12),
          TextFormField(
            key: const ValueKey('brucelose-vet'),
            controller: _vet,
            decoration: const InputDecoration(
              labelText: 'Médico-veterinário',
              prefixIcon: Icon(Icons.badge_outlined),
            ),
            validator: (value) => (value == null || value.trim().isEmpty)
                ? 'Informe o médico-veterinário.'
                : null,
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                flex: 3,
                child: TextFormField(
                  key: const ValueKey('brucelose-crmv'),
                  controller: _crmv,
                  decoration: const InputDecoration(
                    labelText: 'CRMV (opcional)',
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 1,
                child: TextFormField(
                  key: const ValueKey('brucelose-uf'),
                  controller: _uf,
                  maxLength: 2,
                  textCapitalization: TextCapitalization.characters,
                  decoration: const InputDecoration(
                    labelText: 'UF',
                    counterText: '',
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          TextFormField(
            key: const ValueKey('brucelose-notas'),
            controller: _notas,
            maxLines: 2,
            decoration: const InputDecoration(
              labelText: 'Observações (opcional)',
              prefixIcon: Icon(Icons.notes_outlined),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 16),
            Semantics(
              liveRegion: true,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    Icons.error_outline,
                    color: Theme.of(context).colorScheme.error,
                  ),
                  const SizedBox(width: 8),
                  Expanded(child: Text(_error!)),
                ],
              ),
            ),
          ],
          const SizedBox(height: 24),
          FilledButton.icon(
            key: const ValueKey('confirm-brucelose'),
            onPressed: _saving ? null : _submit,
            icon: _saving
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.medical_services_outlined),
            label: Text(_saving ? 'Registrando…' : 'Registrar vacinação'),
          ),
        ],
      ),
    ),
  );
}

class _BruceloseResultView extends StatelessWidget {
  const _BruceloseResultView({required this.result, required this.onDone});

  final BruceloseRegistered result;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            color: colors.primaryContainer,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.check_circle_outline,
                        color: colors.onPrimaryContainer,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Vacinação registrada em ${_animais(result.n)}.',
                          key: const ValueKey('brucelose-result-title'),
                          style: Theme.of(context).textTheme.titleMedium
                              ?.copyWith(color: colors.onPrimaryContainer),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    result.prazoSda == null
                        ? 'O prazo no SDA só vale para vacinações a partir de 01/01/2027.'
                        : 'Lançamento no SDA até ${dataBr(result.prazoSda!)}.',
                    key: const ValueKey('brucelose-result-prazo'),
                    style: TextStyle(color: colors.onPrimaryContainer),
                  ),
                ],
              ),
            ),
          ),
          if (result.avisos.isNotEmpty) ...[
            const SizedBox(height: 12),
            Card(
              color: colors.tertiaryContainer,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  key: const ValueKey('brucelose-result-avisos'),
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Avisos',
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        color: colors.onTertiaryContainer,
                      ),
                    ),
                    for (final aviso in result.avisos)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(
                          '• $aviso',
                          style: TextStyle(color: colors.onTertiaryContainer),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
          const SizedBox(height: 24),
          FilledButton.icon(
            key: const ValueKey('finish-brucelose'),
            onPressed: onDone,
            icon: const Icon(Icons.done),
            label: const Text('Concluir'),
          ),
        ],
      ),
    );
  }
}

/// As vacinações contra brucelose e o estado do registro de cada uma no SDA.
class BrucelosePage extends StatefulWidget {
  const BrucelosePage({
    super.key,
    required this.api,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final VoidCallback onUnauthorized;

  @override
  State<BrucelosePage> createState() => _BrucelosePageState();
}

class _BrucelosePageState extends State<BrucelosePage> {
  late Future<List<BruceloseVaccination>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.api.listBruceloseVaccinations();
  }

  void _reload() {
    setState(() {
      _future = widget.api.listBruceloseVaccinations();
    });
  }

  Future<void> _open(BruceloseVaccination v) async {
    final mudou = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => BruceloseDetailPage(
          api: widget.api,
          vacinacaoId: v.id,
          onUnauthorized: widget.onUnauthorized,
        ),
      ),
    );
    if (mudou == true && mounted) _reload();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Brucelose (SDA)')),
    body: FutureBuilder<List<BruceloseVaccination>>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          final error = snapshot.error;
          if (error is ApiException && error.statusCode == 401) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              Navigator.of(context).popUntil((route) => route.isFirst);
              widget.onUnauthorized();
            });
          }
          return _MensagemDeErro(
            message: error is ApiException
                ? error.message
                : erroCarregamento('as vacinações'),
            onRetry: _reload,
          );
        }
        final lista = snapshot.data!;
        return RefreshIndicator(
          onRefresh: () async {
            _reload();
            await _future;
          },
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (lista.isEmpty)
                const Card(
                  key: ValueKey('brucelose-vazia'),
                  child: ListTile(
                    leading: Icon(Icons.info_outline),
                    title: Text('Nenhuma vacinação contra brucelose registrada.'),
                    subtitle: Text(
                      'Para registrar, selecione fêmeas na lista de animais e '
                      'toque em "Vacinar contra brucelose".',
                    ),
                  ),
                ),
              for (final v in lista)
                Card(
                  child: ListTile(
                    key: ValueKey('brucelose-${v.id}'),
                    leading: Icon(_iconeDoEstado(v)),
                    title: Text('${dataBr(v.data)} · ${v.propriedade}'),
                    subtitle: Text(
                      '${_animais(v.nAnimais)} · ${v.produto}\n'
                      '${rotuloRegistroSda(v)}',
                    ),
                    isThreeLine: true,
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _open(v),
                  ),
                ),
            ],
          ),
        );
      },
    ),
  );
}

/// Um ato com a ficha dos animais. Confirmar no SDA, registrar exceção e cancelar precisam de
/// internet: o servidor é quem decide se o estado ainda permite. Volta com `true` quando mudou.
class BruceloseDetailPage extends StatefulWidget {
  const BruceloseDetailPage({
    super.key,
    required this.api,
    required this.vacinacaoId,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final String vacinacaoId;
  final VoidCallback onUnauthorized;

  @override
  State<BruceloseDetailPage> createState() => _BruceloseDetailPageState();
}

class _BruceloseDetailPageState extends State<BruceloseDetailPage> {
  late final Future<BruceloseVaccination> _future;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _future = widget.api.getBruceloseVaccination(widget.vacinacaoId);
  }

  void _mensagem(String texto) => ScaffoldMessenger.of(
    context,
  ).showSnackBar(SnackBar(content: Text(texto)));

  Future<void> _agir(Future<void> Function() acao, String ok) async {
    setState(() => _busy = true);
    try {
      await acao();
      if (!mounted) return;
      _mensagem(ok);
      Navigator.of(context).pop(true);
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        Navigator.of(context).popUntil((route) => route.isFirst);
        widget.onUnauthorized();
      } else {
        _mensagem(error.message);
      }
    } catch (_) {
      if (mounted) _mensagem(kBruceloseSemConexao);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _confirmar() async {
    final referencia = await _pedirTexto(
      context,
      titulo: 'Registrada no SDA',
      rotulo: 'Referência do atestado emitido no SDA',
      vazio: 'Informe a referência do atestado.',
      confirmar: 'Confirmar',
      campoKey: const ValueKey('brucelose-referencia'),
      confirmarKey: const ValueKey('brucelose-confirmar-referencia'),
    );
    if (referencia == null) return;
    await _agir(
      () => widget.api.confirmBruceloseSda(
        widget.vacinacaoId,
        referencia: referencia,
        idempotencyKey: _uuid.v4(),
      ),
      'Registro no SDA confirmado.',
    );
  }

  Future<void> _excecao() async {
    final justificativa = await _pedirTexto(
      context,
      titulo: 'Registrar exceção',
      rotulo: 'Justificativa da exceção',
      vazio: 'Informe a justificativa.',
      confirmar: 'Registrar exceção',
      campoKey: const ValueKey('brucelose-justificativa'),
      confirmarKey: const ValueKey('brucelose-confirmar-excecao'),
    );
    if (justificativa == null) return;
    await _agir(
      () => widget.api.bruceloseSdaException(
        widget.vacinacaoId,
        justificativa: justificativa,
        idempotencyKey: _uuid.v4(),
      ),
      'Exceção registrada.',
    );
  }

  Future<void> _cancelar() async {
    final motivo = await _pedirTexto(
      context,
      titulo: 'Cancelar vacinação',
      rotulo: 'Motivo do cancelamento',
      vazio: 'Informe o motivo.',
      confirmar: 'Cancelar vacinação',
      campoKey: const ValueKey('brucelose-motivo'),
      confirmarKey: const ValueKey('brucelose-confirmar-cancelamento'),
    );
    if (motivo == null) return;
    await _agir(
      () => widget.api.cancelBruceloseVaccination(
        widget.vacinacaoId,
        motivo: motivo,
        idempotencyKey: _uuid.v4(),
      ),
      'Vacinação cancelada.',
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Vacinação contra brucelose')),
    body: FutureBuilder<BruceloseVaccination>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          final error = snapshot.error;
          if (error is ApiException && error.statusCode == 401) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              Navigator.of(context).popUntil((route) => route.isFirst);
              widget.onUnauthorized();
            });
          }
          return _MensagemDeErro(
            message: error is ApiException
                ? error.message
                : erroCarregamento('a vacinação'),
          );
        }
        return _buildDetalhe(snapshot.data!);
      },
    ),
  );

  Widget _buildDetalhe(BruceloseVaccination v) {
    final vet = [
      v.veterinarioNome,
      if (v.veterinarioCrmv != null)
        'CRMV ${v.veterinarioCrmv}${v.veterinarioUf == null ? '' : '/${v.veterinarioUf}'}',
    ].join(' · ');
    final produto = [
      v.produto,
      if (v.lote != null) 'lote ${v.lote}',
      if (v.validade != null) 'val. ${dataBr(v.validade!)}',
      'dose ${v.dose} ${v.unidade}',
    ].join(' · ');
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: Icon(_iconeDoEstado(v)),
              title: Text(
                rotuloRegistroSda(v),
                key: const ValueKey('brucelose-estado'),
              ),
              subtitle: Text(
                '${dataBr(v.data)} · ${v.propriedade}\n$produto\nVet.: $vet',
              ),
              isThreeLine: true,
            ),
          ),
          if (v.cancelada && v.motivoCancelamento != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text('Motivo do cancelamento: ${v.motivoCancelamento}'),
            ),
          if (v.statusOficial == 'excecao' && v.justificativaExcecao != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text('Justificativa: ${v.justificativaExcecao}'),
            ),
          const SizedBox(height: 16),
          Text(
            'Animais (${v.animais.length})',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          for (final a in v.animais)
            ListTile(
              key: ValueKey('brucelose-animal-${a.brinco}'),
              dense: true,
              title: Text(a.brinco),
              subtitle: Text(
                'Identificador oficial: ${a.identificadorOficial ?? '—'} · '
                'Registro genealógico: ${a.registroGenealogico ?? '—'}',
              ),
            ),
          if (v.pendente) ...[
            const SizedBox(height: 24),
            FilledButton.icon(
              key: const ValueKey('brucelose-confirm'),
              onPressed: _busy ? null : _confirmar,
              icon: const Icon(Icons.verified_outlined),
              label: const Text('Confirmar: registrada no SDA'),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              key: const ValueKey('brucelose-excecao'),
              onPressed: _busy ? null : _excecao,
              icon: const Icon(Icons.rule_outlined),
              label: const Text('Registrar exceção'),
            ),
            const SizedBox(height: 12),
            TextButton.icon(
              key: const ValueKey('brucelose-cancel'),
              onPressed: _busy ? null : _cancelar,
              icon: const Icon(Icons.delete_outline),
              label: const Text('Cancelar vacinação'),
            ),
          ],
        ],
      ),
    );
  }
}

Future<String?> _pedirTexto(
  BuildContext context, {
  required String titulo,
  required String rotulo,
  required String vazio,
  required String confirmar,
  required Key campoKey,
  required Key confirmarKey,
}) => showDialog<String>(
  context: context,
  builder: (_) => _TextoDialog(
    titulo: titulo,
    rotulo: rotulo,
    vazio: vazio,
    confirmar: confirmar,
    campoKey: campoKey,
    confirmarKey: confirmarKey,
  ),
);

class _TextoDialog extends StatefulWidget {
  const _TextoDialog({
    required this.titulo,
    required this.rotulo,
    required this.vazio,
    required this.confirmar,
    required this.campoKey,
    required this.confirmarKey,
  });

  final String titulo;
  final String rotulo;
  final String vazio;
  final String confirmar;
  final Key campoKey;
  final Key confirmarKey;

  @override
  State<_TextoDialog> createState() => _TextoDialogState();
}

class _TextoDialogState extends State<_TextoDialog> {
  final _controller = TextEditingController();
  String? _erro;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _enviar() {
    final texto = _controller.text.trim();
    if (texto.isEmpty) {
      setState(() => _erro = widget.vazio);
      return;
    }
    Navigator.of(context).pop(texto);
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.titulo),
    content: TextField(
      key: widget.campoKey,
      controller: _controller,
      autofocus: true,
      decoration: InputDecoration(
        labelText: widget.rotulo,
        errorText: _erro,
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.of(context).pop(),
        child: const Text('Voltar'),
      ),
      FilledButton(
        key: widget.confirmarKey,
        onPressed: _enviar,
        child: Text(widget.confirmar),
      ),
    ],
  );
}

class _MensagemDeErro extends StatelessWidget {
  const _MensagemDeErro({required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.cloud_off,
            size: 48,
            color: Theme.of(context).colorScheme.error,
          ),
          const SizedBox(height: 12),
          Text(message, textAlign: TextAlign.center),
          if (onRetry != null) ...[
            const SizedBox(height: 12),
            OutlinedButton(
              key: const ValueKey('brucelose-retry'),
              onPressed: onRetry,
              child: const Text('Tentar de novo'),
            ),
          ],
        ],
      ),
    ),
  );
}
