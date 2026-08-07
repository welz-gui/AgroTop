"""Regras zootécnicas puras: idade, arroba, peso estimado, GMD de vida.

Sem SQL e sem Streamlit — importável pela API, pelo app mobile e por jobs.
Ver ROADMAP.md R8 (regra de negócio em um só lugar) e R9.
"""

from datetime import datetime, date
from typing import Optional

from .constantes import AGE_BANDS, CARCASS_YIELD, KG_PER_ARROBA


def _months_between(d_start: date, d_end: date) -> int:
    """Diferença em meses cheios entre duas datas."""
    months = (d_end.year - d_start.year) * 12 + (d_end.month - d_start.month)
    if d_end.day < d_start.day:
        months -= 1
    return max(months, 0)


def get_age_months(birth_date_str: Optional[str]) -> Optional[int]:
    """Idade atual em meses (avança automaticamente com o tempo)."""
    if not birth_date_str:
        return None
    try:
        birth = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        return _months_between(birth, date.today())
    except ValueError:
        return None


def get_age_category(birth_date_str: Optional[str], sex: Optional[str] = None) -> str:
    """Categoria por faixa etária. O parâmetro sex é mantido por compatibilidade."""
    months = get_age_months(birth_date_str)
    if months is None:
        return "Sem idade"
    if months <= 12: return AGE_BANDS[0]
    if months <= 24: return AGE_BANDS[1]
    if months <= 36: return AGE_BANDS[2]
    return AGE_BANDS[3]


def get_age_display(animal: dict) -> str:
    """Texto de idade para exibição, indicando se é estimada."""
    months = get_age_months(animal.get("birth_date"))
    if months is None:
        return "—"
    est = " (est.)" if animal.get("birth_estimated") else ""
    years, rem = divmod(months, 12)
    if years and rem:
        base = f"{years}a {rem}m"
    elif years:
        base = f"{years} ano{'s' if years > 1 else ''}"
    else:
        base = f"{months} mes{'es' if months != 1 else ''}"
    return f"{base}{est}"


def kg_to_arrobas(weight_kg: float, yield_: float = CARCASS_YIELD) -> float:
    return round(weight_kg * yield_ / KG_PER_ARROBA, 2)


def estimate_weight_by_measurement(girth_cm: float, length_cm: float) -> float:
    """Estima o peso vivo (kg) a partir do perímetro torácico e do comprimento
    corporal, usando a fórmula de Schaeffer convertida para o sistema métrico:
        Peso(lb) = (PT_pol² × Comp_pol) / 300
    Convertida para cm→kg resulta no fator ~1/10838."""
    if girth_cm <= 0 or length_cm <= 0:
        return 0.0
    return round((girth_cm ** 2) * length_cm / 10838.0, 1)


def calculate_gmd_total(animal: dict) -> Optional[float]:
    """GMD de vida: (peso atual − peso de entrada) ÷ dias desde a entrada.
    Tendência geral do animal na fazenda (recebe o dict do animal)."""
    try:
        entrada = date.fromisoformat(animal["entry_date"])
        dias = (date.today() - entrada).days
        if dias <= 0:
            return None
        return round((animal["current_weight"] - animal["entry_weight"]) / dias, 3)
    except (ValueError, KeyError, TypeError):
        return None


def calculate_gmd_total_bulk(animals: list[dict]) -> dict[str, Optional[float]]:
    """
    GMD de vida em massa. Retorna um dicionário {animal_id: GMD total}.
    Pre-calcula 'hoje' uma única vez para otimização em listas grandes.
    """
    hoje = date.today()
    result = {}
    for a in animals:
        aid = a["id"]
        try:
            entrada = date.fromisoformat(a["entry_date"])
            dias = (hoje - entrada).days
            if dias <= 0:
                result[aid] = None
            else:
                result[aid] = round((a["current_weight"] - a["entry_weight"]) / dias, 3)
        except (ValueError, KeyError, TypeError):
            result[aid] = None
    return result
