import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models.dart';

class MovementPage extends StatefulWidget {
  const MovementPage({
    super.key,
    required this.api,
    required this.animalIds,
    required this.onUnauthorized,
    this.initialDate,
  });

  final ApiClient api;
  final List<String> animalIds;
  final VoidCallback onUnauthorized;
  final DateTime? initialDate;

  @override
  State<MovementPage> createState() => _MovementPageState();
}

class _MovementPageState extends State<MovementPage> {
  late final Future<List<LoteSummary>> _lotes;
  late final TextEditingController _date;
  final _notes = TextEditingController();
  String? _selectedLoteId;
  bool _saving = false;
  String? _error;
  MovementResult? _result;

  @override
  void initState() {
    super.initState();
    _lotes = widget.api.listLotes();
    _date = TextEditingController(
      text: _formatDate(widget.initialDate ?? DateTime.now()),
    );
  }

  @override
  void dispose() {
    _date.dispose();
    _notes.dispose();
    super.dispose();
  }

  String _formatDate(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';

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

  bool _validDate() {
    final parsed = DateTime.tryParse(_date.text);
    return parsed != null && _formatDate(parsed) == _date.text;
  }

  Future<void> _submit() async {
    if (_selectedLoteId == null) {
      setState(() => _error = 'Escolha o piquete de destino.');
      return;
    }
    if (!_validDate()) {
      setState(() => _error = 'Informe uma data válida no formato AAAA-MM-DD.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final result = await widget.api.moveAnimals(
        animalIds: widget.animalIds,
        toLoteId: _selectedLoteId!,
        movementDate: _date.text,
        notes: _notes.text.trim().isEmpty ? null : _notes.text.trim(),
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
      if (mounted) {
        setState(
          () => _error =
              'API indisponível. Verifique a conexão e tente novamente.',
        );
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
          result == null ? 'Mover de piquete' : 'Resultado da movimentação',
        ),
      ),
      body: result == null
          ? _buildForm()
          : MovementResultView(
              result: result,
              onDone: () => Navigator.of(context).pop(true),
            ),
    );
  }

  Widget _buildForm() => FutureBuilder<List<LoteSummary>>(
    future: _lotes,
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
        return _MovementError(
          message: error is ApiException
              ? error.message
              : 'API indisponível. Os piquetes não puderam ser carregados.',
        );
      }
      final lotes = snapshot.data!;
      return SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              widget.animalIds.length == 1
                  ? 'Animal selecionado: ${widget.animalIds.single}'
                  : '${widget.animalIds.length} animais selecionados',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            Text(
              'Piquete de destino',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            if (lotes.isEmpty)
              const Card(
                child: ListTile(
                  leading: Icon(Icons.info_outline),
                  title: Text('Nenhum piquete disponível.'),
                ),
              )
            else
              for (final lote in lotes) ...[
                Card(
                  child: InkWell(
                    key: ValueKey('movement-lote-${lote.id}'),
                    borderRadius: BorderRadius.circular(16),
                    onTap: () => setState(() {
                      _selectedLoteId = lote.id;
                      _error = null;
                    }),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                      child: Row(
                        children: [
                          Icon(
                            _selectedLoteId == lote.id
                                ? Icons.check_circle
                                : Icons.circle_outlined,
                            color: _selectedLoteId == lote.id
                                ? Theme.of(context).colorScheme.primary
                                : null,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  lote.nome,
                                  style: Theme.of(
                                    context,
                                  ).textTheme.titleMedium,
                                ),
                                Text(
                                  '${lote.animaisAtivos} animais ativos'
                                  '${lote.capacidadeUa == null ? '' : ' · ${lote.capacidadeUa!.toStringAsFixed(1)} UA'}',
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
              ],
            const SizedBox(height: 8),
            TextField(
              key: const ValueKey('movement-date'),
              controller: _date,
              decoration: InputDecoration(
                labelText: 'Data da movimentação',
                prefixIcon: const Icon(Icons.calendar_today_outlined),
                suffixIcon: IconButton(
                  tooltip: 'Escolher data',
                  onPressed: _pickDate,
                  icon: const Icon(Icons.edit_calendar_outlined),
                ),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const ValueKey('movement-notes'),
              controller: _notes,
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
              key: const ValueKey('confirm-movement'),
              onPressed: _saving || lotes.isEmpty ? null : _submit,
              icon: _saving
                  ? const SizedBox.square(
                      dimension: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.swap_horiz),
              label: Text(_saving ? 'Movimentando…' : 'Confirmar movimentação'),
            ),
          ],
        ),
      );
    },
  );
}

class MovementResultView extends StatelessWidget {
  const MovementResultView({super.key, required this.result, this.onDone});

  final MovementResult result;
  final VoidCallback? onDone;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _ResultSection(
          key: const ValueKey('movement-result-moved'),
          icon: Icons.check_circle_outline,
          title: 'Movidos (${result.movidos.length})',
          values: result.movidos,
          emptyText: 'Nenhum animal foi movido.',
          background: Theme.of(context).colorScheme.primaryContainer,
          foreground: Theme.of(context).colorScheme.onPrimaryContainer,
        ),
        const SizedBox(height: 12),
        _ResultSection(
          key: const ValueKey('movement-result-already'),
          icon: Icons.info_outline,
          title: 'Já estavam no destino (${result.jaNoDestino.length})',
          values: result.jaNoDestino,
          emptyText: 'Nenhum animal já estava no destino.',
          background: Theme.of(context).colorScheme.tertiaryContainer,
          foreground: Theme.of(context).colorScheme.onTertiaryContainer,
        ),
        const SizedBox(height: 12),
        _ResultSection(
          key: const ValueKey('movement-result-errors'),
          icon: Icons.error_outline,
          title: 'Erros (${result.erros.length})',
          values: result.erros,
          emptyText: 'Nenhum erro.',
          background: Theme.of(context).colorScheme.errorContainer,
          foreground: Theme.of(context).colorScheme.onErrorContainer,
        ),
        if (onDone != null) ...[
          const SizedBox(height: 24),
          FilledButton.icon(
            key: const ValueKey('finish-movement'),
            onPressed: onDone,
            icon: const Icon(Icons.done),
            label: const Text('Concluir'),
          ),
        ],
      ],
    ),
  );
}

class _ResultSection extends StatelessWidget {
  const _ResultSection({
    super.key,
    required this.icon,
    required this.title,
    required this.values,
    required this.emptyText,
    required this.background,
    required this.foreground,
  });

  final IconData icon;
  final String title;
  final List<String> values;
  final String emptyText;
  final Color background;
  final Color foreground;

  @override
  Widget build(BuildContext context) => Card(
    color: background,
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: foreground),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(
                    context,
                  ).textTheme.titleMedium?.copyWith(color: foreground),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (values.isEmpty)
            Text(emptyText, style: TextStyle(color: foreground))
          else
            for (final value in values)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('• $value', style: TextStyle(color: foreground)),
              ),
        ],
      ),
    ),
  );
}

class _MovementError extends StatelessWidget {
  const _MovementError({required this.message});

  final String message;

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
        ],
      ),
    ),
  );
}
