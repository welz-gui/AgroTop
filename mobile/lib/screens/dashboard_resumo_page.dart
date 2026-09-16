import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../app_colors.dart';
import '../copy.dart';
import '../formatters.dart';
import '../models.dart';
import 'alerts_page.dart';

class DashboardResumoPage extends StatefulWidget {
  const DashboardResumoPage({
    super.key,
    required this.api,
    required this.onUnauthorized,
    this.nowProvider,
  });

  final ApiClient api;
  final VoidCallback onUnauthorized;
  final DateTime Function()? nowProvider;

  @override
  State<DashboardResumoPage> createState() => _DashboardResumoPageState();
}

class _DashboardResumoPageState extends State<DashboardResumoPage> {
  DashboardResumo? _resumo;
  String? _error;
  DateTime? _staleSince;
  String? _staleMessage;

  DateTime _now() => (widget.nowProvider ?? DateTime.now)();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final resumo = await widget.api.getDashboardResumo();
      if (!mounted) return;
      setState(() {
        _resumo = resumo;
        _staleSince = null;
        _staleMessage = null;
        _error = null;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        widget.onUnauthorized();
        return;
      }
      _handleError(error.message);
    } catch (_) {
      if (!mounted) return;
      _handleError(erroCarregamento('resumo do rebanho'));
    }
  }

  void _handleError(String message) {
    if (_resumo == null) {
      setState(() => _error = message);
    } else {
      setState(() {
        _staleSince ??= _now();
        _staleMessage = message;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final resumo = _resumo;
    return Scaffold(
      appBar: AppBar(title: const Text('Resumo do rebanho')),
      body: resumo == null
          ? _error == null
                ? const Center(child: CircularProgressIndicator())
                : _LoadError(message: _error!, onRetry: _load)
          : Column(
              children: [
                if (_staleSince != null)
                  _StaleDashboardBanner(
                    staleSince: _staleSince!,
                    staleMessage: _staleMessage,
                    onRetry: _load,
                  ),
                Expanded(
                  child: RefreshIndicator(
                    key: const ValueKey('dashboard-resumo-refresh'),
                    onRefresh: _load,
                    child: resumo.totalAnimais == 0
                        ? const _EmptyDashboard()
                        : _DashboardContent(
                            resumo: resumo,
                            api: widget.api,
                            onUnauthorized: widget.onUnauthorized,
                          ),
                  ),
                ),
              ],
            ),
    );
  }
}

class _StaleDashboardBanner extends StatelessWidget {
  const _StaleDashboardBanner({
    required this.staleSince,
    this.staleMessage,
    required this.onRetry,
  });

  final DateTime staleSince;
  final String? staleMessage;
  final VoidCallback onRetry;

  String get _formattedTime {
    final h = staleSince.hour.toString().padLeft(2, '0');
    final m = staleSince.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    return Container(
      key: const ValueKey('dashboard-stale-banner'),
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: colorScheme.surfaceContainerHighest,
      child: Row(
        children: [
          Tooltip(
            message: staleMessage ?? 'Não foi possível atualizar',
            child: Icon(
              Icons.cloud_off_outlined,
              size: 20,
              color: colorScheme.primary,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Não foi possível atualizar — última tentativa bem-sucedida antes de $_formattedTime',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          const SizedBox(width: 8),
          TextButton(
            key: const ValueKey('dashboard-stale-retry-button'),
            onPressed: onRetry,
            child: const Text('Tentar novamente'),
          ),
        ],
      ),
    );
  }
}

class _EmptyDashboard extends StatelessWidget {
  const _EmptyDashboard();

  @override
  Widget build(BuildContext context) => ListView(
    physics: const AlwaysScrollableScrollPhysics(),
    padding: const EdgeInsets.all(24),
    children: const [
      SizedBox(height: 96),
      Icon(Icons.pets_outlined, size: 48),
      SizedBox(height: 16),
      Text(
        'Nenhum animal cadastrado ainda.',
        key: ValueKey('dashboard-empty-message'),
        textAlign: TextAlign.center,
      ),
      SizedBox(height: 8),
      Text(
        'Cadastre animais para acompanhar o resumo do rebanho.',
        textAlign: TextAlign.center,
      ),
    ],
  );
}

class _DashboardContent extends StatelessWidget {
  const _DashboardContent({
    required this.resumo,
    required this.api,
    required this.onUnauthorized,
  });

  final DashboardResumo resumo;
  final ApiClient api;
  final VoidCallback onUnauthorized;

  void _openAlerts(BuildContext context, AlertCategoria categoria) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => AlertsPage(
          api: api,
          onUnauthorized: onUnauthorized,
          focusCategoria: categoria,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      key: const ValueKey('dashboard-resumo-list'),
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        Text('Alertas', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        _AlertCountCard(
          key: const ValueKey('dashboard-alert-sumidos'),
          icon: Icons.person_search_outlined,
          title: 'Sumidos',
          count: resumo.alertas.sumidos,
          color: _tokenColor(context, 'perigo'),
          onTap: () => _openAlerts(context, AlertCategoria.sumidos),
        ),
        const SizedBox(height: 8),
        _AlertCountCard(
          key: const ValueKey('dashboard-alert-carencia'),
          icon: Icons.medical_services_outlined,
          title: 'Em carência',
          count: resumo.alertas.carencia,
          color: _tokenColor(context, 'atencao'),
          onTap: () => _openAlerts(context, AlertCategoria.carencia),
        ),
        const SizedBox(height: 8),
        _AlertCountCard(
          key: const ValueKey('dashboard-alert-prontos'),
          icon: Icons.check_circle_outline,
          title: 'Prontos para abate',
          count: resumo.alertas.prontosParaAbate,
          color: _tokenColor(context, 'sucesso'),
          onTap: () => _openAlerts(context, AlertCategoria.prontosParaAbate),
        ),
        const SizedBox(height: 24),
        Text(
          'Indicadores do rebanho',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 12),
        _IndicadoresSection(resumo: resumo),
        if (resumo.distribuicaoPorRaca.isNotEmpty) ...[
          const SizedBox(height: 24),
          _BreedDonutChart(entries: resumo.distribuicaoPorRaca),
        ],
      ],
    );
  }
}

class _IndicadoresSection extends StatelessWidget {
  const _IndicadoresSection({required this.resumo});

  final DashboardResumo resumo;

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const ValueKey('dashboard-indicadores-section'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        GridView.count(
          key: const ValueKey('dashboard-kpi-grid'),
          crossAxisCount: 2,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.4,
          physics: const NeverScrollableScrollPhysics(),
          shrinkWrap: true,
          children: [
            _MetricCard(
              metric: _Metric(
                'Total de animais',
                '${resumo.totalAnimais}',
                'total-animais',
              ),
            ),
            _SexCompositionCard(
              machos: resumo.machos,
              femeas: resumo.femeas,
            ),
            _MetricCard(
              metric: _Metric(
                'Peso médio',
                '${_decimal(resumo.pesoMedioKg, 1)} kg',
                'peso-medio',
              ),
            ),
            _MetricCard(
              metric: _Metric(
                'GMD médio',
                '${_decimal(resumo.gmdMedioKgDia, 3)} kg/dia',
                'gmd-medio',
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: _SecondaryMetricCard(
                label: 'Arrobas produzidas',
                value: '${_decimal(resumo.arrobasProduzidas, 1)} @',
                keySuffix: 'arrobas-produzidas',
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _SecondaryMetricCard(
                label: 'Lotação',
                value: '${_decimal(resumo.lotacaoUaHa, 2)} UA/ha',
                keySuffix: 'lotacao',
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _SexCompositionCard extends StatelessWidget {
  const _SexCompositionCard({
    required this.machos,
    required this.femeas,
  });

  final int machos;
  final int femeas;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      key: const ValueKey('dashboard-kpi-sexo'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                'Machos e fêmeas',
                style: theme.textTheme.bodyMedium,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 6),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    '♂ ',
                    style: theme.textTheme.titleLarge?.copyWith(
                      color: theme.colorScheme.primary,
                    ),
                  ),
                  Text(
                    '$machos',
                    key: const ValueKey('dashboard-kpi-machos'),
                    style: theme.textTheme.titleLarge,
                  ),
                  Text(
                    ' · ',
                    style: theme.textTheme.titleLarge?.copyWith(
                      color: theme.colorScheme.outline,
                    ),
                  ),
                  Text(
                    '♀ ',
                    style: theme.textTheme.titleLarge?.copyWith(
                      color: theme.colorScheme.primary,
                    ),
                  ),
                  Text(
                    '$femeas',
                    key: const ValueKey('dashboard-kpi-femeas'),
                    style: theme.textTheme.titleLarge,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SecondaryMetricCard extends StatelessWidget {
  const _SecondaryMetricCard({
    required this.label,
    required this.value,
    required this.keySuffix,
  });

  final String label;
  final String value;
  final String keySuffix;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      key: ValueKey('dashboard-kpi-$keySuffix'),
      elevation: 0,
      color: theme.colorScheme.surfaceContainerLow,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                label,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),
              Text(
                value,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BreedDonutChart extends StatelessWidget {
  const _BreedDonutChart({required this.entries})
    : super(key: const ValueKey('dashboard-breed-donut'));

  final List<RacaContagem> entries;

  String get _semanticsLabel {
    final total = entries.fold<int>(0, (sum, entry) => sum + entry.quantidade);
    final summary = entries.map((entry) {
      final pct = total > 0 ? ((entry.quantidade / total) * 100).round() : 0;
      return '${entry.raca} $pct%';
    }).join(', ');
    return 'Gráfico de distribuição por raça: $summary';
  }

  @override
  Widget build(BuildContext context) {
    final colors = AppColors.series;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Distribuição por raça',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            Center(
              child: SizedBox(
                width: 144,
                height: 144,
                child: Semantics(
                  label: _semanticsLabel,
                  child: CustomPaint(
                    painter: _BreedDonutPainter(entries: entries),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            ...entries.asMap().entries.map(
              (entry) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  children: [
                    Container(
                      width: 12,
                      height: 12,
                      decoration: BoxDecoration(
                        color: colors[entry.key % colors.length],
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '${entry.value.raca} (${entry.value.quantidade})',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BreedDonutPainter extends CustomPainter {
  const _BreedDonutPainter({required this.entries});

  final List<RacaContagem> entries;

  @override
  void paint(ui.Canvas canvas, ui.Size size) {
    final total = entries.fold<int>(0, (sum, entry) => sum + entry.quantidade);
    if (total <= 0) return;

    final strokeWidth = 20.0;
    final radius = size.shortestSide / 2 - strokeWidth / 2;
    final center = ui.Offset(size.width / 2, size.height / 2);
    final rect = ui.Rect.fromCircle(center: center, radius: radius);
    final paint = ui.Paint()
      ..style = ui.PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = ui.StrokeCap.butt;
    var start = -math.pi / 2;
    for (final entry in entries.asMap().entries) {
      paint.color = AppColors.series[entry.key % AppColors.series.length];
      final sweep = math.pi * 2 * entry.value.quantidade / total;
      canvas.drawArc(rect, start, sweep, false, paint);
      start += sweep;
    }
  }

  @override
  bool shouldRepaint(_BreedDonutPainter oldDelegate) =>
      oldDelegate.entries != entries;
}

class _Metric {
  const _Metric(this.label, this.value, this.keySuffix);

  final String label;
  final String value;
  final String keySuffix;
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.metric});

  final _Metric metric;

  @override
  Widget build(BuildContext context) => Card(
    key: ValueKey('dashboard-kpi-${metric.keySuffix}'),
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: FittedBox(
        fit: BoxFit.scaleDown,
        alignment: Alignment.centerLeft,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              metric.label,
              style: Theme.of(context).textTheme.bodyMedium,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 6),
            Text(
              metric.value,
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ],
        ),
      ),
    ),
  );
}

class _AlertCountCard extends StatelessWidget {
  const _AlertCountCard({
    super.key,
    required this.icon,
    required this.title,
    required this.count,
    required this.color,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final int count;
  final Color color;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Card(
    child: ListTile(
      leading: Icon(icon, color: color),
      title: Text(title),
      subtitle: Text('$count animal(is)'),
      trailing: Text(
        '$count',
        style: Theme.of(context).textTheme.titleLarge?.copyWith(color: color),
      ),
      onTap: onTap,
    ),
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

Color _tokenColor(BuildContext context, String token) {
  final colors = Theme.of(context).brightness == Brightness.dark
      ? AppColors.dark
      : AppColors.light;
  return colors[token]!;
}

String _decimal(double value, int digits) => formatDecimalBr(value, digits: digits);
