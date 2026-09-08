# Spec 0082 — Web: cruzamento com CAR (situação ambiental da propriedade)

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 3-4 dias
- **Branch:** `feat/web-cruzamento-com-car`
- **Altere:** `app.py` (nova seção em `page_propriedades`), `services/importacao_car.py`
  (novo), `repositories/propriedades.py` (whitelist de `atualizar` + leitura),
  `database.py` (3 colunas novas em `properties`, com `ALTER TABLE` guardado, mesmo
  padrão de `gta_number`/`poligono`), `supabase/migrations/` (migration nova),
  `requirements.txt` (uma dependência nova, `pyshp`), e os testes correspondentes
- **Pré-requisito:** nenhum — `properties.poligono` (spec 0015) e `services/geometria.py`
  já existem, testados, em produção

---

## Regra de ouro desta spec (não negociável)

Igual à 0080 (pacote de evidências) e ao escore de conformidade que já existe: **isto
organiza e compara dados, não certifica nem substitui o CAR oficial.** O aviso "não é
avaliação de conformidade legal nem certificação oficial" (mesmo texto que
`app.py::_dash_conformidade` já usa) precisa aparecer nesta seção também, visível, não em
rodapé.

**O CAPTCHA do SICAR não é automatizado nesta spec, em nenhuma hipótese.** O produtor baixa
o arquivo dele mesmo, no site oficial, com o e-mail e o CAPTCHA — ação humana, fora do
AgroTop. Esta spec só facilita **antes** desse passo (link direto pro imóvel certo) e
**depois** dele (importar o que já foi baixado, sem o produtor converter nada na mão). Não
escreva, sugira ou deixe pronta nenhuma automação que resolva CAPTCHA — nem "para
facilitar depois". Isso vale tanto para código quanto para comentário/TODO no código.

## Objetivo

Hoje o AgroTop guarda o perímetro que o **produtor desenhou/importou** (`properties.poligono`,
`lotes.poligono`) — mas nada confere isso contra o que está **oficialmente declarado no
CAR**. Esta spec fecha esse cruzamento: o produtor baixa o Shapefile do imóvel dele no
SICAR, importa no AgroTop, e o sistema mostra a área/perímetro segundo o CAR ao lado do
que já está cadastrado, com o percentual de sobreposição — mesma lógica de
`services/lotacao.py::sobrepostos` (já em produção para conferir piquetes entre si), agora
comparando propriedade-cadastrada × CAR-declarado.

## Contexto que você precisa — leia antes de escrever qualquer linha

