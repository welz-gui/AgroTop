import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/formatters/formatters.dart';
import '../../../shared/widgets/custom_button.dart';
import '../domain/animal_model.dart';

class AnimalDetailPage extends StatelessWidget {
  final AnimalModel animal;

  const AnimalDetailPage({super.key, required this.animal});

  @override
  Widget build(BuildContext context) {
    final weightKg = animal.currentWeight ?? 0.0;
    final arrobas = AppFormatters.formatArrobas(weightKg);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text('Ficha: ${animal.id}'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Card Principal de Peso e Identificação
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              animal.id,
                              style: const TextStyle(
                                fontSize: 26,
                                fontWeight: FontWeight.bold,
                                color: AppColors.textPrimary,
                              ),
                            ),
                            Text(
                              '${animal.breed} (${animal.sex == 'M' ? 'Macho' : 'Fêmea'})',
                              style: const TextStyle(
                                fontSize: 16,
                                color: AppColors.textSecondary,
                              ),
                            ),
                          ],
                        ),
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppColors.primary.withOpacity(0.1),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.pets, size: 36, color: AppColors.primary),
                        ),
                      ],
                    ),
                    const Divider(height: 32),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        _buildMetricCol('Peso Atual', AppFormatters.formatWeight(weightKg)),
                        _buildMetricCol('Rendimento (@)', arrobas),
                        _buildMetricCol('GMD Diário', '+${animal.gmd ?? 0} kg/d'),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Card de Localização e Informações de Campo
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Informações de Manejo',
                      style: TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 12),
                    _buildInfoRow('Piquete / Lote', animal.loteId ?? 'Não atribuído'),
                    _buildInfoRow('Data de Entrada', AppFormatters.formatIsoDateStr(animal.entryDate)),
                    _buildInfoRow('Status Sanitário', 'Liberado (Sem carência active)'),
                    _buildInfoRow('Observações', animal.notes ?? 'Nenhuma observação informada.'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            CustomButton(
              label: 'Registrar Nova Pesagem',
              icon: Icons.monitor_weight_rounded,
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Pesagem aberta para o brinco ${animal.id}.')),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricCol(String label, String value) {
    return Column(
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: AppColors.primary,
          ),
        ),
      ],
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(fontSize: 14, color: AppColors.textSecondary),
          ),
          Text(
            value,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}
