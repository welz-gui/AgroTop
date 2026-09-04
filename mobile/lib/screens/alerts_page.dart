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
  List<RecomendacaoItem>? _recomendacoes;
  String? _error;
  String? _alertsError;
  String? _recomendacoesError;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    OperationalAlerts? alerts;
    List<RecomendacaoItem>? recomendacoes;
    String? alertsError;
    String? recomendacoesError;
    bool unauthorized = false;

    await Future.wait([
      () async {
        try {
          alerts = await widget.api.getOperationalAlerts();
        } on ApiException catch (error) {
          if (error.statusCode == 401) {
            unauthorized = true;
          } else {
            alertsError = error.message;
          }
        } catch (_) {
          alertsError =
              'API indisponível. Os alertas não puderam ser carregados.';
        }
      }(),
      () async {
        try {
          recomendacoes = await widget.api.getRecomendacoes();
        } on ApiException catch (error) {
          if (error.statusCode == 401) {
            unauthorized = true;
          } else {
            recomendacoesError = error.message;
          }
        } catch (_) {
          recomendacoesError =
              'API indisponível. As recomendações não puderam ser carregadas.';
        }
      }(),
    ]);

    if (!mounted) return;
    if (unauthorized) {
      widget.onUnauthorized();
      return;
    }

    if (alerts == null && recomendacoes == null) {
      setState(() {
        _alerts = null;
        _recomendacoes = null;
        _alertsError = alertsError;
        _recomendacoesError = recomendacoesError;
        _error = alertsError ?? recomendacoesError ?? 'API indisponível.';
      });
      return;
    }

    setState(() {
      _alerts = alerts;
      _recomendacoes = recomendacoes;
      _alertsError = alertsError;
      _recomendacoesError = recomendacoesError;
      _error = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final alerts = _alerts;
    final recomendacoes = _recomendacoes;
    final hasContent = alerts != null || recomendacoes != null;

    return Scaffold(
      appBar: AppBar(title: const Text('Alertas operacionais')),
      body: !hasContent
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
                  if (recomendacoes != null)
                    _AlertSection(
                      title: '🧭 Recomendações (${recomendacoes.length})',
                      emptyMessage: '✅ Nenhuma recomendação no momento.',
                      children: _sortRecomendacoes(recomendacoes)
                          .map((rec) => _RecomendacaoCard(item: rec))
                          .toList(growable: false),
                    )
                  else if (_recomendacoesError != null)
                    _AlertSection(
                      title: '🧭 Recomendações',
                      emptyMessage: _recomendacoesError!,
                      children: const [],
                    ),
                  if (alerts != null) ...[
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
                  ] else if (_alertsError != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 20),
                      child: Text(
                        _alertsError!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
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

int _severityRank(String severidade) {
  switch (severidade.toLowerCase()) {
    case 'alta':
      return 0;
    case 'media':
      return 1;
    case 'baixa':
      return 2;
    default:
      return 9;
  }
}

List<RecomendacaoItem> _sortRecomendacoes(List<RecomendacaoItem> items) {
  final list = List<RecomendacaoItem>.from(items);
  list.sort(
    (a, b) =>
        _severityRank(a.severidade).compareTo(_severityRank(b.severidade)),
  );
  return list;
}

class _RecomendacaoCard extends StatelessWidget {
  const _RecomendacaoCard({required this.item});

  final RecomendacaoItem item;

  Color _severityColor(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    switch (item.severidade.toLowerCase()) {
      case 'alta':
        return Theme.of(context).colorScheme.error;
      case 'baixa':
        return Theme.of(context).colorScheme.primary;
      case 'media':
      default:
        return isDark ? const Color(0xFFFBBF24) : const Color(0xFFB45309);
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _severityColor(context);
    final acao = item.acao;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: color, width: 1.5),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              item.titulo,
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            const SizedBox(height: 4),
            Text(item.motivo, style: Theme.of(context).textTheme.bodyMedium),
            if (acao != null && acao.trim().isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                '👉 $acao',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

