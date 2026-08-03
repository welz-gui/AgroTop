"""Serviço de previsão de ruptura de estoque para o AgroTop (função pura)."""

from datetime import date, timedelta
import math


def prever(insumos: list[dict], hoje: str) -> list[dict]:
    """Dias restantes e data de ruptura por insumo.

    `insumos`: [{
        "id": int, "nome": str, "unidade": str,
        "saldo": float,
        "consumo_diario": float,      # média observada; 0 = sem consumo conhecido
        "estoque_minimo": float,
        "prazo_reposicao_dias": int,  # da compra até chegar; 0 se desconhecido
    }, ...]
    `hoje`: "AAAA-MM-DD"

    Retorna, ordenado do mais urgente ao menos:
        [{
          "id": int, "nome": str,
          "dias_restantes": float | None,   # None = consumo desconhecido
          "data_ruptura": str | None,       # "AAAA-MM-DD"
          "comprar_ate": str | None,        # data_ruptura menos prazo_reposicao
          "urgencia": "critica" | "atencao" | "ok" | "sem_dados",
        }, ...]
    """
    if not isinstance(insumos, list):
        return []

    try:
        hoje_date = date.fromisoformat(hoje)
    except (ValueError, TypeError):
        hoje_date = date.today()

    resultado = []

    for insumo in insumos:
        if not isinstance(insumo, dict):
            continue

        insumo_id = insumo.get("id")
        nome = str(insumo.get("nome", ""))
        saldo = float(insumo.get("saldo", 0.0) or 0.0)
        consumo_diario = float(insumo.get("consumo_diario", 0.0) or 0.0)
        estoque_minimo = float(insumo.get("estoque_minimo", 0.0) or 0.0)
        prazo_reposicao_dias = int(insumo.get("prazo_reposicao_dias", 0) or 0)

        if consumo_diario <= 0:
            dias_restantes = None
            data_ruptura = None
            comprar_ate = None
            if estoque_minimo > 0 and saldo < estoque_minimo:
                urgencia = "critica"
            else:
                urgencia = "sem_dados"
        else:
            dias_restantes_val = max(0.0, saldo / consumo_diario)
            dias_restantes = float(round(dias_restantes_val, 1))

            dias_inteiros = int(math.floor(dias_restantes_val))
            data_ruptura_dt = hoje_date + timedelta(days=dias_inteiros)
            data_ruptura = data_ruptura_dt.isoformat()

            comprar_ate_dt = data_ruptura_dt - timedelta(
                days=prazo_reposicao_dias
            )
            comprar_ate = comprar_ate_dt.isoformat()

            dias_ate_comprar = (comprar_ate_dt - hoje_date).days

            if saldo < estoque_minimo or dias_ate_comprar < 0:
                urgencia = "critica"
            elif dias_ate_comprar <= 15:
                urgencia = "atencao"
            else:
                urgencia = "ok"

        resultado.append({
            "id": insumo_id,
            "nome": nome,
            "dias_restantes": dias_restantes,
            "data_ruptura": data_ruptura,
            "comprar_ate": comprar_ate,
            "urgencia": urgencia,
        })

    # Ordem de prioridade de urgência:
    # 1. critica (0)
    # 2. atencao (1)
    # 3. sem_dados (2) - insumos sem consumo registrado ficam antes dos seguros (ok) para evitar riscos ocultos
    # 4. ok (3)
    ordem_urgencia = {"critica": 0, "atencao": 1, "sem_dados": 2, "ok": 3}

    def chave_ordenacao(item: dict):
        prio = ordem_urgencia.get(item["urgencia"], 4)
        comprar_str = item.get("comprar_ate") or "9999-12-31"
        dias_val = (
            item.get("dias_restantes")
            if item.get("dias_restantes") is not None
            else 999999.0
        )
        return (prio, comprar_str, dias_val, item.get("nome", ""))

    resultado.sort(key=chave_ordenacao)
    return resultado
