import 'package:flutter/material.dart';

import '../api_client.dart';
import '../app_colors.dart';
import '../models.dart';

const Map<String, String> _origemIdadeLabels = {
  'propriedade': 'Nascido na propriedade (data exata)',
  'estimado': 'Nascimento estimado (mês aproximado)',
  'operador': 'Idade definida pelo operador',
  'nf_gta': 'Idade da NF / GTA',
};

const Map<String, String> _weighMethods = {
  'pesado': 'Pesado na balança',
  'estimado': 'Estimado pelo operador',
  'medicao': 'Estimado por medição (fita/fórmula)',
};

class ReportsPage extends StatefulWidget {
  const ReportsPage({
    super.key,
    required this.api,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final VoidCallback onUnauthorized;

  @override
  State<ReportsPage> createState() => _ReportsPageState();
}

class _ReportsPageState extends State<ReportsPage> {
  List<RelatorioInventarioItem>? _inventario;
  List<RelatorioPesagemItem>? _pesagens;
  String? _inventarioError;
  String? _pesagensError;
  bool _loading = true;
  String _selectedStatus = 'todos';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    List<RelatorioInventarioItem>? inventario;
    List<RelatorioPesagemItem>? pesagens;
    String? inventarioError;
    String? pesagensError;
    bool unauthorized = false;

    await Future.wait([
      () async {
        try {
          inventario = await widget.api.getRelatorioInventario();
        } on ApiException catch (error) {
          if (error.statusCode == 401) {
            unauthorized = true;
          } else {
            inventarioError = error.message;
          }
        } catch (_) {
          inventarioError =
              'Não foi possível carregar o relatório de inventário.';
        }
      }(),
      () async {
        try {
          pesagens = await widget.api.getRelatorioPesagens();
        } on ApiException catch (error) {
          if (error.statusCode == 401) {
            unauthorized = true;
          } else {
            pesagensError = error.message;
          }
        } catch (_) {
          pesagensError =
              'Não foi possível carregar o relatório de pesagens.';
        }
      }(),
    ]);

    if (!mounted) return;
    if (unauthorized) {
      setState(() => _loading = false);
      widget.onUnauthorized();
      return;
    }

    setState(() {
      _inventario = inventario;
      _pesagens = pesagens;
      _inventarioError = inventarioError;
      _pesagensError = pesagensError;
      _loading = false;
    });
  }

  Color _statusColor(BuildContext context, String status) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final colors = isDark ? AppColors.dark : AppColors.light;
    switch (status.toLowerCase()) {
      case 'ativo':
        return colors['sucesso']!;
      case 'vendido':
        return colors['info_texto'] ?? colors['info']!;
      case 'morto':
        return colors['perigo']!;
      case 'carencia':
        return colors['atencao']!;
      default:
        return colors['texto_secundario']!;
    }
  }

