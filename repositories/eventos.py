"""Eventos do animal e trilha de auditoria (ADR 0004 · etapa B2).

Duas tabelas append-only, com gatilhos no banco que recusam `UPDATE` e `DELETE`:

- `animal_events` — §6 do PNIB. A espinha da rastreabilidade. Evento confirmado
  não se corrige: gera-se outro apontando para ele (§6.3).
- `audit_logs` — §14.1. Quem mudou o quê, quando, de onde, com que autorização.

**Adoção incremental** (decisão do ADR 0004): por ora os eventos são
*registrados* junto das operações atuais. Derivar o estado do animal a partir
deles é passo posterior — fazer as duas coisas de uma vez seria reescrever o
sistema num salto.

Camada de dados (ROADMAP R1/R9): aqui mora o SQL, e só aqui.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from .conexao import _conn, _writes

# §6.1 — eventos mínimos. A lista é vocabulário, não restrição do banco: um tipo
# novo exigido por atualização da portaria não pode depender de migration.
TIPOS = (
    "nascimento", "cadastro_inicial", "identificacao_interna",
    "identificacao_oficial", "aplicacao_dispositivo", "leitura_conferencia",
    "perda_brinco", "dano_dispositivo", "substituicao", "retirada_autorizada",
    "entrada_propriedade", "saida_propriedade", "venda", "compra",
    "transferencia_sem_titularidade", "mudanca_titularidade",
    "emissao_gta", "cancelamento_gta", "chegada_confirmada",
    "recusa_recepcao", "manejo_sanitario", "vacinacao", "vacinacao_brucelose",
    "teste_sanitario", "tratamento", "pesagem", "mudanca_lote",
    "mudanca_categoria", "morte", "abate", "correcao", "estorno",
)

ORIGENS = ("web", "app", "integracao", "importacao")


def _agora() -> str:
    """Instante atual em ISO 8601 **com fuso**.

    A R5 manda guardar data de negócio como texto ISO simples; o §6.2 exige
    fuso nos eventos, porque a diferença entre o fato e o registro tem valor
    jurídico. São exigências diferentes para colunas diferentes.
    """
    return datetime.now(timezone.utc).isoformat()


def _json(valor) -> Optional[str]:
    if valor is None:
        return None
    return valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)


# Colunas cujo tipo DIVERGE entre os dois bancos e precisam ser normalizadas na
# leitura. No Postgres, `jsonb` volta como dict e `timestamptz` como datetime;
# no SQLite os dois voltam como texto. Sem isto, o mesmo teste passa num banco e
# quebra no outro — e o chamador teria de saber em qual está rodando.
_COLUNAS_JSON = ("anexos", "registro_anterior", "registro_posterior")
_COLUNAS_INSTANTE = ("ocorrido_em", "registrado_em")


def _normalizar(linha) -> dict:
    """Devolve sempre o mesmo formato: JSON como dict, instante como texto ISO."""
    d = dict(linha)
    for c in _COLUNAS_JSON:
        v = d.get(c)
        if isinstance(v, str):
            try:
                d[c] = json.loads(v)
            except (ValueError, TypeError):
                pass          # texto que não é JSON fica como está
    for c in _COLUNAS_INSTANTE:
        v = d.get(c)
        if v is not None and not isinstance(v, str):
            d[c] = v.isoformat()
    return d


@_writes
def registrar(animal_uuid: str, tipo: str, *,
              ocorrido_em: Optional[str] = None,
              usuario_registro: str = "",
              responsavel: str = "",
              origem_informacao: str = "web",
              propriedade_id: Optional[str] = None,
              local_interno: Optional[str] = None,
              latitude: Optional[float] = None,
              longitude: Optional[float] = None,
              observacoes: str = "",
              documento: Optional[str] = None,
              anexos=None,
              justificativa: str = "",
              evento_anterior_id: Optional[int] = None,
              versao: int = 1) -> dict:
    """Grava um evento. Nunca sobrescreve nada.

    `ocorrido_em` é quando o fato aconteceu; se omitido, assume agora. O
    `registrado_em` é sempre agora — os dois são gravados separados de propósito
    (§6.2), e é o atraso entre eles que uma auditoria consegue enxergar.
    """
    if tipo not in TIPOS:
        return {"ok": False, "erro": f"Tipo de evento desconhecido: '{tipo}'."}

    agora = _agora()
    with _conn() as con:
        existe = con.execute(
            "SELECT 1 FROM animals WHERE uuid=?", (animal_uuid,)).fetchone()
        if existe is None:
            return {"ok": False, "erro": f"Animal {animal_uuid} não encontrado."}

        con.execute(
            """INSERT INTO animal_events
               (animal_uuid,tipo,ocorrido_em,registrado_em,propriedade_id,
                local_interno,responsavel,usuario_registro,origem_informacao,
                latitude,longitude,observacoes,documento,anexos,
                justificativa,evento_anterior_id,versao)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (animal_uuid, tipo, ocorrido_em or agora, agora, propriedade_id,
             local_interno, responsavel or None, usuario_registro or None,
             origem_informacao, latitude, longitude, observacoes or None,
             documento, _json(anexos), justificativa or None,
             evento_anterior_id, versao),
        )
    return {"ok": True}


