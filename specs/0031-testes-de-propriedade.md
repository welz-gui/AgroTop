# Spec 0031 — Testes de propriedade para os services puros

- **Tipo:** teste · **Risco:** baixo · **Esforço:** 2 dias
- **Branch:** `feat/testes-de-propriedade`
- **Crie:** `tests/test_propriedades_matematicas.py` — **arquivo novo**

---

## Regra de ouro desta spec

Você cria **um arquivo novo**. **Não altere nenhum código de produção.** Se um teste de
propriedade revelar um defeito, **anote no PR — não conserte.** O conserto é decisão do
mantenedor, e misturar teste novo com correção esconde qual dos dois quebrou o quê.

## Objetivo

O projeto tem **430 testes**, quase todos baseados em exemplos: entrada conhecida, saída
esperada. Isso pega o que quem escreveu imaginou — e só isso.

Testes de propriedade atacam por outro lado: geram **milhares de entradas** e verificam que
uma afirmação continua verdadeira em todas. Encontram o caso que ninguém pensou.

Este projeto tem vários invariantes fortes e ainda não testados assim.

## Propriedades obrigatórias

### `services/rateio.py`
- **A soma sempre fecha.** Para qualquer valor e qualquer lista não vazia, a soma dos
  quinhões é exatamente o valor total, com 2 casas. Foi o "teste do centavo" — agora com
  10 mil casos em vez de um.
- Rateio de valor negativo (estorno) mantém a soma negativa e do mesmo módulo.

### `services/geometria.py`
- **Área é invariante à rotação da lista.** Girar a ordem dos vértices não muda a área.
- **Anel aberto e fechado dão o mesmo resultado.**
- Área nunca é negativa.
- O centroide de um polígono válido cai **dentro** dos limites de longitude e latitude dele.

### `services/zootecnia.py`
- `kg_to_arrobas` é monotônica: mais peso nunca dá menos arroba.
- GMD entre duas pesagens é simétrico ao trocar a ordem das datas (com sinal invertido).

### `services/estados_animal.py` e `services/estados_dispositivo.py`
- **Transição para o mesmo estado é sempre permitida.**
- Estado terminal nunca admite saída sem autorização.
- Todo estado listado em `ESTADOS` aparece na tabela de transições — **este é o que mais
  provavelmente encontra algo**: estado acrescentado e esquecido na máquina.

### `services/caixa.py`
- Receitas menos despesas é sempre igual a `resultado`, para qualquer conjunto.
- Um lançamento sem `pagamento` **nunca** entra no realizado, em nenhum período.

### `services/regras_regulatorias.py`
- Regra com `data_final` anterior a `data_inicial` **nunca** dispara.
- Operador desconhecido nunca dispara, para qualquer contexto.

## Ferramenta

Use **`hypothesis`**. Acrescente ao `requirements.txt` da raiz apenas se necessário para o
CI — e **justifique no PR**, porque esse arquivo alimenta o deploy do Streamlit Cloud e peso
extra ali custa tempo de inicialização. Se preferir, avalie um `requirements-dev.txt`
separado e diga por quê.

## Critério de aceite

1. Cada propriedade acima tem um teste, com `@given` gerando entradas variadas.
2. **Os geradores são realistas.** Peso de boi entre 1 e 2000 kg; coordenada dentro do
   Brasil; valor monetário com 2 casas. Gerar `float('inf')` e reportar que a função quebra
   não é achado útil — é ruído.
3. A suíte inteira continua verde e **não fica lenta**: diga no PR quanto tempo os testes
   novos acrescentam. Acima de 30 s, reduza `max_examples`.
4. `derandomize=True` ou `seed` fixa, para o CI não falhar de forma intermitente. Teste que
   quebra às vezes é pior que teste ausente.
5. **Se encontrar defeito real, o PR traz o caso mínimo que o reproduz** — e o código de
   produção segue intocado.

## Proibições

- ❌ **Não altere nenhum arquivo de `services/`, `repositories/`, `app.py` ou
  `database.py`.** Nem para consertar o que você encontrar.
- ❌ Não enfraqueça uma propriedade para o teste passar. Se `area_hectares` falha para
  polígono degenerado, isso é achado — não motivo para excluir o caso.
- ❌ Não crie tabela nem migration.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo: quanto tempo os testes acrescentaram, e **a lista de defeitos
encontrados com o caso mínimo de cada** — se não encontrou nenhum, diga isso também, é
informação sobre a qualidade do código.
