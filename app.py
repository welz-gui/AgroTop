"""
AgroTop — Sistema de Gestão de Gado de Corte
PWA responsivo: Streamlit + SQLite + Plotly
"""

import io
import csv
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
import database as db

# ─── Configuração da página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="AgroTop — Gestão de Gado",
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "AgroTop v2.0 — Gestão Completa de Gado de Corte"},
)

db.init_db()
db.refresh_carencia_status()

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.main .block-container{padding-top:.8rem;padding-bottom:2rem}
section[data-testid="stSidebar"]{background:#0a1628!important}

/* Botões grandes — uso ao sol */
.stButton>button{min-height:2.75rem;font-size:1rem;font-weight:600;border-radius:10px;transition:all .15s}
.stButton>button:hover{transform:translateY(-1px)}

/* Métricas */
div[data-testid="stMetric"]{background:#1e293b;border:1px solid #334155;border-radius:14px;padding:1rem 1.2rem}
div[data-testid="stMetricValue"]{font-size:1.55rem!important}

/* Título de página */
.page-title{font-size:1.55rem;font-weight:800;color:#4ade80;border-left:4px solid #4ade80;padding-left:.75rem;margin-bottom:1.4rem}

/* Cards */
.card{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:1.2rem 1.5rem;margin-bottom:1rem}
.card-green{background:linear-gradient(135deg,#14532d,#0f172a);border:1px solid #166534;border-radius:16px;padding:1.2rem 1.5rem;margin-bottom:1rem}
.card-yellow{background:linear-gradient(135deg,#422006,#0f172a);border:1px solid #854d0e;border-radius:16px;padding:1.2rem 1.5rem;margin-bottom:1rem}
.card-red{background:linear-gradient(135deg,#450a0a,#0f172a);border:1px solid #7f1d1d;border-radius:16px;padding:1.2rem 1.5rem;margin-bottom:1rem}

/* Badges */
.badge-green {background:#166534;color:#4ade80;padding:2px 10px;border-radius:999px;font-size:.78rem;font-weight:700}
.badge-yellow{background:#713f12;color:#fbbf24;padding:2px 10px;border-radius:999px;font-size:.78rem;font-weight:700}
.badge-red   {background:#7f1d1d;color:#f87171;padding:2px 10px;border-radius:999px;font-size:.78rem;font-weight:700}
.badge-blue  {background:#1e3a5f;color:#60a5fa;padding:2px 10px;border-radius:999px;font-size:.78rem;font-weight:700}
.badge-gray  {background:#1e293b;color:#94a3b8;padding:2px 10px;border-radius:999px;font-size:.78rem;font-weight:700}

/* Linha de histórico */
.hist-item{background:#0f172a;border-left:3px solid #4ade80;border-radius:8px;padding:.45rem .9rem;margin-bottom:.35rem}

/* Teclado numérico */
.keypad-display{font-size:3rem;font-weight:900;color:#4ade80;text-align:center;background:#0f172a;border:2px solid #334155;border-radius:14px;padding:1rem;margin-bottom:.5rem;letter-spacing:.1em}

/* Ocultar elementos padrão (mantendo o botão de abrir o menu lateral) */
#MainMenu,footer{visibility:hidden}
header[data-testid="stHeader"]{background:transparent}
/* Botão para reabrir o menu lateral — sempre visível e destacado */
[data-testid="collapsedControl"]{
    visibility:visible!important;
    display:flex!important;
    opacity:1!important;
    z-index:999999;
}
[data-testid="collapsedControl"] button{
    background:#4ade80!important;
    color:#0f172a!important;
    border-radius:8px;
}

/* Mobile */
@media(max-width:640px){
  .main .block-container{padding-left:.4rem;padding-right:.4rem}
  .stButton>button{min-height:3.2rem;font-size:1.1rem}
  div[data-testid="stMetricValue"]{font-size:1.3rem!important}
}
</style>
""", unsafe_allow_html=True)

# ─── Constantes ───────────────────────────────────────────────────────────────
BREEDS = ["Nelore","Angus","Brahman","Senepol","Brangus","Canchim","Simental",
          "Hereford","Charolês","Tabapuã","Outro"]
ROUTES = ["Subcutânea","Intramuscular","Oral","Intravenosa","Tópica"]
COST_TYPES = ["compra","insumo","operacional","veterinário","outro"]
# Cotação padrão centralizada (usada no Simulador e no Relatório Financeiro)
DEFAULT_PRICE_ARROBA = 320.0   # R$ por arroba (boi gordo)
DEFAULT_PRICE_KG     = 10.0    # R$ por kg de boi vivo
PLOTLY = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#f1f5f9",size=12),
    margin=dict(l=10,r=10,t=30,b=10),
)

def _layout(**overrides):
    """Mescla o layout padrão PLOTLY com overrides (evita conflito de kwargs)."""
    base = dict(PLOTLY)
    base.update(overrides)
    return base

# ─── Session State ─────────────────────────────────────────────────────────────
_DEFAULTS = dict(
    authenticated=False, user=None, page="dashboard",
    animal_detail=None, campo_id="", keypad_value="",
    unit_pref="kg",   # "kg" ou "@"
)
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Helpers ──────────────────────────────────────────────────────────────────
def _go(page, animal_id=None):
    st.session_state.page = page
    if animal_id is not None:
        st.session_state.animal_detail = animal_id

def _status_badge(status):
    m = {"ativo":"badge-green ● Ativo","vendido":"badge-blue ✓ Vendido",
         "morto":"badge-red ✕ Morto","carencia":"badge-yellow ⚠ Carência"}
    parts = m.get(status, "badge-gray "+status).split(" ",1)
    return f'<span class="{parts[0]}">{parts[1]}</span>'

def _gmd_badge(gmd):
    if gmd is None: return '<span class="badge-gray">— N/D</span>'
    if gmd > 0:     return f'<span class="badge-green">▲ {gmd:.3f} kg/dia</span>'
    if gmd < 0:     return f'<span class="badge-red">▼ {gmd:.3f} kg/dia</span>'
    return f'<span class="badge-yellow">= {gmd:.3f} kg/dia</span>'

# ─── Helpers de unidade (kg / @) ─────────────────────────────────────────────
def _use_arroba() -> bool:
    return st.session_state.get("unit_pref", "kg") == "@"

def _unit_label() -> str:
    """Retorna o símbolo da unidade configurada."""
    return "@" if _use_arroba() else "kg"

def _prod_weight(kg_gain: float, yield_: float = 0.52) -> float:
    """Converte ganho em kg para a unidade configurada (@ ou kg vivo)."""
    if _use_arroba():
        return db.kg_to_arrobas(kg_gain, yield_)
    return round(kg_gain, 1)

def _live_weight(kg: float, yield_: float = 0.52) -> float:
    """Converte peso vivo para a unidade configurada."""
    if _use_arroba():
        return db.kg_to_arrobas(kg, yield_)
    return round(kg, 1)

def _fmt_prod(kg_gain: float, yield_: float = 0.52) -> str:
    """Formata ganho na unidade configurada."""
    val = _prod_weight(kg_gain, yield_)
    return f"{val:.2f} {_unit_label()}" if _use_arroba() else f"{val:.1f} kg"

def _fmt_live(kg: float, yield_: float = 0.52) -> str:
    """Formata peso vivo na unidade configurada."""
    val = _live_weight(kg, yield_)
    return f"{val:.2f} {_unit_label()}" if _use_arroba() else f"{val:.1f} kg"

def _cost_per_unit_label() -> str:
    # Deixa explícito que é sobre o PESO VIVO ATUAL (não sobre o ganho)
    return "Custo/@ vivo (R$)" if _use_arroba() else "Custo/kg vivo (R$)"

def _cost_per_unit(total_cost: float, kg: float, yield_: float = 0.52) -> float:
    """Custo total dividido pelo peso vivo atual (na unidade configurada)."""
    denom = _live_weight(kg, yield_)
    return round(total_cost / denom, 2) if denom else 0

def _breakeven_label() -> str:
    return "Breakeven (R$/@)" if _use_arroba() else "Breakeven (R$/kg)"

def _revenue(kg: float, price_per_unit: float, yield_: float = 0.52) -> float:
    """Receita = unidades × preço."""
    return round(_live_weight(kg, yield_) * price_per_unit, 2)

# ─── Formatação PT-BR (plural e números) ─────────────────────────────────────
def _plural(n, singular: str, plural: str = None) -> str:
    """Ex.: _plural(1,'animal','animais') -> '1 animal'; _plural(3,...) -> '3 animais'."""
    plural = plural or (singular + "s")
    return f"{n} {singular if n == 1 else plural}"

def _num_br(v, casas: int = 1) -> str:
    """Número no padrão brasileiro: 10.0 -> '10,0'."""
    try:
        return f"{float(v):.{casas}f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(v)

def _fmt_dose(dose, unit: str) -> str:
    """Dose + unidade formatadas: '10,0 ml', '2,0 doses', '1,0 comprimido'."""
    plurais = {"dose": "doses", "comprimido": "comprimidos"}
    try:
        d = float(dose)
    except (TypeError, ValueError):
        return f"{dose} {unit}"
    u = plurais.get(unit, unit) if d != 1 else unit
    return f"{_num_br(d)} {u}"

def _df_to_csv(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.where(pd.notna(df), "").to_csv(buf, index=False, encoding="utf-8-sig")
    return buf.getvalue().encode("utf-8-sig")

def _df_to_xlsx(title: str, df: pd.DataFrame) -> bytes:
    """Exporta o DataFrame para Excel (.xlsx) com cabeçalho estilizado."""
    buf = io.BytesIO()
    sheet = (title[:28] or "Dados").replace("/", "-").replace("\\", "-")
    df = df.where(pd.notna(df), "")   # substitui NaN/None por vazio
    try:
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet, startrow=1)
            wb = writer.book
            ws = writer.sheets[sheet]
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

            # Título mesclado no topo
            ncols = max(len(df.columns), 1)
            ws.cell(row=1, column=1, value=f"AgroTop — {title}")
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
            ws.cell(row=1, column=1).font = Font(bold=True, size=13, color="166534")
            ws.cell(row=1, column=1).alignment = Alignment(horizontal="left")

            # Cabeçalho das colunas (linha 2)
            header_fill = PatternFill("solid", fgColor="14532D")
            thin = Side(style="thin", color="D0D0D0")
            border = Border(left=thin, right=thin, top=thin, bottom=thin)
            for col_idx, col_name in enumerate(df.columns, start=1):
                c = ws.cell(row=2, column=col_idx)
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = header_fill
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.border = border

            # Bordas e largura automática das colunas
            for col_idx, col_name in enumerate(df.columns, start=1):
                max_len = len(str(col_name))
                for v in df.iloc[:, col_idx - 1].tolist():
                    max_len = max(max_len, len(str(v)))
                ws.column_dimensions[ws.cell(row=2, column=col_idx).column_letter].width = min(max_len + 3, 40)
            ws.freeze_panes = "A3"
        return buf.getvalue()
    except Exception:
        return b""

def _pdf_safe(text) -> str:
    """Sanitiza texto para a fonte Helvetica (Latin-1) do fpdf.
    Substitui caracteres Unicode não suportados; mantém acentos do português."""
    s = str(text)
    repl = {
        "—": "-", "–": "-", "→": "->", "←": "<-", "•": "*", "●": "*",
        "○": "o", "▲": "^", "▼": "v", "⚠️": "!", "⚠": "!",
        "♂": "M", "♀": "F", "≥": ">=", "≤": "<=", "…": "...",
        "“": '"', "”": '"', "‘": "'", "’": "'", " ": " ",
        "🐄": "", "📄": "", "🏷️": "", "✅": "", "❌": "", "⬇️": "",
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    # Remove qualquer emoji/símbolo restante fora do Latin-1
    return s.encode("latin-1", "replace").decode("latin-1")


def _df_to_pdf(title: str, df: pd.DataFrame) -> bytes:
    try:
        from fpdf import FPDF
        df = df.where(pd.notna(df), "")   # evita "nan" no PDF
        pdf = FPDF(orientation="L")   # paisagem — comporta mais colunas
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, _pdf_safe(title), ln=True, align="C")
        pdf.set_font("Helvetica", "", 6)
        cols  = list(df.columns)
        n     = max(len(cols), 1)
        col_w = max(min(277 // n, 45), 12)   # largura útil em paisagem ~277mm
        # Cabeçalho
        pdf.set_fill_color(30, 60, 30)
        pdf.set_text_color(200, 255, 200)
        pdf.set_font("Helvetica", "B", 6)
        for c in cols:
            pdf.cell(col_w, 6, _pdf_safe(c)[:22], border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(20, 20, 20)
        for i, row in df.iterrows():
            if i % 2 == 0:
                pdf.set_fill_color(245, 245, 245)
            else:
                pdf.set_fill_color(255, 255, 255)
            for c in cols:
                pdf.cell(col_w, 5, _pdf_safe(row[c])[:22], border=1, fill=True)
            pdf.ln()
        out = pdf.output()
        return bytes(out)
    except ImportError:
        return b""
    except Exception:
        # Falha inesperada não deve derrubar a página de relatórios
        return b""

# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════
def page_login():
    _, col, _ = st.columns([1,1.6,1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:2rem 0 1.5rem">
            <div style="font-size:4.5rem;line-height:1">🐄</div>
            <h1 style="color:#4ade80;margin:.4rem 0 0">AgroTop</h1>
            <p style="color:#64748b;margin:0;font-size:.95rem">Sistema de Gestão de Gado de Corte</p>
        </div>""", unsafe_allow_html=True)
        with st.form("login"):
            user = st.text_input("👤 Usuário", placeholder="seu.usuario")
            pwd  = st.text_input("🔑 Senha", type="password", placeholder="••••••••")
            if st.form_submit_button("🔓  Entrar no Sistema", use_container_width=True, type="primary"):
                u = db.verify_login(user.strip(), pwd)
                if u:
                    st.session_state.authenticated = True
                    st.session_state.user = u
                    # Página inicial conforme o perfil
                    st.session_state.page = "dashboard" if u["role"]=="admin" else "campo"
                    # Token de sessão na URL para manter o login ao recarregar
                    try:
                        st.query_params["sid"] = db.create_session(u["id"])
                    except Exception:
                        pass
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
        st.markdown("""
        <div class="card" style="font-size:.82rem;color:#64748b;text-align:center;margin-top:.8rem">
            <strong style="color:#94a3b8">Demo:</strong><br>
            Admin → <code>admin</code> / <code>admin123</code><br>
            Operador → <code>op1</code> / <code>op1234</code>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def _sidebar():
    alerts  = db.get_alert_animals()
    low_stk  = db.check_low_stock()
    # Badge conta TODOS os itens exibidos na página de Alertas (mesma regra)
    n_alerts = (len(alerts["sumidos"]) + len(alerts["carencia"])
                + len(alerts["prontos"]) + len(low_stk))
    user     = st.session_state.user

    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:.8rem 0 .5rem">
            <div style="font-size:2.5rem">🐄</div>
            <h2 style="color:#4ade80;margin:0">AgroTop</h2>
            <div style="color:#94a3b8;font-size:.8rem;margin-top:.25rem">
                {user['name']}<br>
                <span style="color:#4ade80">●</span>&nbsp;
                {"Administrador" if user['role']=='admin' else "Operador"}
            </div>
        </div>""", unsafe_allow_html=True)
        st.markdown("---")

        if user["role"] == "admin":
            pages = [
                ("📊","Dashboard","dashboard",""),
                ("📱","Modo Campo","campo",""),
                ("📋","Rebanho","rebanho",""),
                ("🌿","Lotes / Pastagem","lotes",""),
                ("💰","Financeiro","financeiro",""),
                ("📦","Estoque","estoque",f" 🔴{len(low_stk)}" if low_stk else ""),
                ("🌾","Nutrição","nutricao",""),
                ("🔔","Alertas","alertas",f" 🔴{n_alerts}" if n_alerts else ""),
                ("📄","Relatórios","relatorios",""),
                ("➕","Cadastrar Animal","cadastrar",""),
                ("⚙️","Admin","admin",""),
            ]
        else:
            # Operador: apenas manejo de campo, cadastro e estoque
            pages = [
                ("📱","Modo Campo","campo",""),
                ("➕","Cadastrar Animal","cadastrar",""),
                ("📦","Estoque","estoque",f" 🔴{len(low_stk)}" if low_stk else ""),
            ]

        for icon, label, key, badge in pages:
            active = st.session_state.page == key
            if st.button(f"{icon}  {label}{badge}", key=f"nav_{key}",
                         use_container_width=True,
                         type="primary" if active else "secondary"):
                _go(key); st.rerun()

        st.markdown("---")

        # ── Configuração de unidade (rádio ligado direto ao session_state) ────
        # Fonte única de verdade: a chave 'unit_pref'. Sem rerun manual, evita
        # a barra lateral e a página ficarem dessincronizadas.
        st.radio("⚖️ Unidade de Produção", ["kg", "@"],
                 key="unit_pref", horizontal=True,
                 help="Define a unidade usada em custos, ganhos e relatórios")

        st.markdown("---")
        stats = db.get_rebanho_stats()
        if stats:
            # Usa a MESMA fonte da página (_use_arroba) — sempre consistente
            if _use_arroba():
                prod_str = f"🏷️ <b style='color:#fbbf24'>{stats['arrobas_prod']:.1f} @</b> ganhas"
            else:
                total_gain_kg = sum(a["current_weight"]-a["entry_weight"]
                                    for a in db.get_all_animals())
                prod_str = f"📦 <b style='color:#fbbf24'>{total_gain_kg:.0f} kg</b> ganhos"

            st.markdown(f"""
            <div style="font-size:.78rem;color:#64748b;text-align:center;line-height:2">
                🐄 <b style="color:#f1f5f9">{stats['total']}</b> animais ativos &nbsp;
                ⚖️ <b style="color:#f1f5f9">{stats['avg_weight']:.0f} kg</b> médio<br>
                📈 GMD <b style="color:#4ade80">{stats['avg_gmd']:.3f} kg/dia</b> &nbsp;
                {prod_str}
            </div>""", unsafe_allow_html=True)
        st.markdown("---")
        if st.button("🚪  Sair", use_container_width=True, type="secondary"):
            tok = st.query_params.get("sid")
            if tok:
                db.delete_session(tok)
            st.query_params.clear()
            for k,v in _DEFAULTS.items(): st.session_state[k] = v
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def page_dashboard():
    st.markdown('<div class="page-title">📊 Dashboard — Visão Geral</div>', unsafe_allow_html=True)
    stats   = db.get_rebanho_stats()
    animals = db.get_all_animals()
    alerts  = db.get_alert_animals()
    if not animals:
        st.info("Nenhum animal cadastrado. Use **Cadastrar Animal** para começar."); return

    # KPIs
    # Produção na unidade configurada
    if _use_arroba():
        prod_label = "🏷️ @ Ganhas"
        prod_value = f"{stats['arrobas_prod']:.1f} @"
    else:
        total_gain_kg = sum(a["current_weight"]-a["entry_weight"] for a in animals)
        prod_label = "📦 Ganho Total"
        prod_value = f"{total_gain_kg:.0f} kg"

    k = st.columns(7)
    k[0].metric("🐄 Animais",    stats["total"])
    k[1].metric("⚖️ Peso Médio", f"{stats['avg_weight']:.1f} kg")
    k[2].metric("📈 GMD Médio",  f"{stats['avg_gmd']:.3f} kg/dia")
    k[3].metric(prod_label,      prod_value)
    k[4].metric("🌿 Lotação",    f"{stats['lotacao_ua_ha']:.2f} UA/ha")
    k[5].metric("♂ Machos",      stats["males"])
    k[6].metric("♀ Fêmeas",      stats["females"])

    st.markdown("---")

    # Alertas resumidos
    n_sum = len(alerts["sumidos"]); n_car = len(alerts["carencia"]); n_pro = len(alerts["prontos"])
    if n_sum or n_car or n_pro:
        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            st.markdown(f"""<div class="card-red">
                <b style="color:#f87171">🔴 {n_sum} Sumidos</b><br>
                <span style="color:#94a3b8;font-size:.85rem">Sem pesagem há +30 dias</span>
            </div>""", unsafe_allow_html=True)
        with ac2:
            st.markdown(f"""<div class="card-yellow">
                <b style="color:#fbbf24">🟡 {n_car} Em Carência</b><br>
                <span style="color:#94a3b8;font-size:.85rem">Não podem ser abatidos</span>
            </div>""", unsafe_allow_html=True)
        with ac3:
            st.markdown(f"""<div class="card-green">
                <b style="color:#4ade80">🟢 {n_pro} Prontos para Abate</b><br>
                <span style="color:#94a3b8;font-size:.85rem">Peso-alvo atingido</span>
            </div>""", unsafe_allow_html=True)
        st.markdown("---")

    col_main, col_side = st.columns([3,2])

    with col_main:
        st.subheader("📈 Evolução de Peso do Rebanho")
        raw = db.get_all_weighings()
        if raw:
            df_all = pd.DataFrame(raw)
            df_all["weigh_date"] = pd.to_datetime(df_all["weigh_date"])
            df_avg = (df_all.groupby("weigh_date")["weight"]
                      .mean().reset_index()
                      .rename(columns={"weigh_date":"Data","weight":"Peso Médio (kg)"}))
            fig = go.Figure()
            for aid in df_all["animal_id"].unique():
                sub = df_all[df_all["animal_id"]==aid].sort_values("weigh_date")
                fig.add_trace(go.Scatter(x=sub["weigh_date"],y=sub["weight"],
                    mode="lines+markers",showlegend=False,opacity=0.35,
                    line=dict(width=1,color="#334155"),marker=dict(size=3),
                    hovertemplate=f"<b>{aid}</b><br>%{{x|%d/%m/%Y}}<br>%{{y:.1f}} kg<extra></extra>"))
            fig.add_trace(go.Scatter(x=df_avg["Data"],y=df_avg["Peso Médio (kg)"],
                mode="lines+markers",name="Média do Rebanho",
                line=dict(width=3,color="#4ade80"),
                marker=dict(size=9,color="#4ade80",line=dict(width=2,color="#0f172a")),
                hovertemplate="<b>Média</b><br>%{x|%d/%m/%Y}<br>%{y:.1f} kg<extra></extra>"))
            fig.update_layout(**PLOTLY,height=350,
                legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
                xaxis=dict(gridcolor="#1e293b",title="Data"),
                yaxis=dict(gridcolor="#1e293b",title="Peso (kg)"))
            st.plotly_chart(fig, use_container_width=True)

    with col_side:
        st.subheader("🥧 Por Raça")
        df_br = pd.Series([a["breed"] for a in animals]).value_counts().reset_index()
        df_br.columns=["Raça","Qtd"]
        fig_p=px.pie(df_br,names="Raça",values="Qtd",hole=0.45,
            color_discrete_sequence=["#4ade80","#22d3ee","#a78bfa","#f472b6","#fb923c","#facc15","#34d399"])
        fig_p.update_layout(**_layout(height=240,margin=dict(l=0,r=0,t=10,b=10),
            legend=dict(orientation="h",yanchor="bottom",y=-0.2)))
        fig_p.update_traces(textposition="inside",textinfo="percent+label")
        st.plotly_chart(fig_p, use_container_width=True)

        st.subheader("📊 GMD por Animal")
        gmd_data=[{"ID":a["id"],"GMD":db.calculate_gmd(a["id"])} for a in animals]
        df_g=pd.DataFrame([r for r in gmd_data if r["GMD"] is not None]).sort_values("GMD")
        if not df_g.empty:
            fig_g=px.bar(df_g,x="GMD",y="ID",orientation="h",color="GMD",
                color_continuous_scale=["#f87171","#fbbf24","#4ade80"],
                labels={"GMD":"kg/dia"})
            fig_g.add_vline(x=0,line_dash="dash",line_color="#475569")
            fig_g.update_layout(**PLOTLY,height=max(180,len(df_g)*27),
                coloraxis_showscale=False,
                xaxis=dict(gridcolor="#1e293b"),yaxis=dict(gridcolor="#1e293b",title=""))
            st.plotly_chart(fig_g, use_container_width=True)

    # Tabela resumo
    st.markdown("---"); st.subheader("📋 Resumo Rápido")
    rows=[]
    ul = _unit_label()
    for a in animals:
        gmd  = db.calculate_gmd(a["id"])
        wd   = db.get_withdrawal_end(a["id"])
        gain = round(a["current_weight"]-a["entry_weight"], 1)
        rows.append({"ID":a["id"],"Raça":a["breed"],
            "Sexo":"♂" if a["sex"]=="M" else "♀",
            "Categoria":db.get_age_category(a.get("birth_date")),
            "Lote":a.get("lote_id") or "—",
            "Peso Atual (kg)":a["current_weight"],
            f"Ganho ({ul})":_prod_weight(gain),
            "GMD (kg/dia)":gmd,"Status":a["status"],
            "Carência até":wd.isoformat() if wd else "—"})
    df_sum=pd.DataFrame(rows)
    gain_col = f"Ganho ({ul})"
    fmt_gain = "%.2f" if _use_arroba() else "%.1f"
    st.dataframe(df_sum,use_container_width=True,hide_index=True,height=300,
        column_config={"Peso Atual (kg)":st.column_config.NumberColumn(format="%.1f"),
            gain_col:st.column_config.NumberColumn(format=fmt_gain),
            "GMD (kg/dia)":st.column_config.NumberColumn(format="%.3f")})

# ══════════════════════════════════════════════════════════════════════════════
# MODO CAMPO  (Mobile-first, máx. 3 cliques)
# ══════════════════════════════════════════════════════════════════════════════
def _campo_trato():
    """Checagem de trato/nutrição por piquete — primeira coisa no Modo Campo."""
    hoje = date.today()
    pend = db.get_pending_feedings(hoje)
    if not pend:
        st.info("Nenhum plano de nutrição definido pelo administrador. "
                "Quando houver, os piquetes aparecerão aqui para checagem.")
        return

    # Agrupa por piquete; só mostra piquetes com plano
    lotes_ids = sorted({p["lote_id"] for p in pend})
    pendentes_total = sum(1 for p in pend if not p["done_this_period"])

    if pendentes_total == 0:
        st.success("✅ Todos os tratos do período já foram confirmados. Bom trabalho!")
    else:
        st.markdown(f"**🌾 Trato do dia — {hoje.strftime('%d/%m/%Y')}** · "
                    f"{pendentes_total} item(ns) pendente(s)")

    for lid in lotes_ids:
        itens = [p for p in pend if p["lote_id"]==lid]
        lote_nome = itens[0].get("lote_name") or lid
        pend_lote = [p for p in itens if not p["done_this_period"]]

        # Cabeçalho do piquete
        st.markdown(f'<div class="card" style="margin-bottom:.4rem">'
                    f'<b style="font-size:1.05rem;color:#4ade80">🌿 {lid} — {lote_nome}</b>'
                    f'</div>', unsafe_allow_html=True)

        for p in itens:
            freq = db.FEEDING_FREQUENCIES.get(p["frequency"], p["frequency"])
            if p["done_this_period"]:
                st.markdown(
                    f'<div class="hist-item" style="border-left-color:#166534;opacity:.7">'
                    f'✅ <b>{p["product_name"]}</b> — {p["quantity"]:.0f} {p["unit"]} '
                    f'· {freq} · <span style="color:#4ade80">confirmado</span> '
                    f'(último: {p["last_check"] or "—"})</div>', unsafe_allow_html=True)
                continue

            with st.form(f"trato_{p['id']}", clear_on_submit=True):
                st.markdown(f'**{p["product_name"]}** — aplicar **{p["quantity"]:.0f} {p["unit"]}** · '
                            f'{freq}')
                fc1, fc2, fc3 = st.columns([2,2,2])
                with fc1:
                    status = st.selectbox("Situação", list(db.FEEDING_CHECK_STATUS.keys()),
                        format_func=lambda s: db.FEEDING_CHECK_STATUS[s], key=f"st_{p['id']}")
                with fc2:
                    qtd_real = st.number_input(f"Qtd aplicada ({p['unit']})",
                        min_value=0.0, value=float(p["quantity"]), step=1.0,
                        key=f"q_{p['id']}")
                with fc3:
                    baixar = st.checkbox("Baixar do estoque",
                        value=bool(p.get("insumo_id")),
                        disabled=not p.get("insumo_id"),
                        help="Disponível se o item estiver vinculado a um insumo",
                        key=f"bx_{p['id']}")
                if st.form_submit_button("✅ Confirmar aplicação", type="primary",
                                         use_container_width=True):
                    db.add_feeding_check(
                        p["id"], lid, hoje.isoformat(), status,
                        actual_quantity=qtd_real,
                        operator=st.session_state.user["name"],
                        deduct_stock=baixar,
                        insumo_id=p.get("insumo_id"),
                        quantity_unit=p["unit"],
                    )
                    st.success(f"✅ {p['product_name']} confirmado para {lote_nome}")
                    st.rerun()


def _campo_animal():
    # ── Passo 1: Localizar animal ─────────────────────────────────────────────
    tab_dig, tab_qr, tab_kbd = st.tabs(["⌨️ Digitar ID","📷 Simular QR Code","🔢 Teclado Numérico"])

    with tab_dig:
        c1,c2=st.columns([3,1])
        with c1:
            typed=st.text_input("🏷️ ID do Animal",value=st.session_state.campo_id,
                placeholder="Ex: BR0001",key="campo_text").strip().upper()
        with c2:
            st.markdown("<br>",unsafe_allow_html=True)
            if st.button("🔍 Buscar",type="primary",use_container_width=True):
                st.session_state.campo_id=typed; st.rerun()

    with tab_qr:
        st.caption("Simula leitura de QR Code — em produção integre câmera ou leitor Bluetooth.")
        animals_all=db.get_all_animals()
        qcols=st.columns(4)
        for i,a in enumerate(animals_all[:12]):
            with qcols[i%4]:
                lbl=f"🐄 {a['id']}\n{a['breed'][:7]}"
                if st.button(lbl,key=f"qr_{a['id']}",use_container_width=True):
                    st.session_state.campo_id=a["id"]; st.rerun()

    with tab_kbd:
        st.caption("Teclado grande para uso ao sol / com luvas.")
        disp=st.session_state.keypad_value or "——"
        st.markdown(f'<div class="keypad-display">BR {disp}</div>',unsafe_allow_html=True)
        rows_kbd=[["7","8","9"],["4","5","6"],["1","2","3"],["C","0","✓"]]
        for row in rows_kbd:
            kc=st.columns(3)
            for i,k in enumerate(row):
                with kc[i]:
                    if st.button(k,key=f"kp_{k}_{row[0]}",use_container_width=True):
                        if k=="C":   st.session_state.keypad_value=""
                        elif k=="✓":
                            st.session_state.campo_id=f"BR{st.session_state.keypad_value.zfill(4)}"
                            st.session_state.keypad_value=""
                        else:
                            if len(st.session_state.keypad_value)<4:
                                st.session_state.keypad_value+=k
                        st.rerun()

    # ── Passo 2: Exibir animal ────────────────────────────────────────────────
    eid=st.session_state.campo_id
    if not eid: st.info("Selecione ou busque um animal para começar."); return

    animal=db.get_animal(eid)
    if not animal:
        st.error(f"Animal **{eid}** não encontrado."); return

    gmd=db.calculate_gmd(animal["id"])
    wd =db.get_withdrawal_end(animal["id"])
    gc ="#4ade80" if (gmd and gmd>0) else "#f87171" if (gmd and gmd<0) else "#94a3b8"
    cat=db.get_age_category(animal.get("birth_date"))
    idade=db.get_age_display(animal)

    carencia_html = (f'<div style="color:#fbbf24;font-size:.82rem;margin-top:.3rem">'
                     f'⚠️ Carência até {wd.isoformat()}</div>') if wd else ''
    sex_sym = "♂" if animal['sex']=='M' else "♀"
    gmd_txt = f'{gmd:+.3f} kg/dia' if gmd is not None else '— sem dados'
    st.markdown(
        f'<div class="card-green">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">'
        f'<div>'
        f'<div style="font-size:2rem;font-weight:900;color:#4ade80;line-height:1.1">🐄 {animal["id"]}</div>'
        f'<div style="color:#94a3b8;font-size:.92rem;margin-top:.2rem">'
        f'{animal["breed"]} · {sex_sym} · {cat} ({idade})<br>'
        f'Lote: <b style="color:#f1f5f9">{animal.get("lote_name") or "—"}</b> &nbsp;'
        f'{_status_badge(animal["status"])}'
        f'</div>{carencia_html}</div>'
        f'<div style="text-align:right">'
        f'<div style="font-size:2.4rem;font-weight:900;color:#f1f5f9;line-height:1">'
        f'{animal["current_weight"]:.1f}<span style="font-size:1rem;color:#64748b"> kg</span></div>'
        f'<div style="color:#fbbf24;font-size:.85rem">{_fmt_live(animal["current_weight"])}</div>'
        f'<div style="color:{gc};font-size:.88rem;font-weight:600">GMD: {gmd_txt}</div>'
        f'</div></div></div>',
        unsafe_allow_html=True)

    # ── Passo 3: Ação ─────────────────────────────────────────────────────────
    t1,t2,t3,t4=st.tabs(["⚖️ Pesagem","💉 Medicamento","🚚 Movimentação","📜 Histórico"])

    with t1:  # PESAGEM
        # Comparação com estimativa anterior pendente
        pend = db.get_last_estimate(animal["id"])
        if pend:
            met_lbl = db.WEIGH_METHODS.get(pend.get("method"),"estimativa")
            st.info(f"📋 Última pesagem foi **{met_lbl.lower()}**: "
                    f"**{pend['weight']:.1f} kg** em {pend['weigh_date']}. "
                    f"Se pesar agora na balança, o app mostra a diferença.")

        # Método fora do form para reagir à escolha
        metodo_peso = st.radio("Método da pesagem",
            list(db.WEIGH_METHODS.keys()),
            format_func=lambda m: db.WEIGH_METHODS[m],
            horizontal=True, key=f"peso_metodo_{animal['id']}")

        nw = float(animal["current_weight"])
        if metodo_peso == "medicao":
            st.caption("Informe as medidas do animal — o peso é estimado pela fórmula "
                       "de Schaeffer (perímetro torácico e comprimento corporal).")
            mm1, mm2 = st.columns(2)
            with mm1:
                pt = st.number_input("Perímetro torácico (cm)", min_value=0.0,
                    max_value=350.0, value=180.0, step=1.0, key=f"pt_{animal['id']}")
            with mm2:
                comp = st.number_input("Comprimento corporal (cm)", min_value=0.0,
                    max_value=350.0, value=150.0, step=1.0, key=f"comp_{animal['id']}")
            nw = db.estimate_weight_by_measurement(pt, comp)
            st.success(f"⚖️ Peso estimado por medição: **{nw:.1f} kg**")
            medida_nota = f"PT={pt:.0f}cm Comp={comp:.0f}cm"
        else:
            medida_nota = ""

        with st.form("f_peso",clear_on_submit=True):
            pc1,pc2=st.columns(2)
            with pc1:
                if metodo_peso == "medicao":
                    st.number_input("Peso estimado (kg)", value=float(nw),
                        disabled=True, key=f"pesomed_{animal['id']}")
                    nw_final = nw
                else:
                    lbl = "Peso (kg) — balança" if metodo_peso=="pesado" else "Peso estimado (kg)"
                    nw_final = st.number_input(lbl, min_value=1.0, max_value=2000.0,
                        value=float(animal["current_weight"]), step=0.5, format="%.1f")
            with pc2:
                wd_=st.date_input("Data",value=date.today())
            notes_p=st.text_area("Obs.",height=60,placeholder="Opcional",
                value=medida_nota)
            if st.form_submit_button("✅ Salvar Pesagem",type="primary",use_container_width=True):
                db.add_weighing(animal["id"], nw_final, wd_.strftime("%Y-%m-%d"),
                    st.session_state.user["name"], notes_p, method=metodo_peso)
                msg = f"✅ {nw_final:.1f} kg salvo ({db.WEIGH_METHODS[metodo_peso]})"
                # Comparação estimativa × pesagem real
                if metodo_peso == "pesado" and pend:
                    err = nw_final - pend["weight"]
                    pct = (err/pend["weight"]*100) if pend["weight"] else 0
                    msg += (f" · Diferença para a estimativa anterior "
                            f"({pend['weight']:.1f} kg): {err:+.1f} kg ({pct:+.1f}%)")
                st.success(msg)
                st.rerun()

    with t2:  # MEDICAMENTO
        insumos=[i for i in db.get_all_insumos() if i["category"] in ("medicamento","vacina")]
        with st.form("f_med",clear_on_submit=True):
            use_stock=st.toggle("Usar do Estoque",value=bool(insumos))
            if use_stock and insumos:
                ins_sel=st.selectbox("Insumo",insumos,format_func=lambda x:f"{x['name']} ({x['current_stock']:.0f} {x['unit']} em estoque)")
                med_name=ins_sel["name"]; unit_def=ins_sel["unit"]; insumo_id=ins_sel["id"]
            else:
                med_name=st.text_input("Medicamento *",placeholder="Ex: Ivermectina 1%")
                unit_def="ml"; insumo_id=None
                ins_sel=None
            mc1,mc2,mc3=st.columns(3)
            with mc1: dose=st.number_input("Dose",min_value=0.0,step=0.5,format="%.1f")
            with mc2: unit=st.selectbox("Unidade",["ml","mg","g","dose","comprimido"],
                            index=["ml","mg","g","dose","comprimido"].index(unit_def) if unit_def in ["ml","mg","g","dose","comprimido"] else 0)
            with mc3: route=st.selectbox("Via",ROUTES)
            wd_c=st.number_input("Carência (dias)",min_value=0,max_value=180,value=0,step=1)
            md_=st.date_input("Data Aplicação",value=date.today())
            notes_m=st.text_area("Obs.",height=60,placeholder="Opcional")
            if st.form_submit_button("✅ Salvar Medicamento",type="primary",use_container_width=True):
                if not med_name:
                    st.error("Informe o medicamento.")
                else:
                    db.add_medication(animal["id"],med_name,dose,unit,route,
                        int(wd_c),md_.strftime("%Y-%m-%d"),
                        st.session_state.user["name"],insumo_id,notes_m)
                    st.success(f"✅ {med_name} registrado!" + (f" Carência: {wd_c} dias" if wd_c else ""))
                    st.rerun()

    with t3:  # MOVIMENTAÇÃO
        lotes=db.get_all_lotes()
        with st.form("f_mov",clear_on_submit=True):
            dest=st.selectbox("Destino (Lote)",lotes,
                format_func=lambda x:f"{x['id']} — {x['name']} ({_plural(x['animal_count'],'animal','animais')} | {x['area_ha']} ha)")
            mv_date=st.date_input("Data",value=date.today())
            reason=st.selectbox("Motivo",["manejo","pesagem","tratamento","separação","venda","óbito"])
            notes_mv=st.text_area("Obs.",height=60,placeholder="Opcional")
            if st.form_submit_button("✅ Mover Animal",type="primary",use_container_width=True):
                if dest:
                    db.move_animal(animal["id"],dest["id"],mv_date.strftime("%Y-%m-%d"),
                        reason,st.session_state.user["name"],notes_mv)
                    st.success(f"✅ {animal['id']} movido para {dest['name']}")
                    st.rerun()

    with t4:  # HISTÓRICO
        h1,h2=st.columns(2)
        with h1:
            st.markdown("**⚖️ Pesagens**")
            ws=db.get_weighings(animal["id"])
            if len(ws)>=2:
                df_hw=pd.DataFrame(ws)[["weigh_date","weight"]].sort_values("weigh_date")
                df_hw.columns=["Data","Peso (kg)"]; df_hw["Data"]=pd.to_datetime(df_hw["Data"])
                fig_hw=px.line(df_hw,x="Data",y="Peso (kg)",markers=True,
                    color_discrete_sequence=["#4ade80"])
                fig_hw.update_layout(**PLOTLY,height=150,xaxis=dict(gridcolor="#1e293b"),
                    yaxis=dict(gridcolor="#1e293b"))
                st.plotly_chart(fig_hw,use_container_width=True)
            for w in ws[:5]:
                met = w.get("method") or "pesado"
                mbadge = {"pesado":'<span class="badge-green">balança</span>',
                          "estimado":'<span class="badge-yellow">estimado</span>',
                          "medicao":'<span class="badge-blue">medição</span>'}.get(met,"")
                st.markdown(f'<div class="hist-item"><b>{w["weight"]:.1f} kg</b> {mbadge}'
                    f'<span style="color:#64748b;font-size:.8rem;float:right">{w["weigh_date"]}</span><br>'
                    f'<span style="color:#94a3b8;font-size:.78rem">{w["operator"] or "—"}</span></div>',
                    unsafe_allow_html=True)
        with h2:
            st.markdown("**💉 Medicamentos**")
            for m in db.get_medications(animal["id"])[:5]:
                end_=datetime.strptime(m["med_date"],"%Y-%m-%d").date()+timedelta(days=m["withdrawal_days"] or 0)
                badge='<span class="badge-yellow">Carência</span>' if m["withdrawal_days"] and end_>=date.today() else ""
                st.markdown(f'<div class="hist-item" style="border-left-color:#22d3ee">'
                    f'<b>{m["medication_name"]}</b> {badge}<br>'
                    f'<span style="color:#64748b;font-size:.78rem">'
                    f'{_fmt_dose(m["dose"], m["unit"])} · {m["application_route"]} · {m["med_date"]}'
                    f'{"  ·  carência "+str(m["withdrawal_days"])+"d" if m["withdrawal_days"] else ""}'
                    f'</span></div>',unsafe_allow_html=True)
            st.markdown("**🚚 Movimentações**")
            for mv in db.get_movements(animal["id"])[:4]:
                st.markdown(f'<div class="hist-item" style="border-left-color:#a78bfa">'
                    f'<b>{mv.get("from_name") or "—"} → {mv.get("to_name","?")}</b><br>'
                    f'<span style="color:#64748b;font-size:.78rem">{mv["movement_date"]} · {mv["reason"]}</span>'
                    f'</div>',unsafe_allow_html=True)


def page_campo():
    st.markdown('<div class="page-title">📱 Modo Campo</div>', unsafe_allow_html=True)
    # Badge com nº de tratos pendentes na aba
    pend = db.get_pending_feedings()
    n_pend = sum(1 for p in pend if not p["done_this_period"])
    trato_label = f"🌾 Trato do Dia{' 🔴'+str(n_pend) if n_pend else ''}"
    tab_trato, tab_animal = st.tabs([trato_label, "🐄 Manejo do Animal"])
    with tab_trato:
        _campo_trato()
    with tab_animal:
        _campo_animal()

# ══════════════════════════════════════════════════════════════════════════════
# REBANHO
# ══════════════════════════════════════════════════════════════════════════════
def page_rebanho():
    st.markdown('<div class="page-title">📋 Rebanho</div>', unsafe_allow_html=True)
    animals_all=db.get_all_animals(status=None)
    if not animals_all:
        st.info("Nenhum animal cadastrado."); return

    f1,f2,f3,f4,f5=st.columns([2,1,1,1,1])
    with f1: busca=st.text_input("🔍 ID / Raça / Lote",placeholder="Ex: BR0003").upper()
    with f2:
        races=["Todas"]+sorted({a["breed"] for a in animals_all})
        fr=st.selectbox("Raça",races)
    with f3:
        fcat=st.selectbox("Categoria",["Todas"]+db.AGE_BANDS)
    with f4:
        statuses=["Todos","ativo","vendido","morto","carencia"]
        fs=st.selectbox("Status",statuses)
    with f5:
        lotes_opts=["Todos"]+sorted({a.get("lote_id","") or "—" for a in animals_all})
        fl=st.selectbox("Lote",lotes_opts)

    ul = _unit_label()
    rows=[]
    for a in animals_all:
        gmd=db.calculate_gmd(a["id"])
        wd =db.get_withdrawal_end(a["id"])
        rows.append({"ID":a["id"],"Raça":a["breed"],"Sexo":"♂" if a["sex"]=="M" else "♀",
            "Categoria":db.get_age_category(a.get("birth_date")),
            "Idade":db.get_age_display(a),
            "Lote":a.get("lote_id") or "—","Status":a["status"],
            "Peso Atual (kg)":a["current_weight"],
            f"Ganho ({ul})":_prod_weight(a["current_weight"]-a["entry_weight"]),
            "GMD (kg/dia)":gmd,
            "Carência até":wd.isoformat() if wd else "—",
            "Fornecedor":a.get("fornecedor_name") or "—"})
    df=pd.DataFrame(rows)

    if busca: df=df[df["ID"].str.contains(busca,na=False)|df["Raça"].str.contains(busca,case=False,na=False)|df["Lote"].str.contains(busca,na=False)]
    if fr!="Todas": df=df[df["Raça"]==fr]
    if fcat!="Todas": df=df[df["Categoria"]==fcat]
    if fs!="Todos": df=df[df["Status"]==fs]
    if fl!="Todos": df=df[df["Lote"]==fl]

    st.markdown(f"**{len(df)}** registro(s)")
    fmt_gain = "%.2f" if _use_arroba() else "%.1f"
    st.dataframe(df,use_container_width=True,hide_index=True,height=460,
        column_config={"Peso Atual (kg)":st.column_config.NumberColumn(format="%.1f"),
            f"Ganho ({ul})":st.column_config.NumberColumn(format=fmt_gain),
            "GMD (kg/dia)":st.column_config.NumberColumn(format="%.3f")})

    st.markdown("---")
    r1,r2=st.columns([2,1])
    with r1:
        sel=st.selectbox("Animal para detalhar",[a["id"] for a in animals_all])
    with r2:
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("📂 Abrir Ficha",type="primary",use_container_width=True):
            _go("animal",sel); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# FICHA DO ANIMAL  (Linha do Tempo)
# ══════════════════════════════════════════════════════════════════════════════
def page_animal():
    aid=st.session_state.animal_detail
    if not aid: st.warning("Nenhum animal selecionado."); return
    animal=db.get_animal(aid)
    if not animal: st.error(f"Animal {aid} não encontrado."); return

    if st.button("← Voltar",type="secondary"): _go("rebanho"); st.rerun()

    gmd =db.calculate_gmd(aid)
    ws  =db.get_weighings(aid)
    meds=db.get_medications(aid)
    movs=db.get_movements(aid)
    cost_total=db.get_total_cost(aid)
    yield_     =animal.get("carcass_yield") or 0.52
    arrobas    =db.kg_to_arrobas(animal["current_weight"], yield_)
    gain       =round(animal["current_weight"]-animal["entry_weight"],1)
    wd =db.get_withdrawal_end(aid)
    cat=db.get_age_category(animal.get("birth_date"))
    ul =_unit_label()

    st.markdown(f"## 🐄 Ficha — {animal['id']}  {_status_badge(animal['status'])}",
        unsafe_allow_html=True)

    m=st.columns(6)
    m[0].metric("Raça",       animal["breed"])
    m[1].metric("Categoria",  cat)
    m[2].metric("Peso Atual", f"{animal['current_weight']:.1f} kg")
    m[3].metric("Ganho",      f"{gain:+.1f} kg",
                help="Peso atual menos o peso de entrada")
    m[4].metric("@ Atuais",   f"{arrobas:.2f} @",
                help="Arrobas equivalentes ao peso vivo atual (rendimento de carcaça)")
    m[5].metric("GMD",        f"{gmd:.3f} kg/dia" if gmd else "N/A",
                delta=f"{gmd:.3f}" if gmd else None)

    src_label = db.AGE_SOURCES.get(animal.get("age_source","propriedade"),"—")
    doc_parts = []
    if animal.get("nf_number"):  doc_parts.append(f"NF: **{animal['nf_number']}**")
    if animal.get("gta_number"): doc_parts.append(f"GTA: **{animal['gta_number']}**")
    st.caption(f"📆 Origem da idade: **{src_label}**"
               + (f" · nascimento: {animal['birth_date']}" if animal.get("birth_date") else "")
               + (f"  |  📄 {' · '.join(doc_parts)}" if doc_parts else ""))

    # Editor de idade
    with st.expander("✏️ Corrigir / redefinir idade"):
        bd2, est2, src2, err2 = _age_inputs(date.today(), f"edit_{aid}_")
        if st.button("💾 Salvar nova idade", key=f"save_age_{aid}", type="primary"):
            if err2:
                st.error(f"❌ {err2}")
            else:
                db.update_animal_age(aid, bd2, est2, src2)
                st.success(f"✅ Idade atualizada · Categoria: **{db.get_age_category(bd2)}**")
                st.rerun()

    if wd:
        st.warning(f"⚠️ Animal em carência até **{wd.isoformat()}** "
                   f"({(wd-date.today()).days} dias restantes). Não pode ser abatido.")

    st.markdown("---")
    tl_peso,tl_med,tl_mov,tl_fin=st.tabs(["📈 Curva de Peso","💉 Sanidade","🚚 Movimentações","💰 Financeiro"])

    with tl_peso:
        if len(ws)>=2:
            import numpy as np
            df_w=pd.DataFrame(ws)[["weigh_date","weight"]].sort_values("weigh_date")
            df_w.columns=["Data","Peso (kg)"]; df_w["Data"]=pd.to_datetime(df_w["Data"])
            x_num=(df_w["Data"]-df_w["Data"].min()).dt.days
            coef=np.polyfit(x_num,df_w["Peso (kg)"],1)
            fig=go.Figure()
            fig.add_trace(go.Scatter(x=df_w["Data"],y=np.polyval(coef,x_num),
                mode="lines",name="Tendência",line=dict(dash="dot",color="#fbbf24",width=2),hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=df_w["Data"],y=df_w["Peso (kg)"],
                mode="lines+markers",name="Pesagens",
                line=dict(color="#4ade80",width=2.5),
                marker=dict(size=10,color="#4ade80",line=dict(width=2,color="#0f172a")),
                hovertemplate="%{x|%d/%m/%Y}<br><b>%{y:.1f} kg</b><extra></extra>"))
            fig.update_layout(**PLOTLY,height=300,
                xaxis=dict(gridcolor="#1e293b",title="Data"),
                yaxis=dict(gridcolor="#1e293b",title="Peso (kg)"),
                legend=dict(orientation="h",y=1.08))
            st.plotly_chart(fig,use_container_width=True)
        else:
            st.info("São necessárias ao menos 2 pesagens para exibir o gráfico.")
        st.subheader("Tabela de Pesagens")
        if ws:
            df_wt=pd.DataFrame(ws)[["weigh_date","weight","method","lote_id","operator","notes"]].copy()
            df_wt["method"]=df_wt["method"].fillna("pesado").map(
                lambda m: db.WEIGH_METHODS.get(m,m))
            df_wt.columns=["Data","Peso (kg)","Método","Lote","Operador","Obs"]
            st.dataframe(df_wt,use_container_width=True,hide_index=True,
                column_config={"Peso (kg)":st.column_config.NumberColumn(format="%.1f")})

    with tl_med:
        if meds:
            for m_ in meds:
                end_=datetime.strptime(m_["med_date"],"%Y-%m-%d").date()+timedelta(days=m_["withdrawal_days"] or 0)
                active=m_["withdrawal_days"] and end_>=date.today()
                bc="border-left-color:#f87171" if active else "border-left-color:#22d3ee"
                st.markdown(f'<div class="hist-item" style="{bc}">'
                    f'<b style="font-size:1rem">{m_["medication_name"]}</b>'
                    f'{"  "+_gmd_badge(None).replace("badge-gray","badge-yellow").replace("N/D","Carência ativa") if active else ""}<br>'
                    f'<span style="color:#94a3b8;font-size:.82rem">'
                    f'{m_["med_date"]} · {_fmt_dose(m_["dose"], m_["unit"])} · {m_["application_route"]}'
                    f'{"  ·  carência "+str(m_["withdrawal_days"])+" dias (até "+end_.isoformat()+")" if m_["withdrawal_days"] else ""}'
                    f'{"  ·  por: "+m_["applied_by"] if m_["applied_by"] else ""}'
                    f'</span></div>',unsafe_allow_html=True)
        else:
            st.info("Nenhum medicamento registrado.")

    with tl_mov:
        if movs:
            for mv in movs:
                st.markdown(f'<div class="hist-item" style="border-left-color:#a78bfa">'
                    f'<b>{mv.get("from_name") or "Entrada"} → {mv.get("to_name","?")}</b><br>'
                    f'<span style="color:#94a3b8;font-size:.82rem">'
                    f'{mv["movement_date"]} · {mv["reason"]} · {mv.get("operator") or "—"}'
                    f'</span></div>',unsafe_allow_html=True)
        else:
            st.info("Nenhuma movimentação registrada.")

    with tl_fin:
        costs=db.get_animal_costs(aid)
        prod_gain   = _prod_weight(gain, yield_) if gain > 0 else 0
        cpu_val     = _cost_per_unit(cost_total, animal["current_weight"], yield_)
        cpu_gain = round(cost_total / prod_gain, 2) if prod_gain > 0 else 0
        cp1,cp2,cp3 = st.columns(3)
        cp1.metric("Custo Total",          f"R$ {cost_total:,.2f}",
                   help="Compra + insumos + custeio operacional")
        cp2.metric(_cost_per_unit_label(), f"R$ {cpu_val:,.2f}" if cpu_val else "—",
                   help="Custo total ÷ peso vivo atual")
        cp3.metric(f"Custo da Produção (R$/{ul})",
                   f"R$ {cpu_gain:,.2f}" if cpu_gain else "—",
                   help=f"Custo total ÷ {ul} ganhos (produzidos) desde a entrada")
        if costs:
            df_c=pd.DataFrame(costs)[["cost_date","cost_type","description","amount"]]
            df_c.columns=["Data","Tipo","Descrição","Valor (R$)"]
            st.dataframe(df_c,use_container_width=True,hide_index=True,
                column_config={"Valor (R$)":st.column_config.NumberColumn(format="R$ %.2f")})
        # Adicionar custo
        with st.expander("➕ Adicionar Custo"):
            with st.form("f_cost",clear_on_submit=True):
                cc1,cc2,cc3=st.columns(3)
                with cc1: ct=st.selectbox("Tipo",COST_TYPES)
                with cc2: val=st.number_input("Valor (R$)",min_value=0.0,step=0.01,format="%.2f")
                with cc3: cd=st.date_input("Data",value=date.today())
                desc=st.text_input("Descrição")
                if st.form_submit_button("Salvar",type="primary",use_container_width=True):
                    db.add_animal_cost(aid,ct,desc,val,cd.strftime("%Y-%m-%d"))
                    st.success("Custo registrado!"); st.rerun()

    st.markdown("---")
    qa1,qa2,qa3=st.columns(3)
    with qa1:
        if st.button("📱 Abrir no Campo",use_container_width=True):
            st.session_state.campo_id=aid; _go("campo"); st.rerun()
    with qa2:
        if st.button("📊 Dashboard",use_container_width=True):
            _go("dashboard"); st.rerun()
    with qa3:
        if st.button("📋 Rebanho",use_container_width=True):
            _go("rebanho"); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# LOTES / PASTAGEM
# ══════════════════════════════════════════════════════════════════════════════
def page_lotes():
    st.markdown('<div class="page-title">🌿 Lotes / Pastagem</div>', unsafe_allow_html=True)
    lotes=db.get_all_lotes()

    lt1,lt2=st.tabs(["📋 Visão Geral","➕ Novo Lote"])

    with lt1:
        for l in lotes:
            ua  = l["total_ua"] or 0
            cap = l["capacity_ua"] or 0
            has_cap = cap > 0
            pct = min(ua/cap*100, 100) if has_cap else 0
            bar_col="#4ade80" if pct<75 else "#fbbf24" if pct<95 else "#f87171"
            status_badge={"ativo":'<span class="badge-green">Ativo</span>',
                "descanso":'<span class="badge-yellow">Descanso</span>',
                "reforma":'<span class="badge-red">Reforma</span>'}.get(l["status"],'')
            dias_ocup=""
            if l.get("last_entry_date") and l.get("last_exit_date"):
                d0=datetime.strptime(l["last_entry_date"],"%Y-%m-%d").date()
                d1=datetime.strptime(l["last_exit_date"],"%Y-%m-%d").date()
                dias_ocup=f"Última ocupação: {abs((d1-d0).days)} dias"
            elif l.get("last_entry_date"):
                d0=datetime.strptime(l["last_entry_date"],"%Y-%m-%d").date()
                dias_ocup=f"Em ocupação há {(date.today()-d0).days} dias"

            # Ocupação: só mostra % quando há capacidade definida (> 0)
            if has_cap:
                ocup_txt = f"{ua:.1f} / {cap:.0f} UA ({pct:.0f}%)"
                cap_txt  = f"Cap. {cap:.0f} UA"
                barra = (f'<div style="background:#0f172a;border-radius:6px;height:8px;margin-top:.6rem;overflow:hidden">'
                         f'<div style="background:{bar_col};width:{pct:.0f}%;height:100%;border-radius:6px;transition:width .4s"></div></div>')
            else:
                ocup_txt = f"{ua:.1f} UA · sem capacidade definida"
                cap_txt  = "Sem capacidade de pasto (curral/manejo)"
                barra = ""

            st.markdown(f"""
            <div class="card">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap">
                <div>
                  <b style="font-size:1.1rem;color:#f1f5f9">{l['id']} — {l['name']}</b>&nbsp;{status_badge}
                  <div style="color:#94a3b8;font-size:.82rem;margin-top:.2rem">
                    {l['area_ha']} ha · {cap_txt} · {dias_ocup}
                  </div>
                </div>
                <div style="text-align:right">
                  <div style="font-size:1.5rem;font-weight:800;color:#4ade80">{_plural(l['animal_count'],'animal','animais')}</div>
                  <div style="color:#94a3b8;font-size:.82rem">{ocup_txt}</div>
                </div>
              </div>
              {barra}
            </div>""",unsafe_allow_html=True)

            # Lista de animais do lote
            with st.expander(f"Ver animais do {l['name']}"):
                anilist=db.get_all_animals(lote_id=l["id"])
                if anilist:
                    rows_l=[{"ID":a["id"],"Raça":a["breed"],"Sexo":"♂" if a["sex"]=="M" else "♀",
                        "Peso (kg)":a["current_weight"],"GMD":db.calculate_gmd(a["id"])} for a in anilist]
                    st.dataframe(pd.DataFrame(rows_l),use_container_width=True,hide_index=True,
                        column_config={"Peso (kg)":st.column_config.NumberColumn(format="%.1f"),
                            "GMD":st.column_config.NumberColumn(format="%.3f")})
                else:
                    st.caption("Nenhum animal neste lote.")

        # Gráfico UA por Lote
        if lotes:
            df_lot=pd.DataFrame([{"Lote":f"{l['id']}·{l['name'][:8]}",
                "UA Atual":l["total_ua"] or 0,"Cap. UA":l["capacity_ua"]} for l in lotes])
            fig_l=go.Figure()
            fig_l.add_bar(x=df_lot["Lote"],y=df_lot["Cap. UA"],name="Capacidade",
                marker_color="#334155")
            fig_l.add_bar(x=df_lot["Lote"],y=df_lot["UA Atual"],name="UA Atual",
                marker_color="#4ade80")
            fig_l.update_layout(**PLOTLY,height=280,barmode="overlay",
                legend=dict(orientation="h",y=1.1),
                xaxis=dict(gridcolor="#1e293b"),yaxis=dict(gridcolor="#1e293b",title="UA"))
            st.plotly_chart(fig_l,use_container_width=True)

    with lt2:
        with st.form("f_lote",clear_on_submit=True):
            nl1,nl2=st.columns(2)
            with nl1:
                lid=st.text_input("ID do Lote *",placeholder="Ex: P06").strip().upper()
                name=st.text_input("Nome *",placeholder="Ex: Piquete Sul 2")
            with nl2:
                area=st.number_input("Área (ha)",min_value=0.0,step=0.5,format="%.1f")
                cap=st.number_input("Capacidade (UA)",min_value=0.0,step=1.0,format="%.0f")
            notes_l=st.text_area("Obs.",height=60)
            if st.form_submit_button("✅ Criar Lote",type="primary",use_container_width=True):
                if not lid or not name:
                    st.error("ID e Nome são obrigatórios.")
                elif db.get_lote(lid):
                    st.error(f"Lote {lid} já existe.")
                else:
                    db.add_lote(lid,name,area,cap,notes_l)
                    st.success(f"✅ Lote {lid} criado!"); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# FINANCEIRO
# ══════════════════════════════════════════════════════════════════════════════
def page_financeiro():
    st.markdown('<div class="page-title">💰 Financeiro & Mercado</div>', unsafe_allow_html=True)
    animals=db.get_all_animals()
    if not animals: st.info("Sem animais ativos."); return

    ft1,ft_fix,ft2,ft3,ft4=st.tabs(["📊 Custos por Animal","🏢 Custos Fixos","💵 Simulador de Venda","⚖️ Ponto de Equilíbrio","🏆 Desempenho por Origem"])

    with ft1:  # CUSTOS
        ul   = _unit_label()
        rows_f=[]
        for a in animals:
            tc    = db.get_total_cost(a["id"])
            yield_= a.get("carcass_yield") or 0.52
            prod  = _live_weight(a["current_weight"], yield_)
            gain  = a["current_weight"] - a["entry_weight"]
            prod_g= _prod_weight(gain, yield_) if gain > 0 else 0
            cpu   = round(tc/prod, 2) if prod else 0
            cpu_g = round(tc/prod_g, 2) if prod_g > 0 else 0
            rows_f.append({"ID":a["id"],"Raça":a["breed"],
                "Peso (kg)":a["current_weight"],
                f"Prod. ({ul})":prod,
                "Custo Total (R$)":tc,
                _cost_per_unit_label():cpu,
                f"Ganho ({ul})":prod_g,
                f"Custo Produção/{ul}":cpu_g})
        df_f=pd.DataFrame(rows_f)

        tot_tc  = df_f["Custo Total (R$)"].sum()
        tot_prod= df_f[f"Prod. ({ul})"].sum()
        tot_gnh = df_f[f"Ganho ({ul})"].sum()
        kk=st.columns(4)
        kk[0].metric("Custo Total do Rebanho", f"R$ {tot_tc:,.2f}")
        kk[1].metric(f"Total {ul} no Rebanho", f"{tot_prod:.1f} {ul}")
        kk[2].metric(f"Total {ul} Ganhos",     f"{tot_gnh:.1f} {ul}")
        kk[3].metric(_cost_per_unit_label(),    f"R$ {tot_tc/tot_prod:.2f}" if tot_prod else "—")

        prod_col = f"Prod. ({ul})"
        cpu_col  = _cost_per_unit_label()
        fmt_prod = "%.2f" if _use_arroba() else "%.1f"
        st.dataframe(df_f,use_container_width=True,hide_index=True,
            column_config={
                "Peso (kg)":st.column_config.NumberColumn(format="%.1f"),
                prod_col:st.column_config.NumberColumn(format=fmt_prod),
                "Custo Total (R$)":st.column_config.NumberColumn(format="R$ %.2f"),
                cpu_col:st.column_config.NumberColumn(format="R$ %.2f"),
                f"Ganho ({ul})":st.column_config.NumberColumn(format=fmt_prod),
                f"Custo Produção/{ul}":st.column_config.NumberColumn(format="R$ %.2f")})

        fig_c=px.scatter(df_f,x=prod_col,y="Custo Total (R$)",
            color=cpu_col,text="ID",
            color_continuous_scale=["#4ade80","#fbbf24","#f87171"],
            labels={prod_col:f"Produção ({ul})","Custo Total (R$)":"Custo Total (R$)"})
        fig_c.update_traces(textposition="top center",marker=dict(size=12))
        fig_c.update_layout(**PLOTLY,height=320,coloraxis_colorbar=dict(title=f"R$/{ul}"))
        st.plotly_chart(fig_c,use_container_width=True)

    with ft_fix:  # CUSTOS FIXOS
        st.subheader("🏢 Custos Fixos da Fazenda")
        st.caption("Aluguel de pastagem, salários, bonificações, impostos, taxas e outros "
                   "custos que não são atribuídos a um animal específico.")

        # Filtro por período
        pc1,pc2=st.columns(2)
        with pc1:
            start_f=st.date_input("De", value=date(date.today().year,1,1), key="fix_start")
        with pc2:
            end_f=st.date_input("Até", value=date.today(), key="fix_end")
        s_iso, e_iso = start_f.isoformat(), end_f.isoformat()

        fixed=db.get_fixed_costs(s_iso, e_iso)
        total_fix=db.get_total_fixed_costs(s_iso, e_iso)
        by_cat=db.get_fixed_costs_by_category(s_iso, e_iso)

        mk=st.columns(3)
        mk[0].metric("Total de Custos Fixos", f"R$ {total_fix:,.2f}")
        mk[1].metric("Lançamentos", len(fixed))
        n_animals=len(animals)
        mk[2].metric("Rateio por Animal Ativo",
                     f"R$ {total_fix/n_animals:,.2f}" if n_animals else "—",
                     help="Custo fixo dividido igualmente pelos animais ativos")

        # Formulário de lançamento
        with st.expander("➕ Lançar Custo Fixo", expanded=not fixed):
            with st.form("f_fixed",clear_on_submit=True):
                fx1,fx2=st.columns(2)
                with fx1:
                    fx_cat=st.selectbox("Categoria *", db.FIXED_COST_CATEGORIES)
                    fx_amount=st.number_input("Valor (R$) *", min_value=0.0, step=50.0, format="%.2f")
                with fx2:
                    fx_date=st.date_input("Data *", value=date.today())
                    fx_recur=st.checkbox("Custo recorrente (mensal)")
                fx_desc=st.text_input("Descrição", placeholder="Ex: Aluguel piquete Norte / Salário João")
                if st.form_submit_button("✅ Lançar Custo Fixo", type="primary", use_container_width=True):
                    if fx_amount<=0:
                        st.error("O valor deve ser maior que zero.")
                    else:
                        db.add_fixed_cost(fx_cat, fx_desc, fx_amount,
                                          fx_date.strftime("%Y-%m-%d"), fx_recur, "")
                        st.success(f"✅ {fx_cat}: R$ {fx_amount:,.2f} lançado!")
                        st.rerun()

        if fixed:
            # Gráfico por categoria
            cga,cgb=st.columns([2,3])
            with cga:
                df_cat=pd.DataFrame(by_cat)
                df_cat.columns=["Categoria","Total"]
                fig_fx=px.pie(df_cat,names="Categoria",values="Total",hole=0.45,
                    color_discrete_sequence=["#4ade80","#22d3ee","#a78bfa","#f472b6","#fb923c","#facc15","#34d399","#f87171"])
                fig_fx.update_layout(**_layout(height=260,margin=dict(l=0,r=0,t=10,b=10),
                    legend=dict(orientation="h",yanchor="bottom",y=-0.25)))
                fig_fx.update_traces(textposition="inside",textinfo="percent")
                st.plotly_chart(fig_fx,use_container_width=True)
            with cgb:
                df_fx=pd.DataFrame(fixed)[["cost_date","category","description","amount","recurring"]].copy()
                df_fx["recurring"]=df_fx["recurring"].map({1:"Mensal",0:"Único"})
                df_fx.columns=["Data","Categoria","Descrição","Valor (R$)","Tipo"]
                st.dataframe(df_fx,use_container_width=True,hide_index=True,height=260,
                    column_config={"Valor (R$)":st.column_config.NumberColumn(format="R$ %.2f")})

            # Excluir lançamento
            with st.expander("🗑️ Excluir um lançamento"):
                opt={f"#{f['id']} · {f['cost_date']} · {f['category']} · R$ {f['amount']:,.2f}":f["id"] for f in fixed}
                sel_del=st.selectbox("Lançamento", list(opt.keys()), key="del_fix")
                if st.button("Excluir", type="secondary"):
                    db.delete_fixed_cost(opt[sel_del])
                    st.success("Lançamento excluído."); st.rerun()
        else:
            st.info("Nenhum custo fixo lançado no período selecionado.")

    with ft2:  # SIMULADOR
        ul = _unit_label()
        arroba_mode = _use_arroba()
        st.subheader("💵 Simulador de Venda")
        st.caption("Projeção de receita e lucro. Em kg, o valor é da arroba do **boi vivo** "
                   "(peso vivo, sem desconto de carcaça).")

        sc1,sc2=st.columns(2)
        with sc1:
            price_label = "Cotação por @ (R$)" if arroba_mode else "Cotação por kg de boi vivo (R$)"
            default_price = DEFAULT_PRICE_ARROBA if arroba_mode else DEFAULT_PRICE_KG
            cotacao=st.number_input(price_label, min_value=0.01, max_value=5000.0,
                value=default_price, step=(5.0 if arroba_mode else 0.10), format="%.2f")
            # Rendimento de carcaça só faz sentido no modo @
            if arroba_mode:
                rendimento=st.slider("Rendimento de Carcaça (%)",min_value=40,max_value=65,value=52)
            else:
                rendimento=52  # ignorado no modo kg (peso vivo)
            incluir_fixos=st.checkbox("Incluir rateio de custos fixos no cálculo",
                help="Divide os custos fixos do ano igualmente entre os animais ativos")
        with sc2:
            sub = ("Rendimento: "+str(rendimento)+"%") if arroba_mode else "Peso vivo (sem desconto de carcaça)"
            st.markdown(
                f'<div class="card">'
                f'<div style="color:#94a3b8;font-size:.85rem">Cotação atual</div>'
                f'<div style="font-size:2rem;font-weight:800;color:#4ade80">R$ {cotacao:.2f}/{ul}</div>'
                f'<div style="color:#94a3b8;font-size:.85rem;margin-top:.5rem">{sub}</div>'
                f'</div>', unsafe_allow_html=True)

        # Rateio de custos fixos (ano corrente) por animal ativo
        rateio_fixo = 0.0
        if incluir_fixos and animals:
            total_fix_ano = db.get_total_fixed_costs(
                date(date.today().year,1,1).isoformat(), date.today().isoformat())
            rateio_fixo = total_fix_ano / len(animals)
            st.info(f"Rateio de custos fixos: **R$ {rateio_fixo:,.2f}** por animal "
                    f"(total R$ {total_fix_ano:,.2f} ÷ {len(animals)} animais ativos).")

        sim_rows=[]
        for a in animals:
            tc     = db.get_total_cost(a["id"]) + rateio_fixo
            # Modo kg: peso vivo direto. Modo @: aplica rendimento de carcaça.
            prod   = _live_weight(a["current_weight"], rendimento/100)
            receita= round(prod * cotacao, 2)
            lucro  = round(receita - tc, 2)
            sim_rows.append({"ID":a["id"],"Peso (kg)":a["current_weight"],
                f"Venda ({ul})":prod,"Receita (R$)":receita,
                "Custo Total (R$)":round(tc,2),"Lucro (R$)":lucro,
                "Margem (%)":round(lucro/receita*100,1) if receita else 0})
        df_sim=pd.DataFrame(sim_rows)
        tot_rec=df_sim["Receita (R$)"].sum(); tot_luc=df_sim["Lucro (R$)"].sum()
        tot_cost=df_sim["Custo Total (R$)"].sum()
        margem_media=df_sim["Margem (%)"].mean()

        sk=st.columns(4)
        sk[0].metric("Receita Total", f"R$ {tot_rec:,.2f}")
        sk[1].metric("Custo Total",   f"R$ {tot_cost:,.2f}")
        # Delta com sinal explícito: '+' fica verde/↑, '-' fica vermelho/↓
        sk[2].metric("Lucro / Prejuízo Total", f"R$ {tot_luc:,.2f}",
            delta=f"{tot_luc:+,.2f}", delta_color="normal")
        sk[3].metric("Margem Média", f"{margem_media:.1f}%",
            delta=f"{margem_media:+.1f}%", delta_color="normal")

        if tot_luc < 0:
            st.error(f"⚠️ Projeção de **PREJUÍZO** de R$ {abs(tot_luc):,.2f} nesta cotação. "
                     f"Reveja a cotação, os custos ou o ponto de venda.")

        fmt_prod = "%.2f" if arroba_mode else "%.1f"
        st.dataframe(df_sim,use_container_width=True,hide_index=True,
            column_config={
                "Peso (kg)":st.column_config.NumberColumn(format="%.1f"),
                f"Venda ({ul})":st.column_config.NumberColumn(format=fmt_prod),
                "Receita (R$)":st.column_config.NumberColumn(format="R$ %.2f"),
                "Custo Total (R$)":st.column_config.NumberColumn(format="R$ %.2f"),
                "Lucro (R$)":st.column_config.NumberColumn(format="R$ %.2f")})

    with ft3:  # BREAKEVEN
        ul = _unit_label()
        st.subheader("⚖️ Ponto de Equilíbrio (Breakeven)")
        be_rows=[]
        for a in animals:
            tc   = db.get_total_cost(a["id"])
            prod = _live_weight(a["current_weight"], a.get("carcass_yield") or 0.52)
            be   = round(tc/prod, 2) if prod else 0
            be_rows.append({"ID":a["id"],"Raça":a["breed"],
                "Peso (kg)":a["current_weight"],
                f"Prod. ({ul})":prod,
                "Custo Total (R$)":tc,
                _breakeven_label():be})
        df_be    = pd.DataFrame(be_rows)
        be_col   = _breakeven_label()
        prod_col = f"Prod. ({ul})"
        fmt_prod = "%.2f" if _use_arroba() else "%.1f"
        fig_be=px.bar(df_be.sort_values(be_col),
            x="ID",y=be_col,color=be_col,
            color_continuous_scale=["#4ade80","#fbbf24","#f87171"],
            labels={be_col:f"R$ mínimo por {ul}"})
        fig_be.update_layout(**PLOTLY,height=300,coloraxis_showscale=False,
            xaxis=dict(gridcolor="#1e293b"),yaxis=dict(gridcolor="#1e293b"))
        st.plotly_chart(fig_be,use_container_width=True)
        st.dataframe(df_be,use_container_width=True,hide_index=True,
            column_config={"Peso (kg)":st.column_config.NumberColumn(format="%.1f"),
                prod_col:st.column_config.NumberColumn(format=fmt_prod),
                "Custo Total (R$)":st.column_config.NumberColumn(format="R$ %.2f"),
                be_col:st.column_config.NumberColumn(format="R$ %.2f")})

    with ft4:  # DESEMPENHO POR ORIGEM
        st.subheader("🏆 Desempenho por Fornecedor / Origem")
        perf=db.get_fornecedor_performance()
        if perf:
            df_p=pd.DataFrame(perf)
            fig_p=px.bar(df_p,x="Fornecedor",y="GMD Médio",color="GMD Médio",
                color_continuous_scale=["#f87171","#fbbf24","#4ade80"],
                text="GMD Médio",labels={"GMD Médio":"GMD Médio (kg/dia)"})
            fig_p.update_traces(texttemplate="%{text:.3f}",textposition="outside")
            fig_p.update_layout(**PLOTLY,height=300,coloraxis_showscale=False,
                xaxis=dict(gridcolor="#1e293b"),yaxis=dict(gridcolor="#1e293b"))
            st.plotly_chart(fig_p,use_container_width=True)
            st.dataframe(df_p,use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# ESTOQUE DE INSUMOS
# ══════════════════════════════════════════════════════════════════════════════
def page_estoque():
    st.markdown('<div class="page-title">📦 Estoque de Insumos</div>', unsafe_allow_html=True)
    insumos=db.get_all_insumos()
    low=db.check_low_stock()
    if low:
        st.warning(f"⚠️ **{_plural(len(low),'insumo','insumos')} abaixo do estoque mínimo:** " +
            ", ".join(f"**{i['name']}** ({_num_br(i['current_stock'],0)} {i['unit']})" for i in low))

    et1,et2,et3=st.tabs(["📋 Inventário","📥 Entrada de Estoque","➕ Novo Insumo"])

    CAT_LABELS={"racao":"Ração","trato":"Trato (volumoso)","medicamento":"Medicamento",
                "vacina":"Vacina","mineral":"Mineral","outro":"Outro"}
    with et1:
        cats_present=sorted({i["category"] for i in insumos})
        fcat_ins=st.selectbox("Filtrar por categoria",
            ["Todas"]+cats_present,
            format_func=lambda c:c if c=="Todas" else CAT_LABELS.get(c,c))
        rows_i=[]
        for i in insumos:
            if fcat_ins!="Todas" and i["category"]!=fcat_ins: continue
            pct=i["current_stock"]/i["min_stock"]*100 if i["min_stock"] else 100
            rows_i.append({"Insumo":i["name"],"Categoria":CAT_LABELS.get(i["category"],i["category"]),
                "Estoque":i["current_stock"],"Unidade":i["unit"],
                "Mínimo":i["min_stock"],
                "Status":"🔴 Crítico" if pct<50 else "🟡 Baixo" if pct<100 else "🟢 OK",
                "Custo/Un (R$)":i["cost_per_unit"],
                "Valor Total (R$)":round(i["current_stock"]*i["cost_per_unit"],2)})
        df_i=pd.DataFrame(rows_i)
        st.dataframe(df_i,use_container_width=True,hide_index=True,
            column_config={"Estoque":st.column_config.NumberColumn(format="%.1f"),
                "Custo/Un (R$)":st.column_config.NumberColumn(format="R$ %.2f"),
                "Valor Total (R$)":st.column_config.NumberColumn(format="R$ %.2f")})
        tot_val=sum(r["Valor Total (R$)"] for r in rows_i)
        st.metric("Valor Total do Estoque",f"R$ {tot_val:,.2f}")

        # Gráfico % do mínimo
        df_bar=pd.DataFrame([{"Insumo":r["Insumo"],
            "% do Mínimo":min(r["Estoque"]/max(r["Mínimo"],0.01)*100,200)} for r in rows_i])
        fig_e=px.bar(df_bar.sort_values("% do Mínimo"),x="% do Mínimo",y="Insumo",
            orientation="h",color="% do Mínimo",
            color_continuous_scale=["#f87171","#fbbf24","#4ade80"],range_color=[0,200])
        fig_e.add_vline(x=100,line_dash="dash",line_color="#fbbf24",
            annotation_text="Mínimo",annotation_position="top")
        fig_e.update_layout(**PLOTLY,height=280,coloraxis_showscale=False,
            xaxis=dict(gridcolor="#1e293b",title="% do Estoque Mínimo"),
            yaxis=dict(gridcolor="#1e293b",title=""))
        st.plotly_chart(fig_e,use_container_width=True)

    with et2:
        with st.form("f_entrada",clear_on_submit=True):
            ins=st.selectbox("Insumo",insumos,format_func=lambda x:f"{x['name']} ({x['current_stock']:.1f} {x['unit']})")
            ec1,ec2=st.columns(2)
            with ec1: qty=st.number_input("Quantidade",min_value=0.01,step=1.0,format="%.2f")
            with ec2: cpu=st.number_input("Custo por Unidade (R$)",min_value=0.0,step=0.01,format="%.2f",
                value=float(ins["cost_per_unit"]) if ins else 0.0)
            if st.form_submit_button("✅ Registrar Entrada",type="primary",use_container_width=True):
                db.add_insumo_entry(ins["id"],qty,cpu,st.session_state.user["name"])
                st.success(f"✅ +{qty:.1f} {ins['unit']} de {ins['name']}"); st.rerun()

    with et3:
        with st.form("f_new_ins",clear_on_submit=True):
            ni1,ni2=st.columns(2)
            with ni1:
                ni_name=st.text_input("Nome *",placeholder="Ex: Silagem de milho / Massa de soja")
                ni_cat=st.selectbox("Categoria",
                    ["medicamento","vacina","racao","trato","mineral","outro"],
                    format_func=lambda c:{"racao":"ração","trato":"trato (volumoso)"}.get(c,c),
                    help="'trato' = volumosos como silagem, massa de soja, bagaço de laranja")
            with ni2:
                ni_unit=st.selectbox("Unidade",
                    ["kg","ton","saco","ml","mg","g","dose","litro","comprimido"],
                    format_func=lambda u:{"ton":"tonelada (ton)"}.get(u,u))
                ni_stk=st.number_input("Estoque Inicial",min_value=0.0,step=1.0,format="%.1f")
            ni_min=st.number_input("Estoque Mínimo (alerta)",min_value=0.0,step=1.0,format="%.1f")
            ni_cpu=st.number_input("Custo por Unidade (R$)",min_value=0.0,step=0.01,format="%.2f")
            if st.form_submit_button("✅ Criar Insumo",type="primary",use_container_width=True):
                if ni_name:
                    db.add_new_insumo(ni_name,ni_cat,ni_unit,ni_stk,ni_min,ni_cpu)
                    st.success(f"✅ Insumo {ni_name} criado!"); st.rerun()
                else:
                    st.error("Nome é obrigatório.")

# ══════════════════════════════════════════════════════════════════════════════
# ALERTAS
# ══════════════════════════════════════════════════════════════════════════════
def page_alertas():
    st.markdown('<div class="page-title">🔔 Alertas Ativos</div>', unsafe_allow_html=True)
    alerts=db.get_alert_animals()
    low   =db.check_low_stock()

    # Sumidos
    st.subheader(f"🔴 Animais Sumidos ({len(alerts['sumidos'])})")
    st.caption("Sem pesagem registrada há mais de 30 dias.")
    if alerts["sumidos"]:
        df_sum=pd.DataFrame([{"ID":a["id"],"Raça":a["breed"],"Lote":a.get("lote_id") or "—",
            "Último Peso (kg)":a["current_weight"],
            "Dias sem Pesagem":a["days_since_weighing"]} for a in alerts["sumidos"]])
        st.dataframe(df_sum,use_container_width=True,hide_index=True)
        for a in alerts["sumidos"]:
            c1,c2=st.columns([3,1])
            with c1:
                st.markdown(f'<div class="card-red">🔴 <b>{a["id"]}</b> — {a["breed"]} — '
                    f'Sem pesagem há <b>{a["days_since_weighing"]} dias</b></div>',
                    unsafe_allow_html=True)
            with c2:
                if st.button("📱 Ir para Campo",key=f"alr_sum_{a['id']}",use_container_width=True):
                    st.session_state.campo_id=a["id"]; _go("campo"); st.rerun()
    else:
        st.success("✅ Nenhum animal sumido.")

    st.markdown("---")

    # Carência
    st.subheader(f"🟡 Em Período de Carência ({len(alerts['carencia'])})")
    if alerts["carencia"]:
        for a in alerts["carencia"]:
            st.markdown(f'<div class="card-yellow">🟡 <b>{a["id"]}</b> — {a["breed"]} — '
                f'Carência até <b>{a["withdrawal_end"]}</b> '
                f'(<b>{a["days_remaining"]} dias restantes</b>)</div>',
                unsafe_allow_html=True)
    else:
        st.success("✅ Nenhum animal em carência.")

    st.markdown("---")

    # Prontos para abate
    st.subheader(f"🟢 Prontos para Abate ({len(alerts['prontos'])})")
    st.caption("Atingiram o peso-alvo e estão livres de carência.")
    if alerts["prontos"]:
        df_pro=pd.DataFrame([{"ID":a["id"],"Raça":a["breed"],
            "Peso Atual (kg)":a["current_weight"],"Peso-Alvo (kg)":a.get("target_weight") or 500,
            "@ Atuais":a["arrobas"]} for a in alerts["prontos"]])
        st.dataframe(df_pro,use_container_width=True,hide_index=True,
            column_config={"Peso Atual (kg)":st.column_config.NumberColumn(format="%.1f"),
                "@ Atuais":st.column_config.NumberColumn(format="%.2f")})
    else:
        st.info("Nenhum animal atingiu o peso-alvo ainda.")

    st.markdown("---")

    # Estoque crítico
    st.subheader(f"📦 Estoque Abaixo do Mínimo ({len(low)})")
    if low:
        for i in low:
            pct=i["current_stock"]/i["min_stock"]*100 if i["min_stock"] else 0
            st.markdown(f'<div class="card-yellow">⚠️ <b>{i["name"]}</b> — '
                f'Estoque: <b>{i["current_stock"]:.1f} {i["unit"]}</b> '
                f'(mínimo: {i["min_stock"]:.0f}) — <b>{pct:.0f}% do mínimo</b></div>',
                unsafe_allow_html=True)
        if st.button("📦 Ir para Estoque",type="primary"):
            _go("estoque"); st.rerun()
    else:
        st.success("✅ Todos os insumos com estoque adequado.")

# ══════════════════════════════════════════════════════════════════════════════
# RELATÓRIOS  (CSV + PDF)
# ══════════════════════════════════════════════════════════════════════════════
def page_relatorios():
    st.markdown('<div class="page-title">📄 Relatórios e Exportação</div>', unsafe_allow_html=True)
    animals=db.get_all_animals(status=None)

    rt1,rt2,rt3=st.tabs(["🐄 Inventário","⚖️ Pesagens","💰 Financeiro"])

    def _download_row(title, df, key):
        dc1,dc2,dc3=st.columns(3)
        with dc1:
            st.download_button(f"⬇️ CSV",_df_to_csv(df),
                f"agrotop_{key}.csv","text/csv",use_container_width=True,
                key=f"csv_{key}")
        with dc2:
            xlsx_bytes=_df_to_xlsx(title,df)
            if xlsx_bytes:
                st.download_button(f"⬇️ Excel",xlsx_bytes,
                    f"agrotop_{key}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,key=f"xlsx_{key}")
            else:
                st.info("Instale `openpyxl` p/ Excel.")
        with dc3:
            pdf_bytes=_df_to_pdf(f"AgroTop — {title}",df)
            if pdf_bytes:
                st.download_button(f"⬇️ PDF",pdf_bytes,
                    f"agrotop_{key}.pdf","application/pdf",use_container_width=True,
                    key=f"pdf_{key}")
            else:
                st.info("Instale `fpdf2` p/ PDF.")

    with rt1:
        st.subheader("🐄 Inventário Completo do Rebanho")
        rows_inv=[]
        for a in animals:
            gmd=db.calculate_gmd(a["id"])
            wd=db.get_withdrawal_end(a["id"])
            rows_inv.append({"ID":a["id"],"Raça":a["breed"],
                "Sexo":"M" if a["sex"]=="M" else "F",
                "Categoria":db.get_age_category(a.get("birth_date")),
                "Idade":db.get_age_display(a),
                "Data Nascimento":a.get("birth_date") or "",
                "Nasc. Estimado":"Sim" if a.get("birth_estimated") else "Não",
                "Origem Idade":db.AGE_SOURCES.get(a.get("age_source","propriedade"),""),
                "Data Entrada":a["entry_date"],
                "Peso Entrada (kg)":a["entry_weight"],
                "Peso Atual (kg)":a["current_weight"],
                "Ganho (kg)":round(a["current_weight"]-a["entry_weight"],1),
                "@ Atuais":db.kg_to_arrobas(a["current_weight"]),
                "GMD (kg/dia)":gmd or 0,"Status":a["status"],
                "Lote":a.get("lote_id") or "",
                "Fornecedor":a.get("fornecedor_name") or "",
                "NF":a.get("nf_number") or "",
                "GTA":a.get("gta_number") or "",
                "Carência até":wd.isoformat() if wd else ""})
        df_inv=pd.DataFrame(rows_inv)
        st.dataframe(df_inv,use_container_width=True,hide_index=True,height=350)
        _download_row("Inventário",df_inv,"inventario")

    with rt2:
        st.subheader("⚖️ Histórico de Pesagens")
        raw=db.get_all_weighings()
        if raw:
            df_p=pd.DataFrame(raw)[["animal_id","weigh_date","weight","method","lote_id","operator","notes"]].copy()
            df_p["method"]=df_p["method"].fillna("pesado").map(lambda m: db.WEIGH_METHODS.get(m,m))
            df_p.columns=["Animal","Data","Peso (kg)","Método","Lote","Operador","Obs"]
            st.dataframe(df_p,use_container_width=True,hide_index=True,height=350)
            _download_row("Pesagens",df_p,"pesagens")

    with rt3:
        ul = _unit_label()
        st.subheader("💰 Relatório Financeiro")
        price_lbl = f"Cotação (R$/{ul}) para o relatório"
        default_p = DEFAULT_PRICE_ARROBA if _use_arroba() else DEFAULT_PRICE_KG
        cotacao_r = st.number_input(price_lbl, min_value=0.01, max_value=5000.0,
            value=default_p, step=1.0)
        rend_r = 52
        if _use_arroba():
            rend_r = st.slider("Rendimento de Carcaça (%)", 40, 65, 52,
                key="rend_relatorio")
        rows_fin=[]
        for a in animals:
            if a["status"] not in ("ativo","carencia"): continue
            tc   = db.get_total_cost(a["id"])
            prod = _live_weight(a["current_weight"], rend_r/100)
            be   = round(tc/prod, 2) if prod else 0
            receita = round(prod * cotacao_r, 2)
            lucro   = round(receita - tc, 2)
            rows_fin.append({"ID":a["id"],"Raça":a["breed"],
                "Peso Atual (kg)":a["current_weight"],
                f"Prod. ({ul})":prod,
                "Custo Total (R$)":tc,
                _breakeven_label():be,
                f"Receita @ R${cotacao_r:.0f}/{ul}":receita,
                "Lucro Estimado (R$)":lucro})
        df_fin=pd.DataFrame(rows_fin)
        if not df_fin.empty:
            st.dataframe(df_fin,use_container_width=True,hide_index=True)
            _download_row("Financeiro",df_fin,"financeiro")

# ══════════════════════════════════════════════════════════════════════════════
# CADASTRAR
# ══════════════════════════════════════════════════════════════════════════════
def _age_inputs(entry_date, key_prefix=""):
    """Renderiza os campos de idade conforme o método escolhido.
    Retorna (birth_date_str|None, birth_estimated, age_source, erro|None).
    Deve ser chamado FORA de um st.form para permitir troca dinâmica."""
    MESES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    metodo = st.radio(
        "🎂 Como definir a idade?",
        list(db.AGE_SOURCES.keys()),
        format_func=lambda k: db.AGE_SOURCES[k],
        key=f"{key_prefix}age_method",
        horizontal=False,
    )

    bd_str, estimated, err = None, 0, None

    if metodo == "propriedade":
        bd = st.date_input("Data de Nascimento (exata)", value=None,
                           key=f"{key_prefix}bd_exact",
                           help="Para animais nascidos na propriedade")
        if bd:
            bd_str, estimated = bd.isoformat(), 0
        else:
            err = "Informe a data de nascimento exata."

    elif metodo == "estimado":
        st.caption("Estime o mês/ano aproximado do nascimento.")
        c1, c2 = st.columns(2)
        with c1:
            mes = st.selectbox("Mês aproximado", range(1,13),
                format_func=lambda m: MESES[m-1], key=f"{key_prefix}est_m")
        with c2:
            ano = st.number_input("Ano", min_value=2000, max_value=date.today().year,
                value=date.today().year-1, step=1, key=f"{key_prefix}est_y")
        try:
            bd_str = date(int(ano), int(mes), 15).isoformat()
            estimated = 1
        except ValueError:
            err = "Mês/ano inválido."

    elif metodo == "operador":
        st.caption("Informe a idade atual estimada do animal (hoje).")
        meses = st.number_input("Idade atual (meses)", min_value=0, max_value=360,
            value=24, step=1, key=f"{key_prefix}op_m")
        bd_str = db.birth_date_from_age(int(meses), date.today())
        estimated = 1
        st.info(f"📌 Nascimento estimado: **{bd_str}** · Categoria: "
                f"**{db.get_age_category(bd_str)}**")

    elif metodo == "nf_gta":
        st.caption("Informe a idade que consta na NF / GTA e a data do documento.")
        c1, c2 = st.columns(2)
        with c1:
            meses = st.number_input("Idade na NF/GTA (meses)", min_value=0, max_value=360,
                value=18, step=1, key=f"{key_prefix}nf_m")
        with c2:
            doc_date = st.date_input("Data do documento", value=entry_date,
                key=f"{key_prefix}nf_d")
        bd_str = db.birth_date_from_age(int(meses), doc_date)
        estimated = 1
        st.info(f"📌 Nascimento estimado: **{bd_str}** · Idade hoje: "
                f"**{db.get_age_months(bd_str)} meses** · Categoria: "
                f"**{db.get_age_category(bd_str)}**")

    return bd_str, estimated, metodo, err


def page_cadastrar():
    st.markdown('<div class="page-title">➕ Cadastrar Novo Animal</div>', unsafe_allow_html=True)
    fornecedores=db.get_all_fornecedores()
    lotes=[l for l in db.get_all_lotes() if l["status"]=="ativo"]

    # Campos fora do form (para reagir à troca de método de idade/peso)
    c_top1, c_top2 = st.columns(2)
    with c_top1:
        aid=st.text_input("🏷️ ID / Brinco *",placeholder="Ex: BR0015").strip().upper()
        breed=st.selectbox("🐄 Raça *",BREEDS)
        sex=st.radio("Sexo *",["♂ Macho","♀ Fêmea"],horizontal=True)
    with c_top2:
        entry_date=st.date_input("📅 Data de Entrada *",value=date.today())
        target_weight=st.number_input("🎯 Peso-Alvo de Abate (kg)",
            min_value=0.0,max_value=2000.0,value=500.0,step=5.0,format="%.1f")

    st.markdown("**📆 Definição de Idade / Categoria**")
    birth_date_str, birth_est, age_src, age_err = _age_inputs(entry_date, "cad_")
    is_propriedade = (age_src == "propriedade")

    # ── Peso de entrada (com método) ──────────────────────────────────────────
    st.markdown("**⚖️ Peso de Entrada**")
    st.caption("Não é obrigatório pesar na balança — pode estimar ou usar medição.")
    peso_metodo = st.radio("Como obter o peso?",
        list(db.WEIGH_METHODS.keys()),
        format_func=lambda m: db.WEIGH_METHODS[m],
        horizontal=True, key="cad_peso_metodo")

    if peso_metodo == "medicao":
        pm1, pm2, pm3 = st.columns(3)
        with pm1:
            pt_c=st.number_input("Perímetro torácico (cm)",min_value=0.0,max_value=350.0,
                value=180.0,step=1.0,key="cad_pt")
        with pm2:
            comp_c=st.number_input("Comprimento corporal (cm)",min_value=0.0,max_value=350.0,
                value=150.0,step=1.0,key="cad_comp")
        entry_weight = db.estimate_weight_by_measurement(pt_c, comp_c)
        with pm3:
            st.metric("Peso estimado", f"{entry_weight:.1f} kg")
        medida_nota = f"PT={pt_c:.0f}cm Comp={comp_c:.0f}cm"
    else:
        lbl = "Peso na balança (kg) *" if peso_metodo=="pesado" else "Peso estimado (kg) *"
        entry_weight=st.number_input(lbl,min_value=0.1,max_value=2000.0,
            step=0.5,format="%.1f",key="cad_peso_valor")
        medida_nota = ""

    with st.form("f_cad",clear_on_submit=False):
        cf1, cf2 = st.columns(2)
        with cf1:
            # Valor de compra só para animais adquiridos (não nascidos na propriedade)
            if not is_propriedade:
                purchase_price=st.number_input("💰 Valor de Compra (R$)",
                    min_value=0.0,step=10.0,format="%.2f")
            else:
                purchase_price=0.0
                st.caption("💰 Valor de compra não se aplica a animais nascidos na propriedade.")
            lote_sel=st.selectbox("🌿 Lote de Destino",
                [None]+lotes,format_func=lambda x:"— Sem lote —" if x is None else f"{x['id']} — {x['name']}")
        with cf2:
            forn_sel=st.selectbox("🚚 Fornecedor / Origem",
                [None]+fornecedores,format_func=lambda x:"— Não informado —" if x is None else f"{x['name']} ({x['city']}/{x['state']})")
            notes=st.text_area("📝 Observações",height=70,
                placeholder="Opcional",value=medida_nota)

        if not is_propriedade:
            st.caption("📄 Documentos de compra (opcional)")
            cd1, cd2 = st.columns(2)
            with cd1:
                nf_number=st.text_input("Número da NF",placeholder="Ex: 012345",
                    help="Nota Fiscal — opcional").strip()
            with cd2:
                gta_number=st.text_input("Número da GTA",placeholder="Ex: MT-0009876",
                    help="Guia de Trânsito Animal — opcional").strip()
        else:
            nf_number=gta_number=""

        if st.form_submit_button("✅ Cadastrar Animal",type="primary",use_container_width=True):
            errs=[]
            if not aid:             errs.append("ID do animal é obrigatório.")
            elif db.get_animal(aid):errs.append(f"Animal **{aid}** já existe.")
            if entry_weight<=0:     errs.append("Peso de entrada deve ser > 0.")
            if age_err:             errs.append(age_err)
            if errs:
                for e in errs: st.error(f"❌ {e}")
            else:
                db.add_animal(
                    aid, breed,
                    "M" if "Macho" in sex else "F",
                    birth_date_str,
                    entry_date.strftime("%Y-%m-%d"),
                    entry_weight, target_weight, purchase_price,
                    lote_sel["id"] if lote_sel else None,
                    forn_sel["id"] if forn_sel else None,
                    notes,
                    birth_estimated=birth_est,
                    age_source=age_src,
                    nf_number=nf_number,
                    gta_number=gta_number,
                    weight_method=peso_metodo,
                )
                cat = db.get_age_category(birth_date_str)
                st.success(f"✅ Animal **{aid}** cadastrado! Categoria: **{cat}** · "
                           f"Peso: {entry_weight:.1f} kg ({db.WEIGH_METHODS[peso_metodo]})")
                st.balloons()

    # Cadastrar Fornecedor rápido
    with st.expander("➕ Cadastrar novo Fornecedor / Origem"):
        with st.form("f_forn",clear_on_submit=True):
            ff1,ff2,ff3=st.columns(3)
            with ff1: fn=st.text_input("Nome *")
            with ff2: fc=st.text_input("Cidade")
            with ff3: fs=st.selectbox("Estado",["MT","MS","GO","MG","SP","PR","RS","BA","TO","PA","RO","Outro"])
            fcontact=st.text_input("Contato")
            if st.form_submit_button("✅ Salvar Fornecedor",use_container_width=True):
                if fn:
                    db.add_fornecedor(fn,fc,fs,fcontact)
                    st.success(f"✅ {fn} cadastrado!"); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN
# ══════════════════════════════════════════════════════════════════════════════
def _admin_users():
    st.subheader("👥 Gestão de Usuários")
    users = db.get_all_users()

    # ── Lista de usuários ─────────────────────────────────────────────────────
    df_u = pd.DataFrame([{
        "ID": u["id"], "Usuário": u["username"], "Nome": u["name"],
        "Papel": "Administrador" if u["role"]=="admin" else "Operador",
    } for u in users])
    st.dataframe(df_u, use_container_width=True, hide_index=True)

    st.markdown("---")
    col_edit, col_new = st.columns(2)

    # ── Editar usuário existente ──────────────────────────────────────────────
    with col_edit:
        st.markdown("**✏️ Editar Usuário**")
        sel = st.selectbox("Usuário", users,
            format_func=lambda u: f"{u['username']} — {u['name']}", key="edit_user_sel")
        with st.form("f_edit_user", clear_on_submit=False):
            e_username = st.text_input("Usuário (login)", value=sel["username"]).strip()
            e_name = st.text_input("Nome", value=sel["name"]).strip()
            e_role = st.selectbox("Papel", ["operator","admin"],
                index=0 if sel["role"]=="operator" else 1,
                format_func=lambda r: "Operador" if r=="operator" else "Administrador")
            st.caption("Deixe a senha em branco para mantê-la. Preencha para redefinir.")
            e_pwd = st.text_input("Nova senha", type="password", placeholder="••••••••")
            e_pwd2 = st.text_input("Confirmar nova senha", type="password", placeholder="••••••••")
            if st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True):
                errs = []
                if not e_username: errs.append("Usuário não pode ficar vazio.")
                elif db.username_exists(e_username, exclude_id=sel["id"]):
                    errs.append(f"O login '{e_username}' já está em uso.")
                if not e_name: errs.append("Nome não pode ficar vazio.")
                if e_pwd and e_pwd != e_pwd2: errs.append("As senhas não coincidem.")
                # Impede remover o último admin
                if sel["role"]=="admin" and e_role=="operator" and db.count_admins()<=1:
                    errs.append("Não é possível rebaixar o único administrador.")
                if errs:
                    for x in errs: st.error(f"❌ {x}")
                else:
                    if e_username != sel["username"]:
                        db.update_username(sel["id"], e_username)
                    db.update_user(sel["id"], e_name, e_role, e_pwd or None)
                    st.success(f"✅ Usuário '{e_username}' atualizado!")
                    # Se editou a si mesmo, atualiza a sessão
                    if sel["id"] == st.session_state.user["id"]:
                        st.session_state.user = db.get_user(sel["id"])
                    st.rerun()

        # Excluir usuário
        with st.expander("🗑️ Excluir usuário"):
            del_sel = st.selectbox("Usuário a excluir", users,
                format_func=lambda u: f"{u['username']} — {u['name']}", key="del_user_sel")
            st.warning("Esta ação é permanente.")
            if st.button("Excluir definitivamente", type="secondary"):
                if del_sel["id"] == st.session_state.user["id"]:
                    st.error("Você não pode excluir a sua própria conta logada.")
                elif del_sel["role"]=="admin" and db.count_admins()<=1:
                    st.error("Não é possível excluir o único administrador.")
                else:
                    db.delete_user(del_sel["id"])
                    st.success(f"Usuário '{del_sel['username']}' excluído."); st.rerun()

    # ── Novo usuário ──────────────────────────────────────────────────────────
    with col_new:
        st.markdown("**➕ Novo Usuário**")
        with st.form("f_new_user", clear_on_submit=True):
            n_username = st.text_input("Usuário (login) *", placeholder="ex: op2").strip()
            n_name = st.text_input("Nome *", placeholder="ex: Maria Operadora").strip()
            n_role = st.selectbox("Papel *", ["operator","admin"],
                format_func=lambda r: "Operador" if r=="operator" else "Administrador")
            n_pwd = st.text_input("Senha *", type="password", placeholder="••••••••")
            n_pwd2 = st.text_input("Confirmar senha *", type="password", placeholder="••••••••")
            if st.form_submit_button("✅ Criar Usuário", type="primary", use_container_width=True):
                errs = []
                if not n_username: errs.append("Usuário é obrigatório.")
                elif db.username_exists(n_username): errs.append(f"O login '{n_username}' já existe.")
                if not n_name: errs.append("Nome é obrigatório.")
                if not n_pwd: errs.append("Senha é obrigatória.")
                elif n_pwd != n_pwd2: errs.append("As senhas não coincidem.")
                if errs:
                    for x in errs: st.error(f"❌ {x}")
                else:
                    db.add_user(n_username, n_pwd, n_name, n_role)
                    st.success(f"✅ Usuário '{n_username}' criado!")
                    st.rerun()


def page_nutricao():
    if st.session_state.user["role"]!="admin":
        st.error("🔒 Acesso restrito ao Administrador."); return
    st.markdown('<div class="page-title">🌾 Nutrição — Plano de Trato por Piquete</div>',
                unsafe_allow_html=True)
    st.caption("Defina o que cada piquete recebe (silagem, ração, massa de soja, sal mineral...) "
               "e a frequência. Os operadores confirmam a aplicação no Modo Campo.")

    lotes = db.get_all_lotes()
    insumos = db.get_all_insumos()

    nt1, nt2, nt3 = st.tabs(["📋 Planos Ativos", "➕ Novo Item de Trato", "✅ Histórico de Checagens"])

    with nt1:
        plans = db.get_feeding_plans(active_only=False)
        if not plans:
            st.info("Nenhum plano de nutrição cadastrado. Use a aba **Novo Item de Trato**.")
        else:
            # Agrupa por piquete
            lotes_com_plano = sorted({p["lote_id"] for p in plans})
            for lid in lotes_com_plano:
                lote_nome = next((l["name"] for l in lotes if l["id"]==lid), lid)
                itens = [p for p in plans if p["lote_id"]==lid]
                st.markdown(f"#### 🌿 {lid} — {lote_nome}")
                for p in itens:
                    freq = db.FEEDING_FREQUENCIES.get(p["frequency"], p["frequency"])
                    ativo = "🟢 ativo" if p["active"] else "⚪ inativo"
                    c1, c2, c3 = st.columns([5,1,1])
                    with c1:
                        st.markdown(
                            f'<div class="hist-item">'
                            f'<b>{p["product_name"]}</b> — {p["quantity"]:.0f} {p["unit"]} '
                            f'· <span style="color:#4ade80">{freq}</span> · {ativo}'
                            f'{"  · vinc. estoque: "+p["insumo_name"] if p.get("insumo_name") else ""}'
                            f'</div>', unsafe_allow_html=True)
                    with c2:
                        novo = 0 if p["active"] else 1
                        if st.button("Ativar" if not p["active"] else "Pausar",
                                     key=f"tgl_{p['id']}", use_container_width=True):
                            db.set_feeding_plan_active(p["id"], novo); st.rerun()
                    with c3:
                        if st.button("🗑️", key=f"delp_{p['id']}", use_container_width=True):
                            db.delete_feeding_plan(p["id"]); st.rerun()

    with nt2:
        if not lotes:
            st.warning("Cadastre piquetes primeiro (em Lotes / Pastagem).")
        else:
            with st.form("f_plan", clear_on_submit=True):
                fp1, fp2 = st.columns(2)
                with fp1:
                    lote_sel = st.selectbox("Piquete *", lotes,
                        format_func=lambda l: f"{l['id']} — {l['name']}")
                    prod = st.text_input("Produto *", placeholder="Ex: Silagem de milho")
                    freq = st.selectbox("Frequência *", list(db.FEEDING_FREQUENCIES.keys()),
                        format_func=lambda f: db.FEEDING_FREQUENCIES[f])
                with fp2:
                    qtd = st.number_input("Quantidade *", min_value=0.0, step=5.0, format="%.1f")
                    unid = st.selectbox("Unidade", ["kg","ton","saco","litro","g"])
                    ins_link = st.selectbox("Vincular a insumo (opcional)",
                        [None]+insumos,
                        format_func=lambda x: "— Sem vínculo —" if x is None else f"{x['name']} ({x['current_stock']:.0f} {x['unit']})",
                        help="Se vinculado, a confirmação do operador pode baixar do estoque")
                notes = st.text_input("Observações", placeholder="Opcional")
                if st.form_submit_button("✅ Adicionar ao Plano", type="primary", use_container_width=True):
                    if not prod or qtd<=0:
                        st.error("Informe o produto e a quantidade.")
                    else:
                        db.add_feeding_plan(lote_sel["id"], prod.strip(), qtd, unid, freq,
                            insumo_id=ins_link["id"] if ins_link else None, notes=notes)
                        st.success(f"✅ {prod} adicionado ao {lote_sel['name']} ({db.FEEDING_FREQUENCIES[freq]})")
                        st.rerun()

    with nt3:
        st.markdown("**Checagens registradas pelos operadores**")
        cc1, cc2 = st.columns(2)
        with cc1:
            start_c = st.date_input("De", value=date.today()-timedelta(days=30), key="chk_start")
        with cc2:
            end_c = st.date_input("Até", value=date.today(), key="chk_end")
        checks = db.get_feeding_checks(start_date=start_c.isoformat(), end_date=end_c.isoformat())
        if checks:
            df_c = pd.DataFrame(checks)[["check_date","lote_id","product_name","status","actual_quantity","operator"]].copy()
            df_c["status"] = df_c["status"].map(lambda s: db.FEEDING_CHECK_STATUS.get(s,s))
            df_c.columns = ["Data","Piquete","Produto","Status","Qtd Aplicada","Operador"]
            st.dataframe(df_c, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma checagem registrada no período.")


def page_admin():
    if st.session_state.user["role"]!="admin":
        st.error("🔒 Acesso restrito ao Administrador."); return
    st.markdown('<div class="page-title">⚙️ Administração</div>', unsafe_allow_html=True)
    at_user,at1,at2,at3=st.tabs(["👥 Usuários","📋 Dados","🔧 Status Animais","🗄️ Banco"])

    with at_user:
        _admin_users()

    with at1:
        st.subheader("✏️ Edição Direta de Dados")
        st.caption("Corrija qualquer registro: edite células, adicione linhas (+) ou remova (🗑). "
                   "Clique em **Salvar alterações** para gravar no banco.")
        st.warning("⚠️ Área técnica: alterações são gravadas diretamente no banco. "
                   "Edite com cuidado — não há desfazer.")

        tab=st.selectbox("Tabela", db.ADMIN_TABLES, key="admin_tab_edit")
        cols, pk = db.admin_table_info(tab)
        orig_rows = db.admin_get_rows(tab)
        orig_df = pd.DataFrame(orig_rows, columns=cols)

        st.caption(f"Tabela **{tab}** · chave primária: **{pk}** · {len(orig_rows)} registro(s)")

        edited = st.data_editor(
            orig_df, num_rows="dynamic", use_container_width=True,
            hide_index=True, key=f"editor_{tab}",
            column_config={pk: st.column_config.Column(f"{pk} (chave)", help="Chave primária")},
        )

        cbtn1, cbtn2 = st.columns([1,3])
        with cbtn1:
            do_save = st.button("💾 Salvar alterações", type="primary",
                                use_container_width=True, key=f"savebtn_{tab}")
        with cbtn2:
            st.caption("Para inserir: use a linha em branco no fim da tabela. "
                       "Em tabelas com ID automático, deixe a chave vazia.")

        if do_save:
            import math
            def _pyval(v):
                if v is None: return None
                try:
                    if pd.isna(v): return None
                except (TypeError, ValueError): pass
                if hasattr(v, "item"):
                    try: v = v.item()
                    except Exception: pass
                if isinstance(v, float) and v.is_integer(): return int(v)
                return v

            def _is_empty_pk(v):
                pv = _pyval(v)
                return pv is None or (isinstance(pv, str) and pv.strip() == "")

            orig_by_pk = {_pyval(r[pk]): r for r in orig_rows}
            updates, inserts, seen = [], [], set()

            for rec in edited.to_dict("records"):
                clean = {c: _pyval(rec.get(c)) for c in cols}
                pkv = clean.get(pk)
                if _is_empty_pk(pkv) or pkv not in orig_by_pk:
                    row_ins = dict(clean)
                    if _is_empty_pk(pkv):
                        row_ins.pop(pk, None)   # deixa o banco gerar o ID
                    # ignora linhas totalmente vazias
                    if any(v is not None and str(v) != "" for v in row_ins.values()):
                        inserts.append(row_ins)
                else:
                    seen.add(pkv)
                    orig = orig_by_pk[pkv]
                    if any(str(_pyval(orig.get(c))) != str(clean.get(c)) for c in cols):
                        updates.append(clean)

            delete_pks = [k for k in orig_by_pk if k not in seen]

            try:
                res = db.admin_apply_changes(tab, updates, inserts, delete_pks)
                st.success(f"✅ Salvo em **{tab}**: {res['updated']} atualizada(s), "
                           f"{res['inserted']} inserida(s), {res['deleted']} excluída(s).")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao salvar: {e}")

    with at2:
        st.subheader("Alterar Status de Animal")
        all_a=db.get_all_animals(status=None)
        ac1,ac2,ac3=st.columns(3)
        with ac1: sel_a=st.selectbox("Animal",[a["id"] for a in all_a])
        with ac2: new_st=st.selectbox("Novo Status",["ativo","vendido","morto","carencia"])
        with ac3:
            st.markdown("<br>",unsafe_allow_html=True)
            if st.button("✅ Atualizar",type="primary",use_container_width=True):
                db.update_animal_status(sel_a,new_st)
                st.success(f"{sel_a} → {new_st}"); st.rerun()

    with at3:
        import os
        if db.USE_PG:
            st.markdown("**Banco de Dados:** PostgreSQL / Supabase (nuvem) ☁️")
            st.caption("Os dados ficam no Supabase e são acessíveis de qualquer lugar.")
            for t in db.ADMIN_TABLES:
                try:
                    n = db.admin_get_rows(t)
                    st.write(f"• `{t}`: {len(n)} registro(s)")
                except Exception:
                    pass
        else:
            st.markdown("**Banco de Dados:** SQLite local `agrotop.db` — funciona offline")
            if os.path.exists(db.DB_PATH):
                st.metric("Tamanho",f"{os.path.getsize(db.DB_PATH)/1024:.1f} KB")

# ══════════════════════════════════════════════════════════════════════════════
# ROTEADOR
# ══════════════════════════════════════════════════════════════════════════════
# Páginas que o operador pode acessar (as demais são exclusivas do admin)
OPERATOR_PAGES = {"campo", "cadastrar", "estoque"}

def _try_restore_session():
    """Tenta restaurar o login a partir do token na URL (mantém login ao recarregar)."""
    if st.session_state.authenticated:
        return
    token = st.query_params.get("sid")
    if token:
        u = db.get_session_user(token)
        if u:
            st.session_state.authenticated = True
            st.session_state.user = u
            st.session_state.page = "dashboard" if u["role"] == "admin" else "campo"

def main():
    _try_restore_session()
    if not st.session_state.authenticated:
        page_login(); return

    user = st.session_state.user
    # Controle de acesso: operador só acessa páginas permitidas
    if user["role"] != "admin" and st.session_state.page not in OPERATOR_PAGES:
        st.session_state.page = "campo"

    _sidebar()
    {
        "dashboard": page_dashboard,
        "campo":     page_campo,
        "rebanho":   page_rebanho,
        "animal":    page_animal,
        "lotes":     page_lotes,
        "financeiro":page_financeiro,
        "estoque":   page_estoque,
        "nutricao":  page_nutricao,
        "alertas":   page_alertas,
        "relatorios":page_relatorios,
        "cadastrar": page_cadastrar,
        "admin":     page_admin,
    }.get(st.session_state.page, page_campo if user["role"]!="admin" else page_dashboard)()

if __name__ == "__main__":
    main()
