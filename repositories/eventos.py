"""Eventos, sincronização e trilha de auditoria (ADR 0004 · B2 · ADR 0005).

Três tabelas append-only, com gatilhos no banco que recusam `UPDATE` e `DELETE`:

- `animal_events` — §6 do PNIB. A espinha da rastreabilidade. Evento confirmado
  não se corrige: gera-se outro apontando para ele (§6.3).
- `evento_sincronizacao` — §10.3. O que já foi comunicado ao sistema oficial.
  Fica fora de `animal_events` por decisão do ADR 0005 (§10.2 manda manter a
  camada de integração fora do núcleo).
- `audit_logs` — §14.1. Quem mudou o quê, quando, de onde, com que autorização.

**Adoção incremental** (decisão do ADR 0004): por ora os eventos são
*registrados* junto das operações atuais. Derivar o estado do animal a partir
deles é passo posterior — fazer as duas coisas de uma vez seria reescrever o
sistema num salto.

⚠️ `animal_events.status_sincronizacao` e `animal_events.identificador_oficial`
são **legadas** (ADR 0005): a linha é imutável, então elas guardam o estado de
nascimento do evento e nunca mudam. Este módulo é o único lugar que pode
mencioná-las, e nenhum predicado novo deve usá-las — quem responde "já foi
comunicado?" é `evento_sincronizacao`.

Camada de dados (ROADMAP R1/R9): aqui mora o SQL, e só aqui.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from services import sincronizacao as sinc

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


def registrar_em(con, animal_uuid: str, tipo: str, **campos) -> dict:
    """Grava o evento **na conexão do chamador**, dentro da transação dele.

    É a forma que os repositórios usam. Duas razões:

    1. `_conn()` abre conexão NOVA a cada chamada. Registrar de dentro de um
       bloco aberto daria `database is locked` no SQLite e leitura suja no
       Postgres — o `SELECT` de validação não enxergaria o animal recém-inserido.
    2. **Atomicidade.** Operação e evento entram juntos ou não entram. Numa base
       de rastreabilidade, pesagem gravada sem evento correspondente é
       exatamente o buraco que o §6 existe para fechar.
    """
    return _gravar(con, animal_uuid, tipo, **campos)


@_writes
def registrar(animal_uuid: str, tipo: str, **campos) -> dict:
    """Grava um evento abrindo a própria conexão.

    Use quando não houver transação em curso. De dentro de um repositório,
    prefira `registrar_em(con, ...)`.
    """
    with _conn() as con:
        return _gravar(con, animal_uuid, tipo, **campos)


def _gravar(con, animal_uuid: str, tipo: str, *,
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
    """Grava um evento na conexão recebida. Nunca sobrescreve nada.

    `ocorrido_em` é quando o fato aconteceu; se omitido, assume agora. O
    `registrado_em` é sempre agora — os dois são gravados separados de propósito
    (§6.2), e é o atraso entre eles que uma auditoria consegue enxergar.
    """
    if tipo not in TIPOS:
        return {"ok": False, "erro": f"Tipo de evento desconhecido: '{tipo}'."}

    agora = _agora()
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


# ─── Fila de sincronização (§10.3 · ADR 0005) ────────────────────────────────
#
# A situação vigente de um par (evento, sistema) é a ÚLTIMA linha registrada.
# Não há coluna "atual" — coluna atual poderia divergir do histórico, e é
# justamente a divergência entre "o que dizem que aconteceu" e "o que
# aconteceu" que uma base de rastreabilidade não pode admitir.
#
# Um evento está EM ABERTO se: (a) nunca foi encaminhado a sistema nenhum, ou
# (b) a última transição de algum sistema não é resolvida. Aceito num destino e
# rejeitado noutro continua pendente — o dever de comunicar é por destino.
_MARCAS_RESOLVIDAS = ",".join("?" for _ in sinc.RESOLVIDAS)

_EM_ABERTO = f"""
    NOT EXISTS (SELECT 1 FROM evento_sincronizacao s WHERE s.evento_id = e.id)
    OR EXISTS (
        SELECT 1 FROM evento_sincronizacao s
         WHERE s.evento_id = e.id
           AND s.id = (SELECT MAX(s2.id) FROM evento_sincronizacao s2
                        WHERE s2.evento_id = s.evento_id
                          AND s2.sistema = s.sistema)
           AND s.situacao NOT IN ({_MARCAS_RESOLVIDAS}))
"""


@_writes
def registrar_situacao(evento_id: int, situacao: str, *,
                       sistema: str = sinc.SISTEMA_PADRAO,
                       protocolo: Optional[str] = None,
                       mensagem: str = "",
                       observacoes: str = "",
                       anexos=None,
                       usuario: str = "",
                       conferido_por: str = "",
                       ocorrido_em: Optional[str] = None) -> dict:
    """Acrescenta uma transição de sincronização ao evento (§10.3).

    Nunca altera o evento: `animal_events` continua estritamente imutável
    (ADR 0005). Esta tabela também é append-only — uma tentativa de envio que
    aconteceu não desacontece.

    `situacao` é validada contra o §10.3, que é lista fechada. `sistema` **não**
    é, porque o §10.1 termina em "protocolos privados homologados".
    """
    if not sinc.conhecida(situacao):
        return {"ok": False,
                "erro": f"Situação de sincronização desconhecida: '{situacao}' (§10.3)."}

    agora = _agora()
    with _conn() as con:
        if con.execute("SELECT 1 FROM animal_events WHERE id=?",
                       (evento_id,)).fetchone() is None:
            return {"ok": False, "erro": f"Evento {evento_id} não encontrado."}

        con.execute(
            """INSERT INTO evento_sincronizacao
               (evento_id,sistema,situacao,protocolo,mensagem,observacoes,
                anexos,usuario,conferido_por,ocorrido_em,registrado_em)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (evento_id, sistema or sinc.SISTEMA_PADRAO, situacao, protocolo,
             mensagem or None, observacoes or None, _json(anexos),
             usuario or None, conferido_por or None,
             ocorrido_em or agora, agora),
        )
    return {"ok": True}


