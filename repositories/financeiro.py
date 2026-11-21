"""Custos, custos fixos, vendas, óbitos e preços por categoria.

Camada de dados (ROADMAP.md R1/R9): aqui mora o SQL, e só aqui.
Sem regra de negócio — cálculo e decisão ficam em `services/`.
Sem Streamlit no topo do módulo.
"""

from datetime import date, datetime
from dataclasses import dataclass
from typing import Optional

from . import conexao as _conexao
from .animais import get_animal, uuid_de
from . import eventos
from .conexao import _cache, _conn, _writes
from .revisao import (
    RegistroJaCancelado, RegistroNaoEncontrado, RevisaoNaoPermitida, foto, motivo_obrigatorio,
    versao_do_evento,
)

# Regras puras importadas em vez de reimplementadas (ROADMAP R8).
from services.zootecnia import get_age_category
from services.financeiro import valor_esperado_venda
# Parcelamento é a mesma conta de `repositories/compras.py` — venda a prazo e
# compra a prazo dividem o total do mesmo jeito (resto na última parcela,
# vencimento mensal com o dia preso ao mês). Reexportar em vez de duplicar (R8).
from services.compras import gerar_parcelas
from services.carencia import fim_da_carencia


@dataclass
class AnimalCostData:
    animal_id: str
    cost_type: str
    description: str
    amount: float
    cost_date: str
    notes: str = ""


@dataclass
class FixedCostData:
    category: str
    description: str
    amount: float
    cost_date: str
    recurring: int = 0
    notes: str = ""
    lote_id: Optional[str] = None


@_cache
def _costs_by_animal() -> dict:
    """Soma de custos por animal. 1 consulta."""
    with _conn() as con:
        rows = con.execute(
            """SELECT a.id AS animal_id, COALESCE(SUM(c.amount),0) AS total
               FROM animal_costs c JOIN animals a ON a.uuid=c.animal_uuid
               WHERE c.cancelada_em IS NULL
               GROUP BY a.id"""
        ).fetchall()
    return {r["animal_id"]: round(float(r["total"]), 2) for r in rows}


def get_total_cost(animal_id: str) -> float:
    return _costs_by_animal().get(animal_id, 0.0)


