"""Validação de vínculo materno e consistência genealógica para o AgroTop (função pura)."""

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


def _calcular_idade_meses(nasc_mae: date, nasc_cria: date) -> int:
    """Calcula idade exata em meses entre o nascimento da mãe e o nascimento da cria."""
    meses = (nasc_cria.year - nasc_mae.year) * 12 + (
        nasc_cria.month - nasc_mae.month
    )
    if nasc_cria.day < nasc_mae.day:
        meses -= 1
    return max(0, meses)


def validar_vinculo(
    cria: dict, mae: dict | None, contexto: dict | None = None
) -> list[dict]:
    """Problemas no vínculo materno. Lista vazia = consistente.

    `cria`: {"id", "sexo", "nascimento", "propriedade_id"}
    `mae`:  {"id", "sexo", "nascimento", "propriedade_id", "morte"} | None
    `contexto`: {
        "hoje": "AAAA-MM-DD",
        "idade_minima_parto_meses": int,       # padrão 18
        "intervalo_minimo_partos_dias": int,   # padrão 270
        "partos_anteriores": ["AAAA-MM-DD", ...],
    }

    Retorna [{"codigo": str, "gravidade": "bloqueio"|"alerta"|"informativo",
              "mensagem": str, "campo": str | None}, ...]
    """
    if not isinstance(cria, dict):
        return []

    if contexto is None:
        contexto = {}

    erros: list[dict] = []

    if mae is None:
        return [
            {
                "codigo": "sem_mae_vinculada",
                "gravidade": "informativo",
                "mensagem": "Cria cadastrada sem mãe vinculada.",
                "campo": "mae_id",
            }
        ]

    if not isinstance(mae, dict):
        return []

    mae_id = mae.get("id", "desconhecida")
    sexo_mae = str(mae.get("sexo", "")).strip().upper()
    if sexo_mae in ("M", "MACHO", "MASCULINO") or (
        sexo_mae and sexo_mae not in ("F", "FEMEA", "FÊMEA", "FEMININO")
    ):
        erros.append({
            "codigo": "mae_macho",
            "gravidade": "bloqueio",
            "mensagem": f"Mãe {mae_id} informada possui sexo masculino ('{mae.get('sexo')}').",
            "campo": "sexo",
        })

    nasc_cria = _parse_date(cria.get("nascimento"))
    nasc_mae = _parse_date(mae.get("nascimento"))
    morte_mae = _parse_date(mae.get("morte"))

    if nasc_cria and nasc_mae:
        if nasc_mae >= nasc_cria:
            erros.append({
                "codigo": "mae_mais_nova_que_cria",
                "gravidade": "bloqueio",
                "mensagem": (
                    f"Data de nascimento da mãe {mae_id} ({nasc_mae.strftime('%d/%m/%Y')}) "
                    f"é posterior ou igual ao nascimento da cria ({nasc_cria.strftime('%d/%m/%Y')})."
                ),
                "campo": "nascimento",
            })
        else:
            idade_meses = _calcular_idade_meses(nasc_mae, nasc_cria)
            idade_minima = int(
                contexto.get("idade_minima_parto_meses", 18) or 18
            )
            if idade_meses < idade_minima:
                erros.append({
                    "codigo": "mae_jovem_demais",
                    "gravidade": "bloqueio",
                    "mensagem": (
                        f"Mãe {mae_id} tinha {idade_meses} meses na data do parto em {nasc_cria.strftime('%d/%m/%Y')} "
                        f"(nascida em {nasc_mae.strftime('%d/%m/%Y')}), abaixo do mínimo de {idade_minima} meses."
                    ),
                    "campo": "nascimento",
                })

    if nasc_cria and morte_mae:
        if nasc_cria > morte_mae:
            erros.append({
                "codigo": "parto_apos_morte_da_mae",
                "gravidade": "bloqueio",
                "mensagem": (
                    f"Nascimento da cria em {nasc_cria.strftime('%d/%m/%Y')} ocorreu após "
                    f"a data de morte da mãe {mae_id} ({morte_mae.strftime('%d/%m/%Y')})."
                ),
                "campo": "nascimento",
            })

    if nasc_cria:
        partos_anteriores = contexto.get("partos_anteriores")
        if isinstance(partos_anteriores, list) and partos_anteriores:
            intervalo_minimo_dias = int(
                contexto.get("intervalo_minimo_partos_dias", 270) or 270
            )
            for p_raw in partos_anteriores:
                p_dt = _parse_date(p_raw)
                if p_dt and p_dt <= nasc_cria:
                    dias_intervalo = (nasc_cria - p_dt).days
                    if dias_intervalo < intervalo_minimo_dias:
                        erros.append({
                            "codigo": "intervalo_entre_partos_curto",
                            "gravidade": "alerta",
                            "mensagem": (
                                f"Intervalo de {dias_intervalo} dias entre este parto ({nasc_cria.strftime('%d/%m/%Y')}) "
                                f"e o parto anterior ({p_dt.strftime('%d/%m/%Y')}) é menor que o mínimo de {intervalo_minimo_dias} dias."
                            ),
                            "campo": "nascimento",
                        })
                        break

    prop_cria = cria.get("propriedade_id")
    prop_mae = mae.get("propriedade_id")
    if prop_cria and prop_mae and str(prop_cria) != str(prop_mae):
        erros.append({
            "codigo": "mae_em_outra_propriedade",
            "gravidade": "alerta",
            "mensagem": (
                f"Mãe {mae_id} está cadastrada na propriedade '{prop_mae}', "
                f"enquanto a cria nasceu na propriedade '{prop_cria}'."
            ),
            "campo": "propriedade_id",
        })

    return erros