@_writes
def marcar_sincronizado(evento_ids, *,
                        protocolo: Optional[str] = None,
                        usuario: str = "",
                        sistema: str = sinc.SISTEMA_PADRAO,
                        situacao: str = "aceito",
                        conferido_por: str = "",
                        observacoes: str = "") -> dict:
    """§10.4 — "marcação como comunicado externamente", em lote.

    É o caminho previsto **enquanto não houver API oficial** (§23): lança-se no
    portal, guarda-se o protocolo, marca-se aqui. `conferido_por` é a dupla
    conferência que o §10.4 pede; fica vazia se ninguém conferiu, e a ausência é
    auditável justamente por isso.

    Recusa situação que não tire o evento da fila — quem quer registrar
    `rejeitado` ou `erro_tecnico` usa `registrar_situacao`, que é onde essa
    intenção fica explícita.
    """
    if not sinc.resolvida(situacao):
        return {"ok": False,
                "erro": f"'{situacao}' não encerra a pendência; use "
                        f"registrar_situacao() para registrá-la."}

    ids = [evento_ids] if isinstance(evento_ids, int) else list(evento_ids)
    if not ids:
        return {"ok": False, "erro": "Nenhum evento informado."}

    for eid in ids:
        r = registrar_situacao(eid, situacao, sistema=sistema,
                               protocolo=protocolo, usuario=usuario,
                               conferido_por=conferido_por,
                               observacoes=observacoes)
        if not r["ok"]:
            # Sem gravação parcial silenciosa: o chamador precisa saber que a
            # lista não foi inteira. As transições já gravadas permanecem —
            # append-only não se desfaz —, e o erro diz onde parou.
            return {"ok": False, "erro": r["erro"], "parou_em": eid}

    return {"ok": True, "registrados": len(ids)}


def situacao_atual(evento_id: int) -> dict:
    """Última transição de cada sistema, por sistema. `{}` se nunca foi enviado."""
    with _conn() as con:
        linhas = con.execute(
            """SELECT * FROM evento_sincronizacao s
                WHERE s.evento_id = ?
                  AND s.id = (SELECT MAX(s2.id) FROM evento_sincronizacao s2
                               WHERE s2.evento_id = s.evento_id
                                 AND s2.sistema = s.sistema)""",
            (evento_id,)).fetchall()
    return {r["sistema"]: _normalizar(r) for r in linhas}


def historico_de_sincronizacao(evento_id: int) -> list[dict]:
    """Todas as transições do evento, da mais antiga à mais recente (§10.2).

    É o "log técnico" e a contagem de tentativas que o §10.2 pede — derivados do
    histórico, não de contador guardado, que poderia mentir.
    """
    with _conn() as con:
        return [_normalizar(r) for r in con.execute(
            "SELECT * FROM evento_sincronizacao WHERE evento_id=? ORDER BY id",
            (evento_id,)).fetchall()]


def contar_pendentes_em(con) -> int:
    """Quantos eventos seguem em aberto — **na conexão do chamador**.

    Existe pelo mesmo motivo de `registrar_em`: quem já está dentro de uma
    transação não pode abrir outra conexão no meio dela.
    """
    return con.execute(
        f"SELECT count(*) c FROM animal_events e WHERE ({_EM_ABERTO})",
        list(sinc.RESOLVIDAS)).fetchone()["c"]


def contar_pendentes() -> int:
    with _conn() as con:
        return contar_pendentes_em(con)


def pendentes_de_sincronizacao(limite: int = 200) -> list[dict]:
    """Eventos que ainda não foram aceitos pelo sistema oficial.

    A fila é o que separa "registrei" de "comuniquei" — e o PNIB cobra a
    segunda. Cada evento vem com `situacao_sincronizacao`: a última transição
    em aberto, ou a situação inicial quando nunca houve envio.
    """
    with _conn() as con:
        eventos = [_normalizar(r) for r in con.execute(
            f"SELECT * FROM animal_events e WHERE ({_EM_ABERTO}) "
            f"ORDER BY e.ocorrido_em LIMIT ?",
            list(sinc.RESOLVIDAS) + [limite]).fetchall()]

        if not eventos:
            return []

        marcas = ",".join("?" for _ in eventos)
        situacoes = {}
        for r in con.execute(
                f"""SELECT s.evento_id, s.situacao FROM evento_sincronizacao s
                     WHERE s.evento_id IN ({marcas})
                       AND s.id = (SELECT MAX(s2.id) FROM evento_sincronizacao s2
                                    WHERE s2.evento_id = s.evento_id
                                      AND s2.sistema = s.sistema)""",
                [e["id"] for e in eventos]).fetchall():
            # Vários sistemas: o que importa é o que ainda prende o evento na
            # fila, então a situação em aberto vence a resolvida.
            atual = situacoes.get(r["evento_id"])
            if atual is None or sinc.resolvida(atual):
                situacoes[r["evento_id"]] = r["situacao"]

    for e in eventos:
        e["situacao_sincronizacao"] = situacoes.get(e["id"], sinc.SITUACAO_INICIAL)
    return eventos


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
