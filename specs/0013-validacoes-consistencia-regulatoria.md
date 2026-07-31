# Spec 0013 — Validações de consistência regulatória (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1–2 dias
- **Branch:** `feat/validacao-regulatoria`
- **Crie:** `services/validacao_regulatoria.py` e `tests/test_validacao_regulatoria.py`
- **Base regulatória:** [PNIB §17.3](../docs/regulatorio/requisitos_sistema_pnib_rs.md)

---

## Regra de ouro

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.** Função pura, testada,
contrato fixo — o mantenedor liga ao banco e à interface depois.

## Objetivo

O §17.3 lista as inconsistências que impedem rastreabilidade confiável. Elas aparecem
sobretudo na **importação de dados históricos** — que é exatamente o que vai acontecer
quando o rebanho real (150–200 animais) entrar no sistema.

Detectar isso **na importação** custa minutos. Detectar depois, num relatório oficial
rejeitado, custa muito mais.

## Contrato obrigatório

```python
def validar_animal(animal: dict, contexto: dict) -> list[dict]:
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
```

**Assine exatamente assim.**

## Validações obrigatórias (§17.3)

| codigo | Detecta | Gravidade |
|---|---|---|
| `morte_antes_nascimento` | data de morte anterior à de nascimento | bloqueio |
| `movimentacao_apos_morte` | evento de movimentação depois da morte | bloqueio |
| `mae_mais_nova_que_cria` | mãe nascida depois da cria | bloqueio |
| `sexo_incompativel_com_parto` | mãe registrada como macho | bloqueio |
| `data_futura` | qualquer data posterior a hoje | bloqueio |
| `identificador_duplicado` | dois identificadores **ativos** do mesmo tipo | bloqueio |
| `eventos_fora_de_ordem` | sequência temporal impossível | alerta |
| `animal_sem_origem` | sem propriedade de nascimento nem de entrada | alerta |
| `nascimento_sem_mae` | sem mãe vinculada | alerta |
| `mae_jovem_demais` | mãe com menos de ~18 meses na data do parto | alerta |
| `nascimento_estimado` | data de nascimento marcada como estimada | informativo |

**Sobre `mae_jovem_demais`:** o §7.2 pede detecção de intervalo biologicamente inconsistente,
mas **sem substituir a avaliação técnica** — por isso é alerta, não bloqueio. O limite deve
ser **parâmetro com valor padrão**, não número fixo no código.

## Qualidade das mensagens

Serão lidas por quem está importando uma planilha com centenas de linhas. Diga o problema
**e os dados**:

- ❌ `"inconsistência detectada no campo nascimento"`
- ✅ `"Morte registrada em 2025-03-10, anterior ao nascimento em 2025-06-01."`

## Testes obrigatórios

Cada código de validação disparando e **não** disparando; animal íntegro (lista vazia);
contexto vazio e com chaves faltando; vários problemas simultâneos; e as fronteiras da
`mae_jovem_demais` (parâmetro padrão e customizado).

## Critério de aceite

1. Contrato respeitado exatamente.
2. As 11 validações implementadas e testadas nos dois sentidos.
3. Contexto incompleto não quebra.
4. Limites biológicos são **parâmetro**, não constante embutida.
5. Não importa `streamlit`, `database` nem driver de banco (R9).
6. Suíte verde.

## Proibições

- ❌ Não altere arquivo existente.
- ❌ Não consulte o banco — tudo vem do `contexto`.
- ❌ Não **corrija** dado: a função aponta, quem decide é o operador.
- ❌ Não crie migration nem toque no schema (R4).
- ❌ Não adicione dependência.

## Verificação antes do PR

```bash
python -m unittest discover -s tests -t . -v
git diff --stat origin/main    # apenas os 2 arquivos novos
```
