"""Animais, movimentações entre lotes e o seed de demonstração.

Camada de dados (ROADMAP.md R1/R9): aqui mora o SQL, e só aqui.
Sem regra de negócio — cálculo e decisão ficam em `services/`.
Sem Streamlit no topo do módulo.
"""

import random
import uuid as _uuid
from datetime import date, timedelta
from dataclasses import dataclass
from typing import Optional

from . import eventos
from .conexao import _cache, _conn, _writes
from .revisao import (
    RegistroJaCancelado, RegistroNaoEncontrado, RevisaoNaoPermitida,
    foto, motivo_obrigatorio, versao_do_evento,
)


@dataclass
class AnimalData:
    animal_id: str
    breed: str
    sex: str
    birth_date: str | None
    entry_date: str
    entry_weight: float
    target_weight: float | None
    purchase_price: float | None
    lote_id: str | None
    fornecedor_id: int | None
    notes: str = ""
    birth_estimated: int = 0
    age_source: str = "propriedade"
    nf_number: str = ""
    gta_number: str = ""
    weight_method: str = "pesado"
    purchase_mode: str = "cabeca"
    property_id: str | None = None


@dataclass
class MovementParams:
    to_lote_id: str
    movement_date: str
    reason: str = "manejo"
    operator: str = ""
    notes: str = ""
    # Piquete em que quem registrou viu os animais (mobile offline, ADR 0006 / D2).
    # None = não confere (comportamento de sempre: a origem é o que o servidor tem).
    from_lote_esperado: str | None = None
    # Piquete visto POR ANIMAL (animal → piquete), para seleção com origens diferentes.
    # Vale no lugar de `from_lote_esperado` para os animais listados; quem não está no
    # mapa cai no valor único (ou não confere, se ele também for None).
    origens_esperadas: dict | None = None


class OrigemDivergente(ValueError):
    """Animal não está mais no piquete em que o operador o viu.

    `.divergentes` mapeia animal → piquete atual (None = sem piquete) e `.esperados`
    animal → piquete em que foi visto. `.esperado` é o piquete esperado quando é o
    mesmo para todos os divergentes, senão None. Nada é gravado: quem decide o que
    fazer é o operador (ADR 0006, zero merge automático).
    """

    def __init__(self, esperado: str | None, divergentes: dict, esperados: dict | None = None):
        self.esperado = esperado
        self.divergentes = divergentes
        self.esperados = esperados or {a: esperado for a in divergentes}
        if esperado is not None:
            msg = (f"{len(divergentes)} animal(is) não estão mais no piquete {esperado}: "
                   + ", ".join(f"{a} (agora em {l or 'sem piquete'})" for a, l in divergentes.items()))
        else:
            msg = (f"{len(divergentes)} animal(is) não estão mais no piquete em que foram vistos: "
                   + ", ".join(f"{a} (visto em {self.esperados[a]}, agora em {l or 'sem piquete'})"
                               for a, l in divergentes.items()))
        super().__init__(msg)


def _confere_origem(params: MovementParams, atuais: dict) -> None:
    """Levanta `OrigemDivergente` se algum animal saiu do piquete esperado.

    Animal que já está no destino não é divergência: a movimentação pedida já
    aconteceu (é o `ja_no_destino`), e recusar impediria repetir um pedido
    cuja resposta se perdeu.
    """
    unico = params.from_lote_esperado
    mapa = params.origens_esperadas or {}
    if unico is None and not mapa:
        return
    divergentes: dict = {}
    esperados: dict = {}
    for animal, lote in atuais.items():
        esperado = mapa.get(animal, unico)
        if esperado is None or lote == esperado or lote == params.to_lote_id:
            continue
        divergentes[animal] = lote
        esperados[animal] = esperado
    if divergentes:
        distintos = set(esperados.values())
        raise OrigemDivergente(next(iter(distintos)) if len(distintos) == 1 else None,
                               divergentes, esperados)


