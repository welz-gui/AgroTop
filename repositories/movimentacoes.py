"""Movimentação entre propriedades (ADR 0004 · etapa B6 · PNIB §8).

Distinta de `animal_movements`, que é piquete→piquete e continua valendo para
manejo interno. Esta é a movimentação com **valor regulatório**: tem GTA,
titular, transportador e confirmação de chegada — coisas que trocar de pasto
não tem.

A pré-validação é `services/movimentacao.py` (§8.3 e §8.4), pura. Aqui é a
ligação: apurar o contexto, chamar a regra, e só gravar o que ela permitir.

Depende da **B4** (propriedades) e usa a **B3** só indiretamente.

Camada de dados (ROADMAP R1/R9): aqui mora o SQL, e só aqui.
"""

import uuid as _uuid
from datetime import date
from typing import Optional

from services.movimentacao import (TIPOS, exige_confirmacao, pode_liberar,
                                   pre_validar_saida, resumo)

from . import eventos
from .conexao import _cache, _conn, _writes

ABERTAS = ("rascunho", "liberada", "em_transito")


def _novo_id() -> str:
    return str(_uuid.uuid4())


def _animais_para_validacao(con, uuids: list[str]) -> list[dict]:
    """Monta o retrato que a regra pura precisa de cada animal.

    A função pura não consulta banco (R31) — quem apura é aqui.
    """
    if not uuids:
        return []
    marcas = ",".join("?" for _ in uuids)
    rows = con.execute(
        f"""SELECT a.id, a.uuid, a.status, a.property_id,
                   EXISTS(SELECT 1 FROM animal_identifiers i
                          WHERE i.animal_uuid=a.uuid AND i.tipo='oficial_pnib'
                            AND i.status='ativo') AS tem_oficial
            FROM animals a WHERE a.uuid IN ({marcas})""", uuids).fetchall()

    out = []
    for r in rows:
        # Carência vem de `medications`; a data-fim é calculada, não guardada.
        meds = con.execute(
            "SELECT med_date, withdrawal_days FROM medications "
            "WHERE animal_uuid=? AND withdrawal_days > 0", (r["uuid"],)).fetchall()
        fim = None
        for m in meds:
            try:
                d = date.fromisoformat(m["med_date"])
                cand = d.toordinal() + int(m["withdrawal_days"])
                cand = date.fromordinal(cand)
                if cand >= date.today() and (fim is None or cand > fim):
                    fim = cand
            except (ValueError, TypeError):
                pass
        out.append({
            "id": r["id"], "uuid": r["uuid"], "status": r["status"],
            "property_id": r["property_id"],
            "tem_identificacao_oficial": bool(r["tem_oficial"]),
            "carencia_ate": fim.isoformat() if fim else None,
        })
    return out


def _em_outra_movimentacao(con, uuids: list[str],
                           excluindo: Optional[str] = None) -> list[str]:
    """§8.3: duplicidade do animal em outra movimentação aberta."""
    if not uuids:
        return []
    marcas = ",".join("?" for _ in uuids)
    abertas = ",".join("?" for _ in ABERTAS)
    args = list(uuids) + list(ABERTAS)
    sql = (f"SELECT ma.animal_uuid FROM movimentacao_animais ma "
           f"JOIN movimentacoes m ON m.id = ma.movimentacao_id "
           f"WHERE ma.animal_uuid IN ({marcas}) AND m.status IN ({abertas})")
    if excluindo:
        sql += " AND m.id <> ?"; args.append(excluindo)
    return [r["animal_uuid"] for r in con.execute(sql, args).fetchall()]


