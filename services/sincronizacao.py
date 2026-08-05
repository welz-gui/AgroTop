"""Situação de sincronização com os sistemas oficiais (PNIB §10.3 · ADR 0005).

Vocabulário e classificação, e nada mais: sem banco, sem Streamlit (R9). Quem
guarda é `repositories/eventos.py`, na tabela `evento_sincronizacao`.

**A pergunta que este módulo responde é uma só:** esta situação tira o evento da
fila ou não? Ela parece trivial e não é — `cancelado` tira (ninguém mais espera
resposta), `rejeitado` não tira (o dever de comunicar continua), e é essa
distinção que decide se o alerta do §8.4 aparece na liberação de saída.
"""

# §10.3 — as catorze situações, na ordem do documento. Lista FECHADA na norma,
# ao contrário de `TIPOS` em repositories/eventos.py: aqui a validação é
# restrição, não sugestão.
SITUACOES = (
    "nao_aplicavel",
    "aguardando_envio",
    "em_fila",
    "enviado",
    "processando",
    "aceito",
    "aceito_com_ressalva",
    "rejeitado",
    "erro_tecnico",
    "aguardando_correcao",
    "cancelamento_solicitado",
    "cancelado",
    "divergente",
    "reconciliado_manualmente",
)

# O que tira o evento da fila. O critério é "não se espera mais nada de
# ninguém", não "deu certo": `nao_aplicavel` nunca precisou ir, `cancelado`
# deixou de precisar, e `aceito_com_ressalva` foi aceito apesar da ressalva.
#
# `rejeitado`, `divergente` e `erro_tecnico` NÃO estão aqui de propósito: o
# sistema oficial recusou, então a obrigação de comunicar continua de pé — e é
# exatamente o caso em que o alerta do §8.4 precisa aparecer.
RESOLVIDAS = (
    "nao_aplicavel",
    "aceito",
    "aceito_com_ressalva",
    "cancelado",
    "reconciliado_manualmente",
)

# Situação de quem ainda não tem nenhuma transição registrada. É também o valor
# legado de `animal_events.status_sincronizacao` ('pendente'), que precede o
# vocabulário do §10.3 e continua contando como fila.
SITUACAO_INICIAL = "aguardando_envio"
SITUACAO_LEGADA = "pendente"

# §10.1. Lista ABERTA — o parágrafo termina em "protocolos privados
# homologados", então não é validada. 'oficial' é o destino único enquanto as
# APIs não existem (§23): nome neutro para não presumir qual virá primeiro.
SISTEMAS = (
    "oficial",
    "seapi_rs",
    "sda_rs",
    "base_central_pnib",
    "gta",
    "sisbov",
    "privado",
)

SISTEMA_PADRAO = "oficial"

# R21: informação nunca depende só de cor nem de código interno. Quem exibe a
# fila precisa de texto, e o texto mora junto do vocabulário para não haver duas
# traduções diferentes da mesma situação em duas telas.
ROTULOS = {
    "nao_aplicavel": "Não aplicável",
    "aguardando_envio": "Aguardando envio",
    "em_fila": "Em fila",
    "enviado": "Enviado",
    "processando": "Processando",
    "aceito": "Aceito",
    "aceito_com_ressalva": "Aceito com ressalva",
    "rejeitado": "Rejeitado",
    "erro_tecnico": "Erro técnico",
    "aguardando_correcao": "Aguardando correção",
    "cancelamento_solicitado": "Cancelamento solicitado",
    "cancelado": "Cancelado",
    "divergente": "Divergente",
    "reconciliado_manualmente": "Reconciliado manualmente",
    SITUACAO_LEGADA: "Pendente",
}


def conhecida(situacao: str) -> bool:
    return situacao in SITUACOES


def resolvida(situacao) -> bool:
    """A situação tira o evento da fila?

    Situação desconhecida conta como **em aberto**, nunca como resolvida: entre
    errar deixando na fila e errar tirando dela, só o segundo esconde uma
    obrigação de comunicar.
    """
    return situacao in RESOLVIDAS


def em_aberto(situacao) -> bool:
    return not resolvida(situacao)


def rotulo(situacao) -> str:
    return ROTULOS.get(situacao, str(situacao))


def resumo(situacoes) -> dict:
    """Contagem por situação, do mais frequente ao menos — o que a tela mostra."""
    contagem: dict = {}
    for s in situacoes:
        contagem[s] = contagem.get(s, 0) + 1
    return dict(sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0])))