  String _statusLabel(String status) {
    switch (status.toLowerCase()) {
      case 'ativo':
        return 'Ativo';
      case 'vendido':
        return 'Vendido';
      case 'morto':
        return 'Morto';
      case 'carencia':
        return 'Carência';
      default:
        return status;
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Relatórios'),
          bottom: const TabBar(
            tabs: [
              Tab(
                key: ValueKey('tab-inventario'),
                text: '🐄 Inventário',
              ),
              Tab(
                key: ValueKey('tab-pesagens'),
                text: '⚖️ Pesagens',
              ),
            ],
          ),
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : TabBarView(
                children: [
                  _buildInventarioTab(context),
                  _buildPesagensTab(context),
                ],
              ),
      ),
    );
  }

  Widget _buildInventarioTab(BuildContext context) {
    if (_inventarioError != null && _inventario == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_inventarioError!, textAlign: TextAlign.center),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Tentar novamente'),
              ),
            ],
          ),
        ),
      );
    }

    final items = _inventario ?? [];
    final filtered = items.where((item) {
      if (_selectedStatus == 'todos') return true;
      return item.status.toLowerCase() == _selectedStatus.toLowerCase();
    }).toList(growable: false);

    final isDark = Theme.of(context).brightness == Brightness.dark;
    final colors = isDark ? AppColors.dark : AppColors.light;

    return RefreshIndicator(
      onRefresh: _load,
      child: Column(
        children: [
          _buildStatusFilter(),
          Expanded(
            child: filtered.isEmpty
                ? const Center(
                    child: Padding(
                      padding: EdgeInsets.all(24),
                      child: Text('Nenhum animal encontrado no inventário.'),
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.only(top: 4, bottom: 24),
                    itemCount: filtered.length,
                    itemBuilder: (context, index) {
                      final item = filtered[index];
                      return _buildInventarioCard(context, item, colors);
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusFilter() {
    const statuses = [
      {'key': 'todos', 'label': 'Todos'},
      {'key': 'ativo', 'label': 'Ativos'},
      {'key': 'carencia', 'label': 'Carência'},
      {'key': 'vendido', 'label': 'Vendidos'},
      {'key': 'morto', 'label': 'Mortos'},
    ];

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: statuses.map((st) {
          final isSelected = _selectedStatus == st['key'];
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              key: ValueKey('filter-${st['key']}'),
              label: Text(st['label']!),
              selected: isSelected,
              onSelected: (_) {
                setState(() => _selectedStatus = st['key']!);
              },
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildInventarioCard(
    BuildContext context,
    RelatorioInventarioItem item,
    Map<String, Color> colors,
  ) {
    final statusColor = _statusColor(context, item.status);
    final gmdText = item.gmdKgDia != null
        ? '${item.gmdKgDia!.toStringAsFixed(2)} kg/dia'
        : '—';

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          key: ValueKey('inventario-item-${item.id}'),
          leading: CircleAvatar(
            backgroundColor: colors['fundo_alt'],
            child: Text(
              item.id.length > 4
                  ? item.id.substring(item.id.length - 4)
                  : item.id,
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 12,
                color: colors['texto'],
              ),
            ),
          ),
          title: Row(
            children: [
              Text(
                item.id,
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: statusColor.withAlpha((0.15 * 255).round()),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: statusColor.withAlpha((0.4 * 255).round()),
                  ),
                ),
                child: Text(
                  _statusLabel(item.status),
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: statusColor,
                  ),
                ),
              ),
            ],
          ),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${item.raca ?? 'Sem raça'} · ${item.sexo ?? '—'} · Lote: ${item.loteId ?? 'Sem lote'}',
                  style: TextStyle(fontSize: 13, color: colors['texto_secundario']),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        '${item.categoriaIdade} (${item.idadeDisplay})',
                        style: const TextStyle(fontSize: 13),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (item.nascimentoEstimado) ...[
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 4,
                          vertical: 1,
                        ),
                        decoration: BoxDecoration(
                          color: colors['atencao_fundo'],
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: colors['atencao']!),
                        ),
                        child: Text(
                          '(est.)',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: colors['atencao'],
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  'Peso: ${item.pesoAtualKg.toStringAsFixed(1)} kg · GMD: $gmdText',
                  style: TextStyle(fontSize: 13, color: colors['texto']),
                ),
              ],
            ),
          ),
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: colors['fundo_alt'],
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  children: [
                    _buildDetailRow(
                      'Entrada',
                      '${item.dataEntrada.isNotEmpty ? item.dataEntrada : "—"} (${item.pesoEntradaKg.toStringAsFixed(1)} kg)',
                      colors,
                    ),
                    _buildDetailRow(
                      'Ganho acumulado',
                      '${item.ganhoKg >= 0 ? "+" : ""}${item.ganhoKg.toStringAsFixed(1)} kg (${item.arrobasAtuais.toStringAsFixed(2)} @)',
                      colors,
                    ),
                    _buildDetailRow(
                      'Data nascimento',
                      item.dataNascimento ?? 'Não informada',
                      colors,
                    ),
                    _buildDetailRow(
                      'Origem da idade',
                      _origemIdadeLabels[item.origemIdade] ?? item.origemIdade,
                      colors,
                    ),
                    _buildDetailRow(
                      'Fornecedor',
                      item.fornecedor ?? '—',
                      colors,
                    ),
                    _buildDetailRow(
                      'NF / GTA',
                      'NF: ${item.nf ?? "—"} / GTA: ${item.gta ?? "—"}',
                      colors,
                    ),
                    _buildDetailRow(
                      'Carência até',
                      item.carenciaAte ?? 'Sem carência',
                      colors,
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

  Widget _buildDetailRow(
    String label,
    String value,
    Map<String, Color> colors,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: colors['texto_secundario'],
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 12,
                color: colors['texto'],
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPesagensTab(BuildContext context) {
    if (_pesagensError != null && _pesagens == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_pesagensError!, textAlign: TextAlign.center),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Tentar novamente'),
              ),
            ],
          ),
        ),
      );
    }

    final items = _pesagens ?? [];
    if (items.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text('Nenhuma pesagem registrada.'),
        ),
      );
    }

    final isDark = Theme.of(context).brightness == Brightness.dark;
    final colors = isDark ? AppColors.dark : AppColors.light;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        itemCount: items.length,
        itemBuilder: (context, index) {
          final item = items[index];
          final metodoLabel = _weighMethods[item.metodo] ?? item.metodo;

          return Card(
            margin: const EdgeInsets.symmetric(vertical: 6),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          Icon(
                            Icons.monitor_weight_outlined,
                            size: 20,
                            color: colors['primaria'],
                          ),
                          const SizedBox(width: 8),
                          Text(
                            item.animalId,
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 16,
                            ),
                          ),
                        ],
                      ),
                      Text(
                        item.data,
                        style: TextStyle(
                          fontSize: 13,
                          color: colors['texto_secundario'],
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        '${item.pesoKg.toStringAsFixed(1)} kg',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: colors['texto'],
                        ),
                      ),
                      const SizedBox(width: 8),
                      Flexible(
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            color: colors['fundo_alt'],
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: colors['borda']!),
                          ),
                          child: Text(
                            metodoLabel,
                            style: TextStyle(
                              fontSize: 12,
                              color: colors['texto_secundario'],
                              fontWeight: FontWeight.w500,
                            ),
                            overflow: TextOverflow.ellipsis,
                            maxLines: 1,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Text(
                        item.loteId != null ? 'Lote: ${item.loteId}' : 'Sem lote',
                        style: TextStyle(
                          fontSize: 12,
                          color: colors['texto_secundario'],
                        ),
                      ),
                      const Text(' · '),
                      Expanded(
                        child: Text(
                          item.operador != null
                              ? 'Operador: ${item.operador}'
                              : 'Operador não informado',
                          style: TextStyle(
                            fontSize: 12,
                            color: colors['texto_secundario'],
                          ),
                          overflow: TextOverflow.ellipsis,
                          maxLines: 1,
                        ),
                      ),
                    ],
                  ),
                  if (item.observacoes != null &&
                      item.observacoes!.trim().isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: colors['fundo_alt'],
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        'Obs: ${item.observacoes}',
                        style: TextStyle(
                          fontSize: 12,
                          fontStyle: FontStyle.italic,
                          color: colors['texto_secundario'],
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
