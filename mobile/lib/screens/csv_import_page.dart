import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models.dart';

class SelectedCsvFile {
  const SelectedCsvFile({required this.name, required this.bytes});

  final String name;
  final Uint8List bytes;
}

abstract interface class CsvFilePicker {
  Future<SelectedCsvFile?> pick();
}

class DeviceCsvFilePicker implements CsvFilePicker {
  const DeviceCsvFilePicker();

  @override
  Future<SelectedCsvFile?> pick() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['csv', 'txt'],
      withData: true,
    );
    final file = result?.files.single;
    if (file == null || file.bytes == null) return null;
    return SelectedCsvFile(name: file.name, bytes: file.bytes!);
  }
}

class CsvImportPage extends StatefulWidget {
  const CsvImportPage({
    super.key,
    required this.api,
    required this.onUnauthorized,
    CsvFilePicker? filePicker,
  }) : filePicker = filePicker ?? const DeviceCsvFilePicker();

  final ApiClient api;
  final VoidCallback onUnauthorized;
  final CsvFilePicker filePicker;

  @override
  State<CsvImportPage> createState() => _CsvImportPageState();
}

class _CsvImportPageState extends State<CsvImportPage> {
  SelectedCsvFile? _file;
  CsvImportResult? _result;
  String? _error;
  bool _sending = false;
  bool _saved = false;

  Future<void> _chooseFile() async {
    final file = await widget.filePicker.pick();
    if (!mounted || file == null) return;
    setState(() {
      _file = file;
      _result = null;
      _error = null;
      _saved = false;
    });
    await _send(confirmar: false);
  }

  Future<void> _send({required bool confirmar}) async {
    final file = _file;
    if (file == null) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      final result = await widget.api.importWeighingsCsv(
        bytes: file.bytes,
        filename: file.name,
        confirmar: confirmar,
      );
      if (!mounted) return;
      setState(() {
        _result = result;
        _saved = confirmar;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        widget.onUnauthorized();
        return;
      }
      setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'API indisponível. Verifique a conexão e tente novamente.',
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final result = _result;
    return Scaffold(
      appBar: AppBar(title: const Text('Importar pesagens')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          OutlinedButton.icon(
            key: const ValueKey('pick-csv-file'),
            onPressed: _sending ? null : _chooseFile,
            icon: const Icon(Icons.attach_file),
            label: const Text('Selecionar arquivo CSV ou TXT'),
          ),
          if (_file != null) ...[
            const SizedBox(height: 12),
            Card(
              child: ListTile(
                leading: const Icon(Icons.description_outlined),
                title: Text(_file!.name),
                subtitle: const Text('Arquivo selecionado'),
              ),
            ),
          ],
          if (_sending) ...[
            const SizedBox(height: 20),
            const Center(child: CircularProgressIndicator()),
          ],
          if (_error != null) ...[
            const SizedBox(height: 16),
            Card(
              child: ListTile(
                leading: Icon(
                  Icons.error_outline,
                  color: Theme.of(context).colorScheme.error,
                ),
                title: Text(_error!),
                trailing: TextButton(
                  onPressed: _sending ? null : () => _send(confirmar: false),
                  child: const Text('Tentar novamente'),
                ),
              ),
            ),
          ],
          if (result != null) ...[
            const SizedBox(height: 20),
            Text(
              'Pré-visualização',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Card(
              child: Column(
                children: [
                  ListTile(
                    title: const Text('Linhas lidas'),
                    trailing: Text('${result.totalLinhas}'),
                  ),
                  ListTile(
                    title: const Text('Aceitas'),
                    trailing: Text('${result.aceitas.length}'),
                  ),
                  ListTile(
                    title: const Text('Rejeitadas'),
                    trailing: Text('${result.rejeitadas.length}'),
                  ),
                ],
              ),
            ),
            if (!_saved)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('Ainda não foi gravado.'),
              ),
            if (_saved)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('${result.gravadas} pesagem(ns) gravada(s).'),
              ),
            const SizedBox(height: 16),
            Text(
              'Pesagens aceitas',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            for (final accepted in result.aceitas)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${accepted.animalId} · ${accepted.peso.toStringAsFixed(1)} kg',
                      ),
                      Text(accepted.data),
                      for (final alert in accepted.alertas)
                        Padding(
                          padding: const EdgeInsets.only(top: 8),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                Icons.warning_amber_rounded,
                                color: Theme.of(context).colorScheme.error,
                              ),
                              const SizedBox(width: 8),
                              Expanded(child: Text(alert)),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: 16),
            Text(
              'Linhas rejeitadas',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            if (result.rejeitadas.isEmpty)
              const Text('Nenhuma linha rejeitada.')
            else
              for (final rejected in result.rejeitadas)
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.error_outline),
                    title: Text('Linha ${rejected.linha}: ${rejected.motivo}'),
                    subtitle: Text(rejected.conteudo),
                  ),
                ),
            if (!_saved && result.aceitas.isNotEmpty) ...[
              const SizedBox(height: 20),
              FilledButton.icon(
                key: const ValueKey('confirm-csv-import'),
                onPressed: _sending ? null : () => _send(confirmar: true),
                icon: const Icon(Icons.save_outlined),
                label: Text('Gravar ${result.aceitas.length} pesagem(ns)'),
              ),
            ],
          ],
        ],
      ),
    );
  }
}
