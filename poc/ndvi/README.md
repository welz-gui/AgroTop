# PoC: NDVI é viável para os piquetes desta fazenda?

## Objetivo

Esta PoC responde à pergunta: **em Mato Grosso, há imagem de satélite utilizável com NDVI
para um piquete de pastagem plausível durante 12 meses?**

O foco é nuvem e disponibilidade real de cena. O script `demo.py` reproduz a busca de
cenas Sentinel-2 e sumariza cobertura de nuvem para um polígono de 20 ha em Mato Grosso.

## Fonte de dados escolhida

Usamos a interface STAC pública do Sentinel-2 L2A COGs disponível em:

- `https://earth-search.aws.element84.com/v0/search`

Esta fonte não exige chave de API para busca de metadados, é gratuita para consulta e
opera sobre a coleção `sentinel-s2-l2a-cogs`.

### Limites e observações

- O endpoint é público e pode impor limites internos de taxa; o script usa apenas
  um único `POST` para buscar até 250 cenas.
- O script não baixa pixels brutos, apenas metadados de cena e cobertura de nuvem.
- Não há chave de API no código. Se o usuário tiver outra fonte com API key, pode
  usar variável de ambiente `SENTINEL_API_KEY` para indicar isso, mas o PoC atual
  não requer nem consome essa variável.

## Área de teste

Escolhemos um polígono plausível em Mato Grosso, cerca de 20 hectares, com coordenadas:

- `(-55.9000, -13.3000)`
- `(-55.9000, -13.2950)`
- `(-55.8950, -13.2950)`
- `(-55.8950, -13.3000)`

A área é um retângulo em torno de uma região de pastagem típica de MT e serve apenas
para esta análise de viabilidade.

## Resultados principais

Para o período de 12 meses de 2025-05-01 até 2026-04-30, a busca STAC retornou 56
cenas Sentinel-2 sobre a área.

**Cenas utilizáveis por limiar de nuvem:**

- <= 10 % nuvem: 27 cenas
- <= 20 % nuvem: 29 cenas
- <= 40 % nuvem: 32 cenas

**Maior intervalo sem cena utilizável:**

- <= 10 % nuvem: 12 dias
- <= 20 % nuvem: 12 dias
- <= 40 % nuvem: 12 dias

**Distribuição mensal de nuvem média:**

- Jun/2025: 14.0 %
- Jul/2025: 6.9 %
- Ago/2025: 15.4 %
- Set/2025: 29.9 %
- Out/2025: 60.4 %
- Nov/2025: 66.4 %
- Dez/2025: 90.2 %

## Interpretação

- A temporada seca de Mato Grosso (junho a setembro) tem várias cenas com cobertura
  baixa, o que torna o NDVI potencialmente útil nesses meses.
- No entanto, a estação chuvosa mostra uma queda acentuada de qualidade de imagem:
  em outubro a dezembro a nuvem média supera 60 % e muitas cenas ficam pouco úteis.
- O maior vão de 12 dias significa que um piquete em MT pode passar quase duas semanas
  sem cena de qualidade suficiente, mesmo no período avaliado. Isso reduz a capacidade
  de detectar mudanças rápidas de pastagem.

## Conclusão

Em MT, há imagem utilizável com frequência suficiente na seca, mas a estação chuvosa
impõe limite real: o maior vão sem cena utilizável foi de 12 dias com os limiares de
nuvem testados. O NDVI pode ser valioso como dado de apoio, mas não deve ser tratado
como fonte de monitoramento diário confiável durante a chuva.

## Reprodutibilidade

1. Crie um ambiente Python e instale as dependências de `poc/ndvi/requirements.txt`.
2. Execute:

```bash
python poc/ndvi/demo.py
```

O script busca metadados STAC e exibe:

- número total de cenas no período de 12 meses;
- percentuais de cobertura de nuvem por cena;
- contagem de cenas utilizáveis com limiares de 10 %, 20 % e 40 %;
- maior intervalo sem cena utilizável em dias;
- resumo mensal de nuvem média.

## Observações de interpretação

- O PoC não usa NDVI para estimar matéria seca ou forragem. Ele apenas mede a
  disponibilidade de cenas de Sentinel-2 e a variação de NDVI médio se as bandas
  forem adicionadas numa etapa futura.
- Se o maior vão sem cena utilizável for maior do que a janela de decisão da gestão
  de pasto, o módulo de satélite deve ser tratado como de suporte, não como fonte
  principal de monitoramento diário.
