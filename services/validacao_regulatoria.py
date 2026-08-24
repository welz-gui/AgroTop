"""Módulo de validações de consistência regulatória de animais (PNIB §17.3)."""

from datetime import date, datetime


def _parse_date(val) -> date | None:
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val.strip():
        val_str = val.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(val_str, fmt).date()
            except ValueError:
                pass
    return None


def _checar_morte_antes_nascimento(nasc_dt: date | None, morte_dt: date | None) -> list[dict]:
    problemas = []
    if nasc_dt and morte_dt and morte_dt < nasc_dt:
        problemas.append(
            {
                "codigo": "morte_antes_nascimento",
                "gravidade": "bloqueio",
                "mensagem": (
                    f"Morte registrada em {morte_dt.strftime('%Y-%m-%d')}, "
                    f"anterior ao nascimento em {nasc_dt.strftime('%Y-%m-%d')}."
                ),
                "campo": "morte",
            }
        )
    return problemas


def _checar_movimentacao_apos_morte(morte_dt: date | None, eventos: list | None) -> list[dict]:
    problemas = []
    if morte_dt and isinstance(eventos, list):
        for evento in eventos:
            ev_dt = _parse_date(evento.get("data"))
            tipo_ev = evento.get("tipo", "").lower()
            eh_mov = (
                tipo_ev in {"movimentacao", "saida", "transferencia", "transporte"} or "moviment" in tipo_ev
            )
            if ev_dt and morte_dt and ev_dt > morte_dt and eh_mov:
                problemas.append(
                    {
                        "codigo": "movimentacao_apos_morte",
                        "gravidade": "bloqueio",
                        "mensagem": (
                            f"Evento de movimentação registrado em {ev_dt.strftime('%Y-%m-%d')}, "
                            f"posterior à morte em {morte_dt.strftime('%Y-%m-%d')}."
                        ),
                        "campo": "morte",
                    }
                )
    return problemas


def _checar_data_futura_animal(nasc_dt: date | None, morte_dt: date | None, hoje_dt: date) -> list[dict]:
    problemas = []
    if nasc_dt and nasc_dt > hoje_dt:
        problemas.append(
            {
                "codigo": "data_futura",
                "gravidade": "bloqueio",
                "mensagem": (
                    f"Data de nascimento ({nasc_dt.strftime('%Y-%m-%d')}) "
                    f"no futuro (relativo a {hoje_dt.strftime('%Y-%m-%d')})."
                ),
                "campo": "nascimento",
            }
        )

    if morte_dt and morte_dt > hoje_dt:
        problemas.append(
            {
                "codigo": "data_futura",
                "gravidade": "bloqueio",
                "mensagem": (
                    f"Data de morte ({morte_dt.strftime('%Y-%m-%d')}) "
                    f"no futuro (relativo a {hoje_dt.strftime('%Y-%m-%d')})."
                ),
                "campo": "morte",
            }
        )
    return problemas


def _checar_mae(
    nasc_dt: date | None,
    hoje_dt: date,
    mae: dict | None,
    idade_minima_mae_meses: int,
) -> list[dict]:
    problemas = []
    if isinstance(mae, dict):
        mae_sexo = str(mae.get("sexo", "")).upper()
        if mae_sexo in {"M", "MACHO"}:
            problemas.append(
                {
                    "codigo": "sexo_incompativel_com_parto",
                    "gravidade": "bloqueio",
                    "mensagem": f"Mãe registrada com sexo masculino ('{mae.get('sexo')}').",
                    "campo": "mae_id",
                }
            )

        mae_nasc_dt = _parse_date(mae.get("nascimento"))
        if mae_nasc_dt:
            if mae_nasc_dt > hoje_dt:
                problemas.append(
                    {
                        "codigo": "data_futura",
                        "gravidade": "bloqueio",
                        "mensagem": (
                            f"Data de nascimento da mãe ({mae_nasc_dt.strftime('%Y-%m-%d')}) "
                            f"no futuro (relativo a {hoje_dt.strftime('%Y-%m-%d')})."
                        ),
                        "campo": "mae_id",
                    }
                )

            if nasc_dt:
                if mae_nasc_dt > nasc_dt:
                    problemas.append(
                        {
                            "codigo": "mae_mais_nova_que_cria",
                            "gravidade": "bloqueio",
                            "mensagem": (
                                f"Mãe nascida em {mae_nasc_dt.strftime('%Y-%m-%d')}, "
                                f"posterior ao nascimento da cria em "
                                f"{nasc_dt.strftime('%Y-%m-%d')}."
                            ),
                            "campo": "mae_id",
                        }
                    )
                elif mae_nasc_dt <= nasc_dt:
                    meses = (nasc_dt.year - mae_nasc_dt.year) * 12 + (nasc_dt.month - mae_nasc_dt.month)
                    if nasc_dt.day < mae_nasc_dt.day:
                        meses -= 1

                    if meses < idade_minima_mae_meses:
                        problemas.append(
                            {
                                "codigo": "mae_jovem_demais",
                                "gravidade": "alerta",
                                "mensagem": (
                                    f"Mãe tinha aproximadamente {meses} meses no parto "
                                    f"(mínimo esperado: {idade_minima_mae_meses} meses)."
                                ),
                                "campo": "mae_id",
                            }
                        )
    return problemas


