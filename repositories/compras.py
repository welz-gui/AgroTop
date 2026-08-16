"""Compra de insumos com documento fiscal (Trilha 3 — Estoque → Financeiro).

"Compra atualiza estoque e financeiro na mesma operação" (ROADMAP §5, Trilha 3,
"Pronto quando"): `registrar()` grava cabeçalho, itens, entrada de estoque
(custo médio ponderado, ADR 0003) e as parcelas em `contas_pagar` numa única
transação (`_conn()`, R1) — se qualquer parte falhar, nada fica meio-gravado.

Substitui, para compra com documento fiscal, o caminho de `add_insumo_entry`
em `database.py` (que continua existindo para entrada avulsa sem nota —
doação, ajuste manual — e não gera conta a pagar).

Camada de dados (ROADMAP R1/R9): aqui mora o SQL. Regra pura (total da nota,
parcelamento) vem de `services/compras.py` (R8 — não recalculado aqui).
"""

import uuid as _uuid
from typing import Optional

from services.compras import gerar_parcelas, total_compra
from services.estoque import custo_medio_ponderado

from .conexao import _cache, _conn, _writes


def _novo_id() -> str:
    return str(_uuid.uuid4())


@_writes
def registrar(*, data_emissao: str, data_recebimento: str, itens: list[dict],
             primeiro_vencimento: str, num_parcelas: int = 1,
             fornecedor_id: Optional[int] = None, fornecedor_nome: str = "",
             documento_numero: str = "", documento_serie: str = "",
             operator: str = "", notes: str = "") -> dict:
    """Registra a compra inteira: cabeçalho, itens, estoque e contas a pagar.

    `itens`: lista de `{"insumo_id": int, "quantidade": float, "custo_unitario": float}`.
    Cada item aplica custo médio ponderado (ADR 0003) e vira uma entrada em
    `insumo_transactions` vinculada a esta compra. As parcelas usam
    `services.compras.gerar_parcelas` a partir do total real da nota.
    """
    if not itens:
        return {"ok": False, "erro": "compra sem nenhum item"}
    for item in itens:
        if float(item["quantidade"]) <= 0:
            return {"ok": False, "erro": "quantidade deve ser maior que zero"}
        if float(item["custo_unitario"]) < 0:
            return {"ok": False, "erro": "custo unitário não pode ser negativo"}

    valor_total = total_compra(itens)
    parcelas = gerar_parcelas(valor_total, num_parcelas, primeiro_vencimento)
    compra_id = _novo_id()

    with _conn() as con:
        con.execute(
            """INSERT INTO compras
               (id, fornecedor_id, fornecedor_nome, documento_numero, documento_serie,
                data_emissao, data_recebimento, valor_total, operator, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (compra_id, fornecedor_id, fornecedor_nome, documento_numero,
             documento_serie, data_emissao, data_recebimento, valor_total,
             operator, notes))

        for item in itens:
            insumo_id = item["insumo_id"]
            quantidade = float(item["quantidade"])
            custo_unitario = float(item["custo_unitario"])
            subtotal = round(quantidade * custo_unitario, 2)

            con.execute(
                """INSERT INTO compra_itens
                   (compra_id, insumo_id, quantidade, custo_unitario, subtotal)
                   VALUES (?,?,?,?,?)""",
                (compra_id, insumo_id, quantidade, custo_unitario, subtotal))

            atual = con.execute(
                "SELECT current_stock, cost_per_unit FROM insumos WHERE id=?",
                (insumo_id,)).fetchone()
            novo_custo = custo_medio_ponderado(
                float(atual["current_stock"] or 0) if atual else 0.0,
                float(atual["cost_per_unit"] or 0) if atual else 0.0,
                quantidade, custo_unitario)
            con.execute(
                "UPDATE insumos SET current_stock=current_stock+?, cost_per_unit=? WHERE id=?",
                (quantidade, novo_custo, insumo_id))
            con.execute(
                """INSERT INTO insumo_transactions
                   (insumo_id, type, quantity, reason, transaction_date, operator,
                    notes, compra_id)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (insumo_id, "entrada", quantidade, "compra", data_recebimento,
                 operator, f"compra {compra_id}", compra_id))

        rotulo_fornecedor = fornecedor_nome or "fornecedor não informado"
        rotulo_doc = documento_numero or compra_id[:8]
        for p in parcelas:
            con.execute(
                """INSERT INTO contas_pagar
                   (compra_id, fornecedor_nome, descricao, valor, vencimento,
                    parcela_numero, parcela_total, status, operator)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (compra_id, fornecedor_nome,
                 f"Compra {rotulo_doc} — {rotulo_fornecedor}",
                 p["valor"], p["vencimento"], p["numero"], p["total"],
                 "aberto", operator))

    return {"ok": True, "compra_id": compra_id, "valor_total": valor_total,
            "parcelas": len(parcelas)}


def get_compra(compra_id: str) -> Optional[dict]:
    with _conn() as con:
        c = con.execute("SELECT * FROM compras WHERE id=?", (compra_id,)).fetchone()
        if not c:
            return None
        itens = con.execute(
            """SELECT ci.*, i.name AS insumo_nome, i.unit AS insumo_unidade
               FROM compra_itens ci JOIN insumos i ON i.id=ci.insumo_id
               WHERE ci.compra_id=?""", (compra_id,)).fetchall()
        parcelas = con.execute(
            "SELECT * FROM contas_pagar WHERE compra_id=? ORDER BY parcela_numero",
            (compra_id,)).fetchall()
    out = dict(c)
    out["itens"] = [dict(i) for i in itens]
    out["parcelas"] = [dict(p) for p in parcelas]
    return out


def listar_compras(limit: int = 50) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM compras ORDER BY data_recebimento DESC, created_at DESC LIMIT ?",
            (limit,)).fetchall()
    return [dict(r) for r in rows]


def listar_contas_pagar(status: Optional[str] = None) -> list[dict]:
    """Contas a pagar, mais próximas do vencimento primeiro.

    `status=None` traz todas; `"aberto"`/`"pago"`/`"cancelado"` filtra.
    """
    sql = "SELECT * FROM contas_pagar WHERE 1=1"
    args: list = []
    if status:
        sql += " AND status=?"
        args.append(status)
    sql += " ORDER BY vencimento ASC"
    with _conn() as con:
        rows = con.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


@_writes
def marcar_pago(conta_id: int, data_pagamento: str, forma_pagamento: str = "") -> bool:
    with _conn() as con:
        cur = con.execute(
            """UPDATE contas_pagar SET status='pago', data_pagamento=?,
               forma_pagamento=? WHERE id=? AND status='aberto'""",
            (data_pagamento, forma_pagamento, conta_id))
        return cur.rowcount > 0


@_writes
def cancelar(conta_id: int) -> bool:
    """Cancela uma conta em aberto — não apaga (nota cancelada, devolução etc.)."""
    with _conn() as con:
        cur = con.execute(
            "UPDATE contas_pagar SET status='cancelado' WHERE id=? AND status='aberto'",
            (conta_id,))
        return cur.rowcount > 0
