// ignore_for_file: unnecessary_overrides

import 'dart:io';

import 'package:agrotop_mobile/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/io_client.dart';

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
