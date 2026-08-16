"""Serviço de normalização de lançamentos financeiros (função pura).

Converte registros de `sales`, `fixed_costs`, `animal_costs` e `insumo_transactions`
para o formato único consumido por `services.caixa`.
"""

from typing import Iterable


def _safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_str(val, default: str = "") -> str:
    if val is None:
        return default
    return str(val)


def normalizar(
    *,
    vendas: Iterable[dict] = (),
    custos_fixos: Iterable[dict] = (),
    custos_animal: Iterable[dict] = (),
    compras_insumo: Iterable[dict] = (),
    contas_pagar: Iterable[dict] = (),
    contas_receber: Iterable[dict] = (),
) -> list[dict]:
    """Normaliza lançamentos heterogêneos para a estrutura esperada por `services.caixa`.

    Parâmetros:
    - `vendas`: linhas de `sales` (usa `sale_date`, `total_value`).
    - `custos_fixos`: linhas de `fixed_costs` (usa `cost_date`, `amount`, `category`).
    - `custos_animal`: linhas de `animal_costs` (usa `cost_date`, `amount`, `cost_type`).
    - `compras_insumo`: linhas de `insumo_transactions` com `type == "compra"`.
       Usa `transaction_date`, `quantity` e `insumo.cost_per_unit`.
    - `contas_pagar`/`contas_receber`: parcelas (`repositories.compras`/
       `repositories.financeiro`). Usa `valor`, `vencimento`, `data_pagamento`/
       `data_recebimento` — `competencia` sai `None` de propósito: a receita/
       despesa já foi reconhecida no lançamento de origem (a venda, a compra);
       aqui é só o CRONOGRAMA de caixa dela, não um fato novo. Por isso
       `resultado_por_competencia` nunca conta estas linhas (ela ignora
       `competencia=None`) — quem monta a lista para
       `services.caixa.fluxo_de_caixa`/`em_aberto` precisa excluir da fonte
       original (`vendas`/`compras_insumo`) o que já tem parcela aqui, senão
       o mesmo evento é contado duas vezes. Ver `app.py::_fin_lancamentos_caixa`.

    Retorna uma lista de dicionários no formato:
      {"tipo": "receita" | "despesa", "valor": float, "categoria": str,
       "competencia": "AAAA-MM-DD" | None, "vencimento": "AAAA-MM-DD" | None,
       "pagamento": "AAAA-MM-DD" | None}
    """
    resultado = []

    # 1. Vendas -> Receita
    if vendas:
        for v in vendas:
            if not isinstance(v, dict):
                continue
            dt = v.get("sale_date") or v.get("data") or v.get("date")
            dt_str = _safe_str(dt, "") or None
            valor = _safe_float(
                v.get("total_value")
                if v.get("total_value") is not None
                else v.get("valor")
            )
            resultado.append({
                "tipo": "receita",
                "valor": valor,
                "categoria": "venda",
                "competencia": dt_str,
                "vencimento": dt_str,
                "pagamento": dt_str,
            })

    # 2. Custos Fixos -> Despesa
    if custos_fixos:
        for cf in custos_fixos:
            if not isinstance(cf, dict):
                continue
            dt = cf.get("cost_date") or cf.get("data") or cf.get("date")
            dt_str = _safe_str(dt, "") or None
            raw_amount = (
                cf.get("amount")
                if cf.get("amount") is not None
                else cf.get("valor")
            )
            valor = _safe_float(raw_amount)
            raw_cat = (
                cf.get("category")
                if cf.get("category") is not None
                else cf.get("categoria")
            )
            cat = _safe_str(raw_cat, "")
            resultado.append({
                "tipo": "despesa",
                "valor": valor,
                "categoria": cat,
                "competencia": dt_str,
                "vencimento": dt_str,
                "pagamento": dt_str,
            })

    # 3. Custos de Animais -> Despesa
    if custos_animal:
        for ca in custos_animal:
            if not isinstance(ca, dict):
                continue
            dt = ca.get("cost_date") or ca.get("data") or ca.get("date")
            dt_str = _safe_str(dt, "") or None
            raw_amount = (
                ca.get("amount")
                if ca.get("amount") is not None
                else ca.get("valor")
            )
            valor = _safe_float(raw_amount)
            raw_cat = (
                ca.get("cost_type")
                if ca.get("cost_type") is not None
                else ca.get("categoria")
            )
            cat = _safe_str(raw_cat, "")
            resultado.append({
                "tipo": "despesa",
                "valor": valor,
                "categoria": cat,
                "competencia": dt_str,
                "vencimento": dt_str,
                "pagamento": dt_str,
            })

    # 4. Compras de Insumo -> Despesa (apenas type == "compra")
    if compras_insumo:
        for ci in compras_insumo:
            if not isinstance(ci, dict):
                continue
            tipo_transacao = _safe_str(
                ci.get("type") or ci.get("tipo"), ""
            ).strip().lower()
            if tipo_transacao != "compra":
                continue

            dt = ci.get("transaction_date") or ci.get("data") or ci.get("date")
            dt_str = _safe_str(dt, "") or None

            qty = _safe_float(
                ci.get("quantity")
                if ci.get("quantity") is not None
                else ci.get("quantidade"),
                0.0,
            )

            insumo_info = ci.get("insumo")
            if isinstance(insumo_info, dict):
                raw_cpu = (
                    insumo_info.get("cost_per_unit")
                    if insumo_info.get("cost_per_unit") is not None
                    else insumo_info.get("custo_unitario")
                )
                cost_per_unit = _safe_float(raw_cpu, 0.0)
                cat = _safe_str(
                    insumo_info.get("name") or insumo_info.get("nome"), ""
                )
            else:
                cost_per_unit = 0.0
                cat = _safe_str(ci.get("category") or ci.get("categoria"), "")

            valor = qty * cost_per_unit

            resultado.append({
                "tipo": "despesa",
                "valor": valor,
                "categoria": cat,
                "competencia": dt_str,
                "vencimento": dt_str,
                "pagamento": dt_str,
            })

    # 5. Contas a pagar -> Despesa (cronograma de caixa; sem competência aqui)
    if contas_pagar:
        for cp in contas_pagar:
            if not isinstance(cp, dict):
                continue
            resultado.append({
                "tipo": "despesa",
                "valor": _safe_float(cp.get("valor")),
                "categoria": _safe_str(cp.get("descricao"), "conta a pagar"),
                "competencia": None,
                "vencimento": _safe_str(cp.get("vencimento"), "") or None,
                "pagamento": _safe_str(cp.get("data_pagamento"), "") or None,
            })

    # 6. Contas a receber -> Receita (cronograma de caixa; sem competência aqui)
    if contas_receber:
        for cr in contas_receber:
            if not isinstance(cr, dict):
                continue
            resultado.append({
                "tipo": "receita",
                "valor": _safe_float(cr.get("valor")),
                "categoria": _safe_str(cr.get("descricao"), "conta a receber"),
                "competencia": None,
                "vencimento": _safe_str(cr.get("vencimento"), "") or None,
                "pagamento": _safe_str(cr.get("data_recebimento"), "") or None,
            })

    return resultado
