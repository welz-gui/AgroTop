import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../api_client.dart';
import '../app.dart';
import '../models.dart';
import '../offline_queue.dart';
import '../shallow_cache.dart';
import 'animal_photo_section.dart';
import 'alerts_page.dart';
import 'create_lote_page.dart';
import 'csv_import_page.dart';
import 'dashboard_resumo_page.dart';
import 'devices_page.dart';
import 'feeding_page.dart';
import 'medication_page.dart';
import 'movement_page.dart';
import 'offline_cache_banner.dart';
import 'perimeter_gps_page.dart';
import 'qr_scanner_page.dart';
import 'reports_page.dart';
import 'stock_page.dart';
import 'sync_report_dialog.dart';
import 'weighing_page.dart';

class AnimalsPage extends StatefulWidget {
  const AnimalsPage({
    super.key,
    required this.api,
    required this.themeMode,
    required this.onThemeChanged,
    required this.onUnauthorized,
    this.qrScannerBuilder,
    this.offlineQueue,
    this.shallowCache,
    this.gpsPositionProvider,
    this.gpsPermissionRequester,
    this.gpsPermissionChecker,
  });

  final ApiClient api;
  final ThemeMode themeMode;
  final ValueChanged<ThemeMode> onThemeChanged;
  final VoidCallback onUnauthorized;
  final QrScannerBuilder? qrScannerBuilder;
  final OfflineQueue? offlineQueue;
  final ShallowCache? shallowCache;
  final Future<PositionPoint> Function()? gpsPositionProvider;
  final Future<LocationPermission> Function()? gpsPermissionRequester;
  final Future<LocationPermission> Function()? gpsPermissionChecker;

  @override
  State<AnimalsPage> createState() => _AnimalsPageState();
}

class _AnimalsPageState extends State<AnimalsPage> with WidgetsBindingObserver {
  static const _pageSize = 50;