def pre_validar(movimentacao_id: str, *,
                identificacao_obrigatoria: bool = False) -> dict:
    """Roda a pré-validação do §8.3 **sem gravar nada**.

    `identificacao_obrigatoria` é `False` por ora: o §4.1 só torna a
    identificação exigível para trânsito a partir de **01/01/2033**, e o formato
    oficial ainda não foi publicado (§23). Vira `True` por configuração, não por
    mudança de código.
    """
    with _conn() as con:
        mov = con.execute(
            "SELECT * FROM movimentacoes WHERE id=?", (movimentacao_id,)).fetchone()
        if mov is None:
            return {"ok": False, "erro": "Movimentação não encontrada."}
        mov = dict(mov)

        uuids = [r["animal_uuid"] for r in con.execute(
            "SELECT animal_uuid FROM movimentacao_animais WHERE movimentacao_id=?",
            (movimentacao_id,)).fetchall()]

        animais = _animais_para_validacao(con, uuids)
        contexto = {
            "hoje": date.today().isoformat(),
            "animais_em_outra_movimentacao": _em_outra_movimentacao(
                con, uuids, excluindo=movimentacao_id),
            # ADR 0005: quem responde isto é `evento_sincronizacao`, não a
            # coluna legada de `animal_events` — que, sendo a linha imutável,
            # jamais deixava de dizer 'pendente' e fazia o alerta do §8.4
            # aparecer em TODA liberação.
            "eventos_pendentes_de_sincronizacao": eventos.contar_pendentes_em(con),
            "identificacao_obrigatoria": identificacao_obrigatoria,
        }

    problemas = pre_validar_saida(mov, animais, contexto)
    return {"ok": True, "problemas": problemas,
            "pode_liberar": pode_liberar(problemas),
            "exige_confirmacao": exige_confirmacao(problemas),
            "resumo": resumo(problemas)}


@_writes
def criar(tipo: str, *, propriedade_origem_id: Optional[str] = None,
          propriedade_destino_id: Optional[str] = None,
          titular_origem_id: Optional[str] = None,
          titular_destino_id: Optional[str] = None,
          finalidade: str = "", data_prevista: str = "",
          transportador: str = "", veiculo: str = "",
          gta_numero: str = "", documento_comercial: str = "",
          animais: Optional[list[str]] = None,
          usuario: str = "") -> dict:
    """Cria a movimentação em **rascunho**. Não valida ainda — rascunho é
    justamente onde o usuário monta antes de conferir."""
    if tipo not in TIPOS:
        return {"ok": False, "erro": f"Tipo de movimentação desconhecido: '{tipo}'."}

    mid = _novo_id()
    with _conn() as con:
        con.execute(
            """INSERT INTO movimentacoes
               (id,tipo,propriedade_origem_id,propriedade_destino_id,
                titular_origem_id,titular_destino_id,finalidade,data_prevista,
                transportador,veiculo,gta_numero,documento_comercial,status)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'rascunho')""",
            (mid, tipo, propriedade_origem_id, propriedade_destino_id,
             titular_origem_id, titular_destino_id, finalidade or None,
             data_prevista or None, transportador or None, veiculo or None,
             gta_numero or None, documento_comercial or None))
        for u in (animais or []):
            con.execute(
                "INSERT INTO movimentacao_animais (movimentacao_id,animal_uuid) "
                "VALUES(?,?)", (mid, u))

    eventos.auditar("criacao_de_movimentacao", usuario=usuario,
                    entidade="movimentacoes", entidade_id=mid,
                    registro_posterior={"tipo": tipo, "animais": len(animais or [])})
    return {"ok": True, "id": mid}


@_writes
def liberar(movimentacao_id: str, *, usuario: str,
            justificativa: str = "",
            identificacao_obrigatoria: bool = False) -> dict:
    """Libera a saída, se a pré-validação permitir (§8.3 e §8.4).

    **Bloqueio impede.** **Alerta exige justificativa** — é a "confirmação e
    justificativa" que o §8.4 pede, e é o que distingue o operador que avaliou
    do que apenas clicou.
    """
    v = pre_validar(movimentacao_id,
                    identificacao_obrigatoria=identificacao_obrigatoria)
    if not v.get("ok"):
        return v

    # `**v` vem PRIMEIRO: ele carrega `ok: True` do `pre_validar`, e espalhá-lo
    # depois sobrescreveria a recusa. A movimentação seria liberada apesar do
    # bloqueio — foi o que os testes pegaram.
    if not v["pode_liberar"]:
        bloq = [p for p in v["problemas"] if p["gravidade"] == "bloqueio"]
        return {**v, "ok": False, "erro": bloq[0]["mensagem"]}

    if v["exige_confirmacao"] and not justificativa.strip():
        return {**v, "ok": False, "exige_confirmacao": True,
                "erro": "Há alertas: informe a justificativa (§8.4)."}

    with _conn() as con:
        con.execute(
            "UPDATE movimentacoes SET status='liberada', justificativa=? WHERE id=?",
            (justificativa.strip() or None, movimentacao_id))
        uuids = [r["animal_uuid"] for r in con.execute(
            "SELECT animal_uuid FROM movimentacao_animais WHERE movimentacao_id=?",
            (movimentacao_id,)).fetchall()]
        for u in uuids:
            eventos.registrar_em(
                con, u, "saida_propriedade", usuario_registro=usuario,
                observacoes=f"movimentação {movimentacao_id[:8]} liberada",
                justificativa=justificativa.strip())

    eventos.auditar("liberacao_de_movimentacao", usuario=usuario,
                    entidade="movimentacoes", entidade_id=movimentacao_id,
                    registro_anterior={"status": "rascunho"},
                    registro_posterior={"status": "liberada"},
                    motivo=justificativa.strip(), autorizacao=usuario)
    return {**v, "ok": True}


