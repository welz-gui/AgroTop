"""Hierarquia Organização → Produtor → Propriedade (ADR 0004 · etapa B4 · PNIB §3).

O PNIB exige essa estrutura **mesmo com uma fazenda só** (§3), porque o titular
pode ter várias propriedades e movimentar animais entre elas (§8.1). Antes desta
etapa, `lote_id` (piquete) era a única noção de lugar no sistema — e piquete não
é estabelecimento perante o órgão.

O identificador da propriedade é **interno e imutável** (§3.4). O `codigo_oficial`
do estabelecimento pode mudar, ou nem existir ainda — mesma razão de o animal ter
uuid separado do brinco.

Camada de dados (ROADMAP R1/R9): aqui mora o SQL, e só aqui.
"""

import uuid as _uuid
from typing import Optional

from .conexao import _cache, _conn, _writes

# Nome da propriedade criada automaticamente quando o banco ainda não tem
# nenhuma. Genérico de propósito: inventar um nome de fazenda seria pior que
# deixar claro que falta preencher.
NOME_PADRAO = "Propriedade principal"


def novo_id() -> str:
    """Gerado em Python, não pelo banco — `gen_random_uuid()` não existe no
    SQLite, e a compatibilidade dupla é requisito (mesma razão de `novo_uuid`)."""
    return str(_uuid.uuid4())


@_cache
def listar(*, apenas_ativas: bool = True) -> list[dict]:
    """Propriedades, com o nome do produtor e da organização."""
    sql = """SELECT p.*, pr.nome AS produtor_nome, o.nome AS organizacao_nome
             FROM properties p
             JOIN produtores pr   ON pr.id = p.produtor_id
             JOIN organizacoes o  ON o.id  = pr.organizacao_id"""
    if apenas_ativas:
        sql += " WHERE p.situacao='ativa'"
    sql += " ORDER BY p.nome"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql).fetchall()]


def listar_produtores() -> list[dict]:
    """Produtores com a organização a que pertencem.

    A tela de cadastro precisa saber sob qual titular a propriedade nasce: o
    `produtor_id` é escolhido **na criação e nunca mais** — trocá-lo depois é
    transferência de titularidade, que é evento do §8, não edição de cadastro.
    """
    with _conn() as con:
        return [dict(r) for r in con.execute(
            "SELECT pr.*, o.nome AS organizacao_nome FROM produtores pr "
            "JOIN organizacoes o ON o.id = pr.organizacao_id "
            "ORDER BY o.nome, pr.nome").fetchall()]


def get(property_id: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM properties WHERE id=?", (property_id,)).fetchone()
    return dict(row) if row else None


def padrao() -> Optional[dict]:
    """A propriedade a assumir quando o usuário não escolheu nenhuma.

    Com uma só, é ela. Com várias, é a mais antiga — e a interface precisa
    passar a perguntar, porque assumir vira erro silencioso de localização.
    """
    ativas = listar()
    return ativas[0] if ativas else None


@_writes
def criar_organizacao(nome: str, *, documento: str = "",
                      responsavel_legal: str = "", contato: str = "") -> str:
    oid = novo_id()
    with _conn() as con:
        con.execute(
            """INSERT INTO organizacoes (id,nome,documento,responsavel_legal,contato)
               VALUES(?,?,?,?,?)""",
            (oid, nome, documento or None, responsavel_legal or None, contato or None))
    return oid


@_writes
def criar_produtor(organizacao_id: str, nome: str, *, documento: str = "",
                   inscricao_estadual: str = "", contato: str = "") -> str:
    pid = novo_id()
    with _conn() as con:
        con.execute(
            """INSERT INTO produtores
               (id,organizacao_id,nome,documento,inscricao_estadual,contato)
               VALUES(?,?,?,?,?,?)""",
            (pid, organizacao_id, nome, documento or None,
             inscricao_estadual or None, contato or None))
    return pid


@_writes
def criar_propriedade(produtor_id: str, nome: str, *,
                      codigo_oficial: str = "", municipio: str = "",
                      uf: str = "", endereco: str = "",
                      latitude: Optional[float] = None,
                      longitude: Optional[float] = None,
                      atividade: str = "", inicio: str = "") -> str:
    prid = novo_id()
    with _conn() as con:
        con.execute(
            """INSERT INTO properties
               (id,produtor_id,nome,codigo_oficial,municipio,uf,endereco,
                latitude,longitude,atividade,inicio)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (prid, produtor_id, nome, codigo_oficial or None, municipio or None,
             uf or None, endereco or None, latitude, longitude,
             atividade or None, inicio or None))
    return prid


@_writes
def atualizar(property_id: str, **campos) -> bool:
    """Atualiza dados cadastrais. **`id` e `produtor_id` não são alteráveis.**

    O `id` é imutável por exigência do §3.4. Mudar `produtor_id` seria
    transferência de titularidade, que é evento regulatório (§8) e não edição
    de cadastro — vai na etapa B6.
    """
    permitidos = {"nome", "codigo_oficial", "municipio", "uf", "endereco",
                  "latitude", "longitude", "poligono", "atividade",
                  "situacao", "inicio", "encerramento"}
    campos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos:
        return False
    sets = ", ".join(f"{k}=?" for k in campos)
    with _conn() as con:
        con.execute(f"UPDATE properties SET {sets} WHERE id=?",
                    (*campos.values(), property_id))
    return True


def _seed_hierarquia(con) -> Optional[str]:
    """Cria a hierarquia mínima se o banco ainda não tiver nenhuma propriedade.

    Sem isso, um banco novo não tem onde ancorar animal nem piquete. Os nomes
    são genéricos de propósito: inventar razão social e CNPJ seria pior que
    deixar evidente que falta preencher.

    Devolve o `property_id` criado, ou o existente. Idempotente.
    """
    row = con.execute("SELECT id FROM properties ORDER BY created_at LIMIT 1").fetchone()
    if row:
        return row["id"]

    oid, pid, prid = novo_id(), novo_id(), novo_id()
    con.execute("INSERT INTO organizacoes (id,nome) VALUES(?,?)",
                (oid, "Organização principal"))
    con.execute("INSERT INTO produtores (id,organizacao_id,nome) VALUES(?,?,?)",
                (pid, oid, "Produtor principal"))
    con.execute("INSERT INTO properties (id,produtor_id,nome) VALUES(?,?,?)",
                (prid, pid, NOME_PADRAO))
    return prid


def _backfill_property_id(con) -> int:
    """Aponta animais e piquetes sem propriedade para a propriedade padrão.

    Só faz sentido enquanto existe **uma** propriedade — com várias, adivinhar
    a que pertence cada animal seria inventar localização, e localização errada
    num sistema de rastreabilidade é pior que localização ausente.
    """
    props = con.execute("SELECT id FROM properties").fetchall()
    if len(props) != 1:
        return 0
    prid = props[0]["id"]

    total = 0
    for tabela in ("animals", "lotes"):
        cur = con.execute(
            f"UPDATE {tabela} SET property_id=? WHERE property_id IS NULL", (prid,))
        total += getattr(cur, "rowcount", 0) or 0
    return total
