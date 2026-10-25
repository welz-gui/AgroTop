"""Revisão de registros por cancelamento ou correção (PNIB §6.3).

Pesagem, movimentação e tratamento seguem o mesmo desenho: o registro errado não some nem é
editado; é marcado como cancelado (com motivo e autor) e, numa correção, substituído por outro
que aponta para ele. Aqui ficam os erros e os pequenos auxiliares comuns, para os repositórios
e as telas tratarem os três do mesmo jeito.

Camada de dados: sem Streamlit, sem regra de domínio de cada registro.
"""


class RegistroNaoEncontrado(ValueError):
    """Não há registro com esse id (ou ele é de outro animal)."""


class RegistroJaCancelado(ValueError):
    """O registro já foi cancelado ou corrigido: não se revisa duas vezes a mesma linha."""


class RevisaoNaoPermitida(ValueError):
    """A revisão pedida não pode ser feita (sem motivo, ou contra uma regra do registro)."""


def motivo_obrigatorio(motivo) -> str:
    """Motivo sem espaços repetidos; vazio é recusado."""
    m = " ".join(str(motivo or "").split())
    if not m:
        raise RevisaoNaoPermitida("Informe o motivo da correção.")
    return m


def versao_do_evento(con, evento_id) -> int:
    """Versão do evento original (1 quando o registro é anterior ao vínculo com o evento)."""
    if not evento_id:
        return 1
    ev = con.execute("SELECT versao FROM animal_events WHERE id=?", (evento_id,)).fetchone()
    return (ev["versao"] if ev else 1) or 1


def foto(registro: dict) -> dict:
    """Cópia serializável para a auditoria (o Postgres devolve Decimal e datas)."""
    return {k: (v if v is None or isinstance(v, (str, int, float)) else str(v))
            for k, v in registro.items()}