def _checar_data_futura_eventos(eventos: list | None, hoje_dt: date) -> list[dict]:
    problemas = []
    if isinstance(eventos, list):
        for evento in eventos:
            ev_dt = _parse_date(evento.get("data"))
            if ev_dt and ev_dt > hoje_dt:
                problemas.append(
                    {
                        "codigo": "data_futura",
                        "gravidade": "bloqueio",
                        "mensagem": (
                            f"Data do evento ({ev_dt.strftime('%Y-%m-%d')}) "
                            f"no futuro (relativo a {hoje_dt.strftime('%Y-%m-%d')})."
                        ),
                        "campo": "eventos",
                    }
                )
    return problemas


def _checar_identificador_duplicado(
    identificadores: list | None,
) -> list[dict]:
    problemas = []
    if isinstance(identificadores, list):
        contagem_tipos: dict[str, int] = {}
        for ident in identificadores:
            if ident.get("ativo", True):
                t = str(ident.get("tipo", "")).strip().lower()
                if t:
                    contagem_tipos[t] = contagem_tipos.get(t, 0) + 1

        for t, qtd in contagem_tipos.items():
            if qtd > 1:
                problemas.append(
                    {
                        "codigo": "identificador_duplicado",
                        "gravidade": "bloqueio",
                        "mensagem": f"Múltiplos identificadores ativos do tipo '{t}' encontrados.",
                        "campo": "identificadores",
                    }
                )
    return problemas


def _checar_eventos_fora_de_ordem(eventos: list | None, nasc_dt: date | None) -> list[dict]:
    problemas = []
    if isinstance(eventos, list) and eventos:
        ult_dt = None
        for evento in eventos:
            ev_dt = _parse_date(evento.get("data"))
            if ev_dt:
                if nasc_dt and ev_dt < nasc_dt:
                    problemas.append(
                        {
                            "codigo": "eventos_fora_de_ordem",
                            "gravidade": "alerta",
                            "mensagem": (
                                f"Evento ({evento.get('tipo', 'evento')}) em {ev_dt.strftime('%Y-%m-%d')} "
                                f"é anterior ao nascimento ({nasc_dt.strftime('%Y-%m-%d')})."
                            ),
                            "campo": "eventos",
                        }
                    )
                elif ult_dt and ev_dt < ult_dt:
                    problemas.append(
                        {
                            "codigo": "eventos_fora_de_ordem",
                            "gravidade": "alerta",
                            "mensagem": (
                                f"Evento em {ev_dt.strftime('%Y-%m-%d')} registrado fora de ordem "
                                f"cronológica após evento em {ult_dt.strftime('%Y-%m-%d')}."
                            ),
                            "campo": "eventos",
                        }
                    )
                else:
                    ult_dt = ev_dt
    return problemas