def uuid_de(con, animal_id: str) -> str | None:
    """UUID interno a partir do número do brinco (ADR 0004, etapa B1.4).

    Usado nas escritas das tabelas filhas enquanto `animal_id` ainda é o que
    chega da interface. Some na etapa 6, quando as funções passarem a receber o
    uuid direto.
    """
    if not animal_id:
        return None
    row = con.execute("SELECT uuid FROM animals WHERE id=?", (animal_id,)).fetchone()
    return row["uuid"] if row else None


def novo_uuid() -> str:
    """Identificador interno imutável de um animal (ADR 0004, §4.1 do PNIB).

    Gerado em Python, e não pelo banco, porque o `gen_random_uuid()` do Postgres
    não existe no SQLite — e a compatibilidade dupla é requisito do projeto.
    """
    return str(_uuid.uuid4())


def get_all_animal_ids(status: str = "ativo") -> set[str]:
    sql = "SELECT id FROM animals WHERE status=?"
    with _conn() as con:
        return {r["id"] for r in con.execute(sql, (status,)).fetchall()}

@_cache
def get_total_gain_kg(status: Optional[str] = "ativo",
                      lote_id: Optional[str] = None,
                      breed: Optional[str] = None) -> float:
    sql = "SELECT SUM(current_weight - entry_weight) FROM animals WHERE 1=1"
    args = []
    if status:
        sql += " AND status=?"
        args.append(status)
    if lote_id:
        sql += " AND lote_id=?"
        args.append(lote_id)
    if breed:
        sql += " AND breed=?"
        args.append(breed)
    with _conn() as con:
        result = con.execute(sql, args).fetchone()
        return float(result[0]) if result and result[0] is not None else 0.0

@_cache
def get_all_animals(status: Optional[str] = "ativo",
                    lote_id: Optional[str] = None,
                    breed: Optional[str] = None,
                    id_contains: Optional[str] = None) -> list[dict]:
    sql  = "SELECT a.*, f.name as fornecedor_name FROM animals a LEFT JOIN fornecedores f ON f.id=a.fornecedor_id WHERE 1=1"
    args: list = []
    if status:
        sql += " AND a.status=?"; args.append(status)
    if lote_id:
        sql += " AND a.lote_id=?"; args.append(lote_id)
    if breed:
        sql += " AND a.breed=?"; args.append(breed)
    if id_contains:
        sql += " AND LOWER(a.id) LIKE LOWER(?)"; args.append(f"%{id_contains}%")
    sql += " ORDER BY a.id"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def count_animals(status: Optional[str] = "ativo",
                  lote_id: Optional[str] = None,
                  breed: Optional[str] = None) -> int:
    sql  = "SELECT COUNT(*) FROM animals a WHERE 1=1"
    args: list = []
    if status:
        sql += " AND a.status=?"; args.append(status)
    if lote_id:
        sql += " AND a.lote_id=?"; args.append(lote_id)
    if breed:
        sql += " AND a.breed=?"; args.append(breed)
    with _conn() as con:
        return con.execute(sql, args).fetchone()[0]


def get_animal(animal_id: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            """SELECT a.*, f.name as fornecedor_name, l.name as lote_name
               FROM animals a
               LEFT JOIN fornecedores f ON f.id=a.fornecedor_id
               LEFT JOIN lotes l ON l.id=a.lote_id
               WHERE a.id=?""",
            (animal_id,),
        ).fetchone()
    return dict(row) if row else None


