"""Nascimentos e vínculo materno (ADR 0004 · etapa B3 · PNIB §7).

O parto é **entidade própria**, e não um campo do animal, porque o §7.2 exige
que gêmeos gerem "animais distintos ligados ao mesmo parto". Com o parto no
animal, dois gêmeos teriam dois partos e a informação de que nasceram juntos se
perderia.

A validação biológica é `services/genealogia.py`, entregue pela spec 0022 —
função pura, sem banco. Aqui é a ligação: buscar mãe e contexto, chamar a regra,
e gravar só se ela permitir.

Camada de dados (ROADMAP R1/R9): aqui mora o SQL, e só aqui.
"""

import uuid as _uuid
from datetime import date
from typing import Optional

from services.genealogia import validar_vinculo

from . import eventos
from .animais import novo_uuid
from .conexao import _cache, _conn, _writes

ORIGENS = ("nascido", "comprado", "transferido", "importado")
TIPOS_PARTO = ("normal", "assistido", "cesarea")
CONDICOES = ("nascido_vivo", "natimorto")


def _novo_parto_id() -> str:
    return str(_uuid.uuid4())


def _contexto_da_mae(con, mae_uuid: str, data_parto: str) -> dict:
    """Monta o que `validar_vinculo` precisa saber sobre a mãe.

    A função pura não consulta banco (R31) — quem apura é aqui.
    """
    partos = con.execute(
        "SELECT data FROM partos WHERE mae_uuid=? AND data < ? ORDER BY data DESC",
        (mae_uuid, data_parto)).fetchall()
    return {
        "hoje": date.today().isoformat(),
        "partos_anteriores": [r["data"] for r in partos],
    }


def _dados_da_mae(con, mae_uuid: str) -> Optional[dict]:
    row = con.execute(
        """SELECT uuid AS id, sex, birth_date, property_id, status
           FROM animals WHERE uuid=?""", (mae_uuid,)).fetchone()
    if row is None:
        return None
    # A data de morte vive em `deaths`; o §7.2 exige a mãe ATIVA na data do parto.
    morte = con.execute(
        "SELECT death_date FROM deaths WHERE animal_uuid=? ORDER BY death_date LIMIT 1",
        (mae_uuid,)).fetchone()
    return {
        "id": row["id"],
        "sexo": "F" if row["sex"] == "F" else "M",
        "nascimento": row["birth_date"],
        "propriedade_id": row["property_id"],
        "morte": morte["death_date"] if morte else None,
    }


def avaliar(mae_uuid: Optional[str], nascimento: str,
            propriedade_id: Optional[str] = None) -> list[dict]:
    """Problemas do vínculo, SEM gravar nada. Serve à prévia na interface."""
    with _conn() as con:
        mae = _dados_da_mae(con, mae_uuid) if mae_uuid else None
        contexto = _contexto_da_mae(con, mae_uuid, nascimento) if mae_uuid else {}
    cria = {"id": None, "sexo": None, "nascimento": nascimento,
            "propriedade_id": propriedade_id}
    return validar_vinculo(cria, mae, contexto)


@_writes
def registrar(mae_uuid: Optional[str], data: str, crias: list[dict], *,
              hora: str = "", tipo_parto: str = "normal",
              condicao: str = "nascido_vivo",
              propriedade_id: Optional[str] = None,
              responsavel: str = "", data_estimada: bool = False,
              observacoes: str = "",
              ignorar_alertas: bool = False) -> dict:
    """Registra um parto e as crias dele.

    `crias`: [{"id": brinco, "sexo": "M"|"F", "raca": str,
               "peso": float|None, "pai_uuid": str|None}, ...]
    Duas ou mais crias = parto múltiplo, ligadas ao mesmo `parto_id` (§7.2).

    Bloqueio impede o registro. **Alerta não** — o §7.2 diz que o sistema deve
    "emitir alerta, sem substituir a avaliação técnica". `ignorar_alertas=True`
    é a confirmação de quem avaliou.
    """
    if not crias:
        return {"ok": False, "erro": "Nenhuma cria informada."}
    if data > date.today().isoformat():
        return {"ok": False, "erro": f"Data de nascimento no futuro: {data}."}

    problemas = avaliar(mae_uuid, data, propriedade_id)
    bloqueios = [p for p in problemas if p["gravidade"] == "bloqueio"]
    if bloqueios:
        return {"ok": False, "erro": bloqueios[0]["mensagem"],
                "problemas": problemas}

    alertas = [p for p in problemas if p["gravidade"] == "alerta"]
    if alertas and not ignorar_alertas:
        return {"ok": False, "exige_confirmacao": True, "problemas": problemas}

    parto_id = _novo_parto_id()
    with _conn() as con:
        if propriedade_id is None:
            r = con.execute(
                "SELECT id FROM properties ORDER BY created_at LIMIT 1").fetchone()
            propriedade_id = r["id"] if r else None

        if mae_uuid:
            con.execute(
                """INSERT INTO partos
                   (id,mae_uuid,data,hora,tipo_parto,condicao,propriedade_id,
                    responsavel,data_estimada,observacoes)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (parto_id, mae_uuid, data, hora or None, tipo_parto, condicao,
                 propriedade_id, responsavel or None, int(data_estimada),
                 observacoes or None))

        criadas = []
        for c in crias:
            uuid_cria = novo_uuid()
            con.execute(
                """INSERT INTO animals
                   (id,uuid,breed,sex,birth_date,birth_estimated,age_source,
                    entry_date,entry_weight,current_weight,target_weight,
                    lote_id,property_id,propriedade_nascimento_id,
                    mae_uuid,pai_uuid,parto_id,peso_nascimento,origem)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (c["id"], uuid_cria, c.get("raca", ""), c.get("sexo", "M"),
                 data, int(data_estimada), "propriedade",
                 data, c.get("peso") or 0, c.get("peso") or 0,
                 c.get("peso_alvo") or 500,
                 c.get("lote_id"), propriedade_id, propriedade_id,
                 mae_uuid, c.get("pai_uuid"),
                 parto_id if mae_uuid else None,
                 c.get("peso"), "nascido"))

            eventos.registrar_em(
                con, uuid_cria, "nascimento", ocorrido_em=data,
                usuario_registro=responsavel, propriedade_id=propriedade_id,
                observacoes=f"parto {tipo_parto}, {condicao}"
                            + (f", {len(crias)} crias" if len(crias) > 1 else ""))
            criadas.append(uuid_cria)

    eventos.auditar(
        "registro_de_nascimento", usuario=responsavel,
        entidade="partos", entidade_id=parto_id,
        registro_posterior={"mae_uuid": mae_uuid, "data": data,
                            "crias": [c["id"] for c in crias]},
        motivo=observacoes)

    return {"ok": True, "parto_id": parto_id if mae_uuid else None,
            "crias": criadas, "problemas": problemas}


