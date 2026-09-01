import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models.dart';

class AlertsPage extends StatefulWidget {
  const AlertsPage({
    super.key,
    required this.api,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final VoidCallback onUnauthorized;

  @override
  State<AlertsPage> createState() => _AlertsPageState();
}

class _AlertsPageState extends State<AlertsPage> {
  OperationalAlerts? _alerts;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final alerts = await widget.api.getOperationalAlerts();
      if (mounted) {
        setState(() {
          _alerts = alerts;
          _error = null;
        });
      }
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
              'API indisponível. Os alertas não puderam ser carregados.',
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final alerts = _alerts;
    return Scaffold(
      appBar: AppBar(title: const Text('Alertas operacionais')),
      body: alerts == null
          ? _error == null
                ? const Center(child: CircularProgressIndicator())
                : _LoadError(message: _error!, onRetry: _load)
          : RefreshIndicator(
              key: const ValueKey('alerts-refresh'),
              onRefresh: _load,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                children: [
                  _AlertSection(
                    title: '🔴 Animais Sumidos (${alerts.sumidos.length})',
                    emptyMessage: '✅ Nenhum animal sumido.',
                    children: alerts.sumidos
                        .map(
                          (alert) => _AlertCard(
                            title: '${alert.animalId} — ${alert.breed}',
                            subtitle:
                                'Lote ${alert.loteId ?? '—'} · Último peso ${_weight(alert.pesoAtual)} · ${alert.diasSemPesagem} dias sem pesagem',
                          ),
                        )
                        .toList(growable: false),
                  ),
                  _AlertSection(
                    title:
                        '🟡 Em Período de Carência (${alerts.carencia.length})',
                    emptyMessage: '✅ Nenhum animal em carência.',
                    children: alerts.carencia
                        .map(
                          (alert) => _AlertCard(
                            title: '${alert.animalId} — ${alert.breed}',
                            subtitle:
                                'Carência até ${alert.carenciaAte} · ${alert.diasRestantes} dias restantes',
                          ),
                        )
                        .toList(growable: false),
                  ),
                  _AlertSection(
                    title:
                        '🟢 Prontos para Abate (${alerts.prontosParaAbate.length})',
                    emptyMessage: '✅ Nenhum animal atingiu o peso-alvo ainda.',
                    children: alerts.prontosParaAbate
                        .map(
                          (alert) => _AlertCard(
                            title: '${alert.animalId} — ${alert.breed}',
                            subtitle:
                                'Peso ${_weight(alert.pesoAtual)} · alvo ${_weight(alert.pesoAlvo)} · ${alert.arrobas.toStringAsFixed(2)} @',
                          ),
                        )
                        .toList(growable: false),
                  ),
                  _AlertSection(
                    title:
                        '📦 Estoque Abaixo do Mínimo (${alerts.estoqueBaixo.length})',
                    emptyMessage: '✅ Todos os insumos com estoque adequado.',
                    children: alerts.estoqueBaixo
                        .map(
                          (alert) => _AlertCard(
                            title: alert.nome,
                            subtitle:
                                'Estoque ${_quantity(alert.estoqueAtual, alert.unidade)} · mínimo ${_quantity(alert.estoqueMinimo, alert.unidade)}',
                          ),
                        )
                        .toList(growable: false),
                  ),
                  _AlertSection(
                    title:
                        '📉 Baixo Desempenho (${alerts.baixoDesempenho.length})',
                    emptyMessage: '✅ Nenhum animal abaixo da meta de GMD.',
                    children: alerts.baixoDesempenho
                        .map(
                          (alert) => _AlertCard(
                            title: '${alert.animalId} — ${alert.breed}',
                            subtitle:
                                'Lote ${alert.loteId ?? '—'} · peso ${_weight(alert.pesoAtual)} · GMD ${alert.gmd.toStringAsFixed(3)} kg/dia · referência ${alert.gmdReferencia.toStringAsFixed(3)} kg/dia',
                          ),
                        )
                        .toList(growable: false),
                  ),
                ],
              ),
            ),
    );
  }
}

String _weight(double value) => '${value.toStringAsFixed(1)} kg';

String _quantity(double value, String unit) =>
    '${value.toStringAsFixed(1)} $unit';

class _AlertSection extends StatelessWidget {
  const _AlertSection({
    required this.title,
    required this.emptyMessage,
    required this.children,
  });

  final String title;
  final String emptyMessage;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 20),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        if (children.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(emptyMessage),
          )
        else
          ...children,
      ],
    ),
  );
}

class _AlertCard extends StatelessWidget {
  const _AlertCard({required this.title, required this.subtitle});

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(bottom: 8),
    child: ListTile(title: Text(title), subtitle: Text(subtitle)),
  );
}

class _LoadError extends StatelessWidget {
  const _LoadError({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 12),
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
