"""
Kavach Financial | Multi-Asset Capital Allocator & Valuation Terminal
Google Finance, TradingView & Screener.in Integrated Pro Dark Terminal

Self-contained deployment edition for Streamlit Community Cloud.
"""

import os
import sys
import io
import re
import math
import urllib.parse
from datetime import datetime, timezone
from dataclasses import dataclass
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

# -----------------------------------------------------------------------------
# CORE STOCK MODEL IMPORTS (With fallback to src)
# -----------------------------------------------------------------------------
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


# =============================================================================
# SELF-CONTAINED MULTI-ASSET ENGINES (Budget 2024 Rules)
# Embedded directly so Streamlit Cloud never encounters ModuleNotFoundError!
# =============================================================================

# -------------------- 1. FIXED DEPOSIT CALCULATOR --------------------
@dataclass
class FDParameters:
    principal: float
    tenure_months: int
    interest_rate_pct: float
    compounding_frequency: str = "quarterly"
    tax_bracket_pct: float = 30.0
    is_senior_citizen: bool = False
    institution_type: str = "scheduled_commercial_bank"
    expected_inflation_pct: float = 6.0
    premature_penalty_pct: float = 1.0


@dataclass
class FDAnalysisResult:
    principal: float
    tenure_months: int
    gross_maturity_amount: float
    gross_interest_earned: float
    tds_deducted: float
    total_tax_liability: float
    net_maturity_amount: float
    net_post_tax_interest: float
    effective_annual_yield_pct: float
    net_post_tax_annual_yield_pct: float
    real_inflation_adjusted_yield_pct: float
    dicgc_covered_amount: float
    dicgc_uncovered_amount: float
    dicgc_coverage_status: str
    tds_applicability_note: str
    premature_exit_value: float
    quarterly_schedule: List[Dict[str, Any]]
    key_risks_and_notes: List[str]


class FixedDepositCalculator:
    DICGC_MAX_LIMIT = 500000.0
    TDS_THRESHOLD_GENERAL = 40000.0
    TDS_THRESHOLD_SENIOR = 50000.0

    @classmethod
    def calculate(cls, params: FDParameters) -> FDAnalysisResult:
        if params.principal <= 0:
            raise ValueError("Principal amount must be greater than zero.")
        if params.tenure_months <= 0:
            raise ValueError("Tenure in months must be at least 1 month.")
        if params.interest_rate_pct < 0:
            raise ValueError("Interest rate cannot be negative.")

        r = params.interest_rate_pct / 100.0
        t_years = params.tenure_months / 12.0
        freq = params.compounding_frequency.lower()
        n = 12 if freq == "monthly" else (4 if freq == "quarterly" else (2 if freq == "half_yearly" else (1 if freq == "annual" else 0)))

        if n > 0:
            gross_maturity = params.principal * math.pow(1.0 + (r / n), n * t_years)
        else:
            gross_maturity = params.principal * (1.0 + (r * t_years))

        gross_interest = gross_maturity - params.principal
        effective_annual_yield = ((math.pow(gross_maturity / params.principal, 1.0 / t_years) - 1.0) * 100.0) if t_years > 0 else params.interest_rate_pct

        annual_interest_approx = gross_interest / max(t_years, 1.0)
        tds_threshold = cls.TDS_THRESHOLD_SENIOR if params.is_senior_citizen else cls.TDS_THRESHOLD_GENERAL
        tds_applicable = (annual_interest_approx > tds_threshold) and (params.institution_type != "post_office")
        estimated_tds = gross_interest * 0.10 if tds_applicable else 0.0

        tax_bracket_rate = params.tax_bracket_pct / 100.0
        total_tax_liability = gross_interest * tax_bracket_rate
        net_post_tax_interest = gross_interest - total_tax_liability
        net_maturity = params.principal + net_post_tax_interest

        net_post_tax_yield = ((math.pow(net_maturity / params.principal, 1.0 / t_years) - 1.0) * 100.0) if t_years > 0 else (effective_annual_yield * (1.0 - tax_bracket_rate))
        i_rate = params.expected_inflation_pct / 100.0
        real_yield_pct = (((1.0 + (net_post_tax_yield / 100.0)) / (1.0 + i_rate)) - 1.0) * 100.0

        if params.institution_type == "post_office":
            dicgc_covered = gross_maturity
            dicgc_uncovered = 0.0
            dicgc_status = "100% Sovereign Guaranteed (Ministry of Finance, Govt of India)"
        elif params.institution_type in ["scheduled_commercial_bank", "small_finance_bank"]:
            dicgc_covered = min(gross_maturity, cls.DICGC_MAX_LIMIT)
            dicgc_uncovered = max(0.0, gross_maturity - cls.DICGC_MAX_LIMIT)
            dicgc_status = f"₹5,00,000 Insured by DICGC (RBI). ₹{dicgc_uncovered:,.0f} above insurance cap." if dicgc_uncovered > 0 else "100% Insured under DICGC ₹5 Lakh limit."
        else:
            dicgc_covered = 0.0
            dicgc_uncovered = gross_maturity
            dicgc_status = "Zero DICGC Cover. Subject to issuer corporate credit rating."

        half_t = max(t_years * 0.5, 0.25)
        penalized_r = max((params.interest_rate_pct - params.premature_penalty_pct) / 100.0, 0.01)
        premature_exit_val = params.principal * math.pow(1.0 + (penalized_r / 4.0), 4.0 * half_t)

        tds_note = f"TDS @ 10% (₹{estimated_tds:,.0f}) deducted by bank as interest exceeds ₹{tds_threshold:,.0f}. Final tax at {params.tax_bracket_pct:.0f}% slab is ₹{total_tax_liability:,.0f}." if tds_applicable else f"No TDS deducted (annual interest < ₹{tds_threshold:,.0f}). Taxed at {params.tax_bracket_pct:.0f}% in ITR."

        quarterly_schedule: List[Dict[str, Any]] = []
        total_quarters = max(int(params.tenure_months / 3), 1)
        q_rate = r / 4.0
        curr_bal = params.principal
        for q in range(1, total_quarters + 1):
            q_interest = curr_bal * q_rate
            curr_bal += q_interest
            quarterly_schedule.append({
                "quarter": q, "month": q * 3,
                "opening_balance": round(curr_bal - q_interest, 2),
                "quarterly_interest": round(q_interest, 2),
                "closing_balance": round(curr_bal, 2),
            })

        risks = []
        if real_yield_pct < 0:
            risks.append(f"Negative Real Return: Net yield ({net_post_tax_yield:.2f}%) trails inflation ({params.expected_inflation_pct:.1f}%).")
        if dicgc_uncovered > 0:
            risks.append(f"Uncovered Balance: ₹{dicgc_uncovered:,.0f} is above DICGC ₹5L cover.")

        return FDAnalysisResult(
            principal=params.principal, tenure_months=params.tenure_months,
            gross_maturity_amount=round(gross_maturity, 2), gross_interest_earned=round(gross_interest, 2),
            tds_deducted=round(estimated_tds, 2), total_tax_liability=round(total_tax_liability, 2),
            net_maturity_amount=round(net_maturity, 2), net_post_tax_interest=round(net_post_tax_interest, 2),
            effective_annual_yield_pct=round(effective_annual_yield, 2),
            net_post_tax_annual_yield_pct=round(net_post_tax_yield, 2),
            real_inflation_adjusted_yield_pct=round(real_yield_pct, 2),
            dicgc_covered_amount=round(dicgc_covered, 2), dicgc_uncovered_amount=round(dicgc_uncovered, 2),
            dicgc_coverage_status=dicgc_status, tds_applicability_note=tds_note,
            premature_exit_value=round(premature_exit_val, 2), quarterly_schedule=quarterly_schedule,
            key_risks_and_notes=risks
        )


