# Spec 0001 — Atualizar as actions do CI (Node 20 → Node 24)

- **Tipo:** manutenção · **Risco:** baixo · **Esforço:** minutos
- **Branch:** `manutencao/ci-actions-node24`
- **Arquivo a alterar:** `.github/workflows/ci.yml` — **e nenhum outro**

---

## Contexto

O GitHub Actions emite aviso a cada execução:

> Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced
> to run on Node.js 24: `actions/checkout@v4`, `actions/setup-python@v5`

Não quebra nada hoje, mas o aviso vai virar erro quando o Node 20 for removido.
Consta como dívida no [ROADMAP.md](../ROADMAP.md) seção 9.

## O que fazer

Subir as duas actions para a major mais recente que use Node 24:

- `actions/checkout@v4` → `actions/checkout@v5` (ou superior)
- `actions/setup-python@v5` → `actions/setup-python@v6` (ou superior)

Confirme a versão vigente na página de cada action antes de fixar. Não use `@main`
nem `@master` — a versão precisa ser fixada.

## Critério de aceite

1. O workflow continua rodando os mesmos passos, na mesma ordem.
2. **O comando de teste permanece exatamente:**
   ```
   python -m unittest discover -s tests -t . -v
   ```
   O `-t .` **não é opcional** e não pode ser removido: sem ele, `tests/__init__.py` não é
   importado, `AGROTOP_FORCE_SQLITE` não é definida e — numa máquina com
   `.streamlit/secrets.toml` — os testes conectariam no **banco de produção**
   ([ROADMAP.md](../ROADMAP.md) R16).
3. O CI fica verde no PR, com **72 testes**.
4. O aviso de Node 20 desaparece do log da execução.

## Proibições

- ❌ Não altere nenhum arquivo além de `.github/workflows/ci.yml`.
- ❌ Não adicione, remova nem reordene passos do workflow.
- ❌ Não mexa na versão do Python (`3.12`).
- ❌ Não remova itens da seção "Dívidas conhecidas" do ROADMAP — quem fecha a dívida é o
   mantenedor, ao revisar. *(Um PR anterior removeu uma dívida de segurança que continuava
   valendo; por isso esta regra é explícita.)*

## Como verificar antes de abrir o PR

```bash
python -m unittest discover -s tests -t . -v   # 72 testes, verde
python -m compileall app.py database.py repositories services ui tests tools
```

## Entrega

PR para `main` explicando qual versão de cada action foi usada e por quê. Aguarde o CI
verde — a `main` é protegida e exige o check `test` aprovado.
