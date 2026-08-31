import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models.dart';

class FeedingPage extends StatefulWidget {
  const FeedingPage({
    super.key,
    required this.api,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final VoidCallback onUnauthorized;

  @override
  State<FeedingPage> createState() => _FeedingPageState();
}

class _FeedingPageState extends State<FeedingPage> {
  List<PendingFeeding>? _feedings;
  String? _error;

  final _quickConfirming = <int>{};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final feedings = await widget.api.listPendingFeedings();
      if (mounted) setState(() => _feedings = feedings);
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
              'API indisponível. Os tratos não puderam ser carregados.',
        );
      }
    }
  }

  Future<void> _openDetail(PendingFeeding feeding) async {
    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (context) => _FeedingConfirmationSheet(
        api: widget.api,
        feeding: feeding,
        onUnauthorized: widget.onUnauthorized,
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() {
      _feedings = _feedings!
          .map(
            (item) =>
                item.planId == feeding.planId ? item.confirmedNow() : item,
          )
          .toList(growable: false);
    });
  }

  Future<void> _quickConfirm(PendingFeeding feeding) async {
    if (_quickConfirming.contains(feeding.planId)) return;
    setState(() => _quickConfirming.add(feeding.planId));
    try {
      await widget.api.confirmFeeding(
        feeding.planId,
        situation: 'feito',
        quantityApplied: feeding.quantidade,
        deductStock: feeding.insumoId != null,
      );
      if (!mounted) return;
      setState(() {
        _feedings = _feedings!
            .map(
              (item) =>
                  item.planId == feeding.planId ? item.confirmedNow() : item,
            )
            .toList(growable: false);
      });
      final messenger = ScaffoldMessenger.of(context);
      messenger.hideCurrentSnackBar();
      messenger.showSnackBar(
        SnackBar(content: Text('Trato confirmado: ${feeding.produto}')),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        Navigator.of(context).popUntil((route) => route.isFirst);
        widget.onUnauthorized();
      } else {
        final messenger = ScaffoldMessenger.of(context);
        messenger.hideCurrentSnackBar();
        messenger.showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } catch (_) {
      if (mounted) {
        final messenger = ScaffoldMessenger.of(context);
        messenger.hideCurrentSnackBar();
        messenger.showSnackBar(
          const SnackBar(
            content: Text(
              'API indisponível. Verifique a conexão e tente novamente.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _quickConfirming.remove(feeding.planId));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final feedings = _feedings;
    return Scaffold(
      appBar: AppBar(title: const Text('Trato do dia')),
      body: feedings == null
          ? _error == null
                ? const Center(child: CircularProgressIndicator())
                : _LoadError(message: _error!, onRetry: _load)
          : _FeedingList(
              feedings: feedings,
              onOpenDetail: _openDetail,
              onQuickConfirm: _quickConfirm,
              quickConfirming: _quickConfirming,
            ),
    );
  }
}

class _FeedingList extends StatelessWidget {
  const _FeedingList({
    required this.feedings,
    required this.onOpenDetail,
    required this.onQuickConfirm,
    required this.quickConfirming,
  });

  final List<PendingFeeding> feedings;
  final ValueChanged<PendingFeeding> onOpenDetail;
  final ValueChanged<PendingFeeding> onQuickConfirm;
  final Set<int> quickConfirming;

  @override
  Widget build(BuildContext context) {
    final pendingCount = feedings
        .where((item) => !item.confirmadoNoPeriodo)
        .length;
    final grouped = <String, List<PendingFeeding>>{};
    for (final feeding in feedings) {
      grouped.putIfAbsent(feeding.loteId, () => []).add(feeding);
    }
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            key: const ValueKey('feeding-summary'),
            child: ListTile(
              leading: Icon(
                pendingCount == 0
                    ? Icons.check_circle_outline
                    : Icons.agriculture_outlined,
              ),
              title: Text(
                pendingCount == 0
                    ? 'Tudo confirmado'
                    : '$pendingCount item(ns) pendente(s)',
              ),
              subtitle: const Text('Os itens confirmados continuam na lista.'),
            ),
          ),
          const SizedBox(height: 12),
          if (feedings.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: Text('Nenhum trato programado para hoje.'),
              ),
            )
          else
            for (final entry in grouped.entries) ...[
              _LoteFeedingSection(
                loteId: entry.key,
                loteNome: entry.value.first.loteNome,
                feedings: entry.value,
                onOpenDetail: onOpenDetail,
                onQuickConfirm: onQuickConfirm,
                quickConfirming: quickConfirming,
              ),
              const SizedBox(height: 12),
            ],
        ],
      ),
    );
  }
}

class _LoteFeedingSection extends StatelessWidget {
  const _LoteFeedingSection({
    required this.loteId,
    required this.loteNome,
    required this.feedings,
    required this.onOpenDetail,
    required this.onQuickConfirm,
    required this.quickConfirming,
  });

  final String loteId;
  final String loteNome;
  final List<PendingFeeding> feedings;
  final ValueChanged<PendingFeeding> onOpenDetail;
  final ValueChanged<PendingFeeding> onQuickConfirm;
  final Set<int> quickConfirming;

  @override
  Widget build(BuildContext context) => Card(
    key: ValueKey('feeding-lote-$loteId'),
    child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                const Icon(Icons.grass_outlined),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '$loteNome · $loteId',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
              ],
            ),
          ),
          for (final feeding in feedings)
            _FeedingItem(
              feeding: feeding,
              onOpenDetail: onOpenDetail,
              onQuickConfirm: onQuickConfirm,
              isQuickConfirming: quickConfirming.contains(feeding.planId),
            ),
        ],
      ),
    ),
  );
}

