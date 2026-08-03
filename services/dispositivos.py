"""Controle de estoque de brincos e identificadores PNIB para o AgroTop (função pura)."""

import re


def _decompor_identificador(identificador: str) -> tuple[str, int, int]:
    """Decompõe um identificador no formato alfanumérico.

    Exemplo: "BR0001" -> ("BR", 1, 4) onde 4 é o número de dígitos (padding).
    Levanta ValueError se o formato for inválido.
    """
    if not isinstance(identificador, str) or not identificador.strip():
        raise ValueError("Identificador inválido ou vazio.")

    identificador = identificador.strip()
    match = re.match(r"^([A-Za-z_-]*?)(\d+)$", identificador)
    if not match:
        raise ValueError(
            f"Identificador '{identificador}' não possui sufixo numérico válido."
        )

    prefixo, sufixo_str = match.groups()
    num = int(sufixo_str)
    largura = len(sufixo_str)
    return prefixo, num, largura


def expandir_faixa(inicio: str, fim: str) -> list[str]:
    """Todos os números de uma faixa, inclusive nas pontas.

    Os identificadores têm prefixo alfanumérico e sufixo numérico
    ("BR0001".."BR0100"). O prefixo tem de ser idêntico nas duas pontas.
    Levanta ValueError se o prefixo divergir ou se `fim` < `inicio`.
    """
    pref_ini, num_ini, larg_ini = _decompor_identificador(inicio)
    pref_fim, num_fim, larg_fim = _decompor_identificador(fim)

    if pref_ini != pref_fim:
        raise ValueError(
            f"Prefixos divergentes entre início ('{pref_ini}') e fim ('{pref_fim}')."
        )

    if num_fim < num_ini:
        raise ValueError(
            f"Fim da faixa ('{fim}', num={num_fim}) é menor que o início ('{inicio}', num={num_ini})."
        )

    largura = max(larg_ini, larg_fim)
    return [f"{pref_ini}{n:0{largura}d}" for n in range(num_ini, num_fim + 1)]


def _numero_pertence_a_faixa(numero: str, faixa: dict) -> bool:
    """Verifica em O(1) se um número pertence ao intervalo de uma faixa."""
    try:
        pref_num, n_num, _ = _decompor_identificador(numero)
        pref_ini, n_ini, _ = _decompor_identificador(faixa.get("inicio", ""))
        pref_fim, n_fim, _ = _decompor_identificador(faixa.get("fim", ""))
    except ValueError:
        return False

    if pref_num != pref_ini or pref_ini != pref_fim:
        return False

    return n_ini <= n_num <= n_fim


def validar_aplicacao(
    numero: str, faixas: list[dict], aplicados: dict
) -> dict:
    """Este número pode ser aplicado agora?

    `faixas`: [{"inicio": str, "fim": str, "status": "disponivel"|"cancelada"}, ...]
    `aplicados`: {numero: {"animal_uuid": str, "status": "ativo"|"removido"}}

    Retorna {"pode": bool, "motivo": str, "codigo": str}
    """
    if not isinstance(numero, str) or not numero.strip():
        return {
            "pode": False,
            "motivo": "Número de brinco não informado.",
            "codigo": "fora_das_faixas",
        }

    numero = numero.strip()

    if not isinstance(faixas, list):
        faixas = []

    if not isinstance(aplicados, dict):
        aplicados = {}

    faixas_que_contem = [
        f for f in faixas if _numero_pertence_a_faixa(numero, f)
    ]

    if not faixas_que_contem:
        return {
            "pode": False,
            "motivo": f"Brinco {numero} não pertence a nenhuma faixa da propriedade.",
            "codigo": "fora_das_faixas",
        }

    faixas_ativas = [
        f for f in faixas_que_contem if f.get("status") != "cancelada"
    ]
    if not faixas_ativas:
        return {
            "pode": False,
            "motivo": f"Brinco {numero} pertence a uma faixa cancelada.",
            "codigo": "faixa_cancelada",
        }

    info_aplicado = aplicados.get(numero)
    if isinstance(info_aplicado, dict):
        status_ap = str(info_aplicado.get("status", "")).strip().lower()
        if status_ap == "ativo":
            animal_uuid = info_aplicado.get("animal_uuid", "")
            msg = f"Brinco {numero} já está ativo em outro animal"
            if animal_uuid:
                msg += f" (uuid: {animal_uuid})"
            msg += "."
            return {"pode": False, "motivo": msg, "codigo": "ja_aplicado_ativo"}
        elif status_ap == "removido":
            return {
                "pode": True,
                "motivo": f"Brinco {numero} esteve aplicado anteriormente, mas foi removido (reaproveitável).",
                "codigo": "reaproveitavel",
            }

    return {
        "pode": True,
        "motivo": f"Brinco {numero} disponível para aplicação.",
        "codigo": "disponivel",
    }


def situacao_do_estoque(faixas: list[dict], aplicados: dict) -> dict:
    """Quantos brincos restam.

    Cálculo otimizado em O(faixas + aplicados) sem materializar listas gigantes de números.

    Retorna {"total": int, "aplicados": int, "disponiveis": int,
             "percentual_usado": float,
             "proximos_disponiveis": [str, ...]}   # até 10
    """
    if not isinstance(faixas, list):
        faixas = []

    if not isinstance(aplicados, dict):
        aplicados = {}

    faixas_validas = []
    total_brincos = 0

    for f in faixas:
        if not isinstance(f, dict):
            continue
        if f.get("status") == "cancelada":
            continue

        ini_str = f.get("inicio")
        fim_str = f.get("fim")
        try:
            pref_i, num_i, larg_i = _decompor_identificador(ini_str)
            pref_f, num_f, larg_f = _decompor_identificador(fim_str)
            if pref_i == pref_f and num_f >= num_i:
                largura = max(larg_i, larg_f)
                tam = num_f - num_i + 1
                total_brincos += tam
                faixas_validas.append((pref_i, num_i, num_f, largura))
        except ValueError:
            continue

    # Contagem de ativos dentro de faixas válidas
    aplicados_ativos_count = 0
    for num_str, info in aplicados.items():
        if not isinstance(info, dict):
            continue
        if str(info.get("status", "")).strip().lower() == "ativo":
            # Verificar se pertence a alguma faixa válida
            for pref_i, num_i, num_f, _ in faixas_validas:
                try:
                    p_n, n_n, _ = _decompor_identificador(num_str)
                    if p_n == pref_i and num_i <= n_n <= num_f:
                        aplicados_ativos_count += 1
                        break
                except ValueError:
                    pass

    disponiveis_count = max(0, total_brincos - aplicados_ativos_count)
    percentual_usado = (
        round((aplicados_ativos_count / total_brincos) * 100.0, 2)
        if total_brincos > 0
        else 0.0
    )

    # Busca lazy dos até 10 próximos disponíveis (sem materializar faixas gigantes de 100k)
    proximos: list[str] = []
    for pref_i, num_i, num_f, largura in faixas_validas:
        if len(proximos) >= 10:
            break
        for n in range(num_i, num_f + 1):
            cand = f"{pref_i}{n:0{largura}d}"
            info = aplicados.get(cand)
            # Se não está em aplicados ou status != "ativo", está disponível
            if not isinstance(info, dict) or str(
                info.get("status", "")
            ).strip().lower() != "ativo":
                proximos.append(cand)
                if len(proximos) >= 10:
                    break

    return {
        "total": total_brincos,
        "aplicados": aplicados_ativos_count,
        "disponiveis": disponiveis_count,
        "percentual_usado": percentual_usado,
        "proximos_disponiveis": proximos,
    }