@_writes
def vincular_mae(animal_uuid: str, mae_uuid: Optional[str], *,
                 motivo: str, usuario: str) -> dict:
    """Altera o vínculo materno de um animal já cadastrado.

    §7.2: **alterações no vínculo materno devem ser auditadas.** Por isso o
    `motivo` é obrigatório — trocar a mãe muda a rastreabilidade da cria, e sem
    justificativa ninguém consegue reconstruir por que mudou.
    """
    if not motivo.strip():
        return {"ok": False, "erro": "Alterar vínculo materno exige motivo (§7.2)."}

    with _conn() as con:
        atual = con.execute(
            "SELECT mae_uuid, birth_date, property_id FROM animals WHERE uuid=?",
            (animal_uuid,)).fetchone()
        if atual is None:
            return {"ok": False, "erro": "Animal não encontrado."}

    if mae_uuid:
        problemas = avaliar(mae_uuid, atual["birth_date"] or date.today().isoformat(),
                            atual["property_id"])
        bloqueios = [p for p in problemas if p["gravidade"] == "bloqueio"]
        if bloqueios:
            return {"ok": False, "erro": bloqueios[0]["mensagem"],
                    "problemas": problemas}

    with _conn() as con:
        con.execute("UPDATE animals SET mae_uuid=? WHERE uuid=?",
                    (mae_uuid, animal_uuid))

    eventos.auditar(
        "alteracao_de_vinculo_materno", usuario=usuario,
        entidade="animals", entidade_id=animal_uuid,
        registro_anterior={"mae_uuid": atual["mae_uuid"]},
        registro_posterior={"mae_uuid": mae_uuid},
        motivo=motivo.strip(), autorizacao=usuario)
    return {"ok": True}


def crias_do_parto(parto_id: str) -> list[dict]:
    """Animais nascidos no mesmo parto — é o que identifica gêmeos (§7.2)."""
    with _conn() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM animals WHERE parto_id=? ORDER BY id", (parto_id,)).fetchall()]


def partos_da_mae(mae_uuid: str) -> list[dict]:
    with _conn() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM partos WHERE mae_uuid=? ORDER BY data DESC",
            (mae_uuid,)).fetchall()]


@_cache
def pendencias() -> dict:
    """As listas que o §7.3 exige.

    Existem porque conformidade não é só registrar certo — é **saber o que
    falta**. Sem esta consulta, o buraco só aparece na fiscalização.
    """
    with _conn() as con:
        def ids(sql):
            return [r["id"] for r in con.execute(sql).fetchall()]

        return {
            "sem_mae_vinculada": ids(
                "SELECT id FROM animals WHERE origem='nascido' AND mae_uuid IS NULL "
                "AND status<>'vendido' ORDER BY id"),
            "nascimento_estimado": ids(
                "SELECT id FROM animals WHERE birth_estimated=1 "
                "AND status='ativo' ORDER BY id"),
            "sem_raca": ids(
                "SELECT id FROM animals WHERE (breed IS NULL OR breed='') "
                "AND status='ativo' ORDER BY id"),
            "sem_propriedade_de_nascimento": ids(
                "SELECT id FROM animals WHERE origem='nascido' "
                "AND propriedade_nascimento_id IS NULL ORDER BY id"),
            "sem_identificacao_oficial": ids(
                "SELECT a.id FROM animals a WHERE a.status='ativo' AND NOT EXISTS ("
                "  SELECT 1 FROM animal_identifiers i WHERE i.animal_uuid=a.uuid "
                "  AND i.tipo='oficial_pnib' AND i.status='ativo') ORDER BY a.id"),
        }