class _FeedingItem extends StatelessWidget {
  const _FeedingItem({
    required this.feeding,
    required this.onOpenDetail,
    required this.onQuickConfirm,
    this.isQuickConfirming = false,
  });

  final PendingFeeding feeding;
  final ValueChanged<PendingFeeding> onOpenDetail;
  final ValueChanged<PendingFeeding> onQuickConfirm;
  final bool isQuickConfirming;

  @override
  Widget build(BuildContext context) {
    final confirmed = feeding.confirmadoNoPeriodo;
    return Opacity(
      opacity: confirmed ? 0.65 : 1,
      child: ListTile(
        key: ValueKey('feeding-item-${feeding.planId}'),
        onTap: confirmed ? null : () => onOpenDetail(feeding),
        leading: Icon(
          confirmed ? Icons.check_circle : Icons.radio_button_unchecked,
          color: confirmed ? Theme.of(context).colorScheme.primary : null,
        ),
        title: Text(feeding.produto),
        subtitle: Text(
          '${feeding.quantidade.toStringAsFixed(2)} ${feeding.unidade} · ${feeding.frequencia}'
          '${confirmed ? '\n${feeding.ultimaConfirmacao == null ? 'Confirmado agora' : 'Confirmado em ${feeding.ultimaConfirmacao}'}' : ''}',
        ),
        isThreeLine: confirmed,
        trailing: confirmed
            ? const Icon(Icons.done, semanticLabel: 'Confirmado')
            : isQuickConfirming
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : IconButton(
                    key: ValueKey('confirm-feeding-${feeding.planId}'),
                    tooltip: 'Confirmação rápida',
                    icon: const Icon(Icons.check),
                    onPressed: () => onQuickConfirm(feeding),
                  ),
      ),
    );
  }
}

class _FeedingConfirmationSheet extends StatefulWidget {
  const _FeedingConfirmationSheet({
    required this.api,
    required this.feeding,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final PendingFeeding feeding;
  final VoidCallback onUnauthorized;

  @override
  State<_FeedingConfirmationSheet> createState() =>
      _FeedingConfirmationSheetState();
}

class _FeedingConfirmationSheetState extends State<_FeedingConfirmationSheet> {
  late final TextEditingController _quantity;
  final _notes = TextEditingController();
  var _situation = 'feito';
  late bool _deductStock;
  var _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _deductStock = widget.feeding.insumoId != null;
    _quantity = TextEditingController(
      text: widget.feeding.quantidade.toStringAsFixed(2),
    );
  }

  @override
  void dispose() {
    _quantity.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final quantity = double.tryParse(_quantity.text.replaceFirst(',', '.'));
    if (quantity == null || quantity < 0) {
      setState(() => _error = 'Informe uma quantidade válida.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.confirmFeeding(
        widget.feeding.planId,
        situation: _situation,
        quantityApplied: quantity,
        deductStock: _deductStock,
        notes: _notes.text.trim().isEmpty ? null : _notes.text.trim(),
      );
      if (mounted) Navigator.of(context).pop(true);
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        Navigator.of(context).pop();
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
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.only(
      left: 16,
      right: 16,
      top: 16,
      bottom: MediaQuery.viewInsetsOf(context).bottom + 16,
    ),
    child: SafeArea(
      top: false,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Confirmar ${widget.feeding.produto}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              key: const ValueKey('feeding-situation'),
              initialValue: _situation,
              decoration: const InputDecoration(labelText: 'Situação'),
              items: const [
                DropdownMenuItem(value: 'feito', child: Text('feito')),
                DropdownMenuItem(value: 'parcial', child: Text('parcial')),
                DropdownMenuItem(value: 'nao_feito', child: Text('nao_feito')),
              ],
              onChanged: _saving
                  ? null
                  : (value) => setState(() => _situation = value!),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const ValueKey('feeding-quantity'),
              controller: _quantity,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: InputDecoration(
                labelText: 'Quantidade aplicada',
                suffixText: widget.feeding.unidade,
              ),
            ),
            if (widget.feeding.insumoId != null)
              CheckboxListTile(
                key: const ValueKey('feeding-deduct-stock'),
                contentPadding: EdgeInsets.zero,
                value: _deductStock,
                onChanged: _saving
                    ? null
                    : (value) => setState(() => _deductStock = value ?? false),
                title: const Text('Baixar do estoque'),
              )
            else
              const ListTile(
                key: ValueKey('feeding-no-stock-link'),
                contentPadding: EdgeInsets.zero,
                leading: Icon(Icons.inventory_2_outlined),
                title: Text('Sem insumo vinculado ao estoque'),
              ),
            TextField(
              key: const ValueKey('feeding-notes'),
              controller: _notes,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Observações (opcional)',
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Semantics(
                liveRegion: true,
                child: Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            ],
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                key: const ValueKey('submit-feeding'),
                onPressed: _saving ? null : _submit,
                icon: _saving
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.check),
                label: Text(_saving ? 'Confirmando…' : 'Confirmar trato'),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _LoadError extends StatelessWidget {
  const _LoadError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

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
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: onRetry,
            child: const Text('Tentar novamente'),
          ),
        ],
      ),
    ),
  );
}
