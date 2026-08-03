# Spec 0023 — 🇧🇷 Validação de GTA e trânsito (PNIB §8)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1–2 dias
- **Branch:** `feat/validacao-gta`
- **Crie:** `services/gta.py` e `tests/test_gta.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.**

## Objetivo

A etapa **B6** vai implementar movimentação entre propriedades. Hoje o sistema só conhece
piquete→piquete. Esta spec entrega a **regra pura** de validação da GTA, que a B6 vai
precisar — permitindo que a regra e a migração andem em paralelo.

GTA vencida ou incoerente **impede o embarque no dia**, com o caminhão parado. É um erro
caro e evitável por conferência antecipada.

## Contrato obrigatório

```python
def validar(gta: dict, contexto: dict | None = None) -> list[dict]:
    """Problemas na GTA. Lista vazia = apta ao trânsito.

    `gta`: {
        "numero": str,
        "uf_origem": str, "uf_destino": str,
        "propriedade_origem": str, "propriedade_destino": str,
        "emissao": "AAAA-MM-DD",
        "validade": "AAAA-MM-DD",
        "finalidade": str,          # abate | reproducao | engorda | exposicao
        "quantidade": int,
        "animais": [str, ...],      # identificadores declarados
    }
    `contexto`: {
        "hoje": "AAAA-MM-DD",
        "animais_no_embarque": [str, ...],
        "animais_em_carencia": [str, ...],
        "validade_maxima_dias": int,   # padrão 7
    }

    Retorna [{"codigo": str, "gravidade": "bloqueio"|"alerta",
              "mensagem": str}, ...]
    """
```

**Assine exatamente assim.** Chave ausente no contexto → validação pulada, não erro.

## Validações obrigatórias

| código | Quando | Gravidade |
|---|---|---|
| `gta_vencida` | `hoje` depois de `validade` | bloqueio |
| `gta_futura` | `emissao` depois de `hoje` | bloqueio |
| `validade_maior_que_o_permitido` | `validade - emissao` acima de `validade_maxima_dias` | bloqueio |
| `quantidade_divergente` | `quantidade` ≠ tamanho de `animais` | bloqueio |
| `animal_no_embarque_fora_da_gta` | animal embarcado não declarado | bloqueio |
| `animal_da_gta_ausente` | declarado mas não embarcado | bloqueio |
| `animal_em_carencia` | animal com carência vigente indo para abate | bloqueio |
| `origem_igual_ao_destino` | mesma propriedade | bloqueio |
| `uf_diferente_sem_finalidade` | UFs diferentes e `finalidade` vazia | alerta |

**`animal_em_carencia` só bloqueia quando a finalidade é abate.** Carência impede abate, não
movimentação — bloquear transferência entre pastos por causa dela é excesso que atrapalha.

## Critério de aceite

1. Cada código tem um teste que dispara **e** um que não dispara.
2. GTA que vence hoje **é válida** — o vencimento é no fim do dia. Este é o caso de borda
   que mais erra na prática.
3. Conferência de embarque é **nos dois sentidos**: sobra e falta são erros diferentes, com
   códigos diferentes.
4. Contexto vazio valida só o que dá para validar com a própria GTA.
5. Lista de animais vazia com `quantidade` zero não é erro; com `quantidade` > 0 é.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `ui/`, nem em módulo existente
  de `services/`.
- ❌ **Não consulte banco nem API de órgão estadual.** Tudo entra por parâmetro.
- ❌ Não crie tabela nem migration (a B6 é do mantenedor, R4).
- ❌ **Não valide o formato do número da GTA.** Ele varia por UF e não há especificação
  única publicada; inventar máscara produziria recusa de documento válido.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`, pronto para revisão. No corpo, mostre o teste da GTA que **vence hoje** e é
aceita.
