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
      expect(animals.single.id, 'BR0001');
      expect(server.refreshRequests, 1);
      final before = await api.getAnimal('BR0001');
      expect(before.currentWeight, 382.4);
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
