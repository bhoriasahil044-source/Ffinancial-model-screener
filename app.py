"""
Financial Model & DCF Valuation Screener
Professional TradingView & Bloomberg-inspired dark terminal interface
Built with Streamlit, Plotly, and OpenPyXL.
"""

import os
import sys
import io

# Prioritize current application directory in sys.path for Streamlit Cloud
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

try:
    from screener_scraper import (
        ScreenerScraper, ScreenerScraperError, InvalidURLError, CompanyNotFoundError,
        ScreenerAccessError, InsufficientDataError
    )
    from forecasting_engine import (
        FinancialStatementForecaster, ForecastingError, InsufficientHistoryError
    )
    from dcf_model import DCFValuationEngine, ValuationValidationError
    from workbook_builder import WorkbookBuilder
except ImportError:
    from src.scraper.screener_scraper import (
        ScreenerScraper, ScreenerScraperError, InvalidURLError, CompanyNotFoundError,
        ScreenerAccessError, InsufficientDataError
    )
    from src.prediction.forecasting_engine import (
        FinancialStatementForecaster, ForecastingError, InsufficientHistoryError
    )
    from src.valuation.dcf_model import DCFValuationEngine, ValuationValidationError
    from src.excel.workbook_builder import WorkbookBuilder

# Page configuration
st.set_page_config(
    page_title="Financial Model & Valuation Screener",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Professional Pro-Dark Financial Terminal CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* Global container padding */
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 1440px;
    }

    /* Terminal header bar */
    .terminal-header {
        border-bottom: 1px solid #21262d;
        padding-bottom: 0.8rem;
        margin-bottom: 1.2rem;
    }
    .company-title-row {
        display: flex;
        align-items: baseline;
        gap: 12px;
        flex-wrap: wrap;
    }
    .company-name {
        font-size: 1.55rem;
        font-weight: 700;
        color: #f0f6fc;
        letter-spacing: -0.02em;
        margin: 0;
    }
    .company-ticker {
        font-size: 0.9rem;
        font-weight: 600;
        color: #58a6ff;
        background: rgba(56, 189, 248, 0.12);
        padding: 3px 9px;
        border-radius: 4px;
        border: 1px solid rgba(56, 189, 248, 0.25);
    }
    .company-sector {
        font-size: 0.82rem;
        font-weight: 500;
        color: #8b949e;
        background: #161b22;
        padding: 3px 8px;
        border-radius: 4px;
        border: 1px solid #30363d;
    }
    .company-meta {
        font-size: 0.8rem;
        color: #8b949e;
        margin-top: 5px;
    }

    /* KPI metric strip */
    .metric-strip {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
        gap: 10px;
        margin-bottom: 1.2rem;
    }
    .metric-cell {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 10px 14px;
    }
    .metric-label {
        font-size: 0.72rem;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        font-weight: 500;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.15rem;
        font-weight: 700;
        color: #f0f6fc;
        line-height: 1.2;
    }
    .metric-badge-pos {
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 600;
        color: #3fb950;
        margin-top: 2px;
    }
    .metric-badge-neg {
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 600;
        color: #f85149;
        margin-top: 2px;
    }

    /* Discreet terminal disclaimer */
    .disclaimer-card {
        padding: 12px 16px;
        background: #161b22;
        border-left: 3px solid #38bdf8;
        border-radius: 4px;
        font-size: 0.78rem;
        color: #8b949e;
        margin-top: 2.5rem;
        line-height: 1.5;
        border-top: 1px solid #21262d;
        border-right: 1px solid #21262d;
        border-bottom: 1px solid #21262d;
    }

    .sidebar-section-title {
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #8b949e;
        margin-top: 0.8rem;
        margin-bottom: 0.4rem;
    }
