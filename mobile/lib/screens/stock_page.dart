import 'package:flutter/material.dart';

import '../api_client.dart';
import '../app_colors.dart';
import '../models.dart';

const catLabels = <String, String>{
  'racao': 'Ração',
  'trato': 'Trato (volumoso)',
  'medicamento': 'Medicamento',
  'vacina': 'Vacina',
  'mineral': 'Mineral',
  'outro': 'Outro',
};

class StockPage extends StatefulWidget {
  const StockPage({
    super.key,
    required this.api,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final VoidCallback onUnauthorized;

  @override
  State<StockPage> createState() => _StockPageState();
}

class _StockPageState extends State<StockPage> {
  List<InsumoInventario>? _inventario;
  List<PrevisaoEstoqueItem>? _previsao;
  String? _inventarioError;
  String? _previsaoError;
  bool _loading = true;
  String? _selectedCategory;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    List<InsumoInventario>? inventario;
    List<PrevisaoEstoqueItem>? previsao;
    String? inventarioError;
    String? previsaoError;
    bool unauthorized = false;

    await Future.wait([
      () async {
        try {
          inventario = await widget.api.getEstoqueInventario();
        } on ApiException catch (error) {
          if (error.statusCode == 401) {
            unauthorized = true;
          } else {
            inventarioError = error.message;
          }
        } catch (_) {
          inventarioError =
              'Não foi possível carregar o inventário de estoque.';
        }
      }(),
      () async {
        try {
          previsao = await widget.api.getEstoquePrevisao();
        } on ApiException catch (error) {
          if (error.statusCode == 401) {
            unauthorized = true;
          } else {
            previsaoError = error.message;
          }
        } catch (_) {
          previsaoError =
              'Não foi possível carregar a previsão de estoque.';
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
      _previsao = previsao;
      _inventarioError = inventarioError;
      _previsaoError = previsaoError;
      _loading = false;
    });
  }

  Color _statusColor(BuildContext context, String status) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final colors = isDark ? AppColors.dark : AppColors.light;
    switch (status.toLowerCase()) {
      case 'critico':
        return colors['perigo']!;
      case 'baixo':
        return colors['atencao']!;
      case 'ok':
        return colors['sucesso']!;
      default:
        return colors['texto_secundario']!;
    }
  }

  String _statusLabel(String status) {
    switch (status.toLowerCase()) {
      case 'critico':
        return '🔴 Crítico';
      case 'baixo':
        return '🟡 Baixo';
      case 'ok':
        return '🟢 OK';
      default:
        return status;
    }
  }

  Color _urgenciaColor(BuildContext context, String urgencia) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final colors = isDark ? AppColors.dark : AppColors.light;
    switch (urgencia.toLowerCase()) {
      case 'critica':
        return colors['perigo']!;
      case 'atencao':
        return colors['atencao']!;
      case 'ok':
        return colors['sucesso']!;
      case 'sem_dados':
      default:
        return colors['texto_secundario']!;
    }
  }

  String _urgenciaLabel(String urgencia) {
    switch (urgencia.toLowerCase()) {
      case 'critica':
        return '🔴 Crítica';
      case 'atencao':
        return '🟡 Atenção';
      case 'ok':
        return '🟢 OK';
      case 'sem_dados':
        return '⚪ Sem dados';
      default:
        return urgencia;
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Estoque'),
          bottom: const TabBar(
            tabs: [
              Tab(
                key: ValueKey('tab-inventario'),
                text: '📋 Inventário',
              ),
              Tab(
                key: ValueKey('tab-previsao'),
                text: '📈 Previsão de Ruptura',
              ),
            ],
          ),
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : TabBarView(
                children: [
                  _buildInventarioTab(context),
                  _buildPrevisaoTab(context),
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

    final allItems = _inventario ?? [];
    final filteredItems = _selectedCategory == null
        ? allItems
        : allItems.where((i) => i.categoria == _selectedCategory).toList();

    return RefreshIndicator(
      key: const ValueKey('stock-inventory-refresh'),
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          // Filtro por categoria
          Card(
            margin: const EdgeInsets.only(bottom: 16),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String?>(
                  key: const ValueKey('stock-category-filter'),
                  isExpanded: true,
                  value: _selectedCategory,
                  hint: const Text('Todas as categorias'),
                  items: [
                    const DropdownMenuItem<String?>(
                      value: null,
                      child: Text('Todas as categorias'),
                    ),
                    ...catLabels.entries.map(
                      (e) => DropdownMenuItem<String?>(
                        value: e.key,
                        child: Text(e.value),
                      ),
                    ),
                  ],
                  onChanged: (val) {
                    setState(() => _selectedCategory = val);
                  },
                ),
              ),
            ),
          ),
          if (filteredItems.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 32),
              child: Center(
                child: Text('Nenhum insumo encontrado.'),
              ),
            )
          else
            ...filteredItems.map((item) {
              final statusColor = _statusColor(context, item.status);
              final statusLabel = _statusLabel(item.status);
              final categoriaFormatada =
                  catLabels[item.categoria] ?? item.categoria;

              return Card(
                key: ValueKey('inventory-item-${item.id}'),
                margin: const EdgeInsets.only(bottom: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(color: statusColor.withAlpha(120), width: 1.5),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              item.nome,
                              style: Theme.of(context)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: statusColor.withAlpha(30),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: statusColor, width: 1),
                            ),
                            child: Text(
                              statusLabel,
                              style: TextStyle(
                                color: statusColor,
                                fontWeight: FontWeight.bold,
                                fontSize: 12,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Categoria: $categoriaFormatada',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Theme.of(context)
                                  .textTheme
                                  .bodySmall
                                  ?.color
                                  ?.withAlpha(180),
                            ),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 12,
                        runSpacing: 4,
                        alignment: WrapAlignment.spaceBetween,
                        children: [
                          Text(
                            'Estoque: ${item.estoqueAtual.toStringAsFixed(1)} ${item.unidade}',
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                          Text(
                            'Mínimo: ${item.estoqueMinimo.toStringAsFixed(1)} ${item.unidade}',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Valor total: R\$ ${item.valorTotal.toStringAsFixed(2)}',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                      ),
                    ],
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }

  Widget _buildPrevisaoTab(BuildContext context) {
    if (_previsaoError != null && _previsao == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_previsaoError!, textAlign: TextAlign.center),
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

    final items = _previsao ?? [];

    return RefreshIndicator(
      key: const ValueKey('stock-forecast-refresh'),
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          if (items.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 32),
              child: Center(
                child: Text('Nenhuma previsão de ruptura no momento.'),
              ),
            )
          else
            ...items.map((item) {
              final urgenciaColor = _urgenciaColor(context, item.urgencia);
              final urgenciaLabel = _urgenciaLabel(item.urgencia);
              final isSemDados = item.urgencia == 'sem_dados';

              return Card(
                key: ValueKey('forecast-item-${item.insumoId}'),
                margin: const EdgeInsets.only(bottom: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side:
                      BorderSide(color: urgenciaColor.withAlpha(120), width: 1.5),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              item.nome,
                              style: Theme.of(context)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: urgenciaColor.withAlpha(30),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: urgenciaColor, width: 1),
                            ),
                            child: Text(
                              urgenciaLabel,
                              style: TextStyle(
                                color: urgenciaColor,
                                fontWeight: FontWeight.bold,
                                fontSize: 12,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      if (isSemDados)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            'Sem plano de trato ativo',
                            style:
                                Theme.of(context).textTheme.bodyMedium?.copyWith(
                                      fontStyle: FontStyle.italic,
                                      color: Theme.of(context)
                                          .textTheme
                                          .bodyMedium
                                          ?.color
                                          ?.withAlpha(180),
                                    ),
                          ),
                        )
                      else ...[
                        Wrap(
                          spacing: 12,
                          runSpacing: 4,
                          alignment: WrapAlignment.spaceBetween,
                          children: [
                            Text(
                              'Dias restantes: ${item.diasRestantes != null ? item.diasRestantes!.toStringAsFixed(0) : '—'}',
                              style: Theme.of(context).textTheme.bodyMedium,
                            ),
                            if (item.comprarAte != null)
                              Text(
                                'Comprar até: ${item.comprarAte}',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        if (item.dataRuptura != null)
                          Text(
                            'Data de ruptura: ${item.dataRuptura}',
                            style:
                                Theme.of(context).textTheme.bodySmall?.copyWith(
                                      color: urgenciaColor,
                                    ),
                          ),
                      ],
                    ],
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }
}
