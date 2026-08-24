import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image/image.dart' as image_lib;
import 'package:image_picker/image_picker.dart';

import '../api_client.dart';
import '../models.dart';

typedef PhotoCapture = Future<Uint8List?> Function();

Uint8List compressAnimalPhoto(Uint8List original) {
  final decoded = image_lib.decodeImage(original);
  if (decoded == null) {
    throw const FormatException('A imagem capturada é inválida.');
  }
  final oriented = image_lib.bakeOrientation(decoded);
  final longestSide = oriented.width > oriented.height
      ? oriented.width
      : oriented.height;
  final resized = longestSide > 1000
      ? image_lib.copyResize(
          oriented,
          width: oriented.width >= oriented.height ? 1000 : null,
          height: oriented.height > oriented.width ? 1000 : null,
          interpolation: image_lib.Interpolation.average,
        )
      : oriented;
  return Uint8List.fromList(image_lib.encodeJpg(resized, quality: 75));
}

class AnimalPhotoSection extends StatefulWidget {
  const AnimalPhotoSection({
    super.key,
    required this.api,
    required this.animalId,
    required this.onUnauthorized,
    this.capturePhoto,
  });

  final ApiClient api;
  final String animalId;
  final VoidCallback onUnauthorized;
  final PhotoCapture? capturePhoto;

  @override
  State<AnimalPhotoSection> createState() => _AnimalPhotoSectionState();
}

class _AnimalPhotoSectionState extends State<AnimalPhotoSection> {
  final _photoFutures = <int, Future<Uint8List>>{};
  List<AnimalPhoto> _photos = const [];
  Uint8List? _pendingPhoto;
  String? _pendingDate;
  String? _error;
  String? _success;
  bool _loading = true;
  bool _working = false;

  @override
  void initState() {
    super.initState();
    _loadPhotos();
  }

  String _formatDate(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';

  Future<Uint8List?> _captureWithCamera() async {
    final file = await ImagePicker().pickImage(source: ImageSource.camera);
    return file?.readAsBytes();
  }

  Future<void> _loadPhotos() async {
    try {
      final photos = await widget.api.listAnimalPhotos(widget.animalId);
      photos.sort((a, b) {
        final byDate = b.takenDate.compareTo(a.takenDate);
        return byDate != 0 ? byDate : b.id.compareTo(a.id);
      });
      if (!mounted) return;
      setState(() {
        _photos = photos;
        _loading = false;
        _error = null;
        for (final photo in photos) {
          _photoFutures.putIfAbsent(
            photo.id,
            () => widget.api.getAnimalPhoto(photo.id),
          );
        }
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        widget.onUnauthorized();
      } else {
        setState(() {
          _loading = false;
          _error = error.message;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'API indisponível. Não foi possível carregar as fotos.';
        });
      }
    }
  }

  Future<void> _capture() async {
    setState(() {
      _working = true;
      _error = null;
      _success = null;
    });
    try {
      final original = await (widget.capturePhoto ?? _captureWithCamera)();
      if (original == null || !mounted) return;
      final compressed = compressAnimalPhoto(original);
      setState(() {
        _pendingPhoto = compressed;
        _pendingDate = _formatDate(DateTime.now());
      });
    } on FormatException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'Não foi possível abrir a câmera. Tente novamente.',
        );
      }
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _upload() async {
    final photo = _pendingPhoto;
    if (photo == null) return;
    setState(() {
      _working = true;
      _error = null;
      _success = null;
    });
    try {
      await widget.api.uploadAnimalPhoto(
        widget.animalId,
        bytes: photo,
        takenDate: _pendingDate,
      );
      if (!mounted) return;
      setState(() {
        _pendingPhoto = null;
        _pendingDate = null;
        _success = 'Foto enviada com sucesso.';
      });
      await _loadPhotos();
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401) {
        widget.onUnauthorized();
      } else {
        setState(
          () => _error = '${error.message} A foto foi mantida para reenviar.',
        );
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Falha de rede. A foto foi mantida para você tentar enviar novamente.',
        );
      }
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  @override
  Widget build(BuildContext context) => Card(
    key: const ValueKey('animal-photo-section'),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Icon(Icons.photo_camera_outlined),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Fotos do animal',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_loading)
            const Center(child: CircularProgressIndicator())
          else if (_photos.isEmpty)
            const ListTile(
              key: ValueKey('empty-photo-gallery'),
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.photo_library_outlined),
              title: Text('Nenhuma foto enviada'),
              subtitle: Text('Tire a primeira foto deste animal.'),
            )
          else
            Wrap(
              key: const ValueKey('animal-photo-gallery'),
              spacing: 8,
              runSpacing: 8,
              children: [for (final photo in _photos) _thumbnail(photo)],
            ),
          if (_pendingPhoto != null) ...[
            const SizedBox(height: 16),
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.memory(
                _pendingPhoto!,
                key: const ValueKey('pending-animal-photo'),
                height: 180,
                fit: BoxFit.cover,
              ),
            ),
            const SizedBox(height: 8),
            const Text('Foto pronta para enviar.'),
            const SizedBox(height: 8),
            FilledButton.icon(
              key: const ValueKey('send-animal-photo'),
              onPressed: _working ? null : _upload,
              icon: const Icon(Icons.cloud_upload_outlined),
              label: Text(_working ? 'Enviando…' : 'Enviar foto'),
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 12),
            Semantics(
              liveRegion: true,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    Icons.error_outline,
                    color: Theme.of(context).colorScheme.error,
                  ),
                  const SizedBox(width: 8),
                  Expanded(child: Text(_error!)),
                ],
              ),
            ),
          ],
          if (_success != null) ...[
            const SizedBox(height: 12),
            Semantics(
              liveRegion: true,
              child: const Row(
                children: [
                  Icon(Icons.check_circle_outline),
                  SizedBox(width: 8),
                  Expanded(child: Text('Foto enviada com sucesso.')),
                ],
              ),
            ),
          ],
          const SizedBox(height: 16),
          OutlinedButton.icon(
            key: const ValueKey('take-animal-photo'),
            onPressed: _working ? null : _capture,
            icon: const Icon(Icons.photo_camera),
            label: Text(
              _pendingPhoto == null ? 'Tirar foto' : 'Tirar outra foto',
            ),
          ),
        ],
      ),
    ),
  );

  Widget _thumbnail(AnimalPhoto photo) => SizedBox.square(
    dimension: 96,
    child: FutureBuilder<Uint8List>(
      future: _photoFutures[photo.id],
      builder: (context, snapshot) {
        if (snapshot.hasData) {
          return ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: Image.memory(
              snapshot.data!,
              key: ValueKey('animal-photo-${photo.id}'),
              fit: BoxFit.cover,
            ),
          );
        }
        if (snapshot.hasError) {
          return const Card(child: Icon(Icons.broken_image_outlined));
        }
        return const Card(child: Center(child: CircularProgressIndicator()));
      },
    ),
  );
}
