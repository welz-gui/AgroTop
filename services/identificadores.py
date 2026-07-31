import re

_RE_NORMALIZE = re.compile(r"[ .-]+")

REGRAS_PADRAO = {
    "rfid": {
        "tipo": "rfid",
        "tamanho": 15,
        "somente_digitos": True,
    },
    "sisbov": {
        "tipo": "sisbov",
        "tamanho": 15,
        "somente_digitos": True,
    },
    "manejo": {
        "tipo": "manejo",
        "tamanho_min": 1,
        "tamanho_max": 20,
    },
    "oficial_pnib": {
        # O formato oficial ainda não foi publicado (§23 do PNIB).
        # Esta regra provisória existe apenas para deixar claro que o valor
        # será validado por configuração, não por formato fixo no código.
    },
}


def _normalize(valor: str) -> str:
    if valor is None:
        return ""
    if not isinstance(valor, str):
        valor = str(valor)
    return _RE_NORMALIZE.sub("", valor).upper()


def _compute_mod10_checksum(digits: list[int]) -> int:
    total = 0
    factor = 2
    for digit in reversed(digits):
        product = digit * factor
        total += product - 9 if product > 9 else product
        factor = 1 if factor == 2 else 2
    return (10 - (total % 10)) % 10


def _check_mod10(value: str) -> bool:
    if len(value) < 2 or not value.isdigit():
        return False
    body = [int(ch) for ch in value[:-1]]
    expected = _compute_mod10_checksum(body)
    return expected == int(value[-1])


def _compute_mod11_checksum(digits: list[int]) -> int | None:
    weights = [2, 3, 4, 5, 6, 7]
    total = 0
    for index, digit in enumerate(reversed(digits)):
        total += digit * weights[index % len(weights)]
    remainder = total % 11
    if remainder == 0:
        return 0
    check = 11 - remainder
    return check if check < 10 else None


def _check_mod11(value: str) -> bool:
    if len(value) < 2 or not value.isdigit():
        return False
    body = [int(ch) for ch in value[:-1]]
    expected = _compute_mod11_checksum(body)
    return expected is not None and expected == int(value[-1])


def validar(valor: str, regra: dict) -> dict:
    normalizado = _normalize(valor)
    erros: list[str] = []
    regra = regra or {}

    tamanho = regra.get("tamanho")
    tamanho_min = regra.get("tamanho_min")
    tamanho_max = regra.get("tamanho_max")
    prefixo = regra.get("prefixo")
    somente_digitos = regra.get("somente_digitos")
    padrao = regra.get("padrao")
    digito_verificador = regra.get("digito_verificador")

    if tamanho is not None:
        if not isinstance(tamanho, int):
            erros.append("tamanho deve ser um inteiro")
        elif len(normalizado) != tamanho:
            erros.append(f"tamanho deve ser {tamanho} caracteres")

    if tamanho_min is not None:
        if not isinstance(tamanho_min, int):
            erros.append("tamanho_min deve ser um inteiro")
        elif len(normalizado) < tamanho_min:
            erros.append(f"tamanho deve ter pelo menos {tamanho_min} caracteres")

    if tamanho_max is not None:
        if not isinstance(tamanho_max, int):
            erros.append("tamanho_max deve ser um inteiro")
        elif len(normalizado) > tamanho_max:
            erros.append(f"tamanho deve ter no máximo {tamanho_max} caracteres")

    if prefixo is not None:
        if not isinstance(prefixo, str):
            erros.append("prefixo deve ser texto")
        elif not normalizado.startswith(prefixo.upper()):
            prefixo_text = prefixo.upper()
            erros.append(f"deve começar com '{prefixo_text}'")

    if somente_digitos:
        if not normalizado.isdigit():
            erros.append("deve conter apenas dígitos")

    if padrao is not None:
        try:
            regex = re.compile(padrao)
        except re.error:
            erros.append("padrão inválido")
        else:
            if not regex.fullmatch(normalizado):
                erros.append("não corresponde ao padrão")

    if digito_verificador is not None:
        if not normalizado.isdigit():
            erros.append("dígito verificador só é aplicável a valores numéricos")
        elif digito_verificador == "mod10":
            if not _check_mod10(normalizado):
                erros.append("dígito verificador mod10 inválido")
        elif digito_verificador == "mod11":
            if not _check_mod11(normalizado):
                erros.append("dígito verificador mod11 inválido")
        else:
            erros.append(f"dígito verificador desconhecido '{digito_verificador}'")

    return {
        "valido": not erros,
        "normalizado": normalizado,
        "erros": erros,
    }


def mesmo_identificador(a: str, b: str) -> bool:
    return _normalize(a) == _normalize(b)
