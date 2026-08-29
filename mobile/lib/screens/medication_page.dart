import 'package:flutter/material.dart';

import '../api_client.dart';
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
  });

  final ApiClient api;
  final String animalId;
  final VoidCallback onUnauthorized;
  final DateTime? initialDate;
  final OfflineQueue? offlineQueue;

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
  late final TextEditingController _date;
  late final OfflineQueue _offlineQueue;

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
    _loadProtocolos();
  }

  @override
  void dispose() {
    _medicamento.dispose();
    _dose.dispose();
    _unidade.dispose();
    _via.dispose();
    _carenciaDias.dispose();
    _notes.dispose();
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
    final protoVal = _selectedProtocolo?.id;
    final notasVal = _notes.text.trim().isEmpty ? null : _notes.text.trim();
    try {
      final carenciaAte = await widget.api.registerMedication(
        widget.animalId,
        medicamento: medVal,
        dose: doseVal,
        unidade: unidadeVal,
        via: viaVal,
        carenciaDias: carenciaVal,
        data: dataVal,
        protocoloId: protoVal,
        notas: notasVal,
      );
      if (mounted) Navigator.of(context).pop<String?>(carenciaAte ?? '');
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        Navigator.of(context).popUntil((route) => route.isFirst);
        widget.onUnauthorized();
      } else {
        setState(() => _error = error.message);
      }
    } catch (_) {
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
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Salvo. Será enviado quando houver conexão.'),
          ),
        );
        Navigator.of(context).pop<String?>('');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text('Sanidade ${widget.animalId}')),
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
                label: Text(_saving ? 'Salvando…' : 'Salvar aplicação'),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
