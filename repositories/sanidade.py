"""Medicamentos, protocolos sanitários e carência.

Camada de dados (ROADMAP.md R1/R9): aqui mora o SQL, e só aqui.
Sem regra de negócio — cálculo e decisão ficam em `services/`.
Sem Streamlit no topo do módulo.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from .animais import get_all_animals
from .animais import uuid_de
from . import eventos
from .conexao import _cache, _conn, _writes
from services.tratamento import TratamentoInvalido, normalizar_produto
from services.zootecnia import get_age_months


@dataclass
class MedicationData:
    animal_id: str
    medication_name: str
    dose: float
    unit: str
    application_route: str
    withdrawal_days: int
    med_date: str
    applied_by: str = ""
    insumo_id: Optional[int] = None
    notes: str = ""
    protocol_id: Optional[int] = None
    # Produto aplicado (opcionais). Princípio ativo vazio + insumo ligado = usa o do
    # cadastro do insumo. Validade (AAAA-MM-DD) anterior à data da aplicação é recusada.
    principio_ativo: str = ""
    lote_produto: str = ""
    validade_produto: str = ""


@dataclass
class ProtocolData:
    name: str
    sex_target: str
    age_min: int
    age_max: int
    dose_value: float
    dose_ref_kg: float
    dose_unit: str
    insumo_id: Optional[str]
    frequency: str
    withdrawal_days: int
    route: str = "Subcutânea"
    notes: str = ""


@_cache
def _medications_by_animal() -> dict:
    """Todos os medicamentos agrupados por animal (mais recente primeiro). 1 consulta."""
    with _conn() as con:
        rows = con.execute(
            """SELECT m.*, a.id AS animal_id
               FROM medications m JOIN animals a ON a.uuid=m.animal_uuid
               WHERE m.cancelada_em IS NULL
               ORDER BY m.med_date DESC, m.id DESC"""
        ).fetchall()
    out: dict = {}
    for r in rows:
        out.setdefault(r["animal_id"], []).append(dict(r))
    return out


def get_medications(animal_id: str, limit: Optional[int] = None) -> list[dict]:
    """Aplicações **vigentes** do animal. As canceladas ficam em `get_medication_history`."""
    meds = _medications_by_animal().get(animal_id, [])
    return meds[:limit] if limit is not None else list(meds)


def get_medication_history(animal_id: str) -> list[dict]:
    """Todas as aplicações do animal, vigentes e canceladas (sem cache): é o histórico
    que a ficha mostra para a correção ficar visível ao lado do original."""
    with _conn() as con:
        rows = con.execute(
            """SELECT m.*, a.id AS animal_id
               FROM medications m JOIN animals a ON a.uuid=m.animal_uuid
               WHERE a.id=?
               ORDER BY m.med_date DESC, m.id DESC""", (animal_id,)).fetchall()
    return [dict(r) for r in rows]


@_writes
def add_medication(data: MedicationData) -> None:
    with _conn() as con:
        _inserir_aplicacao(con, data)


def _inserir_aplicacao(con, data: MedicationData, *, corrige_id: Optional[int] = None,
                       evento_anterior_id: Optional[int] = None, versao: int = 1,
                       justificativa: str = "") -> int:
    """Grava a aplicação, a baixa de estoque e o evento, na conexão do chamador.

    `corrige_id`/`evento_anterior_id`/`versao`/`justificativa` só vêm de uma correção:
    ligam a linha nova (e o evento novo) ao que ela substitui. Devolve o id da aplicação.
    """
    _uuid = uuid_de(con, data.animal_id)
    if _uuid is None:
        raise ValueError(f"Animal {data.animal_id} não encontrado.")
    produto = normalizar_produto(
        data.principio_ativo, data.lote_produto, data.validade_produto, data.med_date)
    if not produto["principio_ativo"] and data.insumo_id:
        r = con.execute("SELECT principio_ativo FROM insumos WHERE id=?",
                        (data.insumo_id,)).fetchone()
        produto["principio_ativo"] = (r["principio_ativo"] or "") if r else ""
    # `vacinacao` e `tratamento` sao tipos proprios no §6.1; sem campo que
    # distinga um do outro, `manejo_sanitario` e o termo honesto.
    evento = eventos.registrar_em(
        con, _uuid, "manejo_sanitario", ocorrido_em=data.med_date,
        usuario_registro=data.applied_by,
        justificativa=justificativa, evento_anterior_id=evento_anterior_id, versao=versao,
        observacoes=f"{data.medication_name} {data.dose}{data.unit}"
                    + (f", principio ativo {produto['principio_ativo']}" if produto["principio_ativo"] else "")
                    + (f", lote {produto['lote_produto']}" if produto["lote_produto"] else "")
                    + (f", validade {produto['validade_produto']}" if produto["validade_produto"] else "")
                    + (f", carencia {data.withdrawal_days}d" if data.withdrawal_days else ""))
    medication_id = con.execute(
        """INSERT INTO medications
           (animal_uuid,medication_name,dose,unit,application_route,
            withdrawal_days,med_date,applied_by,insumo_id,notes,protocol_id,
            principio_ativo,lote_produto,validade_produto,evento_id,corrige_id)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           RETURNING id""",
        (_uuid, data.medication_name, data.dose, data.unit,
         data.application_route,
         data.withdrawal_days, data.med_date, data.applied_by, data.insumo_id or None, data.notes,
         data.protocol_id or None,
         produto["principio_ativo"] or None, produto["lote_produto"] or None,
         produto["validade_produto"] or None, evento.get("id"), corrige_id),
    ).fetchone()["id"]
    # Baixa automática no estoque
    if data.insumo_id and data.dose > 0:
        con.execute(
            "UPDATE insumos SET current_stock = MAX(0, current_stock - ?) WHERE id=?",
            (data.dose, data.insumo_id),
        )
        con.execute(
            """INSERT INTO insumo_transactions
               (insumo_id,type,quantity,reason,animal_uuid,transaction_date,operator)
               VALUES(?,?,?,?,?,?,?)""",
            (data.insumo_id, "saida", data.dose, "uso_animal", _uuid, data.med_date, data.applied_by),
        )

    # Atualiza status do animal se há carência
    if data.withdrawal_days and data.withdrawal_days > 0:
        con.execute(
            "UPDATE animals SET status='carencia' WHERE id=? AND status='ativo'",
            (data.animal_id,),
        )
    return medication_id


class AplicacaoNaoEncontrada(ValueError):
    """Não há aplicação com esse id."""


class AplicacaoJaCancelada(ValueError):
    """A aplicação já foi cancelada ou corrigida: não se corrige duas vezes a mesma linha."""


def _motivo(motivo) -> str:
    m = " ".join(str(motivo or "").split())
    if not m:
        raise TratamentoInvalido("Informe o motivo da correção.")
    return m


def _cancelar_em(con, medication_id: int, motivo: str, usuario: str, *,
                 registrar_estorno: bool, animal_id: Optional[str] = None) -> dict:
    """Marca a aplicação como cancelada e desfaz o que ela causou, na conexão do chamador.

    Desfaz a baixa de estoque (saída negativa, para as somas por motivo se anularem) e
    devolve o animal a `ativo` se a carência dele só vinha desta aplicação. Com
    `registrar_estorno`, grava o evento `estorno` apontando para o original; numa correção
    quem aponta para o original é o evento novo, e o estorno ficaria redundante.
    Devolve a linha cancelada (como era antes) e a versão do evento original.
    """
    m = con.execute(
        """SELECT m.*, a.id AS animal_id FROM medications m
           JOIN animals a ON a.uuid=m.animal_uuid WHERE m.id=?""", (medication_id,)).fetchone()
    if m is None or (animal_id is not None and m["animal_id"] != animal_id):
        raise AplicacaoNaoEncontrada(f"Aplicação {medication_id} não encontrada.")
    m = dict(m)
    if m["cancelada_em"]:
        raise AplicacaoJaCancelada(f"A aplicação {medication_id} já foi cancelada em {m['cancelada_em']}.")

    agora = eventos._agora()
    cur = con.execute(
        """UPDATE medications SET cancelada_em=?, cancelada_por=?, motivo_cancelamento=?
           WHERE id=? AND cancelada_em IS NULL""", (agora, usuario or None, motivo, medication_id))
    if cur.rowcount == 0:      # outro pedido cancelou entre a leitura e a escrita
        raise AplicacaoJaCancelada(f"A aplicação {medication_id} já foi cancelada.")

    # ponytail: se a baixa original foi cortada em zero (MAX(0, ...)), o estorno devolve a dose
    # inteira e o estoque passa do real; conferir no inventário se importar.
    if m["insumo_id"] and (m["dose"] or 0) > 0:
        con.execute("UPDATE insumos SET current_stock = current_stock + ? WHERE id=?",
                    (m["dose"], m["insumo_id"]))
        con.execute(
            """INSERT INTO insumo_transactions
               (insumo_id,type,quantity,reason,animal_uuid,transaction_date,operator,notes)
               VALUES(?,?,?,?,?,?,?,?)""",
            (m["insumo_id"], "saida", -float(m["dose"]), "uso_animal", m["animal_uuid"],
             date.today().isoformat(), usuario or None,
             f"Estorno da aplicação {medication_id}: {motivo}"))

    versao = 1
    if m["evento_id"]:
        ev = con.execute("SELECT versao FROM animal_events WHERE id=?", (m["evento_id"],)).fetchone()
        versao = (ev["versao"] if ev else 1) or 1
    if registrar_estorno:
        eventos.registrar_em(
            con, m["animal_uuid"], "estorno", usuario_registro=usuario, justificativa=motivo,
            evento_anterior_id=m["evento_id"], versao=versao + 1,
            observacoes=f"Cancelamento da aplicação de {m['medication_name']} "
                        f"{m['dose']}{m['unit']} de {m['med_date']}")

    # Se esta era a única carência vigente, o animal sai de `carencia`.
    vigentes = con.execute(
        """SELECT med_date, withdrawal_days FROM medications
           WHERE animal_uuid=? AND withdrawal_days>0 AND cancelada_em IS NULL""",
        (m["animal_uuid"],)).fetchall()
    hoje = date.today()
    ainda = False
    for r in vigentes:
        try:
            if datetime.strptime(r["med_date"], "%Y-%m-%d").date() + timedelta(days=r["withdrawal_days"]) > hoje:
                ainda = True
        except ValueError:
            ainda = True        # data ilegível: na dúvida, mantém a carência
    if not ainda:
        con.execute("UPDATE animals SET status='ativo' WHERE id=? AND status='carencia'", (m["animal_id"],))
    # Cópia serializável para a auditoria (o Postgres devolve Decimal/datas).
    foto = {k: (v if v is None or isinstance(v, (str, int, float)) else str(v)) for k, v in m.items()}
    return {"aplicacao": m, "foto": foto, "versao_evento": versao}


@_writes
def cancelar_medicamento(medication_id: int, motivo: str, usuario: str, *, origem: str = "web",
                         animal_id: Optional[str] = None) -> dict:
    """Cancela uma aplicação registrada por engano. A linha fica, marcada com o motivo.

    `animal_id`, quando informado, exige que a aplicação seja desse animal (a API passa o da URL).

    Levanta `TratamentoInvalido` (motivo vazio), `AplicacaoNaoEncontrada` ou
    `AplicacaoJaCancelada`; em qualquer uma nada é gravado.
    """
    motivo = _motivo(motivo)
    with _conn() as con:
        r = _cancelar_em(con, medication_id, motivo, usuario, registrar_estorno=True,
                         animal_id=animal_id)
        m = r["aplicacao"]
        eventos.auditar_em(
            con, "cancelar_aplicacao", usuario=usuario, entidade="medications",
            entidade_id=medication_id, registro_anterior=r["foto"], motivo=motivo, origem=origem)
    return {"cancelada": medication_id, "animal_id": m["animal_id"]}


@_writes
def corrigir_medicamento(medication_id: int, data: MedicationData, motivo: str, usuario: str, *,
                         origem: str = "web") -> dict:
    """Corrige uma aplicação: cancela a original e grava a certa, ligada a ela.

    O animal não muda: `data.animal_id` precisa ser o da aplicação, senão ela "não existe" para
    ele (aplicação no animal errado: cancele e registre no certo). A nova aplicação e o novo
    evento apontam para os originais e guardam o motivo. Tudo na mesma transação: ou as duas
    coisas acontecem ou nenhuma.
    """
    motivo = _motivo(motivo)
    with _conn() as con:
        r = _cancelar_em(con, medication_id, motivo, usuario, registrar_estorno=False,
                         animal_id=data.animal_id)
        m = r["aplicacao"]
        if not data.applied_by:
            data.applied_by = usuario
        nova = _inserir_aplicacao(
            con, data, corrige_id=medication_id, evento_anterior_id=m["evento_id"],
            versao=r["versao_evento"] + 1, justificativa=motivo)
        eventos.auditar_em(
            con, "corrigir_aplicacao", usuario=usuario, entidade="medications",
            entidade_id=medication_id, registro_anterior=r["foto"],
            registro_posterior={"nova_aplicacao": nova, "medicamento": data.medication_name,
                                "dose": data.dose, "unidade": data.unit, "data": data.med_date,
                                "carencia_dias": data.withdrawal_days,
                                "principio_ativo": data.principio_ativo, "lote": data.lote_produto,
                                "validade": data.validade_produto},
            motivo=motivo, origem=origem)
    return {"cancelada": medication_id, "nova": nova, "animal_id": m["animal_id"]}


def get_withdrawal_end(animal_id: str) -> Optional[date]:
    """Retorna a maior data de fim de carência ativa do animal, ou None."""
    rows = _medications_by_animal().get(animal_id, [])
    latest = None
    for r in rows:
        if not r["withdrawal_days"]:
            continue
        try:
            end = datetime.strptime(r["med_date"], "%Y-%m-%d").date() + timedelta(days=r["withdrawal_days"])
            if end > date.today() and (latest is None or end > latest):
                latest = end
        except ValueError:
            pass
    return latest


def get_withdrawal_end_batch(animal_ids: list[str]) -> dict[str, Optional[date]]:
    """Calcula o fim de carência em lote, usando Pandas para vetorização.
    Retorna um dicionário mapeando animal_id para a data de fim (date ou None)."""
    import pandas as pd

    meds_all = _medications_by_animal()
    wd_records = []

    for aid in animal_ids:
        rows = meds_all.get(aid, [])
        for r in rows:
            if r["withdrawal_days"]:
                wd_records.append({
                    "id": aid,
                    "med_date": r["med_date"],
                    "wd_days": r["withdrawal_days"]
                })

    if not wd_records:
        return {aid: None for aid in animal_ids}

    df = pd.DataFrame(wd_records)
    df["med_date"] = pd.to_datetime(df["med_date"])
    df["end_date"] = df["med_date"] + pd.to_timedelta(df["wd_days"], unit="D")

    if df.empty:
        return {aid: None for aid in animal_ids}

    df_max = df.groupby("id")["end_date"].max()
    # Converter para date e dicionário
    wd_dict = {aid: ts.date() for aid, ts in df_max.items()}

    return {aid: wd_dict.get(aid) for aid in animal_ids}


def get_protocols(active_only: bool = True) -> list[dict]:
    sql = ("SELECT p.*, i.name AS insumo_name, i.current_stock, i.unit AS insumo_unit "
           "FROM health_protocols p LEFT JOIN insumos i ON i.id=p.insumo_id WHERE 1=1")
    if active_only:
        sql += " AND p.active=1"
    sql += " ORDER BY p.name"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql).fetchall()]


@_writes
def add_protocol(data: ProtocolData) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO health_protocols
               (name,sex_target,age_min,age_max,dose_value,dose_ref_kg,dose_unit,
                insumo_id,frequency,withdrawal_days,route,notes)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data.name, data.sex_target, int(data.age_min), int(data.age_max), data.dose_value,
             data.dose_ref_kg, data.dose_unit, data.insumo_id or None, data.frequency,
             int(data.withdrawal_days), data.route, data.notes),
        )


@_writes
def set_protocol_active(pid: int, active: int) -> None:
    with _conn() as con:
        con.execute("UPDATE health_protocols SET active=? WHERE id=?", (int(active), pid))


@_writes
def delete_protocol(pid: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM health_protocols WHERE id=?", (pid,))


_FREQ_DAYS = {"anual": 365, "semestral": 182, "trimestral": 91, "mensal": 30}


def _protocol_eligible(protocol: dict, animal: dict) -> bool:
    stt = protocol.get("sex_target", "ambos")
    if stt in ("M", "F") and animal["sex"] != stt:
        return False
    months = get_age_months(animal.get("birth_date"))
    if months is None:
        return False
    return (protocol.get("age_min") or 0) <= months <= (protocol.get("age_max") or 999)


def _protocol_pending(protocol: dict, animal: dict, ref_date: date) -> bool:
    """True se o animal ainda precisa da aplicação no ciclo atual."""
    freq = protocol.get("frequency", "anual")
    aplicadas = [m for m in get_medications(animal["id"])
                 if m.get("protocol_id") == protocol["id"]]
    if not aplicadas:
        return True
    if freq == "unica":
        return False
    try:
        ultima = datetime.strptime(aplicadas[0]["med_date"], "%Y-%m-%d").date()
    except (ValueError, TypeError, KeyError):
        return True
    return (ref_date - ultima).days >= _FREQ_DAYS.get(freq, 365)


def get_protocol_plan(protocol: dict, ref_date: Optional[date] = None) -> dict:
    """Elegíveis, pendentes, doses necessárias e projeção de estoque."""
    ref = ref_date or date.today()
    animals = get_all_animals()
    elegiveis, pendentes = [], []
    idade_desconhecida = 0
    for a in animals:
        if get_age_months(a.get("birth_date")) is None:
            stt = protocol.get("sex_target", "ambos")
            if stt == "ambos" or a["sex"] == stt:
                idade_desconhecida += 1
            continue
        if not _protocol_eligible(protocol, a):
            continue
        elegiveis.append(a)
        if _protocol_pending(protocol, a, ref):
            pendentes.append(a)
    doses = round(sum(dose_for_animal(protocol, a) for a in pendentes), 2)
    stock = float(protocol.get("current_stock") or 0)
    return {
        "n_eligible": len(elegiveis),
        "n_pending":  len(pendentes),
        "pending":    pendentes,
        "doses_needed": doses,
        "stock":      round(stock, 2),
        "shortfall":  round(max(0.0, doses - stock), 2),
        "idade_desconhecida": idade_desconhecida,
    }


@_writes
def apply_protocol_campaign(protocol_id: int, med_date: str, operator: str = "", *,
                            lote_produto: str = "", validade_produto: str = "") -> dict:
    """Aplica o protocolo a todos os animais pendentes (registra + baixa estoque).

    `lote_produto` e `validade_produto` valem para o frasco usado na campanha toda; a
    validade é conferida ANTES de aplicar no primeiro animal, para a campanha não
    ficar pela metade com produto vencido.
    """
    prot = next((p for p in get_protocols(active_only=False) if p["id"] == protocol_id), None)
    if not prot:
        return {"n": 0, "doses": 0}
    normalizar_produto("", lote_produto, validade_produto, med_date)
    try:
        ref = datetime.strptime(med_date, "%Y-%m-%d").date()
    except ValueError:
        ref = date.today()
    plan = get_protocol_plan(prot, ref)
    n = 0
    for a in plan["pending"]:
        dose = dose_for_animal(prot, a)
        add_medication(MedicationData(
            animal_id=a["id"],
            medication_name=prot["name"],
            dose=dose,
            unit=prot["dose_unit"],
            application_route=prot.get("route", "Subcutânea"),
            withdrawal_days=prot.get("withdrawal_days", 0),
            med_date=med_date,
            applied_by=operator,
            insumo_id=prot.get("insumo_id"),
            notes="Campanha sanitária",
            protocol_id=prot["id"],
            lote_produto=lote_produto,
            validade_produto=validade_produto,
        ))
        n += 1
    return {"n": n, "doses": plan["doses_needed"]}


def dose_for_animal(protocol: dict, animal: dict) -> float:
    """Dose para um animal: fixa, ou proporcional ao peso (dose_ref_kg > 0)."""
    ref = protocol.get("dose_ref_kg") or 0
    if ref > 0:
        return round(animal["current_weight"] / ref * protocol["dose_value"], 2)
    return round(protocol["dose_value"], 2)
