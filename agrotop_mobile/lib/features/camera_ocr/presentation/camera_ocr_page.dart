import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../shared/widgets/custom_button.dart';

class CameraOcrPage extends StatefulWidget {
  const CameraOcrPage({super.key});

  @override
  State<CameraOcrPage> createState() => _CameraOcrPageState();
}

class _CameraOcrPageState extends State<CameraOcrPage> {
  bool _hasPhoto = false;
  bool _isUploading = false;
  double _uploadProgress = 0.0;
  String? _detectedEarring;

  void _simulatePhotoCapture() {
    setState(() {
      _hasPhoto = true;
      _detectedEarring = null;
    });
  }

  Future<void> _uploadAndProcessImage() async {
    setState(() {
      _isUploading = true;
      _uploadProgress = 0.1;
    });

    // Simulação do envio e processamento assíncrono via API FastAPI
    for (int i = 2; i <= 10; i++) {
      await Future.delayed(const Duration(milliseconds: 150));
      setState(() => _uploadProgress = i / 10.0);
    }

    if (mounted) {
      setState(() {
        _isUploading = false;
        _detectedEarring = 'BR-1002';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Leitura de Brinco / QR Code'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            // Área de Pré-visualização da Câmera
            Expanded(
              child: Card(
                clipBehavior: Clip.antiAlias,
                child: Container(
                  width: double.infinity,
                  color: Colors.black12,
                  child: _hasPhoto
                      ? Stack(
                          alignment: Alignment.center,
                          children: [
                            Container(
                              color: AppColors.primaryDark,
                              child: const Center(
                                child: Icon(
                                  Icons.pets_rounded,
                                  size: 100,
                                  color: Colors.white24,
                                ),
                              ),
                            ),
                            if (_isUploading)
                              Container(
                                color: Colors.black54,
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    const CircularProgressIndicator(color: AppColors.accent),
                                    const SizedBox(height: 16),
                                    Text(
                                      'Enviando imagem... ${(_uploadProgress * 100).toInt()}%',
                                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                                    ),
                                  ],
                                ),
                              ),
                          ],
                        )
                      : Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: const [
                            Icon(Icons.camera_alt_outlined, size: 64, color: AppColors.textSecondary),
                            SizedBox(height: 12),
                            Text(
                              'Toque no botão abaixo para capturar ou selecionar uma foto do brinco.',
                              textAlign: TextAlign.center,
                              style: TextStyle(color: AppColors.textSecondary),
                            ),
                          ],
                        ),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Painel de Resultados do OCR
            if (_detectedEarring != null) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.alertSuccess.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppColors.alertSuccess),
                ),
                child: Column(
                  children: [
                    const Text(
                      '✅ Brinco Identificado via OCR:',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _detectedEarring!,
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: AppColors.primary,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
            ],

            // Botões de Ação
            Row(
              children: [
                Expanded(
                  child: CustomButton(
                    label: _hasPhoto ? 'Nova Foto' : 'Abrir Câmera',
                    icon: Icons.camera_alt,
                    backgroundColor: Colors.blueGrey,
                    onPressed: _simulatePhotoCapture,
                  ),
                ),
                if (_hasPhoto) ...[
                  const SizedBox(width: 12),
                  Expanded(
                    child: CustomButton(
                      label: 'Processar OCR',
                      icon: Icons.search_rounded,
                      isLoading: _isUploading,
                      onPressed: _uploadAndProcessImage,
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}
