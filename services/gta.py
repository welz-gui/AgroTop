"""Validação pura de GTA e trânsito de animais (PNIB §8)."""

from datetime import date


def _data_iso(valor) -> date | None:
    if not isinstance(valor, str):
        return None
    try:
        return date.fromisoformat(valor.strip())
    except ValueError:
        return None


def validar(gta: dict, contexto: dict | None = None) -> list[dict]:
    """Problemas na GTA. Lista vazia = apta ao trânsito.

    Valida somente os dados presentes. As verificações que dependem de uma
    chave ausente no contexto são puladas.
    """
    if not isinstance(gta, dict):
        return []
    if not isinstance(contexto, dict):
        contexto = {}

    problemas: list[dict] = []
    emissao = _data_iso(gta.get("emissao"))
    validade = _data_iso(gta.get("validade"))
    hoje = _data_iso(contexto.get("hoje"))

    if hoje and validade and hoje > validade:
        problemas.append({
            "codigo": "gta_vencida",
            "gravidade": "bloqueio",
            "mensagem": (
                f"A GTA venceu em {validade.isoformat()} e não permite trânsito "
                f"em {hoje.isoformat()}."
            ),
        })

    if hoje and emissao and emissao > hoje:
        problemas.append({
            "codigo": "gta_futura",
            "gravidade": "bloqueio",
            "mensagem": (
                f"A GTA foi emitida em {emissao.isoformat()}, depois da data "
                f"do trânsito ({hoje.isoformat()})."
            ),
        })

    limite = contexto.get("validade_maxima_dias", 7)
    if emissao and validade and isinstance(limite, int):
        dias_validade = (validade - emissao).days
        if dias_validade > limite:
            problemas.append({
                "codigo": "validade_maior_que_o_permitido",
                "gravidade": "bloqueio",
                "mensagem": (
                    f"A GTA tem validade de {dias_validade} dias, acima do limite "
                    f"de {limite} dias."
                ),
            })

    animais = gta.get("animais")
    quantidade = gta.get("quantidade")
    if isinstance(animais, list) and isinstance(quantidade, int):
        if quantidade != len(animais):
            problemas.append({
                "codigo": "quantidade_divergente",
                "gravidade": "bloqueio",
                "mensagem": (
                    f"A GTA informa {quantidade} animais, mas declara "
                    f"{len(animais)} identificadores."
                ),
            })

    animais_gta = set(animais) if isinstance(animais, list) else set()
    embarque = contexto.get("animais_no_embarque")
    animais_embarque = set(embarque) if isinstance(embarque, list) else None
    if animais_embarque is not None and isinstance(animais, list):
        for animal in sorted(animais_embarque - animais_gta):
            problemas.append({
                "codigo": "animal_no_embarque_fora_da_gta",
                "gravidade": "bloqueio",
                "mensagem": f"O animal '{animal}' está no embarque, mas não consta na GTA.",
            })
        for animal in sorted(animais_gta - animais_embarque):
            problemas.append({
                "codigo": "animal_da_gta_ausente",
                "gravidade": "bloqueio",
                "mensagem": f"O animal '{animal}' consta na GTA, mas não está no embarque.",
            })

    finalidade = str(gta.get("finalidade", "")).strip().lower()
    carencia = contexto.get("animais_em_carencia")
    if finalidade == "abate" and isinstance(carencia, list):
        animais_em_transito = animais_gta
        if animais_embarque is not None:
            animais_em_transito = animais_em_transito & animais_embarque
        for animal in sorted(animais_em_transito & set(carencia)):
            problemas.append({
                "codigo": "animal_em_carencia",
                "gravidade": "bloqueio",
                "mensagem": f"O animal '{animal}' está em carência e não pode seguir para abate.",
            })

    origem = str(gta.get("propriedade_origem", "")).strip()
    destino = str(gta.get("propriedade_destino", "")).strip()
    if origem and destino and origem == destino:
        problemas.append({
            "codigo": "origem_igual_ao_destino",
            "gravidade": "bloqueio",
            "mensagem": "A propriedade de origem é igual à propriedade de destino.",
        })

    uf_origem = str(gta.get("uf_origem", "")).strip().upper()
    uf_destino = str(gta.get("uf_destino", "")).strip().upper()
    if uf_origem and uf_destino and uf_origem != uf_destino and not finalidade:
        problemas.append({
            "codigo": "uf_diferente_sem_finalidade",
            "gravidade": "alerta",
            "mensagem": (
                f"O trânsito entre {uf_origem} e {uf_destino} está sem finalidade informada."
            ),
        })

    return problemas
