"""Motor de regras de recomendação técnica para o AgroTop."""

from datetime import date, datetime


def _parse_date(val) -> date | None:
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val.strip():
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(val.strip(), fmt).date()
            except ValueError:
                pass
    return None


def _regra_estoque_insuficiente(contexto: dict) -> list[dict]:
    recomended = []
    insumos = contexto.get("insumos")
    if not isinstance(insumos, list):
        return recomended

    for insumo in insumos:
        if not isinstance(insumo, dict):
            continue
        saldo = insumo.get("saldo")
        consumo_diario = insumo.get("consumo_diario")
        if (
            saldo is not None
            and consumo_diario is not None
            and consumo_diario > 0
        ):
            dias_restantes = saldo / consumo_diario
            if saldo < consumo_diario * 15:
                nome = insumo.get("nome", str(insumo.get("id", "")))
                recomended.append({
                    "regra": "estoque_insuficiente",
                    "severidade": "alta",
                    "titulo": f"Estoque insuficiente do insumo {nome}",
                    "motivo": (
                        f"Saldo atual de {saldo:.1f} unidades é suficiente para {dias_restantes:.1f} dias "
                        f"(consumo diário de {consumo_diario:.1f}), abaixo do mínimo recomendado de 15 dias."
                    ),
                    "dados": {
                        "insumo_id": insumo.get("id"),
                        "nome": nome,
                        "saldo": float(saldo),
                        "consumo_diario": float(consumo_diario),
                        "dias_restantes": round(dias_restantes, 1),
                    },
                    "acao": (
                        f"Providenciar compra ou reabastecimento do insumo {nome}."
                    ),
                })
    return recomended


def _regra_piquete_acima_da_capacidade(contexto: dict) -> list[dict]:
    recomended = []
    lotes = contexto.get("lotes")
    if not isinstance(lotes, list):
        return recomended

    for lote in lotes:
        if not isinstance(lote, dict):
            continue
        ua_atual = lote.get("ua_atual")
        capacidade_ua = lote.get("capacidade_ua")
        if (
            ua_atual is not None
            and capacidade_ua is not None
            and capacidade_ua > 0
        ):
            if ua_atual > capacidade_ua:
                nome = lote.get("nome", str(lote.get("id", "")))
                pct_excesso = (
                    (ua_atual - capacidade_ua) / capacidade_ua
                ) * 100
                recomended.append({
                    "regra": "piquete_acima_da_capacidade",
                    "severidade": "alta",
                    "titulo": f"Piquete/Lote {nome} acima da capacidade",
                    "motivo": (
                        f"{ua_atual:.1f} UA em um piquete com capacidade para {capacidade_ua:.1f} UA "
                        f"({pct_excesso:.0f}% acima)."
                    ),
                    "dados": {
                        "lote_id": lote.get("id"),
                        "ua_atual": float(ua_atual),
                        "capacidade_ua": float(capacidade_ua),
                        "excesso_ua": round(ua_atual - capacidade_ua, 1),
                    },
                    "acao": (
                        "Mover animais para outro piquete ou antecipar a venda dos mais pesados."
                    ),
                })
    return recomended