# -------------------- 2. MUTUAL FUND ANALYZER --------------------
@dataclass
class MutualFundParameters:
    investment_mode: str = "lumpsum"
    investment_amount: float = 100000.0
    tenure_years: float = 5.0
    category: str = "flexi_cap"
    expected_cagr_pct: float = 12.0
    direct_expense_ratio_pct: float = 0.65
    regular_expense_ratio_pct: float = 1.65
    tax_bracket_pct: float = 30.0
    expected_inflation_pct: float = 6.0


@dataclass
class MutualFundAnalysisResult:
    investment_mode: str
    total_invested_capital: float
    tenure_years: float
    category_name: str
    direct_corpus: float
    regular_corpus: float
    expense_drag_lost_wealth: float
    gross_gains_direct: float
    estimated_tax_budget_2024: float
    net_post_tax_corpus: float
    net_cagr_post_tax_pct: float
    real_inflation_adjusted_cagr_pct: float
    tax_treatment_summary: str
    historical_risk_profile: Dict[str, Any]
    wealth_growth_schedule: List[Dict[str, Any]]
    suitability_verdict: str
    cautions_and_warnings: List[str]


class MutualFundAnalyzer:
    CATEGORIES = {
        "large_cap": {"name": "Large Cap Equity / Nifty 50 Index", "typical_cagr": 12.0, "direct_ter": 0.35, "regular_ter": 1.25, "equity_tax_status": True, "min_recommended_horizon_years": 5.0},
        "flexi_cap": {"name": "Flexi Cap Equity Fund", "typical_cagr": 13.5, "direct_ter": 0.70, "regular_ter": 1.75, "equity_tax_status": True, "min_recommended_horizon_years": 5.0},
        "mid_cap": {"name": "Mid Cap Equity Fund", "typical_cagr": 15.0, "direct_ter": 0.75, "regular_ter": 1.85, "equity_tax_status": True, "min_recommended_horizon_years": 7.0},
        "arbitrage": {"name": "Arbitrage Fund (Cash-Futures Spread)", "typical_cagr": 7.0, "direct_ter": 0.30, "regular_ter": 0.95, "equity_tax_status": True, "min_recommended_horizon_years": 0.5},
        "liquid": {"name": "Liquid / Overnight Debt Fund", "typical_cagr": 6.6, "direct_ter": 0.15, "regular_ter": 0.35, "equity_tax_status": False, "min_recommended_horizon_years": 0.1},
        "aggressive_hybrid": {"name": "Aggressive Hybrid Fund (65-80% Equity)", "typical_cagr": 11.5, "direct_ter": 0.65, "regular_ter": 1.60, "equity_tax_status": True, "min_recommended_horizon_years": 3.0}
    }

    EQUITY_LTCG_EXEMPTION = 125000.0
    EQUITY_LTCG_TAX_RATE = 0.125
    EQUITY_STCG_TAX_RATE = 0.200

    @classmethod
    def analyze(cls, params: MutualFundParameters) -> MutualFundAnalysisResult:
        cat_key = params.category if params.category in cls.CATEGORIES else "flexi_cap"
        cat_info = cls.CATEGORIES[cat_key]
        cagr = params.expected_cagr_pct / 100.0
        ter_dir = params.direct_expense_ratio_pct / 100.0
        ter_reg = params.regular_expense_ratio_pct / 100.0
        t_years = max(params.tenure_years, 0.25)

        net_cagr_direct = max(cagr - ter_dir, -0.90)
        net_cagr_reg = max(cagr - ter_reg, -0.90)

        if params.investment_mode.lower() == "sip":
            total_invested = params.investment_amount * 12.0 * t_years
            months = int(t_years * 12)
            r_month_dir = math.pow(1.0 + net_cagr_direct, 1.0 / 12.0) - 1.0
            r_month_reg = math.pow(1.0 + net_cagr_reg, 1.0 / 12.0) - 1.0
            direct_corpus, regular_corpus = 0.0, 0.0
            for _ in range(months):
                direct_corpus = (direct_corpus + params.investment_amount) * (1.0 + r_month_dir)
                regular_corpus = (regular_corpus + params.investment_amount) * (1.0 + r_month_reg)
        else:
            total_invested = params.investment_amount
            direct_corpus = total_invested * math.pow(1.0 + net_cagr_direct, t_years)
            regular_corpus = total_invested * math.pow(1.0 + net_cagr_reg, t_years)

        lost_wealth = max(0.0, direct_corpus - regular_corpus)
        gross_gains_direct = max(0.0, direct_corpus - total_invested)

        if cat_info["equity_tax_status"]:
            if t_years >= 1.0:
                taxable_gain = max(0.0, gross_gains_direct - cls.EQUITY_LTCG_EXEMPTION)
                tax_liability = taxable_gain * cls.EQUITY_LTCG_TAX_RATE
                tax_summary = f"Equity LTCG (Budget 2024): 12.5% tax above ₹1.25 Lakh exemption. Estimated Tax: ₹{tax_liability:,.0f}."
            else:
                tax_liability = gross_gains_direct * cls.EQUITY_STCG_TAX_RATE
                tax_summary = f"Equity STCG (Budget 2024): 20.0% flat tax on gains < 12 mos. Estimated Tax: ₹{tax_liability:,.0f}."
        else:
            tax_liability = gross_gains_direct * (params.tax_bracket_pct / 100.0)
            tax_summary = f"Debt Fund Slab Tax: Gains taxed at your {params.tax_bracket_pct:.0f}% slab rate. Estimated Tax: ₹{tax_liability:,.0f}."

        net_corpus = direct_corpus - tax_liability
        net_cagr_post_tax = ((math.pow(net_corpus / total_invested, 1.0 / t_years) - 1.0) * 100.0) if total_invested > 0 and t_years > 0 else 0.0
        real_cagr_pct = (((1.0 + (net_cagr_post_tax / 100.0)) / (1.0 + (params.expected_inflation_pct / 100.0))) - 1.0) * 100.0

        schedule: List[Dict[str, Any]] = []
        for yr in range(1, max(int(t_years), 1) + 1):
            if params.investment_mode.lower() == "sip":
                inv_so_far = params.investment_amount * 12.0 * yr
                dir_val, reg_val = 0.0, 0.0
                r_m_d = math.pow(1.0 + net_cagr_direct, 1.0 / 12.0) - 1.0
                r_m_r = math.pow(1.0 + net_cagr_reg, 1.0 / 12.0) - 1.0
                for _ in range(yr * 12):
                    dir_val = (dir_val + params.investment_amount) * (1.0 + r_m_d)
                    reg_val = (reg_val + params.investment_amount) * (1.0 + r_m_r)
            else:
                inv_so_far = total_invested
                dir_val = total_invested * math.pow(1.0 + net_cagr_direct, yr)
                reg_val = total_invested * math.pow(1.0 + net_cagr_reg, yr)
            schedule.append({
                "year": yr, "invested_capital": round(inv_so_far, 2),
                "direct_corpus": round(dir_val, 2), "regular_corpus": round(reg_val, 2),
                "advisor_commission_drag": round(max(0.0, dir_val - reg_val), 2)
            })

        verdict = f"Aligned Horizon: {t_years:.1f} Yrs fits {cat_info['name']}." if t_years >= cat_info["min_recommended_horizon_years"] else f"Horizon Warning: {t_years:.1f} Yrs is below recommended {cat_info['min_recommended_horizon_years']:.0f}+ Yrs."
        cautions = [f"Intermediary Commission Drag: ₹{lost_wealth:,.0f} lost to distributor commissions in regular plans."] if lost_wealth > 20000 else []

        return MutualFundAnalysisResult(
            investment_mode=params.investment_mode.upper(), total_invested_capital=round(total_invested, 2),
            tenure_years=params.tenure_years, category_name=cat_info["name"],
            direct_corpus=round(direct_corpus, 2), regular_corpus=round(regular_corpus, 2),
            expense_drag_lost_wealth=round(lost_wealth, 2), gross_gains_direct=round(gross_gains_direct, 2),
            estimated_tax_budget_2024=round(tax_liability, 2), net_post_tax_corpus=round(net_corpus, 2),
            net_cagr_post_tax_pct=round(net_cagr_post_tax, 2), real_inflation_adjusted_cagr_pct=round(real_cagr_pct, 2),
            tax_treatment_summary=tax_summary, historical_risk_profile=cat_info, wealth_growth_schedule=schedule,
            suitability_verdict=verdict, cautions_and_warnings=cautions
        )


