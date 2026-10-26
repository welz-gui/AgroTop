import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../api_client.dart';
import '../copy.dart';
import '../models.dart';

String _formatDate(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-'
    '${value.month.toString().padLeft(2, '0')}-'
    '${value.day.toString().padLeft(2, '0')}';

String? _validateDate(String? value) {
  if (value == null || !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value)) {
    return 'Use o formato AAAA-MM-DD.';
  }
  final parsed = DateTime.tryParse(value);
  if (parsed == null || _formatDate(parsed) != value) {
    return 'Informe uma data válida.';
  }
  return null;
}

const _metodos = {
  'pesado': 'Pesado na balança',
  'estimado': 'Estimado pelo operador',
  'medicao': 'Estimado por medição (fita/fórmula)',
};

/// Rodapé comum das telas de revisão: erro, "salvar correção" e "cancelar".
class _RevisionFooter extends StatelessWidget {
  const _RevisionFooter({
    required this.error,
    required this.saving,
    required this.cancelLabel,
    required this.onSave,
    required this.onCancel,
  });

  final String? error;
  final bool saving;
  final String cancelLabel;
  final VoidCallback onSave;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      if (error != null) ...[
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
              Expanded(child: Text(error!)),
            ],
          ),
        ),
      ],
      const SizedBox(height: 24),
      FilledButton.icon(
        key: const ValueKey('save-revision'),
        onPressed: saving ? null : onSave,
        icon: saving
            ? const SizedBox.square(
                dimension: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Icon(Icons.save_outlined),
        label: Text(saving ? 'Salvando…' : 'Salvar correção'),
      ),
      const SizedBox(height: 12),
      OutlinedButton.icon(
        key: const ValueKey('cancel-revision'),
        onPressed: saving ? null : onCancel,
        icon: const Icon(Icons.delete_outline),
        label: Text(cancelLabel),
      ),
    ],
  );
}

Future<bool> _confirmarCancelamento(
  BuildContext context, {
  required String titulo,
  required String texto,
}) async {
  final confirmou = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(titulo),
      content: Text(texto),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Voltar'),
        ),
        FilledButton(
          key: const ValueKey('confirm-cancel-revision'),
          onPressed: () => Navigator.of(context).pop(true),
          child: const Text('Cancelar registro'),
        ),
      ],
    ),
  );
  return confirmou == true;
}

TextFormField _campoMotivo(TextEditingController controller) => TextFormField(
  key: const ValueKey('revision-reason'),
  controller: controller,
  maxLines: 2,
  decoration: const InputDecoration(
    labelText: 'Motivo da correção',
    prefixIcon: Icon(Icons.rule_outlined),
    helperText:
        'Fica gravado com o seu nome. O registro original continua no histórico.',
  ),
  validator: (value) => value == null || value.trim().isEmpty
      ? 'Informe o motivo da correção.'
      : null,
);

