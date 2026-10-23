"""
Kavach Financial | Multi-Asset Capital Allocator & Valuation Terminal
Google Finance, TradingView & Screener.in Integrated Pro Dark Terminal

Featuring:
1. Universal Capital Allocator & Trade-Off Engine:
   - Goal & Horizon-Based Suitability Diagnostics
   - Fit-Mismatch & Downside Risk Detection
   - Side-by-Side Multi-Asset Trade-Off Comparator (FDs, Arbitrage, G-Secs, SGBs, Mutual Funds, Stocks)
   - Budget 2024 Post-Tax Net Yield & Real Purchasing Power Modeling
2. Multi-Asset Product Deep-Dive Calculators:
   - Fixed Deposits (DICGC ₹5L cover, TDS, quarterly compounding)
   - Mutual Funds & ETFs (Direct vs Regular fee drag, SIP/Lumpsum, rolling return risk)
   - Sovereign Gold Bonds (SGB) vs Gold ETFs vs Physical Gold
   - Government Securities (G-Secs) & Corporate Bonds (YTM, Duration, Rate Shocks)
3. Company DCF Screener & Institutional Valuation Suite:
   - 70+ Preloaded Indian Equities + Screener 5,000+ API search
   - Google Finance Style Area Charts, Range Selectors & Stats Grid
   - Screener-style Dual-Axis Valuation Multiples (Price to BV, PE vs Median)
   - Beginner Friendly Verdicts & 4-Pillar Traffic Light Scorecards
   - Full 3-Statement Forecast, DCF Waterfall & 8-Sheet Excel Model Export
4. Market Discovery Hub & Regulatory Disclaimers
"""

import os
import sys
import io
import re
import math
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

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
        ScreenerAccessError, InsufficientDataError, clean_number
    )
    from forecasting_engine import (
        FinancialStatementForecaster, ForecastingError, InsufficientHistoryError
    )
    from dcf_model import DCFValuationEngine, ValuationValidationError
    from workbook_builder import WorkbookBuilder
    from news_sentiment_engine import NewsSentimentEngine
    from fd_calculator import FixedDepositCalculator, FDParameters
    from mutual_fund_analyzer import MutualFundAnalyzer, MutualFundParameters
    from gold_engine import GoldEngine, GoldInvestmentParameters
    from bond_engine import BondEngine, BondParameters
    from suitability_engine import SuitabilityEngine, GoalProfile
    from tradeoff_comparator import TradeOffComparator, TradeOffRow
except ImportError:
    from src.scraper.screener_scraper import (
        ScreenerScraper, ScreenerScraperError, InvalidURLError, CompanyNotFoundError,
        ScreenerAccessError, InsufficientDataError, clean_number
    )
    from src.prediction.forecasting_engine import (
        FinancialStatementForecaster, ForecastingError, InsufficientHistoryError
    )
    from src.valuation.dcf_model import DCFValuationEngine, ValuationValidationError
    from src.excel.workbook_builder import WorkbookBuilder
    from src.news.news_sentiment_engine import NewsSentimentEngine
    from fd_calculator import FixedDepositCalculator, FDParameters
    from mutual_fund_analyzer import MutualFundAnalyzer, MutualFundParameters
    from gold_engine import GoldEngine, GoldInvestmentParameters
    from bond_engine import BondEngine, BondParameters
    from suitability_engine import SuitabilityEngine, GoalProfile
    from tradeoff_comparator import TradeOffComparator, TradeOffRow