# -------------------- 3. GOLD & SGB ENGINE --------------------
@dataclass
class GoldInvestmentParameters:
    investment_amount: float = 100000.0
    tenure_years: float = 8.0
    expected_gold_cagr_pct: float = 8.5
    tax_bracket_pct: float = 30.0
    sgb_coupon_rate_pct: float = 2.50
    gold_etf_ter_pct: float = 0.40
    physical_gold_making_and_gst_pct: float = 8.0
    annual_locker_cost: float = 1500.0


@dataclass
class GoldComparisonResult:
    investment_amount: float
    tenure_years: float
    expected_gold_cagr_pct: float
    sgb_total_payout: float
    sgb_net_gains: float
    sgb_net_cagr_pct: float
    etf_total_payout: float
    etf_net_gains: float
    etf_net_cagr_pct: float
    physical_total_payout: float
    physical_net_gains: float
    physical_net_cagr_pct: float
    sgb_advantage_vs_etf: float
    sgb_advantage_vs_physical: float
    tax_comparison_notes: Dict[str, str]
    cash_flow_schedule: List[Dict[str, Any]]
    key_takeaways: List[str]


class GoldEngine:
    @classmethod
    def compare(cls, params: GoldInvestmentParameters) -> GoldComparisonResult:
        amt = params.investment_amount
        t = max(params.tenure_years, 1.0)
        g_cagr = params.expected_gold_cagr_pct / 100.0
        tax_slab = params.tax_bracket_pct / 100.0

        # SGB: Gold appreciation + 2.5% coupon (slab taxed) + 100% tax free at maturity
        sgb_gold_value = amt * math.pow(1.0 + g_cagr, t)
        annual_net_coupon = (amt * (params.sgb_coupon_rate_pct / 100.0)) * (1.0 - tax_slab)
        total_coupons = annual_net_coupon * t
        sgb_cg_tax = 0.0 if t >= 5.0 else (sgb_gold_value - amt) * 0.125
        sgb_total_payout = sgb_gold_value - sgb_cg_tax + total_coupons
        sgb_net_gains = sgb_total_payout - amt
        sgb_net_cagr = ((math.pow(sgb_total_payout / amt, 1.0 / t) - 1.0) * 100.0)

        # Gold ETF: 12.5% LTCG after 12 months + expense ratio
        etf_ter = params.gold_etf_ter_pct / 100.0
        etf_gross = amt * math.pow(1.0 + max(g_cagr - etf_ter, -0.9), t)
        etf_gains = max(0.0, etf_gross - amt)
        etf_tax = etf_gains * 0.125 if t >= 1.0 else etf_gains * 0.20
        etf_total_payout = etf_gross - etf_tax
        etf_net_gains = etf_total_payout - amt
        etf_net_cagr = ((math.pow(etf_total_payout / amt, 1.0 / t) - 1.0) * 100.0)

        # Physical Gold: 3% GST + Making charge friction + locker rent
        friction_rate = params.physical_gold_making_and_gst_pct / 100.0
        eff_gold = amt / (1.0 + friction_rate)
        phys_gross = eff_gold * math.pow(1.0 + g_cagr, t)
        phys_net_pretax = max(0.0, phys_gross - (params.annual_locker_cost * t))
        phys_gains = max(0.0, phys_net_pretax - amt)
        phys_tax = phys_gains * 0.125 if t >= 2.0 else phys_gains * tax_slab
        phys_total_payout = phys_net_pretax - phys_tax
        phys_net_gains = phys_total_payout - amt
        phys_net_cagr = ((math.pow(max(phys_total_payout, 1.0) / amt, 1.0 / t) - 1.0) * 100.0)

        schedule: List[Dict[str, Any]] = []
        for yr in range(1, int(t) + 1):
            s_val = (amt * math.pow(1.0 + g_cagr, yr)) + (annual_net_coupon * yr)
            e_val = amt * math.pow(1.0 + max(g_cagr - etf_ter, -0.9), yr)
            p_val = (eff_gold * math.pow(1.0 + g_cagr, yr)) - (params.annual_locker_cost * yr)
            schedule.append({
                "year": yr, "sgb_cumulative_value": round(s_val, 2),
                "gold_etf_value": round(e_val, 2), "physical_gold_value": round(p_val, 2)
            })

        takeaways = [
            f"SGB Advantage: Generates ₹{sgb_total_payout - etf_total_payout:,.0f} more than Gold ETFs and ₹{sgb_total_payout - phys_total_payout:,.0f} more than Physical Gold.",
            "Tax-Free Redemption: SGB capital gains are 100% exempt from income tax at RBI maturity (8 years).",
            "Liquidity Note: Gold ETFs provide instant intraday liquidity on NSE/BSE. SGB secondary markets can trade at discounts."
        ]

        return GoldComparisonResult(
            investment_amount=amt, tenure_years=t, expected_gold_cagr_pct=params.expected_gold_cagr_pct,
            sgb_total_payout=round(sgb_total_payout, 2), sgb_net_gains=round(sgb_net_gains, 2),
            sgb_net_cagr_pct=round(sgb_net_cagr, 2), etf_total_payout=round(etf_total_payout, 2),
            etf_net_gains=round(etf_net_gains, 2), etf_net_cagr_pct=round(etf_net_cagr, 2),
            physical_total_payout=round(phys_total_payout, 2), physical_net_gains=round(phys_net_gains, 2),
            physical_net_cagr_pct=round(phys_net_cagr, 2), sgb_advantage_vs_etf=round(sgb_total_payout - etf_total_payout, 2),
            sgb_advantage_vs_physical=round(sgb_total_payout - phys_total_payout, 2),
            tax_comparison_notes={"SGB": "100% Tax Free at maturity", "ETF": "12.5% LTCG", "Physical": "12.5% LTCG + GST friction"},
            cash_flow_schedule=schedule, key_takeaways=takeaways
        )


