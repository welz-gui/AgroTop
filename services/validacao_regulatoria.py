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

    # 1. morte_antes_nascimento (bloqueio)
    if nasc_dt and morte_dt and morte_dt < nasc_dt:
        problemas.append({
            "codigo": "morte_antes_nascimento",
            "gravidade": "bloqueio",
            "mensagem": (
                f"Morte registrada em {morte_dt.strftime('%Y-%m-%d')}, "
                f"anterior ao nascimento em {nasc_dt.strftime('%Y-%m-%d')}."
            ),
            "campo": "morte",
        })

    # 2. movimentacao_apos_morte (bloqueio)
    eventos = contexto.get("eventos")
    if morte_dt and isinstance(eventos, list):
        for evento in eventos:
            ev_dt = _parse_date(evento.get("data"))
            tipo_ev = evento.get("tipo", "").lower()
            eh_mov = (
                tipo_ev in {"movimentacao", "saida", "transferencia", "transporte"}
                or "moviment" in tipo_ev
            )
            if ev_dt and morte_dt and ev_dt > morte_dt and eh_mov:
                problemas.append({
                    "codigo": "movimentacao_apos_morte",
                    "gravidade": "bloqueio",
                    "mensagem": (
                        f"Evento de movimentação registrado em {ev_dt.strftime('%Y-%m-%d')}, "
                        f"posterior à morte em {morte_dt.strftime('%Y-%m-%d')}."
                    ),
                    "campo": "morte",
                })

    # Data futura em animal (nascimento / morte)
    if nasc_dt and nasc_dt > hoje_dt:
        problemas.append({
            "codigo": "data_futura",
            "gravidade": "bloqueio",
            "mensagem": (
                f"Data de nascimento ({nasc_dt.strftime('%Y-%m-%d')}) "
                f"no futuro (relativo a {hoje_dt.strftime('%Y-%m-%d')})."
            ),
            "campo": "nascimento",
        })

    if morte_dt and morte_dt > hoje_dt:
        problemas.append({
            "codigo": "data_futura",
            "gravidade": "bloqueio",
            "mensagem": (
                f"Data de morte ({morte_dt.strftime('%Y-%m-%d')}) "
                f"no futuro (relativo a {hoje_dt.strftime('%Y-%m-%d')})."
            ),
            "campo": "morte",
        })

    # Checagens da Mãe
    mae = contexto.get("mae")
    if isinstance(mae, dict):
        mae_sexo = str(mae.get("sexo", "")).upper()
        # 4. sexo_incompativel_com_parto (bloqueio)
        if mae_sexo in {"M", "MACHO"}:
            problemas.append({
                "codigo": "sexo_incompativel_com_parto",
                "gravidade": "bloqueio",
                "mensagem": f"Mãe registrada com sexo masculino ('{mae.get('sexo')}').",
                "campo": "mae_id",
            })

        mae_nasc_dt = _parse_date(mae.get("nascimento"))
        if mae_nasc_dt:
            # Data futura na mãe
            if mae_nasc_dt > hoje_dt:
                problemas.append({
                    "codigo": "data_futura",
                    "gravidade": "bloqueio",
                    "mensagem": (
                        f"Data de nascimento da mãe ({mae_nasc_dt.strftime('%Y-%m-%d')}) "
                        f"no futuro (relativo a {hoje_dt.strftime('%Y-%m-%d')})."
                    ),
                    "campo": "mae_id",
                })

            if nasc_dt:
                # 3. mae_mais_nova_que_cria (bloqueio)
                if mae_nasc_dt > nasc_dt:
                    problemas.append({
                        "codigo": "mae_mais_nova_que_cria",
                        "gravidade": "bloqueio",
                        "mensagem": (
                            f"Mãe nascida em {mae_nasc_dt.strftime('%Y-%m-%d')}, "
                            f"posterior ao nascimento da cria em {nasc_dt.strftime('%Y-%m-%d')}."
                        ),
                        "campo": "mae_id",
                    })

                # 10. mae_jovem_demais (alerta)
                elif mae_nasc_dt <= nasc_dt:
                    meses = (nasc_dt.year - mae_nasc_dt.year) * 12 + (
                        nasc_dt.month - mae_nasc_dt.month
                    )
                    if nasc_dt.day < mae_nasc_dt.day:
                        meses -= 1

                    if meses < idade_minima_mae_meses:
                        problemas.append({
                            "codigo": "mae_jovem_demais",
                            "gravidade": "alerta",
                            "mensagem": (
                                f"Mãe tinha aproximadamente {meses} meses no parto "
                                f"(mínimo esperado: {idade_minima_mae_meses} meses)."
                            ),
                            "campo": "mae_id",
                        })

    # 5. Data futura em eventos
    if isinstance(eventos, list):
        for evento in eventos:
            ev_dt = _parse_date(evento.get("data"))
            if ev_dt and ev_dt > hoje_dt:
                problemas.append({
                    "codigo": "data_futura",
                    "gravidade": "bloqueio",
                    "mensagem": (
                        f"Data do evento ({ev_dt.strftime('%Y-%m-%d')}) "
                        f"no futuro (relativo a {hoje_dt.strftime('%Y-%m-%d')})."
                    ),
                    "campo": "eventos",
                })

    # 6. identificador_duplicado (bloqueio)
    identificadores = contexto.get("identificadores")
    if isinstance(identificadores, list):
        contagem_tipos: dict[str, int] = {}
        for ident in identificadores:
            if ident.get("ativo", True):
                t = str(ident.get("tipo", "")).strip().lower()
                if t:
                    contagem_tipos[t] = contagem_tipos.get(t, 0) + 1

        for t, qtd in contagem_tipos.items():
            if qtd > 1:
                problemas.append({
                    "codigo": "identificador_duplicado",
                    "gravidade": "bloqueio",
                    "mensagem": f"Múltiplos identificadores ativos do tipo '{t}' encontrados.",
                    "campo": "identificadores",
                })

    # 7. eventos_fora_de_ordem (alerta)
    if isinstance(eventos, list) and eventos:
        ult_dt = None
        for evento in eventos:
            ev_dt = _parse_date(evento.get("data"))
            if ev_dt:
                if nasc_dt and ev_dt < nasc_dt:
                    problemas.append({
                        "codigo": "eventos_fora_de_ordem",
                        "gravidade": "alerta",
                        "mensagem": (
                            f"Evento ({evento.get('tipo', 'evento')}) em {ev_dt.strftime('%Y-%m-%d')} "
                            f"é anterior ao nascimento ({nasc_dt.strftime('%Y-%m-%d')})."
                        ),
                        "campo": "eventos",
                    })
                elif ult_dt and ev_dt < ult_dt:
                    problemas.append({
                        "codigo": "eventos_fora_de_ordem",
                        "gravidade": "alerta",
                        "mensagem": (
                            f"Evento em {ev_dt.strftime('%Y-%m-%d')} registrado fora de ordem "
                            f"cronológica após evento em {ult_dt.strftime('%Y-%m-%d')}."
                        ),
                        "campo": "eventos",
                    })
                else:
                    ult_dt = ev_dt

    # 8. animal_sem_origem (alerta)
    tem_prop_animal = any([
        animal.get("propriedade_id"),
        animal.get("propriedade_origem_id"),
        animal.get("propriedade_nascimento_id"),
        animal.get("origem"),
    ])
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
        problemas.append({
            "codigo": "animal_sem_origem",
            "gravidade": "alerta",
            "mensagem": "Animal sem propriedade de nascimento ou de entrada registrada.",
            "campo": "propriedade_id",
        })

    # 9. nascimento_sem_mae (alerta)
    tem_mae = bool(animal.get("mae_id")) or bool(contexto.get("mae"))
    if not tem_mae:
        problemas.append({
            "codigo": "nascimento_sem_mae",
            "gravidade": "alerta",
            "mensagem": "Animal sem mãe vinculada cadastrada.",
            "campo": "mae_id",
        })

    # 11. nascimento_estimado (informativo)
    eh_estimado = (
        animal.get("nascimento_estimado") is True
        or animal.get("data_estimada") is True
        or str(animal.get("nascimento_tipo", "")).lower() == "estimado"
    )
    if eh_estimado:
        problemas.append({
            "codigo": "nascimento_estimado",
            "gravidade": "informativo",
            "mensagem": "Data de nascimento marcada como estimada.",
            "campo": "nascimento",
        })

    return problemas