def _regra_animais(contexto: dict) -> list[dict]:
    recomended = []
    animais = contexto.get("animais")
    if not isinstance(animais, list):
        return recomended

    hoje_raw = contexto.get("hoje")
    hoje_dt = _parse_date(hoje_raw) if hoje_raw else date.today()

    for animal in animais:
        if not isinstance(animal, dict):
            continue

        animal_id = animal.get("id")
        peso = animal.get("peso")
        peso_alvo = animal.get("peso_alvo")
        carencia_ate_raw = animal.get("carencia_ate")
        carencia_dt = (
            _parse_date(carencia_ate_raw) if carencia_ate_raw else None
        )
        gmd = animal.get("gmd")
        meta_gmd = animal.get("meta_gmd", 0.5)

        if (
            peso is not None
            and peso_alvo is not None
            and peso >= peso_alvo
            and peso_alvo > 0
        ):
            if carencia_dt and carencia_dt > hoje_dt:
                carencia_str = carencia_dt.strftime("%Y-%m-%d")
                recomended.append({
                    "regra": "carencia_impede_abate",
                    "severidade": "alta",
                    "titulo": (
                        f"Animal {animal_id} atingiu peso-alvo mas está em período de carência"
                    ),
                    "motivo": (
                        f"Animal {animal_id} atingiu {peso:.1f} kg (alvo: {peso_alvo:.1f} kg), "
                        f"porém está em carência sanitária até {carencia_str}."
                    ),
                    "dados": {
                        "animal_id": animal_id,
                        "peso": float(peso),
                        "peso_alvo": float(peso_alvo),
                        "carencia_ate": carencia_str,
                    },
                    "acao": (
                        f"Aguardar o término da carência em {carencia_str} antes de efetuar o abate/venda."
                    ),
                })
            else:
                recomended.append({
                    "regra": "pronto_para_venda",
                    "severidade": "media",
                    "titulo": f"Animal {animal_id} pronto para venda/abate",
                    "motivo": (
                        f"Animal {animal_id} atingiu o peso-alvo de {peso_alvo:.1f} kg "
                        f"(peso atual: {peso:.1f} kg) e não possui restrições de carência."
                    ),
                    "dados": {
                        "animal_id": animal_id,
                        "peso": float(peso),
                        "peso_alvo": float(peso_alvo),
                    },
                    "acao": "Programar a venda ou abate do animal.",
                })

        if gmd is not None and meta_gmd is not None and gmd < meta_gmd:
            recomended.append({
                "regra": "gmd_abaixo_da_meta",
                "severidade": "media",
                "titulo": f"GMD do animal {animal_id} abaixo da meta",
                "motivo": (
                    f"GMD atual de {gmd:.2f} kg/dia está abaixo da meta estabelecida de {meta_gmd:.2f} kg/dia."
                ),
                "dados": {
                    "animal_id": animal_id,
                    "gmd": float(gmd),
                    "meta_gmd": float(meta_gmd),
                    "diferenca": round(meta_gmd - gmd, 2),
                },
                "acao": "Revisar dieta, suplementação ou saúde do animal.",
            })

    return recomended


def _regra_margem_em_risco(contexto: dict) -> list[dict]:
    recomended = []
    custo_por_arroba = contexto.get("custo_por_arroba")
    preco_arroba = contexto.get("preco_arroba")

    if custo_por_arroba is not None and preco_arroba is not None:
        if custo_por_arroba > preco_arroba:
            recomended.append({
                "regra": "margem_em_risco",
                "severidade": "alta",
                "titulo": "Custo por arroba supera o preço de mercado",
                "motivo": (
                    f"Custo por arroba produzido (R$ {custo_por_arroba:.2f}) "
                    f"é maior que o preço de venda esperado (R$ {preco_arroba:.2f})."
                ),
                "dados": {
                    "custo_por_arroba": float(custo_por_arroba),
                    "preco_arroba": float(preco_arroba),
                    "prejuizo_por_arroba": round(
                        custo_por_arroba - preco_arroba, 2
                    ),
                },
                "acao": (
                    "Revisar custos operacionais e de nutrição para restaurar a margem de lucro."
                ),
            })
    return recomended


REGRAS = [
    _regra_estoque_insuficiente,
    _regra_piquete_acima_da_capacidade,
    _regra_animais,
    _regra_margem_em_risco,
]


def avaliar(contexto: dict | None = None) -> list[dict]:
    """Aplica as regras ao estado da fazenda e devolve recomendações.

    `contexto` traz os dados já apurados — a função NÃO consulta o banco:
        {
          "animais": [{"id", "peso", "peso_alvo", "gmd", "lote_id",
                       "carencia_ate": "AAAA-MM-DD"|None}, ...],
          "lotes":   [{"id", "capacidade_ua", "ua_atual"}, ...],
          "insumos": [{"id", "nome", "saldo", "consumo_diario"}, ...],
          "preco_arroba": float|None,
          "custo_por_arroba": float|None,
          "hoje": "AAAA-MM-DD",
        }

    Retorna lista de recomendações.
    """
    if contexto is None:
        contexto = {}

    resultado = []
    for fn_regra in REGRAS:
        resultado.extend(fn_regra(contexto))

    return resultado
