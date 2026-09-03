import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../api_client.dart';
import '../models.dart';

enum GpsPermissionStatus {
  granted,
  denied,
  deniedForever,
}

class PerimeterGpsPage extends StatefulWidget {
  const PerimeterGpsPage({
    super.key,
    required this.api,
    required this.onUnauthorized,
    this.positionProvider,
    this.permissionRequester,
    this.permissionChecker,
    this.initialLoteId,
  });

  final ApiClient api;
  final VoidCallback onUnauthorized;
  final Future<PositionPoint> Function()? positionProvider;
  final Future<LocationPermission> Function()? permissionRequester;
  final Future<LocationPermission> Function()? permissionChecker;
  final String? initialLoteId;

  @override
  State<PerimeterGpsPage> createState() => _PerimeterGpsPageState();
}

class _PerimeterGpsPageState extends State<PerimeterGpsPage> {
  GpsPermissionStatus _permissionStatus = GpsPermissionStatus.denied;
  bool _loadingPermission = true;
  bool _loadingLotes = true;
  bool _saving = false;
  bool _readingPosition = false;

  List<LoteSummary> _lotes = [];
  String? _selectedLoteId;
  final List<PositionPoint> _pontos = [];
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _selectedLoteId = widget.initialLoteId;
    _checkPermission();
    _loadLotes();
  }

  Future<PositionPoint> _getPosition() async {
    if (widget.positionProvider != null) {
      return widget.positionProvider!();
    }
    final pos = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
      ),
    );
    return PositionPoint(latitude: pos.latitude, longitude: pos.longitude);
  }

  Future<void> _checkPermission() async {
    setState(() => _loadingPermission = true);
    LocationPermission permission;
    if (widget.permissionChecker != null) {
      permission = await widget.permissionChecker!();
    } else {
      permission = await Geolocator.checkPermission();
    }

    if (permission == LocationPermission.denied) {
      if (widget.permissionRequester != null) {
        permission = await widget.permissionRequester!();
      } else {
        permission = await Geolocator.requestPermission();
      }
    }

    _applyPermission(permission);
  }

  Future<void> _requestPermissionAgain() async {
    setState(() => _loadingPermission = true);
    LocationPermission permission;
    if (widget.permissionRequester != null) {
      permission = await widget.permissionRequester!();
    } else {
      permission = await Geolocator.requestPermission();
    }
    _applyPermission(permission);
  }

  void _applyPermission(LocationPermission permission) {
    if (!mounted) return;
    setState(() {
      _loadingPermission = false;
      if (permission == LocationPermission.always ||
          permission == LocationPermission.whileInUse) {
        _permissionStatus = GpsPermissionStatus.granted;
      } else if (permission == LocationPermission.deniedForever) {
        _permissionStatus = GpsPermissionStatus.deniedForever;
      } else {
        _permissionStatus = GpsPermissionStatus.denied;
      }
    });
  }

  Future<void> _loadLotes() async {
    setState(() => _loadingLotes = true);
    try {
      final lotes = await widget.api.listLotes();
      if (!mounted) return;
      setState(() {
        _lotes = lotes;
        if (_selectedLoteId == null && lotes.isNotEmpty) {
          _selectedLoteId = lotes.first.id;
        }
        _loadingLotes = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _loadingLotes = false);
      if (e.statusCode == 401) {
        widget.onUnauthorized();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message)),
        );
      }
    } catch (_) {
      if (!mounted) return;
      setState(() => _loadingLotes = false);
    }
  }

  Future<void> _markVertex() async {
    setState(() {
      _readingPosition = true;
      _errorMessage = null;
    });
    try {
      final point = await _getPosition();
      if (!mounted) return;
      setState(() {
        _pontos.add(point);
        _readingPosition = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _readingPosition = false;
        _errorMessage = 'Não foi possível ler a posição GPS: ';
      });
    }
  }

  void _undoVertex() {
    if (_pontos.isNotEmpty) {
      setState(() {
        _pontos.removeLast();
        _errorMessage = null;
      });
    }
  }

  void _resetVertices() {
    setState(() {
      _pontos.clear();
      _errorMessage = null;
    });
  }

  Future<void> _savePerimeter() async {
    if (_selectedLoteId == null || _pontos.length < 3 || _saving) return;
    setState(() {
      _saving = true;
      _errorMessage = null;
    });

    try {
      // Pontos no formato [longitude, latitude] exigido pela API
      final pontosList = _pontos
          .map((p) => [p.longitude, p.latitude])
          .toList(growable: false);

      final result = await widget.api.savePerimetro(
        _selectedLoteId!,
        pontos: pontosList,
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Perímetro salvo com sucesso! Área calculada: ${result.areaHa} ha.',
          ),
        ),
      );
      Navigator.of(context).pop(result);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _errorMessage = e.message;
      });
      if (e.statusCode == 401) {
        widget.onUnauthorized();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _errorMessage = 'Falha ao salvar o perímetro: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Demarcar perímetro por GPS'),
      ),
      body: _loadingPermission
          ? const Center(child: CircularProgressIndicator())
          : _permissionStatus != GpsPermissionStatus.granted
              ? _buildPermissionWarning(colorScheme)
              : _buildDemarcationView(colorScheme),
    );
  }

  Widget _buildPermissionWarning(ColorScheme colorScheme) {
    final isForever = _permissionStatus == GpsPermissionStatus.deniedForever;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Card(
          elevation: 0,
          color: colorScheme.errorContainer,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.location_off_outlined,
                  size: 48,
                  color: colorScheme.onErrorContainer,
                ),
                const SizedBox(height: 16),
                Text(
                  'Permissão de localização',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: colorScheme.onErrorContainer,
                        fontWeight: FontWeight.bold,
                      ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 12),
                Text(
                  isForever
                      ? 'Permissão de localização foi negada permanentemente. É necessário liberar o acesso à localização manualmente nas configurações do dispositivo para demarcar piquetes.'
                      : 'Permissão de localização é necessária para coletar as coordenadas dos vértices do piquete no campo.',
                  key: const ValueKey('permission-denied-message'),
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: colorScheme.onErrorContainer,
                      ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 20),
                if (!isForever)
                  FilledButton.icon(
                    key: const ValueKey('request-permission-button'),
                    onPressed: _requestPermissionAgain,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Pedir permissão novamente'),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildDemarcationView(ColorScheme colorScheme) {
    final canSave = _selectedLoteId != null && _pontos.length >= 3 && !_saving;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
        if (_loadingLotes)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: LinearProgressIndicator(),
          )
        else
          DropdownButtonFormField<String>(
            key: const ValueKey('lote-select'),
            isExpanded: true,
            initialValue: _selectedLoteId,
            decoration: const InputDecoration(
              labelText: 'Piquete / Lote',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.fence_outlined),
            ),
            items: _lotes.map((lote) {
              return DropdownMenuItem(
                value: lote.id,
                child: Text('${lote.id} - ${lote.nome}'),
              );
            }).toList(),
            onChanged: _saving
                ? null
                : (value) {
                    setState(() => _selectedLoteId = value);
                  },
          ),
        const SizedBox(height: 16),
        if (_errorMessage != null) ...[
          Card(
            key: const ValueKey('perimeter-error-message'),
            color: colorScheme.errorContainer,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Icon(Icons.error_outline, color: colorScheme.error),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _errorMessage!,
                      style: TextStyle(color: colorScheme.onErrorContainer),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
        ],
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Vértices marcados',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    Badge(
                      label: Text(
                        '${_pontos.length}',
                        key: const ValueKey('points-count'),
                      ),
                      backgroundColor: _pontos.length >= 3
                          ? colorScheme.primary
                          : colorScheme.outline,
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (_pontos.isEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 24),
                    child: Center(
                      child: Text(
                        'Nenhum ponto marcado ainda.\nCaminhe até cada canto do piquete e toque em "Marcar vértice".',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: colorScheme.outline,
                            ),
                      ),
                    ),
                  )
                else ...[
                  for (int index = 0; index < _pontos.length; index++) ...[
                    if (index > 0) const Divider(height: 1),
                    ListTile(
                      dense: true,
                      leading: CircleAvatar(
                        radius: 12,
                        child: Text(
                          '${index + 1}',
                          style: const TextStyle(fontSize: 11),
                        ),
                      ),
                      title: Text(
                        'Lat: ${_pontos[index].latitude.toStringAsFixed(6)}, Lon: ${_pontos[index].longitude.toStringAsFixed(6)}',
                        style: const TextStyle(fontFamily: 'monospace'),
                      ),
                    ),
                  ],
                  if (_pontos.length >= 3) ...[
                    const SizedBox(height: 12),
                    Text(
                      'Pré-visualização do polígono:',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      key: const ValueKey('polygon-preview'),
                      height: 140,
                      decoration: BoxDecoration(
                        color: colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: colorScheme.outlineVariant),
                      ),
                      child: CustomPaint(
                        painter: PolygonPreviewPainter(
                          points: _pontos,
                          color: colorScheme.primary,
                          fillColor: colorScheme.primary.withValues(alpha: 0.2),
                        ),
                      ),
                    ),
                  ],
                ],
                const SizedBox(height: 16),
                FilledButton.icon(
                  key: const ValueKey('mark-point-button'),
                  onPressed: _readingPosition || _saving ? null : _markVertex,
                  icon: _readingPosition
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.add_location_alt),
                  label: Text(_readingPosition
                      ? 'Lendo GPS...'
                      : '📍 Marcar vértice aqui'),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        key: const ValueKey('undo-point-button'),
                        onPressed: _pontos.isNotEmpty && !_saving
                            ? _undoVertex
                            : null,
                        icon: const Icon(Icons.undo),
                        label: const Text('Desfazer'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton.icon(
                        key: const ValueKey('reset-points-button'),
                        onPressed: _pontos.isNotEmpty && !_saving
                            ? _resetVertices
                            : null,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Recomeçar'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),
        FilledButton.tonalIcon(
          key: const ValueKey('save-perimeter-button'),
          onPressed: canSave ? _savePerimeter : null,
          icon: _saving
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.save_outlined),
          label: Text(
            _pontos.length < 3
                ? 'Marque pelo menos 3 vértices (${_pontos.length}/3)'
                : 'Salvar perímetro',
          ),
        ),
      ],
    ),
  );
  }
}

