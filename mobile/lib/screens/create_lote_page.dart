import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models.dart';

class CreateLotePage extends StatefulWidget {
  const CreateLotePage({
    super.key,
    required this.api,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final VoidCallback onUnauthorized;

  @override
  State<CreateLotePage> createState() => _CreateLotePageState();
}

class _CreateLotePageState extends State<CreateLotePage> {
  final _idController = TextEditingController();
  final _nameController = TextEditingController();
  final _areaController = TextEditingController();
  final _capacityController = TextEditingController();
  final _notesController = TextEditingController();

  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _idController.addListener(_onFieldChanged);
    _nameController.addListener(_onFieldChanged);
    _areaController.addListener(_onFieldChanged);
    _capacityController.addListener(_onFieldChanged);
  }

  @override
  void dispose() {
    _idController.removeListener(_onFieldChanged);
    _nameController.removeListener(_onFieldChanged);
    _areaController.removeListener(_onFieldChanged);
    _capacityController.removeListener(_onFieldChanged);

    _idController.dispose();
    _nameController.dispose();
    _areaController.dispose();
    _capacityController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  void _onFieldChanged() {
    setState(() {});
  }

  bool get _isFormValid {
    final id = _idController.text.trim();
    final name = _nameController.text.trim();
    if (id.isEmpty || name.isEmpty) return false;

    final areaStr = _areaController.text.trim().replaceAll(',', '.');
    final area = double.tryParse(areaStr);
    if (area == null || area < 0) return false;

    final capStr = _capacityController.text.trim().replaceAll(',', '.');
    final cap = double.tryParse(capStr);
    if (cap == null || cap < 0) return false;

    return true;
  }

  Future<void> _submit() async {
    if (!_isFormValid) return;
    setState(() {
      _saving = true;
      _error = null;
    });

    final id = _idController.text.trim().toUpperCase();
    final name = _nameController.text.trim();
    final areaHa = double.parse(_areaController.text.trim().replaceAll(',', '.'));
    final capacityUa = double.parse(_capacityController.text.trim().replaceAll(',', '.'));
    final notes = _notesController.text.trim();

    try {
      final result = await widget.api.createLote(
        id: id,
        name: name,
        areaHa: areaHa,
        capacityUa: capacityUa,
        notes: notes,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Lote $id criado com sucesso.')),
      );
      Navigator.of(context).pop<LoteSummary>(result);
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.statusCode == 401) {
        widget.onUnauthorized();
        return;
      }
      setState(() {
        _error = e.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'API indisponível. Verifique a conexão e tente novamente.';
      });
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Novo lote'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_error != null) ...[
              Card(
                color: Theme.of(context).colorScheme.errorContainer,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Icon(
                        Icons.error_outline,
                        color: Theme.of(context).colorScheme.onErrorContainer,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _error!,
                          key: const ValueKey('lote-error-message'),
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.onErrorContainer,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
            ],
            TextField(
              key: const ValueKey('lote-id-field'),
              controller: _idController,
              decoration: const InputDecoration(
                labelText: 'ID do lote (ex: P07) *',
                hintText: 'Identificador único do piquete',
              ),
              textCapitalization: TextCapitalization.characters,
            ),
            const SizedBox(height: 16),
            TextField(
              key: const ValueKey('lote-name-field'),
              controller: _nameController,
              decoration: const InputDecoration(
                labelText: 'Nome *',
                hintText: 'Nome do piquete',
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              key: const ValueKey('lote-area-field'),
              controller: _areaController,
              decoration: const InputDecoration(
                labelText: 'Área (ha) *',
                hintText: 'Área em hectares',
              ),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
            ),
            const SizedBox(height: 16),
            TextField(
              key: const ValueKey('lote-capacity-field'),
              controller: _capacityController,
              decoration: const InputDecoration(
                labelText: 'Capacidade (UA) *',
                hintText: 'Capacidade em Unidades Animais',
              ),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
            ),
            const SizedBox(height: 16),
            TextField(
              key: const ValueKey('lote-notes-field'),
              controller: _notesController,
              decoration: const InputDecoration(
                labelText: 'Observações',
                hintText: 'Observações opcionais',
              ),
              maxLines: 3,
            ),
            const SizedBox(height: 24),
            FilledButton(
              key: const ValueKey('save-lote-button'),
              onPressed: _isFormValid && !_saving ? _submit : null,
              child: _saving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Criar lote'),
            ),
          ],
        ),
      ),
    );
  }
}
