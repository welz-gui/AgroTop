# Spec 0004 — PoC: NDVI é viável para os piquetes desta fazenda?

- **Tipo:** pesquisa (PoC) · **Risco:** baixo · **Esforço:** 2–3 dias
- ⚠️ **Segunda tentativa.** A primeira ([PR #33](https://github.com/welz-gui/AgroTop/pull/33))
  entregou o levantamento de nuvem, que é válido e está mesclado, mas **não fechou a
  pergunta**. Leia "O que a primeira tentativa deixou pendente" antes de começar.
- **Branch:** `poc/ndvi-viabilidade-v2` (o da 1ª tentativa foi mesclado e apagado)
- **Trabalhe apenas em:** `poc/ndvi/` — **que já existe na `main`** e contém o código da 1ª
  tentativa. Você vai corrigi-lo e completá-lo. Nada fora dessa pasta.

> 🛑 **Antes de qualquer coisa: `git fetch origin && git checkout -B poc/ndvi-viabilidade-v2 origin/main`.**
> Um agente já falhou esta spec por trabalhar sobre um checkout velho: viu a versão antiga do
> quadro, concluiu que a 0004 "já estava integrada pelo PR #33" e passou para a próxima
> tarefa. **Está integrada mesmo — e é exatamente por isso que existe uma 2ª tentativa.**
> O PR #33 entregou metade. Sua tarefa é a outra metade.

---

## A pergunta que esta PoC responde

**Com que frequência é possível obter uma imagem de satélite utilizável de um piquete em
Mato Grosso — e o NDVI resultante diz algo acionável sobre a pastagem?**

Esta é a pergunta que decide se o módulo de satélite (Trilha 4 do
[ROADMAP.md](../ROADMAP.md)) vale ser construído. **Não** é "como calcular NDVI" — isso é
trivial e já documentado.

## Por que a pergunta é essa

A resolução não é o problema: Sentinel-2 a 10 m/pixel dá centenas de pixels num piquete
comum. **O problema é nuvem.** Mato Grosso tem estação chuvosa longa, e se metade do ano
não tiver imagem limpa, o módulo entrega pouco justamente quando o pasto muda mais rápido.

Se a resposta for "só há imagem útil de maio a setembro", isso não mata o módulo — mas muda
completamente o que se pode prometer ao usuário, e precisa estar decidido **antes** de
escrever código de produção.

## O que a primeira tentativa deixou pendente

O código está em `poc/ndvi/` na `main`. **Aproveite o que funciona** — a busca STAC no
`earth-search.aws.element84.com` traz cenas reais e não exige chave. Dois problemas:

### 1. O "maior vão" está errado

A primeira tentativa reportou **12 dias para os três limiares** (10 %, 20 % e 40 %). Isso é
aritmeticamente implausível: apertar o limiar derruba cenas (32 → 27) e tem de **alargar** o
vão, nunca mantê-lo igual. E o próprio levantamento mostra **dezembro com 90,2 % de nuvem
média** — nesse mês, no limiar de 10 %, praticamente não sobra cena, o que produziria vão de
~30 dias.

Causas prováveis em `largest_gap()`:
- mede só o intervalo **entre cenas filtradas**, ignorando o trecho do início do período até
  a primeira cena e da última até o fim;
- possivelmente recebe a série não filtrada.

**Corrija e explique no relatório** por que o número mudou.

### 2. O NDVI não foi calculado

`compute_ndvi_mean()` existe no código mas **nunca foi executado** — o README admite ("se as
bandas forem adicionadas numa etapa futura"). Logo:

- a **pergunta 5** (a série mostra variação que um pecuarista reconheceria?) segue sem resposta;
- o arquivo `ndvi_timeseries.png` **não contém série de NDVI**, apesar do nome.

Calcular NDVI exige ler as bandas B04/B08 dos COGs remotos e recortar pelo polígono — é mais
pesado que buscar metadados. **Se não conseguir executar, diga isso claramente** em vez de
entregar um artefato com nome que promete mais do que contém. Foi essa lacuna entre o nome
do arquivo e o conteúdo que reprovou a primeira entrega.

## O que fazer

1. **Escolha uma fonte de dados** e registre o processo de acesso. Candidatos: Copernicus
   Data Space Ecosystem (gratuito, exige cadastro) ou Sentinel Hub. Documente limites do
   plano gratuito, necessidade de chave e limites de requisição.
2. **Use uma área de teste em Mato Grosso.** Não há coordenadas reais da fazenda nesta PoC
   — escolha um polígono de pastagem plausível em MT (10–50 ha) e diga qual usou.
3. **Levante 12 meses de cenas** sobre esse polígono e produza:
   - quantas cenas existem no período (revisita teórica × real);
   - **percentual de cobertura de nuvem por cena**;
   - quantas cenas ficam utilizáveis com limiares de 10 %, 20 % e 40 % de nuvem;
   - **o maior intervalo sem imagem utilizável** — é o número mais importante do relatório;
   - a distribuição ao longo do ano (seca × chuva).
4. **Calcule o NDVI médio do polígono** nas cenas utilizáveis e trace a série temporal.
5. **Avalie honestamente:** a série mostra variação que um pecuarista reconheceria como
   mudança de pasto, ou é ruído?

## Entregável

1. `poc/ndvi/README.md` — relatório com os números acima e uma **recomendação clara**:
   seguir, seguir com ressalvas, ou não seguir agora.
2. `poc/ndvi/demo.py` — script reproduzível que baixa as cenas e gera a série.
3. `poc/ndvi/requirements.txt`
4. O gráfico da série temporal + a tabela de cobertura de nuvem por mês.

## Critério de aceite

O relatório responde, com números: **quantos dias por ano se fica sem imagem utilizável**, e
se o NDVI observado tem amplitude suficiente para ser informativo.

## Proibições

- ❌ **Não afirme que NDVI equivale a matéria seca disponível.** Não equivale. Estimar
  forragem exige calibração com medição de campo. Qualquer conclusão precisa respeitar isso
  — é regra registrada no [ROADMAP.md](../ROADMAP.md), Trilha 4.
- ❌ **Não coloque chave de API no código nem no commit.** Use variável de ambiente e
  documente o nome dela ([ROADMAP.md](../ROADMAP.md) R19).
- ❌ Não adicione dependência ao `requirements.txt` da raiz.
- ❌ Não toque em `app.py`, `database.py`, `services/`, `repositories/`, `ui/`.
- ❌ Não crie tabela nem migration.
- ❌ Não integre ao app. **É PoC** — o produto é o aprendizado (R30).

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .   # 184 testes, verde
git diff --stat origin/main                                        # só arquivos em poc/ndvi/
```

O `-t .` **não é opcional** (R16): sem ele os testes podem conectar em produção. O
`AGROTOP_FORCE_SQLITE=1` é a segunda trava.

## Entrega

PR para `main`. No corpo, comece pela resposta em uma frase: *"Em MT, há imagem utilizável
a cada N dias na seca e a cada M dias na chuva; o maior vão é de X dias."* O resto é
sustentação.
