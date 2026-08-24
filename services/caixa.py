from datetime import date, datetime


def _parse_date(value: str) -> date | None:
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"data inválida: {value}")


def _date_or_none(value: str) -> date | None:
    if not value:
        return None

    try:
        return _parse_date(value)
    except ValueError:
        return None


def _lançamento_valido(lancamento: dict) -> bool:
    for campo in ("competencia", "vencimento", "pagamento"):
        valor = lancamento.get(campo)
        if valor is None or valor == "":
            continue
        try:
            _parse_date(valor)
        except ValueError:
            print(f"lancamento ignorado por data inválida em {campo}: {valor}")
            return False
    return True


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _competencia_mes(lancamento: dict, ano: int, mes: int) -> bool:
    competencia = _parse_date(lancamento.get("competencia"))
    return competencia is not None and competencia.year == ano and competencia.month == mes


def resultado_por_competencia(lancamentos: list[dict], ano: int, mes: int) -> dict:
    receitas = 0.0
    despesas = 0.0
    por_categoria: dict[str, float] = {}

    for lancamento in lancamentos or []:
        if not _lançamento_valido(lancamento):
            continue

        if not _competencia_mes(lancamento, ano, mes):
            continue

        tipo = lancamento.get("tipo")
        valor = _to_float(lancamento.get("valor"))
        categoria = str(lancamento.get("categoria", ""))

        if tipo == "receita":
            receitas += valor
            por_categoria[categoria] = por_categoria.get(categoria, 0.0) + valor
        elif tipo == "despesa":
            despesas += valor
            por_categoria[categoria] = por_categoria.get(categoria, 0.0) + valor
        else:
            print(f"tipo de lançamento inválido ignorado: {tipo}")

    resultado = receitas - despesas
    categorias = [
        {"categoria": categoria, "valor": round(valor, 2)}
        for categoria, valor in sorted(por_categoria.items())
    ]

    return {
        "receitas": round(receitas, 2),
        "despesas": round(despesas, 2),
        "resultado": round(resultado, 2),
        "por_categoria": categorias,
    }


def fluxo_de_caixa(lancamentos: list[dict], de: str, ate: str) -> dict:
    data_de = _parse_date(de)
    data_ate = _parse_date(ate)

    if data_de is None or data_ate is None:
        raise ValueError("intervalo de datas inválido")

    realizado = 0.0
    projetado = 0.0

    for lancamento in lancamentos or []:
        if not _lançamento_valido(lancamento):
            continue

        pagamento = _parse_date(lancamento.get("pagamento"))
        vencimento = _parse_date(lancamento.get("vencimento"))
        valor = _to_float(lancamento.get("valor"))

        if pagamento is not None:
            if data_de <= pagamento <= data_ate:
                realizado += valor
            continue

        if vencimento is None:
            continue

        if data_de <= vencimento <= data_ate:
            projetado += valor

    return {
        "realizado": round(realizado, 2),
        "projetado": round(projetado, 2),
        "saldo_projetado": round(realizado + projetado, 2),
    }


def em_aberto(lancamentos: list[dict], hoje: str) -> list[dict]:
    data_hoje = _parse_date(hoje)
    if data_hoje is None:
        raise ValueError("data de referência inválida")

    saldos: list[dict] = []

    for lancamento in lancamentos or []:
        if lancamento.get("pagamento") is not None:
            continue

        vencimento = _parse_date(lancamento.get("vencimento"))
        if vencimento is None:
            continue

        dias_atraso = max(0, (data_hoje - vencimento).days)
        saldos.append({
            "categoria": str(lancamento.get("categoria", "")),
            "valor": round(_to_float(lancamento.get("valor")), 2),
            "vencimento": vencimento.isoformat(),
            "dias_atraso": dias_atraso,
            "tipo": str(lancamento.get("tipo", "")),
        })

    saldos.sort(key=lambda item: (item["dias_atraso"] <= 0, -item["dias_atraso"], item["vencimento"]))
    return saldos