# -------------------- 4. BOND & DURATION ENGINE --------------------
@dataclass
class BondParameters:
    face_value: float = 1000.0
    market_price: float = 1000.0
    coupon_rate_pct: float = 7.10
    tenure_years: float = 10.0
    coupon_frequency: int = 2
    instrument_type: str = "g_sec"
    credit_rating: str = "SOVEREIGN"
    tax_bracket_pct: float = 30.0
    expected_inflation_pct: float = 6.0


@dataclass
class BondAnalysisResult:
    face_value: float
    market_price: float
    coupon_rate_pct: float
    tenure_years: float
    coupon_frequency: int
    instrument_name: str
    credit_rating: str
    ytm_pct: float
    current_yield_pct: float
    macaulay_duration_years: float
    modified_duration_years: float
    price_change_rate_hike_100bp_pct: float
    price_change_rate_cut_100bp_pct: float
    total_coupons_expected: float
    gross_terminal_cashflow: float
    net_post_tax_ytm_pct: float
    real_inflation_adjusted_ytm_pct: float
    cash_flow_schedule: List[Dict[str, Any]]
    credit_risk_assessment: str
    taxation_summary: str
    key_observations: List[str]


class BondEngine:
    INSTRUMENTS = {
        "g_sec": {"name": "Central Government Security (G-Sec)", "default_rating": "SOVEREIGN"},
        "t_bill": {"name": "Treasury Bill (91 / 182 / 364 Days)", "default_rating": "SOVEREIGN"},
        "psu_aaa": {"name": "PSU Bond (REC/PFC/NABARD)", "default_rating": "AAA"},
        "corporate_aa": {"name": "Corporate Bond (Tier 1 Private)", "default_rating": "AA"},
        "corporate_high_yield": {"name": "High Yield Bond / SDI", "default_rating": "A / BBB"},
    }

    @classmethod
    def calculate_ytm(cls, face_value: float, price: float, coupon_rate: float, tenure_years: float, frequency: int = 2) -> float:
        if price <= 0 or tenure_years <= 0:
            return 0.0
        n_periods = int(round(tenure_years * frequency))
        if n_periods == 0:
            return 0.0
        c_period = (face_value * (coupon_rate / 100.0)) / frequency
        if c_period == 0:
            return ((math.pow(face_value / price, 1.0 / tenure_years) - 1.0) * 100.0)

        low, high = 0.000001, 1.0
        for _ in range(80):
            mid = (low + high) / 2.0
            pv = sum([c_period / math.pow(1.0 + mid, t) for t in range(1, n_periods + 1)]) + (face_value / math.pow(1.0 + mid, n_periods))
            if abs(pv - price) < 1e-5:
                return mid * frequency * 100.0
            if pv > price:
                low = mid
            else:
                high = mid
        return ((low + high) / 2.0) * frequency * 100.0

    @classmethod
    def analyze(cls, params: BondParameters) -> BondAnalysisResult:
        inst_key = params.instrument_type if params.instrument_type in cls.INSTRUMENTS else "g_sec"
        inst_info = cls.INSTRUMENTS[inst_key]
        freq = max(params.coupon_frequency, 1)
        t_years = max(params.tenure_years, 0.25)
        n_periods = int(round(t_years * freq))
        c_payment = (params.face_value * (params.coupon_rate_pct / 100.0)) / freq

        ytm = cls.calculate_ytm(params.face_value, params.market_price, params.coupon_rate_pct, t_years, freq)
        y_p = (ytm / 100.0) / freq

        if y_p > 0 and n_periods > 0:
            pv_cf_sum = sum([(c_payment + (params.face_value if t == n_periods else 0.0)) / math.pow(1.0 + y_p, t) for t in range(1, n_periods + 1)])
            w_cf_sum = sum([((t / freq) * (c_payment + (params.face_value if t == n_periods else 0.0))) / math.pow(1.0 + y_p, t) for t in range(1, n_periods + 1)])
            macaulay = w_cf_sum / max(pv_cf_sum, 0.001)
            modified = macaulay / (1.0 + y_p)
        else:
            macaulay, modified = t_years, t_years

        price_hike_100bp = - modified * 1.0
        price_cut_100bp = modified * 1.0
        current_yield = (params.face_value * (params.coupon_rate_pct / 100.0) / params.market_price) * 100.0

        total_coupons = c_payment * n_periods
        gross_terminal = total_coupons + params.face_value

        tax_slab = params.tax_bracket_pct / 100.0
        net_coupons = total_coupons * (1.0 - tax_slab)
        cap_gain = max(0.0, params.face_value - params.market_price)
        cg_tax = cap_gain * 0.125 if t_years >= 1.0 else cap_gain * tax_slab
        net_terminal = params.face_value - cg_tax + net_coupons
        net_post_tax_ytm = ((math.pow(net_terminal / params.market_price, 1.0 / t_years) - 1.0) * 100.0) if params.market_price > 0 and t_years > 0 else (ytm * (1.0 - tax_slab))
        real_ytm = (((1.0 + (net_post_tax_ytm / 100.0)) / (1.0 + (params.expected_inflation_pct / 100.0))) - 1.0) * 100.0

        schedule: List[Dict[str, Any]] = []
        for period in range(1, min(n_periods + 1, 15)):
            cf = c_payment + (params.face_value if period == n_periods else 0.0)
            schedule.append({
                "period": period, "year": round(period / freq, 2),
                "coupon_received": round(c_payment, 2),
                "principal_repayment": round(params.face_value if period == n_periods else 0.0, 2),
                "total_cashflow": round(cf, 2)
            })

        credit_assess = "Zero Credit Risk: 100% sovereign backing." if params.credit_rating == "SOVEREIGN" else f"Credit Rating: {params.credit_rating}."
        tax_sum = f"Coupons taxed at {params.tax_bracket_pct:.0f}% slab. Discount redemption taxed at 12.5% LTCG."

        return BondAnalysisResult(
            face_value=params.face_value, market_price=params.market_price, coupon_rate_pct=params.coupon_rate_pct,
            tenure_years=t_years, coupon_frequency=freq, instrument_name=inst_info["name"], credit_rating=params.credit_rating,
            ytm_pct=round(ytm, 2), current_yield_pct=round(current_yield, 2), macaulay_duration_years=round(macaulay, 2),
            modified_duration_years=round(modified, 2), price_change_rate_hike_100bp_pct=round(price_hike_100bp, 2),
            price_change_rate_cut_100bp_pct=round(price_cut_100bp, 2), total_coupons_expected=round(total_coupons, 2),
            gross_terminal_cashflow=round(gross_terminal, 2), net_post_tax_ytm_pct=round(net_post_tax_ytm, 2),
            real_inflation_adjusted_ytm_pct=round(real_ytm, 2), cash_flow_schedule=schedule, credit_risk_assessment=credit_assess,
            taxation_summary=tax_sum, key_observations=[f"Modified Duration: {modified:.2f} Yrs (Sensitivity: ~{abs(price_hike_100bp):.2f}% per 100 bps rate change)."]
        )