@_writes
def corrigir(evento_id: int, justificativa: str, *,
             usuario_registro: str,
             tipo: str = "correcao",
             observacoes: str = "") -> dict:
    """Corrige um evento **criando outro** que aponta para ele (§6.3).

    O original permanece. É o que permite reconstruir não só o que se sabe hoje,
    mas o que se acreditava antes — e quem mudou de ideia.
    """
    if not justificativa.strip():
        return {"ok": False, "erro": "Correção exige justificativa (§6.3)."}
    if tipo not in ("correcao", "estorno"):
        return {"ok": False, "erro": "Tipo deve ser 'correcao' ou 'estorno'."}

    with _conn() as con:
        orig = con.execute(
            "SELECT animal_uuid, versao FROM animal_events WHERE id=?",
            (evento_id,)).fetchone()
    if orig is None:
        return {"ok": False, "erro": f"Evento {evento_id} não encontrado."}

    return registrar(
        orig["animal_uuid"], tipo,
        usuario_registro=usuario_registro,
        justificativa=justificativa,
        observacoes=observacoes,
        evento_anterior_id=evento_id,
        versao=(orig["versao"] or 1) + 1,
    )


def do_animal(animal_uuid: str, *, tipo: Optional[str] = None) -> list[dict]:
    """Linha do tempo do animal, do mais recente ao mais antigo."""
    sql = "SELECT * FROM animal_events WHERE animal_uuid=?"
    args: list = [animal_uuid]
    if tipo:
        sql += " AND tipo=?"; args.append(tipo)
    sql += " ORDER BY ocorrido_em DESC, id DESC"
    with _conn() as con:
        return [_normalizar(r) for r in con.execute(sql, args).fetchall()]


def pendentes_de_sincronizacao(limite: int = 200) -> list[dict]:
    """Eventos que ainda não foram aceitos pelo sistema oficial.

    Existe desde já porque a fila de sincronização é o que separa "registrei" de
    "comuniquei" — e o PNIB cobra a segunda.
    """
    with _conn() as con:
        return [_normalizar(r) for r in con.execute(
            "SELECT * FROM animal_events WHERE status_sincronizacao <> 'sincronizado' "
            "ORDER BY ocorrido_em LIMIT ?", (limite,)).fetchall()]


# ─── Trilha de auditoria (§14.1) ─────────────────────────────────────────────

@_writes
def auditar(acao: str, *,
            usuario: str = "",
            entidade: Optional[str] = None,
            entidade_id: Optional[str] = None,
            registro_anterior=None,
            registro_posterior=None,
            motivo: str = "",
            autorizacao: str = "",
            origem: str = "web",
            dispositivo: Optional[str] = None,
            ip: Optional[str] = None,
            protocolo_externo: Optional[str] = None) -> dict:
    """Registra uma ação na trilha de auditoria.

    `registro_anterior` e `registro_posterior` aceitam dicionário — viram JSON.
    Guardar os dois é o que distingue auditoria de log: permite responder o que
    exatamente mudou, não só que algo mudou.
    """
    with _conn() as con:
        con.execute(
            """INSERT INTO audit_logs
               (usuario,ocorrido_em,dispositivo,ip,acao,entidade,entidade_id,
                registro_anterior,registro_posterior,motivo,autorizacao,
                origem,protocolo_externo)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (usuario or None, _agora(), dispositivo, ip, acao, entidade,
             str(entidade_id) if entidade_id is not None else None,
             _json(registro_anterior), _json(registro_posterior),
             motivo or None, autorizacao or None, origem, protocolo_externo),
        )
    return {"ok": True}


def trilha(*, entidade: Optional[str] = None,
           entidade_id: Optional[str] = None,
           limite: int = 100) -> list[dict]:
    """Trilha de auditoria, do mais recente ao mais antigo."""
    sql = "SELECT * FROM audit_logs WHERE 1=1"
    args: list = []
    if entidade:
        sql += " AND entidade=?"; args.append(entidade)
    if entidade_id is not None:
        sql += " AND entidade_id=?"; args.append(str(entidade_id))
    sql += " ORDER BY ocorrido_em DESC, id DESC LIMIT ?"
    args.append(limite)
    with _conn() as con:
        return [_normalizar(r) for r in con.execute(sql, args).fetchall()]
