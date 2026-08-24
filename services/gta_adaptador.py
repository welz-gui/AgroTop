"""Serviço adaptador de GTA para validação (função pura).

Monta as estruturas `gta` e `contexto` para serem validadas por `services.gta.validar()`.
"""

def montar_contexto(
    movimentacao: dict,
    dados_do_documento: dict,
    animais_no_embarque_uuids: list[str],
    animais_em_carencia_uuids: list[str],
    hoje: str,
) -> tuple[dict, dict]:
    """Monta os dicionários (gta, contexto) para `services.gta.validar(gta, contexto)`.

    Parâmetros:
    - `movimentacao`: dict com gta_numero, propriedade_origem_nome,
      propriedade_destino_nome, finalidade, animais_uuids.
    - `dados_do_documento`: dict com emissao, validade, quantidade_declarada (opcionais).
    - `animais_no_embarque_uuids`: lista de UUIDs dos animais que subiram no caminhão.
    - `animais_em_carencia_uuids`: lista de UUIDs dos animais em período de carência.
    - `hoje`: data de referência no formato "AAAA-MM-DD".

    Retorna:
    - tupla `(gta, contexto)` pronta para `services.gta.validar()`.

    Observações:
    - `uf_origem` e `uf_destino` não são incluídos no dict `gta`, pois `movimentacoes`
      não possui essa informação no schema atual.
    - `emissao`, `validade` e `quantidade` só são incluídos em `gta` se estiverem
      presentes (não None) em `dados_do_documento`.
    """
    if not isinstance(movimentacao, dict):
        movimentacao = {}

    if not isinstance(dados_do_documento, dict):
        dados_do_documento = {}

    if not isinstance(animais_no_embarque_uuids, list):
        animais_no_embarque_uuids = []

    if not isinstance(animais_em_carencia_uuids, list):
        animais_em_carencia_uuids = []

    gta = {}

    gta_num = movimentacao.get("gta_numero")
    if gta_num is not None:
        gta["numero"] = str(gta_num)

    origem = movimentacao.get("propriedade_origem_nome") or movimentacao.get("origem")
    if origem is not None:
        gta["propriedade_origem"] = str(origem)

    destino = movimentacao.get("propriedade_destino_nome") or movimentacao.get("destino")
    if destino is not None:
        gta["propriedade_destino"] = str(destino)

    finalidade = movimentacao.get("finalidade")
    if finalidade is not None:
        gta["finalidade"] = str(finalidade)

    animais = movimentacao.get("animais_uuids")
    if isinstance(animais, list):
        gta["animais"] = list(animais)
    else:
        gta["animais"] = []

    if dados_do_documento.get("emissao") is not None:
        gta["emissao"] = str(dados_do_documento["emissao"])

    if dados_do_documento.get("validade") is not None:
        gta["validade"] = str(dados_do_documento["validade"])

    if dados_do_documento.get("quantidade_declarada") is not None:
        try:
            gta["quantidade"] = int(dados_do_documento["quantidade_declarada"])
        except (ValueError, TypeError):
            pass

    contexto = {
        "hoje": str(hoje) if hoje is not None else "",
        "animais_no_embarque": list(animais_no_embarque_uuids),
        "animais_em_carencia": list(animais_em_carencia_uuids),
    }

    return gta, contexto
