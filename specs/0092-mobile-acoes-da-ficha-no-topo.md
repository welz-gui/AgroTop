# Spec 0092 — Mobile: ações da ficha do animal promovidas para o topo

- **Tipo:** manutenção · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `fix/mobile-ficha-acoes-no-topo`
- **Altere:** `mobile/lib/screens/animals_page.dart` (`_AnimalDetailPageState.build`),
  testes/goldens correspondentes
- **Pré-requisito:** nenhum

---

## Objetivo

Achado da auditoria de design (`DESIGN-IS-2026-09-10/03-verdict.md`, item #2, evidência
`animals_page.dart:992-1119` na época da auditoria): na ficha do animal, os três botões de
ação (**Registrar pesagem**, **Registrar medicamento**, **Mover de piquete**) ficam no
**fim** da tela — depois do card de dados básicos, métricas, dados de entrada/fornecedor,
histórico de sanidade e fotos. A [spec 0084](0084-mobile-menu-de-navegacao-lateral.md) já
resolveu a metade deste achado que era sobre navegação (`AppBar`→`Drawer`); esta spec
resolve a outra metade, citada explicitamente pelo parecer: "tornar Registrar pesagem
imediatamente acessível".

## Contexto que você precisa

- **Ordem atual da ficha** (`_AnimalDetailPageState.build`, dentro do `ListView`):
  1. Card de dados básicos (id, raça/sexo, piquete, status)
  2. Card de status de carência (`carencia-status-card`)
  3. `Wrap` com 5 `MetricCard`s (peso atual, peso de entrada, GMD recente, GMD total,
     peso-alvo)
  4. Card de dados adicionais (nascimento, entrada, fornecedor, UUID)
  5. Card de histórico de sanidade (`medications-history-card`)
  6. `AnimalPhotoSection`
  7. `FilledButton` "Registrar medicamento" (`open-medication`)
  8. `OutlinedButton` "Registrar pesagem" (`open-weighing`)
  9. `OutlinedButton` "Mover de piquete" (`open-movement`)
  10. `ListTile` informativo ("Indicadores calculados no servidor")
- **Pesagem é a ação mais frequente** — é o motivo de o parecer citar especificamente
  "Registrar pesagem" (não medicamento nem movimentação) como a que precisa de acesso
  imediato: um animal é pesado com regularidade, medicado ou movido só ocasionalmente.
- Os três botões já têm `ValueKey`s estáveis (`open-medication`/`open-weighing`/
  `open-movement`) — **não altere os nomes das chaves nem os handlers**
  (`_openMedication`/`_openWeighing`/`_openMovement`), só a posição no `ListView` e a ordem
  relativa entre eles.
- Testes que hoje rolam a tela até esses botões com `scrollUntilVisible`/
  `ensureVisible` (`mobile/test/flow_test.dart`, `mobile/test/offline_flow_test.dart`,
  `mobile/test/golden_screens_test.dart`) precisam ser conferidos — depois da mudança,
  a rolagem necessária deve ser bem menor ou nenhuma, mas **não remova a chamada de
  rolagem só porque parece desnecessária agora**; confirme rodando o teste antes de decidir.

## Contrato obrigatório

Nova ordem do `ListView` da ficha:

1. Card de dados básicos
2. Card de status de carência
3. **Botões de ação, nesta ordem: Registrar pesagem (`open-weighing`) primeiro, depois
   Registrar medicamento (`open-medication`), depois Mover de piquete (`open-movement`)**
4. `Wrap` de métricas (inalterado)
5. Card de dados adicionais (inalterado)
6. Card de histórico de sanidade (inalterado)
7. `AnimalPhotoSection` (inalterada)
8. `ListTile` informativo ("Indicadores calculados no servidor") — continua por último

Estilo dos botões: mantenha `FilledButton.icon`/`OutlinedButton.icon` como hoje, mas
**"Registrar pesagem" passa a ser o `FilledButton`** (destaque visual, é a ação primária
agora) e "Registrar medicamento"/"Mover de piquete" viram `OutlinedButton` (secundários).
Ícones continuam os mesmos de hoje, só a associação estilo↔botão muda.

## Critério de aceite

1. Na ficha (sem rolar, ou com rolagem mínima — confirme visualmente no golden), os três
   botões de ação aparecem logo após o card de carência, antes de qualquer métrica.
2. "Registrar pesagem" é o primeiro botão e usa `FilledButton.icon`; os outros dois usam
   `OutlinedButton.icon`.
3. Os três `ValueKey`s (`open-weighing`/`open-medication`/`open-movement`) continuam
   existindo e disparando os mesmos handlers de antes — nenhum teste de fluxo (pesagem,
   medicamento, movimentação) muda de comportamento, só a posição do botão na tela.
4. `flutter test` completo verde, incluindo os testes que hoje rolam até esses botões.
5. Goldens de `03-ficha` (dentro de `golden_screens_test.dart`) regenerados nos três temas.

## Proibições

- ❌ Não mude os handlers (`_openMedication`/`_openWeighing`/`_openMovement`) nem o que
  cada ação faz — só a posição e o estilo visual dos botões.
- ❌ Não remova nem reordene o card de carência ou o de dados básicos — eles continuam
  primeiro, antes das ações.
- ❌ Não mexa nas métricas, no histórico de sanidade ou nas fotos além de movê-los para
  depois dos botões — conteúdo e comportamento de cada seção continuam os mesmos.
- ❌ Não toque `backend_api/` nem o dashboard — escopo é só a ficha do animal.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
CAPTURE_GOLDENS=1 flutter test --update-goldens
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo do PR que os testes que antes
rolavam até os botões (`scrollUntilVisible`/`ensureVisible`) foram conferidos, não só
deixados como estavam.
