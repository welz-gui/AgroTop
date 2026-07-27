import 'package:flutter/material.dart';

class SyncStatusBadge extends StatelessWidget {
  final bool isOnline;
  final int pendingSyncCount;

  const SyncStatusBadge({
    super.key,
    this.isOnline = true,
    this.pendingSyncCount = 0,
  });

  @override
  Widget build(BuildContext context) {
    final color = isOnline
        ? (pendingSyncCount > 0 ? Colors.orange : Colors.green)
        : Colors.red;

    final label = isOnline
        ? (pendingSyncCount > 0 ? 'Sincronizando ($pendingSyncCount)' : 'Online')
        : 'Modo Offline';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color, width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 12,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}