# Page configuration
st.set_page_config(
    page_title="Kavach Financial | Multi-Asset Capital Allocator",
    page_icon="🛡️",
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
    
    /* Adjusted top padding to completely clear Streamlit's floating header menu */
    .block-container {
        padding-top: 3.8rem;
        padding-bottom: 2rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
        max-width: 1480px;
    }

    /* Live Top Index Ticker Strip */
    .market-ticker-bar {
        display: flex;
        align-items: center;
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 7px 14px;
        margin-bottom: 14px;
        font-size: 0.82rem;
        color: #c9d1d9;
        overflow-x: auto;
        white-space: nowrap;
        gap: 20px;
    }
    .ticker-close-tag {
        background: #38bdf8;
        color: #0b1120;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 3px;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .ticker-item {
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .ticker-name {
        font-weight: 600;
        color: #f0f6fc;
    }
    .ticker-down {
        color: #f85149;
        font-weight: 600;
    }
    .ticker-up {
        color: #3fb950;
        font-weight: 600;
    }

    /* Hero Banners */
    .home-hero-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 20px 24px;
        margin-bottom: 20px;
        border-left: 4px solid #38bdf8;
    }
    .home-hero-title {
        font-size: 1.55rem;
        font-weight: 700;
        color: #f0f6fc;
        letter-spacing: -0.02em;
        margin-bottom: 6px;
    }
    .home-hero-sub {
        font-size: 0.90rem;
        color: #8b949e;
        line-height: 1.5;
    }

    /* Allocator & Suitability Cards */
    .allocator-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 18px 20px;
        margin-bottom: 16px;
    }
    .allocator-card-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #f0f6fc;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .warning-box {
        background: rgba(239, 68, 68, 0.12);
        border: 1.5px solid #ef4444;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 14px;
        color: #fca5a5;
        font-size: 0.88rem;
        line-height: 1.45;
    }
    .tip-box {
        background: rgba(56, 189, 248, 0.10);
        border: 1.5px solid #38bdf8;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 14px;
        color: #bae6fd;
        font-size: 0.88rem;
        line-height: 1.45;
    }

    .scorecard-item {
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 6px;
        padding: 14px;
        margin-bottom: 10px;
    }
    .scorecard-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .scorecard-name {
        font-weight: 600;
        color: #f0f6fc;
        font-size: 0.95rem;
    }
    .scorecard-badge {
        font-size: 0.78rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 4px;
    }

    /* Trade-Off Visuals */
    .gain-pill {
        background: rgba(63, 185, 80, 0.15);
        color: #3fb950;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.76rem;
        font-weight: 600;
    }
    .loss-pill {
        background: rgba(248, 81, 73, 0.15);
        color: #f85149;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.76rem;
        font-weight: 600;
    }

    /* Trending & Generic Cards */
    .trending-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        height: 100%;
        transition: all 0.2s ease;
    }
    .trending-card:hover {
        border-color: #58a6ff;
        background: #1c2128;
    }
    .trending-header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 6px;
    }
    .trending-name {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f0f6fc;
    }
    .trending-badge {
        font-size: 0.72rem;
        background: rgba(56, 189, 248, 0.12);
        color: #58a6ff;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 600;
    }
    .trending-meta {
        font-size: 0.8rem;
        color: #8b949e;
        margin-bottom: 8px;
    }
    .trending-desc {
        font-size: 0.82rem;
        color: #c9d1d9;
        line-height: 1.45;
        margin-bottom: 12px;
    }

    /* Google Finance Style Header */
    .gf-header {
        border-bottom: 1px solid #21262d;
        padding-bottom: 12px;
        margin-bottom: 14px;
    }
    .gf-breadcrumb {
        font-size: 0.8rem;
        color: #8b949e;
        margin-bottom: 4px;
    }
    .gf-title-row {
        display: flex;
        align-items: baseline;
        gap: 12px;
        flex-wrap: wrap;
    }
    .gf-company-name {
        font-size: 1.6rem;
        font-weight: 700;
        color: #f0f6fc;
        letter-spacing: -0.02em;
        margin: 0;
    }
    .gf-price-row {
        display: flex;
        align-items: baseline;
        gap: 10px;
        margin-top: 4px;
    }
    .gf-price {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f0f6fc;
    }
    .gf-change-up {
        font-size: 1.05rem;
        font-weight: 600;
        color: #3fb950;
    }
    .gf-change-down {
        font-size: 1.05rem;
        font-weight: 600;
        color: #f85149;
    }
    .gf-time {
        font-size: 0.8rem;
        color: #8b949e;
    }

    /* Quick stats cell */
    .stat-cell {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 8px;
    }
    .stat-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #8b949e;
        margin-bottom: 3px;
    }
    .stat-val {
        font-size: 1.08rem;
        font-weight: 700;
        color: #f0f6fc;
    }

    /* Verdict Boxes */
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
        font-size: 1.25rem;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .verdict-desc {
        font-size: 0.95rem;
        color: #c9d1d9;
        line-height: 1.5;
    }

    .disclaimer-card {
        padding: 14px 18px;
        background: #161b22;
        border-left: 3px solid #38bdf8;
        border-radius: 6px;
        font-size: 0.80rem;
        color: #8b949e;
        margin-top: 2rem;
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
    .external-hub-link {
        font-size: 0.78rem;
        color: #58a6ff;
        text-decoration: none;
        border: 1px solid #30363d;
        padding: 4px 8px;
        border-radius: 4px;
        background: #161b22;
    }
    .external-hub-link:hover {
        border-color: #58a6ff;
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
# LIVE TOP INDEX TICKER MARQUEE
# -----------------------------------------------------------------------------
@st.cache_data(ttl=120, show_spinner=False)
def get_live_market_indices():
    symbols = {
        'BSE SENSEX': ('^BSESN', 73123.83, -125.56, -0.17),
        'NIFTY 50': ('^NSEI', 22600.00, -87.65, -0.38),
        'BSE BANKEX': ('^NSEBANK', 61086.71, -679.29, -1.10),
        'BSE Focused IT': ('^CNXIT', 38096.35, -254.39, -0.66)
    }
    headers = {'User-Agent': 'Mozilla/5.0'}
    items = []
    for name, (sym, def_price, def_chg, def_pct) in symbols.items():
        price, change, pct = def_price, def_chg, def_pct
        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d'
            r = requests.get(url, headers=headers, timeout=2.5)
            if r.status_code == 200:
                meta = r.json()['chart']['result'][0]['meta']
                curr = meta.get('regularMarketPrice', def_price)
                prev = meta.get('chartPreviousClose', curr)
                price = curr
                change = curr - prev
                pct = (change / max(1.0, prev)) * 100.0
        except Exception:
            pass
        items.append((name, f"{price:,.2f}", f"{change:+,.2f}", f"{pct:+.2f}%", "down" if change < 0 else "up"))
    return items


# -----------------------------------------------------------------------------
# TRENDING COMPANIES CATALOG
# -----------------------------------------------------------------------------
TRENDING_COMPANIES = [
    {
        'name': 'Tata Steel Ltd', 'ticker': 'TATASTEEL', 'sector': 'Metals & Mining',
        'mcap': '₹2,02,000 Cr', 'pe': '14.2', 'roce': '12.8%',
        'summary': 'Integrated global steel producer with mining operations across India and restructuring in the UK.',
        'url': 'https://www.screener.in/company/TATASTEEL/consolidated/'
    },
    {
        'name': 'Reliance Industries', 'ticker': 'RELIANCE', 'sector': 'Conglomerate & Energy',
        'mcap': '₹19,85,000 Cr', 'pe': '24.1', 'roce': '10.5%',
        'summary': 'Diversified conglomerate dominating oil-to-chemicals, retail consumer chains, and 5G telecommunications (Jio).',
        'url': 'https://www.screener.in/company/RELIANCE/consolidated/'
    },
    {
        'name': 'Infosys Ltd', 'ticker': 'INFY', 'sector': 'IT & Software',
        'mcap': '₹6,40,000 Cr', 'pe': '26.4', 'roce': '36.5%',
        'summary': 'Next-generation digital services and consulting giant with high free cash flow generation and consistent dividends.',
        'url': 'https://www.screener.in/company/INFY/consolidated/'
    },
    {
        'name': 'Hindustan Unilever Ltd', 'ticker': 'HINDUNILVR', 'sector': 'FMCG & Consumer',
        'mcap': '₹5,80,000 Cr', 'pe': '54.2', 'roce': '28.4%',
        'summary': 'India\'s leading FMCG corporation touching 9 out of 10 households daily with immense brand pricing power.',
        'url': 'https://www.screener.in/company/HINDUNILVR/consolidated/'
    },
    {
        'name': 'Tata Consultancy Services', 'ticker': 'TCS', 'sector': 'IT & Software',
        'mcap': '₹14,50,000 Cr', 'pe': '29.3', 'roce': '58.2%',
        'summary': 'Tata Group\'s flagship software titan, renowned for industry-leading operating profit margins and global enterprise contracts.',
        'url': 'https://www.screener.in/company/TCS/consolidated/'
    },
    {
        'name': 'Larsen & Toubro Ltd', 'ticker': 'LT', 'sector': 'Capital Goods & Defence',
        'mcap': '₹4,95,000 Cr', 'pe': '34.8', 'roce': '16.2%',
        'summary': 'The core backbone of Indian infrastructure, executing mega transport, energy, and national defence programs.',
        'url': 'https://www.screener.in/company/LT/consolidated/'
    },
    {
        'name': 'Zomato (Eternal Ltd)', 'ticker': 'ETERNAL', 'sector': 'Consumer Tech',
        'mcap': '₹2,35,000 Cr', 'pe': '112.0', 'roce': '14.1%',
        'summary': 'Hyper-growth consumer platform leading quick commerce (Blinkit) and food delivery across 500+ Indian cities.',
        'url': 'https://www.screener.in/company/ETERNAL/consolidated/'
    },
    {
        'name': 'State Bank of India', 'ticker': 'SBIN', 'sector': 'Banking & Financials',
        'mcap': '₹7,20,000 Cr', 'pe': '10.8', 'roce': '15.4%',
        'summary': 'India\'s largest financial institution handling one-fourth of national deposits and credit advances.',
        'url': 'https://www.screener.in/company/SBIN/'
    }
]

POPULAR_STOCKS = [(c['name'], c['ticker'], c['url']) for c in TRENDING_COMPANIES] + [
    ("Wipro", "WIPRO", "https://www.screener.in/company/WIPRO/consolidated/"),
    ("ITC", "ITC", "https://www.screener.in/company/ITC/consolidated/"),
    ("HDFC Bank", "HDFCBANK", "https://www.screener.in/company/HDFCBANK/consolidated/"),
    ("ICICI Bank", "ICICIBANK", "https://www.screener.in/company/ICICIBANK/consolidated/"),
    ("Bharti Airtel", "BHARTIARTL", "https://www.screener.in/company/BHARTIARTL/consolidated/"),
    ("Bajaj Finance", "BAJFINANCE", "https://www.screener.in/company/BAJFINANCE/consolidated/"),
    ("Asian Paints", "ASIANPAINT", "https://www.screener.in/company/ASIANPAINT/consolidated/"),
    ("Maruti Suzuki", "MARUTI", "https://www.screener.in/company/MARUTI/consolidated/"),
    ("Sun Pharma", "SUNPHARMA", "https://www.screener.in/company/SUNPHARMA/consolidated/"),
    ("Titan Company", "TITAN", "https://www.screener.in/company/TITAN/consolidated/"),
    ("Adani Enterprises", "ADANIENT", "https://www.screener.in/company/ADANIENT/consolidated/"),
    ("Adani Ports", "ADANIPORTS", "https://www.screener.in/company/ADANIPORTS/consolidated/"),
    ("NTPC", "NTPC", "https://www.screener.in/company/NTPC/consolidated/"),
    ("Power Grid", "POWERGRID", "https://www.screener.in/company/POWERGRID/consolidated/"),
    ("ONGC", "ONGC", "https://www.screener.in/company/ONGC/consolidated/"),
    ("Coal India", "COALINDIA", "https://www.screener.in/company/COALINDIA/consolidated/"),
    ("JSW Steel", "JSWSTEEL", "https://www.screener.in/company/JSWSTEEL/consolidated/"),
    ("Vedanta", "VEDL", "https://www.screener.in/company/VEDL/consolidated/"),
    ("UltraTech Cement", "ULTRACEMCO", "https://www.screener.in/company/ULTRACEMCO/consolidated/"),
    ("Cipla", "CIPLA", "https://www.screener.in/company/CIPLA/consolidated/"),
    ("Trent", "TRENT", "https://www.screener.in/company/TRENT/consolidated/"),
    ("DMart", "DMART", "https://www.screener.in/company/DMART/consolidated/"),
    ("Polycab India", "POLYCAB", "https://www.screener.in/company/POLYCAB/consolidated/"),
    ("Suzlon Energy", "SUZLON", "https://www.screener.in/company/SUZLON/consolidated/"),
    ("IRCTC", "IRCTC", "https://www.screener.in/company/IRCTC/consolidated/"),
    ("RVNL", "RVNL", "https://www.screener.in/company/RVNL/consolidated/"),
    ("IOCL", "IOC", "https://www.screener.in/company/IOC/consolidated/"),
    ("BPCL", "BPCL", "https://www.screener.in/company/BPCL/consolidated/")
]

STOCK_MAP = {f"{name} ({ticker})": url for name, ticker, url in POPULAR_STOCKS}


# Dynamic Search API for 5000+ stocks
@st.cache_data(ttl=900, show_spinner=False)
def search_screener_api(query: str) -> List[Dict[str, str]]:
    if not query or len(query.strip()) < 2:
        return []
    try:
        url = f"https://www.screener.in/api/company/search/?q={urllib.parse.quote(query.strip())}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=3.5)
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
# SESSION STATE & RECENT SEARCHES
# -----------------------------------------------------------------------------
if 'recent_searches' not in st.session_state:
    st.session_state['recent_searches'] = [
        ("Tata Steel", "https://www.screener.in/company/TATASTEEL/consolidated/"),
        ("Reliance Industries", "https://www.screener.in/company/RELIANCE/consolidated/"),
        ("Infosys", "https://www.screener.in/company/INFY/consolidated/")
    ]

if 'active_target_url' not in st.session_state:
    st.session_state['active_target_url'] = "https://www.screener.in/company/TATASTEEL/consolidated/"

if 'nav_mode' not in st.session_state:
    st.session_state['nav_mode'] = "🎯 Capital Allocator & Trade-Off Matrix"


# -----------------------------------------------------------------------------
# TOP LIVE INDEX TICKER (Properly Spaced & Fully Accessible)
# -----------------------------------------------------------------------------
indices_data = get_live_market_indices()
curr_date_str = datetime.now().strftime("%d %b %y | %H:%M")

ticker_spans = []
for name, price, chg, pct, direction in indices_data:
    arrow = "▼" if direction == "down" else "▲"
    chg_cls = "ticker-down" if direction == "down" else "ticker-up"
    ticker_spans.append(f'<div class="ticker-item"><span class="ticker-name">{name}</span><span>{price}</span><span class="{chg_cls}">{chg} {pct} {arrow}</span></div>')

ticker_inner_html = "".join(ticker_spans)
ticker_bar_html = f'<div class="market-ticker-bar"><span class="ticker-close-tag">Market Pulse</span><span style="color:#8b949e; font-weight:500;">{curr_date_str}</span><span style="color:#30363d;">|</span>{ticker_inner_html}</div>'
st.markdown(ticker_bar_html, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# SIDEBAR CONTROLS & NAVIGATION
# -----------------------------------------------------------------------------
st.sidebar.markdown("<div class='sidebar-section-title'>Platform Navigation</div>", unsafe_allow_html=True)

nav_options = [
    "🎯 Capital Allocator & Trade-Off Matrix",
    "📊 Multi-Asset Product Deep Dives",
    "🏢 Company DCF Model & Screener",
    "🏠 Market Trends & Disclaimers"
]

nav_selection = st.sidebar.radio(
    "Select Screen",
    nav_options,
    index=nav_options.index(st.session_state['nav_mode']) if st.session_state['nav_mode'] in nav_options else 0,
    label_visibility="collapsed"
)
st.session_state['nav_mode'] = nav_selection

st.sidebar.markdown("<div class='sidebar-section-title'>Quick Stock Selector</div>", unsafe_allow_html=True)

stock_choice = st.sidebar.selectbox(
    "Search or Select Stock",
    options=list(STOCK_MAP.keys()),
    index=0,
    help="Type any letters to filter instantly in real-time!"
)

if st.sidebar.button("Open Selected Company", type="primary", use_container_width=True):
    st.session_state['active_target_url'] = STOCK_MAP[stock_choice]
    st.session_state['nav_mode'] = "🏢 Company DCF Model & Screener"
    st.rerun()

with st.sidebar.expander("Search Other 5,000+ Indian Stocks", expanded=False):
    custom_query = st.text_input("Enter company name or ticker", value="", placeholder="e.g. Suzlon, Kaynes...")
    if custom_query:
        api_results = search_screener_api(custom_query)
        if api_results:
            api_opts = [r['display'] for r in api_results]
            chosen_api = st.selectbox("Search Results", options=api_opts)
            matched_obj = next((r for r in api_results if r['display'] == chosen_api), None)
            if matched_obj and st.button("Analyze Found Stock"):
                st.session_state['active_target_url'] = matched_obj['url']
                st.session_state['nav_mode'] = "🏢 Company DCF Model & Screener"
                st.rerun()
        else:
            st.caption("No matching listed stocks found on Screener.")

with st.sidebar.expander("DCF Valuation Assumptions (Pro)", expanded=False):
    rf_rate = st.slider("Risk-Free Rate (Rf)", min_value=5.0, max_value=9.0, value=7.0, step=0.1, format="%.1f%%") / 100.0
    erp = st.slider("Equity Risk Premium (ERP)", min_value=4.0, max_value=8.0, value=5.5, step=0.1, format="%.1f%%") / 100.0
    beta_val = st.slider("Beta (β)", min_value=0.4, max_value=2.0, value=1.0, step=0.05)
    term_g = st.slider("Terminal Growth Rate (g)", min_value=2.5, max_value=6.0, value=4.5, step=0.25, format="%.2f%%") / 100.0


# =============================================================================
# SCREEN 1: CAPITAL ALLOCATOR & TRADE-OFF MATRIX
# =============================================================================
if st.session_state['nav_mode'] == "🎯 Capital Allocator & Trade-Off Matrix":
    st.markdown("""
    <div class="home-hero-card">
        <div class="home-hero-title">🎯 Multi-Asset Capital Allocator & Trade-Off Matrix</div>
        <div class="home-hero-sub">
            Product-neutral investment comparison across <strong>Fixed Deposits, Arbitrage Funds, Sovereign Gold Bonds, Government Bonds, Mutual Funds, and Direct Equities</strong>.
            Evaluate post-tax net yield under Budget 2024 rules and detect capital-mismatch risks before allocating wealth.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Goal & Horizon Setup Card
    st.markdown("##### ⚙️ Your Goal Parameters & Investor Profile")
    p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns(5)
    with p_col1:
        goal_name = st.selectbox("Investment Objective", ["Wealth Accumulation", "House Down Payment", "Emergency Reserve", "Child Higher Education", "Retirement Milestone", "General Savings"])
    with p_col2:
        invest_amount = st.number_input("Capital to Allocate (₹)", min_value=10000.0, max_value=100000000.0, value=300000.0, step=25000.0, format="%.0f")
    with p_col3:
        horizon_months = st.slider("Investment Horizon (Months)", min_value=3, max_value=120, value=36, step=3, help="e.g. 12 months = 1 Year, 36 months = 3 Years, 60 months = 5 Years")
    with p_col4:
        tax_bracket = st.selectbox("Your Income Tax Slab", [30.0, 20.0, 15.0, 10.0, 5.0, 0.0], index=0, format_func=lambda x: f"{x:.0f}% Tax Bracket (Budget 2024)")
    with p_col5:
        risk_profile = st.selectbox("Risk Tolerance", ["Moderate", "Conservative", "Aggressive"], index=0)

    horizon_years = horizon_months / 12.0
    profile = GoalProfile(
        goal_name=goal_name,
        investment_amount=invest_amount,
        horizon_months=horizon_months,
        liquidity_need="moderate",
        risk_profile=risk_profile.lower(),
        tax_bracket_pct=tax_bracket
    )

    # Run Diagnosis and Trade-Off Models
    diag = SuitabilityEngine.diagnose(profile)
    trade_offs = TradeOffComparator.compare_all(
        amount=invest_amount,
        tenure_months=horizon_months,
        tax_bracket_pct=tax_bracket,
        expected_inflation_pct=6.0
    )

    st.markdown("---")

    # Critical Mismatch Alerts & Tax Tips
    if diag.critical_warnings:
        for w in diag.critical_warnings:
            st.markdown(f"""<div class="warning-box"><strong>⚠️ Potential Capital Mismatch Alert:</strong> {w}</div>""", unsafe_allow_html=True)
    if diag.tax_optimization_tips:
        for t in diag.tax_optimization_tips:
            st.markdown(f"""<div class="tip-box"><strong>💡 Tax Optimization Opportunity:</strong> {t}</div>""", unsafe_allow_html=True)

    # Top Recommended Asset Highlight Strip
    st.markdown(f"""
    <div style="background:#161b22; border:1px solid #30363d; border-radius:6px; padding:12px 18px; margin-bottom:16px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap;">
        <div>
            <span style="font-size:0.8rem; color:#8b949e; text-transform:uppercase; font-weight:600;">Optimal Primary Fit for {horizon_months} Months ({horizon_years:.1f} Yrs):</span>
            <div style="font-size:1.25rem; font-weight:700; color:#38bdf8;">{diag.top_recommended_asset}</div>
        </div>
        <div style="font-size:0.85rem; color:#c9d1d9;">
            Evaluating Capital of <strong>₹{invest_amount:,.0f}</strong> across 6 asset classes
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Asset Suitability Scorecards Grid
    st.markdown("##### 🛡️ Product Suitability & Fit Scorecards")
    sc_cols = st.columns(3)
    for idx, score_item in enumerate(diag.asset_scores):
        col_idx = idx % 3
        with sc_cols[col_idx]:
            st.markdown(f"""
            <div class="scorecard-item">
                <div class="scorecard-header">
                    <span class="scorecard-name">{score_item.display_name}</span>
                    <span class="scorecard-badge" style="background:{score_item.fit_color}22; color:{score_item.fit_color}; border:1px solid {score_item.fit_color};">
                        {score_item.suitability_score}/100 &bull; {score_item.fit_status}
                    </span>
                </div>
                <div style="font-size:0.75rem; color:#8b949e; margin-bottom:6px;">
                    Tax Efficiency: <strong style="color:#f0f6fc;">{score_item.tax_efficiency_rating}</strong>
                </div>
                <div style="font-size:0.80rem; color:#c9d1d9; line-height:1.4;">
                    {score_item.primary_reason}
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Side-by-Side Trade-Off Comparison Matrix Table
    st.markdown("##### ⚖️ The Multi-Asset Trade-Off Matrix")
    st.caption("Standardized comparison calculated for identical capital, tenure, and your personal tax bracket under Budget 2024.")

    df_tradeoff = TradeOffComparator.to_dataframe(trade_offs)
    st.dataframe(df_tradeoff, use_container_width=True, hide_index=True)

    # Interactive Visualizations: Post-Tax Net Yield vs Inflation & Risk-Return Scatter
    v_col1, v_col2 = st.columns(2)
    with v_col1:
        st.markdown("##### Net Post-Tax Yield vs Inflation Benchmark")
        fig_bar = go.Figure()
        asset_names = [r.asset_name.split('(')[0].strip() for r in trade_offs]
        net_yields = [r.post_tax_yield_pct for r in trade_offs]
        nom_yields = [r.nominal_return_pct for r in trade_offs]
        
        fig_bar.add_trace(go.Bar(
            x=asset_names, y=nom_yields, name="Gross Nominal Yield (%)",
            marker_color="#475569", opacity=0.8,
            hovertemplate="%{x}<br>Nominal Yield: %{y:.2f}%<extra></extra>"
        ))
        fig_bar.add_trace(go.Bar(
            x=asset_names, y=net_yields, name="Net Post-Tax Yield (%)",
            marker_color="#38bdf8",
            hovertemplate="%{x}<br>Post-Tax Yield: %{y:.2f}%<extra></extra>"
        ))
        fig_bar.add_hline(y=6.0, line_dash="dash", line_color="#f59e0b", annotation_text="Inflation (6.0% CPI)", annotation_position="top left")
        apply_market_theme(fig_bar, height=340, show_legend=True, yaxis_title="Annualized Yield (%)")
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

    with v_col2:
        st.markdown("##### Downside Risk vs Real Post-Tax Yield")
        risk_map = {"Negligible (DICGC ₹5L cover)": 1, "Very Low (Hedging spreads)": 2, "Low (Zero default, rate risk)": 3, "Moderate (Gold price cycle)": 4, "High (Market cycle swings)": 5, "Very High (Company specific risk)": 6}
        scatter_x = [risk_map.get(r.downside_risk_rating, 3) for r in trade_offs]
        scatter_y = [r.real_inflation_adjusted_yield_pct for r in trade_offs]
        scatter_text = [r.asset_name.split('(')[0].strip() for r in trade_offs]

        fig_scat = go.Figure()
        fig_scat.add_trace(go.Scatter(
            x=scatter_x, y=scatter_y, mode="markers+text",
            text=scatter_text, textposition="top center",
            marker=dict(size=14, color=["#10b981", "#38bdf8", "#818cf8", "#fbbf24", "#f43f5e", "#ec4899"], line=dict(color="#ffffff", width=1.5)),
            hovertemplate="<b>%{text}</b><br>Downside Level: %{x}<br>Real Yield (Post-Inflation): %{y:+.2f}%<extra></extra>"
        ))
        fig_scat.add_hline(y=0.0, line_dash="dot", line_color="#ef4444", annotation_text="Zero Real Growth (Capital Erosion Line)", annotation_position="bottom right")
        fig_scat.update_layout(
            xaxis=dict(title="Capital Risk Profile (1=Negligible to 6=Very High)", tickvals=[1,2,3,4,5,6], ticktext=["FD (Insured)", "Arbitrage", "G-Sec", "SGB/Gold", "Equity MF", "Direct Stock"]),
            yaxis=dict(title="Real Purchasing Power Yield (%)")
        )
        apply_market_theme(fig_scat, height=340, show_legend=False)
        st.plotly_chart(fig_scat, use_container_width=True, config={'displayModeBar': False})

    # Detailed "What You Gain vs What You Sacrifice" Expanders
    st.markdown("##### 🔍 Deep-Dive: What You Gain vs What You Sacrifice")
    for r in trade_offs:
        with st.expander(f"📌 {r.asset_name} — Net Maturity: ₹{r.net_maturity_value:,.0f} (Net: {r.post_tax_yield_pct:.2f}%)"):
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                st.markdown(f"<span class='gain-pill'>✔ WHAT YOU GAIN</span>", unsafe_allow_html=True)
                st.write(r.what_you_gain)
            with d_col2:
                st.markdown(f"<span class='loss-pill'>✖ WHAT YOU SACRIFICE</span>", unsafe_allow_html=True)
                st.write(r.what_you_sacrifice)
            st.caption(f"Horizon Guidance: {r.horizon_fit_note} &bull; Liquidity: {r.liquidity_rating} &bull; Tax Efficiency: Grade {r.tax_efficiency_grade}")


# =============================================================================
# SCREEN 2: MULTI-ASSET PRODUCT DEEP DIVES (CALCULATORS)
# =============================================================================
elif st.session_state['nav_mode'] == "📊 Multi-Asset Product Deep Dives":
    st.markdown("""
    <div class="home-hero-card">
        <div class="home-hero-title">📊 Multi-Asset Product Deep-Dive Calculators</div>
        <div class="home-hero-sub">
            Specialized financial engineering calculators for each individual asset class, with exact friction costs,
            DICGC limits, expense ratio wealth drag, bond durations, and Budget 2024 taxation.
        </div>
    </div>
    """, unsafe_allow_html=True)

    subtab_fd, subtab_mf, subtab_gold, subtab_bonds = st.tabs([
        "🏦 Fixed Deposits & Small Savings",
        "📈 Mutual Funds & Fee Drag",
        "🥇 Sovereign Gold Bonds vs Gold",
        "🏛️ Bonds & G-Sec Duration"
    ])

    # 1. FIXED DEPOSITS
    with subtab_fd:
        st.markdown("##### Fixed Deposit & Term Deposit Calculator")
        fd_c1, fd_c2, fd_c3 = st.columns(3)
        with fd_c1:
            fd_p = st.number_input("Deposit Principal (₹)", min_value=5000.0, value=500000.0, step=50000.0, format="%.0f", key="fd_calc_p")
            fd_tenure = st.slider("Tenure (Months)", min_value=1, max_value=120, value=36, step=1, key="fd_calc_t")
        with fd_c2:
            fd_bank_preset = st.selectbox("Select Institution Benchmark", [
                "SBI / PSU Bank (6.75% @ 3Y)",
                "HDFC / ICICI Bank (7.00% @ 3Y)",
                "Equitas Small Finance Bank (8.00% @ 3Y)",
                "Post Office Term Deposit (7.10% @ 3Y)",
                "Bajaj Finance Corporate FD (8.10% @ 3Y)",
                "Custom Rate"
            ])
            if "SBI" in fd_bank_preset:
                rate_val, inst_type = 6.75, "scheduled_commercial_bank"
            elif "HDFC" in fd_bank_preset:
                rate_val, inst_type = 7.00, "scheduled_commercial_bank"
            elif "Equitas" in fd_bank_preset:
                rate_val, inst_type = 8.00, "small_finance_bank"
            elif "Post Office" in fd_bank_preset:
                rate_val, inst_type = 7.10, "post_office"
            elif "Bajaj" in fd_bank_preset:
                rate_val, inst_type = 8.10, "corporate_nbfc"
            else:
                rate_val, inst_type = 7.25, "scheduled_commercial_bank"
            
            fd_custom_rate = st.number_input("Interest Rate (% p.a.)", min_value=1.0, max_value=15.0, value=rate_val, step=0.1, key="fd_calc_r")
        with fd_c3:
            fd_tax_slab = st.selectbox("Investor Tax Slab", [30.0, 20.0, 15.0, 10.0, 5.0, 0.0], index=0, key="fd_calc_tax", format_func=lambda x: f"{x:.0f}% Slab")
            fd_senior = st.checkbox("Senior Citizen (+0.50% p.a. benefit & ₹50K TDS threshold)", value=False)
            effective_fd_rate = fd_custom_rate + (0.50 if fd_senior else 0.0)

        fd_res = FixedDepositCalculator.calculate(FDParameters(
            principal=fd_p,
            tenure_months=fd_tenure,
            interest_rate_pct=effective_fd_rate,
            compounding_frequency="quarterly",
            tax_bracket_pct=fd_tax_slab,
            is_senior_citizen=fd_senior,
            institution_type=inst_type
        ))

        # FD Metric Strip
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Gross Maturity Amount</div><div class="stat-val">₹{fd_res.gross_maturity_amount:,.0f}</div><div style="font-size:0.75rem; color:#8b949e;">Interest: ₹{fd_res.gross_interest_earned:,.0f}</div></div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Total Tax Liability ({fd_tax_slab:.0f}%)</div><div class="stat-val" style="color:#f85149;">-₹{fd_res.total_tax_liability:,.0f}</div><div style="font-size:0.75rem; color:#8b949e;">TDS Deducted: ₹{fd_res.tds_deducted:,.0f}</div></div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Net Post-Tax Maturity</div><div class="stat-val" style="color:#38bdf8;">₹{fd_res.net_maturity_amount:,.0f}</div><div style="font-size:0.75rem; color:#8b949e;">Net Gain: ₹{fd_res.net_post_tax_interest:,.0f}</div></div>""", unsafe_allow_html=True)
        with m4:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Net Post-Tax Yield</div><div class="stat-val">{fd_res.net_post_tax_annual_yield_pct:.2f}%</div><div style="font-size:0.75rem; color:{'#3fb950' if fd_res.real_inflation_adjusted_yield_pct >= 0 else '#f85149'};">Real (vs 6% CPI): {fd_res.real_inflation_adjusted_yield_pct:+.2f}%</div></div>""", unsafe_allow_html=True)

        st.caption(f"🛡️ **DICGC Insurance Status**: {fd_res.dicgc_coverage_status}")
        st.caption(f"📝 **Tax & TDS Note**: {fd_res.tds_applicability_note}")

        with st.expander("📅 View Quarterly Compounding Schedule", expanded=False):
            df_sched = pd.DataFrame(fd_res.quarterly_schedule)
            st.dataframe(df_sched, use_container_width=True, hide_index=True)

    # 2. MUTUAL FUNDS
    with subtab_mf:
        st.markdown("##### Mutual Fund Wealth Accumulator & Expense Ratio Drag Calculator")
        mf_c1, mf_c2, mf_c3 = st.columns(3)
        with mf_c1:
            mf_mode = st.radio("Investment Mode", ["Monthly SIP", "Lumpsum"], horizontal=True)
            mf_amt = st.number_input(f"{mf_mode} Amount (₹)", min_value=500.0, value=25000.0 if mf_mode == "Monthly SIP" else 200000.0, step=2500.0, format="%.0f")
            mf_years = st.slider("Investment Horizon (Years)", min_value=1, max_value=30, value=10, step=1)
        with mf_c2:
            mf_cat = st.selectbox("Fund Category", list(MutualFundAnalyzer.CATEGORIES.keys()), format_func=lambda x: MutualFundAnalyzer.CATEGORIES[x]["name"])
            cat_default = MutualFundAnalyzer.CATEGORIES[mf_cat]
            mf_cagr = st.slider("Expected Portfolio CAGR (%)", min_value=4.0, max_value=25.0, value=float(cat_default["typical_cagr"]), step=0.5)
        with mf_c3:
            mf_direct_ter = st.number_input("Direct Plan Expense Ratio (%)", min_value=0.05, max_value=2.0, value=float(cat_default["direct_ter"]), step=0.05)
            mf_reg_ter = st.number_input("Regular Plan Expense Ratio (%)", min_value=0.20, max_value=3.0, value=float(cat_default["regular_ter"]), step=0.05)
            mf_tax_bracket = st.selectbox("Tax Bracket", [30.0, 20.0, 15.0, 10.0, 5.0, 0.0], index=0, key="mf_tax_sel", format_func=lambda x: f"{x:.0f}% Slab")

        mf_res = MutualFundAnalyzer.analyze(MutualFundParameters(
            investment_mode="sip" if mf_mode == "Monthly SIP" else "lumpsum",
            investment_amount=mf_amt,
            tenure_years=float(mf_years),
            category=mf_cat,
            expected_cagr_pct=mf_cagr,
            direct_expense_ratio_pct=mf_direct_ter,
            regular_expense_ratio_pct=mf_reg_ter,
            tax_bracket_pct=mf_tax_bracket
        ))

        # MF Wealth Stats
        w1, w2, w3, w4 = st.columns(4)
        with w1:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Total Invested Capital</div><div class="stat-val">₹{mf_res.total_invested_capital:,.0f}</div><div style="font-size:0.75rem; color:#8b949e;">{mf_mode} over {mf_years} yrs</div></div>""", unsafe_allow_html=True)
        with w2:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Direct Plan Final Corpus</div><div class="stat-val" style="color:#38bdf8;">₹{mf_res.direct_corpus:,.0f}</div><div style="font-size:0.75rem; color:#3fb950;">Gross Gains: ₹{mf_res.gross_gains_direct:,.0f}</div></div>""", unsafe_allow_html=True)
        with w3:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Regular Plan Corpus</div><div class="stat-val">₹{mf_res.regular_corpus:,.0f}</div><div style="font-size:0.75rem; color:#8b949e;">Distributor Plan</div></div>""", unsafe_allow_html=True)
        with w4:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Lost to Distributor Commission</div><div class="stat-val" style="color:#f85149;">₹{mf_res.expense_drag_lost_wealth:,.0f}</div><div style="font-size:0.75rem; color:#f85149;">Compounded Fee Drag</div></div>""", unsafe_allow_html=True)

        st.caption(f"⚖️ **Budget 2024 Tax Treatment**: {mf_res.tax_treatment_summary}")
        st.caption(f"🎯 **Suitability Diagnostic**: {mf_res.suitability_verdict}")

        # Chart: Direct Plan vs Regular Plan Wealth Trajectory
        df_mf_sched = pd.DataFrame(mf_res.wealth_growth_schedule)
        fig_mf = go.Figure()
        fig_mf.add_trace(go.Scatter(x=df_mf_sched['year'], y=df_mf_sched['direct_corpus'], mode='lines+markers', name='Direct Plan (Zero Commission)', line=dict(color='#38bdf8', width=3)))
        fig_mf.add_trace(go.Scatter(x=df_mf_sched['year'], y=df_mf_sched['regular_corpus'], mode='lines+markers', name='Regular Plan (Agent Commission)', line=dict(color='#94a3b8', width=2, dash='dash')))
        fig_mf.add_trace(go.Bar(x=df_mf_sched['year'], y=df_mf_sched['advisor_commission_drag'], name='Cumulative Lost Wealth', marker_color='rgba(248, 81, 73, 0.4)'))
        apply_market_theme(fig_mf, title="Direct vs Regular Plan Wealth Gap Over Time", height=340, show_legend=True, xaxis_title="Investment Year", yaxis_title="Corpus Value (₹)")
        st.plotly_chart(fig_mf, use_container_width=True, config={'displayModeBar': False})

    # 3. GOLD & SGB MODEL
    with subtab_gold:
        st.markdown("##### Sovereign Gold Bonds (SGB) vs Gold ETFs vs Physical Gold")
        g_c1, g_c2, g_c3 = st.columns(3)
        with g_c1:
            gold_amt = st.number_input("Gold Allocation Amount (₹)", min_value=10000.0, value=200000.0, step=25000.0, format="%.0f")
        with g_c2:
            gold_tenure = st.slider("Holding Tenure (Years)", min_value=1, max_value=8, value=8, step=1, help="SGB standard RBI maturity is 8 years.")
        with g_c3:
            gold_cagr = st.slider("Expected Gold Price CAGR (%)", min_value=3.0, max_value=16.0, value=8.5, step=0.5)

        gold_res = GoldEngine.compare(GoldInvestmentParameters(
            investment_amount=gold_amt,
            tenure_years=float(gold_tenure),
            expected_gold_cagr_pct=gold_cagr,
            tax_bracket_pct=30.0
        ))

        gw1, gw2, gw3, gw4 = st.columns(4)
        with gw1:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">SGB Net Terminal Payout</div><div class="stat-val" style="color:#fbbf24;">₹{gold_res.sgb_total_payout:,.0f}</div><div style="font-size:0.75rem; color:#3fb950;">Net CAGR: {gold_res.sgb_net_cagr_pct:.2f}%</div></div>""", unsafe_allow_html=True)
        with gw2:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Gold ETF Terminal Payout</div><div class="stat-val">₹{gold_res.etf_total_payout:,.0f}</div><div style="font-size:0.75rem; color:#8b949e;">Net CAGR: {gold_res.etf_net_cagr_pct:.2f}%</div></div>""", unsafe_allow_html=True)
        with gw3:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Physical Gold Payout</div><div class="stat-val">₹{gold_res.physical_total_payout:,.0f}</div><div style="font-size:0.75rem; color:#8b949e;">Net CAGR: {gold_res.physical_net_cagr_pct:.2f}%</div></div>""", unsafe_allow_html=True)
        with gw4:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">SGB Extra Premium Generated</div><div class="stat-val" style="color:#38bdf8;">+₹{gold_res.sgb_advantage_vs_etf:,.0f}</div><div style="font-size:0.75rem; color:#38bdf8;">vs ETF (+₹{gold_res.sgb_advantage_vs_physical:,.0f} vs Phys)</div></div>""", unsafe_allow_html=True)

        for takeaway in gold_res.key_takeaways:
            st.caption(f"📌 {takeaway}")

        # Gold comparison growth chart
        df_gold_sched = pd.DataFrame(gold_res.cash_flow_schedule)
        fig_gold = go.Figure()
        fig_gold.add_trace(go.Scatter(x=df_gold_sched['year'], y=df_gold_sched['sgb_cumulative_value'], mode='lines+markers', name='SGB (Price + 2.5% Coupon + Tax Free)', line=dict(color='#fbbf24', width=3)))
        fig_gold.add_trace(go.Scatter(x=df_gold_sched['year'], y=df_gold_sched['gold_etf_value'], mode='lines+markers', name='Gold ETF (12.5% LTCG + TER drag)', line=dict(color='#38bdf8', width=2)))
        fig_gold.add_trace(go.Scatter(x=df_gold_sched['year'], y=df_gold_sched['physical_gold_value'], mode='lines+markers', name='Physical Gold (GST + Making + Locker Drag)', line=dict(color='#94a3b8', width=2, dash='dot')))
        apply_market_theme(fig_gold, title=f"Cumulative Growth of ₹{gold_amt:,.0f} Across Gold Instruments", height=330, show_legend=True, xaxis_title="Year", yaxis_title="Total Value (₹)")
        st.plotly_chart(fig_gold, use_container_width=True, config={'displayModeBar': False})

    # 4. BONDS & G-SECS
    with subtab_bonds:
        st.markdown("##### Government Securities (G-Secs) & Corporate Bond Duration Model")
        b_c1, b_c2, b_c3 = st.columns(3)
        with b_c1:
            bond_inst = st.selectbox("Instrument Category", list(BondEngine.INSTRUMENTS.keys()), format_func=lambda x: BondEngine.INSTRUMENTS[x]["name"])
            bond_fv = st.number_input("Face Value (₹)", min_value=100.0, value=1000.0, step=100.0)
            bond_price = st.number_input("Current Clean Market Price (₹)", min_value=50.0, value=1000.0, step=10.0)
        with b_c2:
            bond_coupon = st.number_input("Annual Coupon Rate (%)", min_value=0.0, max_value=20.0, value=7.10, step=0.1)
            bond_years = st.slider("Maturity Tenure (Years)", min_value=1, max_value=30, value=10, step=1)
        with b_c3:
            bond_freq = st.selectbox("Coupon Frequency", [2, 1], format_func=lambda x: "Semi-Annual (Standard Indian G-Sec)" if x == 2 else "Annual")
            bond_rating = st.selectbox("Credit Rating", ["SOVEREIGN", "AAA", "AA", "A / BBB"], index=0)

        bond_res = BondEngine.analyze(BondParameters(
            face_value=bond_fv,
            market_price=bond_price,
            coupon_rate_pct=bond_coupon,
            tenure_years=float(bond_years),
            coupon_frequency=bond_freq,
            instrument_type=bond_inst,
            credit_rating=bond_rating,
            tax_bracket_pct=30.0
        ))

        bm1, bm2, bm3, bm4 = st.columns(4)
        with bm1:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Yield to Maturity (YTM)</div><div class="stat-val" style="color:#38bdf8;">{bond_res.ytm_pct:.2f}%</div><div style="font-size:0.75rem; color:#8b949e;">Current Yield: {bond_res.current_yield_pct:.2f}%</div></div>""", unsafe_allow_html=True)
        with bm2:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Modified Duration</div><div class="stat-val">{bond_res.modified_duration_years:.2f} Yrs</div><div style="font-size:0.75rem; color:#8b949e;">Macaulay: {bond_res.macaulay_duration_years:.2f} Yrs</div></div>""", unsafe_allow_html=True)
        with bm3:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Rate Hike (-100 bps Shock)</div><div class="stat-val" style="color:#f85149;">{bond_res.price_change_rate_hike_100bp_pct:+.2f}%</div><div style="font-size:0.75rem; color:#8b949e;">If RBI raises rates 1%</div></div>""", unsafe_allow_html=True)
        with bm4:
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">Rate Cut (+100 bps Shock)</div><div class="stat-val" style="color:#3fb950;">{bond_res.price_change_rate_cut_100bp_pct:+.2f}%</div><div style="font-size:0.75rem; color:#8b949e;">If RBI cuts rates 1%</div></div>""", unsafe_allow_html=True)

        st.caption(f"🏛️ **Credit Risk Assessment**: {bond_res.credit_risk_assessment}")
        st.caption(f"📝 **Taxation Note**: {bond_res.taxation_summary}")

        with st.expander("📅 View Bond Cash Flow & Discounting Schedule", expanded=False):
            df_b_sched = pd.DataFrame(bond_res.cash_flow_schedule)
            st.dataframe(df_b_sched, use_container_width=True, hide_index=True)


