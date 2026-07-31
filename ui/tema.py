"""Paleta e tema do AgroTop — fonte única de verdade das cores.

Implementa o [DESIGN.md](../DESIGN.md). Regra ROADMAP.md R20: **nenhum hex literal
fora deste arquivo**; escolha pelo significado (`sucesso`), não pela aparência
(`verde`).

O tema é **escolha do usuário** (escuro/claro), no web e no mobile. Por isso a
paleta é indexada por token semântico com valor por tema — e não uma lista de cores.

⚠️ O tema claro NÃO é a paleta invertida. As cores semânticas são deliberadamente
mais escuras nele: verde-limão `#4ade80` sobre branco não atinge contraste de
leitura. Ao mexer em qualquer valor, confira o contraste (alvo: WCAG AA, 4,5:1)
contra `fundo` e `superficie` do respectivo tema.

Uso no web:
    from ui.tema import cores, css_variaveis, plotly_layout
    c = cores()                       # paleta do tema ativo
    st.markdown(css_variaveis(), unsafe_allow_html=True)   # injeta :root
    fig.update_layout(**plotly_layout(height=300))

No CSS, referencie por variável — assim a folha de estilo não muda com o tema:
    .card-green { border-color: var(--sucesso); }
"""

ESCURO = {
    "fundo":            "#0f172a",
    "fundo_alt":        "#0a1628",
    "superficie":       "#1e293b",
    "borda":            "#334155",
    "borda_suave":      "#475569",
    "texto":            "#f1f5f9",
    "texto_secundario": "#94a3b8",
    "texto_terciario":  "#64748b",
    "primaria":         "#4ade80",
    "sucesso":          "#4ade80",
    "sucesso_escuro":   "#166534",
    "sucesso_fundo":    "#14532d",
    "atencao":          "#fbbf24",
    "atencao_escuro":   "#854d0e",
    "atencao_fundo":    "#422006",
    "perigo":           "#f87171",
    "perigo_escuro":    "#7f1d1d",
    "perigo_fundo":     "#450a0a",
    "info":             "#22d3ee",
    "info_fundo":       "#1e3a5f",
    "destaque":         "#a78bfa",
}

CLARO = {
    "fundo":            "#f8fafc",
    "fundo_alt":        "#f1f5f9",
    "superficie":       "#ffffff",
    "borda":            "#e2e8f0",
    "borda_suave":      "#cbd5e1",
    "texto":            "#0f172a",
    "texto_secundario": "#475569",
    "texto_terciario":  "#64748b",
    "primaria":         "#15803d",
    "sucesso":          "#15803d",
    "sucesso_escuro":   "#166534",
    "sucesso_fundo":    "#dcfce7",
    "atencao":          "#b45309",
    "atencao_escuro":   "#854d0e",
    "atencao_fundo":    "#fef3c7",
    "perigo":           "#b91c1c",
    "perigo_escuro":    "#7f1d1d",
    "perigo_fundo":     "#fee2e2",
    "info":             "#0e7490",
    "info_fundo":       "#cffafe",
    "destaque":         "#6d28d9",
}

TEMAS = {"escuro": ESCURO, "claro": CLARO}
TEMA_PADRAO = "escuro"   # tema atual do app — manter para não haver mudança visual

# Séries categóricas de gráfico. Áreas grandes exigem menos contraste que texto,
# mas o matiz precisa continuar reconhecível nos dois temas (R21: cor nunca é o
# único portador de informação).
SERIES = ["#4ade80", "#22d3ee", "#fbbf24", "#a78bfa", "#f87171",
          "#34d399", "#60a5fa", "#fb923c", "#f472b6", "#facc15"]

# Escalas contínuas usadas em gráficos de barra por desempenho.
ESCALA_RUIM_BOM = ["#f87171", "#fbbf24", "#4ade80"]
ESCALA_BOM_RUIM = ["#4ade80", "#fbbf24", "#f87171"]


def cores(tema: str | None = None) -> dict:
    """Paleta do tema pedido (ou do padrão). Nome desconhecido cai no padrão."""
    return TEMAS.get(tema or TEMA_PADRAO, TEMAS[TEMA_PADRAO])


def css_variaveis(tema: str | None = None) -> str:
    """Bloco `<style>` com as variáveis CSS do tema.

    Injetar uma vez por página. Trocar de tema passa a ser reemitir este bloco —
    a folha de estilo em si nunca muda, porque referencia `var(--token)`.
    """
    linhas = "\n".join(f"  --{nome}: {valor};" for nome, valor in cores(tema).items())
    return f"<style>\n:root {{\n{linhas}\n}}\n</style>"


def plotly_layout(tema: str | None = None, **overrides) -> dict:
    """Layout padrão dos gráficos, já no tema ativo.

    Substitui o antigo dicionário `PLOTLY` de `app.py`, que fixava
    `template='plotly_dark'` e a cor da fonte.
    """
    c = cores(tema)
    escuro = (tema or TEMA_PADRAO) == "escuro"
    base = dict(
        template="plotly_dark" if escuro else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=c["texto"], size=12),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    base.update(overrides)
    return base
