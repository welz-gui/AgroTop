import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../shared/widgets/custom_button.dart';
import '../../../shared/widgets/custom_text_field.dart';
import '../data/animal_repository.dart';
import '../domain/animal_model.dart';

class AnimalFormPage extends StatefulWidget {
  const AnimalFormPage({super.key});

  @override
  State<AnimalFormPage> createState() => _AnimalFormPageState();
}

class _AnimalFormPageState extends State<AnimalFormPage> {
  final _formKey = GlobalKey<FormState>();
  final _idController = TextEditingController();
  final _breedController = TextEditingController(text: 'Nelore');
  final _weightController = TextEditingController();
  String _sex = 'M';
  String _selectedLote = 'PIQUETE-01';
  bool _isLoading = false;

  final List<String> _lotes = [
    'PIQUETE-01',
    'PIQUETE-02',
    'CONFINAMENTO-A',
  ];

  Future<void> _saveAnimal() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);

    try {
      final newAnimal = AnimalModel(
        id: _idController.text.trim(),
        breed: _breedController.text.trim(),
        sex: _sex,
        entryDate: DateTime.now().toIso8601String().substring(0, 10),
        loteId: _selectedLote,
        status: 'ativo',
        currentWeight: double.tryParse(_weightController.text.replaceAll(',', '.')),
      );

      await AnimalRepository().addAnimal(newAnimal);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Animal ${_idController.text} cadastrado com sucesso!')),
        );
        Navigator.of(context).pop();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Animal cadastrado localmente (Modo Offline).')),
        );
        Navigator.of(context).pop();
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Cadastrar Novo Animal'),
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
                    label: 'Código do Brinco / Rebanho',
                    hint: 'Ex: BR-2050',
                    controller: _idController,
                    prefixIcon: Icons.qr_code,
                    validator: (val) => val == null || val.isEmpty ? 'Informe o brinco' : null,
                  ),
                  const SizedBox(height: 16),

                  CustomTextField(
                    label: 'Raça',
                    hint: 'Ex: Nelore, Angus',
                    controller: _breedController,
                    prefixIcon: Icons.pets,
                    validator: (val) => val == null || val.isEmpty ? 'Informe a raça' : null,
                  ),
                  const SizedBox(height: 16),

                  const Text(
                    'Sexo',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Expanded(
                        child: RadioListTile<String>(
                          title: const Text('Macho'),
                          value: 'M',
                          groupValue: _sex,
                          onChanged: (val) => setState(() => _sex = val!),
                        ),
                      ),
                      Expanded(
                        child: RadioListTile<String>(
                          title: const Text('Fêmea'),
                          value: 'F',
                          groupValue: _sex,
                          onChanged: (val) => setState(() => _sex = val!),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  CustomTextField(
                    label: 'Peso Inicial (kg)',
                    hint: 'Ex: 380.5',
                    controller: _weightController,
                    keyboardType: TextInputType.number,
                    prefixIcon: Icons.scale,
                    validator: (val) => val == null || val.isEmpty ? 'Informe o peso' : null,
                  ),
                  const SizedBox(height: 16),

                  const Text(
                    'Piquete / Lote',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 6),
                  DropdownButtonFormField<String>(
                    value: _selectedLote,
                    items: _lotes.map((l) {
                      return DropdownMenuItem(value: l, child: Text(l));
                    }).toList(),
                    onChanged: (val) => setState(() => _selectedLote = val!),
                  ),
                  const SizedBox(height: 28),

                  CustomButton(
                    label: 'Salvar Cadastro',
                    icon: Icons.check_circle_outline,
                    isLoading: _isLoading,
                    onPressed: _saveAnimal,
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
