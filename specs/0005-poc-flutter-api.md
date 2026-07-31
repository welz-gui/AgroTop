# Spec 0005 — PoC: esqueleto Flutter + API autenticada

- **Tipo:** pesquisa (PoC) · **Risco:** médio · **Esforço:** 3–5 dias
- **Branch:** `poc/flutter-api`
- **Trabalhe apenas em:** `poc/mobile/` e `poc/api/` (pastas novas). Nada fora delas.

---

## A pergunta que esta PoC responde

**O caminho "app Flutter → API Python → mesma regra de negócio do web" funciona de ponta a
ponta, e quanto custa operá-lo?**

O app nativo é prioridade declarada do dono do produto (Trilha 1 do
[ROADMAP.md](../ROADMAP.md)). Antes de construí-lo, é preciso provar o encanamento e
levantar os custos reais.

## Leia antes de começar

**[ADR 0002](../docs/adr/0002-fronteira-de-portabilidade.md)** — ele **veta Supabase Auth**.
A identidade dos usuários fica na tabela `users` do próprio banco (PBKDF2 já implementado).
Um app com Supabase Auth e um web com tabela própria criariam dois modelos de permissão
incompatíveis.

Existe um app Flutter **abandonado** em `git show archive/app-mobile-obsoleto:...`.
**Não copie nada dele.** Ele tinha login simulado, consultava colunas inexistentes
(`animal_id`, `gmd`, `category`, `origin`) e devolvia três animais fictícios num `catch`
silencioso. Serve só como aviso. O `backend_api/` do mesmo branch tem estrutura FastAPI
aproveitável — mas **a lógica não**: o `terminacao_service.py` de lá duplica
`services/terminacao.py`, exatamente o erro que a R8 proíbe.

## O que fazer

### Parte 1 — API (FastAPI)

Endpoints mínimos:
- `POST /auth/login` — valida contra a tabela `users` usando `services.seguranca`, devolve token
- `GET /animais` — lista animais ativos
- `GET /animais/{id}` — ficha, com GMD

**A API importa `services/` e `repositories/`. Não reimplementa cálculo nenhum** (R8).
Rode contra SQLite local (`AGROTOP_FORCE_SQLITE=1`), nunca contra produção.

### Parte 2 — App Flutter

Três telas: login, lista de animais, ficha. Consumindo a API. Sem offline.

**Design espelha o [DESIGN.md](../DESIGN.md):** o `app_colors.dart` deve ser gerado a
partir dos tokens de `ui/tema.py`, com suporte a escuro, claro e "seguir o sistema" desde
o início. Foi escrevendo cores à mão que o app abandonado virou outro produto visualmente.

### Parte 3 — Responder as perguntas de custo

1. **Onde hospedar a API?** Ela não roda no Streamlit Cloud. Compare Render, Fly.io e
   Railway: plano gratuito existe? dorme? quanto custa o menor plano pago?
2. **Build Android:** o `build_apk.yml` do branch arquivado ainda funciona? Gera APK
   instalável?
3. **iOS:** o que exatamente é necessário (Mac, conta, certificados)? Quanto custa por ano?
4. **Token:** onde guardar com segurança no dispositivo, e qual validade adotar?

## Entregável

1. `poc/README.md` — relatório com as respostas de custo e o veredito: o caminho se sustenta?
2. `poc/api/` — API executável + instruções.
3. `poc/mobile/` — app Flutter executável em Android.
4. Vídeo curto ou capturas do fluxo: login → lista → ficha.

## Critério de aceite

1. Login real funciona: usuário criado no SQLite local autentica pelo app.
2. A lista mostra os animais **do banco**, não dados fictícios.
3. O GMD exibido vem de `services/`, e não de cálculo feito no Dart. **Demonstre isso.**
4. As quatro perguntas de custo estão respondidas com números.

## Proibições

- ❌ **Nada de Supabase Auth** (ADR 0002).
- ❌ **Nada de fallback com dados fictícios.** Se a API falhar, o app mostra erro. Foi o
  `catch` silencioso que fez o app antigo parecer funcionar por meses sem nunca ter lido o
  banco de verdade.
- ❌ Não reimplemente regra de negócio no Dart nem na API (R8).
- ❌ Não conecte em produção. `AGROTOP_FORCE_SQLITE=1`, sempre.
- ❌ Não toque em `app.py`, `database.py`, `services/`, `repositories/`, `ui/`.
- ❌ Não adicione dependência ao `requirements.txt` da raiz.

## Como verificar antes de abrir o PR

```bash
python -m unittest discover -s tests -t . -v   # 72 testes, verde
git diff --stat origin/main                    # só arquivos em poc/
```

## Entrega

PR para `main`. Abra o corpo com o veredito em uma frase e o custo mensal estimado de
manter a API no ar. **É PoC** — o produto é o aprendizado (R30).
