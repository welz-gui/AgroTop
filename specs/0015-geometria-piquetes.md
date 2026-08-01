# Spec 0015 — Área e centroide do piquete a partir do polígono (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1–2 dias
- **Branch:** `feat/geometria-piquetes`
- **Crie:** `services/geometria.py` e `tests/test_geometria.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.** Seu produto é um
módulo de funções puras, testado, com contrato fixo — o mantenedor liga ao banco e à
interface depois (R31).

## Objetivo

Hoje a área do piquete é **digitada à mão**. Ela alimenta `capacity_ua` e a lotação UA/ha
do painel, então **um erro de digitação vira decisão errada de lotação** — e ninguém
percebe, porque não há com o que conferir.

A PoC 0003 já recomendou a pilha: `shapely` + `pyproj`. Esta spec entrega o cálculo.
**Este item se paga sozinho, sem satélite nenhum** — é a razão de ele vir antes do NDVI.

## Por que não é `shapely.area` e pronto

Coordenadas de GPS vêm em graus (EPSG:4326). Área calculada direto em graus **não é
área** — o grau de longitude encolhe conforme se afasta do equador, e o resultado sai
errado por dezenas de por cento. É preciso projetar para um sistema métrico antes de medir.

Para Mato Grosso, use **UTM** (a fazenda-alvo cai na zona 21S, EPSG:31981) ou, melhor,
**escolha a zona a partir do centroide** para o módulo servir a qualquer propriedade.
Documente a escolha no README do módulo — e diga qual erro ela evita.

## Contrato obrigatório

```python
def area_hectares(anel: list[tuple[float, float]]) -> float:
    """Área do polígono em hectares.

    `anel`: vértices [(lon, lat), ...] em graus (EPSG:4326), em ordem.
    Fecha o anel sozinho se o último ponto não repetir o primeiro.
    """

def centroide(anel: list[tuple[float, float]]) -> tuple[float, float]:
    """Centroide em (lon, lat) — serve à previsão do tempo por piquete."""

def perimetro_metros(anel: list[tuple[float, float]]) -> float:
    ...

def validar(anel: list[tuple[float, float]]) -> list[str]:
    """Problemas que impedem o uso do polígono. Lista vazia = válido.

    Detecte pelo menos: menos de 3 vértices, coordenada fora de faixa
    (lon -180..180, lat -90..90), polígono auto-interceptante, e área zero.
    """
```

**Assine exatamente assim.** A assinatura será integrada pelo mantenedor; assinatura
diferente inutiliza o trabalho.

## Critério de aceite

1. **Um quadrado conhecido bate.** Construa um polígono de dimensão conhecida em MT e
   mostre que a área calculada fica **dentro de 0,5 %** do valor esperado. Este teste é o
   que prova que a projeção está certa.
2. **A diferença contra o cálculo ingênuo está demonstrada** — um teste que calcula em
   graus e mostra o erro grosseiro. É o que impede alguém de "simplificar" depois.
3. `validar` recusa polígono auto-interceptante e devolve mensagem em português.
4. Cobertura dos casos de borda: anel já fechado e anel aberto dão o mesmo resultado.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `services/` existentes, `repositories/`, `ui/`.
- ❌ **Não crie tabela nem migration.** Onde a geometria vai ser guardada é decisão do
  mantenedor (R4) — provavelmente GeoJSON em coluna `JSONB`, mas isso não é seu escopo.
- ❌ Não integre à interface.
- ❌ Não adicione `shapely`/`pyproj` ao `requirements.txt` da raiz sem necessidade — se
  adicionar, **justifique no PR**, porque esse arquivo alimenta o deploy do Streamlit Cloud
  e peso extra ali custa tempo de inicialização.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

O `-t .` não é opcional (R16). No diff, só `services/geometria.py` e
`tests/test_geometria.py` (mais `requirements.txt` se justificado).

## Entrega

PR para `main`. No corpo, comece pelo número que importa: **o erro do cálculo ingênuo em
graus contra o projetado, no polígono de teste** — é o que justifica a dependência.