</style>
""", unsafe_allow_html=True)


# High-Contrast TradingView Dark Chart Theme Helper
def apply_market_theme(fig, title="", height=380, show_legend=True, xaxis_title=None, yaxis_title=None):
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=14, color="#f0f6fc", family="Inter, sans-serif"),
            x=0.01,
            xanchor="left"
        ) if title else None,
        template="plotly_dark",
        height=height,
        margin=dict(l=50, r=30, t=55 if title else 35, b=45),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#1f242c",
            font_size=12,
            font_family="Inter, sans-serif",
            font_color="#ffffff",
            bordercolor="#38bdf8"
        ),
        showlegend=show_legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.03,
            xanchor="left",
            x=0.01,
            font=dict(size=11, color="#c9d1d9", family="Inter, sans-serif"),
            bgcolor="rgba(0,0,0,0)"
        ),
        font=dict(family="Inter, -apple-system, sans-serif", color="#c9d1d9"),
        plot_bgcolor="#131722",
        paper_bgcolor="#131722",
        xaxis=dict(
            title=dict(text=xaxis_title, font=dict(size=11, color="#8b949e", family="Inter, sans-serif")) if xaxis_title else None,
            showgrid=True,
            gridcolor="#1e222d",
            zeroline=False,
            tickfont=dict(size=11, color="#8b949e"),
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
            spikedash="dot",
            spikecolor="#484f58"
        ),
        yaxis=dict(
            title=dict(text=yaxis_title, font=dict(size=11, color="#8b949e", family="Inter, sans-serif")) if yaxis_title else None,
            showgrid=True,
            gridcolor="#1e222d",
            zeroline=False,
            tickfont=dict(size=11, color="#8b949e"),
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
            spikedash="dot",
            spikecolor="#484f58"
        )
    )
    return fig


# -----------------------------------------------------------------------------
# SIDEBAR CONTROLS
# -----------------------------------------------------------------------------
st.sidebar.markdown("<div class='sidebar-section-title'>Company Selection</div>", unsafe_allow_html=True)

presets = {
    "Tata Steel (Metals)": "https://www.screener.in/company/TATASTEEL/consolidated/",
    "Hindustan Unilever (FMCG)": "https://www.screener.in/company/HINDUNILVR/",
    "TCS (IT Services)": "https://www.screener.in/company/TCS/",
    "Reliance Industries (Energy)": "https://www.screener.in/company/RELIANCE/consolidated/",
    "Custom URL": ""
}

selected_preset = st.sidebar.selectbox("Quick Presets", options=list(presets.keys()), index=0)

default_target_url = presets[selected_preset] if presets[selected_preset] else "https://www.screener.in/company/TATASTEEL/consolidated/"

if "target_url" not in st.session_state or selected_preset != st.session_state.get("prev_preset"):
    st.session_state["target_url"] = default_target_url
    st.session_state["prev_preset"] = selected_preset

url_input = st.sidebar.text_input(
    "Screener Company URL",
    value=st.session_state["target_url"],
    help="Direct link to any listed company page on Screener.in"
)
st.session_state["target_url"] = url_input

with st.sidebar.expander("Valuation Assumptions", expanded=False):
    rf_rate = st.slider("Risk-Free Rate (Rf)", min_value=5.0, max_value=9.0, value=7.0, step=0.1, format="%.1f%%") / 100.0
    erp = st.slider("Equity Risk Premium (ERP)", min_value=4.0, max_value=8.0, value=5.5, step=0.1, format="%.1f%%") / 100.0
    beta_val = st.slider("Beta (β)", min_value=0.4, max_value=2.0, value=1.0, step=0.05)
    term_g = st.slider("Terminal Growth Rate (g)", min_value=2.5, max_value=6.0, value=4.5, step=0.25, format="%.2f%%") / 100.0

run_button = st.sidebar.button("Run Valuation", type="primary", use_container_width=True)


# -----------------------------------------------------------------------------
# COMPUTATION CACHE
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_and_compute(url: str, rf: float, erp_val: float, beta: float, g_term: float):
    scraper = ScreenerScraper()
    raw = scraper.fetch_company_data(url)
    forecaster = FinancialStatementForecaster(raw)
    fc_res = forecaster.run_forecast(forecast_years=5)
    dcf = DCFValuationEngine(raw, fc_res)
    val_res = dcf.calculate_valuation(
        risk_free_rate=rf,
        equity_risk_premium=erp_val,
        beta=beta,
        terminal_growth=g_term
    )
    return raw, fc_res, val_res


# -----------------------------------------------------------------------------
# MAIN APP BODY
# -----------------------------------------------------------------------------
if not url_input.strip():
    st.info("Enter a Screener.in company URL in the sidebar to begin analysis.")
    st.stop()

with st.spinner("Extracting audited financials and computing valuation..."):
    try:
        raw_data, fc_results, val_results = fetch_and_compute(url_input, rf_rate, erp, beta_val, term_g)
    except InvalidURLError as e:
        st.error(f"Invalid URL: {e}")
        st.info("Ensure the URL follows the format: `https://www.screener.in/company/<TICKER>/`.")
        st.stop()
    except CompanyNotFoundError as e:
        st.error(f"Company Not Found: {e}")
        st.info("Verify that the ticker symbol is actively listed on Screener.in.")
        st.stop()
    except InsufficientDataError as e:
        st.error(f"Data Extraction Error: {e}")
        st.stop()
    except InsufficientHistoryError as e:
        st.error(f"Insufficient History: {e}")
        st.stop()
    except ValuationValidationError as e:
        st.error(f"Valuation Constraint Error: {e}")
        st.warning("Terminal Growth Rate (g) must remain strictly lower than WACC.")
        st.stop()
    except Exception as e:
        st.error(f"Unexpected Calculation Error: {str(e)}")
        st.stop()

# Basic Identifiers & Metrics
company_name = raw_data.get('company_name', 'Company')
ticker = raw_data.get('ticker', '')
kpis = raw_data.get('kpis', {})
prov = raw_data.get('provenance', {})
sector = raw_data.get('sector', 'Corporate')

cmp = float(val_results['valuation_bridge']['current_market_price'])
mcap = float(val_results['valuation_bridge']['market_capitalization_cr'])
g_data = val_results['gordon_growth_method']
g_target = g_data['target_price_per_share']
g_upside = g_data['upside_pct']
m_target = val_results['exit_multiple_method']['target_price_per_share']
m_upside = val_results['exit_multiple_method']['upside_pct']
fair_target = val_results['fair_value_summary']['blended_target_price']
fair_upside = val_results['fair_value_summary']['blended_upside_pct']
wacc_pct = val_results['wacc_parameters']['wacc_pct']

# Top Header
st.markdown(f"""
<div class="terminal-header">
    <div class="company-title-row">
        <h1 class="company-name">{company_name}</h1>
        <span class="company-ticker">{ticker}</span>
        <span class="company-sector">{sector}</span>
    </div>
    <div class="company-meta">
        Source: {prov.get('source_url', url_input)} &bull; Reporting Scope: {prov.get('reporting_type', 'Audited')} &bull; Extracted: {prov.get('extracted_at_utc', 'Real-time')}
    </div>
