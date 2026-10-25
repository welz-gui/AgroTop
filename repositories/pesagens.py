"""Pesagens e GMD recente.

`_weighings_by_animal` é bulk loader cacheado (ROADMAP R11): 1 consulta traz tudo,
o resto é leitura em memória. Não consultar por animal em laço.

Camada de dados (ROADMAP.md R1/R9): aqui mora o SQL, e só aqui.
Sem regra de negócio — cálculo e decisão ficam em `services/`.
Sem Streamlit no topo do módulo.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from . import eventos
from .conexao import _cache, _conn, _writes
from .revisao import (
    RegistroJaCancelado, RegistroNaoEncontrado, RevisaoNaoPermitida,
    foto, motivo_obrigatorio, versao_do_evento,
)


@dataclass
class WeighingCreate:
    animal_id: str
    weight: float
    weigh_date: str
    operator: str = ""
    notes: str = ""
    method: str = "pesado"


@_cache
def _weighings_by_animal() -> dict:
    """Todas as pesagens agrupadas por animal (mais recente primeiro). 1 consulta.

    A ligação é por `animal_uuid` (ADR 0004, etapa B1.6), mas o dicionário
    continua indexado pelo **brinco**: é o que a interface usa e o que os
    chamadores esperam. O `JOIN` faz essa tradução numa consulta só.
    """
    with _conn() as con:
        rows = con.execute(
            """SELECT w.*, a.id AS animal_id
               FROM weighings w JOIN animals a ON a.uuid=w.animal_uuid
               WHERE w.cancelada_em IS NULL
               ORDER BY w.weigh_date DESC, w.id DESC"""
        ).fetchall()
    out: dict = {}
    for r in rows:
        out.setdefault(r["animal_id"], []).append(dict(r))
    return out


def get_weighings(animal_id: str) -> list[dict]:
    return list(_weighings_by_animal().get(animal_id, []))


def get_weighings_batch(animal_ids: set[str]) -> dict[str, list[dict]]:
    """Busca pesagens apenas para os animais especificados numa única consulta."""
    if not animal_ids:
        return {}

    out: dict[str, list[dict]] = {}

    # Processa em lotes de 900 para evitar o limite de variáveis do SQLite
    animal_ids_list = list(animal_ids)
    batch_size = 900

    with _conn() as con:
        for i in range(0, len(animal_ids_list), batch_size):
            chunk = animal_ids_list[i:i + batch_size]
            placeholders = ",".join("?" * len(chunk))
            rows = con.execute(
                f"""SELECT w.*, a.id AS animal_id
                   FROM weighings w JOIN animals a ON a.uuid=w.animal_uuid
                   WHERE a.id IN ({placeholders}) AND w.cancelada_em IS NULL
                   ORDER BY w.weigh_date DESC, w.id DESC""", tuple(chunk)
            ).fetchall()

            for r in rows:
                out.setdefault(r["animal_id"], []).append(dict(r))

    return out


@_writes
def add_weighing(data: WeighingCreate) -> bool:
    """Registra a pesagem. Devolve True se ela passou a ser o peso atual do animal.

    Pesagem mais antiga que a última já registrada (ou que a entrada do animal)
    entra no histórico, mas não sobrescreve `current_weight`: a fila offline do
    mobile pode entregar uma pesagem de dias atrás depois de uma mais nova
    (ADR 0006, D2). Mesma data conta como mais nova, como sempre foi.
    """
    with _conn() as con:
        # Busca lote e uuid na mesma consulta (ADR 0004 etapa B1.4).
        a = con.execute(
            "SELECT lote_id, uuid, entry_date FROM animals WHERE id=?", (data.animal_id,)
        ).fetchone()
        if a is None:
            raise ValueError(f"Animal {data.animal_id} não encontrado.")
        ultima = con.execute(
            "SELECT MAX(weigh_date) AS d FROM weighings WHERE animal_uuid=? AND cancelada_em IS NULL",
            (a["uuid"],)
        ).fetchone()["d"]
        referencia = max((str(d)[:10] for d in (ultima, a["entry_date"]) if d), default="")
        # Evento na MESMA transação da pesagem (§6): ou entram os dois, ou nenhum.
        _inserir_pesagem(con, a["uuid"], a["lote_id"], data)
        eh_a_mais_recente = str(data.weigh_date)[:10] >= referencia
        if eh_a_mais_recente:
            con.execute("UPDATE animals SET current_weight=? WHERE id=?", (data.weight, data.animal_id))
    return eh_a_mais_recente


def _inserir_pesagem(con, animal_uuid: str, lote_id, data: WeighingCreate, *,
                     corrige_id: Optional[int] = None, evento_anterior_id: Optional[int] = None,
                     versao: int = 1, justificativa: str = "") -> int:
    """Grava a pesagem e o evento, na conexão do chamador. Devolve o id da pesagem.

    `corrige_id`/`evento_anterior_id`/`versao`/`justificativa` só vêm de uma correção.
    """
    evento = eventos.registrar_em(
        con, animal_uuid, "pesagem", ocorrido_em=data.weigh_date,
        usuario_registro=data.operator, observacoes=f"{data.weight} kg ({data.method})",
        justificativa=justificativa, evento_anterior_id=evento_anterior_id, versao=versao)
    return con.execute(
        """INSERT INTO weighings
           (animal_uuid,weight,weigh_date,lote_id,operator,method,notes,evento_id,corrige_id)
           VALUES(?,?,?,?,?,?,?,?,?) RETURNING id""",
        (animal_uuid, data.weight, data.weigh_date, lote_id, data.operator, data.method, data.notes,
         evento.get("id"), corrige_id),
    ).fetchone()["id"]


def get_weighing_history(animal_id: str) -> list[dict]:
    """Todas as pesagens do animal, vigentes e canceladas (sem cache): é o histórico que a
    ficha mostra para a correção ficar visível ao lado do original."""
    with _conn() as con:
        rows = con.execute(
            """SELECT w.*, a.id AS animal_id
               FROM weighings w JOIN animals a ON a.uuid=w.animal_uuid
               WHERE a.id=? ORDER BY w.weigh_date DESC, w.id DESC""", (animal_id,)).fetchall()
    return [dict(r) for r in rows]


def _recalcular_peso_atual(con, animal_id: str, animal_uuid: str) -> None:
    """`current_weight` volta a ser o da pesagem vigente mais recente (ou o peso de entrada,
    se nenhuma sobrar). É o que o animal pesa agora depois de cancelar ou corrigir."""
    ultima = con.execute(
        """SELECT weight FROM weighings WHERE animal_uuid=? AND cancelada_em IS NULL
           ORDER BY weigh_date DESC, id DESC LIMIT 1""", (animal_uuid,)).fetchone()
    if ultima is not None:
        con.execute("UPDATE animals SET current_weight=? WHERE id=?", (ultima["weight"], animal_id))
    else:
        con.execute("UPDATE animals SET current_weight=entry_weight WHERE id=?", (animal_id,))


def _cancelar_pesagem_em(con, weighing_id: int, motivo: str, usuario: str, *,
                         registrar_estorno: bool, animal_id: Optional[str] = None) -> dict:
    """Marca a pesagem como cancelada e acerta o peso atual, na conexão do chamador."""
    w = con.execute(
        """SELECT w.*, a.id AS animal_id FROM weighings w
           JOIN animals a ON a.uuid=w.animal_uuid WHERE w.id=?""", (weighing_id,)).fetchone()
    if w is None or (animal_id is not None and w["animal_id"] != animal_id):
        raise RegistroNaoEncontrado(f"Pesagem {weighing_id} não encontrada.")
    w = dict(w)
    if w["cancelada_em"]:
        raise RegistroJaCancelado(f"A pesagem {weighing_id} já foi cancelada em {w['cancelada_em']}.")
    if (w.get("operator") or "") == "Cadastro":
        raise RevisaoNaoPermitida(
            "A pesagem de entrada faz parte do cadastro do animal e não se cancela nem se corrige aqui.")
    cur = con.execute(
        """UPDATE weighings SET cancelada_em=?, cancelada_por=?, motivo_cancelamento=?
           WHERE id=? AND cancelada_em IS NULL""", (eventos._agora(), usuario or None, motivo, weighing_id))
    if cur.rowcount == 0:      # outro pedido cancelou entre a leitura e a escrita
        raise RegistroJaCancelado(f"A pesagem {weighing_id} já foi cancelada.")
    versao = versao_do_evento(con, w["evento_id"])
    if registrar_estorno:
        eventos.registrar_em(
            con, w["animal_uuid"], "estorno", usuario_registro=usuario, justificativa=motivo,
            evento_anterior_id=w["evento_id"], versao=versao + 1,
            observacoes=f"Cancelamento da pesagem de {w['weight']} kg de {w['weigh_date']}")
    return {"pesagem": w, "foto": foto(w), "versao_evento": versao}


@_writes
def cancelar_pesagem(weighing_id: int, motivo: str, usuario: str, *, origem: str = "web",
                     animal_id: Optional[str] = None) -> dict:
    """Cancela uma pesagem lançada por engano. A linha fica, marcada com o motivo, e o peso
    atual do animal volta a ser o da pesagem vigente mais recente.

    Levanta `RevisaoNaoPermitida` (motivo vazio, ou pesagem de entrada), `RegistroNaoEncontrado`
    ou `RegistroJaCancelado`; em qualquer uma nada é gravado.
    """
    motivo = motivo_obrigatorio(motivo)
    with _conn() as con:
        r = _cancelar_pesagem_em(con, weighing_id, motivo, usuario, registrar_estorno=True,
                                 animal_id=animal_id)
        w = r["pesagem"]
        _recalcular_peso_atual(con, w["animal_id"], w["animal_uuid"])
        eventos.auditar_em(
            con, "cancelar_pesagem", usuario=usuario, entidade="weighings", entidade_id=weighing_id,
            registro_anterior=r["foto"], motivo=motivo, origem=origem)
    return {"cancelada": weighing_id, "animal_id": w["animal_id"]}


@_writes
def corrigir_pesagem(weighing_id: int, data: WeighingCreate, motivo: str, usuario: str, *,
                     origem: str = "web") -> dict:
    """Corrige uma pesagem: cancela a original e grava a certa, ligada a ela.

    O animal não muda: `data.animal_id` precisa ser o da pesagem. A nova pesagem e o novo evento
    apontam para os originais e guardam o motivo, na mesma transação. O piquete registrado é o
    da original (onde o animal estava ao ser pesado).
    """
    motivo = motivo_obrigatorio(motivo)
    with _conn() as con:
        r = _cancelar_pesagem_em(con, weighing_id, motivo, usuario, registrar_estorno=False,
                                 animal_id=data.animal_id)
        w = r["pesagem"]
        if not data.operator:
            data.operator = w.get("operator") or usuario
        nova = _inserir_pesagem(
            con, w["animal_uuid"], w["lote_id"], data, corrige_id=weighing_id,
            evento_anterior_id=w["evento_id"], versao=r["versao_evento"] + 1, justificativa=motivo)
        _recalcular_peso_atual(con, w["animal_id"], w["animal_uuid"])
        eventos.auditar_em(
            con, "corrigir_pesagem", usuario=usuario, entidade="weighings", entidade_id=weighing_id,
            registro_anterior=r["foto"],
            registro_posterior={"nova_pesagem": nova, "peso": data.weight, "data": data.weigh_date,
                                "metodo": data.method},
            motivo=motivo, origem=origem)
    return {"cancelada": weighing_id, "nova": nova, "animal_id": w["animal_id"]}


def get_all_weighings() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT w.*, a.id AS animal_id, a.breed
               FROM weighings w JOIN animals a ON a.uuid=w.animal_uuid
               WHERE a.status='ativo' AND w.cancelada_em IS NULL ORDER BY w.weigh_date""",
        ).fetchall()
    return [dict(r) for r in rows]