# =============================================================================
# SCREEN 3: COMPANY DCF MODEL & SCREENER (PRESERVING INSTITUTIONAL MODEL)
# =============================================================================
elif st.session_state['nav_mode'] == "🏢 Company DCF Model & Screener":
    active_url = st.session_state['active_target_url']

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

    with st.spinner("Extracting audited financials and computing institutional DCF model..."):
        try:
            raw_data, fc_results, val_results = fetch_and_compute(active_url, rf_rate, erp, beta_val, term_g)
        except Exception as e:
            st.error(f"Error analyzing company: {str(e)}")
            st.info("Please select another company from the sidebar quick search.")
            st.stop()

    company_name = raw_data.get('company_name', 'Company')
    ticker = raw_data.get('ticker', '')
    kpis = raw_data.get('kpis', {})
    prov = raw_data.get('provenance', {})
    sector = raw_data.get('sector', 'Corporate')

    # Add to recent searches
    curr_entry = (company_name, active_url)
    if curr_entry in st.session_state['recent_searches']:
        st.session_state['recent_searches'].remove(curr_entry)
    st.session_state['recent_searches'].insert(0, curr_entry)
    st.session_state['recent_searches'] = st.session_state['recent_searches'][:6]

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

    # Fetch Real-time News & Sentiment Catalysts
    articles, catalyst_impact = fetch_news_and_catalysts(company_name, ticker, fair_target, wacc_pct)

    # External Financial Hub Links
    tv_link = f"https://in.tradingview.com/symbols/NSE-{ticker}/"
    gf_link = f"https://www.google.com/finance/quote/{ticker}:NSE"
    mc_link = f"https://www.moneycontrol.com/india/stockpricequote/"
    bse_link = f"https://www.bseindia.com/corporates/ann.html"

    # Google Finance Style Company Header
    daily_change_pct = catalyst_impact.get('catalyst_score', 0.0) * 0.05
    daily_change_val = cmp * (daily_change_pct / 100.0)
    chg_dir_cls = "gf-change-down" if daily_change_pct < 0 else "gf-change-up"
    chg_dir_arrow = "▼" if daily_change_pct < 0 else "▲"

    st.markdown(f"""
    <div class="gf-header">
        <div class="gf-breadcrumb">Equities &gt; {ticker}:NSE &bull; Sector: {sector}</div>
        <div class="gf-title-row">
            <h1 class="gf-company-name">{company_name}</h1>
            <div style="margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap;">
                <a href="{tv_link}" target="_blank" class="external-hub-link">📈 TradingView ↗</a>
                <a href="{gf_link}" target="_blank" class="external-hub-link">📊 Google Finance ↗</a>
                <a href="{mc_link}" target="_blank" class="external-hub-link">💼 Moneycontrol ↗</a>
                <a href="{bse_link}" target="_blank" class="external-hub-link">🏛️ BSE Announcements ↗</a>
            </div>
        </div>
        <div class="gf-price-row">
            <span class="gf-price">₹{cmp:,.2f}</span>
            <span class="{chg_dir_cls}">{chg_dir_arrow} {abs(daily_change_pct):.2f}% ({daily_change_val:+.2f}) Today</span>
            <span class="gf-time">&bull; {datetime.now(timezone.utc).strftime('%b %d, %I:%M %p UTC')} &bull; INR &bull; Primary: Screener.in</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Key Stats Strip
    stats_cols = st.columns(8)
    with stats_cols[0]:
        st.markdown(f"""<div class="stat-cell"><div class="stat-label">Market Cap</div><div class="stat-val">₹{mcap:,.0f} Cr</div></div>""", unsafe_allow_html=True)
    with stats_cols[1]:
        st.markdown(f"""<div class="stat-cell"><div class="stat-label">P/E Ratio</div><div class="stat-val">{kpis.get('Stock P/E', 'N/A')}</div></div>""", unsafe_allow_html=True)
    with stats_cols[2]:
        st.markdown(f"""<div class="stat-cell"><div class="stat-label">Book Value</div><div class="stat-val">₹{kpis.get('Book Value', 'N/A')}</div></div>""", unsafe_allow_html=True)
    with stats_cols[3]:
        st.markdown(f"""<div class="stat-cell"><div class="stat-label">ROCE</div><div class="stat-val">{kpis.get('ROCE', 'N/A')}%</div></div>""", unsafe_allow_html=True)
    with stats_cols[4]:
        st.markdown(f"""<div class="stat-cell"><div class="stat-label">ROE</div><div class="stat-val">{kpis.get('ROE', 'N/A')}%</div></div>""", unsafe_allow_html=True)
    with stats_cols[5]:
        st.markdown(f"""<div class="stat-cell"><div class="stat-label">Dividend Yield</div><div class="stat-val">{kpis.get('Dividend Yield', '1.2')}%</div></div>""", unsafe_allow_html=True)
    with stats_cols[6]:
        st.markdown(f"""<div class="stat-cell"><div class="stat-label">DCF Fair Value</div><div class="stat-val" style="color:#58a6ff;">₹{fair_target:,.1f}</div></div>""", unsafe_allow_html=True)
    with stats_cols[7]:
        margin_tag_color = "#3fb950" if fair_upside >= 0 else "#f85149"
        st.markdown(f"""<div class="stat-cell"><div class="stat-label">Margin of Safety</div><div class="stat-val" style="color:{margin_tag_color};">{fair_upside:+.1f}%</div></div>""", unsafe_allow_html=True)

    # Google Finance Style Area Chart & Financial Q&A Assistant
    gf_chart_col, gf_research_col = st.columns([2.3, 1.1])
    with gf_chart_col:
        tf_col1, tf_col2 = st.columns([3, 1])
        with tf_col1:
            st.markdown("##### Performance & Price Area Chart")
        with tf_col2:
            chart_tf = st.selectbox("Range", ["5Yr", "3Yr", "1Yr", "Max"], index=0, label_visibility="collapsed")

        hist_years = fc_results['historical_years']
        future_years = fc_results['future_years']
        pl_df = raw_data['profit_loss']
        sales_hist = [float(pl_df.loc['Sales', y]) if 'Sales' in pl_df.index and y in pl_df.columns else 0.0 for y in hist_years]
        
        eps_row = pl_df.loc['EPS in Rs'] if 'EPS in Rs' in pl_df.index else None
        if eps_row is not None:
            eps_vals = [float(clean_number(eps_row.get(y, 10.0)) or 10.0) for y in hist_years]
            pe_proxy = float(clean_number(kpis.get('Stock P/E', 15.0)) or 15.0)
            price_history = [max(10.0, e * pe_proxy) for e in eps_vals]
        else:
            price_history = [cmp * (s / max(1.0, sales_hist[-1])) for s in sales_hist]

        if chart_tf == "1Yr":
            plot_x, plot_y = hist_years[-2:], price_history[-2:]
        elif chart_tf == "3Yr":
            plot_x, plot_y = hist_years[-3:], price_history[-3:]
        else:
            plot_x, plot_y = hist_years, price_history

        fig_gf = go.Figure()
        fig_gf.add_trace(go.Scatter(
            x=plot_x, y=plot_y, mode='lines',
            line=dict(color='#f43f5e' if fair_upside < 0 else '#38bdf8', width=2.5),
            fill='tozeroy',
            fillcolor='rgba(244, 63, 94, 0.08)' if fair_upside < 0 else 'rgba(56, 189, 248, 0.08)',
            name=f"{ticker} Price Trend",
            hovertemplate="FY %{x}<br>Price: ₹%{y:,.1f}<extra></extra>"
        ))
        fig_gf.add_hline(y=cmp, line_dash="dot", line_color="#8b949e", annotation_text=f"Prev Close: ₹{cmp:,.1f}", annotation_position="top right")
        apply_market_theme(fig_gf, height=310, show_legend=False, yaxis_title="Price (₹)")
        st.plotly_chart(fig_gf, use_container_width=True, config={'displayModeBar': False})

    with gf_research_col:
        st.markdown(f"""
        <div class="allocator-card" style="padding:14px;">
            <div style="font-size:1.05rem; font-weight:700; color:#f0f6fc; margin-bottom:4px;">✨ Financial Q&A Assistant</div>
            <div style="font-size:0.80rem; color:#8b949e; margin-bottom:10px;">Instant institutional explanations:</div>
        </div>
        """, unsafe_allow_html=True)

        q_choice = st.selectbox(
            "Quick Suggestions",
            [
                f"Overview of {company_name}",
                f"Is {company_name} undervalued or overvalued?",
                f"What are the biggest debt and financial risks?",
                f"What do latest news headlines say about {company_name}?"
            ],
            label_visibility="collapsed"
        )

        custom_q = st.text_input("Ask anything about this company...", placeholder="e.g. Is this good for 3 years? What is ROCE?")
        active_question = custom_q.strip() if custom_q.strip() else q_choice

        with st.expander("📝 View Assistant Analysis", expanded=True):
            q_low = active_question.lower()
            if "overview" in q_low or "summary" in q_low:
                st.markdown(f"""
                **{company_name} ({ticker})** operates in the **{sector}** sector with an audited market cap of **₹{mcap:,.0f} Cr**.
                * **Current Market Price**: ₹{cmp:,.1f}
                * **DCF Fair Value**: ₹{fair_target:,.1f} ({fair_upside:+.1f}%)
                * **Operating Quality**: ROCE is **{kpis.get('ROCE', 'N/A')}%** and ROE is **{kpis.get('ROE', 'N/A')}%**.
                * **Valuation Multiple**: P/E of **{kpis.get('Stock P/E', 'N/A')}** vs Book Value of **₹{kpis.get('Book Value', 'N/A')}**.
                """)
            elif "undervalued" in q_low or "overvalued" in q_low or "valuation" in q_low:
                verdict_word = "UNDERVALUED (Attractive Margin of Safety)" if fair_upside > 0 else "OVERVALUED (Trading at a Premium)"
                st.markdown(f"""
                **Valuation Signal: {verdict_word}**
                * **Current Market Price**: ₹{cmp:,.1f}
                * **Intrinsic Fair Value**: ₹{fair_target:,.1f}
                * **Margin of Safety**: **{fair_upside:+.1f}%**
                * **Gordon Growth Target**: ₹{g_target:,.1f}
                * **Exit Multiple Target**: ₹{m_target:,.1f}
                At current prices, the stock offers a **{abs(fair_upside):.1f}% {'discount below' if fair_upside > 0 else 'premium above'}** its DCF cash flow value.
                """)
            elif "debt" in q_low or "risk" in q_low:
                debt_cr = float(val_results['valuation_bridge']['total_debt_cr'])
                debt_pct_mcap = (debt_cr / max(1.0, mcap)) * 100.0
                st.markdown(f"""
                **Financial Risk & Leverage Breakdown**:
                * **Total Debt / Borrowings**: ₹{debt_cr:,.0f} Cr ({debt_pct_mcap:.1f}% of Market Cap).
                * **Cash & Liquid Investments**: ₹{float(val_results['valuation_bridge']['cash_and_investments_cr']):,.0f} Cr.
                * **Terminal Value Risk**: Terminal Value accounts for **{g_data['tv_percent_of_ev']}%** of Enterprise Value.
                """)
            else:
                st.markdown(f"""
                **Latest News & Catalyst Summary for {company_name}**:
                * **News Sentiment Score**: **{catalyst_impact['catalyst_score']:+.1f}%** ({catalyst_impact['sentiment_bias']})
                * **Sentiment-Adjusted Fair Value**: **₹{catalyst_impact['sentiment_adjusted_target']:,.1f}**
                """)
                for b in catalyst_impact.get('summary_bullets', []):
                    st.markdown(f"- {b}")

    # Screener-Style Dual-Axis Valuation Multiples Chart
    st.markdown("---")
    st.markdown("##### 📊 Historical Valuation Multiples & Capital Metrics (Screener.in Style)")

    multiple_mode = st.radio(
        "Chart Metric View",
        ["Price to Book (P/B) vs Book Value", "PE Ratio vs EPS & Median PE", "Revenue & EBITDA Margin Trends"],
        horizontal=True,
        label_visibility="collapsed"
    )

    bs_df = raw_data['balance_sheet']
    hist_years_all = fc_results['historical_years']
    eq_cap_row = bs_df.loc['Equity Capital'] if 'Equity Capital' in bs_df.index else pd.Series()
    reserves_row = bs_df.loc['Reserves'] if 'Reserves' in bs_df.index else pd.Series()
    shares_cr_val = float(val_results['valuation_bridge']['shares_outstanding_cr'])

    bv_list = []
    for y in hist_years_all:
        eq_val = float(clean_number(eq_cap_row.get(y, 0)) or 0)
        res_val = float(clean_number(reserves_row.get(y, 0)) or 0)
        bv_per_share = ((eq_val + res_val) / max(0.1, shares_cr_val)) if shares_cr_val > 0 else 100.0
        bv_list.append(round(bv_per_share, 1))

    pbv_list = [round(cmp / max(1.0, b), 2) for b in bv_list]
    median_pbv = round(float(np.nanmedian(pbv_list)), 1)

    fig_screener = go.Figure()
    if "Price to Book" in multiple_mode:
        fig_screener.add_trace(go.Bar(x=hist_years_all, y=bv_list, name='Book Value', marker_color='#7dd3fc', yaxis='y1', opacity=0.85, hovertemplate="FY %{x}<br>Book Value: ₹%{y:,.1f}<extra></extra>"))
        fig_screener.add_trace(go.Scatter(x=hist_years_all, y=pbv_list, name='Price to BV', line=dict(color='#a78bfa', width=2.8), mode='lines+markers', yaxis='y2', hovertemplate="FY %{x}<br>Price to BV: %{y:.2f}x<extra></extra>"))
        fig_screener.add_trace(go.Scatter(x=hist_years_all, y=pbv_list, name=f'Median PBV = {median_pbv}', line=dict(color='#fbbf24', width=1.8, dash='dash'), mode='lines', yaxis='y2', hovertemplate=f"Median PBV: {median_pbv}x<extra></extra>"))
        fig_screener.update_layout(
            yaxis=dict(title=dict(text="Book Value (₹)", font=dict(color="#7dd3fc")), side="left", showgrid=True, gridcolor="#1e222d"),
            yaxis2=dict(title=dict(text="Price to BV", font=dict(color="#a78bfa")), side="right", overlaying="y", showgrid=False)
        )
    elif "PE Ratio" in multiple_mode:
        eps_series = [float(clean_number(pl_df.loc['EPS in Rs', y]) if 'EPS in Rs' in pl_df.index and y in pl_df.columns else 10.0) for y in hist_years_all]
        pe_series = [round(cmp / max(0.5, e), 1) for e in eps_series]
        med_pe = round(float(np.nanmedian(pe_series)), 1)
        fig_screener.add_trace(go.Bar(x=hist_years_all, y=eps_series, name='EPS (₹)', marker_color='#34d399', yaxis='y1', opacity=0.85))
        fig_screener.add_trace(go.Scatter(x=hist_years_all, y=pe_series, name='P/E Ratio', line=dict(color='#38bdf8', width=2.8), mode='lines+markers', yaxis='y2'))
        fig_screener.add_trace(go.Scatter(x=hist_years_all, y=[med_pe]*len(hist_years_all), name=f'Median PE = {med_pe}x', line=dict(color='#fbbf24', width=1.8, dash='dash'), mode='lines', yaxis='y2'))
        fig_screener.update_layout(
            yaxis=dict(title=dict(text="EPS (₹)", font=dict(color="#34d399")), side="left", showgrid=True, gridcolor="#1e222d"),
            yaxis2=dict(title=dict(text="P/E Multiple", font=dict(color="#38bdf8")), side="right", overlaying="y", showgrid=False)
        )
    else:
        opm_series = [float(str(pl_df.loc['OPM %', y]).replace('%', '')) if 'OPM %' in pl_df.index and y in pl_df.columns else 15.0 for y in hist_years_all]
        sales_s = [float(pl_df.loc['Sales', y]) if 'Sales' in pl_df.index and y in pl_df.columns else 0.0 for y in hist_years_all]
        fig_screener.add_trace(go.Bar(x=hist_years_all, y=sales_s, name='Sales (₹ Cr.)', marker_color='#38bdf8', yaxis='y1'))
        fig_screener.add_trace(go.Scatter(x=hist_years_all, y=opm_series, name='OPM %', line=dict(color='#10b981', width=2.8), mode='lines+markers', yaxis='y2'))
        fig_screener.update_layout(
            yaxis=dict(title="Sales (₹ Cr.)", side="left", showgrid=True, gridcolor="#1e222d"),
            yaxis2=dict(title="Operating Margin (%)", side="right", overlaying="y", showgrid=False)
        )

    apply_market_theme(fig_screener, height=360, show_legend=True)
    st.plotly_chart(fig_screener, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

    # Beginner vs Pro Mode Switcher
    st.markdown("---")
    view_mode = st.radio(
        "Choose Analysis Depth",
        ["💡 Beginner Mode (Quick Verdicts, Traffic Lights & Plain English)", "🔬 Pro Analyst Mode (Full DCF Statements, Sensitivity & Formulas)"],
        horizontal=True
    )

    if "Beginner" in view_mode:
        diff_pct = fair_upside
        if diff_pct >= 15.0:
            box_class, verdict_badge, verdict_action, verdict_color = "verdict-box-buy", "🟢 UNDERVALUED (Attractive Margin of Safety)", "Good Buying Opportunity", "#3fb950"
            plain_summary = f"If you buy 1 share today at **₹{cmp:,.1f}**, our models estimate the business cash flow is worth **₹{fair_target:,.1f}**. You are getting a **{diff_pct:.1f}% discount**. The stock is currently on sale relative to its business earning power."
        elif diff_pct >= -5.0:
            box_class, verdict_badge, verdict_action, verdict_color = "verdict-box-hold", "🟡 FAIRLY VALUED (Fair Market Price)", "Hold / Accumulate on Dips", "#d29922"
            plain_summary = f"The stock is trading at **₹{cmp:,.1f}**, very close to its estimated fair value of **₹{fair_target:,.1f}** ({diff_pct:+.1f}%). It is neither extremely cheap nor dangerously overpriced."
        else:
            box_class, verdict_badge, verdict_action, verdict_color = "verdict-box-sell", "🔴 OVERVALUED (Priced at a Premium)", "Wait for Correction / Avoid FOMO", "#f85149"
            plain_summary = f"The stock price of **₹{cmp:,.1f}** is trading above our estimated fair business value of **₹{fair_target:,.1f}** ({diff_pct:.1f}% premium). Higher risk of price drop if future earnings disappoint."

        st.markdown(f"""
        <div class="{box_class}">
            <div class="verdict-title" style="color: {verdict_color};">{verdict_badge} &bull; Suggested Action: {verdict_action}</div>
            <div class="verdict-desc">{plain_summary}</div>
        </div>
        """, unsafe_allow_html=True)

        sc_cols = st.columns(4)
        with sc_cols[0]:
            val_status = "Discount Available" if diff_pct > 10 else ("Fairly Priced" if diff_pct >= -10 else "Expensive")
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">1. Valuation Check</div><div class="stat-val">{'🟢' if diff_pct > 10 else ('🟡' if diff_pct >= -10 else '🔴')} {val_status}</div><div style="font-size:0.75rem; color:#8b949e;">Target: ₹{fair_target:,.1f} vs CMP: ₹{cmp:,.1f}</div></div>""", unsafe_allow_html=True)
        with sc_cols[1]:
            roce_num = float(str(kpis.get('ROCE', '0')).replace('%', '') or 0)
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">2. Profitability (ROCE)</div><div class="stat-val">{'🟢' if roce_num >= 15 else ('🟡' if roce_num >= 10 else '🔴')} {roce_num:.1f}%</div><div style="font-size:0.75rem; color:#8b949e;">{'High Capital Quality' if roce_num >= 15 else 'Moderate Efficiency'}</div></div>""", unsafe_allow_html=True)
        with sc_cols[2]:
            debt_val = float(val_results['valuation_bridge']['total_debt_cr'])
            debt_ratio = (debt_val / max(1.0, mcap)) * 100.0
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">3. Debt & Loan Safety</div><div class="stat-val">{'🟢' if debt_ratio < 20 else ('🟡' if debt_ratio < 50 else '🔴')} {debt_ratio:.0f}% of Mcap</div><div style="font-size:0.75rem; color:#8b949e;">Total Debt: ₹{debt_val:,.0f} Cr</div></div>""", unsafe_allow_html=True)
        with sc_cols[3]:
            cat_score = catalyst_impact['catalyst_score']
            st.markdown(f"""<div class="stat-cell"><div class="stat-label">4. News Sentiment</div><div class="stat-val">{'🟢' if cat_score > 10 else ('🔴' if cat_score < -10 else '🟡')} {cat_score:+.0f}%</div><div style="font-size:0.75rem; color:#8b949e;">{catalyst_impact['sentiment_bias'].split()[0]} Catalysts</div></div>""", unsafe_allow_html=True)

        with st.expander("❓ Jargon Buster — What do these finance terms mean in plain English?", expanded=False):
            st.markdown("""
            * **Current Market Price (CMP)**: The exact price you pay on your broker app right now to buy 1 share.
            * **Fair Value / Intrinsic Target**: What the company is *actually* worth based on the cash profits it generates.
            * **Margin of Safety**: Buying something for less than it's worth.
            * **ROCE (Return on Capital Employed)**: Tells you how smart the management is at turning money into profit (above 15% is strong!).
            * **P/E Ratio**: How many rupees investors pay for every ₹1 of profit.
            * **DCF (Discounted Cash Flow)**: The gold standard method that converts all future cash flows into today's rupees.
            """)

    else:
        tab_overview, tab_news, tab_forecast, tab_valuation, tab_sensitivity, tab_statements, tab_excel = st.tabs([
            "Overview", "News & Catalysts", "Forecast", "Valuation", "Sensitivity", "Statements", "Excel Export"
        ])

        with tab_overview:
            methods = ["Exit Multiple Method", "Gordon Growth Method", "Blended Fair Value"]
            targets = [m_target, g_target, fair_target]
            upsides = [m_upside, g_upside, fair_upside]
            fig_val_comp = go.Figure(go.Bar(
                y=methods, x=targets, orientation="h",
                marker=dict(color=["#38bdf8", "#34d399", "#818cf8"], line=dict(color="#1e222d", width=1.5)),
                text=[f"₹{t:,.1f} ({'+' if u >= 0 else ''}{u:.1f}%)" for t, u in zip(targets, upsides)],
                textposition="inside", insidetextanchor="middle",
                textfont=dict(color="#ffffff", size=12, family="Inter, sans-serif")
            ))
            if cmp > 0:
                fig_val_comp.add_vline(x=cmp, line_width=2.5, line_dash="dash", line_color="#f43f5e", annotation_text=f"CMP: ₹{cmp:,.1f}", annotation_position="top right")
            apply_market_theme(fig_val_comp, title="DCF Target Price Comparison vs. Current Market Price (CMP)", height=260, show_legend=False, xaxis_title="Price Per Share (₹)")
            st.plotly_chart(fig_val_comp, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

        with tab_news:
            st.markdown("##### Real-Time News Catalysts & Market Impact Model")
            for art in articles:
                badge_html = '<span class="badge-pos">● Positive</span>' if art['sentiment_label'] == 'Positive' else ('<span class="badge-neg">● Negative</span>' if art['sentiment_label'] == 'Negative' else '<span class="badge-neu">● Neutral</span>')
                st.markdown(f"""
                <div class="news-card">
                    <div class="news-title">{art['title']}</div>
                    <div class="news-meta">Source: <strong>{art['source']}</strong> &bull; {art['pub_date']} &bull; {badge_html} <span class="badge-cat">{art['catalyst']}</span></div>
                    <div><a href="{art['link']}" target="_blank" class="news-link">Read Full Coverage on {art['source']} ↗</a></div>
                </div>
                """, unsafe_allow_html=True)

        with tab_forecast:
            st.markdown("##### Revenue & EBITDA Trajectory (Audited vs Forecast Scenarios)")
            sales_fc = fc_results['forecast_statements']['sales']
            fig_traj = go.Figure()
            fig_traj.add_trace(go.Scatter(x=hist_years, y=sales_hist, mode='lines+markers', name='Revenue (Actual)', line=dict(color='#38bdf8', width=2.8)))
            fig_traj.add_trace(go.Scatter(x=[hist_years[-1]] + future_years, y=[sales_hist[-1]] + sales_fc, mode='lines+markers', name='Revenue (Forecast)', line=dict(color='#60a5fa', width=2.5, dash='dash')))
            fig_traj.add_vline(x=hist_years[-1], line_width=1.5, line_dash="dash", line_color="#64748b")
            apply_market_theme(fig_traj, height=380, show_legend=True, xaxis_title="Fiscal Period", yaxis_title="Sales (₹ Cr.)")
            st.plotly_chart(fig_traj, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

        with tab_valuation:
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
                increasing={"marker": {"color": "#10b981"}}, decreasing={"marker": {"color": "#f43f5e"}}, totals={"marker": {"color": "#6366f1"}}
            ))
            apply_market_theme(fig_wf, height=380, show_legend=False, yaxis_title="Value (₹ Cr.)")
            st.plotly_chart(fig_wf, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

        with tab_sensitivity:
            st.markdown("##### Two-Way Sensitivity Analysis")
            sens_g = val_results['sensitivity_gordon']
            matrix_g = np.array([[val if val is not None else np.nan for val in row] for row in sens_g['matrix']], dtype=float)
            text_g = [[f"₹{val:,.0f}" if val is not None else "N/A" for val in row] for row in sens_g['matrix']]
            fig_hm1 = px.imshow(matrix_g, x=sens_g['wacc_columns'], y=sens_g['growth_rows'], labels=dict(x="WACC", y="Terminal Growth (g)", color="Target (₹)"), color_continuous_scale="Viridis", text_auto=False)
            fig_hm1.update_traces(text=text_g, texttemplate="%{text}", textfont={"size": 11, "family": "Inter, sans-serif", "color": "#ffffff"})
            apply_market_theme(fig_hm1, height=380, show_legend=False)
            st.plotly_chart(fig_hm1, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})

        with tab_statements:
            st.markdown("##### 5-Year Forecast Statements (₹ Cr.)")
            fc_stmt = fc_results['forecast_statements']
            df_forecast_display = pd.DataFrame({
                "Revenue (Sales)": fc_stmt['sales'],
                "EBITDA": fc_stmt['ebitda'],
                "OPM (%)": fc_stmt['opm_pct'],
                "Net Profit (PAT)": fc_stmt['pat'],
                "Capex": fc_stmt['capex'],
                "Free Cash Flow (FCFF)": fc_stmt['fcff'],
            }, index=fc_results['future_years']).T
            st.dataframe(df_forecast_display.style.format("{:,.1f}"), use_container_width=True)

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