</div>
""", unsafe_allow_html=True)

# Compact KPI Strip
upside_sign = "+" if fair_upside >= 0 else ""
kpi_cols = st.columns(7)
with kpi_cols[0]:
    st.metric("CMP", f"₹{cmp:,.1f}" if cmp > 0 else "N/A")
with kpi_cols[1]:
    st.metric("Fair Value", f"₹{fair_target:,.1f}", delta=f"{upside_sign}{fair_upside:.1f}%")
with kpi_cols[2]:
    st.metric("Market Cap", f"₹{mcap:,.0f} Cr" if mcap > 0 else "N/A")
with kpi_cols[3]:
    st.metric("P/E Ratio", f"{kpis.get('Stock P/E', 'N/A')}")
with kpi_cols[4]:
    st.metric("Book Value", f"₹{kpis.get('Book Value', 'N/A')}")
with kpi_cols[5]:
    st.metric("ROCE", f"{kpis.get('ROCE', 'N/A')}%")
with kpi_cols[6]:
    st.metric("ROE", f"{kpis.get('ROE', 'N/A')}%")

# Discreet Data Quality & Scope Expander
with st.expander("Data Quality, Audit & Source Details", expanded=False):
    q_c1, q_c2, q_c3 = st.columns(3)
    q_c1.markdown(f"**Reporting Scope**: {prov.get('reporting_type', 'Audited')}")
    q_c1.markdown(f"**Source URL**: [{prov.get('source_url', url_input)}]({prov.get('source_url', url_input)})")
    q_c2.markdown(f"**Cash Flow Statements**: {'Available' if prov.get('has_cash_flow') else 'Not Found'}")
    q_c2.markdown(f"**Financial Ratios**: {'Available' if prov.get('has_ratios') else 'Not Found'}")
    q_c3.markdown(f"**Audited Fiscal Years**: {len(prov.get('historical_years_available', []))} periods")
    q_c3.markdown(f"**Extraction Timestamp**: {prov.get('extracted_at_utc', 'Real-time')}")

# -----------------------------------------------------------------------------
# NAVIGATION TABS (Strictly 6 Major Areas)
# -----------------------------------------------------------------------------
tab_overview, tab_forecast, tab_valuation, tab_sensitivity, tab_statements, tab_excel = st.tabs([
    "Overview",
    "Forecast",
    "Valuation",
    "Sensitivity",
    "Statements",
    "Excel Export"
])

# =============================================================================
# TAB 1: OVERVIEW
# =============================================================================
with tab_overview:
    # 1. High-Contrast Valuation Targets vs CMP Visual
    methods = ["Exit Multiple Method", "Gordon Growth Method", "Blended Fair Value"]
    targets = [m_target, g_target, fair_target]
    upsides = [m_upside, g_upside, fair_upside]
    bar_colors = ["#38bdf8", "#34d399", "#818cf8"]

    fig_val_comp = go.Figure()
    fig_val_comp.add_trace(go.Bar(
        y=methods,
        x=targets,
        orientation="h",
        marker=dict(color=bar_colors, line=dict(color="#1e222d", width=1.5)),
        text=[f"₹{t:,.1f} ({'+' if u >= 0 else ''}{u:.1f}%)" for t, u in zip(targets, upsides)],
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(color="#ffffff", size=12, family="Inter, sans-serif"),
        hovertemplate="<b>%{y}</b><br>Target Price: ₹%{x:,.1f}<extra></extra>"
    ))

    # Benchmark reference line for CMP
    if cmp > 0:
        fig_val_comp.add_vline(
            x=cmp,
            line_width=2.5,
            line_dash="dash",
            line_color="#f43f5e",
            annotation_text=f"CMP: ₹{cmp:,.1f}",
            annotation_position="top right",
            annotation_font=dict(color="#f43f5e", size=12, family="Inter, sans-serif")
        )

    apply_market_theme(
        fig_val_comp,
        title="DCF Target Price Comparison vs. Current Market Price (CMP)",
        height=260,
        show_legend=False,
        xaxis_title="Price Per Share (₹)"
    )
    st.plotly_chart(fig_val_comp, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

    # Valuation & Key Decision Highlights
    col_ov1, col_ov2 = st.columns(2)
    with col_ov1:
        st.markdown("##### Valuation Takeaways")
        diff_val = fair_target - cmp
        status_text = "Undervalued (Favorable Entry)" if diff_val > 0 else "Overvalued (Premium Multiple)"
        summary_df = pd.DataFrame([
            {"Parameter": "Valuation Assessment", "Value": status_text},
            {"Parameter": "Blended Fair Value", "Value": f"₹{fair_target:,.1f}"},
            {"Parameter": "Implied Margin of Safety", "Value": f"{fair_upside:+.1f}%"},
            {"Parameter": "Gordon Growth Target (Perpetual)", "Value": f"₹{g_target:,.1f} ({g_upside:+.1f}%)"},
            {"Parameter": "Exit Multiple Target (EV/EBITDA)", "Value": f"₹{m_target:,.1f} ({m_upside:+.1f}%)"},
            {"Parameter": "Cost of Capital (WACC)", "Value": f"{wacc_pct:.2f}%"},
            {"Parameter": "Perpetual Terminal Growth (g)", "Value": f"{term_g*100:.2f}%"}
        ])
        st.dataframe(summary_df, hide_index=True, use_container_width=True)

    with col_ov2:
        st.markdown("##### Operating Profile & Drivers")
        backtest = fc_results['backtest']
        best_model = backtest.get('best_model', 'Auto-Regressive')
        best_eval = backtest['model_evaluations'].get(best_model, {})
        mape_val = best_eval.get('mape', 'N/A')
        
        pl_df = raw_data['profit_loss']
        hist_years = fc_results['historical_years']
        sales_hist_row = pl_df.loc['Sales'] if 'Sales' in pl_df.index else pd.Series()
        sales_start = float(sales_hist_row.get(hist_years[0], 0.0))
        sales_end = float(sales_hist_row.get(hist_years[-1], 0.0))
        cagr_hist = ((sales_end / sales_start) ** (1.0 / max(1, len(hist_years) - 1)) - 1.0) * 100 if sales_start > 0 else 0.0

        sales_fc = fc_results['forecast_statements']['sales']
        cagr_fc = ((sales_fc[-1] / sales_end) ** (1.0 / len(sales_fc)) - 1.0) * 100 if sales_end > 0 else 0.0

        driver_df = pd.DataFrame([
            {"Metric": "Optimal Forecasting Engine", "Value": f"{best_model}"},
            {"Metric": "Out-of-Sample Backtest MAPE", "Value": f"{mape_val}%"},
            {"Metric": "Historical Revenue CAGR", "Value": f"{cagr_hist:.1f}% ({len(hist_years)} Periods)"},
            {"Metric": "Projected 5-Yr Revenue CAGR", "Value": f"{cagr_fc:.1f}%"},
            {"Metric": "Audited Fiscal Periods Analyzed", "Value": f"{hist_years[0]} to {hist_years[-1]}"},
            {"Metric": "Forecast Horizon", "Value": f"{fc_results['future_years'][0]} to {fc_results['future_years'][-1]}"},
            {"Metric": "Discounting Framework", "Value": "Mid-Year Convention (t - 0.5)"}
        ])
        st.dataframe(driver_df, hide_index=True, use_container_width=True)


# =============================================================================
# TAB 2: FORECAST
# =============================================================================
with tab_forecast:
    hist_years = fc_results['historical_years']
    future_years = fc_results['future_years']
    pl_df = raw_data['profit_loss']

    sales_hist = [float(pl_df.loc['Sales', y]) if 'Sales' in pl_df.index and y in pl_df.columns else 0.0 for y in hist_years]
    ebitda_hist = [float(pl_df.loc['Operating Profit', y]) if 'Operating Profit' in pl_df.index and y in pl_df.columns else 0.0 for y in hist_years]

    sales_fc = fc_results['forecast_statements']['sales']
    ebitda_fc = fc_results['forecast_statements']['ebitda']
    fcff_fc = fc_results['forecast_statements']['fcff']

    # 2. Historical vs. Forecast Financials (High-Contrast Pro Dark Chart)
    st.markdown("##### Historical vs. Forecast Trajectory (Revenue, EBITDA & FCFF)")
    
    fig_traj = go.Figure()

    # Revenue: Historical (Solid Cyan) & Forecast (Dashed Sky Blue)
    fig_traj.add_trace(go.Scatter(
        x=hist_years, y=sales_hist, mode='lines+markers', name='Revenue (Actual)',
        line=dict(color='#38bdf8', width=2.8), marker=dict(size=6, color='#38bdf8'),
        hovertemplate="FY %{x}<br>Actual Revenue: ₹%{y:,.0f} Cr<extra></extra>"
    ))
    fig_traj.add_trace(go.Scatter(
        x=[hist_years[-1]] + future_years, y=[sales_hist[-1]] + sales_fc, mode='lines+markers', name='Revenue (Forecast)',
        line=dict(color='#60a5fa', width=2.5, dash='dash'), marker=dict(size=6, symbol='diamond', color='#60a5fa'),
        hovertemplate="FY %{x}<br>Forecast Revenue: ₹%{y:,.0f} Cr<extra></extra>"
    ))

    # EBITDA: Historical (Solid Mint) & Forecast (Dashed Green)
    fig_traj.add_trace(go.Scatter(
        x=hist_years, y=ebitda_hist, mode='lines+markers', name='EBITDA (Actual)',
        line=dict(color='#10b981', width=2.2), marker=dict(size=5, color='#10b981'),
        hovertemplate="FY %{x}<br>Actual EBITDA: ₹%{y:,.0f} Cr<extra></extra>"
    ))
    fig_traj.add_trace(go.Scatter(
        x=[hist_years[-1]] + future_years, y=[ebitda_hist[-1]] + ebitda_fc, mode='lines+markers', name='EBITDA (Forecast)',
        line=dict(color='#34d399', width=2.0, dash='dash'), marker=dict(size=5, symbol='diamond', color='#34d399'),
        hovertemplate="FY %{x}<br>Forecast EBITDA: ₹%{y:,.0f} Cr<extra></extra>"
    ))

    # FCFF: Forecast (Bright Lavender)
    fig_traj.add_trace(go.Scatter(
        x=future_years, y=fcff_fc, mode='lines+markers', name='FCFF (Forecast)',
        line=dict(color='#c084fc', width=2.2, dash='dot'), marker=dict(size=6, symbol='triangle-up', color='#c084fc'),
        hovertemplate="FY %{x}<br>Projected FCFF: ₹%{y:,.0f} Cr<extra></extra>"
    ))

    # Vertical divider separating historical actuals from forecast
    fig_traj.add_vline(
        x=hist_years[-1],
        line_width=1.5,
        line_dash="dash",
        line_color="#64748b"
    )

    # Shaded forecast horizon with clean tint
    fig_traj.add_vrect(
        x0=hist_years[-1],
        x1=future_years[-1],
        fillcolor="rgba(56, 189, 248, 0.08)",
        layer="below",
        line_width=0,
        annotation_text="Forecast Horizon →",
        annotation_position="top left",
        annotation_font=dict(size=11, color="#94a3b8", family="Inter, sans-serif")
    )

    apply_market_theme(
        fig_traj,
        height=400,
        show_legend=True,
        xaxis_title="Fiscal Period",
        yaxis_title="Amount (₹ Cr.)"
    )
    fig_traj.update_xaxes(tickangle=-25)
    st.plotly_chart(fig_traj, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

    # 3. Scenario Analysis Chart (Base vs. Bull vs. Bear with Dynamic Scaling)
    st.markdown("##### Revenue Scenario Analysis (Base vs. Bull vs. Bear)")
    sales_bull = fc_results['scenarios']['bull']['sales']
    sales_bear = fc_results['scenarios']['bear']['sales']

    fig_scen = go.Figure()
    # Bull Case (Vivid Emerald)
    fig_scen.add_trace(go.Scatter(
        x=future_years, y=sales_bull, mode='lines+markers', name='Bull Case (+0.5σ)',
        line=dict(color='#22c55e', width=2.0, dash='dot'), marker=dict(size=6, color='#22c55e'),
        hovertemplate="FY %{x}<br>Bull Sales: ₹%{y:,.0f} Cr<extra></extra>"
    ))
    # Bear Case (Vivid Coral)
    fig_scen.add_trace(go.Scatter(
        x=future_years, y=sales_bear, mode='lines+markers', name='Bear Case (-0.5σ)',
        line=dict(color='#f43f5e', width=2.0, dash='dot'), marker=dict(size=6, color='#f43f5e'),
        fill='tonexty', fillcolor='rgba(56, 189, 248, 0.1)',
        hovertemplate="FY %{x}<br>Bear Sales: ₹%{y:,.0f} Cr<extra></extra>"
    ))
    # Base Case (Vivid Sky Blue)
    fig_scen.add_trace(go.Scatter(
        x=future_years, y=sales_fc, mode='lines+markers', name='Base Case',
        line=dict(color='#38bdf8', width=3.0), marker=dict(size=8, color='#38bdf8'),
        hovertemplate="FY %{x}<br>Base Sales: ₹%{y:,.0f} Cr<extra></extra>"
    ))

    # Dynamic Y-axis scale to clearly highlight scenario spreads
    y_all = sales_bull + sales_bear + sales_fc
    y_min, y_max = min(y_all), max(y_all)
    y_padding = max(100.0, (y_max - y_min) * 0.35)

    apply_market_theme(
        fig_scen,
        height=360,
        show_legend=True,
        xaxis_title="Forecast Fiscal Period",
        yaxis_title="Sales (₹ Cr.)"
    )
    fig_scen.update_layout(yaxis=dict(range=[max(0.0, y_min - y_padding), y_max + y_padding]))
    st.plotly_chart(fig_scen, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

    # Econometric Backtesting Selection Details
    with st.expander("Walk-Forward Model Backtest Details", expanded=False):
        st.write("An ensemble of statistical and econometric models is evaluated using out-of-sample walk-forward testing. The model with the lowest Mean Absolute Percentage Error (MAPE) is selected as the primary driver.")
        backtest_evals = fc_results['backtest']['model_evaluations']
        bt_data = []
        for m_name, m_res in backtest_evals.items():
            is_winner = "Selected (Lowest MAPE)" if m_name == fc_results['backtest']['best_model'] else ("Invalid" if not m_res.get('is_valid', True) else "Evaluated")
            bt_data.append({
                "Forecasting Engine": m_name,
                "Backtest MAPE (%)": f"{m_res.get('mape', 'N/A')}%" if m_res.get('is_valid', True) else "Failed",
                "RMSE (₹ Cr.)": f"₹{m_res.get('rmse', 'N/A'):,.0f}" if m_res.get('is_valid', True) else "N/A",
                "MAE (₹ Cr.)": f"₹{m_res.get('mae', 'N/A'):,.0f}" if m_res.get('is_valid', True) else "N/A",
                "Status": is_winner
            })
        st.dataframe(pd.DataFrame(bt_data), hide_index=True, use_container_width=True)


# =============================================================================
# TAB 3: VALUATION
# =============================================================================
with tab_valuation:
    # High Terminal Value Warning Banner
    if g_data.get('high_tv_warning', False):
        st.warning(
            f"Terminal Value represents **{g_data['tv_percent_of_ev']}%** of Enterprise Value. "
            f"Valuation results are highly sensitive to Terminal Growth ({g_data['terminal_growth_pct']}%) and WACC ({wacc_pct}%)."
        )

    # 4. Enterprise Value to Equity Value Waterfall Bridge (High-Contrast White Text)
    st.markdown("##### Enterprise Value to Equity Value Bridge")
    cum_fcf = val_results['valuation_bridge']['cumulative_pv_fcff_cr']
    pv_tv = g_data['pv_terminal_value_cr']
    ev = g_data['enterprise_value_cr']
    cash = val_results['valuation_bridge']['cash_and_investments_cr']
    debt = val_results['valuation_bridge']['total_debt_cr']
    eq_val = g_data['implied_equity_value_cr']

    fig_wf = go.Figure(go.Waterfall(
        name="Bridge",
        orientation="v",
        measure=["relative", "relative", "total", "relative", "relative", "total"],
        x=["PV of 5-Yr FCFF", "PV of Terminal Value", "Enterprise Value", "(+) Cash & Inv.", "(-) Total Debt", "Equity Value"],
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(color="#ffffff", size=12, family="Inter, sans-serif"),
        text=[f"₹{cum_fcf:,.0f}", f"₹{pv_tv:,.0f}", f"₹{ev:,.0f}", f"₹{cash:,.0f}", f"-₹{debt:,.0f}", f"₹{eq_val:,.0f}"],
        y=[cum_fcf, pv_tv, ev, cash, -debt, eq_val],
        connector={"line": {"color": "#64748b", "width": 1.5}},
        increasing={"marker": {"color": "#10b981"}},
        decreasing={"marker": {"color": "#f43f5e"}},
        totals={"marker": {"color": "#6366f1"}}
    ))
    apply_market_theme(
        fig_wf,
        height=380,
        show_legend=False,
        yaxis_title="Value (₹ Cr.)"
    )
    st.plotly_chart(fig_wf, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

    # WACC Breakdown & Bridge Metrics
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        st.markdown("##### Weighted Average Cost of Capital (WACC)")
        w_p = val_results['wacc_parameters']
        w_breakdown = pd.DataFrame([
            {"Component": "Risk-Free Rate (Rf)", "Value": f"{w_p['risk_free_rate_pct']:.2f}%"},
            {"Component": "Equity Risk Premium (ERP)", "Value": f"{w_p['equity_risk_premium_pct']:.2f}%"},
            {"Component": "Beta (β)", "Value": f"{w_p['beta']:.2f}"},
            {"Component": "Cost of Equity (Ke)", "Value": f"{w_p['cost_of_equity_pct']:.2f}%"},
            {"Component": "Pre-Tax Cost of Debt (Kd)", "Value": f"{w_p['cost_of_debt_pre_tax_pct']:.2f}%"},
            {"Component": "Post-Tax Cost of Debt (Kd)", "Value": f"{w_p['cost_of_debt_post_tax_pct']:.2f}%"},
            {"Component": "Weight of Equity (We)", "Value": f"{w_p['weight_equity_pct']:.1f}%"},
            {"Component": "Weight of Debt (Wd)", "Value": f"{w_p['weight_debt_pct']:.1f}%"},
            {"Component": "Calculated WACC", "Value": f"{w_p['wacc_pct']:.2f}%"}
        ])
        st.dataframe(w_breakdown, hide_index=True, use_container_width=True)

    with col_w2:
        st.markdown("##### Valuation Bridge & Per-Share Output")
        out_table = pd.DataFrame([
            {"Metric": "Discounting Framework", "Value": "Mid-Year Convention (t - 0.5)"},
            {"Metric": "5-Year Cumulative PV of FCFF", "Value": f"₹{cum_fcf:,.1f} Cr."},
            {"Metric": "PV of Terminal Value", "Value": f"₹{pv_tv:,.1f} Cr."},
            {"Metric": "% Terminal Value of Total EV", "Value": f"{g_data['tv_percent_of_ev']}%"},
            {"Metric": "Enterprise Value (EV)", "Value": f"₹{ev:,.1f} Cr."},
            {"Metric": "(+) Cash & Liquid Investments", "Value": f"₹{cash:,.1f} Cr."},
            {"Metric": "(-) Total Borrowings (Debt)", "Value": f"₹{debt:,.1f} Cr."},
            {"Metric": "Implied Equity Value", "Value": f"₹{eq_val:,.1f} Cr."},
            {"Metric": "Diluted Shares Outstanding", "Value": f"{val_results['valuation_bridge']['shares_outstanding_cr']:,.1f} Cr."},
            {"Metric": "Gordon Growth Target Price", "Value": f"₹{g_target:,.1f}"}
        ])
        st.dataframe(out_table, hide_index=True, use_container_width=True)


# =============================================================================
# TAB 4: SENSITIVITY
# =============================================================================
with tab_sensitivity:
    st.markdown("##### Two-Way Sensitivity Analysis")
    st.write("Target share price sensitivity across varying Cost of Capital (WACC), Terminal Growth Rates (g), and Exit Multiples. Combinations where WACC &le; g are marked N/A.")

    sens_g = val_results['sensitivity_gordon']
    sens_m = val_results['sensitivity_multiple']

    col_hm1, col_hm2 = st.columns(2)
    with col_hm1:
        st.markdown("###### WACC vs. Terminal Growth Rate (g)")
        matrix_g = np.array([[val if val is not None else np.nan for val in row] for row in sens_g['matrix']], dtype=float)
        
        # Prepare clean display text for heatmap cells
        text_g = []
        for row in sens_g['matrix']:
            row_txt = []
            for val in row:
                row_txt.append(f"₹{val:,.0f}" if val is not None else "N/A")
            text_g.append(row_txt)

        fig_hm1 = px.imshow(
            matrix_g,
            x=sens_g['wacc_columns'],
            y=sens_g['growth_rows'],
            labels=dict(x="WACC", y="Terminal Growth (g)", color="Target (₹)"),
            color_continuous_scale="Viridis",
            text_auto=False
        )
        fig_hm1.update_traces(
            text=text_g,
            texttemplate="%{text}",
            textfont={"size": 11, "family": "Inter, sans-serif", "color": "#ffffff"},
            hovertemplate="WACC: %{x}<br>Growth (g): %{y}<br>Target Price: %{text}<extra></extra>"
        )
        apply_market_theme(fig_hm1, height=380, show_legend=False)
        st.plotly_chart(fig_hm1, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

    with col_hm2:
        st.markdown("###### WACC vs. Exit Multiple (EV/EBITDA)")
        matrix_m = np.array(sens_m['matrix'], dtype=float)
        text_m = [[f"₹{val:,.0f}" for val in row] for row in matrix_m]

        fig_hm2 = px.imshow(
            matrix_m,
            x=sens_m['wacc_columns'],
            y=sens_m['multiple_rows'],
            labels=dict(x="WACC", y="Exit Multiple", color="Target (₹)"),
            color_continuous_scale="Viridis",
            text_auto=False
        )
        fig_hm2.update_traces(
            text=text_m,
            texttemplate="%{text}",
            textfont={"size": 11, "family": "Inter, sans-serif", "color": "#ffffff"},
            hovertemplate="WACC: %{x}<br>Exit Multiple: %{y}<br>Target Price: %{text}<extra></extra>"
        )
        apply_market_theme(fig_hm2, height=380, show_legend=False)
        st.plotly_chart(fig_hm2, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})


# =============================================================================
# TAB 5: STATEMENTS
# =============================================================================
with tab_statements:
    st.markdown("##### Statement Metric Explorer")
    
    metric_options = [
        "Revenue (Sales)",
        "Operating Profit (EBITDA)",
        "Operating Margin (OPM %)",
        "EBIT",
        "Profit Before Tax (PBT)",
        "Net Profit (PAT)",
        "Free Cash Flow (FCFF)",
        "Total Borrowings (Debt)",
        "Capital Expenditures (Capex)",
        "Net PP&E (Fixed Assets)"
    ]
    
    selected_metric = st.selectbox("Select Financial Metric to Inspect", options=metric_options, index=0)

    # Metric extraction mapping
    fc_stmt = fc_results['forecast_statements']
    hist_years = fc_results['historical_years']
    future_years = fc_results['future_years']
    pl_df = raw_data['profit_loss']
    bs_df = raw_data['balance_sheet']

    hist_vals = None
    fc_vals = None
    unit_label = "₹ Cr."

    if selected_metric == "Revenue (Sales)":
        hist_vals = [float(pl_df.loc['Sales', y]) if 'Sales' in pl_df.index and y in pl_df.columns else np.nan for y in hist_years]
        fc_vals = fc_stmt['sales']
    elif selected_metric == "Operating Profit (EBITDA)":
        hist_vals = [float(pl_df.loc['Operating Profit', y]) if 'Operating Profit' in pl_df.index and y in pl_df.columns else np.nan for y in hist_years]
        fc_vals = fc_stmt['ebitda']
    elif selected_metric == "Operating Margin (OPM %)":
        hist_vals = [float(str(pl_df.loc['OPM %', y]).replace('%', '')) if 'OPM %' in pl_df.index and y in pl_df.columns else np.nan for y in hist_years]
        fc_vals = fc_stmt['opm_pct']
        unit_label = "%"
    elif selected_metric == "EBIT":
        hist_vals = None
        fc_vals = fc_stmt['ebit']
    elif selected_metric == "Profit Before Tax (PBT)":
        hist_vals = [float(pl_df.loc['Profit before tax', y]) if 'Profit before tax' in pl_df.index and y in pl_df.columns else np.nan for y in hist_years]
        fc_vals = fc_stmt['pbt']
    elif selected_metric == "Net Profit (PAT)":
        hist_vals = [float(pl_df.loc['Net Profit', y]) if 'Net Profit' in pl_df.index and y in pl_df.columns else np.nan for y in hist_years]
        fc_vals = fc_stmt['pat']
    elif selected_metric == "Free Cash Flow (FCFF)":
        hist_vals = None
        fc_vals = fc_stmt['fcff']
    elif selected_metric == "Total Borrowings (Debt)":
        hist_vals = [float(bs_df.loc['Borrowings', y]) if 'Borrowings' in bs_df.index and y in bs_df.columns else np.nan for y in hist_years]
        fc_vals = fc_stmt['debt']
    elif selected_metric == "Capital Expenditures (Capex)":
        hist_vals = None
        fc_vals = fc_stmt['capex']
    elif selected_metric == "Net PP&E (Fixed Assets)":
        hist_vals = [float(bs_df.loc['Fixed Assets', y]) if 'Fixed Assets' in bs_df.index and y in bs_df.columns else np.nan for y in hist_years]
        fc_vals = fc_stmt['fixed_assets']

    fig_metric = go.Figure()
    if hist_vals is not None:
        fig_metric.add_trace(go.Scatter(
            x=hist_years, y=hist_vals, mode='lines+markers', name='Audited Historical',
            line=dict(color='#38bdf8', width=2.8), marker=dict(size=6, color='#38bdf8'),
            hovertemplate=f"FY %{{x}}<br>Actual: %{{y:,.1f}} {unit_label}<extra></extra>"
        ))
        fig_metric.add_trace(go.Scatter(
            x=[hist_years[-1]] + future_years, y=[hist_vals[-1]] + fc_vals, mode='lines+markers', name='Projected Forecast',
            line=dict(color='#818cf8', width=2.5, dash='dash'), marker=dict(size=6, symbol='diamond', color='#818cf8'),
            hovertemplate=f"FY %{{x}}<br>Projected: %{{y:,.1f}} {unit_label}<extra></extra>"
        ))
        fig_metric.add_vline(x=hist_years[-1], line_width=1.5, line_dash="dash", line_color="#64748b")
        fig_metric.add_vrect(
            x0=hist_years[-1], x1=future_years[-1], fillcolor="rgba(56, 189, 248, 0.08)", layer="below", line_width=0,
            annotation_text="Forecast Horizon →", annotation_position="top left", annotation_font=dict(size=11, color="#94a3b8", family="Inter, sans-serif")
        )
    else:
        fig_metric.add_trace(go.Scatter(
            x=future_years, y=fc_vals, mode='lines+markers', name='Projected Forecast',
            line=dict(color='#818cf8', width=2.8), marker=dict(size=6, color='#818cf8'),
            hovertemplate=f"FY %{{x}}<br>Projected: %{{y:,.1f}} {unit_label}<extra></extra>"
        ))

    apply_market_theme(
        fig_metric,
        title=f"{selected_metric} Evolution ({unit_label})",
        height=350,
        show_legend=True,
        xaxis_title="Fiscal Period",
        yaxis_title=f"{selected_metric} ({unit_label})"
    )
    fig_metric.update_xaxes(tickangle=-25)
    st.plotly_chart(fig_metric, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

    # Full 5-Year Statement Table
    st.markdown("##### 5-Year Comprehensive Forecast Statements (₹ Cr.)")
    df_forecast_display = pd.DataFrame({
        "Revenue (Sales)": fc_stmt['sales'],
        "Operating Expenses": fc_stmt['expenses'],
        "EBITDA": fc_stmt['ebitda'],
        "OPM (%)": fc_stmt['opm_pct'],
        "Depreciation & Amortization": fc_stmt['depreciation'],
        "EBIT": fc_stmt['ebit'],
        "Interest Expense": fc_stmt['interest'],
        "Other Income": fc_stmt['other_income'],
        "Profit Before Tax (PBT)": fc_stmt['pbt'],
        "Tax Provision": fc_stmt['tax'],
        "Net Profit (PAT)": fc_stmt['pat'],
        "Net Fixed Assets (PP&E)": fc_stmt['fixed_assets'],
        "Capital Expenditures (Capex)": fc_stmt['capex'],
        "Total Borrowings (Debt)": fc_stmt['debt'],
        "Free Cash Flow (FCFF)": fc_stmt['fcff'],
    }, index=fc_results['future_years']).T

    st.dataframe(df_forecast_display.style.format("{:,.1f}"), use_container_width=True)


# =============================================================================
# TAB 6: EXCEL EXPORT
# =============================================================================
with tab_excel:
    st.markdown("##### Institutional 8-Worksheet Excel Model")
    st.write("Generate and download the formula-linked `.xlsx` workbook containing dynamic statement linkages, working capital schedules, DCF tables, and built-in audit checks.")

    col_l1, col_l2 = st.columns(2)
    with col_l1:
        st.markdown("""
        * **1. Read_Me**: Operational guide, color coding standard, and dynamic integrity checks.
        * **2. Raw_Data**: Audited historical statements extracted verbatim from filings.
        * **3. Historical_Financials**: Standardized historical financials and common-size margin analysis.
        * **4. Assumptions**: Econometric drivers, working capital cycle, and WACC parameters.
        """)
    with col_l2:
        st.markdown("""
        * **5. Forecast**: 5-Year 3-statement forecast with zero hardcoded forecast values.
        * **6. DCF_Valuation**: FCFF discounting, Terminal Value, and Enterprise-to-Equity bridge.
        * **7. Sensitivity_Analysis**: Two-way sensitivity grids for WACC and growth/multiples.
        * **8. Dashboard**: Executive KPI cards, DuPont metrics, and audit check status lights.
        """)

    out_filename = f"{ticker}_Financial_Model.xlsx"
    builder = WorkbookBuilder(raw_data, fc_results, val_results)
    file_bytes = builder.generate_bytes()

    st.download_button(
        label=f"Download {ticker} Financial Model (.xlsx)",
        data=file_bytes,
        file_name=out_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True
    )
    st.caption(f"Status: Workbook successfully compiled ({len(file_bytes)/1024:.1f} KB). Ready for download.")

# -----------------------------------------------------------------------------
# CONCISE INVESTMENT DISCLAIMER
# -----------------------------------------------------------------------------
st.markdown("""
<div class="disclaimer-card">
    <strong>Analytical Model Disclaimer:</strong> This application is an automated quantitative financial modeling tool designed for research and educational purposes. Financial projections and intrinsic valuations are estimated algorithmically from historical public filings and user-defined parameters. Outputs do not constitute registered investment, financial, or legal advice, nor a recommendation to buy or sell any security.
</div>
""", unsafe_allow_html=True)
