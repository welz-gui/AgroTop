import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../api_client.dart';
import '../models.dart';
import 'animals_page.dart';

typedef QrScannerBuilder = Widget Function(
  BuildContext context, {
  required ValueChanged<String> onScanned,
  required VoidCallback onError,
});

class QrScannerPage extends StatefulWidget {
  const QrScannerPage({
    super.key,
    required this.api,
    required this.onUnauthorized,
    this.onAnimalFound,
    this.scannerBuilder,
  });

  final ApiClient api;
  final VoidCallback onUnauthorized;
  final ValueChanged<AnimalDetail>? onAnimalFound;
  final QrScannerBuilder? scannerBuilder;

  @override
  State<QrScannerPage> createState() => _QrScannerPageState();
}

class _QrScannerPageState extends State<QrScannerPage> {
  MobileScannerController? _controller;
  bool _isProcessing = false;
  String? _errorMessage;
  String? _lastScannedCode;
  bool _isNotFound = false;

  @override
  void initState() {
    super.initState();
    if (widget.scannerBuilder == null) {
      _controller = MobileScannerController(
        detectionSpeed: DetectionSpeed.normal,
        facing: CameraFacing.back,
      );
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _handleScanned(String rawCode) async {
    final code = rawCode.trim();
    if (code.isEmpty) {
      if (mounted) {
        setState(() {
          _errorMessage =
              'QR Code ilegível. Reposicione o brinco e tente novamente.';
          _isNotFound = false;
          _isProcessing = false;
        });
      }
      return;
    }
    if (_isProcessing) return;

    setState(() {
      _isProcessing = true;
      _errorMessage = null;
      _lastScannedCode = code;
      _isNotFound = false;
    });

    try {
      final animal = await widget.api.getAnimal(code);
      if (!mounted) return;

      widget.onAnimalFound?.call(animal);

      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => AnimalDetailPage(
            api: widget.api,
            id: animal.id,
            onUnauthorized: widget.onUnauthorized,
            onMovementCompleted: () {},
          ),
        ),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        widget.onUnauthorized();
        return;
      }
      setState(() {
        _isProcessing = false;
        if (error.statusCode == 404) {
          _isNotFound = true;
          _errorMessage = 'Animal "$code" não encontrado.';
        } else {
          _isNotFound = false;
          _errorMessage = 'Erro ao consultar animal: ${error.message}';
        }
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isProcessing = false;
        _isNotFound = false;
        _errorMessage =
            'Erro de conexão ao consultar animal "$code". Tente novamente.';
      });
    }
  }

  void _retryScanning() {
    setState(() {
      _errorMessage = null;
      _isProcessing = false;
      _isNotFound = false;
    });
  }

  Widget _buildScanner(BuildContext context) {
    if (widget.scannerBuilder != null) {
      return widget.scannerBuilder!(
        context,
        onScanned: (code) => _handleScanned(code),
        onError: () {
          if (mounted) {
            setState(() {
              _errorMessage =
                  'Não foi possível ler o QR Code. Reposicione e tente novamente.';
              _isProcessing = false;
            });
          }
        },
      );
    }

    return MobileScanner(
      controller: _controller!,
      onDetect: (capture) {
        if (_isProcessing || _errorMessage != null) return;
        final barcodes = capture.barcodes;
        for (final barcode in barcodes) {
          final value = barcode.rawValue;
          if (value != null && value.trim().isNotEmpty) {
            _handleScanned(value);
            break;
          }
        }
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Ler QR do brinco'),
      ),
      body: Stack(
        children: [
          Positioned.fill(
            child: _buildScanner(context),
          ),
          if (!_isProcessing && _errorMessage == null)
            Positioned(
              top: 24,
              left: 24,
              right: 24,
              child: Card(
                color: theme.colorScheme.surface.withValues(alpha: 0.9),
                child: const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  child: Row(
                    children: [
                      Icon(Icons.qr_code_scanner),
                      SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'Aponte a câmera para o QR Code do brinco.',
                          style: TextStyle(fontSize: 14),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          if (_isProcessing)
            Container(
              color: Colors.black54,
              child: const Center(
                child: Card(
                  child: Padding(
                    padding: EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        CircularProgressIndicator(),
                        SizedBox(height: 16),
                        Text(
                          'Consultando animal na API…',
                          style: TextStyle(fontWeight: FontWeight.w500),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          if (_errorMessage != null)
            Container(
              color: Colors.black54,
              padding: const EdgeInsets.all(24),
              child: Center(
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          _isNotFound
                              ? Icons.search_off
                              : Icons.warning_amber_rounded,
                          size: 48,
                          color: _isNotFound
                              ? theme.colorScheme.primary
                              : theme.colorScheme.error,
                        ),
                        const SizedBox(height: 12),
                        Text(
                          _errorMessage!,
                          textAlign: TextAlign.center,
                          style: theme.textTheme.bodyLarge,
                        ),
                        const SizedBox(height: 20),
                        Wrap(
                          spacing: 12,
                          runSpacing: 8,
                          alignment: WrapAlignment.center,
                          children: [
                            FilledButton.icon(
                              key: const ValueKey('qr-retry-button'),
                              onPressed: _retryScanning,
                              icon: const Icon(Icons.refresh),
                              label: const Text('Tentar novamente'),
                            ),
                            if (_lastScannedCode != null && !_isNotFound)
                              OutlinedButton.icon(
                                key: const ValueKey('qr-recheck-button'),
                                onPressed: () =>
                                    _handleScanned(_lastScannedCode!),
                                icon: const Icon(Icons.sync),
                                label: const Text('Repetir consulta'),
                              ),
                            OutlinedButton.icon(
                              key: const ValueKey('qr-manual-search-button'),
                              onPressed: () => Navigator.of(context).pop(),
                              icon: const Icon(Icons.keyboard),
                              label: const Text('Buscar manualmente'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
