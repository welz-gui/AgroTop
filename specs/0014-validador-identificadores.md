# Spec 0014 — Validador configurável de identificadores (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/validador-identificadores`
- **Crie:** `services/identificadores.py` e `tests/test_identificadores.py`
- **Base regulatória:** [PNIB §4.1, §4.2](../docs/regulatorio/requisitos_sistema_pnib_rs.md)

---

## Regra de ouro

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.**

## O ponto central: o formato oficial **ainda não existe**

O §23 lista o *"formato definitivo do identificador oficial"* entre os 19 itens **não
confirmados**. O §2.1 é explícito: não presumir formato, e tratar tudo por configuração.

Portanto esta função **não** implementa "o formato do PNIB". Ela implementa um **validador
configurável** que aceitará o formato quando ele for publicado — trocando parâmetro, não
código.

Quem escrever `if len(codigo) == 15` nesta spec entendeu errado.

## Contrato obrigatório

```python
def validar(valor: str, regra: dict) -> dict:
    """Valida um identificador contra uma regra configurável.

    `regra` (todos os campos opcionais; ausente = não verifica):
        {
          "tipo": "oficial_pnib" | "rfid" | "sisbov" | "visual" | "manejo",
          "tamanho": int | None,
          "tamanho_min": int | None,
          "tamanho_max": int | None,
          "prefixo": str | None,
          "somente_digitos": bool,
          "padrao": str | None,          # expressão regular
          "digito_verificador": "mod11" | "mod10" | None,
        }

    Retorna:
        {"valido": bool, "normalizado": str, "erros": [str, ...]}

    `normalizado`: sem espaços, traços e pontos; maiúsculas. É o valor que deve
    ser gravado, para que a comparação de duplicidade funcione.
    """


def mesmo_identificador(a: str, b: str) -> bool:
    """True se os dois valores são o mesmo identificador após normalização.

    `BR 123-456` e `br123456` são o MESMO. É o que impede duplicidade escapar
    por diferença de formatação (§4.2.1 e §4.2.2).
    """
```

**Assine exatamente assim.**

## Regras padrão a incluir

Um dicionário `REGRAS_PADRAO` com valores **provisórios e marcados como tal**:

- `rfid`: 15 dígitos numéricos — base ISO 11784/11785, citada no §12.3 como referência,
  **não** como obrigação;
- `sisbov`: 15 dígitos numéricos;
- `manejo`: livre, 1 a 20 caracteres;
- `oficial_pnib`: **vazia**, com comentário explicando que o formato não foi publicado.

Deixe evidente no código que esses valores mudam quando a regulamentação sair.

## Testes obrigatórios

Cada critério isolado (tamanho, prefixo, dígitos, padrão, verificador); regra vazia aceita
qualquer coisa; normalização removendo espaço, traço e ponto; `mesmo_identificador` com
formatações diferentes; valor vazio; e acumulação de vários erros.

## Critério de aceite

1. Contrato respeitado exatamente.
2. **Nenhum formato fixo no código** — tudo vem da `regra`.
3. `mesmo_identificador` compara após normalizar.
4. Não importa `streamlit`, `database` nem driver de banco (R9).
5. Suíte verde.

## Proibições

- ❌ Não altere arquivo existente.
- ❌ **Não presuma o formato do código oficial do PNIB.** Ele não foi publicado (§23).
- ❌ Não consulte o banco — a verificação de duplicidade real é do mantenedor; aqui só a
  comparação entre dois valores.
- ❌ Não crie migration nem toque no schema (R4).
- ❌ Não adicione dependência: `re` da biblioteca padrão basta.

## Verificação antes do PR

```bash
python -m unittest discover -s tests -t . -v
git diff --stat origin/main    # apenas os 2 arquivos novos
```
