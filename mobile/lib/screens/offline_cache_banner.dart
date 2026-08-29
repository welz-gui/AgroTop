import 'package:flutter/material.dart';

class OfflineCacheBanner extends StatelessWidget {
  const OfflineCacheBanner({
    super.key,
    required this.formattedTime,
  });

  final String formattedTime;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    return Container(
      key: const ValueKey('offline-cache-banner'),
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: colorScheme.surfaceContainerHighest,
      child: Row(
        children: [
          Icon(
            Icons.cloud_off_outlined,
            size: 20,
            color: colorScheme.primary,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Dados de $formattedTime, pode estar desatualizado.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
