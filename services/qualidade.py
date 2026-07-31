from datetime import date, datetime


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _percentage_change(current: float, previous: float) -> float:
    if previous == 0:
        return float("inf") if current != 0 else 0.0
    return abs((current - previous) / previous) * 100.0


def _local_gmd(current_weight: float, previous_weight: float, current_date: date,
               previous_date: date) -> float | None:
    days = (current_date - previous_date).days
    if days <= 0:
        return None
    return round((current_weight - previous_weight) / days, 3)


def avaliar_pesagem(
    peso: float,
    data: str,
    historico: list[dict],
) -> list[dict]:
    """Aponta indícios de erro numa pesagem, sem bloquear.

    Esta função calcula o GMD local entre a pesagem atual e a última do histórico.
    Não é o mesmo GMD exibido no app, que usa lógica própria de tendência.
    """
    hoje = date.today()
    data_atual = _parse_date(data)
    alerts: list[dict] = []

    if peso <= 0 or peso > 1500:
        if peso <= 0:
            mensagem = f"Peso de {peso:.0f} kg está fora da faixa válida; verifique a leitura."
        else:
            mensagem = f"Peso de {peso:.0f} kg excede o limite máximo de 1500 kg."
        alerts.append({
            "tipo": "fora_de_faixa",
            "severidade": "alta",
            "mensagem": mensagem,
        })

    if data_atual is not None and data_atual > hoje:
        alerts.append({
            "tipo": "data_futura",
            "severidade": "alta",
            "mensagem": f"Data {data_atual.isoformat()} é futura; confirme se a data está correta.",
        })

    if historico:
        ultima = historico[0]
        peso_anterior = float(ultima.get("peso", 0.0))
        data_anterior = _parse_date(ultima.get("data", ""))

        if any(item.get("data") == data for item in historico):
            alerts.append({
                "tipo": "duplicidade",
                "severidade": "media",
                "mensagem": (
                    f"Já existe pesagem em {data} no histórico. Confirme se esta entrada não duplica" 
                    " um registro anterior."
                ),
            })

        if peso_anterior > 0:
            percentual = _percentage_change(peso, peso_anterior)
            if percentual > 20.0:
                alerts.append({
                    "tipo": "variacao_absurda",
                    "severidade": "alta",
                    "mensagem": (
                        f"Variação de {percentual:.1f}% em relação à última pesagem "
                        f"({peso_anterior:.0f} → {peso:.0f} kg) excede 20%."
                    ),
                })

        if peso_anterior > 0 and data_anterior is not None:
            current_date = data_atual or hoje
            gmd_local = _local_gmd(peso, peso_anterior, current_date, data_anterior)
            if gmd_local is not None and (gmd_local < -1.0 or gmd_local > 3.0):
                dias = (current_date - data_anterior).days
                peso_diff = peso - peso_anterior
                unidade = "ganho" if peso_diff >= 0 else "perda"
                mensagem = (
                    f"{unidade.capitalize()} de {abs(peso_diff):.0f} kg em {dias} dias "
                    f"({gmd_local:+.2f} kg/dia) está fora da faixa plausível −1,0…+3,0 kg/dia."
                )
                alerts.append({
                    "tipo": "gmd_implausivel",
                    "severidade": "alta",
                    "mensagem": mensagem,
                })

        if peso_anterior > peso and 0 < peso <= 1500:
            if not any(alert["tipo"] == "gmd_implausivel" for alert in alerts):
                # Mesmo que haja perda moderada, a função deve avisar o operador.
                dias = None
                if data_anterior is not None and data_atual is not None:
                    dias = (data_atual - data_anterior).days
                if dias is None or dias <= 0:
                    mensagem = (
                        f"Peso menor que o anterior ({peso_anterior:.0f} → {peso:.0f} kg); "
                        "confirme se a pesagem está correta."
                    )
                else:
                    perda_kg = peso_anterior - peso
                    gmd = round((peso - peso_anterior) / dias, 2)
                    mensagem = (
                        f"Perda de {perda_kg:.0f} kg em {dias} dias ({gmd:.2f} kg/dia) — "
                        "confirme se a pesagem está correta."
                    )
                alerts.append({
                    "tipo": "perda_de_peso",
                    "severidade": "media",
                    "mensagem": mensagem,
                })

    return alerts
