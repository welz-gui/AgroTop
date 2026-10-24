import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../api_client.dart';
import '../copy.dart';
import '../models.dart';
import '../offline_queue.dart';

class MedicationPage extends StatefulWidget {
  const MedicationPage({
    super.key,
    required this.api,
    required this.animalId,
    required this.onUnauthorized,
    this.initialDate,
    this.offlineQueue,
    this.corrigir,
  });

  final ApiClient api;
  final String animalId;
  final VoidCallback onUnauthorized;
  final DateTime? initialDate;
  final OfflineQueue? offlineQueue;

  /// Aplicação a corrigir ou cancelar (precisa ter `id`). Com ela, a tela abre
  /// preenchida, pede o motivo e envia direto ao servidor: correção não entra na fila
  /// offline, porque precisa da resposta dele (a aplicação pode já ter sido cancelada).
  final MedicationApplication? corrigir;

  @override
  State<MedicationPage> createState() => _MedicationPageState();
}

class _MedicationPageState extends State<MedicationPage> {
  final _formKey = GlobalKey<FormState>();
  final _medicamento = TextEditingController();
  final _dose = TextEditingController();
  final _unidade = TextEditingController(text: 'ml');
  final _via = TextEditingController(text: 'Subcutânea');
  final _carenciaDias = TextEditingController(text: '0');
  final _notes = TextEditingController();
  final _principioAtivo = TextEditingController();
  final _lote = TextEditingController();
  final _validade = TextEditingController();
  final _motivo = TextEditingController();
  late final TextEditingController _date;
  late final OfflineQueue _offlineQueue;
  final _uuid = const Uuid();
  // Uma chave por tentativa: repetir o mesmo pedido (rede que caiu na resposta) devolve a
  // resposta guardada; se o servidor respondeu com recusa, o pedido muda e a chave também.
  late String _chaveCorrecao = _uuid.v4();
  late String _chaveCancelamento = _uuid.v4();