- **Não existe API viável para automação.** Já foi pesquisado a fundo (ver a conversa que
  originou esta spec, e registre o resumo em `ROADMAP.md`/`specs/QUADRO.md` ao entregar):
  - A API oficial "Consulta SICAR CPF/CNPJ" ([gov.br/conecta](https://www.gov.br/conecta/catalogo/apis/consulta-sicar-cpf-cnpj))
    é **restrita a órgão da administração pública federal** — autenticação por certificado
    ICP-Brasil de servidor público. **Não está disponível para o AgroTop.**
  - O download em massa (`car.gov.br/publico/estados/downloads` e
    `/publico/municipios/downloads`) exige **e-mail + CAPTCHA por download**. Fica de fora
    da automação, de propósito (ver "Regra de ouro" acima).
  - O app oficial **"Meu Imóvel Rural"** (lançado em julho de 2026, login gov.br) entrega
    só **PDF de recibo/extrato**, sem geometria — não serve para o polígono, só como
    possível documento de apoio (fora de escopo desta spec).
- **O link direto para o imóvel:** a consulta individual do SICAR fica em
  `consultapublica.car.gov.br/publico/imoveis/index`, e aceita um parâmetro identificando o
  imóvel — **mas confirme o formato exato do parâmetro na hora de implementar** (abra o
  link, faça uma consulta manual de teste, confira a URL resultante) em vez de supor o
  nome/formato do parâmetro por inferência. Se não conseguir confirmar com segurança, o
  botão pode linkar para a página de busca geral (`consultapublica.car.gov.br/publico/imoveis/index`)
  sem pré-preencher — ainda economiza a navegação principal, só não pula a busca.
- **O formato do arquivo é Shapefile, não GeoJSON/KML.** O SICAR entrega um `.zip` com
  `.shp`/`.shx`/`.dbf`/`.prj`. **Não é o mesmo parser de `services/importacao_geometria.py`**
  (que só lê GeoJSON/KML de um polígono) — precisa de leitor de Shapefile novo. Use
  `pyshp` (pacote `shapefile`, puro Python, sem depender de GDAL) — mais alinhado ao que o
  projeto já usa (`shapely`/`pyproj` sem GDAL de sistema) do que `geopandas`/`fiona`.
- **O Shapefile do CAR tem VÁRIAS camadas** (perímetro do imóvel, APP, Reserva Legal,
  vegetação nativa, hidrografia, área consolidada, uso restrito, servidão administrativa,
  pousio) — **não é um polígono só**, diferente do que `_ler_poligono`/`_entrada_de_perimetro`
  assumem. **Antes de implementar o parser, obtenha uma amostra real** (peça ao mantenedor
  um export de teste, ou baixe um manualmente uma vez) e confira como as camadas
  efetivamente aparecem no arquivo — como `.shp` separados dentro do `.zip`, ou como um
  único `.shp` com uma coluna de atributo distinguindo o tipo. **Não hardcode nome de
  camada por suposição** — a estrutura real do arquivo manda, não a documentação genérica
  do SICAR.
- **`repositories/propriedades.py::atualizar()`** tem uma whitelist explícita de campos
  editáveis (`permitidos`, linha ~133) — os três campos novos desta spec
  (`car_numero`, `poligono_car`, `car_area_ha`) precisam entrar nela, senão a gravação
  silenciosamente não faz nada (comportamento atual da função para campo fora da lista).
- **`database.py`** já tem o padrão de adicionar coluna nova com guarda (`if "gta_number"
  not in cols: ALTER TABLE ...`, por volta da linha 1046) — siga o mesmo padrão para as três
  colunas novas, tanto no SQLite quanto na migration nova do Postgres
  (`supabase/migrations/`, próximo número disponível).
- **`services/lotacao.py::_avaliar_par_sobreposto`** já implementa o cálculo de área de
  interseção entre dois polígonos via `shapely` com projeção UTM — **reuse esse padrão**
  (projeção antes de calcular área/interseção, mesmo raciocínio de `services/geometria.py::_poligono_projetado`)
  para a nova comparação propriedade×CAR. Não é código idêntico (aqui é sempre 1 propriedade
  × 1 polígono do CAR, não N piquetes entre si), mas a técnica é a mesma.

## Contrato obrigatório

### `database.py` / migration — 3 colunas novas em `properties`

```sql
ALTER TABLE properties ADD COLUMN car_numero TEXT;
ALTER TABLE properties ADD COLUMN poligono_car TEXT;   -- GeoJSON, mesmo formato de `poligono`
ALTER TABLE properties ADD COLUMN car_area_ha REAL;    -- área declarada no CAR (do próprio shapefile)
```

Todas nulas por padrão — propriedade sem CAR importado ainda é estado válido, não erro.

### `services/importacao_car.py` (novo módulo, funções puras)

```python
def ler_shapefile_car(conteudo_zip: bytes) -> dict[str, list[CamadaCar]]:
    """Lê um .zip de Shapefile exportado do SICAR e devolve as camadas encontradas,
    agrupadas por tipo identificado (a lista real de tipos depende da amostra real
    verificada durante a implementação — ver 'Contexto que você precisa').

    Levanta ValueError com mensagem em português se o .zip não contém um Shapefile
    válido, ou se nenhuma camada reconhecível como perímetro do imóvel foi encontrada.
    """
```

- `CamadaCar`: dataclass com `tipo` (rótulo legível, ex. "Área do Imóvel", "APP",
  "Reserva Legal"), `poligonos` (lista de anéis `[(lon, lat), ...]` — uma camada pode ter
  mais de um polígono, ex. várias APPs isoladas), `area_ha_atributo` (se o Shapefile trouxer
  área como atributo do próprio arquivo, `None` se não trouxer).
- **Só a camada "perímetro do imóvel" é persistida** (`properties.poligono_car`/`car_area_ha`).
  As demais (APP, Reserva Legal, etc.) são mostradas na tela **sem persistir** — ver
  proibição abaixo.

### Nova seção em `page_propriedades` (dentro de `_propriedades_editar`, após o bloco de
perímetro que já existe)

1. **"🌳 Situação Ambiental (CAR)"** — expander ou seção própria:
   - Campo `car_numero` (texto livre, editável, salvo via `atualizar()`).
   - Botão "Consultar no SICAR" — abre o link (com ou sem parâmetro pré-preenchido,
     conforme confirmado no contexto acima) numa nova aba.
   - `st.file_uploader` aceitando `.zip`.
   - Ao importar: mostra a área do imóvel segundo o CAR, a área já cadastrada no AgroTop
     (`properties.poligono`/`geometria_area_ha`), o percentual de sobreposição (reusando a
     técnica de `_avaliar_par_sobreposto`), e um mapa (`folium`, mesmo padrão de
     `_entrada_de_perimetro`) com as duas geometrias sobrepostas em cores diferentes — mais
     as camadas de APP/Reserva Legal se o arquivo trouxer, só para referência visual,
     **sem botão de salvar essas camadas**.
   - Botão "Salvar perímetro do CAR" grava só `poligono_car`/`car_area_ha` (a camada de
     perímetro do imóvel) via `atualizar()`.
   - Aviso obrigatório de não-certificação, visível (ver Regra de Ouro).

## Critério de aceite

1. `ler_shapefile_car` testado com um `.zip` de amostra real (peça ao mantenedor, ou
   documente no PR de onde veio a amostra usada nos testes — não gere um Shapefile
   sintético que só bate com a própria suposição de formato).
2. `.zip` corrompido/sem Shapefile válido → `ValueError` claro, testado.
3. Propriedade sem CAR importado ainda → nenhum erro em `page_propriedades`, campos
   simplesmente vazios/não preenchidos.
4. Após importar, `car_numero`/`poligono_car`/`car_area_ha` persistem e voltam a aparecer
   ao reabrir a propriedade (teste real de gravação e releitura, não só o valor em memória).
5. `repositories/propriedades.py::atualizar()` grava os três campos novos — teste
   confirmando que `permitidos` foi atualizado (chamando `atualizar()` com esses campos e
   lendo de volta via `get()`).
6. Percentual de sobreposição calculado bate com um caso manual conferido no teste (dois
   polígonos conhecidos, sobreposição calculada à mão ou via `shapely` direto no teste,
   comparada contra o resultado da função).
7. Aviso de não-certificação presente e visível no texto renderizado da seção — mesmo
   padrão de teste usado na spec 0080/0079 (prova real, não revisão visual).
8. `flake8`/`ruff` e a suíte inteira verdes (`AGROTOP_FORCE_SQLITE=1 python -m unittest
   discover -s tests -t . -v`), incluindo com `pyshp` instalado.

## Proibições

- ❌ **Não automatize nem contorne o CAPTCHA do SICAR**, em nenhuma forma — nem OCR, nem
  serviço de terceiro que resolve CAPTCHA, nem "modo semi-automático". É a proibição
  central desta spec.
- ❌ Não persista as camadas de APP/Reserva Legal/vegetação nativa/hidrografia/etc — só o
  perímetro do imóvel. Se aparecer necessidade real de guardar essas camadas depois (ex.
  para o cruzamento com NDVI que o ROADMAP também lista como objetivo futuro), é spec
  nova, decisão à parte — não expanda o escopo aqui.
- ❌ Não prometa certificação, conformidade legal ou aprovação de auditoria em nenhum
  texto desta seção — mesma regra da spec 0080.
- ❌ Não hardcode o formato/nome das camadas do Shapefile sem antes verificar contra uma
  amostra real — é a causa mais provável de bug silencioso nesta spec (camada errada
  identificada como "perímetro do imóvel").
- ❌ Não altere `properties.poligono` (o perímetro que o produtor já desenha/importa
  hoje) — `poligono_car` é um campo **separado**, para comparação, não substitui nem
  sincroniza automaticamente com o perímetro cadastrado.
- ❌ Não adicione endpoint de API nem tela mobile para isto — mesmo raciocínio de exclusão
  já aplicado ao NDVI (spec 0079) e ao pacote de evidências (spec 0080): é ferramenta de
  conferência de mesa, não de campo.
- ❌ Não adicione `geopandas`/`fiona`/GDAL de sistema — `pyshp` é suficiente e mais leve.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall app.py services repositories
grep -rn "captcha\|CAPTCHA\|resolver.*desafio" services/importacao_car.py app.py  # confirme: nada
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo do PR: de onde veio a amostra real
de Shapefile usada nos testes, qual formato de camadas o arquivo real tinha (para
documentar a decisão de identificação de camada), e cole o texto exato do aviso de
não-certificação como aparece na UI.