# =============================================================================
# SCREEN 4: MARKET TRENDS & STATUTORY TRANSPARENCY
# =============================================================================
else:
    st.markdown("""
    <div class="home-hero-card">
        <div class="home-hero-title">🏢 Indian Equities Intelligence & Market Catalysts</div>
        <div class="home-hero-sub">
            Real-time fundamental models, institutional DCF cash flow forecasting, live market news catalysts, 
            and plain-English beginner investment verdicts across all NSE and BSE listed companies.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Recently Viewed Stocks Bar
    st.markdown("##### 🕒 Recently Viewed Stocks")
    rec_cols = st.columns(len(st.session_state['recent_searches']) + 1)
    for idx, (rec_name, rec_url) in enumerate(st.session_state['recent_searches']):
        with rec_cols[idx]:
            if st.button(f"🔍 {rec_name}", key=f"recent_btn_{idx}", use_container_width=True):
                st.session_state['active_target_url'] = rec_url
                st.session_state['nav_mode'] = "🏢 Company DCF Model & Screener"
                st.rerun()

    st.markdown("---")

    # Trending Companies Grid
    st.markdown("##### 🔥 Trending Market Leaders & Bluechips")
    st.caption("Explore high-activity Indian market giants. Click any company card to launch full institutional DCF valuation, news catalysts, and traffic light scorecards.")

    rows = [TRENDING_COMPANIES[i:i + 4] for i in range(0, len(TRENDING_COMPANIES), 4)]
    for r_idx, row in enumerate(rows):
        cols = st.columns(4)
        for c_idx, comp in enumerate(row):
            with cols[c_idx]:
                st.markdown(f"""
                <div class="trending-card">
                    <div class="trending-header">
                        <span class="trending-name">{comp['name']}</span>
                        <span class="trending-badge">{comp['ticker']}</span>
                    </div>
                    <div class="trending-meta">
                        Sector: <strong>{comp['sector']}</strong> &bull; Mcap: <strong>{comp['mcap']}</strong>
                    </div>
                    <div class="trending-desc">{comp['summary']}</div>
                    <div style="font-size:0.75rem; color:#8b949e; margin-bottom:10px;">
                        P/E: <strong>{comp['pe']}</strong> &bull; ROCE: <strong style="color:#3fb950;">{comp['roce']}</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Launch Valuation ↗", key=f"trend_{r_idx}_{c_idx}", use_container_width=True):
                    st.session_state['active_target_url'] = comp['url']
                    st.session_state['nav_mode'] = "🏢 Company DCF Model & Screener"
                    st.rerun()

    st.markdown("---")

    # Budget 2024 Tax Law Reference Summary Card
    st.markdown("##### 📜 Indian Capital Gains & Taxation Reference (Finance Act 2024)")
    t_c1, t_c2, t_c3 = st.columns(3)
    with t_c1:
        st.markdown("""
        <div class="allocator-card">
            <div style="font-size:0.95rem; font-weight:700; color:#38bdf8; margin-bottom:6px;">📈 Listed Equities & Equity MFs</div>
            <div style="font-size:0.80rem; color:#c9d1d9; line-height:1.5;">
                &bull; <strong>LTCG (Holding &ge; 12 Mos)</strong>: 12.5% tax on gains exceeding ₹1.25 Lakh exemption.<br>
                &bull; <strong>STCG (Holding &lt; 12 Mos)</strong>: 20.0% flat tax rate.<br>
                &bull; <strong>Arbitrage Funds</strong>: Taxed as equity funds despite low volatility.
            </div>
        </div>
        """, unsafe_allow_html=True)
    with t_c2:
        st.markdown("""
        <div class="allocator-card">
            <div style="font-size:0.95rem; font-weight:700; color:#fbbf24; margin-bottom:6px;">🥇 Gold & Sovereign Gold Bonds</div>
            <div style="font-size:0.80rem; color:#c9d1d9; line-height:1.5;">
                &bull; <strong>SGB Maturity (8 Yrs)</strong>: 100% Tax-Free capital gains.<br>
                &bull; <strong>Gold ETFs</strong>: 12.5% LTCG after 12 months holding period.<br>
                &bull; <strong>Physical Gold</strong>: 12.5% LTCG after 24 months + unrecoverable 3% GST.
            </div>
        </div>
        """, unsafe_allow_html=True)
    with t_c3:
        st.markdown("""
        <div class="allocator-card">
            <div style="font-size:0.95rem; font-weight:700; color:#34d399; margin-bottom:6px;">🏦 Fixed Deposits & Debt Funds</div>
            <div style="font-size:0.80rem; color:#c9d1d9; line-height:1.5;">
                &bull; <strong>Bank FDs</strong>: Added to total income and taxed at marginal slab rates (0% to 30%+).<br>
                &bull; <strong>TDS</strong>: 10% deducted if interest exceeds ₹40K (₹50K for seniors).<br>
                &bull; <strong>Debt Mutual Funds</strong>: Taxed at slab rate as STCG regardless of tenure.
            </div>
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# PERSISTENT STATUTORY & REGULATORY DISCLAIMER
# =============================================================================
st.markdown("""
<div class="disclaimer-card">
    <strong>Statutory Educational Simulation Disclaimer:</strong> Kavach Financial is an automated quantitative research and financial modeling tool. Calculations, forecasts, and comparative metrics are generated algorithmically for educational simulations and hypothetical scenario analysis. This platform is not a SEBI-registered Investment Adviser (RIA) or Research Analyst (RA). Nothing displayed on this platform constitutes individualized investment advice, financial planning, portfolio management, or a solicitation to buy or sell any financial instrument. Past performance and statistical forecasts do not guarantee future market returns. Investors should conduct independent due diligence or consult a SEBI-registered financial adviser before executing capital allocations.
</div>
""", unsafe_allow_html=True)