def get_average_weighings_by_date() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT w.weigh_date AS "Data", AVG(w.weight) AS "Peso Médio (kg)"
               FROM weighings w JOIN animals a ON a.uuid=w.animal_uuid
               WHERE a.status='ativo' AND w.cancelada_em IS NULL
               GROUP BY w.weigh_date
               ORDER BY w.weigh_date"""
        ).fetchall()
    return [dict(r) for r in rows]


def calculate_gmd(animal_id: str) -> Optional[float]:
    """GMD recente: entre as duas últimas pesagens (como o animal está agora)."""
    ws = get_weighings(animal_id)
    if len(ws) < 2:
        return None
    try:
        d0 = date.fromisoformat(ws[0]["weigh_date"])
        d1 = date.fromisoformat(ws[1]["weigh_date"])
        days = abs((d0 - d1).days)
        return round((ws[0]["weight"] - ws[1]["weight"]) / days, 3) if days else None
    except (ValueError, KeyError):
        return None


def calculate_gmd_bulk(animal_ids: list[str]) -> dict[str, Optional[float]]:
    """
    GMD recente em massa. Retorna um dicionário {animal_id: GMD}.
    Evita chamadas repetitivas pegando o cache de uma vez e operando em memória.
    """
    all_ws = _weighings_by_animal()
    gmds = {}
    for aid in animal_ids:
        ws = all_ws.get(aid, [])
        if len(ws) < 2:
            gmds[aid] = None
            continue
        try:
            d0 = date.fromisoformat(ws[0]["weigh_date"])
            d1 = date.fromisoformat(ws[1]["weigh_date"])
            days = abs((d0 - d1).days)
            gmds[aid] = round((ws[0]["weight"] - ws[1]["weight"]) / days, 3) if days else None
        except (ValueError, KeyError, TypeError):
            gmds[aid] = None
    return gmds


def get_last_estimate(animal_id: str) -> Optional[dict]:
    """Retorna a pesagem estimada (operador ou medição) mais recente ainda não
    confirmada por uma pesagem real posterior. Usada para comparação."""
    ws = get_weighings(animal_id)  # já vem ordenado do mais recente ao mais antigo
    for w in ws:
        if w.get("method") in ("estimado", "medicao"):
            return w
        # se a mais recente já é 'pesado', não há estimativa pendente antes dela
        return None
    return None
