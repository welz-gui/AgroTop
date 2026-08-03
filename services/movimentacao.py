"""Pré-validação de saída de movimentação (PNIB §8.3 e §8.4).

Função pura: tudo entra por parâmetro, nada consulta banco. Quem apura o
contexto é `repositories/movimentacoes.py`.

**Os três níveis do §8.4 não são decoração.** Eles definem o que o sistema faz:

- `informativo` — permite continuar, só registra;
- `alerta` — exige confirmação e justificativa de quem avaliou;
- `bloqueio` — impede a operação sem autorização ou regularização.

Confundir alerta com bloqueio trava o usuário sem prova; confundir bloqueio com
alerta deixa sair animal morto. A gravidade é a regra, não um enfeite.
"""

from datetime import date, datetime
from typing import Optional

# §8.1 — tipos previstos. Vocabulário, não restrição de banco: a portaria prevê
# "outra prevista na regulamentação", então a lista precisa poder crescer.
TIPOS = (
    "entre_propriedades_mesmo_titular", "entre_titulares_diferentes",
    "venda", "compra", "remate", "emprestimo", "parceria", "exposicao",
    "evento_agropecuario", "retorno", "frigorifico", "confinamento",
    "temporaria", "sanitaria", "outra",
)

# Finalidades que caracterizam abate — carência impede estas, não as demais.
FINALIDADES_ABATE = ("frigorifico", "abate")

NIVEIS = ("informativo", "alerta", "bloqueio")


def _data(valor) -> Optional[date]:
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _p(codigo: str, gravidade: str, mensagem: str) -> dict:
    return {"codigo": codigo, "gravidade": gravidade, "mensagem": mensagem}


def pre_validar_saida(movimentacao: dict, animais: list[dict],
                      contexto: Optional[dict] = None) -> list[dict]:
    """Problemas antes de liberar a saída. Lista vazia = pode liberar.

    `movimentacao`: {
        "tipo", "propriedade_origem_id", "propriedade_destino_id",
        "finalidade", "data_prevista", "gta_numero", "status",
    }
    `animais`: [{
        "id", "uuid", "status", "property_id",
        "tem_identificacao_oficial": bool,
        "carencia_ate": "AAAA-MM-DD" | None,
    }, ...]
    `contexto`: {
        "hoje": "AAAA-MM-DD",
        "animais_em_outra_movimentacao": [uuid, ...],
        "eventos_pendentes_de_sincronizacao": int,
        "identificacao_obrigatoria": bool,   # §4.1 vira exigível em 2033
    }

    Chave ausente no contexto faz a validação correspondente ser **pulada**,
    não falhar — mesmo contrato de `services/validacao_regulatoria.py`.
    """
    contexto = contexto or {}
    problemas: list[dict] = []
    hoje = _data(contexto.get("hoje")) or date.today()

    # ── A movimentação em si ─────────────────────────────────────────────────
    if movimentacao.get("status") == "concluida":
        problemas.append(_p("movimentacao_ja_concluida", "bloqueio",
                            "Movimentação já concluída não pode ser liberada de novo."))

    origem = movimentacao.get("propriedade_origem_id")
    destino = movimentacao.get("propriedade_destino_id")
    if origem and destino and origem == destino:
        problemas.append(_p("origem_igual_ao_destino", "bloqueio",
                            "Origem e destino são a mesma propriedade."))

    if movimentacao.get("tipo") not in TIPOS:
        problemas.append(_p("tipo_desconhecido", "alerta",
                            f"Tipo de movimentação não previsto: "
                            f"'{movimentacao.get('tipo')}'."))

    prevista = _data(movimentacao.get("data_prevista"))
    if prevista and prevista < hoje:
        problemas.append(_p("data_prevista_no_passado", "alerta",
                            f"Data prevista {prevista.isoformat()} já passou."))

    if not movimentacao.get("gta_numero"):
        problemas.append(_p("sem_gta", "alerta",
                            "Movimentação sem GTA informada."))

    # ── Os animais ───────────────────────────────────────────────────────────
    if not animais:
        problemas.append(_p("sem_animais", "bloqueio",
                            "Nenhum animal na movimentação."))

    em_outra = set(contexto.get("animais_em_outra_movimentacao") or [])
    exige_id = contexto.get("identificacao_obrigatoria")
    abate = (movimentacao.get("finalidade") or "").lower() in FINALIDADES_ABATE \
        or movimentacao.get("tipo") == "frigorifico"

    for a in animais:
        rot = a.get("id") or a.get("uuid")

        if a.get("status") in ("morto", "abatido"):
            problemas.append(_p("animal_morto_ou_abatido", "bloqueio",
                                f"Animal {rot} está {a['status']}."))

        if origem and a.get("property_id") and a["property_id"] != origem:
            problemas.append(_p("animal_de_outra_propriedade", "bloqueio",
                                f"Animal {rot} não pertence à propriedade de origem."))

        if a.get("uuid") in em_outra:
            problemas.append(_p("animal_em_outra_movimentacao", "bloqueio",
                                f"Animal {rot} já está em outra movimentação aberta."))

        if exige_id and not a.get("tem_identificacao_oficial"):
            problemas.append(_p("sem_identificacao_obrigatoria", "bloqueio",
                                f"Animal {rot} sem identificação oficial."))

        carencia = _data(a.get("carencia_ate"))
        if carencia and carencia >= hoje:
            # Carência impede ABATE, não movimentação. Bloquear transferência
            # entre pastos por causa dela é excesso que atrapalha o manejo.
            if abate:
                problemas.append(_p("animal_em_carencia", "bloqueio",
                                    f"Animal {rot} em carência até "
                                    f"{carencia.isoformat()} e destino é abate."))
            else:
                problemas.append(_p("animal_em_carencia_sem_abate", "informativo",
                                    f"Animal {rot} em carência até "
                                    f"{carencia.isoformat()}; destino não é abate."))

    # ── Sincronização pendente (§8.3) ────────────────────────────────────────
    pend = contexto.get("eventos_pendentes_de_sincronizacao")
    if pend:
        problemas.append(_p("sincronizacao_pendente", "alerta",
                            f"{pend} evento(s) ainda não comunicados ao sistema oficial."))

    return problemas


def pode_liberar(problemas: list[dict]) -> bool:
    """Só bloqueio impede. Alerta exige confirmação, que é decisão de quem opera."""
    return not any(p["gravidade"] == "bloqueio" for p in problemas)


def exige_confirmacao(problemas: list[dict]) -> bool:
    return any(p["gravidade"] == "alerta" for p in problemas)


def resumo(problemas: list[dict]) -> dict:
    """Contagem por nível — o que a interface mostra antes de o usuário decidir."""
    return {nivel: sum(1 for p in problemas if p["gravidade"] == nivel)
            for nivel in NIVEIS}
