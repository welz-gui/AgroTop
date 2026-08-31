import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models.dart';
import '../offline_queue.dart';

class WeighingPage extends StatefulWidget {
  const WeighingPage({
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
  State<WeighingPage> createState() => _WeighingPageState();
}

class _WeighingPageState extends State<WeighingPage> {
  final _formKey = GlobalKey<FormState>();
  final _weight = TextEditingController();
  String _method = 'pesado';
  late final TextEditingController _date;
  late final OfflineQueue _offlineQueue;
  bool _saving = false;
  String? _error;

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
    _weight.dispose();
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
      lastDate: DateTime.now(),
    );
    if (selected != null) setState(() => _date.text = _formatDate(selected));
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    final pesoVal = double.parse(_weight.text.replaceFirst(',', '.'));
    final dataVal = _date.text.trim();
    final methodVal = _method;
    try {
      final result = await widget.api.registerWeighing(
        widget.animalId,
        peso: pesoVal,
        data: dataVal,
        method: methodVal,
      );
      if (mounted) Navigator.of(context).pop<WeighingResult>(result);
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        Navigator.of(context).popUntil((route) => route.isFirst);
        widget.onUnauthorized();
      } else {
        setState(() => _error = error.message);
      }
    } catch (_) {
      await _offlineQueue.enqueueWeighing(
        animalId: widget.animalId,
        peso: pesoVal,
        data: dataVal,
        method: methodVal,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Salvo. Será enviado quando houver conexão.'),
          ),
        );
        Navigator.of(context).pop(true);
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text('Pesagem ${widget.animalId}')),
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
                      TextFormField(
                        key: const ValueKey('weighing-weight'),
                        controller: _weight,
                        autofocus: true,
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
                        key: const ValueKey('weighing-date'),
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
                        key: const ValueKey('weighing-method'),
                        initialValue: 'pesado',
                        decoration: const InputDecoration(
                          labelText: 'Método',
                          prefixIcon: Icon(Icons.scale_outlined),
                        ),
                        isExpanded: true,
                        items: const [
                          DropdownMenuItem(
                            value: 'pesado',
                            child: Text('Pesado na balança'),
                          ),
                          DropdownMenuItem(
                            value: 'estimado',
                            child: Text('Estimado pelo operador'),
                          ),
                          DropdownMenuItem(
                            value: 'medicao',
                            child: Text('Estimado por medição (fita/fórmula)'),
                          ),
                        ],
                        onChanged: (value) => _method = value!,
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
                key: const ValueKey('save-weighing'),
                onPressed: _saving ? null : _submit,
                icon: _saving
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.save_outlined),
                label: Text(_saving ? 'Salvando…' : 'Salvar pesagem'),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
