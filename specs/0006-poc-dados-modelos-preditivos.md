# Spec 0006 — PoC: quanto histórico os modelos preditivos exigem

- **Tipo:** pesquisa (PoC) · **Risco:** baixo · **Esforço:** 2–3 dias
- **Branch:** `poc/dados-modelos`
- **Trabalhe apenas em:** `poc/modelos/` (pasta nova). Nada fora dela.

---

## A pergunta que esta PoC responde

**A partir de quanto histórico uma previsão de GMD deixa de ser chute — e o que precisa
estar sendo registrado hoje para que isso seja possível amanhã?**

O dono do produto quer modelos preditivos (Trilha 4 do [ROADMAP.md](../ROADMAP.md)). Eles
estão adiados não por preconceito, mas porque **os insumos ainda não existem**. Esta PoC
transforma "ainda não dá" em um **número e uma data**.

## Contexto que evita erro de premissa

- O rebanho real tem **~150–200 animais ativos**. Os 12 do banco atual são **dados
  fictícios de seed** — não os use como amostra.
- Com 150–200 animais pesados a cada 30–60 dias, são ~1.200–2.400 pesagens por ano.
  **Volume de linhas não é o gargalo.**
- O gargalo real são **ciclos completos com desfecho conhecido** (entrada → venda com peso
  de carcaça, receita e custo). Um ciclo de terminação leva 12–24 meses.
- Parte das *features* ainda não existe: consumo nutricional e custo apropriado dependem da
  Trilha 3; NDVI depende da Trilha 4. Chuva (`pluviometria`) e lotação histórica
  (`animal_movements`) **já existem**.

## O que fazer

### 1. Gerar dados sintéticos realistas
Simule um rebanho de 200 animais com curvas de crescimento plausíveis para gado de corte,
incluindo variação por estação, piquete e indivíduo, além de ruído de pesagem. Documente as
premissas — elas determinam a validade da conclusão.

### 2. Medir a curva de aprendizado
Treine um modelo simples de previsão de GMD (regressão é suficiente; não precisa ser
sofisticado) variando a quantidade de histórico: 3, 6, 12, 18, 24 meses. Para cada ponto,
reporte o erro em **kg/dia** — unidade que o pecuarista entende.

Compare sempre com uma **linha de base ingênua** ("o GMD do próximo período é igual ao
atual"). Um modelo que não bate a linha de base não serve para nada. Essa comparação é o
coração do relatório.

### 3. Auditar a prontidão dos dados reais
Verifique no schema atual (`docs/schema-nuvem.txt` e o DDL de `init_db()`) o que já é
capturado e o que faltaria. Pontos já confirmados como corretos, que **não devem ser
quebrados**:
- `current_weight` é atualizado num único lugar, sempre junto do `INSERT` em `weighings` —
  o histórico nunca se perde;
- `weighings` guarda o `lote_id` **do momento da pesagem** (feature "piquete na data");
- `method` distingue peso pesado de estimado.

Aponte o que falta para as features futuras.

### 4. Propor o indicador de completude
Especifique (não implemente) um painel que mostre, mês a mês, se a base está ficando
treinável: percentual de animais com pesagem em dia, ciclos completos acumulados,
features disponíveis.

## Entregável

1. `poc/modelos/README.md` — relatório com a curva de aprendizado, a comparação com a linha
   de base e a resposta: **"a partir de X meses de coleta consistente, a previsão supera a
   ingênua em Y kg/dia."**
2. `poc/modelos/gerar_dados.py` e `poc/modelos/avaliar.py` — reproduzíveis.
3. `poc/modelos/requirements.txt`
4. Gráfico erro × quantidade de histórico.

## Critério de aceite

O relatório entrega um **número de meses** e uma comparação honesta com a linha de base
ingênua — inclusive se a conclusão for "não compensa nem com 24 meses".

## Proibições

- ❌ **Não use os 12 animais do banco como amostra.** São fictícios; qualquer conclusão
  tirada deles seria inválida.
- ❌ **Não apresente resultado de dado sintético como se fosse real.** Toda conclusão deve
  vir rotulada como estimativa sob as premissas declaradas.
- ❌ Não conecte em produção. `AGROTOP_FORCE_SQLITE=1`.
- ❌ Não toque em `app.py`, `database.py`, `services/`, `repositories/`, `ui/`.
- ❌ Não adicione dependência ao `requirements.txt` da raiz.
- ❌ Não implemente o indicador de completude — apenas especifique.

## Como verificar antes de abrir o PR

```bash
python -m unittest discover -s tests -t . -v   # 72 testes, verde
git diff --stat origin/main                    # só arquivos em poc/modelos/
```

## Entrega

PR para `main` começando pela frase-resposta. **É PoC** — o produto é o aprendizado (R30);
o que se mescla é a decisão sobre quando começar a valer a pena.
