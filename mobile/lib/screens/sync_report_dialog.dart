import 'package:flutter/material.dart';

import '../offline_queue.dart';

class SyncReportDialog extends StatelessWidget {
  const SyncReportDialog({super.key, required this.report});

  final SyncReport report;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AlertDialog(
      key: const ValueKey('sync-report-dialog'),
      title: const Text('Relatório de sincronização'),
      content: SizedBox(
        width: double.maxFinite,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildSection(
                context,
                title:
                    'Sincronizados com sucesso (${report.sincronizados.length})',
                icon: Icons.check_circle_outline,
                iconColor: Colors.green,
                items: report.sincronizados
                    .map((s) => Text('• ${s.description}'))
                    .toList(growable: false),
                emptyMessage: 'Nenhum item sincronizado nesta rodada.',
              ),
              const Divider(height: 24),
              _buildSection(
                context,
                title: 'Ainda pendentes (${report.pendentes.length})',
                icon: Icons.schedule,
                iconColor: Colors.orange,
                items: report.pendentes
                    .map(
                      (p) => Text(
                        '• ${p.description} (${p.reason ?? "Sem conexão"})',
                      ),
                    )
                    .toList(growable: false),
                emptyMessage: 'Nenhum item pendente.',
              ),
              const Divider(height: 24),
              _buildSection(
                context,
                title: 'Rejeitados pelo servidor (${report.rejeitados.length})',
                icon: Icons.error_outline,
                iconColor: theme.colorScheme.error,
                items: report.rejeitados
                    .map((r) => Text('• ${r.description}: ${r.reason}'))
                    .toList(growable: false),
                emptyMessage: 'Nenhum item rejeitado.',
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          key: const ValueKey('close-sync-report'),
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Fechar'),
        ),
      ],
    );
  }

  Widget _buildSection(
    BuildContext context, {
    required String title,
    required IconData icon,
    required Color iconColor,
    required List<Widget> items,
    required String emptyMessage,
  }) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, size: 20, color: iconColor),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                title,
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        if (items.isEmpty)
          Padding(
            padding: const EdgeInsets.only(left: 28),
            child: Text(
              emptyMessage,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          )
        else
          Padding(
            padding: const EdgeInsets.only(left: 28),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: items
                  .map(
                    (w) => Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: w,
                    ),
                  )
                  .toList(growable: false),
            ),
          ),
      ],
    );
  }
}