@_writes
def add_animal(data: AnimalData) -> None:
    _uuid_novo = novo_uuid()
    with _conn() as con:
        # ADR 0004 · B4: o animal nasce numa propriedade (§3.4). Sem escolha
        # explícita, herda a do piquete; sem piquete, a propriedade padrão.
        # É o que permite a B4.3 exigir a coluna depois.
        if data.property_id is None and data.lote_id:
            r = con.execute(
                "SELECT property_id FROM lotes WHERE id=?", (data.lote_id,)).fetchone()
            data.property_id = r["property_id"] if r else None
        if data.property_id is None:
            r = con.execute(
                "SELECT id FROM properties ORDER BY created_at LIMIT 1").fetchone()
            data.property_id = r["id"] if r else None

        con.execute(
            """INSERT INTO animals
               (id,uuid,breed,sex,birth_date,birth_estimated,age_source,nf_number,
                gta_number,entry_date,entry_weight,current_weight,target_weight,
                purchase_price,purchase_mode,lote_id,property_id,fornecedor_id,notes)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data.animal_id, _uuid_novo, data.breed, data.sex, data.birth_date or None,
             int(data.birth_estimated), data.age_source,
             data.nf_number or None, data.gta_number or None, data.entry_date,
             data.entry_weight, data.entry_weight, data.target_weight, data.purchase_price,
             data.purchase_mode, data.lote_id or None, data.property_id,
             data.fornecedor_id or None, data.notes),
        )
        con.execute(
            "INSERT INTO weighings (animal_uuid,weight,weigh_date,lote_id,operator,method) VALUES(?,?,?,?,?,?)",
            (_uuid_novo, data.entry_weight, data.entry_date, data.lote_id or None,
             "Cadastro", data.weight_method),
        )
        # Registra custo de compra apenas para animais adquiridos
        if data.age_source != "propriedade" and data.purchase_price and data.purchase_price > 0:
            con.execute(
                "INSERT INTO animal_costs (animal_uuid,cost_type,description,amount,cost_date) VALUES(?,?,?,?,?)",
                (_uuid_novo, "compra", "Valor de compra", data.purchase_price,
                 data.entry_date),
            )
        if data.lote_id:
            con.execute(
                "INSERT INTO animal_movements (animal_uuid,from_lote_id,to_lote_id,movement_date,reason,operator) VALUES(?,?,?,?,?,?)",
                (_uuid_novo, None, data.lote_id, data.entry_date, "entrada", "Cadastro"),
            )
        eventos.registrar_em(con, _uuid_novo, "cadastro_inicial",
                             ocorrido_em=data.entry_date,
                             observacoes=f"{data.breed}, {data.entry_weight} kg")
        eventos.registrar_em(con, _uuid_novo, "identificacao_interna",
                             ocorrido_em=data.entry_date,
                             observacoes=f"brinco {data.animal_id}")


def _mover_animal_em(con, animal_id, params: MovementParams, *, corrige_id: Optional[int] = None,
                     evento_anterior_id: Optional[int] = None, versao: int = 1,
                     justificativa: str = "") -> int:
    """O que `move_animal` faz, mas recebendo a conexão de fora — para
    `move_animals_bulk` mover várias cabeças na mesma transação, em vez de
    uma conexão por animal (R8: mesma regra, um lugar só). Devolve o id da movimentação.

    `corrige_id`/`evento_anterior_id`/`versao`/`justificativa` só vêm de uma correção."""
    row = con.execute("SELECT lote_id, uuid FROM animals WHERE id=?", (animal_id,)).fetchone()
    if row is None:
        raise ValueError(f"Animal {animal_id} não encontrado.")
    from_lote = row["lote_id"]
    _confere_origem(params, {animal_id: from_lote})
    # Mudar de piquete pode mudar de propriedade — a B6 vai tratar isso como
    # evento regulatório de trânsito. Por ora o animal acompanha o piquete.
    destino = con.execute(
        "SELECT property_id FROM lotes WHERE id=?", (params.to_lote_id,)).fetchone()
    con.execute(
        "UPDATE animals SET lote_id=?, property_id=COALESCE(?, property_id) "
        "WHERE id=?",
        (params.to_lote_id, destino["property_id"] if destino else None, animal_id)
    )
    evento = eventos.registrar_em(
        con, row["uuid"], "mudanca_lote", ocorrido_em=params.movement_date,
        usuario_registro=params.operator, local_interno=params.to_lote_id,
        observacoes=f"{from_lote or '—'} → {params.to_lote_id} ({params.reason})",
        justificativa=justificativa, evento_anterior_id=evento_anterior_id, versao=versao)
    movimento_id = con.execute(
        """INSERT INTO animal_movements
           (animal_uuid,from_lote_id,to_lote_id,movement_date,reason,
            operator,notes,evento_id,corrige_id)
           VALUES(?,?,?,?,?,?,?,?,?) RETURNING id""",
        (row["uuid"], from_lote, params.to_lote_id,
         params.movement_date, params.reason, params.operator, params.notes,
         evento.get("id"), corrige_id),
    ).fetchone()["id"]
    con.execute(
        "UPDATE lotes SET last_entry_date=? WHERE id=?", (params.movement_date, params.to_lote_id)
    )
    if from_lote:
        con.execute(
            "UPDATE lotes SET last_exit_date=? WHERE id=?", (params.movement_date, from_lote)
        )
    return movimento_id


@_writes
def move_animal(animal_id, params: MovementParams) -> None:
    with _conn() as con:
        _mover_animal_em(con, animal_id, params)


@_writes
def move_animals_bulk(animal_ids: list, params: MovementParams) -> dict:
    """Transfere várias cabeças para o mesmo piquete de destino, na mesma
    transação — a versão em lote de `move_animal` (transferência entre
    piquetes, ROADMAP §5, Trilha 3). Sem isso, mover um piquete inteiro
    exigia abrir a ficha de cada animal, um de cada vez.

    Animal que já está no piquete de destino é pulado (não é erro: apenas
    não gera um evento de mudança de piquete que não mudou nada).
    """
    movidos, ja_no_destino, erros = [], [], []
    animal_data = {}
    from_lotes = set()
    with _conn() as con:
        # Get destination property
        destino = con.execute("SELECT property_id FROM lotes WHERE id=?", (params.to_lote_id,)).fetchone()
        to_property_id = destino["property_id"] if destino else None

        chunk_size = 900
        for i in range(0, len(animal_ids), chunk_size):
            chunk = animal_ids[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            rows = con.execute(f"SELECT id, uuid, lote_id FROM animals WHERE id IN ({placeholders})", chunk).fetchall()
            for row in rows:
                animal_data[row["id"]] = {"lote_id": row["lote_id"], "uuid": row["uuid"]}

        # Antes de qualquer escrita: com origem divergente o lote inteiro é recusado.
        _confere_origem(params, {a: d["lote_id"] for a, d in animal_data.items()})

        update_animals_args = []
        insert_movements_args = []

        for animal_id in animal_ids:
            if animal_id not in animal_data:
                erros.append(animal_id)
                continue
            if animal_data[animal_id]["lote_id"] == params.to_lote_id:
                ja_no_destino.append(animal_id)
                continue

            from_lote = animal_data[animal_id]["lote_id"]
            uuid = animal_data[animal_id]["uuid"]

            update_animals_args.append((params.to_lote_id, to_property_id, animal_id))

            # Um evento por animal, e o id dele fica na movimentação (é o que a revisão
            # usa para apontar de volta). Mesmo número de comandos que antes no Postgres,
            # onde `executemany` já é um laço.
            evento = eventos.registrar_em(
                con, uuid, "mudanca_lote", ocorrido_em=params.movement_date,
                usuario_registro=params.operator, local_interno=params.to_lote_id,
                observacoes=f"{from_lote or '—'} → {params.to_lote_id} ({params.reason})")
            insert_movements_args.append((
                uuid, from_lote, params.to_lote_id, params.movement_date, params.reason,
                params.operator, params.notes, evento.get("id")
            ))

            if from_lote:
                from_lotes.add(from_lote)

            movidos.append(animal_id)

        if movidos:
            con.executemany(
                "UPDATE animals SET lote_id=?, property_id=COALESCE(?, property_id) WHERE id=?",
                update_animals_args
            )
            con.executemany(
                """INSERT INTO animal_movements
                   (animal_uuid,from_lote_id,to_lote_id,movement_date,reason,
                    operator,notes,evento_id)
                   VALUES(?,?,?,?,?,?,?,?)""",
                insert_movements_args
            )
            con.execute("UPDATE lotes SET last_entry_date=? WHERE id=?", (params.movement_date, params.to_lote_id))

            if from_lotes:
                for from_lote in from_lotes:
                    con.execute("UPDATE lotes SET last_exit_date=? WHERE id=?", (params.movement_date, from_lote))

    return {"movidos": movidos, "ja_no_destino": ja_no_destino, "erros": erros}


def get_movements(animal_id: str, limit: Optional[int] = None, *,
                  incluir_canceladas: bool = False) -> list[dict]:
    """Movimentações do animal. Por padrão só as vigentes; a ficha pede as canceladas também
    para mostrar a correção ao lado do original."""
    with _conn() as con:
        sql = """SELECT m.*, l1.name as from_name, l2.name as to_name
               FROM animal_movements m
               LEFT JOIN lotes l1 ON l1.id=m.from_lote_id
               LEFT JOIN lotes l2 ON l2.id=m.to_lote_id
               JOIN animals a ON a.uuid=m.animal_uuid
               WHERE a.id=?""" + ("" if incluir_canceladas else " AND m.cancelada_em IS NULL") + """
               ORDER BY m.movement_date DESC"""
        args = [animal_id]
        if limit is not None:
            sql += " LIMIT ?"
            args.append(limit)

        rows = con.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def _ultima_movimentacao_vigente(con, animal_uuid: str):
    return con.execute(
        """SELECT * FROM animal_movements WHERE animal_uuid=? AND cancelada_em IS NULL
           ORDER BY movement_date DESC, id DESC LIMIT 1""", (animal_uuid,)).fetchone()


def movimentacao_revisavel(animal_id: str) -> Optional[dict]:
    """A movimentação que ainda pode ser cancelada ou corrigida, ou None.

    Só a ÚLTIMA vigente do animal, e só se ele ainda está no piquete de destino dela: desfazer
    uma do meio deixaria o piquete atual sem explicação. A entrada do animal (sem piquete de
    origem) também não se desfaz por aqui.
    """
    with _conn() as con:
        a = con.execute("SELECT uuid, lote_id FROM animals WHERE id=?", (animal_id,)).fetchone()
        if a is None:
            return None
        m = _ultima_movimentacao_vigente(con, a["uuid"])
        if m is None or not m["from_lote_id"] or m["to_lote_id"] != a["lote_id"]:
            return None
        return dict(m)


def _reverter_movimentacao_em(con, movement_id: int, motivo: str, usuario: str, *,
                              registrar_estorno: bool, animal_id: Optional[str] = None) -> dict:
    """Cancela a movimentação e devolve o animal ao piquete de origem, na conexão do chamador."""
    m = con.execute(
        """SELECT m.*, a.id AS animal_id, a.lote_id AS lote_atual FROM animal_movements m
           JOIN animals a ON a.uuid=m.animal_uuid WHERE m.id=?""", (movement_id,)).fetchone()
    if m is None or (animal_id is not None and m["animal_id"] != animal_id):
        raise RegistroNaoEncontrado(f"Movimentação {movement_id} não encontrada.")
    m = dict(m)
    if m["cancelada_em"]:
        raise RegistroJaCancelado(
            f"A movimentação {movement_id} já foi cancelada em {m['cancelada_em']}.")
    if not m["from_lote_id"]:
        raise RevisaoNaoPermitida(
            "A entrada do animal não se cancela por aqui: não há piquete de origem para devolvê-lo.")
    ultima = _ultima_movimentacao_vigente(con, m["animal_uuid"])
    if ultima["id"] != movement_id:
        raise RevisaoNaoPermitida(
            "Há movimentação posterior a esta: cancele ou corrija primeiro a mais recente.")
    if m["lote_atual"] != m["to_lote_id"]:
        raise RevisaoNaoPermitida(
            f"O animal já não está no piquete {m['to_lote_id']} (está em "
            f"{m['lote_atual'] or 'nenhum'}): a movimentação não pode ser desfeita.")
    origem = con.execute("SELECT property_id FROM lotes WHERE id=?", (m["from_lote_id"],)).fetchone()
    if origem is None:
        raise RevisaoNaoPermitida(f"O piquete de origem {m['from_lote_id']} não existe mais.")

    cur = con.execute(
        """UPDATE animal_movements SET cancelada_em=?, cancelada_por=?, motivo_cancelamento=?
           WHERE id=? AND cancelada_em IS NULL""", (eventos._agora(), usuario or None, motivo, movement_id))
    if cur.rowcount == 0:      # outro pedido cancelou entre a leitura e a escrita
        raise RegistroJaCancelado(f"A movimentação {movement_id} já foi cancelada.")
    con.execute(
        "UPDATE animals SET lote_id=?, property_id=COALESCE(?, property_id) WHERE id=?",
        (m["from_lote_id"], origem["property_id"], m["animal_id"]))
    # As datas do piquete só mudam se a movimentação cancelada era a que as definia.
    for lote, coluna, extremo in ((m["to_lote_id"], "last_entry_date", "to_lote_id"),
                                  (m["from_lote_id"], "last_exit_date", "from_lote_id")):
        con.execute(
            f"""UPDATE lotes SET {coluna}=(SELECT MAX(movement_date) FROM animal_movements
                                           WHERE {extremo}=? AND cancelada_em IS NULL)
                WHERE id=? AND {coluna}=?""", (lote, lote, m["movement_date"]))
    versao = versao_do_evento(con, m["evento_id"])
    if registrar_estorno:
        eventos.registrar_em(
            con, m["animal_uuid"], "estorno", usuario_registro=usuario, justificativa=motivo,
            evento_anterior_id=m["evento_id"], versao=versao + 1,
            local_interno=m["from_lote_id"],
            observacoes=f"Cancelamento da movimentação {m['from_lote_id']} → {m['to_lote_id']} "
                        f"de {m['movement_date']}")
    return {"movimentacao": m, "foto": foto(m), "versao_evento": versao}


@_writes
def cancelar_movimentacao(movement_id: int, motivo: str, usuario: str, *, origem: str = "web",
                          animal_id: Optional[str] = None) -> dict:
    """Cancela a última movimentação do animal e o devolve ao piquete de origem.

    Levanta `RevisaoNaoPermitida` (motivo vazio, entrada do animal, movimentação que não é a
    última, ou animal que já saiu do piquete de destino), `RegistroNaoEncontrado` ou
    `RegistroJaCancelado`; em qualquer uma nada é gravado.
    """
    motivo = motivo_obrigatorio(motivo)
    with _conn() as con:
        r = _reverter_movimentacao_em(con, movement_id, motivo, usuario, registrar_estorno=True,
                                      animal_id=animal_id)
        m = r["movimentacao"]
        eventos.auditar_em(
            con, "cancelar_movimentacao", usuario=usuario, entidade="animal_movements",
            entidade_id=movement_id, registro_anterior=r["foto"], motivo=motivo, origem=origem)
    return {"cancelada": movement_id, "animal_id": m["animal_id"], "devolvido_a": m["from_lote_id"]}


@_writes
def corrigir_movimentacao(movement_id: int, params: MovementParams, motivo: str, usuario: str, *,
                          animal_id: Optional[str] = None, origem: str = "web") -> dict:
    """Corrige a última movimentação: desfaz a original e grava a certa, ligada a ela.

    A correta parte do piquete de origem da original (o animal volta a ele antes). Destino igual
    ao de origem é cancelar, não corrigir. Tudo na mesma transação.
    """
    motivo = motivo_obrigatorio(motivo)
    with _conn() as con:
        existe = con.execute("SELECT 1 FROM lotes WHERE id=?", (params.to_lote_id,)).fetchone()
        if existe is None:
            raise RevisaoNaoPermitida(f"Piquete de destino {params.to_lote_id} não encontrado.")
        r = _reverter_movimentacao_em(con, movement_id, motivo, usuario, registrar_estorno=False,
                                      animal_id=animal_id)
        m = r["movimentacao"]
        if params.to_lote_id == m["from_lote_id"]:
            raise RevisaoNaoPermitida(
                "O destino corrigido é o piquete de origem: use Cancelar movimentação.")
        if not params.operator:
            params.operator = m.get("operator") or usuario
        nova = _mover_animal_em(
            con, m["animal_id"], params, corrige_id=movement_id,
            evento_anterior_id=m["evento_id"], versao=r["versao_evento"] + 1, justificativa=motivo)
        eventos.auditar_em(
            con, "corrigir_movimentacao", usuario=usuario, entidade="animal_movements",
            entidade_id=movement_id, registro_anterior=r["foto"],
            registro_posterior={"nova_movimentacao": nova, "destino": params.to_lote_id,
                                "data": params.movement_date, "motivo_manejo": params.reason},
            motivo=motivo, origem=origem)
    return {"cancelada": movement_id, "nova": nova, "animal_id": m["animal_id"]}


def get_last_movements_bulk(animal_ids: list[str]) -> dict[str, str]:
    if not animal_ids:
        return {}

    last_movements = {}
    with _conn() as con:
        # SQLite limit is typically 999 parameters. Batch by 900.
        for i in range(0, len(animal_ids), 900):
            batch = animal_ids[i:i+900]
            placeholders = ",".join("?" for _ in batch)
            sql = f"""
                SELECT a.id as animal_id, MAX(m.movement_date) as last_movement_date
                FROM animals a
                LEFT JOIN animal_movements m ON a.uuid = m.animal_uuid AND m.cancelada_em IS NULL
                WHERE a.id IN ({placeholders})
                GROUP BY a.id
            """
            rows = con.execute(sql, batch).fetchall()
            for r in rows:
                if r["last_movement_date"]:
                    last_movements[r["animal_id"]] = r["last_movement_date"]
    return last_movements


def _generate_animal_seed_records(i: int, today: date, breeds: list[str], lotes: list[str], property_id: str = None) -> tuple:
    aid          = f"BR{i:04d}"
    breed        = random.choice(breeds)
    sex          = random.choice(["M", "F"])
    days_in      = random.randint(60, 220)
    days_old     = random.randint(400, 900)
    birth_date   = (today - timedelta(days=days_old)).isoformat()
    entry_date   = (today - timedelta(days=days_in)).isoformat()
    e_weight     = round(random.uniform(220, 320), 1)
    c_weight     = round(e_weight + random.uniform(30, 110), 1)
    target_w     = round(random.uniform(480, 520), 1)
    lote_id      = random.choice(lotes)
    forn_id      = random.randint(1, 4)
    price        = round(e_weight * 0.52 / 15 * random.uniform(280, 320), 2)
    status       = "ativo"

    src, est = random.choice([
        ("propriedade", 0), ("propriedade", 0),
        ("nf_gta", 1), ("operador", 1), ("estimado", 1),
    ])
    if i == 13: status = "vendido"
    if i == 14: status = "morto"

    a_uuid = novo_uuid()
    animal_tuple = (aid, a_uuid, breed, sex, birth_date, est, src, entry_date, e_weight,
         c_weight, target_w, status, lote_id, forn_id, price, property_id)

    weighings_list = []
    for step, days_back in [(0.0, days_in), (0.5, days_in//2), (1.0, 0)]:
        w_date   = (today - timedelta(days=int(days_in * (1 - step)))).isoformat()
        w_weight = round(e_weight + (c_weight - e_weight) * step, 1)
        weighings_list.append((a_uuid, w_weight, w_date, lote_id, "Sistema"))

    medications_list = []
    meds_pool = [
        ("Ivermectina 1%",  "ml",  10, 21),
        ("Vacina FMD",      "dose", 2,  0),
        ("Closantel 10%",   "ml",  10, 28),
        ("Vitamina ADE",    "ml",  10,  0),
        ("Oxitetraciclina", "ml",  20, 14),
    ]
    for _ in range(random.randint(1, 2)):
        mn, mu, dose, wd = random.choice(meds_pool)
        md = (today - timedelta(days=random.randint(0, 60))).isoformat()
        medications_list.append((a_uuid, mn, dose, mu, "Subcutânea", wd, md, "Sistema"))

    costs_list = []
    costs_list.append((a_uuid, "compra", "Valor de compra", price, entry_date))
    op_cost = round(days_in * 0.85, 2)
    costs_list.append((a_uuid, "operacional", "Custeio diário (pasto/água/mão de obra)", op_cost, today.isoformat()))

    movement_tuple = (a_uuid, None, lote_id, entry_date, "entrada", "Sistema")

    return animal_tuple, weighings_list, medications_list, costs_list, movement_tuple


def _insert_seed_data(con, animals_data, weighings_data, medications_data, animal_costs_data, animal_movements_data):
    if animals_data:
        con.executemany(
            """INSERT INTO animals
               (id,uuid,breed,sex,birth_date,birth_estimated,age_source,entry_date,
                entry_weight,current_weight,target_weight,status,lote_id,
                fornecedor_id,purchase_price,property_id)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            animals_data,
        )

    if weighings_data:
        con.executemany(
            "INSERT INTO weighings (animal_uuid,weight,weigh_date,lote_id,operator) VALUES(?,?,?,?,?)",
            weighings_data,
        )

    if medications_data:
        con.executemany(
            """INSERT INTO medications
               (animal_uuid,medication_name,dose,unit,application_route,
                withdrawal_days,med_date,applied_by)
               VALUES(?,?,?,?,?,?,?,?)""",
            medications_data,
        )

    if animal_costs_data:
        con.executemany(
            "INSERT INTO animal_costs (animal_uuid,cost_type,description,amount,cost_date) VALUES(?,?,?,?,?)",
            animal_costs_data,
        )

    if animal_movements_data:
        con.executemany(
            """INSERT INTO animal_movements
               (animal_uuid,from_lote_id,to_lote_id,movement_date,reason,operator)
               VALUES(?,?,?,?,?,?)""",
            animal_movements_data,
        )


def _seed_animals(con, property_id: str = None):
    if con.execute("SELECT COUNT(*) FROM animals").fetchone()[0]:
        return

    random.seed(7)
    today  = date.today()
    breeds = ["Nelore", "Angus", "Brahman", "Senepol", "Brangus", "Canchim"]
    lotes  = ["P01", "P01", "P01", "P02", "P02", "P03", "P03", "P03", "CRL"]

    animals_data = []
    weighings_data = []
    medications_data = []
    animal_costs_data = []
    animal_movements_data = []

    for i in range(1, 15):
        a_tuple, w_list, m_list, c_list, mv_tuple = _generate_animal_seed_records(i, today, breeds, lotes, property_id)
        animals_data.append(a_tuple)
        weighings_data.extend(w_list)
        medications_data.extend(m_list)
        animal_costs_data.extend(c_list)
        animal_movements_data.append(mv_tuple)

    _insert_seed_data(con, animals_data, weighings_data, medications_data, animal_costs_data, animal_movements_data)
