"""Reconcilia um lote de dispositivos com os códigos já existentes."""


def reconciliar(
    itens_do_arquivo: list[dict],
    codigos_em_estoque: dict[str, str],
) -> dict:
    """Classifica itens novos, duplicados no estoque e linhas sem código."""

    para_gravar: list[dict] = []
    ja_existentes: list[dict] = []

    for item in itens_do_arquivo:
        codigo_visual = item.get("codigo_visual") or ""
        if not codigo_visual:
            ja_existentes.append(
                {"codigo_visual": codigo_visual, "status_atual": "sem_codigo"}
            )
        elif codigo_visual in codigos_em_estoque:
            ja_existentes.append(
                {
                    "codigo_visual": codigo_visual,
                    "status_atual": codigos_em_estoque[codigo_visual],
                }
            )
        else:
            para_gravar.append(item)

    return {
        "para_gravar": para_gravar,
        "ja_existentes": ja_existentes,
        "resumo": {
            "total": len(itens_do_arquivo),
            "para_gravar": len(para_gravar),
            "ja_existentes": len(ja_existentes),
        },
    }
