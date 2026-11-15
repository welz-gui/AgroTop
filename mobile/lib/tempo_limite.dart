import 'dart:async';

import 'package:http/http.dart' as http;

/// Quanto uma chamada comum espera o servidor antes de desistir. A partida a frio do Cloud Run já
/// levou 12 s (e 2 s com ele quente), então 20 s deixa folga sem prender o curral para sempre.
/// Estourar não perde nada: a tela guarda o registro na fila e a fila reenvia com a mesma chave.
const Duration kTempoLimiteDeRede = Duration(seconds: 20);

/// Envio de arquivo (foto, importação de CSV) sobe mais bytes por sinal pior: limite maior. Também é o
/// prazo total para receber o corpo de uma resposta: uma baixada lenta mas que anda cabe, uma parada não.
const Duration kTempoLimiteDeEnvio = Duration(seconds: 60);

/// O servidor não respondeu a tempo (ou parou no meio do corpo). É um `TimeoutException`, e não um
/// `ApiException`: as telas e a fila tratam como falta de conexão, não como recusa do servidor.
class TempoLimiteDeRede extends TimeoutException {
  TempoLimiteDeRede(Duration limite)
    : super('O servidor não respondeu em ${limite.inSeconds} s.', limite);
}

/// Embrulha um cliente HTTP: espera até [limite] pelo cabeçalho da resposta (pedido com arquivo,
/// multipart, usa [limiteDeEnvio]) e até [limiteDoCorpo] no total para receber o corpo.
///
/// O corpo é lido inteiro aqui dentro, e não vigiado pedaço a pedaço: o `ApiClient` sempre o lê
/// inteiro de qualquer jeito, e embrulhar o fluxo (`Stream.timeout`) muda a temporização com que os
/// eventos chegam, o que quebrava dezenas de testes de tela que contam os `pump()`.
class ClienteComTempoLimite extends http.BaseClient {
  ClienteComTempoLimite(
    this._inner, {
    this.limite = kTempoLimiteDeRede,
    this.limiteDeEnvio = kTempoLimiteDeEnvio,
    this.limiteDoCorpo = kTempoLimiteDeEnvio,
  });

  final http.Client _inner;
  final Duration limite;
  final Duration limiteDeEnvio;
  final Duration limiteDoCorpo;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final espera = request is http.MultipartRequest ? limiteDeEnvio : limite;
    final resposta = await _inner
        .send(request)
        .timeout(espera, onTimeout: () => throw TempoLimiteDeRede(espera));
    final corpo = await resposta.stream.toBytes().timeout(
      limiteDoCorpo,
      onTimeout: () => throw TempoLimiteDeRede(limiteDoCorpo),
    );
    return http.StreamedResponse(
      http.ByteStream.fromBytes(corpo),
      resposta.statusCode,
      contentLength: resposta.contentLength,
      request: resposta.request,
      headers: resposta.headers,
      isRedirect: resposta.isRedirect,
      persistentConnection: resposta.persistentConnection,
      reasonPhrase: resposta.reasonPhrase,
    );
  }

  @override
  void close() => _inner.close();
}