class PolygonPreviewPainter extends CustomPainter {
  PolygonPreviewPainter({
    required this.points,
    required this.color,
    required this.fillColor,
  });

  final List<PositionPoint> points;
  final Color color;
  final Color fillColor;

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length < 3) return;

    double minLat = points.first.latitude;
    double maxLat = points.first.latitude;
    double minLon = points.first.longitude;
    double maxLon = points.first.longitude;

    for (final p in points) {
      if (p.latitude < minLat) minLat = p.latitude;
      if (p.latitude > maxLat) maxLat = p.latitude;
      if (p.longitude < minLon) minLon = p.longitude;
      if (p.longitude > maxLon) maxLon = p.longitude;
    }

    final latSpan = maxLat - minLat;
    final lonSpan = maxLon - minLon;
    final maxSpan = latSpan > lonSpan
        ? (latSpan == 0 ? 1.0 : latSpan)
        : (lonSpan == 0 ? 1.0 : lonSpan);

    const padding = 16.0;
    final drawWidth = size.width - 2 * padding;
    final drawHeight = size.height - 2 * padding;

    Offset toOffset(PositionPoint p) {
      final normX = (p.longitude - minLon) / maxSpan;
      final normY = 1.0 - ((p.latitude - minLat) / maxSpan);
      return Offset(
        padding + normX * drawWidth,
        padding + normY * drawHeight,
      );
    }

    final path = Path();
    final firstOffset = toOffset(points.first);
    path.moveTo(firstOffset.dx, firstOffset.dy);

    for (int i = 1; i < points.length; i++) {
      final off = toOffset(points[i]);
      path.lineTo(off.dx, off.dy);
    }
    path.close();

    final fillPaint = Paint()
      ..color = fillColor
      ..style = PaintingStyle.fill;
    canvas.drawPath(path, fillPaint);

    final strokePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;
    canvas.drawPath(path, strokePaint);

    final dotPaint = Paint()
      ..color = color
      ..style = PaintingStyle.fill;

    for (final p in points) {
      canvas.drawCircle(toOffset(p), 4.0, dotPaint);
    }
  }

  @override
  bool shouldRepaint(covariant PolygonPreviewPainter oldDelegate) =>
      oldDelegate.points != points || oldDelegate.color != color;
}