# -------------------- 5. SUITABILITY ENGINE --------------------
@dataclass
class GoalProfile:
    goal_name: str = "Wealth Building"
    investment_amount: float = 200000.0
    horizon_months: int = 36
    liquidity_need: str = "moderate"
    risk_profile: str = "moderate"
    tax_bracket_pct: float = 30.0


@dataclass
class AssetSuitabilityScore:
    asset_class: str
    display_name: str
    suitability_score: int
    fit_status: str
    fit_color: str
    primary_reason: str
    tax_efficiency_rating: str


@dataclass
class SuitabilityDiagnosis:
    goal_profile: GoalProfile
    asset_scores: List[AssetSuitabilityScore]
    top_recommended_asset: str
    critical_warnings: List[str]
    tax_optimization_tips: List[str]


class SuitabilityEngine:
    @classmethod
    def diagnose(cls, profile: GoalProfile) -> SuitabilityDiagnosis:
        h_months = max(profile.horizon_months, 1)
        h_years = h_months / 12.0
        risk = profile.risk_profile.lower()
        tax = profile.tax_bracket_pct

        scores: List[AssetSuitabilityScore] = []
        warnings: List[str] = []
        tax_tips: List[str] = []

        # 1. Bank FD
        fd_score = 75
        if h_months <= 24:
            fd_score += 20
        elif h_months > 60:
            fd_score -= 30
        if tax >= 20.0:
            fd_score -= 15
            fd_tax = "Poor (Slab Taxed)"
            tax_tips.append(f"FD Tax Drag: At {tax:.0f}% slab, FD interest is taxed without indexation. Arbitrage funds offer superior post-tax yield.")
        else:
            fd_tax = "Medium"
        scores.append(cls._build("bank_fd", "Fixed Deposit / T-Bills", fd_score, fd_tax, "Capital preservation for short horizons; tax-heavy for long tenures."))

        # 2. Arbitrage Funds
        arb_score = 80
        if h_months <= 36:
            arb_score += 15
        if tax >= 20.0:
            arb_score += 15
            arb_tax = "High (Equity 12.5% LTCG)"
        else:
            arb_tax = "Medium"
        scores.append(cls._build("arbitrage_liquid", "Arbitrage / Liquid Mutual Funds", arb_score, arb_tax, "FD-like stability with equity taxation (12.5% LTCG vs 30% slab)."))

        # 3. SGB / Gold
        sgb_score = 55
        if 48 <= h_months <= 96:
            sgb_score += 30
        elif h_months < 36:
            sgb_score -= 35
            warnings.append("Gold Volatility Risk: Gold price cycles fluctuate over short horizons (< 3 years).")
        scores.append(cls._build("sgb_gold", "Sovereign Gold Bonds / Gold", sgb_score, "High (100% Tax Free at Maturity)", "2.5% coupon + 100% tax-free gains; best for 5-8 year horizons."))

        # 4. G-Secs / Bonds
        bond_score = 65
        if 24 <= h_months <= 84:
            bond_score += 15
        scores.append(cls._build("bonds_gsec", "Government Securities (G-Secs)", bond_score, "Medium (Slab Taxed)", "Zero credit risk; locks in sovereign yield."))

        # 5. Equity Mutual Funds
        eq_score = 50
        if h_months >= 60:
            eq_score += 40
        elif h_months < 36:
            eq_score -= 45
            warnings.append(f"Equity Horizon Mismatch: Stated horizon of {h_months} months is too short for equity volatility. Negative return probability is elevated.")
        if risk == "aggressive":
            eq_score += 10
        scores.append(cls._build("equity_mf", "Equity Diversified / Index Funds", eq_score, "High (12.5% LTCG)", f"Wealth compounding beating inflation for 5+ year horizons."))

        # 6. Direct Stocks
        stk_score = 40
        if h_months >= 60 and risk == "aggressive":
            stk_score += 45
        elif h_months < 36:
            stk_score -= 40
            warnings.append(f"Direct Stock Risk: Holding individual stocks for {h_months} months exposes capital to company earnings shocks.")
        scores.append(cls._build("direct_stocks", "Direct Listed Equities (DCF Selected)", stk_score, "High (12.5% LTCG)", "High upside with fundamental margin of safety; requires 5+ years."))

        scores.sort(key=lambda x: x.suitability_score, reverse=True)
        return SuitabilityDiagnosis(
            goal_profile=profile, asset_scores=scores, top_recommended_asset=scores[0].display_name,
            critical_warnings=warnings, tax_optimization_tips=tax_tips
        )

    @classmethod
    def _build(cls, aid: str, name: str, score: int, tax_eff: str, reason: str) -> AssetSuitabilityScore:
        clamped = max(10, min(95, score))
        status = "High Fit" if clamped >= 70 else ("Moderate Fit" if clamped >= 45 else "Mismatch / Unsuitable")
        color = "#10b981" if clamped >= 70 else ("#f59e0b" if clamped >= 45 else "#ef4444")
        return AssetSuitabilityScore(
            asset_class=aid, display_name=name, suitability_score=clamped,
            fit_status=status, fit_color=color, primary_reason=reason, tax_efficiency_rating=tax_eff
        )


