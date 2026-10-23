"""
Financial Model & DCF Valuation Screener
Professional TradingView & Bloomberg-inspired dark terminal interface
Featuring Real-time Keystroke Search, Beginner-Friendly Investment Verdicts,
Jargon Busters, Multi-Source Market Hub, and Real-Time News Sentiment Modeling.
"""

import os
import sys
import io
import re
import urllib.parse
from typing import Dict, Any, List, Optional

# Prioritize current application directory in sys.path for Streamlit Cloud
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import streamlit as st
import pandas as pd
import numpy as np
import requests
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
    from news_sentiment_engine import NewsSentimentEngine
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
    from src.news.news_sentiment_engine import NewsSentimentEngine

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
    
    .block-container {
        padding-top: 1.0rem;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 1440px;
    }

    .terminal-header {
        border-bottom: 1px solid #21262d;
        padding-bottom: 0.8rem;
        margin-bottom: 1.0rem;
    }
    .company-title-row {
        display: flex;
        align-items: baseline;
        gap: 10px;
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
    .external-hub-link {
        font-size: 0.8rem;
        color: #58a6ff;
        text-decoration: none;
        background: rgba(88, 166, 255, 0.1);
        padding: 3px 8px;
        border-radius: 4px;
        border: 1px solid rgba(88, 166, 255, 0.2);
        margin-right: 6px;
    }
    .external-hub-link:hover {
        background: rgba(88, 166, 255, 0.2);
        color: #79c0ff;
    }
    .company-meta {
        font-size: 0.8rem;
        color: #8b949e;
        margin-top: 5px;
    }

    /* Beginner verdict cards */
    .verdict-box-buy {
        background: rgba(63, 185, 80, 0.12);
        border: 1.5px solid #3fb950;
        border-radius: 8px;
        padding: 18px 20px;
        margin-bottom: 1.2rem;
    }
    .verdict-box-hold {
        background: rgba(210, 153, 34, 0.12);
        border: 1.5px solid #d29922;
        border-radius: 8px;
        padding: 18px 20px;
        margin-bottom: 1.2rem;
    }
    .verdict-box-sell {
        background: rgba(248, 81, 73, 0.12);
        border: 1.5px solid #f85149;
        border-radius: 8px;
        padding: 18px 20px;
        margin-bottom: 1.2rem;
    }
    .verdict-title {
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .verdict-desc {
        font-size: 0.95rem;
        color: #c9d1d9;
        line-height: 1.5;
    }

    /* Scorecard cells */
    .score-cell {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 12px 14px;
        margin-bottom: 10px;
    }
    .score-title {
        font-size: 0.78rem;
        color: #8b949e;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.04em;
    }
    .score-val {
        font-size: 1.1rem;
        font-weight: 700;
        color: #f0f6fc;
        margin-top: 3px;
    }
    .score-sub {
        font-size: 0.8rem;
        color: #8b949e;
        margin-top: 2px;
    }

    /* News card container */
    .news-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 14px 16px;
        margin-bottom: 12px;
    }
    .news-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #f0f6fc;
        margin-bottom: 6px;
        line-height: 1.4;
    }
    .news-meta {
        font-size: 0.78rem;
        color: #8b949e;
        margin-bottom: 8px;
    }
    .badge-pos {
        color: #3fb950;
        background: rgba(63, 185, 80, 0.15);
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .badge-neg {
        color: #f85149;
        background: rgba(248, 81, 73, 0.15);
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .badge-neu {
        color: #8b949e;
        background: rgba(139, 148, 158, 0.15);
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .badge-cat {
        color: #58a6ff;
        background: rgba(56, 189, 248, 0.12);
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 500;
        margin-left: 6px;
    }
    .news-link {
        font-size: 0.8rem;
        color: #58a6ff;
        text-decoration: none;
        font-weight: 500;
    }

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
# PRELOADED INSTANT SEARCH CATALOG (Top 70+ Popular Indian Equities)
# -----------------------------------------------------------------------------
POPULAR_STOCKS = [
    ("Tata Steel", "TATASTEEL", "https://www.screener.in/company/TATASTEEL/consolidated/"),
    ("Tata Motors", "TATAMOTORS", "https://www.screener.in/company/TATAMOTORS/consolidated/"),
    ("Tata Consultancy Services (TCS)", "TCS", "https://www.screener.in/company/TCS/"),
    ("Tata Power", "TATAPOWER", "https://www.screener.in/company/TATAPOWER/consolidated/"),
    ("Tata Consumer Products", "TATACONSUM", "https://www.screener.in/company/TATACONSUM/consolidated/"),
    ("Reliance Industries", "RELIANCE", "https://www.screener.in/company/RELIANCE/consolidated/"),
    ("Infosys", "INFY", "https://www.screener.in/company/INFY/consolidated/"),
    ("Hindustan Unilever (HUL)", "HINDUNILVR", "https://www.screener.in/company/HINDUNILVR/"),
    ("ITC", "ITC", "https://www.screener.in/company/ITC/consolidated/"),
    ("HDFC Bank", "HDFCBANK", "https://www.screener.in/company/HDFCBANK/consolidated/"),
    ("ICICI Bank", "ICICIBANK", "https://www.screener.in/company/ICICIBANK/consolidated/"),
    ("State Bank of India (SBI)", "SBIN", "https://www.screener.in/company/SBIN/"),
    ("Bharti Airtel", "BHARTIARTL", "https://www.screener.in/company/BHARTIARTL/consolidated/"),
    ("Larsen & Toubro (L&T)", "LT", "https://www.screener.in/company/LT/consolidated/"),
    ("Bajaj Finance", "BAJFINANCE", "https://www.screener.in/company/BAJFINANCE/consolidated/"),
    ("Asian Paints", "ASIANPAINT", "https://www.screener.in/company/ASIANPAINT/consolidated/"),
    ("Maruti Suzuki", "MARUTI", "https://www.screener.in/company/MARUTI/consolidated/"),
    ("Sun Pharma", "SUNPHARMA", "https://www.screener.in/company/SUNPHARMA/consolidated/"),
    ("Titan Company", "TITAN", "https://www.screener.in/company/TITAN/consolidated/"),
    ("Zomato (Eternal)", "ETERNAL", "https://www.screener.in/company/ETERNAL/consolidated/"),
    ("Adani Enterprises", "ADANIENT", "https://www.screener.in/company/ADANIENT/consolidated/"),
    ("Adani Ports", "ADANIPORTS", "https://www.screener.in/company/ADANIPORTS/consolidated/"),
    ("Adani Green Energy", "ADANIGREEN", "https://www.screener.in/company/ADANIGREEN/consolidated/"),
    ("Adani Power", "ADANIPOWER", "https://www.screener.in/company/ADANIPOWER/consolidated/"),
    ("Wipro", "WIPRO", "https://www.screener.in/company/WIPRO/consolidated/"),
    ("HCL Technologies", "HCLTECH", "https://www.screener.in/company/HCLTECH/consolidated/"),
    ("Tech Mahindra", "TECHM", "https://www.screener.in/company/TECHM/consolidated/"),
    ("NTPC", "NTPC", "https://www.screener.in/company/NTPC/consolidated/"),
    ("Power Grid Corporation", "POWERGRID", "https://www.screener.in/company/POWERGRID/consolidated/"),
    ("ONGC", "ONGC", "https://www.screener.in/company/ONGC/consolidated/"),
    ("Coal India", "COALINDIA", "https://www.screener.in/company/COALINDIA/consolidated/"),
    ("Jindal Steel & Power", "JINDALSTEL", "https://www.screener.in/company/JINDALSTEL/consolidated/"),
    ("JSW Steel", "JSWSTEEL", "https://www.screener.in/company/JSWSTEEL/consolidated/"),
    ("Vedanta", "VEDL", "https://www.screener.in/company/VEDL/consolidated/"),
    ("Hindalco Industries", "HINDALCO", "https://www.screener.in/company/HINDALCO/consolidated/"),
    ("UltraTech Cement", "ULTRACEMCO", "https://www.screener.in/company/ULTRACEMCO/consolidated/"),
    ("Grasim Industries", "GRASIM", "https://www.screener.in/company/GRASIM/consolidated/"),
    ("Cipla", "CIPLA", "https://www.screener.in/company/CIPLA/consolidated/"),
    ("Dr Reddys Labs", "DRREDDY", "https://www.screener.in/company/DRREDDY/consolidated/"),
    ("Divis Laboratories", "DIVISLAB", "https://www.screener.in/company/DIVISLAB/consolidated/"),
    ("Apollo Hospitals", "APOLLOHOSP", "https://www.screener.in/company/APOLLOHOSP/consolidated/"),
    ("Eicher Motors", "EICHERMOT", "https://www.screener.in/company/EICHERMOT/consolidated/"),
    ("Mahindra & Mahindra (M&M)", "M&M", "https://www.screener.in/company/M&M/consolidated/"),
    ("Hero MotoCorp", "HEROMOTOCO", "https://www.screener.in/company/HEROMOTOCO/consolidated/"),
    ("Bajaj Auto", "BAJAJ-AUTO", "https://www.screener.in/company/BAJAJ-AUTO/consolidated/"),
    ("Nestle India", "NESTLEIND", "https://www.screener.in/company/NESTLEIND/"),
    ("Britannia Industries", "BRITANNIA", "https://www.screener.in/company/BRITANNIA/consolidated/"),
    ("Dabur India", "DABUR", "https://www.screener.in/company/DABUR/consolidated/"),
    ("Godrej Consumer Products", "GODREJCP", "https://www.screener.in/company/GODREJCP/consolidated/"),
    ("Marico", "MARICO", "https://www.screener.in/company/MARICO/consolidated/"),
    ("Pidilite Industries", "PIDILITIND", "https://www.screener.in/company/PIDILITIND/consolidated/"),
    ("Havells India", "HAVELLS", "https://www.screener.in/company/HAVELLS/consolidated/"),
    ("Siemens India", "SIEMENS", "https://www.screener.in/company/SIEMENS/"),
    ("ABB India", "ABB", "https://www.screener.in/company/ABB/"),
    ("Bharat Electronics (BEL)", "BEL", "https://www.screener.in/company/BEL/consolidated/"),
    ("Hindustan Aeronautics (HAL)", "HAL", "https://www.screener.in/company/HAL/consolidated/"),
    ("DLF", "DLF", "https://www.screener.in/company/DLF/consolidated/"),
    ("Trent", "TRENT", "https://www.screener.in/company/TRENT/consolidated/"),
    ("DMart (Avenue Supermarts)", "DMART", "https://www.screener.in/company/DMART/consolidated/"),
    ("Jio Financial Services", "JIOFIN", "https://www.screener.in/company/JIOFIN/consolidated/"),
    ("Varun Beverages (VBL)", "VBL", "https://www.screener.in/company/VBL/consolidated/"),
    ("Polycab India", "POLYCAB", "https://www.screener.in/company/POLYCAB/consolidated/"),
    ("Suzlon Energy", "SUZLON", "https://www.screener.in/company/SUZLON/consolidated/"),
    ("BHEL", "BHEL", "https://www.screener.in/company/BHEL/consolidated/"),
    ("IRCTC", "IRCTC", "https://www.screener.in/company/IRCTC/consolidated/"),
    ("RVNL", "RVNL", "https://www.screener.in/company/RVNL/consolidated/"),
    ("REC Ltd", "RECLTD", "https://www.screener.in/company/RECLTD/consolidated/"),
    ("PFC Ltd", "PFC", "https://www.screener.in/company/PFC/consolidated/"),
    ("IOCL (Indian Oil)", "IOC", "https://www.screener.in/company/IOC/consolidated/"),
    ("BPCL", "BPCL", "https://www.screener.in/company/BPCL/consolidated/"),
    ("GAIL India", "GAIL", "https://www.screener.in/company/GAIL/consolidated/")
]

STOCK_MAP = {f"{name} ({ticker})": url for name, ticker, url in POPULAR_STOCKS}


# -----------------------------------------------------------------------------
# DYNAMIC ONLINE SEARCH API (For Any Other Listed Indian Company)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=900, show_spinner=False)
def search_screener_api(query: str) -> List[Dict[str, str]]:
    if not query or len(query.strip()) < 2:
        return []
    try:
        url = f"https://www.screener.in/api/company/search/?q={urllib.parse.quote(query.strip())}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            res = []
            for item in r.json():
                raw_path = item.get('url', '').strip()
                t_match = re.search(r'/company/([^/]+)/', raw_path)
                ticker_str = t_match.group(1) if t_match else ""
                res.append({
                    'display': f"{item.get('name', '')} ({ticker_str})",
                    'url': f"https://www.screener.in{raw_path}"
                })
            return res
    except Exception:
        pass
    return []


# -----------------------------------------------------------------------------
# SIDEBAR: INSTANT KEYSTROKE AUTOCOMPLETE & ADVANCED SETTINGS
# -----------------------------------------------------------------------------
st.sidebar.markdown("<div class='sidebar-section-title'>Company Search</div>", unsafe_allow_html=True)

# Instant searchable dropdown with 70+ preloaded popular stocks (updates on keystroke!)
stock_choice = st.sidebar.selectbox(
    "Type or Select Company (Instant Suggestions)",
    options=list(STOCK_MAP.keys()),
    index=0,
    help="Click and start typing any letters (e.g., 'tata', 'rel', 'inf', 'zom', 'ada') to see real-time suggestions!"
)
active_url = STOCK_MAP[stock_choice]

# Expander to search any of the 5,000+ unlisted or micro-cap companies
with st.sidebar.expander("Search Other 5,000+ Indian Stocks", expanded=False):
    custom_query = st.text_input("Enter company name or ticker", value="", placeholder="e.g. Suzlon, Kaynes...")
    if custom_query:
        api_results = search_screener_api(custom_query)
        if api_results:
            api_opts = [r['display'] for r in api_results]
            chosen_api = st.selectbox("Search Results", options=api_opts)
            matched_obj = next((r for r in api_results if r['display'] == chosen_api), None)
            if matched_obj:
                active_url = matched_obj['url']
        else:
            st.caption("No matching listed stocks found on Screener.")
    
    direct_link = st.text_input("Or paste direct Screener URL", value="", placeholder="https://www.screener.in/company/...")
    if direct_link.strip():
        active_url = direct_link.strip()

with st.sidebar.expander("Valuation Assumptions (Pro)", expanded=False):
    rf_rate = st.slider("Risk-Free Rate (Rf)", min_value=5.0, max_value=9.0, value=7.0, step=0.1, format="%.1f%%") / 100.0
    erp = st.slider("Equity Risk Premium (ERP)", min_value=4.0, max_value=8.0, value=5.5, step=0.1, format="%.1f%%") / 100.0
    beta_val = st.slider("Beta (β)", min_value=0.4, max_value=2.0, value=1.0, step=0.05)
    term_g = st.slider("Terminal Growth Rate (g)", min_value=2.5, max_value=6.0, value=4.5, step=0.25, format="%.2f%%") / 100.0

st.sidebar.markdown("---")
st.sidebar.caption("💡 **Tip**: In the top search box, simply click and type letters to filter instantly!")


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


@st.cache_data(show_spinner=False, ttl=1800)
def fetch_news_and_catalysts(c_name: str, ticker_sym: str, base_target: float, wacc: float):
    news_engine = NewsSentimentEngine()
    articles = news_engine.fetch_company_news(c_name, ticker_sym, max_items=12)
    impact = news_engine.evaluate_catalyst_impact(articles, base_target, wacc)
    return articles, impact


# -----------------------------------------------------------------------------
# MAIN APP EXECUTION
# -----------------------------------------------------------------------------
with st.spinner("Extracting company data and calculating valuation..."):
    try:
        raw_data, fc_results, val_results = fetch_and_compute(active_url, rf_rate, erp, beta_val, term_g)
    except Exception as e:
        st.error(f"Error analyzing company: {str(e)}")
        st.info("Please select another company or verify the URL in the sidebar.")
        st.stop()

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

# Live News & Sentiment Catalysts
articles, catalyst_impact = fetch_news_and_catalysts(company_name, ticker, fair_target, wacc_pct)

# External Financial Hub Links
tv_link = f"https://in.tradingview.com/symbols/NSE-{ticker}/"
gf_link = f"https://www.google.com/finance/quote/{ticker}:NSE"
mc_link = f"https://www.moneycontrol.com/india/stockpricequote/"
bse_link = f"https://www.bseindia.com/corporates/ann.html"

# Top Header with Multi-Source Hub
st.markdown(f"""
<div class="terminal-header">
    <div class="company-title-row">
        <h1 class="company-name">{company_name}</h1>
        <span class="company-ticker">{ticker}</span>
        <span class="company-sector">{sector}</span>
        <div style="margin-left: auto; display: flex; gap: 6px; flex-wrap: wrap;">
            <a href="{tv_link}" target="_blank" class="external-hub-link">📈 TradingView Chart ↗</a>
            <a href="{gf_link}" target="_blank" class="external-hub-link">📊 Google Finance ↗</a>
            <a href="{mc_link}" target="_blank" class="external-hub-link">💼 Moneycontrol ↗</a>
            <a href="{bse_link}" target="_blank" class="external-hub-link">🏛️ BSE Announcements ↗</a>
        </div>
    </div>
    <div class="company-meta">
        Primary Source: {prov.get('source_url', active_url)} &bull; Reporting Scope: {prov.get('reporting_type', 'Audited')}
    </div>
</div>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# BEGINNER VS. PRO ANALYST MODE SWITCHER
# -----------------------------------------------------------------------------
col_mode1, col_mode2 = st.columns([3, 1])
with col_mode1:
    view_mode = st.radio(
        "Choose Your View Mode",
        ["💡 Beginner Mode (Simple Verdicts, Plain English & Quick Suggestions)", "🔬 Pro Analyst Mode (Full DCF Statements, Multiples & Formulas)"],
        horizontal=True
    )

st.markdown("---")


# =============================================================================
# VIEW 1: BEGINNER-FRIENDLY INVESTMENT SUITE
# =============================================================================
if "Beginner" in view_mode:
    # 1. Plain-English Bottom-Line Investment Verdict
    diff_val = fair_target - cmp
    diff_pct = ((fair_target / max(1.0, cmp)) - 1.0) * 100.0

    if diff_pct >= 15.0:
        box_class = "verdict-box-buy"
        verdict_badge = "🟢 UNDERVALUED (Attractive Margin of Safety)"
        verdict_action = "Good Buying Opportunity"
        verdict_color = "#3fb950"
        plain_summary = (
            f"If you buy 1 share today at **₹{cmp:,.1f}**, our valuation models estimate the genuine business cash flow is worth **₹{fair_target:,.1f}**. "
            f"You are getting an estimated **{diff_pct:.1f}% discount (Margin of Safety)**. In simple terms: the stock is currently on sale relative to its business earning power."
        )
    elif diff_pct >= -5.0:
        box_class = "verdict-box-hold"
        verdict_badge = "🟡 FAIRLY VALUED (Fair Market Price)"
        verdict_action = "Hold / Accumulate on Dips"
        verdict_color = "#d29922"
        plain_summary = (
            f"The stock is trading at **₹{cmp:,.1f}**, which is very close to its estimated true fair value of **₹{fair_target:,.1f}** ({diff_pct:+.1f}%). "
            f"It is neither extremely cheap nor dangerously overpriced. Existing investors can hold, and new buyers should consider waiting for minor market corrections."
        )
    else:
        box_class = "verdict-box-sell"
        verdict_badge = "🔴 OVERVALUED (Priced at a Premium)"
        verdict_action = "Wait for Correction / Avoid FOMO"
        verdict_color = "#f85149"
        plain_summary = (
            f"The stock price of **₹{cmp:,.1f}** is trading above our estimated fair business value of **₹{fair_target:,.1f}** ({diff_pct:.1f}% premium). "
            f"Investors have priced in heavy future growth expectations. There is a higher risk of price drop if future earnings fall short of expectations."
        )

    st.markdown(f"""
    <div class="{box_class}">
        <div class="verdict-title" style="color: {verdict_color};">{verdict_badge} &bull; Suggested Action: {verdict_action}</div>
        <div class="verdict-desc">{plain_summary}</div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Beginner Traffic Light Scorecard (4 Core Pillars)
    st.markdown("##### 🚦 Beginner's 4-Pillar Health Scorecard")
    st.write("Before investing, check these 4 simple traffic lights to see if the stock meets the basic rules of sound investing:")

    sc_cols = st.columns(4)
    # Pillar 1: Valuation
    with sc_cols[0]:
        val_status = "Discount Available" if diff_pct > 10 else ("Fairly Priced" if diff_pct >= -10 else "Expensive")
        val_icon = "🟢" if diff_pct > 10 else ("🟡" if diff_pct >= -10 else "🔴")
        st.markdown(f"""
        <div class="score-cell">
            <div class="score-title">1. Valuation Check</div>
            <div class="score-val">{val_icon} {val_status}</div>
            <div class="score-sub">Fair Value: ₹{fair_target:,.1f} vs CMP: ₹{cmp:,.1f}</div>
        </div>
        """, unsafe_allow_html=True)

    # Pillar 2: Profitability & Returns (ROCE)
    roce_num = float(str(kpis.get('ROCE', '0')).replace('%', '') or 0)
    with sc_cols[1]:
        roce_status = "High Quality (>15%)" if roce_num >= 15 else ("Moderate (10-15%)" if roce_num >= 10 else "Low Return (<10%)")
        roce_icon = "🟢" if roce_num >= 15 else ("🟡" if roce_num >= 10 else "🔴")
        st.markdown(f"""
        <div class="score-cell">
            <div class="score-title">2. Business Quality (ROCE)</div>
            <div class="score-val">{roce_icon} {roce_num:.1f}%</div>
            <div class="score-sub">{roce_status} on invested money</div>
        </div>
        """, unsafe_allow_html=True)

    # Pillar 3: Debt & Financial Safety
    debt_val = float(val_results['valuation_bridge']['total_debt_cr'])
    with sc_cols[2]:
        debt_ratio = (debt_val / max(1.0, mcap)) * 100.0
        debt_status = "Virtually Debt-Free" if debt_ratio < 15 else ("Moderate Debt" if debt_ratio < 50 else "High Borrowings")
        debt_icon = "🟢" if debt_ratio < 15 else ("🟡" if debt_ratio < 50 else "🔴")
        st.markdown(f"""
        <div class="score-cell">
            <div class="score-title">3. Debt & Loan Safety</div>
            <div class="score-val">{debt_icon} {debt_status}</div>
            <div class="score-sub">Total Debt: ₹{debt_val:,.0f} Cr ({debt_ratio:.0f}% of Mcap)</div>
        </div>
        """, unsafe_allow_html=True)

    # Pillar 4: Live Market & News Sentiment
    cat_score = catalyst_impact['catalyst_score']
    with sc_cols[3]:
        news_status = "Positive Tailwinds" if cat_score > 10 else ("Negative Headwinds" if cat_score < -10 else "Neutral News")
        news_icon = "🟢" if cat_score > 10 else ("🔴" if cat_score < -10 else "🟡")
        st.markdown(f"""
        <div class="score-cell">
            <div class="score-title">4. Market News Sentiment</div>
            <div class="score-val">{news_icon} {news_status}</div>
            <div class="score-sub">Score: {cat_score:+.0f}% across recent headlines</div>
        </div>
        """, unsafe_allow_html=True)

    # 3. Simple Visual: Target Price vs CMP
    st.markdown("##### 🎯 Simple Price Target Bar")
    fig_simple = go.Figure()
    fig_simple.add_trace(go.Bar(
        y=["What It's Worth (Fair Value)", "What You Pay (Current Price)"],
        x=[fair_target, cmp],
        orientation="h",
        marker=dict(color=["#3fb950" if diff_pct >= 0 else "#f85149", "#58a6ff"]),
        text=[f"₹{fair_target:,.1f} (Fair Value)", f"₹{cmp:,.1f} (Current Price)"],
        textposition="inside",
        textfont=dict(color="#ffffff", size=13, family="Inter, sans-serif"),
        hovertemplate="<b>%{y}</b>: ₹%{x:,.1f}<extra></extra>"
    ))
    apply_market_theme(fig_simple, height=200, show_legend=False, xaxis_title="Price Per Share (₹)")
    st.plotly_chart(fig_simple, use_container_width=True, config={'displayModeBar': False})

    # 4. Practical Newbie Advice Checklist
    col_chk1, col_chk2 = st.columns(2)
    with col_chk1:
        st.markdown("##### 📌 3 Simple Rules for Investing in this Stock")
        st.markdown("""
        * **1. Don't Put All Money at Once**: Always use **Staggered Buying (SIP)** over 3 to 6 months rather than investing your entire capital in a single day.
        * **2. Diversification Rule**: Never invest more than **5% to 10%** of your total portfolio into any single company, no matter how good it looks.
        * **3. Long-Term Horizon**: Fair values materialize over **2 to 5 years**. Do not treat this as day-trading tips or instant lottery tickets.
        """)
    with col_chk2:
        st.markdown("##### 📰 Latest News Key Takeaways (In Simple Words)")
        for b in catalyst_impact.get('summary_bullets', []):
            st.markdown(f"- {b}")

    # 5. Interactive Jargon Buster ("Explain Like I'm 15")
    with st.expander("❓ Jargon Buster — What do these finance terms mean in plain English?", expanded=False):
        st.markdown("""
        * **Current Market Price (CMP)**: The exact price you pay on your broker app (Zerodha, Groww, Angel One) right now to buy 1 share.
        * **Fair Value / Intrinsic Target**: What the company is *actually* worth based on the real cash profits it generates. Think of it like assessing the genuine value of a rental apartment based on its yearly rent collection.
        * **Margin of Safety**: Buying something for less than it's worth. If a ₹100 shirt is sold for ₹80, you have a 20% margin of safety.
        * **ROCE (Return on Capital Employed)**: Tells you how smart the management is at turning money into profit. Above **15%** is generally considered a strong wealth creator!
        * **P/E Ratio (Price-to-Earnings)**: How many rupees investors are willing to pay for every ₹1 of profit the company makes. Lower usually means cheaper, but quality companies often command higher P/E.
        * **Debt-to-Equity**: Measures how much the company relies on borrowed bank loans versus its own money. Low debt protects you during bad economic times.
        * **DCF (Discounted Cash Flow)**: The gold standard Wall Street mathematical formula that calculates a company's total future cash earnings and converts them into today's rupees.
        """)


# =============================================================================
# VIEW 2: PRO ANALYST SUITE (Full Institutional Capabilities)
# =============================================================================
else:
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

    tab_overview, tab_news, tab_forecast, tab_valuation, tab_sensitivity, tab_statements, tab_excel = st.tabs([
        "Overview", "News & Catalysts", "Forecast", "Valuation", "Sensitivity", "Statements", "Excel Export"
    ])

    # Tab: Overview
    with tab_overview:
        methods = ["Exit Multiple Method", "Gordon Growth Method", "Blended Fair Value"]
        targets = [m_target, g_target, fair_target]
        upsides = [m_upside, g_upside, fair_upside]
        bar_colors = ["#38bdf8", "#34d399", "#818cf8"]

        fig_val_comp = go.Figure()
        fig_val_comp.add_trace(go.Bar(
            y=methods, x=targets, orientation="h",
            marker=dict(color=bar_colors, line=dict(color="#1e222d", width=1.5)),
            text=[f"₹{t:,.1f} ({'+' if u >= 0 else ''}{u:.1f}%)" for t, u in zip(targets, upsides)],
            textposition="inside", insidetextanchor="middle",
            textfont=dict(color="#ffffff", size=12, family="Inter, sans-serif"),
            hovertemplate="<b>%{y}</b><br>Target Price: ₹%{x:,.1f}<extra></extra>"
        ))
        if cmp > 0:
            fig_val_comp.add_vline(x=cmp, line_width=2.5, line_dash="dash", line_color="#f43f5e", annotation_text=f"CMP: ₹{cmp:,.1f}", annotation_position="top right")
        apply_market_theme(fig_val_comp, title="DCF Target Price Comparison vs. Current Market Price (CMP)", height=260, show_legend=False, xaxis_title="Price Per Share (₹)")
        st.plotly_chart(fig_val_comp, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

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

    # Tab: News & Catalysts
    with tab_news:
        st.markdown("##### Real-Time News Catalysts & Market Impact Model")
        cat_score = catalyst_impact['catalyst_score']
        bias_desc = catalyst_impact['sentiment_bias']
        adj_target = catalyst_impact['sentiment_adjusted_target']
        price_impact = catalyst_impact['price_impact_pct']
        rev_impact = catalyst_impact['revenue_growth_impact_pct']
        wacc_adj = catalyst_impact['wacc_impact_bps']

        col_cat1, col_cat2, col_cat3, col_cat4 = st.columns(4)
        with col_cat1:
            st.metric("Catalyst Sentiment Score", f"{cat_score:+.1f}%", delta=catalyst_impact['bias_tag'])
        with col_cat2:
            st.metric("Base DCF Fair Value", f"₹{fair_target:,.1f}")
        with col_cat3:
            st.metric("Sentiment-Adjusted Fair Value", f"₹{adj_target:,.1f}", delta=f"{price_impact:+.1f}%")
        with col_cat4:
            st.metric("Predicted Bias", bias_desc.split()[0], delta=f"Growth {rev_impact:+.1f}% | WACC {wacc_adj:+.0f}bps")

        fig_cat_comp = go.Figure()
        cat_methods = ["Current Market Price (CMP)", "Base DCF Fair Value", "Sentiment-Adjusted Fair Value"]
        cat_vals = [cmp, fair_target, adj_target]
        cat_colors = ["#f43f5e", "#38bdf8", "#34d399" if adj_target >= fair_target else "#fbbf24"]

        fig_cat_comp.add_trace(go.Bar(
            y=cat_methods, x=cat_vals, orientation="h",
            marker=dict(color=cat_colors, line=dict(color="#1e222d", width=1.5)),
            text=[f"₹{v:,.1f}" for v in cat_vals],
            textposition="inside", insidetextanchor="middle",
            textfont=dict(color="#ffffff", size=12, family="Inter, sans-serif"),
            hovertemplate="<b>%{y}</b>: ₹%{x:,.1f}<extra></extra>"
        ))
        apply_market_theme(fig_cat_comp, title="Market Price vs. Unadjusted DCF vs. News Catalyst Adjusted Fair Value", height=240, show_legend=False, xaxis_title="Price Per Share (₹)")
        st.plotly_chart(fig_cat_comp, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

        st.markdown("###### Catalyst Model Key Takeaways")
        for b in catalyst_impact.get('summary_bullets', []):
            st.markdown(f"- {b}")

        st.markdown("---")
        st.markdown("##### Curated Real-Time Financial News Stream")
        if not articles:
            st.info("No recent financial news articles were retrieved for this ticker.")
        else:
            filter_col, _ = st.columns([2, 4])
            with filter_col:
                news_filter = st.selectbox("Filter News by Sentiment", ["All Articles", "Positive / Tailwinds", "Negative / Headwinds", "Neutral"], index=0)

            for art in articles:
                if news_filter == "Positive / Tailwinds" and art['sentiment_label'] != "Positive":
                    continue
                if news_filter == "Negative / Headwinds" and art['sentiment_label'] != "Negative":
                    continue
                if news_filter == "Neutral" and art['sentiment_label'] != "Neutral":
                    continue

                badge_html = (
                    '<span class="badge-pos">● Positive Tailwinds</span>' if art['sentiment_label'] == 'Positive'
                    else ('<span class="badge-neg">● Negative Headwinds</span>' if art['sentiment_label'] == 'Negative'
                    else '<span class="badge-neu">● Neutral</span>')
                )
                cat_html = f'<span class="badge-cat">{art["catalyst"]}</span>'
                st.markdown(f"""
                <div class="news-card">
                    <div class="news-title">{art['title']}</div>
                    <div class="news-meta">Source: <strong>{art['source']}</strong> &bull; {art['pub_date']} &bull; {badge_html} {cat_html}</div>
                    <div><a href="{art['link']}" target="_blank" class="news-link">Read Full Coverage on {art['source']} ↗</a></div>
                </div>
                """, unsafe_allow_html=True)

    # Tab: Forecast
    with tab_forecast:
        hist_years = fc_results['historical_years']
        future_years = fc_results['future_years']
        pl_df = raw_data['profit_loss']
        sales_hist = [float(pl_df.loc['Sales', y]) if 'Sales' in pl_df.index and y in pl_df.columns else 0.0 for y in hist_years]
        ebitda_hist = [float(pl_df.loc['Operating Profit', y]) if 'Operating Profit' in pl_df.index and y in pl_df.columns else 0.0 for y in hist_years]
        sales_fc = fc_results['forecast_statements']['sales']
        ebitda_fc = fc_results['forecast_statements']['ebitda']
        fcff_fc = fc_results['forecast_statements']['fcff']

        st.markdown("##### Historical vs. Forecast Trajectory (Revenue, EBITDA & FCFF)")
        fig_traj = go.Figure()
        fig_traj.add_trace(go.Scatter(x=hist_years, y=sales_hist, mode='lines+markers', name='Revenue (Actual)', line=dict(color='#38bdf8', width=2.8), marker=dict(size=6, color='#38bdf8')))
        fig_traj.add_trace(go.Scatter(x=[hist_years[-1]] + future_years, y=[sales_hist[-1]] + sales_fc, mode='lines+markers', name='Revenue (Forecast)', line=dict(color='#60a5fa', width=2.5, dash='dash'), marker=dict(size=6, symbol='diamond', color='#60a5fa')))
        fig_traj.add_trace(go.Scatter(x=hist_years, y=ebitda_hist, mode='lines+markers', name='EBITDA (Actual)', line=dict(color='#10b981', width=2.2), marker=dict(size=5, color='#10b981')))
        fig_traj.add_trace(go.Scatter(x=[hist_years[-1]] + future_years, y=[ebitda_hist[-1]] + ebitda_fc, mode='lines+markers', name='EBITDA (Forecast)', line=dict(color='#34d399', width=2.0, dash='dash'), marker=dict(size=5, symbol='diamond', color='#34d399')))
        fig_traj.add_trace(go.Scatter(x=future_years, y=fcff_fc, mode='lines+markers', name='FCFF (Forecast)', line=dict(color='#c084fc', width=2.2, dash='dot'), marker=dict(size=6, symbol='triangle-up', color='#c084fc')))
        fig_traj.add_vline(x=hist_years[-1], line_width=1.5, line_dash="dash", line_color="#64748b")
        fig_traj.add_vrect(x0=hist_years[-1], x1=future_years[-1], fillcolor="rgba(56, 189, 248, 0.08)", layer="below", line_width=0, annotation_text="Forecast Horizon →", annotation_position="top left", annotation_font=dict(size=11, color="#94a3b8", family="Inter, sans-serif"))
        apply_market_theme(fig_traj, height=400, show_legend=True, xaxis_title="Fiscal Period", yaxis_title="Amount (₹ Cr.)")
        fig_traj.update_xaxes(tickangle=-25)
        st.plotly_chart(fig_traj, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

        st.markdown("##### Revenue Scenario Analysis (Base vs. Bull vs. Bear)")
        sales_bull = fc_results['scenarios']['bull']['sales']
        sales_bear = fc_results['scenarios']['bear']['sales']
        fig_scen = go.Figure()
        fig_scen.add_trace(go.Scatter(x=future_years, y=sales_bull, mode='lines+markers', name='Bull Case (+0.5σ)', line=dict(color='#22c55e', width=2.0, dash='dot'), marker=dict(size=6, color='#22c55e')))
        fig_scen.add_trace(go.Scatter(x=future_years, y=sales_bear, mode='lines+markers', name='Bear Case (-0.5σ)', line=dict(color='#f43f5e', width=2.0, dash='dot'), marker=dict(size=6, color='#f43f5e'), fill='tonexty', fillcolor='rgba(56, 189, 248, 0.1)'))
        fig_scen.add_trace(go.Scatter(x=future_years, y=sales_fc, mode='lines+markers', name='Base Case', line=dict(color='#38bdf8', width=3.0), marker=dict(size=8, color='#38bdf8')))
        y_all = sales_bull + sales_bear + sales_fc
        y_min, y_max = min(y_all), max(y_all)
        y_padding = max(100.0, (y_max - y_min) * 0.35)
        apply_market_theme(fig_scen, height=360, show_legend=True, xaxis_title="Forecast Fiscal Period", yaxis_title="Sales (₹ Cr.)")
        fig_scen.update_layout(yaxis=dict(range=[max(0.0, y_min - y_padding), y_max + y_padding]))
        st.plotly_chart(fig_scen, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

    # Tab: Valuation
    with tab_valuation:
        if g_data.get('high_tv_warning', False):
            st.warning(f"Terminal Value represents **{g_data['tv_percent_of_ev']}%** of Enterprise Value. Valuation results are highly sensitive to Terminal Growth ({g_data['terminal_growth_pct']}%) and WACC ({wacc_pct}%).")
        st.markdown("##### Enterprise Value to Equity Value Bridge")
        cum_fcf = val_results['valuation_bridge']['cumulative_pv_fcff_cr']
        pv_tv = g_data['pv_terminal_value_cr']
        ev = g_data['enterprise_value_cr']
        cash = val_results['valuation_bridge']['cash_and_investments_cr']
        debt = val_results['valuation_bridge']['total_debt_cr']
        eq_val = g_data['implied_equity_value_cr']

        fig_wf = go.Figure(go.Waterfall(
            name="Bridge", orientation="v", measure=["relative", "relative", "total", "relative", "relative", "total"],
            x=["PV of 5-Yr FCFF", "PV of Terminal Value", "Enterprise Value", "(+) Cash & Inv.", "(-) Total Debt", "Equity Value"],
            textposition="inside", insidetextanchor="middle",
            textfont=dict(color="#ffffff", size=12, family="Inter, sans-serif"),
            text=[f"₹{cum_fcf:,.0f}", f"₹{pv_tv:,.0f}", f"₹{ev:,.0f}", f"₹{cash:,.0f}", f"-₹{debt:,.0f}", f"₹{eq_val:,.0f}"],
            y=[cum_fcf, pv_tv, ev, cash, -debt, eq_val],
            connector={"line": {"color": "#64748b", "width": 1.5}},
            increasing={"marker": {"color": "#10b981"}},
            decreasing={"marker": {"color": "#f43f5e"}},
            totals={"marker": {"color": "#6366f1"}}
        ))
        apply_market_theme(fig_wf, height=380, show_legend=False, yaxis_title="Value (₹ Cr.)")
        st.plotly_chart(fig_wf, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

        col_w1, col_w2 = st.columns(2)
        with col_w1:
            st.markdown("##### Weighted Average Cost of Capital (WACC)")
            w_p = val_results['wacc_parameters']
            w_breakdown = pd.DataFrame([
                {"Component": "Risk-Free Rate (Rf)", "Value": f"{w_p['risk_free_rate_pct']:.2f}%"},
                {"Component": "Equity Risk Premium (ERP)", "Value": f"{w_p['equity_risk_premium_pct']:.2f}%"},
                {"Component": "Beta (β)", "Value": f"{w_p['beta']:.2f}"},
                {"Component": "Cost of Equity (Ke)", "Value": f"{w_p['cost_of_equity_pct']:.2f}%"},
                {"Component": "Calculated WACC", "Value": f"{w_p['wacc_pct']:.2f}%"}
            ])
            st.dataframe(w_breakdown, hide_index=True, use_container_width=True)
        with col_w2:
            st.markdown("##### Valuation Bridge Output")
            out_table = pd.DataFrame([
                {"Metric": "Discounting Framework", "Value": "Mid-Year Convention (t - 0.5)"},
                {"Metric": "5-Year Cumulative PV of FCFF", "Value": f"₹{cum_fcf:,.1f} Cr."},
                {"Metric": "PV of Terminal Value", "Value": f"₹{pv_tv:,.1f} Cr."},
                {"Metric": "Enterprise Value (EV)", "Value": f"₹{ev:,.1f} Cr."},
                {"Metric": "Implied Equity Value", "Value": f"₹{eq_val:,.1f} Cr."},
                {"Metric": "Gordon Growth Target Price", "Value": f"₹{g_target:,.1f}"}
            ])
            st.dataframe(out_table, hide_index=True, use_container_width=True)

    # Tab: Sensitivity
    with tab_sensitivity:
        st.markdown("##### Two-Way Sensitivity Analysis")
        sens_g = val_results['sensitivity_gordon']
        matrix_g = np.array([[val if val is not None else np.nan for val in row] for row in sens_g['matrix']], dtype=float)
        text_g = [[f"₹{val:,.0f}" if val is not None else "N/A" for val in row] for row in sens_g['matrix']]

        fig_hm1 = px.imshow(matrix_g, x=sens_g['wacc_columns'], y=sens_g['growth_rows'], labels=dict(x="WACC", y="Terminal Growth (g)", color="Target (₹)"), color_continuous_scale="Viridis", text_auto=False)
        fig_hm1.update_traces(text=text_g, texttemplate="%{text}", textfont={"size": 11, "family": "Inter, sans-serif", "color": "#ffffff"})
        apply_market_theme(fig_hm1, height=380, show_legend=False)
        st.plotly_chart(fig_hm1, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

    # Tab: Statements
    with tab_statements:
        st.markdown("##### Statement Metric Explorer")
        metric_options = ["Revenue (Sales)", "Operating Profit (EBITDA)", "Operating Margin (OPM %)", "Net Profit (PAT)", "Free Cash Flow (FCFF)", "Total Borrowings (Debt)"]
        selected_metric = st.selectbox("Select Financial Metric to Inspect", options=metric_options, index=0)
        fc_stmt = fc_results['forecast_statements']
        hist_years = fc_results['historical_years']
        future_years = fc_results['future_years']
        pl_df = raw_data['profit_loss']

        hist_vals = [float(pl_df.loc['Sales', y]) if 'Sales' in pl_df.index and y in pl_df.columns else np.nan for y in hist_years] if selected_metric == "Revenue (Sales)" else None
        fc_vals = fc_stmt['sales'] if selected_metric == "Revenue (Sales)" else fc_stmt['ebitda']

        fig_m = go.Figure()
        if hist_vals is not None:
            fig_m.add_trace(go.Scatter(x=hist_years, y=hist_vals, mode='lines+markers', name='Actual', line=dict(color='#38bdf8', width=2.8)))
            fig_m.add_trace(go.Scatter(x=[hist_years[-1]] + future_years, y=[hist_vals[-1]] + fc_vals, mode='lines+markers', name='Forecast', line=dict(color='#818cf8', width=2.5, dash='dash')))
        else:
            fig_m.add_trace(go.Scatter(x=future_years, y=fc_vals, mode='lines+markers', name='Forecast', line=dict(color='#818cf8', width=2.8)))
        apply_market_theme(fig_m, title=f"{selected_metric} Evolution (₹ Cr.)", height=320, show_legend=True)
        st.plotly_chart(fig_m, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

        st.markdown("##### 5-Year Forecast Statements (₹ Cr.)")
        df_forecast_display = pd.DataFrame({
            "Revenue (Sales)": fc_stmt['sales'],
            "EBITDA": fc_stmt['ebitda'],
            "OPM (%)": fc_stmt['opm_pct'],
            "Net Profit (PAT)": fc_stmt['pat'],
            "Capex": fc_stmt['capex'],
            "Free Cash Flow (FCFF)": fc_stmt['fcff'],
        }, index=fc_results['future_years']).T
        st.dataframe(df_forecast_display.style.format("{:,.1f}"), use_container_width=True)

    # Tab: Excel Export
    with tab_excel:
        st.markdown("##### Download Institutional 8-Worksheet Excel Model")
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
    <strong>Analytical Model Disclaimer:</strong> This application is an automated quantitative financial modeling and research tool. Valuations and forecasts are computed algorithmically from historical public filings and user-defined parameters. Outputs do not constitute registered investment, financial, or legal advice, nor a recommendation to buy or sell any security.
</div>
""", unsafe_allow_html=True)
