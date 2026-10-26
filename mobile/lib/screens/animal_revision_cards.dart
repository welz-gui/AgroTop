import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models.dart';
import 'revision_pages.dart';

/// Pesagens e movimentações recentes do animal, cada uma com o botão de corrigir ou cancelar
/// (só nas que o servidor diz serem revisáveis). Se o servidor não tem essas listas (versão
/// anterior) ou não responde, os cartões simplesmente não aparecem: a ficha não depende deles.
class AnimalRevisionCards extends StatefulWidget {
  const AnimalRevisionCards({
    super.key,
    required this.api,
    required this.animalId,
    required this.onUnauthorized,
    required this.onChanged,
  });

  final ApiClient api;
  final String animalId;
  final VoidCallback onUnauthorized;

  /// Algo foi corrigido ou cancelado: a ficha precisa recarregar.
  final VoidCallback onChanged;

  @override
  State<AnimalRevisionCards> createState() => _AnimalRevisionCardsState();
}

class _AnimalRevisionCardsState extends State<AnimalRevisionCards> {
  late final Future<(List<WeighingRecord>, List<MovementRecord>)> _historico =
      _carregar();

  Future<(List<WeighingRecord>, List<MovementRecord>)> _carregar() async {
    final pesagens = await widget.api.listAnimalWeighings(widget.animalId);
    final movimentacoes = await widget.api.listAnimalMovements(widget.animalId);
    return (pesagens, movimentacoes);
  }

  static const _metodos = {
    'pesado': 'Pesado',
    'estimado': 'Estimado',
    'medicao': 'Por medição',
  };

  Future<void> _abrir(Widget pagina) async {
    final mudou = await Navigator.of(
      context,
    ).push<bool>(MaterialPageRoute(builder: (_) => pagina));
    if (mudou != true || !mounted) return;
    widget.onChanged();
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      const SnackBar(
        content: Text('Registro atualizado. O original fica no histórico.'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) =>
      FutureBuilder<(List<WeighingRecord>, List<MovementRecord>)>(
        future: _historico,
        builder: (context, snapshot) {
          final dados = snapshot.data;
          if (dados == null) return const SizedBox.shrink();
          final (pesagens, movimentacoes) = dados;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (pesagens.isNotEmpty)
                Card(
                  key: const ValueKey('weighings-history-card'),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 8,
                          ),
                          child: Text(
                            'Pesagens recentes',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ),
                        for (final p in pesagens)
                          ListTile(
                            leading: const Icon(Icons.monitor_weight_outlined),
                            title: Text('${p.peso} kg · ${p.data}'),
                            subtitle: Text(_metodos[p.method] ?? p.method),
                            trailing: p.revisavel
                                ? IconButton(
                                    key: ValueKey('correct-weighing-${p.id}'),
                                    tooltip: 'Corrigir ou cancelar',
                                    icon: const Icon(Icons.edit_outlined),
                                    onPressed: () => _abrir(
                                      WeighingRevisionPage(
                                        api: widget.api,
                                        animalId: widget.animalId,
                                        registro: p,
                                        onUnauthorized: widget.onUnauthorized,
                                      ),
                                    ),
                                  )
                                : null,
                          ),
                      ],
                    ),
                  ),
                ),
              if (pesagens.isNotEmpty && movimentacoes.isNotEmpty)
                const SizedBox(height: 12),
              if (movimentacoes.isNotEmpty)
                Card(
                  key: const ValueKey('movements-history-card'),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 8,
                          ),
                          child: Text(
                            'Movimentações recentes',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ),
                        for (final m in movimentacoes)
                          ListTile(
                            leading: const Icon(Icons.swap_horiz),
                            title: Text('${m.de ?? 'Entrada'} → ${m.para}'),
                            subtitle: Text(
                              '${m.data}${m.motivo == null ? '' : ' · ${m.motivo}'}',
                            ),
                            trailing: m.revisavel
                                ? IconButton(
                                    key: ValueKey('correct-movement-${m.id}'),
                                    tooltip: 'Corrigir ou cancelar',
                                    icon: const Icon(Icons.edit_outlined),
                                    onPressed: () => _abrir(
                                      MovementRevisionPage(
                                        api: widget.api,
                                        animalId: widget.animalId,
                                        registro: m,
                                        onUnauthorized: widget.onUnauthorized,
                                      ),
                                    ),
                                  )
                                : null,
                          ),
                      ],
                    ),
                  ),
                ),
            ],
          );
        },
      );
}
