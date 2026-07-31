# Spec 0003 — PoC: biblioteca de mapa para desenhar piquetes no Streamlit

- **Tipo:** pesquisa (PoC) · **Risco:** baixo · **Esforço:** 1–2 dias
- **Branch:** `poc/mapa-piquetes`
- **Trabalhe apenas em:** `poc/mapa/` (pasta nova). Nada fora dela.

---

## A pergunta que esta PoC responde

**Qual biblioteca permite ao usuário desenhar o polígono de um piquete dentro do Streamlit,
devolver as coordenadas para o Python, e funcionar num celular?**

Ela destrava a Trilha 2 do [ROADMAP.md](../ROADMAP.md) (geometria dos piquetes), que hoje
está parada por falta dessa resposta.

## Por que importa

Hoje a área do piquete (`lotes.area_ha`) é **digitada à mão** — e ela alimenta
`capacity_ua` e a lotação UA/ha exibida no dashboard. Qualquer erro de digitação se
propaga para a decisão de lotação. Com o polígono, a área passa a ser **calculada**.

## O que avaliar

No mínimo `streamlit-folium` (Folium + Leaflet.Draw) e `pydeck`. Se conhecer outra opção
madura, inclua e justifique.

Para cada uma, responda **com evidência**, não com impressão:

1. **Desenho funciona?** O usuário consegue traçar um polígono sobre imagem de satélite?
2. **As coordenadas voltam para o Python?** É o ponto crítico — muitos componentes
   renderizam mas não devolvem a interação. Mostre o GeoJSON capturado.
3. **Edição posterior?** Dá para carregar um polígono salvo e ajustar os vértices?
4. **Funciona no celular?** Teste num aparelho real: desenhar com o dedo é utilizável?
5. **Cálculo de área confere?** Compare o resultado com um valor conhecido. Atenção: área
   em graus não é área em metros — é preciso projetar. Diga qual método usou.
6. **Custo de tela?** Tempo de carga e se atrapalha o rerun do Streamlit.
7. **Licença e manutenção:** licença compatível com uso comercial? Último commit?

## Entregável

1. `poc/mapa/README.md` — o relatório, com **recomendação explícita** de uma biblioteca e
   o porquê. Inclua o que **não** funcionou: é a parte mais valiosa.
2. `poc/mapa/demo.py` — app Streamlit mínimo, executável, que desenha um polígono, mostra
   as coordenadas capturadas e a área calculada.
3. `poc/mapa/requirements.txt` — dependências da PoC.
4. Capturas de tela (desktop e celular).

## Critério de aceite

O relatório responde às 7 perguntas com evidência, e a demo roda com:
```bash
pip install -r poc/mapa/requirements.txt
python -m streamlit run poc/mapa/demo.py
```

## Proibições

- ❌ **Não adicione dependência ao `requirements.txt` da raiz** — ele alimenta o deploy do
  Streamlit Cloud, e uma lib pesada quebraria produção.
- ❌ Não toque em `app.py`, `database.py`, `services/`, `repositories/`, `ui/`.
- ❌ Não crie tabela, coluna nem migration. Geometria no banco é decisão posterior
  (PostGIS 3.3.7 está disponível, mas não instalado).
- ❌ Não integre ao app real. **Isto é PoC** — o produto é o aprendizado, não o código
  ([ROADMAP.md](../ROADMAP.md) R30). O código fica no branch como evidência.

## Como verificar antes de abrir o PR

```bash
python -m unittest discover -s tests -t . -v   # 72 testes, verde (nada seu deve afetá-los)
```

## Entrega

PR para `main` com o relatório no corpo (resumo) e a recomendação em uma frase.
Não espere que o código seja mesclado — espere que a **decisão** seja tomada a partir dele.
