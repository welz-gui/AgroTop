import 'package:flutter/material.dart';

import '../api_client.dart';
import '../app.dart';
import '../models.dart';
import 'weighing_page.dart';

class AnimalsPage extends StatefulWidget {
  const AnimalsPage({
    super.key,
    required this.api,
    required this.themeMode,
    required this.onThemeChanged,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final ThemeMode themeMode;
  final ValueChanged<ThemeMode> onThemeChanged;
  final VoidCallback onUnauthorized;

  @override
  State<AnimalsPage> createState() => _AnimalsPageState();
}

class _AnimalsPageState extends State<AnimalsPage> {
  static const _pageSize = 50;

  final _animals = <AnimalSummary>[];
  bool _loading = true;
  bool _loadingMore = false;
  bool _hasMore = true;
  String? _error;
  String _query = '';

  @override
  void initState() {
    super.initState();
    _load(reset: true);
  }

  Future<void> _load({required bool reset}) async {
    setState(() {
      if (reset) {
        _loading = true;
        _error = null;
      } else {
        _loadingMore = true;
      }
    });
    try {
      final page = await widget.api.listAnimals(
        skip: reset ? 0 : _animals.length,
        limit: _pageSize,
      );
      if (!mounted) return;
      setState(() {
        if (reset) _animals.clear();
        _animals.addAll(page);
        _hasMore = page.length == _pageSize;
        _error = null;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        widget.onUnauthorized();
        return;
      }
      setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'API indisponível. Verifique a conexão e tente novamente.',
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
          _loadingMore = false;
        });
      }
    }
  }

  Future<void> _logout() async {
    try {
      await widget.api.logout();
    } finally {
      if (mounted) widget.onUnauthorized();
    }
  }

  String _weight(double? value) =>
      value == null ? 'Peso não informado' : '${value.toStringAsFixed(1)} kg';

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Animais ativos'),
      actions: [
        ThemePicker(value: widget.themeMode, onChanged: widget.onThemeChanged),
        IconButton(
          onPressed: _logout,
          tooltip: 'Sair',
          icon: const Icon(Icons.logout),
        ),
      ],
    ),
    body: _buildBody(),
  );

  Widget _buildBody() {
    if (_loading && _animals.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && _animals.isEmpty) {
      return ErrorState(message: _error!, onRetry: () => _load(reset: true));
    }

    final normalizedQuery = _query.trim().toLowerCase();
    final filtered = _animals
        .where((animal) => animal.id.toLowerCase().contains(normalizedQuery))
        .toList(growable: false);

    return RefreshIndicator(
      onRefresh: () => _load(reset: true),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            key: const ValueKey('animal-search'),
            decoration: const InputDecoration(
              labelText: 'Buscar por ID ou brinco',
              prefixIcon: Icon(Icons.search),
            ),
            onChanged: (value) => setState(() => _query = value),
          ),
          const SizedBox(height: 16),
          if (_error != null) ...[
            Card(
              child: ListTile(
                leading: Icon(
                  Icons.error_outline,
                  color: Theme.of(context).colorScheme.error,
                ),
                title: Text(_error!),
                trailing: TextButton(
                  onPressed: () => _load(reset: false),
                  child: const Text('Tentar novamente'),
                ),
              ),
            ),
            const SizedBox(height: 12),
          ],
          if (filtered.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 32),
              child: Center(child: Text('Nenhum animal encontrado.')),
            )
          else
            for (final animal in filtered) ...[
              Card(
                child: ListTile(
                  minVerticalPadding: 14,
                  leading: CircleAvatar(
                    child: Text(
                      animal.id.length > 4
                          ? animal.id.substring(animal.id.length - 4)
                          : animal.id,
                    ),
                  ),
                  title: Text(animal.id),
                  subtitle: Text(
                    '${animal.breed ?? 'Raça não informada'} · ${_weight(animal.currentWeight)}'
                    '${animal.loteId == null ? '' : ' · ${animal.loteId}'}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => AnimalDetailPage(
                        api: widget.api,
                        id: animal.id,
                        onUnauthorized: widget.onUnauthorized,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 8),
            ],
          if (_hasMore)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: OutlinedButton.icon(
                onPressed: _loadingMore ? null : () => _load(reset: false),
                icon: _loadingMore
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.expand_more),
                label: Text(_loadingMore ? 'Carregando…' : 'Carregar mais'),
              ),
            ),
        ],
      ),
    );
  }
}

