"""Custos, custos fixos, vendas, óbitos e preços por categoria.

Camada de dados (ROADMAP.md R1/R9): aqui mora o SQL, e só aqui.
Sem regra de negócio — cálculo e decisão ficam em `services/`.
Sem Streamlit no topo do módulo.
"""

from datetime import date, datetime
from typing import Optional

from . import conexao as _conexao
from .animais import get_animal, uuid_de
from . import eventos
from .conexao import _cache, _conn, _writes

# `expected_sale_value` é regra de negócio (peso × preço da categoria) que ficou
# nesta camada por ora — mover para `services/` é trabalho posterior. Enquanto
# isso, importa a regra de idade em vez de reimplementá-la (ROADMAP R8).
from services.zootecnia import get_age_category


@_cache
def _costs_by_animal() -> dict:
    """Soma de custos por animal. 1 consulta."""
    with _conn() as con:
        rows = con.execute(
            """SELECT a.id AS animal_id, COALESCE(SUM(c.amount),0) AS total
               FROM animal_costs c JOIN animals a ON a.uuid=c.animal_uuid
               GROUP BY a.id"""
        ).fetchall()
    return {r["animal_id"]: round(float(r["total"]), 2) for r in rows}


def get_total_cost(animal_id: str) -> float:
    return _costs_by_animal().get(animal_id, 0.0)


def get_animal_costs(animal_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT c.*, a.id AS animal_id
               FROM animal_costs c JOIN animals a ON a.uuid=c.animal_uuid
               WHERE a.id=? ORDER BY c.cost_date DESC""",
            (animal_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@_writes
def add_animal_cost(animal_id, cost_type, description, amount, cost_date, notes="") -> None:
    with _conn() as con:
        uuid = uuid_de(con, animal_id)
        if uuid is None:
            raise ValueError(f"Animal {animal_id} não encontrado.")
        con.execute(
            "INSERT INTO animal_costs (animal_uuid,cost_type,description,amount,cost_date,notes) VALUES(?,?,?,?,?,?)",
            (uuid, cost_type, description, amount, cost_date, notes),
        )


@_writes
def add_fixed_cost(category, description, amount, cost_date, recurring=0, notes="") -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO fixed_costs (category,description,amount,cost_date,recurring,notes)
               VALUES(?,?,?,?,?,?)""",
            (category, description, amount, cost_date, int(recurring), notes),
        )


