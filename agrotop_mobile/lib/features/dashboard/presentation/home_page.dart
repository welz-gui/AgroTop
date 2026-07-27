import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../shared/widgets/sync_status_badge.dart';
import '../../animal/presentation/animal_list_page.dart';
import '../../animal/presentation/animal_form_page.dart';
import '../../weighings/presentation/weighing_form_page.dart';
import '../../camera_ocr/presentation/camera_ocr_page.dart';
import '../../terminacao/presentation/simulador_terminacao_page.dart';
import '../../profile/presentation/profile_page.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  String _selectedLote = 'Todos os Piquetes';

  final List<String> _lotes = [
    'Todos os Piquetes',
    'Piquete 01 - Recria Nelore',
    'Piquete 02 - Engorda Machos',
    'Piquete 03 - Confinamento A',
    'Piquete 04 - Maternidade',
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: const [
            Icon(Icons.agriculture_rounded, size: 24),
            SizedBox(width: 8),
            Text('AgroTop Mobile'),
          ],
        ),
        actions: [
          const Padding(
            padding: EdgeInsets.only(right: 8.0),
            child: SyncStatusBadge(isOnline: true, pendingSyncCount: 0),
          ),
          IconButton(
            icon: const Icon(Icons.person_outline_rounded),
            tooltip: 'Perfil & Configurações',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const ProfilePage()),
              );
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Seletor de Unidade / Piquete
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.cardBorder),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  value: _selectedLote,
                  isExpanded: true,
                  icon: const Icon(Icons.location_on_outlined, color: AppColors.primary),
                  items: _lotes.map((lote) {
                    return DropdownMenuItem(
                      value: lote,
                      child: Text(
                        lote,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    );
                  }).toList(),
                  onChanged: (val) {
                    if (val != null) setState(() => _selectedLote = val);
                  },
                ),
              ),
            ),
            const SizedBox(height: 20),

            // Resumo de Indicadores KPI
            const Text(
              'Resumo do Rebanho',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _buildKpiCard(
                    title: 'Total Ativo',
                    value: '185',
                    unit: 'cabeças',
                    icon: Icons.pets_rounded,
                    color: AppColors.primary,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildKpiCard(
                    title: 'Peso Médio',
                    value: '412.5',
                    unit: 'kg (14.8 @)',
                    icon: Icons.monitor_weight_outlined,
                    color: AppColors.primaryLight,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _buildKpiCard(
                    title: 'GMD Médio',
                    value: '0.850',
                    unit: 'kg/dia',
                    icon: Icons.trending_up_rounded,
                    color: AppColors.accent,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildKpiCard(
                    title: 'Alertas Carência',
                    value: '2',
                    unit: 'animais',
                    icon: Icons.health_and_safety_outlined,
                    color: AppColors.alertError,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // Menu de Ações Rápidas do Campo
            const Text(
              'Ações Rápidas de Campo',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 12),

            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 2,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              childAspectRatio: 1.25,
              children: [
                _buildActionCard(
                  context,
                  title: 'Ver Rebanho',
                  subtitle: 'Listagem e buscas',
                  icon: Icons.format_list_bulleted_rounded,
                  color: AppColors.primary,
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const AnimalListPage()),
                    );
                  },
                ),
                _buildActionCard(
                  context,
                  title: 'Registrar Pesagem',
                  subtitle: 'Manejo no curral',
                  icon: Icons.scale_rounded,
                  color: AppColors.primaryLight,
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const WeighingFormPage()),
                    );
                  },
                ),
                _buildActionCard(
                  context,
                  title: 'Câmera & OCR',
                  subtitle: 'Ler brinco / QR Code',
                  icon: Icons.qr_code_scanner_rounded,
                  color: AppColors.accent,
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const CameraOcrPage()),
                    );
                  },
                ),
                _buildActionCard(
                  context,
                  title: 'Novo Cadastro',
                  subtitle: 'Inserir animal',
                  icon: Icons.add_circle_outline_rounded,
                  color: Colors.teal,
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const AnimalFormPage()),
                    );
                  },
                ),
                _buildActionCard(
                  context,
                  title: 'Simulador Terminação',
                  subtitle: 'Comparar estratégias',
                  icon: Icons.calculate_outlined,
                  color: Colors.blueGrey,
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const SimuladorTerminacaoPage()),
                    );
                  },
                ),
                _buildActionCard(
                  context,
                  title: 'Perfil & Config',
                  subtitle: 'Sincronização / Conta',
                  icon: Icons.settings_outlined,
                  color: Colors.purple,
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const ProfilePage()),
                    );
                  },
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildKpiCard({
    required String title,
    required String value,
    required String unit,
    required IconData icon,
    required Color color,
  }) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppColors.textSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Icon(icon, size: 20, color: color),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              value,
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            Text(
              unit,
              style: const TextStyle(
                fontSize: 12,
                color: AppColors.textLight,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActionCard(
    BuildContext context, {
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
  }) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(14.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 26),
              ),
              const SizedBox(height: 10),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              Text(
                subtitle,
                style: const TextStyle(
                  fontSize: 11,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
