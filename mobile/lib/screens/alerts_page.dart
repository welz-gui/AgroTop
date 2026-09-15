import 'package:flutter/material.dart';

import '../api_client.dart';
import '../app_colors.dart';
import '../copy.dart';
import '../formatters.dart';
import '../models.dart';

enum AlertCategoria { sumidos, carencia, prontosParaAbate }

class AlertsPage extends StatefulWidget {
  const AlertsPage({
    super.key,
    required this.api,
    required this.onUnauthorized,
    this.focusCategoria,
  });

  final ApiClient api;
  final VoidCallback onUnauthorized;
  final AlertCategoria? focusCategoria;

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
          alertsError = erroCarregamento('alertas');
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
          recomendacoesError = erroCarregamento('recomendações');
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
        _error = alertsError ?? recomendacoesError ?? kErroGenericoRede;
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

  String _titleForCategoria(AlertCategoria categoria) {
    switch (categoria) {
      case AlertCategoria.sumidos:
        return 'Animais Sumidos';
      case AlertCategoria.carencia:
        return 'Em Período de Carência';
      case AlertCategoria.prontosParaAbate:
        return 'Prontos para Abate';
    }
  }

  @override
  Widget build(BuildContext context) {
    final alerts = _alerts;
    final recomendacoes = _recomendacoes;
    final hasContent = alerts != null || recomendacoes != null;
    final title = widget.focusCategoria != null
        ? _titleForCategoria(widget.focusCategoria!)
        : 'Alertas operacionais';

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          if (widget.focusCategoria != null)
            Tooltip(
              message: 'Ver todos os alertas',
              child: TextButton(
                key: const ValueKey('alerts-ver-todos'),
                onPressed: () {
                  Navigator.of(context).pushReplacement(
                    MaterialPageRoute(
                      builder: (_) => AlertsPage(
                        api: widget.api,
                        onUnauthorized: widget.onUnauthorized,
                      ),
                    ),
                  );
                },
                child: const Text('Ver todos os alertas'),
              ),
            ),
        ],
      ),
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
                  if (widget.focusCategoria == null) ...[
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
                  ],
                  if (alerts != null) ...[
                    if (widget.focusCategoria == null ||
                        widget.focusCategoria == AlertCategoria.sumidos)
                      _AlertSection(
                        title: '🔴 Animais Sumidos (${alerts.sumidos.length})',
                        emptyMessage: '✅ Nenhum animal sumido.',
                        children: alerts.sumidos
                            .map(
                              (alert) => _AlertCard(
                                title: '${alert.animalId} — ${alert.breed}',
                                subtitle:
                                    'Lote ${alert.loteId ?? '—'} · Último peso ${_weight(alert.pesoAtual)} · ${alert.diasSemPesagem} dias sem pesagem',
                                statusColor: _tokenColor(context, 'perigo'),
                              ),
                            )
                            .toList(growable: false),
                      ),
                    if (widget.focusCategoria == null ||
                        widget.focusCategoria == AlertCategoria.carencia)
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
                                statusColor: _tokenColor(context, 'atencao'),
                              ),
                            )
                            .toList(growable: false),
                      ),
                    if (widget.focusCategoria == null ||
                        widget.focusCategoria == AlertCategoria.prontosParaAbate)
                      _AlertSection(
                        title:
                            '🟢 Prontos para Abate (${alerts.prontosParaAbate.length})',
                        emptyMessage: '✅ Nenhum animal atingiu o peso-alvo ainda.',
                        children: alerts.prontosParaAbate
                            .map(
                              (alert) => _AlertCard(
                                title: '${alert.animalId} — ${alert.breed}',
                                subtitle:
                                    'Peso ${_weight(alert.pesoAtual)} · alvo ${_weight(alert.pesoAlvo)} · ${formatDecimalBr(alert.arrobas, digits: 2)} @',
                              ),
                            )
                            .toList(growable: false),
                      ),
                    if (widget.focusCategoria == null)
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
                                statusColor: _tokenColor(context, 'atencao'),
                              ),
                            )
                            .toList(growable: false),
                      ),
                    if (widget.focusCategoria == null)
                      _AlertSection(
                        title:
                            '📉 Baixo Desempenho (${alerts.baixoDesempenho.length})',
                        emptyMessage: '✅ Nenhum animal abaixo da meta de GMD.',
                        children: alerts.baixoDesempenho
                            .map(
                              (alert) => _AlertCard(
                                title: '${alert.animalId} — ${alert.breed}',
                                subtitle:
                                    'Lote ${alert.loteId ?? '—'} · peso ${_weight(alert.pesoAtual)} · GMD ${formatDecimalBr(alert.gmd, digits: 3)} kg/dia · referência ${formatDecimalBr(alert.gmdReferencia, digits: 3)} kg/dia',
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

String _weight(double value) => '${formatDecimalBr(value, digits: 1)} kg';

String _quantity(double value, String unit) =>
    '${formatDecimalBr(value, digits: 1)} $unit';

Color _tokenColor(BuildContext context, String token) {
  final colors = Theme.of(context).brightness == Brightness.dark
      ? AppColors.dark
      : AppColors.light;
  return colors[token]!;
}

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
  const _AlertCard({
    required this.title,
    required this.subtitle,
    this.statusColor,
  });

  final String title;
  final String subtitle;
  final Color? statusColor;

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(bottom: 8),
    shape: statusColor == null
        ? null // usa o CardTheme padrão (borda neutra), sem mudança de hoje
        : RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(color: statusColor!, width: 1.5),
          ),
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
    switch (item.severidade.toLowerCase()) {
      case 'alta':
        return _tokenColor(context, 'perigo');
      case 'baixa':
        return _tokenColor(context, 'sucesso');
      case 'media':
      default:
        return _tokenColor(context, 'atencao');
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

