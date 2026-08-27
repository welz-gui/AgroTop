# Spec 0063 — API: alertas operacionais

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/api-alertas-operacionais`
- **Altere:** só `backend_api/` (`main.py`, `schemas.py`) e os testes correspondentes
- **Pré-requisito:** nenhum — todas as funções que esta spec expõe já existem em
  `database.py` e já estão em produção via o app web.

---

## Regra de ouro desta spec

**Zero lógica nova.** Esta API só expõe, em JSON, o que `app.py::_alertas_operacionais`
já calcula chamando `database.py`. Nenhuma conta nova, nenhum limiar novo — mesmo princípio
de toda API deste projeto (R8/ADR 0002): o endpoint é uma tradução para JSON de uma função
que já existe e já está em produção.

## Objetivo

Primeira spec do Tier 1 da [ADR 0007](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md)
(paridade admin no mobile). No web, `page_alertas` (aba "🔔 Operacionais") responde "o que eu
preciso fazer hoje" — é a pergunta mais natural de se fazer olhando o celular no curral, e
hoje só existe no navegador. Esta spec cria a API; a spec mobile seguinte consome.

## Contexto que você precisa

- **Fonte de dados — todas em `database.py`, sem tocar nada**:
  - `db.get_alert_animals() -> dict` com chaves `sumidos`, `carencia`, `prontos` — cada
    lista é de animais (dict completo) mais campos calculados (`days_since_weighing`,
    `withdrawal_end`+`days_remaining`, `arrobas`).
  - `db.check_low_stock() -> list[dict]` — insumos com `current_stock <= min_stock`.
  - `db.get_low_performance(meta=None) -> list[dict]` — animais com `gmd < meta`
    (`meta = db.get_gmd_target()` se não informado), cada um com campo `gmd` adicional.
- **Fora de escopo desta spec: "🧭 Recomendações" (motor de regras,
  `services/recomendacoes.py::avaliar_recomendacoes`).** O contexto que essa função
  consome (`app.py::_contexto_recomendacoes`) é montado hoje **dentro do `app.py`**, não em
  `database.py`/`services/` — expô-lo pela API exigiria mover esse contexto para um lugar
  reutilizável primeiro (trabalho de outra spec, não desta). **Não tente mover
  `_contexto_recomendacoes`** — se notar que falta, pare e reporte, não implemente por
  conta própria.
- **Cada categoria retorna só os campos que a tela precisa** — não serialize o dict de
  animal/insumo inteiro (tem campos internos, alguns nomes em inglês que não fazem sentido
  na API). Escolha explicitamente os campos (ver contrato abaixo).

## Contrato obrigatório

```
GET /alertas
  -> {
       "sumidos": [
         { "animal_id": str, "breed": str, "lote_id": str|null,
           "peso_atual": float, "dias_sem_pesagem": int }
       ],
       "carencia": [
         { "animal_id": str, "breed": str,
           "carencia_ate": str (data ISO), "dias_restantes": int }
       ],
       "prontos_para_abate": [
         { "animal_id": str, "breed": str,
           "peso_atual": float, "peso_alvo": float, "arrobas": float }
       ],
       "estoque_baixo": [
         { "insumo_id": int, "nome": str,
           "estoque_atual": float, "estoque_minimo": float, "unidade": str }
       ],
       "baixo_desempenho": [
         { "animal_id": str, "breed": str, "lote_id": str|null,
           "peso_atual": float, "gmd": float, "meta_gmd": float }
       ]
     }
```

- Autenticação igual às outras rotas (token válido, qualquer papel — **não** restrinja a
  admin: o web não restringe esta página a admin, só "Baixo Desempenho" tinha um botão
  condicional de navegação, que não existe na API).
- Uma única chamada, sem paginação — o volume desta fazenda (dezenas a poucas centenas de
  animais) não justifica.
- Categoria vazia devolve lista vazia `[]`, nunca `null` nem chave ausente.

## Critério de aceite

1. `GET /alertas` sem token → 401.
2. Com token válido, devolve as 5 categorias, cada uma um array (vazio se não houver
   itens) — teste com fazenda sem nenhum alerta (todas vazias) e com pelo menos um item em
   cada categoria.
3. `sumidos`: animal com pesagem há mais de 30 dias aparece; animal pesado recentemente
   não aparece. `dias_sem_pesagem` bate com a conta real.
4. `carencia`: animal com medicamento cuja carência ainda não venceu aparece com
   `dias_restantes` correto; carência já vencida não aparece.
5. `prontos_para_abate`: animal com peso ≥ peso-alvo **e sem carência ativa** aparece;
   peso-alvo ausente usa 500 (mesmo default do web, `a.get("target_weight") or 500`).
6. `estoque_baixo`: insumo com `current_stock <= min_stock` aparece; acima do mínimo não.
7. `baixo_desempenho`: animal com GMD abaixo da meta (`db.get_gmd_target()`) aparece com
   `gmd` e `meta_gmd` corretos; animal sem GMD calculável (poucas pesagens) não aparece
   nem quebra a resposta.
8. `flake8`/`ruff` (o que o projeto já usa) e a suíte inteira de
   `tests/test_backend_api.py` verde.

## Proibições

- ❌ Não implemente "Recomendações" (motor de regras) — fora de escopo, ver "Contexto".
- ❌ Não calcule nada no `backend_api/` — toda conta já existe em `database.py`; se um
  número não bate com o que a função devolve, o bug é na leitura da resposta, não em
  reimplementar a conta.
- ❌ Não altere `app.py`, `database.py`, `services/` nem as specs anteriores.
- ❌ Não invente um sexto tipo de alerta.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall backend_api tests
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que os 8 critérios têm teste com
prova real (não só "não deu erro") — mesmo padrão das specs 0054/0050.
