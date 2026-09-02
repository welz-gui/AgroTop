import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models.dart';

const _statusLabels = {
  'solicitado': 'Solicitado ao fornecedor',
  'recebido': 'Recebido, a conferir',
  'disponivel': 'Disponível',
  'reservado': 'Reservado',
  'aplicado': 'Aplicado em animal',
  'perdido': 'Perdido',
  'danificado': 'Danificado',
  'substituido': 'Substituído',
  'inutilizado': 'Inutilizado (definitivo)',
  'devolvido': 'Devolvido (definitivo)',
  'cancelado': 'Cancelado (definitivo)',
  'bloqueado_orgao': 'Bloqueado pelo órgão',
};

const _typeLabels = {
  'brinco_visual': 'Brinco visual',
  'boton': 'Botton',
  'conjunto': 'Conjunto (visual + eletrônico)',
  'outro': 'Outro',
};

class DevicesPage extends StatefulWidget {
  const DevicesPage({
    super.key,
    required this.api,
    required this.onUnauthorized,
  });

  final ApiClient api;
  final VoidCallback onUnauthorized;

  @override
  State<DevicesPage> createState() => _DevicesPageState();
}

class _DevicesPageState extends State<DevicesPage> {
  final _codeController = TextEditingController();
  DeviceLookup? _device;
  String? _message;
  bool _loading = false;

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final code = _codeController.text.trim();
    if (code.isEmpty) {
      setState(() => _message = 'Informe o código do dispositivo.');
      return;
    }
    setState(() {
      _loading = true;
      _device = null;
      _message = null;
    });
    try {
      final device = await widget.api.findDevice(code);
      if (!mounted) return;
      setState(() {
        _device = device;
        _message = device == null
            ? 'Nenhum dispositivo ativo com esse código.'
            : null;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        widget.onUnauthorized();
        return;
      }
      setState(() => _message = error.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => _message =
              'API indisponível. Verifique a conexão e tente novamente.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _changeStatus(DeviceTransition transition, String motivo) async {
    final device = _device;
    if (device == null) return;
    try {
      await widget.api.updateDeviceStatus(
        device.id,
        novoStatus: transition.para,
        motivo: motivo.isEmpty ? null : motivo,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Situação atualizada.')));
      await _search();
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        widget.onUnauthorized();
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.message)));
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Não foi possível atualizar a situação.'),
          ),
        );
      }
    }
  }

  Future<void> _openTransition(DeviceTransition transition) async {
    if (transition.exigeAutorizacao) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _StatusConfirmationSheet(
        transition: transition,
        onConfirm: (motivo) async {
          Navigator.of(context).pop();
          await _changeStatus(transition, motivo);
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Brincos e dispositivos')),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextFormField(
            key: const ValueKey('device-code-field'),
            controller: _codeController,
            textCapitalization: TextCapitalization.characters,
            decoration: const InputDecoration(
              labelText: 'Código do dispositivo',
              border: OutlineInputBorder(),
            ),
            onFieldSubmitted: (_) => _search(),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            key: const ValueKey('search-device'),
            onPressed: _loading ? null : _search,
            icon: const Icon(Icons.search),
            label: const Text('Buscar'),
          ),
          if (_loading) ...[
            const SizedBox(height: 24),
            const Center(child: CircularProgressIndicator()),
          ],
          if (_message != null) ...[
            const SizedBox(height: 24),
            Text(_message!, key: const ValueKey('device-search-message')),
          ],
          if (_device != null) ...[
            const SizedBox(height: 24),
            _DeviceDetails(device: _device!, onTransition: _openTransition),
          ],
        ],
      ),
    ),
  );
}

class _DeviceDetails extends StatelessWidget {
  const _DeviceDetails({required this.device, required this.onTransition});

  final DeviceLookup device;
  final ValueChanged<DeviceTransition> onTransition;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                device.codigoVisual,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text('Tipo: ${_typeLabels[device.tipo] ?? device.tipo}'),
              Text(
                'Situação: ${_statusLabels[device.status] ?? device.status}',
              ),
              if (device.lote != null) Text('Lote: ${device.lote}'),
            ],
          ),
        ),
      ),
      const SizedBox(height: 16),
      Text('Mudar situação', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      if (device.transicoesPermitidas.isEmpty)
        const Text('Esta situação é definitiva ou bloqueada.')
      else
        ...device.transicoesPermitidas.map(
          (transition) => Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: transition.exigeAutorizacao
                ? ListTile(
                    key: ValueKey('device-transition-${transition.para}'),
                    enabled: false,
                    title: Text(
                      _statusLabels[transition.para] ?? transition.para,
                    ),
                    subtitle: const Text('Só o órgão libera.'),
                    trailing: const Icon(Icons.lock_outline),
                  )
                : OutlinedButton(
                    key: ValueKey('device-transition-${transition.para}'),
                    onPressed: () => onTransition(transition),
                    child: Text(
                      _statusLabels[transition.para] ?? transition.para,
                    ),
                  ),
          ),
        ),
    ],
  );
}

class _StatusConfirmationSheet extends StatefulWidget {
  const _StatusConfirmationSheet({
    required this.transition,
    required this.onConfirm,
  });

  final DeviceTransition transition;
  final Future<void> Function(String motivo) onConfirm;

  @override
  State<_StatusConfirmationSheet> createState() =>
      _StatusConfirmationSheetState();
}

class _StatusConfirmationSheetState extends State<_StatusConfirmationSheet> {
  final _reasonController = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _reasonController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.fromLTRB(
      16,
      16,
      16,
      MediaQuery.viewInsetsOf(context).bottom + 16,
    ),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Confirmar mudança',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        Text(
          'Nova situação: ${_statusLabels[widget.transition.para] ?? widget.transition.para}',
        ),
        if (widget.transition.exigeMotivo) ...[
          const SizedBox(height: 16),
          TextFormField(
            key: const ValueKey('device-status-reason'),
            controller: _reasonController,
            decoration: const InputDecoration(
              labelText: 'Motivo',
              border: OutlineInputBorder(),
            ),
            onChanged: (_) => setState(() {}),
          ),
        ],
        const SizedBox(height: 16),
        FilledButton(
          key: const ValueKey('confirm-device-status'),
          onPressed:
              _saving ||
                  (widget.transition.exigeMotivo &&
                      _reasonController.text.trim().isEmpty)
              ? null
              : () async {
                  setState(() => _saving = true);
                  await widget.onConfirm(_reasonController.text.trim());
                },
          child: const Text('Confirmar'),
        ),
      ],
    ),
  );
}