def get_fixed_costs(start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> list[dict]:
    sql, args = "SELECT * FROM fixed_costs WHERE 1=1", []
    if start_date:
        sql += " AND cost_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND cost_date <= ?"; args.append(end_date)
    sql += " ORDER BY cost_date DESC, id DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def get_total_fixed_costs(start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> float:
    sql, args = "SELECT COALESCE(SUM(amount),0) as total FROM fixed_costs WHERE 1=1", []
    if start_date:
        sql += " AND cost_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND cost_date <= ?"; args.append(end_date)
    with _conn() as con:
        row = con.execute(sql, args).fetchone()
    return round(float(row["total"]), 2)


@_writes
def delete_fixed_cost(cost_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM fixed_costs WHERE id=?", (cost_id,))


def get_fixed_costs_by_category(start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> list[dict]:
    sql = "SELECT category, COALESCE(SUM(amount),0) as total FROM fixed_costs WHERE 1=1"
    args: list = []
    if start_date:
        sql += " AND cost_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND cost_date <= ?"; args.append(end_date)
    sql += " GROUP BY category ORDER BY total DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


@_writes
def register_sale(animal_ids: list, sale_date: str, sale_type: str,
                  pricing_mode: str, value: float, buyer: str = "",
                  operator: str = "", notes: str = "") -> dict:
    """Registra a venda de um ou mais animais.
    - pricing_mode='kg':     `value` é o preço por kg (cada animal: peso × preço).
    - pricing_mode='cabeca': `value` é o valor por cabeça (igual para cada animal).
    - pricing_mode='lote':   `value` é o valor TOTAL do lote, rateado pelo peso.
    Retorna {'receita':..., 'custo':..., 'lucro':..., 'n':...}."""
    animais = [get_animal(a) for a in animal_ids]
    animais = [a for a in animais if a]
    if not animais:
        return {"receita": 0, "custo": 0, "lucro": 0, "n": 0}

    peso_total = sum(a["current_weight"] for a in animais) or 1
    lot_ref = f"V{sale_date.replace('-','')}-{int(datetime.now().timestamp())%100000}" \
              if (pricing_mode == "lote" or len(animais) > 1) else None

    tot_receita = tot_custo = 0.0
    with _conn() as con:
        for a in animais:
            if pricing_mode == "kg":
                ppk = value
                val = round(a["current_weight"] * value, 2)
            elif pricing_mode == "cabeca":
                ppk = None
                val = round(value, 2)
            else:  # lote: rateio proporcional ao peso
                ppk = None
                val = round(value * a["current_weight"] / peso_total, 2)

            custo = get_total_cost(a["id"])
            lucro = round(val - custo, 2)
            tot_receita += val
            tot_custo += custo

            con.execute(
                """INSERT INTO sales
                   (animal_uuid,sale_date,sale_type,pricing_mode,weight_kg,
                    price_per_kg,total_value,buyer,lot_ref,cost_at_sale,profit,
                    operator,notes)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (a["uuid"], sale_date, sale_type, pricing_mode,
                 a["current_weight"], ppk,
                 val, buyer or None, lot_ref, custo, lucro, operator, notes),
            )
            con.execute("UPDATE animals SET status='vendido' WHERE id=?", (a["id"],))
            # Venda e obito mudam status por SQL direto, sem passar por
            # update_animal_status -- entao o evento precisa ser registrado aqui.
            eventos.registrar_em(
                con, a["uuid"], "venda", ocorrido_em=sale_date,
                usuario_registro=operator, documento=lot_ref,
                observacoes=f"R$ {val:.2f} para {buyer or 'comprador nao informado'}")
    return {"receita": round(tot_receita, 2), "custo": round(tot_custo, 2),
            "lucro": round(tot_receita - tot_custo, 2), "n": len(animais),
            "lot_ref": lot_ref}


def get_sales(start_date: Optional[str] = None,
              end_date: Optional[str] = None) -> list[dict]:
    sql = ("SELECT s.*, a.id AS animal_id, a.breed, a.sex FROM sales s "
           "LEFT JOIN animals a ON a.uuid=s.animal_uuid WHERE 1=1")
    args: list = []
    if start_date:
        sql += " AND s.sale_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND s.sale_date <= ?"; args.append(end_date)
    sql += " ORDER BY s.sale_date DESC, s.id DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def get_financial_summary(start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> dict:
    """Planilha financeira consolidada do período (todas as saídas e entradas)."""
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
            "SELECT COALESCE(SUM(amount),0) t FROM animal_costs WHERE cost_type='compra'"+ps, pa)
        operacional = _scalar(con,
            "SELECT COALESCE(SUM(amount),0) t FROM animal_costs WHERE cost_type='operacional'"+ps, pa)
        fs, fa = _period("cost_date")
        fixos = _scalar(con,
            "SELECT COALESCE(SUM(amount),0) t FROM fixed_costs WHERE 1=1"+fs, fa)
        medicamentos = _insumo_cost_by_reason(con, ("uso_animal",), start_date, end_date)
        nutricao     = _insumo_cost_by_reason(con, ("trato_lote",), start_date, end_date)
        # Perda por mortalidade (informativa — o custo já está nas saídas acima)
        ds, dd = _period("death_date")
        perda_mort = _scalar(con,
            "SELECT COALESCE(SUM(cost_at_death),0) t FROM deaths WHERE 1=1"+ds, dd)
        # Entradas
        ss, sa = _period("sale_date")
        rows_v = con.execute(
            "SELECT sale_type, COALESCE(SUM(total_value),0) receita, COALESCE(SUM(profit),0) lucro, COUNT(*) n "
            "FROM sales WHERE 1=1"+ss+" GROUP BY sale_type", sa
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
        con.execute(
            """INSERT INTO deaths
               (animal_uuid,death_date,cause,lote_id,weight_at_death,
                cost_at_death,operator,notes)
               VALUES(?,?,?,?,?,?,?,?)""",
            (a["uuid"], death_date, cause, a.get("lote_id"),
             a["current_weight"], custo, operator, notes),
        )
        con.execute("UPDATE animals SET status='morto' WHERE id=?", (animal_id,))
        eventos.registrar_em(
            con, a["uuid"], "morte", ocorrido_em=death_date,
            usuario_registro=operator,
            observacoes=f"causa: {cause}; perda de R$ {custo:.2f}")
    return {"ok": True, "perda": round(custo, 2)}


def get_deaths(start_date: Optional[str] = None,
               end_date: Optional[str] = None) -> list[dict]:
    sql = ("SELECT d.*, a.id AS animal_id, a.breed, a.sex, l.name AS lote_name "
           "FROM deaths d LEFT JOIN animals a ON a.uuid=d.animal_uuid "
           "LEFT JOIN lotes l ON l.id=d.lote_id WHERE 1=1")
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
    """Valor esperado de venda do animal = peso atual × preço/kg da categoria."""
    band = get_age_category(animal.get("birth_date"))
    price = get_expected_price_kg(band, animal["sex"])
    return round(animal["current_weight"] * price, 2)


def get_category_prices_list() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM category_prices ORDER BY age_band, sex"
        ).fetchall()
    return [dict(r) for r in rows]