  final _animals = <AnimalSummary>[];
  late final OfflineQueue _offlineQueue;
  late final ShallowCache? _shallowCache;
  bool _loading = true;
  bool _loadingMore = false;
  bool _hasMore = true;
  String? _error;
  String _query = '';
  bool _selecting = false;
  final _selectedIds = <String>{};
  int? _pendingFeedings;
  int? _alertCount;
  int _pendingQueueCount = 0;
  String? _cachedTime;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _offlineQueue = widget.offlineQueue ?? OfflineQueue();
    _shallowCache = widget.shallowCache;
    _load(reset: true);
    _loadPendingFeedings();
    _loadAlertCount();
    _loadPendingQueueCount();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _syncQueue(manual: false);
    }
  }

  Future<void> _loadPendingQueueCount() async {
    try {
      final count = await _offlineQueue.countPending();
      if (mounted) {
        setState(() => _pendingQueueCount = count);
      }
    } catch (_) {}
  }

  Future<void> _syncQueue({required bool manual}) async {
    try {
      final report = await _offlineQueue.sync(widget.api);
      await _loadPendingQueueCount();
      if (report.sincronizados.isNotEmpty && mounted) {
        await _load(reset: true);
        _loadPendingFeedings();
      }
      if (manual && mounted) {
        showDialog<void>(
          context: context,
          builder: (_) => SyncReportDialog(report: report),
        );
      }
    } catch (_) {
      await _loadPendingQueueCount();
    }
  }

  Future<void> _loadPendingFeedings() async {
    try {
      final feedings = await widget.api.listPendingFeedings();
      if (mounted) {
        setState(
          () => _pendingFeedings = feedings
              .where((feeding) => !feeding.confirmadoNoPeriodo)
              .length,
        );
      }
    } catch (_) {
      // A lista de animais continua útil sem a contagem de trato.
    }
  }

  Future<void> _loadAlertCount() async {
    try {
      final alerts = await widget.api.getOperationalAlerts();
      if (mounted) setState(() => _alertCount = alerts.total);
    } catch (_) {
      // A lista de animais continua útil sem a contagem de alertas.
    }
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
      if (reset && _shallowCache != null) {
        await _shallowCache.saveAnimals(page);
      }
      setState(() {
        if (reset) _animals.clear();
        _animals.addAll(page);
        _hasMore = page.length == _pageSize;
        _error = null;
        _cachedTime = null;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        widget.onUnauthorized();
        return;
      }
      if (reset && _shallowCache != null) {
        final cached = _shallowCache.getAnimals();
        if (cached != null && cached.data.isNotEmpty) {
          setState(() {
            _animals.clear();
            _animals.addAll(cached.data);
            _hasMore = false;
            _cachedTime = cached.formattedTime;
            _error = null;
          });
          return;
        }
      }
      setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        if (reset && _shallowCache != null) {
          final cached = _shallowCache.getAnimals();
          if (cached != null && cached.data.isNotEmpty) {
            setState(() {
              _animals.clear();
              _animals.addAll(cached.data);
              _hasMore = false;
              _cachedTime = cached.formattedTime;
              _error = null;
            });
            return;
          }
        }
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

  void _startSelecting([String? animalId]) => setState(() {
    _selecting = true;
    if (animalId != null) _selectedIds.add(animalId);
  });

  void _stopSelecting() => setState(() {
    _selecting = false;
    _selectedIds.clear();
  });

  void _toggleSelection(String animalId) => setState(() {
    if (!_selectedIds.remove(animalId)) _selectedIds.add(animalId);
  });

  Future<void> _openMovement(List<String> animalIds) async {
    final moved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => MovementPage(
          api: widget.api,
          animalIds: animalIds,
          onUnauthorized: widget.onUnauthorized,
          offlineQueue: _offlineQueue,
          shallowCache: _shallowCache,
        ),
      ),
    );
    if (moved == true && mounted) {
      _stopSelecting();
      await _loadPendingQueueCount();
      await _load(reset: true);
    }
  }

  Future<void> _openQrScanner() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => QrScannerPage(
          api: widget.api,
          onUnauthorized: widget.onUnauthorized,
          scannerBuilder: widget.qrScannerBuilder,
        ),
      ),
    );
  }

  Future<void> _openFeeding() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) =>
            FeedingPage(api: widget.api, onUnauthorized: widget.onUnauthorized),
      ),
    );
    if (mounted) _loadPendingFeedings();
  }

  Future<void> _openAlerts() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) =>
            AlertsPage(api: widget.api, onUnauthorized: widget.onUnauthorized),
      ),
    );
    if (mounted) _loadAlertCount();
  }

  Future<void> _openDevices() => Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) =>
          DevicesPage(api: widget.api, onUnauthorized: widget.onUnauthorized),
    ),
  );

  Future<void> _openCreateLote() => Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) => CreateLotePage(
        api: widget.api,
        onUnauthorized: widget.onUnauthorized,
      ),
    ),
  );

  Future<void> _openDashboardResumo() => Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) => DashboardResumoPage(
        api: widget.api,
        onUnauthorized: widget.onUnauthorized,
      ),
    ),
  );

  Future<void> _openPerimeterGps() => Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) => PerimeterGpsPage(
        api: widget.api,
        onUnauthorized: widget.onUnauthorized,
        positionProvider: widget.gpsPositionProvider,
        permissionRequester: widget.gpsPermissionRequester,
        permissionChecker: widget.gpsPermissionChecker,
      ),
    ),
  );

  Future<void> _openCsvImport() => Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) =>
          CsvImportPage(api: widget.api, onUnauthorized: widget.onUnauthorized),
    ),
  );

  Future<void> _openStock() => Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) =>
          StockPage(api: widget.api, onUnauthorized: widget.onUnauthorized),
    ),
  );

  Future<void> _openReports() => Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) =>
          ReportsPage(api: widget.api, onUnauthorized: widget.onUnauthorized),
    ),
  );

  void _closeDrawerAnd(Future<void> Function() action) {
    Navigator.of(context).pop();
    action();
  }

  Widget? _drawerBadge(
    int? count, {
    required Key key,
    required String semanticsSuffix,
    required bool useErrorColor,
  }) {
    if (count == null || count <= 0) return null;
    final colors = Theme.of(context).colorScheme;
    return Semantics(
      label: '$count $semanticsSuffix',
      child: SizedBox(
        width: 24,
        height: 24,
        child: Container(
          key: key,
          constraints: const BoxConstraints(minWidth: 17, minHeight: 17),
          padding: const EdgeInsets.symmetric(horizontal: 4),
          decoration: BoxDecoration(
            color: useErrorColor ? colors.error : colors.primary,
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: Text(
            '$count',
            style: TextStyle(
              color: useErrorColor ? colors.onError : colors.onPrimary,
              fontSize: 11,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildDrawer() => Drawer(
    child: SafeArea(
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          const DrawerHeader(
            child: Align(
              alignment: Alignment.bottomLeft,
              child: Text(
                '🐄 AgroTop',
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.w600),
              ),
            ),
          ),
          ListTile(
            key: const ValueKey('open-dashboard-resumo'),
            leading: const Icon(Icons.dashboard_outlined),
            title: const Text('Resumo'),
            onTap: () => _closeDrawerAnd(_openDashboardResumo),
          ),
          ListTile(
            key: const ValueKey('open-perimeter-gps'),
            leading: const Icon(Icons.location_on_outlined),
            title: const Text('Demarcar perímetro'),
            onTap: () => _closeDrawerAnd(_openPerimeterGps),
          ),
          ListTile(
            key: const ValueKey('open-create-lote'),
            leading: const Icon(Icons.add_location_alt_outlined),
            title: const Text('Novo lote'),
            onTap: () => _closeDrawerAnd(_openCreateLote),
          ),
          ListTile(
            key: const ValueKey('open-devices'),
            leading: const Icon(Icons.sell_outlined),
            title: const Text('Brincos e dispositivos'),
            onTap: () => _closeDrawerAnd(_openDevices),
          ),
          ListTile(
            key: const ValueKey('open-stock'),
            leading: const Icon(Icons.inventory_2_outlined),
            title: const Text('Estoque'),
            onTap: () => _closeDrawerAnd(_openStock),
          ),
          ListTile(
            key: const ValueKey('open-reports'),
            leading: const Icon(Icons.description_outlined),
            title: const Text('Relatórios'),
            onTap: () => _closeDrawerAnd(_openReports),
          ),
          ListTile(
            key: const ValueKey('open-alerts'),
            leading: const Icon(Icons.notifications_outlined),
            title: const Text('Alertas operacionais'),
            trailing: _drawerBadge(
              _alertCount,
              key: const ValueKey('alerts-badge'),
              semanticsSuffix: 'alertas operacionais',
              useErrorColor: true,
            ),
            onTap: () => _closeDrawerAnd(_openAlerts),
          ),
          ListTile(
            key: const ValueKey('open-feeding'),
            leading: const Icon(Icons.grass_outlined),
            title: const Text('Trato do dia'),
            trailing: _drawerBadge(
              _pendingFeedings,
              key: const ValueKey('pending-feeding-badge'),
              semanticsSuffix: 'pendências de trato',
              useErrorColor: true,
            ),
            onTap: () => _closeDrawerAnd(_openFeeding),
          ),
          ListTile(
            key: const ValueKey('open-csv-import'),
            leading: const Icon(Icons.upload_file_outlined),
            title: const Text('Importar pesagens'),
            onTap: () => _closeDrawerAnd(_openCsvImport),
          ),
          ListTile(
            key: const ValueKey('sync-queue-button'),
            title: const Text('Fila offline'),
            leading: Icon(
              _pendingQueueCount > 0
                  ? Icons.cloud_upload_outlined
                  : Icons.cloud_outlined,
            ),
            trailing: _drawerBadge(
              _pendingQueueCount,
              key: const ValueKey('pending-queue-badge'),
              semanticsSuffix: 'pendências na fila offline',
              useErrorColor: false,
            ),
            onTap: () => _closeDrawerAnd(() => _syncQueue(manual: true)),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('Sair'),
            onTap: () => _closeDrawerAnd(_logout),
          ),
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Animais ativos'),
      actions: [
        ThemePicker(value: widget.themeMode, onChanged: widget.onThemeChanged),
      ],
    ),
    drawer: _buildDrawer(),
    body: _buildBody(),
    bottomNavigationBar: _selecting
        ? SafeArea(
            minimum: const EdgeInsets.all(16),
            child: FilledButton.icon(
              key: const ValueKey('move-selected-animals'),
              onPressed: _selectedIds.isEmpty
                  ? null
                  : () => _openMovement(_selectedIds.toList(growable: false)),
              icon: const Icon(Icons.swap_horiz),
              label: Text('Mover ${_selectedIds.length} selecionado(s)'),
            ),
          )
        : null,
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
          if (_cachedTime != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: OfflineCacheBanner(formattedTime: _cachedTime!),
            ),
          TextField(
            key: const ValueKey('animal-search'),
            decoration: InputDecoration(
              labelText: 'Buscar por ID ou brinco',
              prefixIcon: const Icon(Icons.search),
              suffixIcon: IconButton(
                key: const ValueKey('scan-qr-button'),
                tooltip: 'Ler QR do brinco',
                icon: const Icon(Icons.qr_code_scanner),
                onPressed: _openQrScanner,
              ),
            ),
            onChanged: (value) => setState(() => _query = value),
          ),
          const SizedBox(height: 12),
          if (_selecting)
            Card(
              child: ListTile(
                leading: const Icon(Icons.checklist),
                title: Text('${_selectedIds.length} selecionado(s)'),
                subtitle: const Text(
                  'Toque nos animais para marcar ou desmarcar.',
                ),
                trailing: TextButton(
                  onPressed: _stopSelecting,
                  child: const Text('Cancelar'),
                ),
              ),
            )
          else
            OutlinedButton.icon(
              key: const ValueKey('start-animal-selection'),
              onPressed: _startSelecting,
              icon: const Icon(Icons.checklist),
              label: const Text('Selecionar vários animais'),
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
                  trailing: Icon(
                    _selecting
                        ? (_selectedIds.contains(animal.id)
                              ? Icons.check_box
                              : Icons.check_box_outline_blank)
                        : Icons.chevron_right,
                  ),
                  onLongPress: () => _startSelecting(animal.id),
                  onTap: _selecting
                      ? () => _toggleSelection(animal.id)
                      : () async {
                          await Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => AnimalDetailPage(
                                api: widget.api,
                                id: animal.id,
                                onUnauthorized: widget.onUnauthorized,
                                onMovementCompleted: () => _load(reset: true),
                                offlineQueue: _offlineQueue,
                                shallowCache: _shallowCache,
                              ),
                            ),
                          );
                          if (mounted) {
                            await _loadPendingQueueCount();
                          }
                        },
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
    required this.onMovementCompleted,
    this.offlineQueue,
    this.shallowCache,
  });

  final ApiClient api;
  final String id;
  final VoidCallback onUnauthorized;
  final VoidCallback onMovementCompleted;
  final OfflineQueue? offlineQueue;
  final ShallowCache? shallowCache;

  @override
  State<AnimalDetailPage> createState() => _AnimalDetailPageState();
}

class _AnimalDetailPageState extends State<AnimalDetailPage> {
  late Future<AnimalDetail> _detail;
  late Future<AnimalMedications> _medications;
  late final OfflineQueue _offlineQueue;
  late final ShallowCache? _shallowCache;
  String? _detailCachedTime;

  @override
  void initState() {
    super.initState();
    _offlineQueue = widget.offlineQueue ?? OfflineQueue();
    _shallowCache = widget.shallowCache;
    _detail = _loadDetail();
    _medications = _loadMedications();
  }

  Future<AnimalDetail> _loadDetail() async {
    try {
      final detail = await widget.api.getAnimal(widget.id);
      if (_shallowCache != null) {
        await _shallowCache.saveAnimalDetail(detail);
      }
      return detail;
    } catch (_) {
      if (_shallowCache != null) {
        final cached = _shallowCache.getAnimalDetail(widget.id);
        if (cached != null) {
          if (mounted) {
            setState(() => _detailCachedTime = cached.formattedTime);
          }
          return cached.data;
        }
      }
      rethrow;
    }
  }

  // Não capture erros aqui para virar "sem carência": um 200 com
  // carencia_ate nulo é a única fonte legítima de "liberado". Se a consulta
  // falhar (rede, servidor), o FutureBuilder abaixo mostra erro com opção de
  // tentar de novo — nunca a ficha afirmando liberação sem ter confirmado.
  Future<AnimalMedications> _loadMedications() =>
      widget.api.getAnimalMedications(widget.id);

  void _reload() => setState(() {
    _detail = _loadDetail();
    _medications = _loadMedications();
  });

  String _metric(double? value, String suffix, {int decimals = 1}) =>
      value == null
      ? 'Sem dados'
      : '${value.toStringAsFixed(decimals)} $suffix';

  String _value(Object? value) => value?.toString() ?? 'Não informado';

  Future<void> _openWeighing() async {
    final result = await Navigator.of(context).push<dynamic>(
      MaterialPageRoute(
        builder: (_) => WeighingPage(
          api: widget.api,
          animalId: widget.id,
          onUnauthorized: widget.onUnauthorized,
          offlineQueue: _offlineQueue,
        ),
      ),
    );
    if (result == null || !mounted) return;
    _reload();
    if (result is WeighingResult) {
      final messenger = ScaffoldMessenger.of(context);
      messenger.hideCurrentSnackBar();
      messenger.showSnackBar(SnackBar(content: Text(result.message)));
    }
  }

  Future<void> _openMedication() async {
    final result = await Navigator.of(context).push<dynamic>(
      MaterialPageRoute(
        builder: (_) => MedicationPage(
          api: widget.api,
          animalId: widget.id,
          onUnauthorized: widget.onUnauthorized,
          offlineQueue: _offlineQueue,
        ),
      ),
    );
    if (result == null || !mounted) return;
    _reload();
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      const SnackBar(content: Text('Medicamento registrado com sucesso.')),
    );
  }

  Future<void> _openMovement() async {
    final moved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => MovementPage(
          api: widget.api,
          animalIds: [widget.id],
          onUnauthorized: widget.onUnauthorized,
          offlineQueue: _offlineQueue,
          shallowCache: _shallowCache,
        ),
      ),
    );
    if (moved != true || !mounted) return;
    _reload();
    widget.onMovementCompleted();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text('Ficha ${widget.id}'),
      actions: [
        IconButton(
          onPressed: _reload,
          tooltip: 'Recarregar',
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: FutureBuilder<List<dynamic>>(
      future: Future.wait([_detail, _medications]),
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          final error = snapshot.error;
          final message = error is ApiException
              ? error.message
              : 'Não foi possível carregar os dados do animal.';
          return ErrorState(message: message, onRetry: _reload);
        }
        final animal = snapshot.data![0] as AnimalDetail;
        final medications = snapshot.data![1] as AnimalMedications;
        final sex = switch (animal.sex) {
          'M' => 'Macho',
          'F' => 'Fêmea',
          _ => 'Não informado',
        };
        final inWithdrawal = medications.carenciaAte != null;

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_detailCachedTime != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: OfflineCacheBanner(formattedTime: _detailCachedTime!),
              ),
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

            Card(
              key: const ValueKey('carencia-status-card'),
              color: inWithdrawal
                  ? Theme.of(context).colorScheme.errorContainer
                  : null,
              child: ListTile(
                leading: Icon(
                  inWithdrawal
                      ? Icons.warning_amber_rounded
                      : Icons.check_circle_outline,
                  color: inWithdrawal
                      ? Theme.of(context).colorScheme.error
                      : Theme.of(context).colorScheme.primary,
                  size: 32,
                ),
                title: Text(
                  inWithdrawal
                      ? 'Em carência até ${medications.carenciaAte}'
                      : 'Sem restrição de carência',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: inWithdrawal
                        ? Theme.of(context).colorScheme.onErrorContainer
                        : null,
                  ),
                ),
                subtitle: Text(
                  inWithdrawal
                      ? 'Abate e comercialização restritos durante este período.'
                      : 'Animal liberado para comercialização/abate.',
                  style: TextStyle(
                    color: inWithdrawal
                        ? Theme.of(context).colorScheme.onErrorContainer
                        : null,
                  ),
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
            const SizedBox(height: 12),

            // Card de Histórico de Sanidade
            Card(
              key: const ValueKey('medications-history-card'),
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
                        'Histórico de aplicações (${medications.aplicacoes.length})',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                    if (medications.aplicacoes.isEmpty)
                      const ListTile(
                        leading: Icon(Icons.info_outline),
                        title: Text('Nenhuma aplicação registrada.'),
                      )
                    else
                      for (final app in medications.aplicacoes)
                        ListTile(
                          leading: const Icon(Icons.medication_outlined),
                          title: Text(
                            '${app.medicamento} · ${app.dose} ${app.unidade}',
                          ),
                          subtitle: Text(
                            '${app.data} · Via ${app.via}'
                            '${app.carenciaDias > 0 ? ' · Carência: ${app.carenciaDias}d' : ''}',
                          ),
                        ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            AnimalPhotoSection(
              api: widget.api,
              animalId: widget.id,
              onUnauthorized: widget.onUnauthorized,
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              key: const ValueKey('open-medication'),
              onPressed: _openMedication,
              icon: const Icon(Icons.medication_outlined),
              label: const Text('Registrar medicamento'),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              key: const ValueKey('open-weighing'),
              onPressed: _openWeighing,
              icon: const Icon(Icons.monitor_weight_outlined),
              label: const Text('Registrar pesagem'),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              key: const ValueKey('open-movement'),
              onPressed: _openMovement,
              icon: const Icon(Icons.swap_horiz),
              label: const Text('Mover de piquete'),
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