def _checar_animal_sem_origem(animal: dict, eventos: list | None) -> list[dict]:
    problemas = []
    tem_prop_animal = any(
        [
            animal.get("propriedade_id"),
            animal.get("propriedade_origem_id"),
            animal.get("propriedade_nascimento_id"),
            animal.get("origem"),
        ]
    )
    tem_prop_evento = False
    if isinstance(eventos, list):
        for ev in eventos:
            if ev.get("propriedade_id") or ev.get("tipo", "").lower() in {
                "nascimento",
                "entrada",
                "compra",
            }:
                tem_prop_evento = True
                break

    if not tem_prop_animal and not tem_prop_evento:
        problemas.append(
            {
                "codigo": "animal_sem_origem",
                "gravidade": "alerta",
                "mensagem": "Animal sem propriedade de nascimento ou de entrada registrada.",
                "campo": "propriedade_id",
            }
        )
    return problemas


def _checar_nascimento_sem_mae(animal: dict, mae: dict | None) -> list[dict]:
    problemas = []
    tem_mae = bool(animal.get("mae_id")) or bool(mae)
    if not tem_mae:
        problemas.append(
            {
                "codigo": "nascimento_sem_mae",
                "gravidade": "alerta",
                "mensagem": "Animal sem mãe vinculada cadastrada.",
                "campo": "mae_id",
            }
        )
    return problemas


def _checar_nascimento_estimado(animal: dict) -> list[dict]:
    problemas = []
    eh_estimado = (
        animal.get("nascimento_estimado") is True
        or animal.get("data_estimada") is True
        or str(animal.get("nascimento_tipo", "")).lower() == "estimado"
    )
    if eh_estimado:
        problemas.append(
            {
                "codigo": "nascimento_estimado",
                "gravidade": "informativo",
                "mensagem": "Data de nascimento marcada como estimada.",
                "campo": "nascimento",
            }
        )
    return problemas


def validar_animal(
    animal: dict,
    contexto: dict | None = None,
    *,
    idade_minima_mae_meses: int = 18,
) -> list[dict]:
    """Verifica a consistência de um animal e do seu histórico.

    `animal`:  {"id", "sexo", "nascimento", "morte", "propriedade_id", ...}
    `contexto`: dados de apoio já apurados — a função NÃO consulta o banco:
        {
          "eventos":         [{"tipo", "data", "propriedade_id"}, ...],
          "mae":             {"id", "sexo", "nascimento"} | None,
          "identificadores": [{"tipo", "valor", "ativo"}, ...],
          "hoje":            "AAAA-MM-DD",
        }

    Retorna lista de problemas (vazia = consistente):
        [{
          "codigo": str,        # identificador estável, ex. "morte_antes_nascimento"
          "gravidade": "bloqueio" | "alerta" | "informativo",
          "mensagem": str,      # legível, com os dados que motivaram
          "campo": str | None,  # campo afetado, quando aplicável
        }, ...]

    Chave ausente no contexto NÃO pode quebrar: a validação que depende dela é pulada.
    """
    if contexto is None:
        contexto = {}

    problemas: list[dict] = []

    hoje_raw = contexto.get("hoje")
    hoje_dt = _parse_date(hoje_raw) if hoje_raw else date.today()

    nasc_dt = _parse_date(animal.get("nascimento"))
    morte_dt = _parse_date(animal.get("morte"))
    eventos = contexto.get("eventos")
    mae = contexto.get("mae")
    identificadores = contexto.get("identificadores")

    problemas.extend(_checar_morte_antes_nascimento(nasc_dt, morte_dt))
    problemas.extend(_checar_movimentacao_apos_morte(morte_dt, eventos))
    problemas.extend(_checar_data_futura_animal(nasc_dt, morte_dt, hoje_dt))
    problemas.extend(_checar_mae(nasc_dt, hoje_dt, mae, idade_minima_mae_meses))
    problemas.extend(_checar_data_futura_eventos(eventos, hoje_dt))
    problemas.extend(_checar_identificador_duplicado(identificadores))
    problemas.extend(_checar_eventos_fora_de_ordem(eventos, nasc_dt))
    problemas.extend(_checar_animal_sem_origem(animal, eventos))
    problemas.extend(_checar_nascimento_sem_mae(animal, mae))
    problemas.extend(_checar_nascimento_estimado(animal))

    return problemas
