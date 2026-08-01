import 'package:flutter/material.dart';

import '../api_client.dart';
import '../app.dart';
import '../models.dart';

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
  late Future<List<AnimalSummary>> _animals;

  @override
  void initState() {
    super.initState();
    _animals = widget.api.listAnimals();
  }

  void _reload() => setState(() => _animals = widget.api.listAnimals());

  Future<void> _logout() async {
    await widget.api.logout();
    widget.onUnauthorized();
  }

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
    body: FutureBuilder<List<AnimalSummary>>(
      future: _animals,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          final error = snapshot.error;
          if (error is ApiException && error.statusCode == 401) {
            WidgetsBinding.instance.addPostFrameCallback((_) async {
              await widget.api.logout();
              widget.onUnauthorized();
            });
          }
          return ErrorState(
            message: error is ApiException
                ? error.message
                : 'API indisponível. Nenhum dado fictício foi exibido.',
            onRetry: _reload,
          );
        }
        final animals = snapshot.data!;
        if (animals.isEmpty) {
          return const Center(child: Text('Nenhum animal ativo no banco.'));
        }
        return RefreshIndicator(
          onRefresh: () async => _reload(),
          child: ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: animals.length,
            separatorBuilder: (_, _) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              final animal = animals[index];
              return Card(
                child: ListTile(
                  minVerticalPadding: 14,
                  leading: CircleAvatar(
                    child: Text(animal.id.replaceFirst('BR', '')),
                  ),
                  title: Text(animal.id),
                  subtitle: Text(
                    '${animal.breed} · ${animal.currentWeight.toStringAsFixed(1)} kg'
                    '${animal.loteId == null ? '' : ' · ${animal.loteId}'}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) =>
                          AnimalDetailPage(api: widget.api, id: animal.id),
                    ),
                  ),
                ),
              );
            },
          ),
        );
      },
    ),
  );
}

class AnimalDetailPage extends StatelessWidget {
  const AnimalDetailPage({super.key, required this.api, required this.id});

  final ApiClient api;
  final String id;

  String _metric(double? value, String suffix, {int decimals = 1}) =>
      value == null
      ? 'Sem dados'
      : '${value.toStringAsFixed(decimals)} $suffix';

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text('Ficha $id')),
    body: FutureBuilder<AnimalDetail>(
      future: api.getAnimal(id),
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return ErrorState(
            message: snapshot.error is ApiException
                ? (snapshot.error! as ApiException).message
                : 'API indisponível. A ficha não pôde ser carregada.',
            onRetry: () => Navigator.of(context).pushReplacement(
              MaterialPageRoute(
                builder: (_) => AnimalDetailPage(api: api, id: id),
              ),
            ),
          );
        }
        final animal = snapshot.data!;
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
                    Text(
                      '${animal.breed} · ${animal.sex == 'M' ? 'Macho' : 'Fêmea'}',
                    ),
                    Text(
                      'Piquete: ${animal.loteName ?? animal.loteId ?? 'Não informado'}',
                    ),
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
            const SizedBox(height: 16),
            const ListTile(
              leading: Icon(Icons.verified_outlined),
              title: Text('GMD calculado no servidor'),
              subtitle: Text(
                'O aplicativo só exibe o resultado da API; não há fórmula de GMD no Dart.',
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