# -------------------- 6. TRADE-OFF COMPARATOR --------------------
@dataclass
class TradeOffRow:
    asset_name: str
    category_group: str
    nominal_return_pct: float
    post_tax_yield_pct: float
    net_maturity_value: float
    real_inflation_adjusted_yield_pct: float
    downside_risk_rating: str
    liquidity_rating: str
    tax_efficiency_grade: str
    what_you_gain: str
    what_you_sacrifice: str
    horizon_fit_note: str


class TradeOffComparator:
    @classmethod
    def compare_all(cls, amount: float = 200000.0, tenure_months: int = 36, tax_bracket_pct: float = 30.0, expected_inflation_pct: float = 6.0) -> List[TradeOffRow]:
        t_years = tenure_months / 12.0
        results: List[TradeOffRow] = []

        # 1. Bank FD
        fd_res = FixedDepositCalculator.calculate(FDParameters(principal=amount, tenure_months=tenure_months, interest_rate_pct=7.0 if t_years >= 3.0 else 6.8, tax_bracket_pct=tax_bracket_pct, expected_inflation_pct=expected_inflation_pct))
        results.append(TradeOffRow(
            asset_name="Bank Fixed Deposit (HDFC/SBI)", category_group="Fixed Income",
            nominal_return_pct=fd_res.effective_annual_yield_pct, post_tax_yield_pct=fd_res.net_post_tax_annual_yield_pct,
            net_maturity_value=fd_res.net_maturity_amount, real_inflation_adjusted_yield_pct=fd_res.real_inflation_adjusted_yield_pct,
            downside_risk_rating="Negligible (DICGC ₹5L cover)", liquidity_rating="Penalty Exit (0.5-1% cut)", tax_efficiency_grade="C (Slab Taxed)",
            what_you_gain="Guaranteed nominal capital preservation and quarterly compounding.",
            what_you_sacrifice="Purchasing power to inflation; heavy tax drag at 20-30% brackets.",
            horizon_fit_note="Excellent for 6 to 24 months; poor for > 5 years."
        ))

        # 2. Arbitrage Fund
        arb_res = MutualFundAnalyzer.analyze(MutualFundParameters(investment_mode="lumpsum", investment_amount=amount, tenure_years=t_years, category="arbitrage", expected_cagr_pct=7.2, direct_expense_ratio_pct=0.30, tax_bracket_pct=tax_bracket_pct, expected_inflation_pct=expected_inflation_pct))
        results.append(TradeOffRow(
            asset_name="Arbitrage Mutual Fund (Direct)", category_group="Cash Equivalent",
            nominal_return_pct=6.90, post_tax_yield_pct=arb_res.net_cagr_post_tax_pct,
            net_maturity_value=arb_res.net_post_tax_corpus, real_inflation_adjusted_yield_pct=arb_res.real_inflation_adjusted_cagr_pct,
            downside_risk_rating="Very Low (Hedging spreads)", liquidity_rating="Instant (T+1 days, no penalty)", tax_efficiency_grade="B (Equity Tax: 12.5% LTCG)",
            what_you_gain="FD-like low volatility with superior equity taxation (12.5% vs 30% slab).",
            what_you_sacrifice="Returns capped to money-market spreads; zero long-term growth.",
            horizon_fit_note="Ideal replacement for FDs for 6-36 months in high tax brackets."
        ))

        # 3. G-Sec 10-Yr Benchmark
        bond_res = BondEngine.analyze(BondParameters(face_value=amount, market_price=amount, coupon_rate_pct=7.10, tenure_years=t_years, coupon_frequency=2, credit_rating="SOVEREIGN", tax_bracket_pct=tax_bracket_pct, expected_inflation_pct=expected_inflation_pct))
        results.append(TradeOffRow(
            asset_name="Government Security (G-Sec 7.10% RBI)", category_group="Fixed Income",
            nominal_return_pct=bond_res.ytm_pct, post_tax_yield_pct=bond_res.net_post_tax_ytm_pct,
            net_maturity_value=amount * math.pow(1.0 + (bond_res.net_post_tax_ytm_pct / 100.0), t_years), real_inflation_adjusted_yield_pct=bond_res.real_inflation_adjusted_ytm_pct,
            downside_risk_rating="Low (Zero default, rate risk)", liquidity_rating="Moderate (NDS-OM secondary market)", tax_efficiency_grade="C (Coupons Slab Taxed)",
            what_you_gain="100% sovereign protection with zero credit risk, locking in yields.",
            what_you_sacrifice="Bond price fluctuates if interest rates rise (Duration risk).",
            horizon_fit_note="Best held to maturity (3 to 10 years)."
        ))

        # 4. SGB
        gold_res = GoldEngine.compare(GoldInvestmentParameters(investment_amount=amount, tenure_years=min(max(t_years, 1.0), 8.0), expected_gold_cagr_pct=8.5, tax_bracket_pct=tax_bracket_pct, sgb_coupon_rate_pct=2.50))
        results.append(TradeOffRow(
            asset_name="Sovereign Gold Bond (SGB)", category_group="Commodity / Gold",
            nominal_return_pct=11.0, post_tax_yield_pct=gold_res.sgb_net_cagr_pct,
            net_maturity_value=gold_res.sgb_total_payout, real_inflation_adjusted_yield_pct=round(((1.0 + gold_res.sgb_net_cagr_pct / 100.0) / (1.0 + expected_inflation_pct / 100.0) - 1.0) * 100.0, 2),
            downside_risk_rating="Moderate (Gold price cycle)", liquidity_rating="Locked (RBI window Y5 / Illiquid secondary)", tax_efficiency_grade="A (100% Tax Free Capital Gains)",
            what_you_gain="Gold price appreciation + 2.5% p.a. sovereign coupon + 100% tax-free gains.",
            what_you_sacrifice="Immediate liquidity (8-year tenure; RBI buyback begins at year 5).",
            horizon_fit_note="Unmatched wealth builder for 5 to 8-year horizons."
        ))

        # 5. Equity Flexi Cap Fund
        mf_res = MutualFundAnalyzer.analyze(MutualFundParameters(investment_mode="lumpsum", investment_amount=amount, tenure_years=t_years, category="flexi_cap", expected_cagr_pct=13.0, direct_expense_ratio_pct=0.60, tax_bracket_pct=tax_bracket_pct, expected_inflation_pct=expected_inflation_pct))
        results.append(TradeOffRow(
            asset_name="Equity Flexi Cap Mutual Fund (Direct)", category_group="Equity",
            nominal_return_pct=12.40, post_tax_yield_pct=mf_res.net_cagr_post_tax_pct,
            net_maturity_value=mf_res.net_post_tax_corpus, real_inflation_adjusted_yield_pct=mf_res.real_inflation_adjusted_cagr_pct,
            downside_risk_rating="High (Market cycle swings)", liquidity_rating="Instant (T+2 days, 1% exit load Y1)", tax_efficiency_grade="B (12.5% LTCG > ₹1.25L)",
            what_you_gain="Powerful long-term wealth compounding beating inflation comfortably.",
            what_you_sacrifice="Short-term capital certainty; subject to 20-40% market drawdowns.",
            horizon_fit_note="Requires minimum 5+ years to eliminate negative return probability."
        ))

        # 6. Direct Equity (DCF Screened)
        gross_stock_cagr = 14.50
        stock_corpus_gross = amount * math.pow(1.0 + (gross_stock_cagr / 100.0), t_years)
        stock_gains = max(0.0, stock_corpus_gross - amount)
        stock_tax = max(0.0, stock_gains - 125000.0) * 0.125 if t_years >= 1.0 else stock_gains * 0.20
        stock_net_corpus = stock_corpus_gross - stock_tax
        stock_net_cagr = (math.pow(stock_net_corpus / amount, 1.0 / t_years) - 1.0) * 100.0
        stock_real_cagr = ((1.0 + stock_net_cagr / 100.0) / (1.0 + expected_inflation_pct / 100.0) - 1.0) * 100.0

        results.append(TradeOffRow(
            asset_name="Direct Listed Equity (DCF Screened)", category_group="Equity",
            nominal_return_pct=gross_stock_cagr, post_tax_yield_pct=round(stock_net_cagr, 2),
            net_maturity_value=round(stock_net_corpus, 2), real_inflation_adjusted_yield_pct=round(stock_real_cagr, 2),
            downside_risk_rating="Very High (Company specific risk)", liquidity_rating="Instant (T+1 market settlement)", tax_efficiency_grade="B (12.5% LTCG)",
            what_you_gain="Maximum upside potential through business ownership and valuation mispricings.",
            what_you_sacrifice="Portfolio diversification; individual stock earnings vulnerability.",
            horizon_fit_note="Strictly for 5+ years and risk-tolerant investors who understand business metrics."
        ))

        return results

    @classmethod
    def to_dataframe(cls, trade_offs: List[TradeOffRow]) -> pd.DataFrame:
        data = []
        for row in trade_offs:
            data.append({
                "Asset / Product": row.asset_name,
                "Category": row.category_group,
                "Nominal Return (%)": f"{row.nominal_return_pct:.2f}%",
                "Post-Tax Net Yield (%)": f"{row.post_tax_yield_pct:.2f}%",
                "Net Maturity (₹)": f"₹{row.net_maturity_value:,.0f}",
                "Real Yield (vs 6% CPI)": f"{row.real_inflation_adjusted_yield_pct:+.2f}%",
                "Downside Risk": row.downside_risk_rating,
                "Liquidity": row.liquidity_rating,
                "Tax Efficiency": row.tax_efficiency_grade,
                "What You Gain": row.what_you_gain,
                "What You Sacrifice": row.what_you_sacrifice
            })
        return pd.DataFrame(data)


# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------------------------
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
    
    .block-container {
        padding-top: 3.8rem;
        padding-bottom: 2rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
        max-width: 1480px;
    }

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

    .allocator-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 18px 20px;
        margin-bottom: 16px;
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

    # Interactive Visualizations
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

    articles, catalyst_impact = fetch_news_and_catalysts(company_name, ticker, fair_target, wacc_pct)

    tv_link = f"https://in.tradingview.com/symbols/NSE-{ticker}/"
    gf_link = f"https://www.google.com/finance/quote/{ticker}:NSE"
    mc_link = f"https://www.moneycontrol.com/india/stockpricequote/"
    bse_link = f"https://www.bseindia.com/corporates/ann.html"

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

    st.markdown("##### 🕒 Recently Viewed Stocks")
    rec_cols = st.columns(len(st.session_state['recent_searches']) + 1)
    for idx, (rec_name, rec_url) in enumerate(st.session_state['recent_searches']):
        with rec_cols[idx]:
            if st.button(f"🔍 {rec_name}", key=f"recent_btn_{idx}", use_container_width=True):
                st.session_state['active_target_url'] = rec_url
                st.session_state['nav_mode'] = "🏢 Company DCF Model & Screener"
                st.rerun()

    st.markdown("---")

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
