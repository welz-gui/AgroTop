import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../shared/widgets/custom_button.dart';
import '../../auth/presentation/login_page.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  bool _offlineSyncEnabled = true;
  bool _compressPhotosBeforeUpload = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Perfil & Configurações'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Card de Perfil do Usuário
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 30,
                      backgroundColor: AppColors.primary,
                      child: const Text(
                        'AD',
                        style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Administrador AgroTop',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: AppColors.accent.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: const Text(
                            'Perfil: Administrador',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: AppColors.primaryDark,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Configurações Técnicas e de Campo
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Configurações de Sincronização',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 8),
                    SwitchListTile(
                      title: const Text('Sincronização Automática Offline'),
                      subtitle: const Text('Enviar registros gravados no curral quando houver internet.'),
                      value: _offlineSyncEnabled,
                      activeColor: AppColors.primary,
                      onChanged: (val) => setState(() => _offlineSyncEnabled = val),
                    ),
                    const Divider(),
                    SwitchListTile(
                      title: const Text('Comprimir Fotos antes do Envio'),
                      subtitle: const Text('Economiza dados móveis no campo.'),
                      value: _compressPhotosBeforeUpload,
                      activeColor: AppColors.primary,
                      onChanged: (val) => setState(() => _compressPhotosBeforeUpload = val),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            CustomButton(
              label: 'Encerrar Sessão (Logout)',
              icon: Icons.logout_rounded,
              backgroundColor: AppColors.alertError,
              onPressed: () {
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute(builder: (_) => const LoginPage()),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