@_writes
def confirmar_chegada(movimentacao_id: str, *, data: str, usuario: str,
                      recebidos: Optional[list[str]] = None,
                      divergencias: str = "") -> dict:
    """Confirma a chegada e conclui (§8.2).

    `recebidos` permite registrar **divergência de recepção**: animal que
    embarcou e não chegou fica marcado, em vez de a movimentação inteira ser
    dada como concluída sem ressalva.
    """
    with _conn() as con:
        mov = con.execute(
            "SELECT * FROM movimentacoes WHERE id=?", (movimentacao_id,)).fetchone()
        if mov is None:
            return {"ok": False, "erro": "Movimentação não encontrada."}
        if mov["status"] == "concluida":
            return {"ok": False, "erro": "Movimentação já concluída."}

        uuids = [r["animal_uuid"] for r in con.execute(
            "SELECT animal_uuid FROM movimentacao_animais WHERE movimentacao_id=?",
            (movimentacao_id,)).fetchall()]

        faltantes = [u for u in uuids if recebidos is not None and u not in recebidos]
        if faltantes:
            con.executemany(
                "UPDATE movimentacao_animais SET divergencia='nao_recebido' "
                "WHERE movimentacao_id=? AND animal_uuid=?",
                [(movimentacao_id, u) for u in faltantes])

        status = "concluida" if not faltantes else "divergente"
        con.execute(
            "UPDATE movimentacoes SET status=?, data_efetiva=?, "
            "confirmacao_chegada=?, divergencias=? WHERE id=?",
            (status, data, data,
             divergencias or (f"{len(faltantes)} animal(is) não recebido(s)"
                              if faltantes else None),
             movimentacao_id))

        # Chegada muda a propriedade do animal — é o efeito da movimentação.
        destino = mov["propriedade_destino_id"]
        chegaram = [u for u in uuids if u not in faltantes]
        if destino and chegaram:
            con.executemany("UPDATE animals SET property_id=? WHERE uuid=?",
                            [(destino, u) for u in chegaram])
        for u in chegaram:
            eventos.registrar_em(
                con, u, "chegada_confirmada", ocorrido_em=data,
                usuario_registro=usuario, propriedade_id=destino,
                observacoes=f"movimentação {movimentacao_id[:8]}")
        for u in faltantes:
            eventos.registrar_em(
                con, u, "recusa_recepcao", ocorrido_em=data,
                usuario_registro=usuario,
                observacoes="declarado na movimentação e não recebido")

    eventos.auditar("confirmacao_de_chegada", usuario=usuario,
                    entidade="movimentacoes", entidade_id=movimentacao_id,
                    registro_posterior={"status": status,
                                        "nao_recebidos": len(faltantes)},
                    motivo=divergencias)
    return {"ok": True, "status": status, "nao_recebidos": faltantes}


def get(movimentacao_id: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM movimentacoes WHERE id=?", (movimentacao_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["animais"] = [dict(r) for r in con.execute(
            "SELECT ma.animal_uuid, ma.divergencia, a.id AS brinco "
            "FROM movimentacao_animais ma JOIN animals a ON a.uuid=ma.animal_uuid "
            "WHERE ma.movimentacao_id=? ORDER BY a.id", (movimentacao_id,)).fetchall()]
        return d


@_cache
def abertas() -> list[dict]:
    """Movimentações não concluídas — a fila que o operador acompanha."""
    marcas = ",".join("?" for _ in ABERTAS)
    with _conn() as con:
        return [dict(r) for r in con.execute(
            f"SELECT * FROM movimentacoes WHERE status IN ({marcas}) "
            f"ORDER BY data_prevista", ABERTAS).fetchall()]