  List<ProtocoloSummary>? _protocolos;
  ProtocoloSummary? _selectedProtocolo;
  bool _loadingProtocolos = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _offlineQueue = widget.offlineQueue ?? OfflineQueue();
    _date = TextEditingController(
      text: _formatDate(widget.initialDate ?? DateTime.now()),
    );
    final original = widget.corrigir;
    if (original != null) {
      _medicamento.text = original.medicamento;
      _dose.text = original.dose.toString();
      _unidade.text = original.unidade;
      _via.text = original.via;
      _carenciaDias.text = original.carenciaDias.toString();
      _date.text = original.data;
      _principioAtivo.text = original.principioAtivo ?? '';
      _lote.text = original.lote ?? '';
      _validade.text = original.validade ?? '';
      _loadingProtocolos = false;
    } else {
      _loadProtocolos();
    }
  }

  @override
  void dispose() {
    _medicamento.dispose();
    _dose.dispose();
    _unidade.dispose();
    _via.dispose();
    _carenciaDias.dispose();
    _notes.dispose();
    _principioAtivo.dispose();
    _lote.dispose();
    _validade.dispose();
    _motivo.dispose();
    _date.dispose();
    super.dispose();
  }

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

  // Mesmos limites do servidor (services/tratamento.py).
  String? _validateMaximo(String? value, int limite) =>
      (value ?? '').trim().length > limite
      ? 'Máximo de $limite caracteres.'
      : null;

  /// Opcional. Preenchida, precisa ser uma data válida e cobrir a data da
  /// aplicação: produto vencido não se aplica (o servidor também recusa, mas
  /// quem está offline só descobriria na sincronização).
  String? _validateValidade(String? value) {
    final validade = (value ?? '').trim();
    if (validade.isEmpty) return null;
    final erro = _validateDate(validade);
    if (erro != null) return erro;
    final aplicacao = _date.text.trim();
    if (_validateDate(aplicacao) == null && validade.compareTo(aplicacao) < 0) {
      return 'Produto vencido em $validade: não pode ser aplicado em $aplicacao.';
    }
    return null;
  }

  Future<void> _pickValidade() async {
    final current = DateTime.tryParse(_validade.text) ?? DateTime.now();
    final selected = await showDatePicker(
      context: context,
      initialDate: current,
      firstDate: DateTime(2000),
      lastDate: DateTime.now().add(const Duration(days: 3650)),
    );
    if (selected != null) {
      setState(() => _validade.text = _formatDate(selected));
    }
  }

  Future<void> _pickDate() async {
    final current = DateTime.tryParse(_date.text) ?? DateTime.now();
    final selected = await showDatePicker(
      context: context,
      initialDate: current,
      firstDate: DateTime(2000),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (selected != null) setState(() => _date.text = _formatDate(selected));
  }

  Future<void> _loadProtocolos() async {
    try {
      final list = await widget.api.listProtocolos(animalId: widget.animalId);
      if (!mounted) return;
      setState(() {
        _protocolos = list;
        _loadingProtocolos = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        Navigator.of(context).popUntil((route) => route.isFirst);
        widget.onUnauthorized();
      } else {
        setState(() => _loadingProtocolos = false);
      }
    } catch (_) {
      if (mounted) setState(() => _loadingProtocolos = false);
    }
  }

  void _onProtocoloSelected(ProtocoloSummary? protocolo) {
    setState(() {
      _selectedProtocolo = protocolo;
      if (protocolo != null) {
        _medicamento.text = protocolo.nome;
        _via.text = protocolo.via;
        _carenciaDias.text = protocolo.carenciaDias.toString();
        _unidade.text = protocolo.unidadeDose;
        if (protocolo.doseSugerida != null) {
          _dose.text = protocolo.doseSugerida.toString();
        } else {
          _dose.text = '';
        }
      }
    });
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    final medVal = _medicamento.text.trim();
    final doseVal = double.parse(_dose.text.replaceFirst(',', '.'));
    final unidadeVal = _unidade.text.trim();
    final viaVal = _via.text.trim();
    final carenciaVal = int.parse(_carenciaDias.text.trim());
    final dataVal = _date.text.trim();
    final protoVal = widget.corrigir?.protocoloId ?? _selectedProtocolo?.id;
    final notasVal = _notes.text.trim().isEmpty ? null : _notes.text.trim();
    final principioVal = _principioAtivo.text.trim().isEmpty
        ? null
        : _principioAtivo.text.trim();
    final loteVal = _lote.text.trim().isEmpty ? null : _lote.text.trim();
    final validadeVal = _validade.text.trim().isEmpty
        ? null
        : _validade.text.trim();
    try {
      final original = widget.corrigir;
      final carenciaAte = original == null
          ? await widget.api.registerMedication(
              widget.animalId,
              medicamento: medVal,
              dose: doseVal,
              unidade: unidadeVal,
              via: viaVal,
              carenciaDias: carenciaVal,
              data: dataVal,
              protocoloId: protoVal,
              notas: notasVal,
              principioAtivo: principioVal,
              lote: loteVal,
              validade: validadeVal,
            )
          : await widget.api.correctMedication(
              widget.animalId,
              original.id!,
              medicamento: medVal,
              dose: doseVal,
              unidade: unidadeVal,
              via: viaVal,
              carenciaDias: carenciaVal,
              data: dataVal,
              motivo: _motivo.text.trim(),
              protocoloId: protoVal,
              notas: notasVal,
              idempotencyKey: _chaveCorrecao,
              principioAtivo: principioVal,
              lote: loteVal,
              validade: validadeVal,
            );
      if (mounted) Navigator.of(context).pop<String?>(carenciaAte ?? '');
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        Navigator.of(context).popUntil((route) => route.isFirst);
        widget.onUnauthorized();
      } else {
        _chaveCorrecao = _uuid.v4();
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (widget.corrigir != null) {
        if (mounted) setState(() => _error = kCorrecaoSemConexao);
        return;
      }
      await _offlineQueue.enqueueMedication(
        animalId: widget.animalId,
        medicamento: medVal,
        dose: doseVal,
        unidade: unidadeVal,
        via: viaVal,
        carenciaDias: carenciaVal,
        data: dataVal,
        protocoloId: protoVal,
        notas: notasVal,
        principioAtivo: principioVal,
        lote: loteVal,
        validade: validadeVal,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(kOfflineEnfileirado)),
        );
        Navigator.of(context).pop<String?>('');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _cancelar() async {
    final original = widget.corrigir!;
    if (_motivo.text.trim().isEmpty) {
      setState(() => _error = 'Informe o motivo para cancelar a aplicação.');
      return;
    }
    final confirmou = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancelar esta aplicação?'),
        content: Text(
          '${original.medicamento} de ${original.data} deixa de valer. '
          'O registro continua no histórico, com o motivo.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Voltar'),
          ),
          FilledButton(
            key: const ValueKey('confirm-cancel-medication'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Cancelar aplicação'),
          ),
        ],
      ),
    );
    if (confirmou != true || !mounted) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final carenciaAte = await widget.api.cancelMedication(
        widget.animalId,
        original.id!,
        motivo: _motivo.text.trim(),
        idempotencyKey: _chaveCancelamento,
      );
      if (mounted) Navigator.of(context).pop<String?>(carenciaAte ?? '');
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        Navigator.of(context).popUntil((route) => route.isFirst);
        widget.onUnauthorized();
      } else {
        _chaveCancelamento = _uuid.v4();
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) setState(() => _error = kCorrecaoSemConexao);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.corrigir == null
            ? 'Sanidade ${widget.animalId}'
            : 'Corrigir aplicação ${widget.animalId}',
      ),
    ),
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
                      if (widget.corrigir != null) ...[
                        TextFormField(
                          key: const ValueKey('correction-reason'),
                          controller: _motivo,
                          maxLines: 2,
                          decoration: const InputDecoration(
                            labelText: 'Motivo da correção',
                            prefixIcon: Icon(Icons.rule_outlined),
                            helperText:
                                'Fica gravado com o seu nome. O registro original continua no histórico.',
                          ),
                          validator: (value) =>
                              value == null || value.trim().isEmpty
                              ? 'Informe o motivo da correção.'
                              : null,
                        ),
                        const SizedBox(height: 16),
                      ],
                      if (_loadingProtocolos)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 12),
                          child: Center(
                            child: SizedBox.square(
                              dimension: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                          ),
                        )
                      else if (_protocolos != null && _protocolos!.isNotEmpty)
                        DropdownButtonFormField<ProtocoloSummary>(
                          key: const ValueKey('protocol-dropdown'),
                          initialValue: _selectedProtocolo,
                          decoration: const InputDecoration(
                            labelText: 'Protocolo sanitário',
                            prefixIcon: Icon(Icons.list_alt_outlined),
                            helperText: 'Preenche os campos automaticamente',
                          ),
                          isExpanded: true,
                          items: [
                            const DropdownMenuItem<ProtocoloSummary>(
                              value: null,
                              child: Text('Preenchimento manual'),
                            ),
                            ..._protocolos!.map(
                              (p) => DropdownMenuItem<ProtocoloSummary>(
                                value: p,
                                child: Text(
                                  p.doseSugerida != null
                                      ? '${p.nome} (${p.doseSugerida} ${p.unidadeDose})'
                                      : p.nome,
                                ),
                              ),
                            ),
                          ],
                          onChanged: _onProtocoloSelected,
                        ),
                      const SizedBox(height: 16),
                      TextFormField(
                        key: const ValueKey('medication-name'),
                        controller: _medicamento,
                        decoration: const InputDecoration(
                          labelText: 'Medicamento / Vacina',
                          prefixIcon: Icon(Icons.medication_outlined),
                        ),
                        validator: (value) =>
                            value == null || value.trim().isEmpty
                            ? 'Informe o medicamento.'
                            : null,
                      ),
                      const SizedBox(height: 16),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            flex: 3,
                            child: TextFormField(
                              key: const ValueKey('medication-dose'),
                              controller: _dose,
                              keyboardType:
                                  const TextInputType.numberWithOptions(
                                    decimal: true,
                                  ),
                              decoration: const InputDecoration(
                                labelText: 'Dose',
                                prefixIcon: Icon(Icons.science_outlined),
                              ),
                              validator: (value) {
                                final parsed = double.tryParse(
                                  (value ?? '').replaceFirst(',', '.'),
                                );
                                return parsed == null || parsed <= 0
                                    ? 'Dose maior que zero.'
                                    : null;
                              },
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            flex: 2,
                            child: TextFormField(
                              key: const ValueKey('medication-unit'),
                              controller: _unidade,
                              decoration: const InputDecoration(
                                labelText: 'Unidade',
                              ),
                              validator: (value) =>
                                  value == null || value.trim().isEmpty
                                  ? 'Unidade obrigatória.'
                                  : null,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        key: const ValueKey('medication-route'),
                        controller: _via,
                        decoration: const InputDecoration(
                          labelText: 'Via de aplicação',
                          prefixIcon: Icon(Icons.vaccines_outlined),
                        ),
                        validator: (value) =>
                            value == null || value.trim().isEmpty
                            ? 'Informe a via de aplicação.'
                            : null,
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        key: const ValueKey('medication-withdrawal-days'),
                        controller: _carenciaDias,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Carência (dias)',
                          prefixIcon: Icon(Icons.timer_outlined),
                          helperText: '0 = sem período de carência',
                        ),
                        validator: (value) {
                          final parsed = int.tryParse(value ?? '');
                          return parsed == null || parsed < 0
                              ? 'Informe dias válidos (>= 0).'
                              : null;
                        },
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        key: const ValueKey('medication-date'),
                        controller: _date,
                        decoration: InputDecoration(
                          labelText: 'Data da aplicação',
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
                      TextFormField(
                        key: const ValueKey('medication-active-ingredient'),
                        controller: _principioAtivo,
                        decoration: const InputDecoration(
                          labelText: 'Princípio ativo (opcional)',
                          prefixIcon: Icon(Icons.biotech_outlined),
                          helperText: 'O que foi aplicado, ex.: ivermectina',
                        ),
                        validator: (value) => _validateMaximo(value, 120),
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        key: const ValueKey('medication-batch'),
                        controller: _lote,
                        decoration: const InputDecoration(
                          labelText: 'Lote do produto (opcional)',
                          prefixIcon: Icon(Icons.inventory_2_outlined),
                        ),
                        validator: (value) => _validateMaximo(value, 60),
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        key: const ValueKey('medication-expiry'),
                        controller: _validade,
                        decoration: InputDecoration(
                          labelText: 'Validade do produto (opcional)',
                          prefixIcon: const Icon(Icons.event_busy_outlined),
                          helperText:
                              'AAAA-MM-DD. Produto vencido não pode ser aplicado.',
                          suffixIcon: IconButton(
                            tooltip: 'Escolher validade',
                            onPressed: _pickValidade,
                            icon: const Icon(Icons.edit_calendar_outlined),
                          ),
                        ),
                        validator: _validateValidade,
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        key: const ValueKey('medication-notes'),
                        controller: _notes,
                        maxLines: 2,
                        decoration: const InputDecoration(
                          labelText: 'Observações (opcional)',
                          prefixIcon: Icon(Icons.notes_outlined),
                        ),
                      ),
                    ],
                  ),
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
                key: const ValueKey('save-medication'),
                onPressed: _saving ? null : _submit,
                icon: _saving
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.save_outlined),
                label: Text(
                  _saving
                      ? 'Salvando…'
                      : widget.corrigir == null
                      ? 'Salvar aplicação'
                      : 'Salvar correção',
                ),
              ),
              if (widget.corrigir != null) ...[
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  key: const ValueKey('cancel-medication'),
                  onPressed: _saving ? null : _cancelar,
                  icon: const Icon(Icons.delete_outline),
                  label: const Text('Cancelar esta aplicação'),
                ),
              ],
            ],
          ),
        ),
      ),
    ),
  );
}
