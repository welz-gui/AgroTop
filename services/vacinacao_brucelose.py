"""Vacinação contra brucelose e o registro oficial no SDA (RS): regras puras.

O AgroTop NÃO registra nada no SDA (o módulo não tem API para terceiros). Aqui ficam as
contas do lado de cá: o prazo de lançamento e a situação dele. Sem banco, sem Streamlit.

Fonte do prazo e da obrigatoriedade: comunicado orientativo do PNCEBT/Seapi (20/10/2026).
A página da Seapi diz que a obrigatoriedade vem de uma Instrução Normativa ainda a publicar;
acompanhar (plano, seção 14).
"""

from datetime import date, datetime, timedelta

# Vacinações feitas a partir desta data têm lançamento no SDA exigido e prazo.
EXIGE_SDA_A_PARTIR_DE = date(2027, 1, 1)
DIA_LIMITE = 5
AVISAR_DIAS = 5

PENDENTE = "pendente_sda"
REGISTRADO = "registrado_sda"
EXCECAO = "excecao"
# `rascunho` (coleta offline) e `atestado_anexado` (arquivo do atestado, depende da D4) ainda
# não existem; o vocabulário do plano os reserva.
ESTADOS = (PENDENTE, REGISTRADO, EXCECAO)

# Idade da vacina B19 (meses): fora disso a vacinação ainda pode ser feita (RB51, por exemplo),
# mas merece um aviso para a pessoa conferir.
B19_IDADE_MESES = (3, 8)


class DadoInvalido(ValueError):
    """Dado da vacinação inválido. Nada é gravado."""


def _data(valor, rotulo: str) -> date:
    try:
        return datetime.strptime(str(valor or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        raise DadoInvalido(f"{rotulo} inválida: use o formato AAAA-MM-DD.") from None


def exige_sda(vacinado_em) -> bool:
    return _data(vacinado_em, "Data da vacinação") >= EXIGE_SDA_A_PARTIR_DE


def prazo_sda(vacinado_em) -> str | None:
    """Quinto dia do mês seguinte à vacinação, ou None se o lançamento ainda não é exigido."""
    d = _data(vacinado_em, "Data da vacinação")
    if d < EXIGE_SDA_A_PARTIR_DE:
        return None
    primeiro_do_mes_seguinte = (d.replace(day=1) + timedelta(days=32)).replace(day=1)
    return primeiro_do_mes_seguinte.replace(day=DIA_LIMITE).isoformat()


def situacao_do_prazo(status, prazo, hoje) -> str:
    """'cumprido', 'sem_prazo', 'atrasado', 'vencendo' (até AVISAR_DIAS dias) ou 'no_prazo'."""
    if status in (REGISTRADO, EXCECAO):
        return "cumprido"
    if not prazo:
        return "sem_prazo"
    h = hoje if isinstance(hoje, date) else _data(hoje, "Data de hoje")
    limite = _data(prazo, "Prazo")
    if h > limite:
        return "atrasado"
    if (limite - h).days <= AVISAR_DIAS:
        return "vencendo"
    return "no_prazo"


def normalizar_veterinario(nome, crmv="", uf="") -> dict:
    """Nome obrigatório; CRMV e UF opcionais (UF com duas letras)."""
    n = " ".join(str(nome or "").split())
    if not n:
        raise DadoInvalido("Informe o médico-veterinário responsável.")
    if len(n) > 120:
        raise DadoInvalido("Nome do veterinário muito longo (máximo 120 caracteres).")
    c = " ".join(str(crmv or "").split())
    if len(c) > 30:
        raise DadoInvalido("CRMV muito longo (máximo 30 caracteres).")
    u = str(uf or "").strip().upper()
    if u and (len(u) != 2 or not u.isalpha()):
        raise DadoInvalido("UF do CRMV deve ter duas letras (ex.: RS).")
    return {"veterinario_nome": n, "veterinario_crmv": c, "veterinario_uf": u}


def aviso_de_idade(produto, idade_meses) -> str | None:
    """Aviso (não bloqueio) quando a B19 é aplicada fora da faixa de 3 a 8 meses."""
    if idade_meses is None or "B19" not in str(produto or "").upper():
        return None
    minimo, maximo = B19_IDADE_MESES
    if minimo <= idade_meses <= maximo:
        return None
    return f"idade de {idade_meses} meses fora da faixa de {minimo} a {maximo} meses da B19"