class AnimalDetailPage extends StatefulWidget {
  const AnimalDetailPage({
    super.key,
    required this.api,
    required this.id,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final String id;
  final VoidCallback onUnauthorized;

  @override
  State<AnimalDetailPage> createState() => _AnimalDetailPageState();
}

class _AnimalDetailPageState extends State<AnimalDetailPage> {
  late Future<AnimalDetail> _detail;

  @override
  void initState() {
    super.initState();
    _detail = widget.api.getAnimal(widget.id);
  }

  void _reload() => setState(() {
    _detail = widget.api.getAnimal(widget.id);
  });

  String _metric(double? value, String suffix, {int decimals = 1}) =>
      value == null
      ? 'Sem dados'
      : '${value.toStringAsFixed(decimals)} $suffix';

  String _value(Object? value) => value?.toString() ?? 'Não informado';

  Future<void> _openWeighing() async {
    final result = await Navigator.of(context).push<WeighingResult>(
      MaterialPageRoute(
        builder: (_) => WeighingPage(
          api: widget.api,
          animalId: widget.id,
          onUnauthorized: widget.onUnauthorized,
        ),
      ),
    );
    if (result == null || !mounted) return;
    _reload();
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(result.message)));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text('Ficha ${widget.id}')),
    body: FutureBuilder<AnimalDetail>(
      future: _detail,
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
          return ErrorState(
            message: error is ApiException
                ? error.message
                : 'API indisponível. A ficha não pôde ser carregada.',
            onRetry: _reload,
          );
        }
        final animal = snapshot.data!;
        final sex = switch (animal.sex) {
          'M' => 'Macho',
          'F' => 'Fêmea',
          _ => 'Não informado',
        };
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.pets),
                        const SizedBox(width: 12),
                        Text(
                          animal.id,
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text('${_value(animal.breed)} · $sex'),
                    Text(
                      'Piquete: ${animal.lotName ?? animal.loteId ?? 'Não informado'}',
                    ),
                    Text('Status: ${_value(animal.status)}'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                MetricCard(
                  icon: Icons.monitor_weight_outlined,
                  label: 'Peso atual',
                  value: _metric(animal.currentWeight, 'kg'),
                ),
                MetricCard(
                  icon: Icons.login,
                  label: 'Peso de entrada',
                  value: _metric(animal.entryWeight, 'kg'),
                ),
                MetricCard(
                  icon: Icons.trending_up,
                  label: 'GMD recente',
                  value: _metric(animal.gmdRecent, 'kg/dia', decimals: 3),
                ),
                MetricCard(
                  icon: Icons.timeline,
                  label: 'GMD total',
                  value: _metric(animal.gmdTotal, 'kg/dia', decimals: 3),
                ),
                MetricCard(
                  icon: Icons.flag_outlined,
                  label: 'Peso-alvo',
                  value: _metric(animal.targetWeight, 'kg'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Card(
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.cake_outlined),
                    title: const Text('Nascimento'),
                    subtitle: Text(_value(animal.birthDate)),
                  ),
                  ListTile(
                    leading: const Icon(Icons.calendar_today_outlined),
                    title: const Text('Entrada'),
                    subtitle: Text(_value(animal.entryDate)),
                  ),
                  ListTile(
                    leading: const Icon(Icons.store_outlined),
                    title: const Text('Fornecedor'),
                    subtitle: Text(
                      animal.fornecedorName ?? _value(animal.fornecedorId),
                    ),
                  ),
                  ListTile(
                    leading: const Icon(Icons.fingerprint),
                    title: const Text('UUID do animal'),
                    subtitle: Text(_value(animal.animalUuid)),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              key: const ValueKey('open-weighing'),
              onPressed: _openWeighing,
              icon: const Icon(Icons.monitor_weight_outlined),
              label: const Text('Registrar pesagem'),
            ),
            const SizedBox(height: 12),
            const ListTile(
              leading: Icon(Icons.verified_outlined),
              title: Text('Indicadores calculados no servidor'),
              subtitle: Text(
                'O aplicativo apenas exibe os resultados recebidos da API.',
              ),
            ),
          ],
        );
      },
    ),
  );
}

class MetricCard extends StatelessWidget {
  const MetricCard({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: 170,
    child: Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 12),
            Text(label, style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 4),
            Text(value, style: Theme.of(context).textTheme.titleMedium),
          ],
        ),
      ),
    ),
  );
}

class ErrorState extends StatelessWidget {
  const ErrorState({super.key, required this.message, required this.onRetry});

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
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Tentar novamente'),
          ),
        ],
      ),
    ),
  );
}
