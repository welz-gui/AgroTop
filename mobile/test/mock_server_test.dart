// ignore_for_file: unnecessary_overrides

import 'dart:io';
import 'dart:typed_data';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/screens/animal_photo_section.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/io_client.dart';
import 'package:image/image.dart' as image_lib;

import 'mock_api_server.dart';

class ServerTokenStore implements TokenStore {
  StoredTokens? tokens;

  @override
  Future<void> clear() async => tokens = null;

  @override
  Future<StoredTokens?> read() async => tokens;

  @override
  Future<void> write(StoredTokens value) async => tokens = value;
}

class PassthroughHttpOverrides extends HttpOverrides {
  // A implementação herdada cria o cliente real em vez do bloqueio do flutter_test.
  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      super.createHttpClient(context);
}

void main() {
  test('fluxo completo percorre o servidor mock HTTP local', () async {
    final server = await MockApiServer.start();
    addTearDown(server.close);

    await HttpOverrides.runWithHttpOverrides(() async {
      final networkClient = IOClient(HttpClient());
      addTearDown(networkClient.close);
      final api = ApiClient(
        tokenStore: ServerTokenStore(),
        httpClient: networkClient,
        baseUrl: server.baseUrl,
      );

      final login = await api.login('admin', 'senha-segura');
      expect(login.user.username, 'admin');
      final animals = await api.listAnimals();
      expect(animals.first.id, 'BR0001');
      expect(server.refreshRequests, 1);
      final before = await api.getAnimal('BR0001');
      expect(before.currentWeight, 382.4);

      // Sanidade: carregar protocolos com dose_sugerida calculada no servidor
      final protocolos = await api.listProtocolos(animalId: 'BR0001');
      expect(server.protocolosRequests, 1);
      expect(protocolos.first.nome, 'Ivermectina 1%');
      expect(protocolos.first.doseSugerida, 7.6);

      // Sanidade: verificar carência inicial e histórico vazio
      final initialMeds = await api.getAnimalMedications('BR0001');
      expect(server.medicationsRequests, 1);
      expect(initialMeds.carenciaAte, isNull);
      expect(initialMeds.aplicacoes, isEmpty);

      // Sanidade: registrar medicamento
      final carenciaAte = await api.registerMedication(
        'BR0001',
        medicamento: 'Ivermectina 1%',
        dose: 8.0,
        unidade: 'ml',
        via: 'Subcutânea',
        carenciaDias: 28,
        data: '2026-08-22',
        protocoloId: 1,
      );
      expect(server.postMedicationRequests, 1);
      expect(carenciaAte, '2026-09-19');

      final afterMeds = await api.getAnimalMedications('BR0001');
      expect(afterMeds.carenciaAte, '2026-09-19');
      expect(afterMeds.aplicacoes.length, 1);
      expect(afterMeds.aplicacoes.first.medicamento, 'Ivermectina 1%');

      final originalPhoto = _testPhoto();
      final compressedPhoto = compressAnimalPhoto(originalPhoto);
      expect(compressedPhoto.length, lessThan(originalPhoto.length));
      final decodedPhoto = image_lib.decodeImage(compressedPhoto)!;
      expect(decodedPhoto.width, 1000);
      expect(decodedPhoto.height, 667);
      final photoId = await api.uploadAnimalPhoto(
        'BR0001',
        bytes: compressedPhoto,
        takenDate: '2026-08-23',
      );
      expect(server.photoUploadRequests, 1);
      expect(server.lastPhotoUploadSize, compressedPhoto.length);
      expect(server.lastPhotoUploadSize, lessThan(originalPhoto.length));
      final photos = await api.listAnimalPhotos('BR0001');
      expect(photos.single.id, photoId);
      expect(await api.getAnimalPhoto(photoId), compressedPhoto);
      final lotes = await api.listLotes();
      expect(lotes.map((lote) => lote.id), containsAll(['P01', 'P02', 'P03']));
      final movement = await api.moveAnimals(
        animalIds: ['BR0001', 'BR0002', 'INEXISTENTE'],
        toLoteId: 'P02',
        movementDate: '2026-08-22',
      );
      expect(server.movementRequests, 1);
      expect(server.lastMovementBody, {
        'animal_ids': ['BR0001', 'BR0002', 'INEXISTENTE'],
        'to_lote_id': 'P02',
        'movement_date': '2026-08-22',
        'reason': 'manejo',
        'notes': null,
      });
      expect(movement.movidos, ['BR0001']);
      expect(movement.jaNoDestino, ['BR0002']);
      expect(movement.erros, ['INEXISTENTE: animal não encontrado']);
      final moved = await api.getAnimal('BR0001');
      expect(moved.loteId, 'P02');
      final weighing = await api.registerWeighing(
        'BR0001',
        peso: 401.2,
        data: '2026-08-22',
      );
      expect(weighing.status, 'success');
      final after = await api.getAnimal('BR0001');
      expect(after.currentWeight, 401.2);
      await api.logout();
    }, PassthroughHttpOverrides());
  });
}

Uint8List _testPhoto() {
  final photo = image_lib.Image(width: 1200, height: 800);
  for (var y = 0; y < photo.height; y++) {
    for (var x = 0; x < photo.width; x++) {
      photo.setPixelRgb(x, y, x % 256, y % 256, (x + y) % 256);
    }
  }
  return Uint8List.fromList(image_lib.encodePng(photo, level: 0));
}