def get_animal_costs(animal_id: str, incluir_canceladas: bool = False) -> list[dict]:
    """Custos vigentes do animal; com `incluir_canceladas`, também os cancelados (a ficha mostra
    a correção ao lado do original)."""
    with _conn() as con:
        rows = con.execute(
            """SELECT c.*, a.id AS animal_id
               FROM animal_costs c JOIN animals a ON a.uuid=c.animal_uuid
               WHERE a.id=?""" + ("" if incluir_canceladas else " AND c.cancelada_em IS NULL")
            + " ORDER BY c.cost_date DESC, c.id DESC",
            (animal_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_animal_costs(start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> list[dict]:
    """Todos os custos por animal, de todos os animais — não um só.

    `get_animal_costs` é por animal, pensada para a ficha individual;
    `services.lancamentos.normalizar` (spec 0034) precisa da lista inteira,
    a mesma fonte que `get_financial_summary` já soma por `cost_type`, aqui
    linha a linha.
    """
    sql = "SELECT c.* FROM animal_costs c WHERE c.cancelada_em IS NULL"
    args: list = []
    if start_date:
        sql += " AND c.cost_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND c.cost_date <= ?"; args.append(end_date)
    sql += " ORDER BY c.cost_date DESC, c.id DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


@_writes
def add_animal_cost(data: AnimalCostData) -> None:
    with _conn() as con:
        uuid = uuid_de(con, data.animal_id)
        if uuid is None:
            raise ValueError(f"Animal {data.animal_id} não encontrado.")
        con.execute(
            "INSERT INTO animal_costs (animal_uuid,cost_type,description,amount,cost_date,notes) VALUES(?,?,?,?,?,?)",
            (uuid, data.cost_type, data.description, data.amount, data.cost_date, data.notes),
        )


@_writes
def add_fixed_cost(data: FixedCostData) -> None:
    """`lote_id` é o centro de custo (o piquete a que este custo fixo pertence).
    `None` é um valor válido — "geral da fazenda", não alocado a um piquete
    específico (salário do gerente, contabilidade) — não "esqueceram de
    preencher"."""
    with _conn() as con:
        con.execute(
            """INSERT INTO fixed_costs
               (category,description,amount,cost_date,recurring,notes,lote_id)
               VALUES(?,?,?,?,?,?,?)""",
            (data.category, data.description, data.amount, data.cost_date, int(data.recurring), data.notes, data.lote_id),
        )


def get_fixed_costs(start_date: Optional[str] = None,
                    end_date: Optional[str] = None, incluir_canceladas: bool = False) -> list[dict]:
    sql, args = "SELECT * FROM fixed_costs WHERE 1=1", []
    if not incluir_canceladas:
        sql += " AND cancelada_em IS NULL"
    if start_date:
        sql += " AND cost_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND cost_date <= ?"; args.append(end_date)
    sql += " ORDER BY cost_date DESC, id DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def get_total_fixed_costs(start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> float:
    sql, args = ("SELECT COALESCE(SUM(amount),0) as total FROM fixed_costs "
                 "WHERE cancelada_em IS NULL"), []
    if start_date:
        sql += " AND cost_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND cost_date <= ?"; args.append(end_date)
    with _conn() as con:
        row = con.execute(sql, args).fetchone()
    return round(float(row["total"]), 2)


@_writes
def delete_fixed_cost(cost_id: int, usuario: str = "") -> None:
    """Apaga o custo fixo e deixa a linha apagada na trilha de auditoria, na mesma transação.
    Id inexistente não faz nada."""
    with _conn() as con:
        antes = con.execute("SELECT * FROM fixed_costs WHERE id=?", (cost_id,)).fetchone()
        if antes is None:
            return
        con.execute("DELETE FROM fixed_costs WHERE id=?", (cost_id,))
        eventos.auditar_em(con, "excluir_custo_fixo", usuario=usuario, entidade="fixed_costs",
                           entidade_id=cost_id, registro_anterior=foto(dict(antes)))


_TABELAS_DE_CUSTO = ("animal_costs", "fixed_costs")


def _cancelar_custo_em(con, tabela: str, cost_id: int, motivo: str, usuario: str, *,
                       animal_id: Optional[str] = None) -> dict:
    """Marca o custo como cancelado, na conexão do chamador. `tabela` é uma das duas fixas.
    Com `animal_id`, o custo precisa ser desse animal (senão "não existe" para ele)."""
    assert tabela in _TABELAS_DE_CUSTO
    c = con.execute(f"SELECT * FROM {tabela} WHERE id=?", (cost_id,)).fetchone()
    if c is None or (animal_id is not None and c["animal_uuid"] != uuid_de(con, animal_id)):
        raise RegistroNaoEncontrado(f"Custo {cost_id} não encontrado.")
    c = dict(c)
    if c["cancelada_em"]:
        raise RegistroJaCancelado(f"O custo {cost_id} já foi cancelado em {c['cancelada_em']}.")
    cur = con.execute(
        f"""UPDATE {tabela} SET cancelada_em=?, cancelada_por=?, motivo_cancelamento=?
            WHERE id=? AND cancelada_em IS NULL""", (eventos._agora(), usuario or None, motivo, cost_id))
    if cur.rowcount == 0:      # outro pedido cancelou entre a leitura e a escrita
        raise RegistroJaCancelado(f"O custo {cost_id} já foi cancelado.")
    return c


@_writes
def cancelar_custo_animal(cost_id: int, motivo: str, usuario: str, *, animal_id: Optional[str] = None,
                          origem: str = "web") -> dict:
    """Cancela um custo de animal lançado por engano. A linha fica, com motivo e autor, e sai de
    todas as somas. Levanta `RevisaoNaoPermitida` (sem motivo), `RegistroNaoEncontrado` ou
    `RegistroJaCancelado`; em qualquer uma nada é gravado."""
    motivo = motivo_obrigatorio(motivo)
    with _conn() as con:
        c = _cancelar_custo_em(con, "animal_costs", cost_id, motivo, usuario, animal_id=animal_id)
        eventos.auditar_em(con, "cancelar_custo_animal", usuario=usuario, entidade="animal_costs",
                           entidade_id=cost_id, registro_anterior=foto(c), motivo=motivo, origem=origem)
    return {"cancelada": cost_id}


@_writes
def corrigir_custo_animal(cost_id: int, data: AnimalCostData, motivo: str, usuario: str, *,
                          origem: str = "web") -> dict:
    """Corrige um custo de animal: cancela o original e grava o certo, ligado a ele, na mesma
    transação. O animal não muda: `data.animal_id` precisa ser o do custo."""
    motivo = motivo_obrigatorio(motivo)
    with _conn() as con:
        c = _cancelar_custo_em(con, "animal_costs", cost_id, motivo, usuario, animal_id=data.animal_id)
        nova = con.execute(
            """INSERT INTO animal_costs
               (animal_uuid,cost_type,description,amount,cost_date,notes,corrige_id)
               VALUES(?,?,?,?,?,?,?) RETURNING id""",
            (c["animal_uuid"], data.cost_type, data.description, data.amount, data.cost_date,
             data.notes, cost_id)).fetchone()["id"]
        eventos.auditar_em(
            con, "corrigir_custo_animal", usuario=usuario, entidade="animal_costs", entidade_id=cost_id,
            registro_anterior=foto(c),
            registro_posterior={"novo_custo": nova, "tipo": data.cost_type, "valor": data.amount,
                                "data": data.cost_date, "descricao": data.description},
            motivo=motivo, origem=origem)
    return {"cancelada": cost_id, "nova": nova}


@_writes
def cancelar_custo_fixo(cost_id: int, motivo: str, usuario: str, *, origem: str = "web") -> dict:
    """Cancela um custo fixo lançado por engano. A linha fica, com motivo e autor, e sai de todas
    as somas. Mesmos erros de `cancelar_custo_animal`."""
    motivo = motivo_obrigatorio(motivo)
    with _conn() as con:
        c = _cancelar_custo_em(con, "fixed_costs", cost_id, motivo, usuario)
        eventos.auditar_em(con, "cancelar_custo_fixo", usuario=usuario, entidade="fixed_costs",
                           entidade_id=cost_id, registro_anterior=foto(c), motivo=motivo, origem=origem)
    return {"cancelada": cost_id}


@_writes
def corrigir_custo_fixo(cost_id: int, data: FixedCostData, motivo: str, usuario: str, *,
                        origem: str = "web") -> dict:
    """Corrige um custo fixo: cancela o original e grava o certo, ligado a ele, na mesma
    transação."""
    motivo = motivo_obrigatorio(motivo)
    with _conn() as con:
        c = _cancelar_custo_em(con, "fixed_costs", cost_id, motivo, usuario)
        nova = con.execute(
            """INSERT INTO fixed_costs
               (category,description,amount,cost_date,recurring,notes,lote_id,corrige_id)
               VALUES(?,?,?,?,?,?,?,?) RETURNING id""",
            (data.category, data.description, data.amount, data.cost_date, int(data.recurring),
             data.notes, data.lote_id, cost_id)).fetchone()["id"]
        eventos.auditar_em(
            con, "corrigir_custo_fixo", usuario=usuario, entidade="fixed_costs", entidade_id=cost_id,
            registro_anterior=foto(c),
            registro_posterior={"novo_custo": nova, "categoria": data.category, "valor": data.amount,
                                "data": data.cost_date, "descricao": data.description},
            motivo=motivo, origem=origem)
    return {"cancelada": cost_id, "nova": nova}


def get_fixed_costs_by_category(start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> list[dict]:
    sql = "SELECT category, COALESCE(SUM(amount),0) as total FROM fixed_costs WHERE cancelada_em IS NULL"
    args: list = []
    if start_date:
        sql += " AND cost_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND cost_date <= ?"; args.append(end_date)
    sql += " GROUP BY category ORDER BY total DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def get_fixed_costs_by_lote(start_date: Optional[str] = None,
                            end_date: Optional[str] = None) -> dict:
    """Custo fixo por centro de custo (piquete). Chave `None` = geral da
    fazenda (custo fixo sem `lote_id`)."""
    sql = "SELECT lote_id, COALESCE(SUM(amount),0) as total FROM fixed_costs WHERE cancelada_em IS NULL"
    args: list = []
    if start_date:
        sql += " AND cost_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND cost_date <= ?"; args.append(end_date)
    sql += " GROUP BY lote_id"
    with _conn() as con:
        rows = con.execute(sql, args).fetchall()
    return {r["lote_id"]: round(float(r["total"]), 2) for r in rows}


def get_animal_costs_by_lote(start_date: Optional[str] = None,
                             end_date: Optional[str] = None) -> dict:
    """Custo por animal (`animal_costs`) agregado pelo piquete ATUAL do
    animal — não pelo piquete de quando o custo foi lançado.

    Limitação conhecida (mesma de `app.py::_nutricao_custo_por_piquete`):
    animal que mudou de piquete no meio do período tem todo o custo
    histórico atribuído ao piquete de hoje, não ao de quando o custo
    ocorreu. Rastrear isso exigiria cruzar com `animal_movements` por data,
    fora do escopo desta integração.
    """
    sql = ("SELECT a.lote_id, COALESCE(SUM(c.amount),0) as total "
           "FROM animal_costs c JOIN animals a ON a.uuid=c.animal_uuid "
           "WHERE a.lote_id IS NOT NULL AND c.cancelada_em IS NULL")
    args: list = []
    if start_date:
        sql += " AND c.cost_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND c.cost_date <= ?"; args.append(end_date)
    sql += " GROUP BY a.lote_id"
    with _conn() as con:
        rows = con.execute(sql, args).fetchall()
    return {r["lote_id"]: round(float(r["total"]), 2) for r in rows}


@dataclass
class SaleParams:
    animal_ids: list
    sale_date: str
    sale_type: str
    pricing_mode: str
    value: float
    buyer: str = ""
    operator: str = ""
    notes: str = ""
    a_prazo: bool = False
    num_parcelas: int = 1
    primeiro_vencimento: Optional[str] = None


class VendaBloqueadaPorCarencia(ValueError):
    """Venda para abate recusada: há animal ainda em carência na data da venda."""

    def __init__(self, bloqueados: dict[str, str]):
        self.bloqueados = bloqueados   # {brinco: "AAAA-MM-DD" do fim da carência}
        detalhe = ", ".join(f"{aid} (até {fim})" for aid, fim in sorted(bloqueados.items()))
        super().__init__(f"Venda para abate bloqueada: animal em carência — {detalhe}.")


def _recusar_abate_em_carencia(con, animal_ids: tuple, data_venda: str) -> None:
    """Lê as carências direto do banco, na mesma transação da venda: o cache de
    `get_withdrawal_end` (120 s) pode estar atrasado, e a API grava medicamento
    em outro processo. A conta é de `services/carencia.py`."""
    referencia = date.fromisoformat(data_venda)
    qmarks = ",".join("?" for _ in animal_ids)
    rows = con.execute(
        f"""SELECT a.id AS animal_id, m.med_date, m.withdrawal_days
            FROM medications m JOIN animals a ON a.uuid = m.animal_uuid
            WHERE m.withdrawal_days > 0 AND m.cancelada_em IS NULL
              AND a.id IN ({qmarks})""", animal_ids
    ).fetchall()
    por_animal: dict[str, list[dict]] = {}
    for r in rows:
        por_animal.setdefault(r["animal_id"], []).append(dict(r))
    bloqueados = {}
    for aid, aplicacoes in por_animal.items():
        fim = fim_da_carencia(aplicacoes, referencia)
        if fim:
            bloqueados[aid] = fim.isoformat()
    if bloqueados:
        raise VendaBloqueadaPorCarencia(bloqueados)


def _fetch_animal_costs(con, animais: list[dict]) -> dict[str, float]:
    """Busca o custo de múltiplos animais em lote."""
    qmarks = ",".join("?" for _ in animais)
    animal_ids_tuple = tuple(a["id"] for a in animais)
    rows = con.execute(
        f"""SELECT a.id AS animal_id, COALESCE(SUM(c.amount),0) AS total
           FROM animal_costs c JOIN animals a ON a.uuid=c.animal_uuid
           WHERE a.id IN ({qmarks}) AND c.cancelada_em IS NULL
           GROUP BY a.id""", animal_ids_tuple
    ).fetchall()
    return {r["animal_id"]: round(float(r["total"]), 2) for r in rows}


def _process_sale_items(con, animais: list[dict], params: SaleParams, costs_dict: dict[str, float], peso_total: float, lot_ref: Optional[str], cadeia: Optional[dict] = None) -> tuple[list[tuple], float, float]:
    """Processa o valor, lucro e os eventos para os itens vendidos. `cadeia` (só numa correção) liga
    o evento e a linha de cada animal ao que eles substituem."""
    tot_receita = tot_custo = 0.0
    sales_data = []

    for a in animais:
        if params.pricing_mode == "kg":
            ppk = params.value
            val = round(a["current_weight"] * params.value, 2)
        elif params.pricing_mode == "cabeca":
            ppk = None
            val = round(params.value, 2)
        else:  # lote: rateio proporcional ao peso
            ppk = None
            val = round(params.value * a["current_weight"] / peso_total, 2)

        custo = costs_dict.get(a["id"], 0.0)
        lucro = round(val - custo, 2)
        tot_receita += val
        tot_custo += custo

        # Venda e obito mudam status por SQL direto, sem passar por
        # update_animal_status -- entao o evento precisa ser registrado aqui.
        elo = (cadeia or {}).get(a["uuid"], {})
        evento = eventos.registrar_em(
            con, a["uuid"], "venda", ocorrido_em=params.sale_date,
            usuario_registro=params.operator, documento=lot_ref,
            justificativa=elo.get("justificativa", ""), evento_anterior_id=elo.get("evento_anterior_id"),
            versao=elo.get("versao", 1),
            observacoes=f"R$ {val:.2f} para {params.buyer or 'comprador nao informado'}")

        sales_data.append((
            a["uuid"], params.sale_date, params.sale_type, params.pricing_mode,
            a["current_weight"], ppk,
            val, params.buyer or None, lot_ref, custo, lucro, params.operator, params.notes,
            1 if params.a_prazo else 0, evento.get("id"), elo.get("corrige_id")
        ))

    return sales_data, tot_receita, tot_custo


def _gerar_contas_receber_venda(con, params: SaleParams, tot_receita: float, lot_ref: Optional[str]) -> int:
    """Gera as parcelas em contas_receber para uma venda a prazo."""
    if not params.a_prazo or tot_receita <= 0:
        return 0
    if not params.primeiro_vencimento:
        raise ValueError("venda a prazo exige primeiro_vencimento")

    rotulo = f"Venda {lot_ref}" if lot_ref else "Venda"
    rotulo += f" — {params.buyer or 'comprador não informado'}"

    for p in gerar_parcelas(round(tot_receita, 2), params.num_parcelas, params.primeiro_vencimento):
        con.execute(
            """INSERT INTO contas_receber
               (lot_ref, comprador, descricao, valor, vencimento,
                parcela_numero, parcela_total, status, operator)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (lot_ref, params.buyer, rotulo, p["valor"], p["vencimento"],
             p["numero"], p["total"], "aberto", params.operator))
    return params.num_parcelas


def _novo_lot_ref(params: SaleParams, n_animais: int) -> Optional[str]:
    """Referência do lote de venda. Vem com mais de um animal, com preço de lote e em venda a prazo
    (as parcelas de `contas_receber` se ligam à venda por ela); venda avulsa à vista não tem."""
    if params.pricing_mode == "lote" or n_animais > 1 or params.a_prazo:
        return f"V{params.sale_date.replace('-', '')}-{int(datetime.now().timestamp()) % 100000}"
    return None


def _recusar_animal_que_nao_pode_ser_vendido(con, animais: list[dict]) -> None:
    """Só `ativo` e `carencia` podem ser vendidos. O status é lido aqui, na transação da venda: o
    cache de `get_animal` (120 s) pode ainda dizer `ativo` para quem outra aba ou outro processo
    acabou de vender ou de dar como morto, e a venda entraria em dobro (receita e evento repetidos).
    Recusa a venda inteira, citando só os animais com problema."""
    if not animais:
        return
    qmarks = ",".join("?" for _ in animais)
    rows = con.execute(f"SELECT id, status FROM animals WHERE uuid IN ({qmarks}) ORDER BY id",
                       tuple(a["uuid"] for a in animais)).fetchall()
    ruins = [(r["id"], r["status"]) for r in rows if r["status"] not in ("ativo", "carencia")]
    if ruins:
        raise RevisaoNaoPermitida("; ".join(
            f"O animal {aid} está '{status}' e não pode entrar na venda." for aid, status in ruins))


def _registrar_venda_em(con, animais: list[dict], params: SaleParams, lot_ref: Optional[str], *,
                        cadeia: Optional[dict] = None) -> dict:
    """Grava a venda na conexão do chamador (a de `register_sale` e a de `corrigir_venda`).
    `cadeia` liga cada linha nova à que ela substitui, por `animal_uuid`: `corrige_id`,
    `evento_anterior_id`, `versao` e `justificativa`."""
    peso_total = sum(a["current_weight"] for a in animais) or 1
    if params.sale_type == "abate":
        _recusar_abate_em_carencia(con, tuple(a["id"] for a in animais), params.sale_date)

    costs_dict = _fetch_animal_costs(con, animais)
    sales_data, tot_receita, tot_custo = _process_sale_items(
        con, animais, params, costs_dict, peso_total, lot_ref, cadeia)

    con.executemany(
        """INSERT INTO sales
           (animal_uuid,sale_date,sale_type,pricing_mode,weight_kg,
            price_per_kg,total_value,buyer,lot_ref,cost_at_sale,profit,
            operator,notes,a_prazo,evento_id,corrige_id)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        sales_data,
    )

    qmarks = ",".join("?" for _ in animais)
    animal_ids_tuple = tuple(a["id"] for a in animais)
    con.execute(f"UPDATE animals SET status='vendido' WHERE id IN ({qmarks})", animal_ids_tuple)

    n_parcelas_receber = _gerar_contas_receber_venda(con, params, tot_receita, lot_ref)
    return {"receita": round(tot_receita, 2), "custo": round(tot_custo, 2),
            "lucro": round(tot_receita - tot_custo, 2), "n": len(animais),
            "lot_ref": lot_ref, "parcelas_a_receber": n_parcelas_receber}


@_writes
def register_sale(params: SaleParams) -> dict:
    """Registra a venda de um ou mais animais.
    - params.pricing_mode='kg':     `params.value` é o preço por kg (cada animal: peso × preço).
    - params.pricing_mode='cabeca': `params.value` é o valor por cabeça (igual para cada animal).
    - params.pricing_mode='lote':   `params.value` é o valor TOTAL do lote, rateado pelo peso.

    `params.a_prazo=True` gera as parcelas em `contas_receber` a partir da receita
    total (`gerar_parcelas`, mesma conta de `repositories/compras.py`) — o
    padrão continua sendo à vista (nenhuma linha em `contas_receber`), o
    comportamento de sempre, preservado (ROADMAP §3).

    `params.sale_date` continua sendo a competência da receita (usada por
    `lancamentos.normalizar`/`services.caixa`); `vencimento` em
    `contas_receber` é só quando o dinheiro chega — as duas datas não se
    misturam (ROADMAP §5, Trilha 3, "cuidados que definem o sucesso").

    Venda do tipo `abate` com algum animal ainda em carência na `sale_date`
    levanta `VendaBloqueadaPorCarencia` e não grava nada (a venda inteira é
    recusada). Venda de criação não é afetada: a carência impede o abate.

    Animal que não está `ativo` nem `carencia` (já vendido, morto) levanta `RevisaoNaoPermitida`
    e também não grava nada.

    Retorna {'receita':..., 'custo':..., 'lucro':..., 'n':...}."""
    animais = [get_animal(a) for a in params.animal_ids]
    animais = [a for a in animais if a]
    if not animais:
        return {"receita": 0, "custo": 0, "lucro": 0, "n": 0}

    lot_ref = _novo_lot_ref(params, len(animais))
    with _conn() as con:
        _recusar_animal_que_nao_pode_ser_vendido(con, animais)
        return _registrar_venda_em(con, animais, params, lot_ref)


def _grupo_da_venda(con, sale_id: int) -> list[dict]:
    """As linhas vigentes da venda a que `sale_id` pertence: o lote inteiro (`lot_ref`), ou só a
    linha, se ela não tem lote. Cancelar ou corrigir vale para o grupo: as parcelas a receber
    nascem do total do lote, e não de cada animal."""
    s = con.execute(
        """SELECT s.*, a.id AS animal_id FROM sales s
           JOIN animals a ON a.uuid=s.animal_uuid WHERE s.id=?""", (sale_id,)).fetchone()
    if s is None:
        raise RegistroNaoEncontrado(f"Venda {sale_id} não encontrada.")
    s = dict(s)
    if s["cancelada_em"]:
        raise RegistroJaCancelado(f"A venda {sale_id} já foi cancelada em {s['cancelada_em']}.")
    if not s["lot_ref"]:
        return [s]
    rows = con.execute(
        """SELECT s.*, a.id AS animal_id FROM sales s
           JOIN animals a ON a.uuid=s.animal_uuid
           WHERE s.lot_ref=? AND s.cancelada_em IS NULL ORDER BY s.id""", (s["lot_ref"],)).fetchall()
    return [dict(r) for r in rows]


def _cancelar_parcelas_da_venda(con, grupo: list[dict]) -> int:
    """Cancela as parcelas em aberto da venda a prazo. Recusa se alguma já foi recebida (não há
    como desfazer o recebimento aqui) ou se a venda é anterior ao vínculo com as parcelas."""
    if not grupo[0]["a_prazo"]:
        return 0
    ref = grupo[0]["lot_ref"]
    if not ref:
        raise RevisaoNaoPermitida(
            "Esta venda a prazo é anterior ao vínculo com as parcelas a receber, que por isso não "
            "podem ser localizadas. Cancele as parcelas em Contas a receber e trate a venda à parte.")
    recebidas = con.execute(
        "SELECT COUNT(*) AS n FROM contas_receber WHERE lot_ref=? AND status='recebido'", (ref,)).fetchone()["n"]
    if recebidas:
        raise RevisaoNaoPermitida(
            f"A venda tem {recebidas} parcela(s) já recebida(s) em Contas a receber: o recebimento "
            "precisa ser tratado antes de cancelar ou corrigir a venda.")
    return con.execute(
        "UPDATE contas_receber SET status='cancelado' WHERE lot_ref=? AND status='aberto'", (ref,)).rowcount


def _cancelar_venda_em(con, sale_id: int, motivo: str, usuario: str, *, registrar_estorno: bool) -> dict:
    """Cancela a venda (o grupo todo), devolve os animais ao rebanho e cancela as parcelas em
    aberto, na conexão do chamador."""
    grupo = _grupo_da_venda(con, sale_id)
    parcelas = _cancelar_parcelas_da_venda(con, grupo)
    versoes = {}
    for linha in grupo:
        cur = con.execute(
            """UPDATE sales SET cancelada_em=?, cancelada_por=?, motivo_cancelamento=?
               WHERE id=? AND cancelada_em IS NULL""", (eventos._agora(), usuario or None, motivo, linha["id"]))
        if cur.rowcount == 0:      # outro pedido cancelou entre a leitura e a escrita
            raise RegistroJaCancelado(f"A venda {linha['id']} já foi cancelada.")
        versoes[linha["id"]] = versao_do_evento(con, linha["evento_id"])
        if registrar_estorno:
            eventos.registrar_em(
                con, linha["animal_uuid"], "estorno", usuario_registro=usuario, justificativa=motivo,
                evento_anterior_id=linha["evento_id"], versao=versoes[linha["id"]] + 1,
                observacoes=f"Cancelamento da venda de {linha['sale_date']} (R$ {linha['total_value']:.2f})")
        _devolver_ao_rebanho(con, linha["animal_uuid"], "vendido")
    return {"grupo": grupo, "parcelas": parcelas, "versoes": versoes}


@_writes
def cancelar_venda(sale_id: int, motivo: str, usuario: str, *, origem: str = "web") -> dict:
    """Cancela uma venda lançada por engano: o lote inteiro (`lot_ref`) ou a venda avulsa. As linhas
    ficam, com motivo e autor, e saem de receita, custo e lucro; os animais voltam ao rebanho
    (`ativo`, ou `carencia`); as parcelas a receber em aberto são canceladas.

    Levanta `RevisaoNaoPermitida` (sem motivo, parcela já recebida, venda a prazo anterior ao
    vínculo com as parcelas), `RegistroNaoEncontrado` ou `RegistroJaCancelado`; em qualquer uma
    nada é gravado."""
    motivo = motivo_obrigatorio(motivo)
    with _conn() as con:
        r = _cancelar_venda_em(con, sale_id, motivo, usuario, registrar_estorno=True)
        for linha in r["grupo"]:
            eventos.auditar_em(
                con, "cancelar_venda", usuario=usuario, entidade="sales", entidade_id=linha["id"],
                registro_anterior=foto(linha), motivo=motivo, origem=origem)
    return {"cancelada": [l["id"] for l in r["grupo"]], "animais": [l["animal_id"] for l in r["grupo"]],
            "parcelas_canceladas": r["parcelas"]}


@_writes
def corrigir_venda(sale_id: int, params: SaleParams, motivo: str, usuario: str, *,
                   origem: str = "web") -> dict:
    """Corrige uma venda: cancela o grupo (o lote inteiro, ou a venda avulsa) e grava a certa,
    ligada a ele, na mesma transação. Vale tudo o que `register_sale` aceita (animais, preço,
    data, comprador, a prazo): a venda nova mantém o `lot_ref` quando o grupo tinha um.

    O peso na venda dos animais que já estavam nela é o do registro original, e não o peso de hoje.
    Quem sai da venda volta ao rebanho e ganha o evento de estorno (a trilha dele fecha, como no
    cancelamento); quem entra tem de poder ser vendido (`ativo` ou `carencia`).
    Recusas (motivo, parcela recebida, abate em carência, animal que não pode ser vendido) não
    gravam nada: a original continua valendo."""
    motivo = motivo_obrigatorio(motivo)
    animais = [a for a in (get_animal(i) for i in params.animal_ids) if a]
    if not animais:
        raise RevisaoNaoPermitida("Escolha ao menos um animal para a venda corrigida.")
    with _conn() as con:
        r = _cancelar_venda_em(con, sale_id, motivo, usuario, registrar_estorno=False)
        grupo = r["grupo"]
        antiga = {l["animal_uuid"]: l for l in grupo}
        # Quem já estava na venda voltou ao rebanho no cancelamento acima; só quem entra é conferido.
        _recusar_animal_que_nao_pode_ser_vendido(con, [a for a in animais if a["uuid"] not in antiga])
        animais = [{**a, "current_weight": antiga[a["uuid"]]["weight_kg"]}
                   if a["uuid"] in antiga and antiga[a["uuid"]]["weight_kg"] is not None else a
                   for a in animais]
        cadeia = {}
        for a in animais:
            ant = antiga.get(a["uuid"])
            cadeia[a["uuid"]] = {
                "corrige_id": (ant or grupo[0])["id"], "justificativa": motivo,
                "evento_anterior_id": ant["evento_id"] if ant else None,
                "versao": r["versoes"][ant["id"]] + 1 if ant else 1}
        lot_ref = grupo[0]["lot_ref"] or _novo_lot_ref(params, len(animais))
        nova = _registrar_venda_em(con, animais, params, lot_ref, cadeia=cadeia)
        ficam = {a["uuid"] for a in animais}
        retirados = [l for l in grupo if l["animal_uuid"] not in ficam]
        for linha in retirados:
            eventos.registrar_em(
                con, linha["animal_uuid"], "estorno", usuario_registro=usuario, justificativa=motivo,
                evento_anterior_id=linha["evento_id"], versao=r["versoes"][linha["id"]] + 1,
                observacoes=f"Retirado da venda de {linha['sale_date']} na correção (R$ {linha['total_value']:.2f})")
        acrescentados = [a["id"] for a in animais if a["uuid"] not in antiga]
        for linha in grupo:
            eventos.auditar_em(
                con, "corrigir_venda", usuario=usuario, entidade="sales", entidade_id=linha["id"],
                registro_anterior=foto(linha),
                registro_posterior={"lot_ref": lot_ref, "animais": len(animais), "receita": nova["receita"],
                                    "data": params.sale_date, "comprador": params.buyer,
                                    "retirados": [l["animal_id"] for l in retirados],
                                    "acrescentados": acrescentados},
                motivo=motivo, origem=origem)
    return {"cancelada": [l["id"] for l in grupo], "lot_ref": lot_ref, "receita": nova["receita"],
            "n": nova["n"], "parcelas_canceladas": r["parcelas"],
            "parcelas_a_receber": nova["parcelas_a_receber"],
            "retirados": [l["animal_id"] for l in retirados], "acrescentados": acrescentados}


def get_sales(start_date: Optional[str] = None,
              end_date: Optional[str] = None, incluir_canceladas: bool = False) -> list[dict]:
    sql = ("SELECT s.*, a.id AS animal_id, a.breed, a.sex, a.carcass_yield "
           "FROM sales s LEFT JOIN animals a ON a.uuid=s.animal_uuid WHERE 1=1")
    if not incluir_canceladas:
        sql += " AND s.cancelada_em IS NULL"
    args: list = []
    if start_date:
        sql += " AND s.sale_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND s.sale_date <= ?"; args.append(end_date)
    sql += " ORDER BY s.sale_date DESC, s.id DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def listar_contas_receber(status: Optional[str] = None) -> list[dict]:
    """Parcelas de venda a prazo, mais próximas do vencimento primeiro.

    `status=None` traz todas; `"aberto"`/`"recebido"`/`"cancelado"` filtra.
    Espelha `repositories.compras.listar_contas_pagar`.
    """
    sql = "SELECT * FROM contas_receber WHERE 1=1"
    args: list = []
    if status:
        sql += " AND status=?"
        args.append(status)
    sql += " ORDER BY vencimento ASC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


@_writes
def marcar_recebido(conta_id: int, data_recebimento: str, forma_recebimento: str = "") -> bool:
    with _conn() as con:
        cur = con.execute(
            """UPDATE contas_receber SET status='recebido', data_recebimento=?,
               forma_recebimento=? WHERE id=? AND status='aberto'""",
            (data_recebimento, forma_recebimento, conta_id))
        return cur.rowcount > 0


@_writes
def cancelar_receber(conta_id: int) -> bool:
    """Cancela uma conta a receber em aberto — não apaga (venda desfeita, etc.)."""
    with _conn() as con:
        cur = con.execute(
            "UPDATE contas_receber SET status='cancelado' WHERE id=? AND status='aberto'",
            (conta_id,))
        return cur.rowcount > 0


def _insumo_cost_by_reason(con, reasons: tuple, start=None, end=None) -> float:
    """Custo dos insumos consumidos (saída) por motivo, usando o custo unitário atual."""
    placeholders = ",".join("?" for _ in reasons)
    sql = ("SELECT COALESCE(SUM(t.quantity * i.cost_per_unit),0) AS total "
           "FROM insumo_transactions t JOIN insumos i ON i.id=t.insumo_id "
           f"WHERE t.type='saida' AND t.reason IN ({placeholders})")
    args = list(reasons)
    if start:
        sql += " AND t.transaction_date >= ?"; args.append(start)
    if end:
        sql += " AND t.transaction_date <= ?"; args.append(end)
    row = con.execute(sql, args).fetchone()
    return round(float((row["total"] if row else 0) or 0), 2)


def get_insumo_compras(start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> list[dict]:
    """Compras de insumo, com o nome e o custo por unidade já resolvidos.

    `services.lancamentos.normalizar` (spec 0034) espera `type == "compra"` em
    cada linha, mas o schema real grava compra como `type='entrada'` +
    `reason='compra'` (ver `database.add_insumo_entry`) — `type='compra'`
    nunca existiu de fato. Esta função já filtra pelo par certo; quem chama
    não precisa saber da diferença.
    """
    sql = ("SELECT t.transaction_date, t.quantity, t.compra_id, "
           "i.name AS insumo_nome, i.cost_per_unit AS insumo_cost_per_unit "
           "FROM insumo_transactions t JOIN insumos i ON i.id=t.insumo_id "
           "WHERE t.type='entrada' AND t.reason='compra'")
    args: list = []
    if start_date:
        sql += " AND t.transaction_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND t.transaction_date <= ?"; args.append(end_date)
    sql += " ORDER BY t.transaction_date DESC, t.id DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def get_financial_summary(start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> dict:
    """Planilha financeira consolidada do período (todas as saídas e entradas).

    ⚠️ `_insumo_cost_by_reason` morou em `database.py` desde o refactor A2
    (2026-07-31, #24) e nunca foi trazida para cá — toda chamada real a esta
    função estourava `NameError`, porque `database.py` importa **de**
    `repositories/`, nunca o contrário. Corrigido em 2026-08-12: a função
    passou a viver aqui, ao lado de quem a usa.
    """
    def _period(col):
        s, a = "", []
        if start_date: s += f" AND {col} >= ?"; a.append(start_date)
        if end_date:   s += f" AND {col} <= ?"; a.append(end_date)
        return s, a

    def _scalar(con, sql, args):
        row = con.execute(sql, args).fetchone()
        return float((row["t"] if row else 0) or 0)

    with _conn() as con:
        # Saídas
        ps, pa = _period("cost_date")
        compra = _scalar(con,
            "SELECT COALESCE(SUM(amount),0) t FROM animal_costs WHERE cost_type='compra' AND cancelada_em IS NULL"+ps, pa)
        operacional = _scalar(con,
            "SELECT COALESCE(SUM(amount),0) t FROM animal_costs WHERE cost_type='operacional' AND cancelada_em IS NULL"+ps, pa)
        fs, fa = _period("cost_date")
        fixos = _scalar(con,
            "SELECT COALESCE(SUM(amount),0) t FROM fixed_costs WHERE cancelada_em IS NULL"+fs, fa)
        medicamentos = _insumo_cost_by_reason(con, ("uso_animal",), start_date, end_date)
        nutricao     = _insumo_cost_by_reason(con, ("trato_lote",), start_date, end_date)
        # Perda por mortalidade (informativa — o custo já está nas saídas acima)
        ds, dd = _period("death_date")
        perda_mort = _scalar(con,
            "SELECT COALESCE(SUM(cost_at_death),0) t FROM deaths WHERE cancelada_em IS NULL"+ds, dd)
        # Entradas
        ss, sa = _period("sale_date")
        rows_v = con.execute(
            "SELECT sale_type, COALESCE(SUM(total_value),0) receita, COALESCE(SUM(profit),0) lucro, COUNT(*) n "
            "FROM sales WHERE cancelada_em IS NULL"+ss+" GROUP BY sale_type", sa
        ).fetchall()

    vendas = {r["sale_type"]: {"receita": round(float(r["receita"]),2),
                               "lucro": round(float(r["lucro"]),2),
                               "n": r["n"]} for r in rows_v}
    receita_total = round(sum(v["receita"] for v in vendas.values()), 2)
    saidas_total = round(float(compra)+float(operacional)+float(fixos)+medicamentos+nutricao, 2)
    return {
        "compra_animais":    round(float(compra), 2),
        "operacional":       round(float(operacional), 2),
        "custos_fixos":      round(float(fixos), 2),
        "medicamentos":      medicamentos,
        "nutricao":          nutricao,
        "saidas_total":      saidas_total,
        "perda_mortalidade": round(perda_mort, 2),
        "vendas":            vendas,
        "receita_total":     receita_total,
        "resultado":         round(receita_total - saidas_total, 2),
    }


@_writes
def register_death(animal_id: str, death_date: str, cause: str,
                   operator: str = "", notes: str = "") -> dict:
    """Registra o óbito de um animal: muda status para 'morto', grava a causa e
    contabiliza o custo investido como perda."""
    a = get_animal(animal_id)
    if not a:
        return {"ok": False}
    custo = get_total_cost(animal_id)
    with _conn() as con:
        evento = eventos.registrar_em(
            con, a["uuid"], "morte", ocorrido_em=death_date,
            usuario_registro=operator,
            observacoes=f"causa: {cause}; perda de R$ {custo:.2f}")
        con.execute(
            """INSERT INTO deaths
               (animal_uuid,death_date,cause,lote_id,weight_at_death,
                cost_at_death,operator,notes,evento_id)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (a["uuid"], death_date, cause, a.get("lote_id"),
             a["current_weight"], custo, operator, notes, evento.get("id")),
        )
        con.execute("UPDATE animals SET status='morto' WHERE id=?", (animal_id,))
    return {"ok": True, "perda": round(custo, 2)}


def _devolver_ao_rebanho(con, animal_uuid: str, de: str) -> str:
    """Tira o animal de `morto` ou `vendido` ao cancelar o registro: volta `ativo`, ou `carencia`
    se ainda houver carência vigente. Só muda quem está mesmo em `de`. Devolve o novo status."""
    aplicacoes = [dict(m) for m in con.execute(
        """SELECT med_date, withdrawal_days FROM medications
           WHERE animal_uuid=? AND withdrawal_days > 0 AND cancelada_em IS NULL""",
        (animal_uuid,)).fetchall()]
    status = "carencia" if fim_da_carencia(aplicacoes, date.today()) else "ativo"
    con.execute("UPDATE animals SET status=? WHERE uuid=? AND status=?", (status, animal_uuid, de))
    return status


def get_morte_vigente(animal_id: str) -> Optional[dict]:
    """O óbito vigente (não cancelado) do animal, ou None."""
    with _conn() as con:
        r = con.execute(
            """SELECT d.*, a.id AS animal_id FROM deaths d JOIN animals a ON a.uuid=d.animal_uuid
               WHERE a.id=? AND d.cancelada_em IS NULL ORDER BY d.death_date DESC, d.id DESC LIMIT 1""",
            (animal_id,)).fetchone()
    return dict(r) if r else None


def _cancelar_morte_em(con, death_id: int, motivo: str, usuario: str, *, registrar_estorno: bool,
                       animal_id: Optional[str] = None) -> dict:
    """Marca o óbito como cancelado, na conexão do chamador."""
    d = con.execute(
        """SELECT d.*, a.id AS animal_id FROM deaths d
           JOIN animals a ON a.uuid=d.animal_uuid WHERE d.id=?""", (death_id,)).fetchone()
    if d is None or (animal_id is not None and d["animal_id"] != animal_id):
        raise RegistroNaoEncontrado(f"Óbito {death_id} não encontrado.")
    d = dict(d)
    if d["cancelada_em"]:
        raise RegistroJaCancelado(f"O óbito {death_id} já foi cancelado em {d['cancelada_em']}.")
    cur = con.execute(
        """UPDATE deaths SET cancelada_em=?, cancelada_por=?, motivo_cancelamento=?
           WHERE id=? AND cancelada_em IS NULL""", (eventos._agora(), usuario or None, motivo, death_id))
    if cur.rowcount == 0:      # outro pedido cancelou entre a leitura e a escrita
        raise RegistroJaCancelado(f"O óbito {death_id} já foi cancelado.")
    versao = versao_do_evento(con, d["evento_id"])
    if registrar_estorno:
        eventos.registrar_em(
            con, d["animal_uuid"], "estorno", usuario_registro=usuario, justificativa=motivo,
            evento_anterior_id=d["evento_id"], versao=versao + 1,
            observacoes=f"Cancelamento do óbito de {d['death_date']} (causa: {d['cause']})")
    return {"morte": d, "foto": foto(d), "versao_evento": versao}


@_writes
def cancelar_morte(death_id: int, motivo: str, usuario: str, *, origem: str = "web",
                   animal_id: Optional[str] = None) -> dict:
    """Cancela um óbito registrado por engano. A linha fica, com motivo e autor, e o animal volta
    ao rebanho: `ativo`, ou `carencia` se ainda houver carência vigente.

    Levanta `RevisaoNaoPermitida` (sem motivo), `RegistroNaoEncontrado` ou `RegistroJaCancelado`;
    em qualquer uma nada é gravado."""
    motivo = motivo_obrigatorio(motivo)
    with _conn() as con:
        r = _cancelar_morte_em(con, death_id, motivo, usuario, registrar_estorno=True, animal_id=animal_id)
        d = r["morte"]
        status = _devolver_ao_rebanho(con, d["animal_uuid"], "morto")
        eventos.auditar_em(
            con, "cancelar_obito", usuario=usuario, entidade="deaths", entidade_id=death_id,
            registro_anterior=r["foto"], registro_posterior={"status": status}, motivo=motivo, origem=origem)
    return {"cancelada": death_id, "animal_id": d["animal_id"], "status": status}


@_writes
def corrigir_morte(death_id: int, death_date: str, cause: str, motivo: str, usuario: str, *,
                   notes: str = "", origem: str = "web", animal_id: Optional[str] = None) -> dict:
    """Corrige data, causa ou observação de um óbito: cancela o original e grava o certo, ligado a
    ele (evento novo na cadeia), na mesma transação. O animal continua `morto`; peso e custo no
    óbito são os do registro original."""
    motivo = motivo_obrigatorio(motivo)
    with _conn() as con:
        r = _cancelar_morte_em(con, death_id, motivo, usuario, registrar_estorno=False, animal_id=animal_id)
        d = r["morte"]
        evento = eventos.registrar_em(
            con, d["animal_uuid"], "morte", ocorrido_em=death_date, usuario_registro=usuario,
            justificativa=motivo, evento_anterior_id=d["evento_id"], versao=r["versao_evento"] + 1,
            observacoes=f"causa: {cause}; perda de R$ {float(d['cost_at_death'] or 0):.2f}")
        nova = con.execute(
            """INSERT INTO deaths
               (animal_uuid,death_date,cause,lote_id,weight_at_death,cost_at_death,operator,notes,
                evento_id,corrige_id)
               VALUES(?,?,?,?,?,?,?,?,?,?) RETURNING id""",
            (d["animal_uuid"], death_date, cause, d["lote_id"], d["weight_at_death"], d["cost_at_death"],
             usuario or d["operator"], notes, evento.get("id"), death_id)).fetchone()["id"]
        eventos.auditar_em(
            con, "corrigir_obito", usuario=usuario, entidade="deaths", entidade_id=death_id,
            registro_anterior=r["foto"],
            registro_posterior={"novo_obito": nova, "data": death_date, "causa": cause},
            motivo=motivo, origem=origem)
    return {"cancelada": death_id, "nova": nova, "animal_id": d["animal_id"]}


def get_deaths(start_date: Optional[str] = None,
               end_date: Optional[str] = None, incluir_canceladas: bool = False) -> list[dict]:
    sql = ("SELECT d.*, a.id AS animal_id, a.breed, a.sex, l.name AS lote_name "
           "FROM deaths d LEFT JOIN animals a ON a.uuid=d.animal_uuid "
           "LEFT JOIN lotes l ON l.id=d.lote_id WHERE 1=1")
    if not incluir_canceladas:
        sql += " AND d.cancelada_em IS NULL"
    args: list = []
    if start_date:
        sql += " AND d.death_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND d.death_date <= ?"; args.append(end_date)
    sql += " ORDER BY d.death_date DESC, d.id DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def get_mortality_stats(start_date: Optional[str] = None,
                        end_date: Optional[str] = None) -> dict:
    """Taxas de mortalidade: geral, por causa e por piquete."""
    deaths = get_deaths(start_date, end_date)
    n_deaths = len(deaths)
    # População exposta: animais que já haviam entrado até a data final
    with _conn() as con:
        if end_date:
            expostos = con.execute(
                "SELECT COUNT(*) c FROM animals WHERE entry_date <= ?", (end_date,)
            ).fetchone()["c"]
        else:
            expostos = con.execute("SELECT COUNT(*) c FROM animals").fetchone()["c"]
    taxa_geral = round(n_deaths / expostos * 100, 1) if expostos else 0.0

    por_causa: dict = {}
    por_lote: dict = {}
    perda_total = 0.0
    for d in deaths:
        por_causa[d["cause"]] = por_causa.get(d["cause"], 0) + 1
        chave_lote = d.get("lote_name") or d.get("lote_id") or "Sem piquete"
        por_lote[chave_lote] = por_lote.get(chave_lote, 0) + 1
        perda_total += float(d.get("cost_at_death") or 0)

    return {
        "n_deaths":    n_deaths,
        "expostos":    expostos,
        "taxa_geral":  taxa_geral,
        "por_causa":   por_causa,
        "por_lote":    por_lote,
        "perda_total": round(perda_total, 2),
    }


def get_category_prices() -> dict:
    """Retorna {(age_band, sex): price_per_kg} para consulta rápida."""
    with _conn() as con:
        rows = con.execute("SELECT age_band, sex, price_per_kg FROM category_prices").fetchall()
    return {(r["age_band"], r["sex"]): r["price_per_kg"] for r in rows}


@_writes
def set_category_price(age_band: str, sex: str, price_per_kg: float) -> None:
    """Insere/atualiza o valor esperado por kg de uma categoria."""
    today = date.today().isoformat()
    with _conn() as con:
        if _conexao.USE_PG:
            con.execute(
                "INSERT INTO category_prices (age_band,sex,price_per_kg,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT (age_band,sex) DO UPDATE SET price_per_kg=EXCLUDED.price_per_kg, updated_at=EXCLUDED.updated_at",
                (age_band, sex, price_per_kg, today),
            )
        else:
            con.execute(
                "INSERT OR REPLACE INTO category_prices (age_band,sex,price_per_kg,updated_at) VALUES(?,?,?,?)",
                (age_band, sex, price_per_kg, today),
            )


def get_expected_price_kg(age_band: str, sex: str) -> float:
    return get_category_prices().get((age_band, sex), 0.0)


def expected_sale_value(animal: dict) -> float:
    """Valor esperado de venda do animal = peso atual × preço/kg da categoria.

    A consulta (preço da categoria) mora aqui — é `_conn()`, e só este
    módulo acessa banco (R1). A conta em si é `services.financeiro`.
    """
    band = get_age_category(animal.get("birth_date"))
    price = get_expected_price_kg(band, animal["sex"])
    return valor_esperado_venda(animal["current_weight"], price)
