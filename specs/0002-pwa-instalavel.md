# Spec 0002 — PWA: tornar o AgroTop instalável no celular

- **Tipo:** funcionalidade · **Risco:** baixo · **Esforço:** ~1 dia
- **Branch:** `feat/pwa-instalavel`
- **Arquivos:** `.streamlit/` (arquivos estáticos), `app.py` (**apenas** a injeção do
  `<head>`), e um ícone novo

---

## Contexto e objetivo

O AgroTop é usado **no campo, pelo celular** (Modo Campo, câmera/QR, teclado numérico).
Hoje abre como página de navegador comum: barra de endereço ocupando tela, e sem ícone
na tela inicial.

O objetivo é que o operador **instale** o app ("adicionar à tela de início") e ele abra
em tela cheia, com ícone próprio.

**Isto não é o app nativo.** A Trilha 1 do [ROADMAP.md](../ROADMAP.md) trata do Flutter,
com offline e Bluetooth. Esta spec entrega só o ganho barato e imediato: ícone e tela cheia.

## O que fazer

1. **`manifest.json`** com: `name` "AgroTop", `short_name` "AgroTop", `display: "standalone"`,
   `start_url` da raiz, `background_color` e `theme_color` **vindos da paleta**
   (`ui/tema.py` → `fundo` = `#0f172a`, `primaria` = `#4ade80` no tema escuro).
2. **Ícones** 192×192 e 512×512 PNG. Tema rural/pecuária, coerente com o emoji 🐄 usado
   no app. Aceitável gerar um ícone simples com o texto/símbolo sobre a cor `primaria`.
3. **Referenciar o manifest no `<head>`.** O Streamlit não expõe o `<head>` diretamente;
   a via usual é injetar via `st.markdown(..., unsafe_allow_html=True)` no início do
   `main()`. Documente no PR a abordagem escolhida e sua limitação.
4. **Testar num celular real** (ou no DevTools → Application → Manifest) e anexar
   evidência no PR.

## Critério de aceite

1. O navegador oferece "instalar" / "adicionar à tela de início".
2. Instalado, abre **sem a barra de endereço**.
3. O ícone aparece na tela inicial.
4. **O login por cookie continua funcionando** no modo instalado — o app usa
   `agrotop_sid` com validade de 7 dias, e um PWA tem contexto de armazenamento próprio.
   Este é o ponto de maior risco da tarefa: **teste explicitamente** entrar, fechar,
   reabrir pelo ícone e confirmar que a sessão persiste.
5. Os 72 testes continuam verdes.

## Proibições

- ❌ Não altere lógica de página, navegação ou o guard de perfil
  (`OPERATOR_PAGES`, [ROADMAP.md](../ROADMAP.md) R13).
- ❌ Não crie diretório `pages/` — nome reservado pelo Streamlit; criaria navegação
  automática contornando o guard de perfil (R12).
- ❌ Não introduza hex de cor literal: use os valores de `ui/tema.py` (R20).
- ❌ Não adicione service worker com cache offline nesta tarefa. Cache mal configurado
   serviria versão velha do app após deploy, e o diagnóstico é penoso. Offline é a
   Trilha 1.
- ❌ Não toque em `database.py`, `services/`, `repositories/` — a Fase A está trabalhando ali.

## Como verificar antes de abrir o PR

```bash
python -m streamlit run app.py                 # abrir no celular na mesma rede
python -m unittest discover -s tests -t . -v   # 72 testes, verde
```

## Entrega

PR para `main` com: abordagem usada para injetar o `<head>` e sua limitação, evidência do
manifest válido (print do DevTools ou do celular), e **confirmação explícita de que o
login por cookie sobrevive** ao fechar e reabrir pelo ícone.