/// Corrige ou cancela uma pesagem. Precisa de internet: a pesagem pode já ter sido cancelada
/// por outra pessoa, e o servidor é quem decide. Volta com `true` quando algo mudou.
class WeighingRevisionPage extends StatefulWidget {
  const WeighingRevisionPage({
    super.key,
    required this.api,
    required this.animalId,
    required this.registro,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final String animalId;
  final WeighingRecord registro;
  final VoidCallback onUnauthorized;

  @override
  State<WeighingRevisionPage> createState() => _WeighingRevisionPageState();
}

class _WeighingRevisionPageState extends State<WeighingRevisionPage> {
  final _formKey = GlobalKey<FormState>();
  final _uuid = const Uuid();
  late final TextEditingController _peso;
  late final TextEditingController _date;
  final _motivo = TextEditingController();
  late String _method;
  late String _chaveCorrecao = _uuid.v4();
  late String _chaveCancelamento = _uuid.v4();
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _peso = TextEditingController(text: widget.registro.peso.toString());
    _date = TextEditingController(text: widget.registro.data);
    _method = _metodos.containsKey(widget.registro.method)
        ? widget.registro.method
        : 'pesado';
  }

  @override
  void dispose() {
    _peso.dispose();
    _date.dispose();
    _motivo.dispose();
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

  Future<void> _executar(Future<void> Function() chamada, VoidCallback novaChave) async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await chamada();
      if (mounted) Navigator.of(context).pop<bool>(true);
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        Navigator.of(context).popUntil((route) => route.isFirst);
        widget.onUnauthorized();
      } else {
        novaChave();
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) setState(() => _error = kCorrecaoSemConexao);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _salvar() async {
    if (!_formKey.currentState!.validate()) return;
    await _executar(
      () => widget.api.correctWeighing(
        widget.animalId,
        widget.registro.id,
        peso: double.parse(_peso.text.replaceFirst(',', '.')),
        data: _date.text.trim(),
        method: _method,
        notes: widget.registro.notes ?? '',
        motivo: _motivo.text.trim(),
        idempotencyKey: _chaveCorrecao,
      ),
      () => _chaveCorrecao = _uuid.v4(),
    );
  }

  Future<void> _cancelar() async {
    if (_motivo.text.trim().isEmpty) {
      setState(() => _error = 'Informe o motivo para cancelar a pesagem.');
      return;
    }
    final ok = await _confirmarCancelamento(
      context,
      titulo: 'Cancelar esta pesagem?',
      texto:
          'A pesagem de ${widget.registro.peso} kg de ${widget.registro.data} deixa de valer e o '
          'peso atual do animal volta ao da pesagem anterior. O registro continua no histórico.',
    );
    if (!ok || !mounted) return;
    await _executar(
      () => widget.api.cancelWeighing(
        widget.animalId,
        widget.registro.id,
        motivo: _motivo.text.trim(),
        idempotencyKey: _chaveCancelamento,
      ),
      () => _chaveCancelamento = _uuid.v4(),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text('Corrigir pesagem ${widget.animalId}')),
    body: SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _campoMotivo(_motivo),
                      const SizedBox(height: 16),
                      TextFormField(
                        key: const ValueKey('revision-weight'),
                        controller: _peso,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Peso (kg)',
                          prefixIcon: Icon(Icons.monitor_weight_outlined),
                        ),
                        validator: (value) {
                          final parsed = double.tryParse(
                            (value ?? '').replaceFirst(',', '.'),
                          );
                          return parsed == null || parsed <= 0
                              ? 'Informe um peso maior que zero.'
                              : null;
                        },
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        key: const ValueKey('revision-date'),
                        controller: _date,
                        decoration: InputDecoration(
                          labelText: 'Data',
                          prefixIcon: const Icon(Icons.calendar_today_outlined),
                          suffixIcon: IconButton(
                            tooltip: 'Escolher data',
                            onPressed: _pickDate,
                            icon: const Icon(Icons.edit_calendar_outlined),
                          ),
                        ),
                        validator: _validateDate,
                      ),
                      const SizedBox(height: 16),
                      DropdownButtonFormField<String>(
                        key: const ValueKey('revision-method'),
                        initialValue: _method,
                        decoration: const InputDecoration(
                          labelText: 'Método',
                          prefixIcon: Icon(Icons.scale_outlined),
                        ),
                        isExpanded: true,
                        items: [
                          for (final e in _metodos.entries)
                            DropdownMenuItem(value: e.key, child: Text(e.value)),
                        ],
                        onChanged: (value) => _method = value!,
                      ),
                    ],
                  ),
                ),
              ),
              _RevisionFooter(
                error: _error,
                saving: _saving,
                cancelLabel: 'Cancelar esta pesagem',
                onSave: _salvar,
                onCancel: _cancelar,
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

/// Corrige ou cancela a última movimentação do animal. Precisa de internet (mesma razão da
/// pesagem). Volta com `true` quando algo mudou.
class MovementRevisionPage extends StatefulWidget {
  const MovementRevisionPage({
    super.key,
    required this.api,
    required this.animalId,
    required this.registro,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final String animalId;
  final MovementRecord registro;
  final VoidCallback onUnauthorized;

  @override
  State<MovementRevisionPage> createState() => _MovementRevisionPageState();
}

class _MovementRevisionPageState extends State<MovementRevisionPage> {
  final _formKey = GlobalKey<FormState>();
  final _uuid = const Uuid();
  late final Future<List<LoteSummary>> _lotes = widget.api.listLotes();
  late final TextEditingController _date;
  final _motivo = TextEditingController();
  late String _destino = widget.registro.para;
  late String _chaveCorrecao = _uuid.v4();
  late String _chaveCancelamento = _uuid.v4();
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _date = TextEditingController(text: widget.registro.data);
  }

  @override
  void dispose() {
    _date.dispose();
    _motivo.dispose();
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

  Future<void> _executar(Future<void> Function() chamada, VoidCallback novaChave) async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await chamada();
      if (mounted) Navigator.of(context).pop<bool>(true);
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        Navigator.of(context).popUntil((route) => route.isFirst);
        widget.onUnauthorized();
      } else {
        novaChave();
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) setState(() => _error = kCorrecaoSemConexao);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _salvar() async {
    if (!_formKey.currentState!.validate()) return;
    await _executar(
      () => widget.api.correctMovement(
        widget.animalId,
        widget.registro.id,
        toLoteId: _destino,
        movementDate: _date.text.trim(),
        reason: widget.registro.motivo ?? 'manejo',
        motivo: _motivo.text.trim(),
        idempotencyKey: _chaveCorrecao,
      ),
      () => _chaveCorrecao = _uuid.v4(),
    );
  }

  Future<void> _cancelar() async {
    if (_motivo.text.trim().isEmpty) {
      setState(() => _error = 'Informe o motivo para cancelar a movimentação.');
      return;
    }
    final origem = widget.registro.de ?? 'origem';
    final ok = await _confirmarCancelamento(
      context,
      titulo: 'Cancelar esta movimentação?',
      texto:
          'O animal volta para $origem. O registro continua no histórico, com o motivo.',
    );
    if (!ok || !mounted) return;
    await _executar(
      () => widget.api.cancelMovement(
        widget.animalId,
        widget.registro.id,
        motivo: _motivo.text.trim(),
        idempotencyKey: _chaveCancelamento,
      ),
      () => _chaveCancelamento = _uuid.v4(),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text('Corrigir movimentação ${widget.animalId}')),
    body: SafeArea(
      child: FutureBuilder<List<LoteSummary>>(
        future: _lotes,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            final error = snapshot.error;
            return Padding(
              padding: const EdgeInsets.all(16),
              child: Text(
                error is ApiException
                    ? error.message
                    : erroCarregamento('piquetes'),
              ),
            );
          }
          // O destino correto nunca é o piquete de origem: isso seria cancelar.
          final opcoes = snapshot.data!
              .where((l) => l.id != widget.registro.de)
              .toList(growable: false);
          if (!opcoes.any((l) => l.id == _destino)) {
            _destino = opcoes.isEmpty ? _destino : opcoes.first.id;
          }
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            'Registrada: ${widget.registro.de ?? '—'} → ${widget.registro.para} em ${widget.registro.data}',
                          ),
                          const SizedBox(height: 16),
                          _campoMotivo(_motivo),
                          const SizedBox(height: 16),
                          DropdownButtonFormField<String>(
                            key: const ValueKey('revision-destination'),
                            initialValue: _destino,
                            decoration: const InputDecoration(
                              labelText: 'Destino correto',
                              prefixIcon: Icon(Icons.swap_horiz),
                            ),
                            isExpanded: true,
                            items: [
                              for (final l in opcoes)
                                DropdownMenuItem(
                                  value: l.id,
                                  child: Text('${l.id} — ${l.nome}'),
                                ),
                            ],
                            onChanged: (value) => _destino = value!,
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            key: const ValueKey('revision-date'),
                            controller: _date,
                            decoration: InputDecoration(
                              labelText: 'Data da movimentação',
                              prefixIcon: const Icon(
                                Icons.calendar_today_outlined,
                              ),
                              suffixIcon: IconButton(
                                tooltip: 'Escolher data',
                                onPressed: _pickDate,
                                icon: const Icon(Icons.edit_calendar_outlined),
                              ),
                            ),
                            validator: _validateDate,
                          ),
                        ],
                      ),
                    ),
                  ),
                  _RevisionFooter(
                    error: _error,
                    saving: _saving,
                    cancelLabel:
                        'Cancelar e devolver a ${widget.registro.de ?? 'origem'}',
                    onSave: _salvar,
                    onCancel: _cancelar,
                  ),
                ],
              ),
            ),
          );
        },
      ),
    ),
  );
}
