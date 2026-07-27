import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../shared/widgets/custom_button.dart';
import '../../../shared/widgets/custom_text_field.dart';

class WeighingFormPage extends StatefulWidget {
  final String? initialAnimalId;

  const WeighingFormPage({super.key, this.initialAnimalId});

  @override
  State<WeighingFormPage> createState() => _WeighingFormPageState();
}

class _WeighingFormPageState extends State<WeighingFormPage> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _animalIdController;
  final _weightController = TextEditingController();
  final _notesController = TextEditingController();
  
  double? _previousWeight = 380.0; // Exemplo de peso anterior retornado
  double? _calculatedGmd;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _animalIdController = TextEditingController(text: widget.initialAnimalId ?? '');
  }

  void _calculateGmd(String val) {
    final weight = double.tryParse(val.replaceAll(',', '.'));
    if (weight != null && _previousWeight != null) {
      final diff = weight - _previousWeight!;
      // Assume 30 dias desde a última pesagem para estimativa instantânea
      setState(() {
        _calculatedGmd = double.parse((diff / 30.0).toStringAsFixed(3));
      });
    }
  }

  Future<void> _saveWeighing() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);

    await Future.delayed(const Duration(milliseconds: 600));

    if (mounted) {
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Pesagem do brinco ${_animalIdController.text} salva com sucesso!'),
          backgroundColor: AppColors.alertSuccess,
        ),
      );
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Registrar Pesagem (Curral)'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CustomTextField(
                    label: 'Brinco / Identificador do Animal',
                    hint: 'Ex: BR-1001',
                    controller: _animalIdController,
                    prefixIcon: Icons.qr_code_scanner,
                    validator: (val) => val == null || val.isEmpty ? 'Informe o brinco' : null,
                  ),
                  const SizedBox(height: 16),

                  CustomTextField(
                    label: 'Novo Peso Registrado (kg)',
                    hint: 'Ex: 420.5',
                    controller: _weightController,
                    keyboardType: TextInputType.number,
                    prefixIcon: Icons.scale,
                    inputFormatters: const [],
                    validator: (val) => val == null || val.isEmpty ? 'Informe o peso' : null,
                    suffixIcon: const Padding(
                      padding: EdgeInsets.all(12.0),
                      child: Text('kg', style: TextStyle(fontWeight: FontWeight.bold)),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Card de Cálculo de GMD Instantâneo
                  if (_weightController.text.isNotEmpty && _calculatedGmd != null) ...[
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: AppColors.primary.withOpacity(0.08),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppColors.primary.withOpacity(0.2)),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'GMD Calculado (30d):',
                            style: TextStyle(fontWeight: FontWeight.w600),
                          ),
                          Text(
                            '+${_calculatedGmd} kg/dia',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: _calculatedGmd! >= 0.8 ? AppColors.alertSuccess : AppColors.alertWarning,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],

                  CustomTextField(
                    label: 'Observações de Campo (Opcional)',
                    hint: 'Ex: Animal calmo, sem sinais clínicos',
                    controller: _notesController,
                    prefixIcon: Icons.notes,
                  ),
                  const SizedBox(height: 28),

                  CustomButton(
                    label: 'Salvar Pesagem',
                    icon: Icons.check_circle_rounded,
                    isLoading: _isLoading,
                    onPressed: _saveWeighing,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
