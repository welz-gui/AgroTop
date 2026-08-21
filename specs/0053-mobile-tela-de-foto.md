# Spec 0053 — Mobile: tela de foto do animal

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2–3 dias
- **Branch:** `feat/mobile-foto-do-animal`
- **Altere:** `mobile/` (a pasta que a spec 0047 criou)
- **Pré-requisito obrigatório:** **a spec [0047](0047-mobile-v1a-login-animais-e-pesagem.md)
  precisa estar mesclada em `main`.** Confirme:
  ```bash
  git fetch origin
  git cat-file -e origin/main:mobile/lib/app.dart 2>/dev/null \
    && echo "0047 já mesclada — pode seguir" \
    || echo "0047 AINDA NÃO mesclada — pare e avise quem te instruiu"
  ```

---

## Regra de ouro desta spec

**Contrato travado na spec [0052](0052-api-foto-do-animal.md) — não invente endpoint,
payload nem formato de erro diferente do que ela define.** Você não precisa esperar a 0052
mesclar — teste contra um **servidor mock**, mesmo padrão da 0047/0049/0051.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), subtarefa 1.11. Tirar e enviar foto do animal direto
da câmera do celular, na ficha (já existente, da 0047).

## Contexto que você precisa

- **A compressão da imagem é responsabilidade DESTA tela, não da API** (decisão registrada
  na spec 0052) — comprima antes de enviar. Alvo: lado máximo 1000px, JPEG qualidade ~75
  (mesmo parâmetro que `app.py::_compress_image` usa no web — não precisa ser idêntico
  byte a byte, só na mesma faixa de tamanho final).
- A API (0052) recusa upload acima de 5 MB — sua compressão deve deixar folga real disso,
  não upload no limite.
- `poc/mobile/` não tem tela de foto — é nova.

## Contrato obrigatório

Contra a API da spec 0052:

```
POST /animais/{id}/fotos   (multipart)   -> envia
GET  /animais/{id}/fotos                 -> lista de fotos já enviadas
GET  /fotos/{id}                         -> exibe uma foto
```

Telas/fluxos obrigatórios:

1. **Botão "Tirar foto" na ficha** — abre a câmera nativa (não a galeria por padrão; galeria
   como opção secundária, se quiser incluir). **Câmera só sob demanda** (ROADMAP R15,
   mesma regra do web): nunca instanciada antes do usuário pedir.
2. **Comprime antes de enviar** — ver "Contexto que você precisa".
3. **Confirmação visível de envio** — sucesso ou erro claros; erro de rede não trava a tela
   nem perde a foto tirada (permita tentar de novo sem precisar refotografar).
4. **Galeria de fotos do animal** na ficha — miniaturas das fotos já enviadas
   (`GET /animais/{id}/fotos` + `GET /fotos/{id}` por miniatura), mais recente primeiro.

## Servidor mock para teste

Estenda o mock já usado pelas specs anteriores, respondendo às três rotas da 0052 —
incluindo aceitar `multipart/form-data` de verdade no teste (não simplifique para JSON).

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo um fluxo completo simulando uma imagem de teste: tirar
   (ou selecionar, no ambiente de teste) → comprimir → enviar → aparece na galeria da ficha
   (contra o mock).
3. Teste prova que a imagem enviada ao mock ficou **menor** que a original de teste (a
   compressão de fato reduziu tamanho, não é só um passo decorativo).
4. Erro de rede durante o envio mostra mensagem clara e **mantém a foto capturada
   disponível para reenviar**, sem obrigar o usuário a tirar de novo.
5. Testes visuais (golden) cobrem a galeria de fotos vazia e com fotos, nos três temas.
6. `grep -rn "calculate_gmd\|regra de negócio\|fórmula" mobile/lib/` continua sem achar
   nada.

## Proibições

- ❌ Não altere `backend_api/`, `poc/`, `app.py`, `database.py`, `services/`,
  `repositories/`, nem os arquivos das specs anteriores.
- ❌ Não implemente exclusão de foto — a 0052 não expõe `DELETE`.
- ❌ Não aponte para a API real nem tente subir `backend_api/` para testar.
- ❌ Não invente campo, endpoint ou formato de erro que a 0052 não define. Diverge → pare
  e reporte.
- ❌ Não envie a imagem sem comprimir "pra simplificar" — é o ponto central desta spec.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, o tamanho antes/depois da compressão no seu teste, e diga
explicitamente: "testado contra servidor mock, não contra a 0052 real".
