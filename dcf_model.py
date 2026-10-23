"""
DCF Valuation & Sensitivity Engine
Computes WACC, Mid-Year Convention FCFF Discounting, Terminal Value (Gordon Growth & Exit Multiple),
Enterprise-to-Equity Value Bridge, and 2D Valuation Sensitivity Matrices with strict validation.
"""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd


class ValuationValidationError(Exception):
    """Raised when DCF parameters violate mathematical or economic constraints."""
    pass


class DCFValuationEngine:
    def __init__(self, raw_data: Dict[str, Any], forecast_results: Dict[str, Any]):
        self.raw_data = raw_data
        self.forecast_results = forecast_results
        self.kpis = raw_data.get('kpis', {})
        self.bs_df = raw_data.get('balance_sheet', pd.DataFrame())
        self.pl_df = raw_data.get('profit_loss', pd.DataFrame())
        self.assumptions = forecast_results['assumptions']
        self.fc_stmt = forecast_results['forecast_statements']

    def calculate_valuation(
        self,
        risk_free_rate: float = 0.070,     # India 10Y Benchmark (7.0%)
        equity_risk_premium: float = 0.055, # India ERP (5.5%)
        beta: float = 1.0,
        terminal_growth: float = 0.045,     # Long-term g (4.5%)
        exit_multiple: Optional[float] = None # EV/EBITDA multiple
    ) -> Dict[str, Any]:
        """Compute full DCF valuation and return summary metrics and sensitivity tables."""
        # Validate inputs
        if risk_free_rate < 0.01 or risk_free_rate > 0.20:
            raise ValuationValidationError(f"Risk-free rate ({risk_free_rate*100:.1f}%) is outside reasonable economic bounds (1% - 20%).")
        if equity_risk_premium < 0.01 or equity_risk_premium > 0.15:
            raise ValuationValidationError(f"Equity risk premium ({equity_risk_premium*100:.1f}%) is outside reasonable bounds (1% - 15%).")
        if beta <= 0.05 or beta > 4.0:
            raise ValuationValidationError(f"Beta ({beta:.2f}) must be positive and within reasonable market bounds (0.05 - 4.0).")

        cmp = float(self.kpis.get('Current Price', 0.0) or 0.0)
        market_cap = float(self.kpis.get('Market Cap', 0.0) or 0.0)

        # 1. Determine Diluted Shares Outstanding
        # Method A: Equity Capital / Face Value (exact share capital count)
        latest_col = self.forecast_results['historical_years'][-1]
        shares_from_equity = None
        if 'Equity Capital' in self.bs_df.index:
            eq_cap = float(self.bs_df.loc['Equity Capital', latest_col] or 0.0)
            fv = float(self.kpis.get('Face Value', 0.0) or 0.0)
            if fv > 0 and eq_cap > 0:
                shares_from_equity = eq_cap / fv

        # Method B: Market Cap / CMP
        shares_from_mcap = (market_cap / cmp) if (cmp > 0 and market_cap > 0) else None

        if shares_from_equity and shares_from_equity > 0:
            shares_cr = shares_from_equity
        elif shares_from_mcap and shares_from_mcap > 0:
            shares_cr = shares_from_mcap
        else:
            shares_cr = 1.0 # Fallback

        # 2. Extract Balance Sheet Claims (Cash, Investments, Debt)
        debt_val = 0.0
        if 'Borrowings' in self.bs_df.index:
            v = self.bs_df.loc['Borrowings', latest_col]
            debt_val = float(v) if v is not None and not np.isnan(float(v)) else 0.0

        cash_and_inv = 0.0
        if 'Investments' in self.bs_df.index:
            v = self.bs_df.loc['Investments', latest_col]
            cash_and_inv += float(v) if v is not None and not np.isnan(float(v)) else 0.0

        # Conservative estimate of operating cash / liquid assets from Other Assets
        other_assets_cash = 0.0
        if 'Other Assets' in self.bs_df.index:
            v = self.bs_df.loc['Other Assets', latest_col]
            other_assets_cash = float(v) * 0.15 if v is not None and not np.isnan(float(v)) else 0.0

        total_cash_and_inv = cash_and_inv + other_assets_cash

        # 3. Capital Structure & WACC Calculation
        # Capital Structure Weights
        effective_cap_base = market_cap + debt_val
        if effective_cap_base > 0:
            weight_equity = market_cap / effective_cap_base
            weight_debt = debt_val / effective_cap_base
        else:
            weight_equity = 0.85
            weight_debt = 0.15

        cost_of_equity = risk_free_rate + beta * equity_risk_premium
        tax_rate = self.assumptions['effective_tax_rate_pct'] / 100.0
        cost_of_debt_pre_tax = self.assumptions['cost_of_debt_pct'] / 100.0
        cost_of_debt_post_tax = cost_of_debt_pre_tax * (1.0 - tax_rate)

        wacc = (weight_equity * cost_of_equity) + (weight_debt * cost_of_debt_post_tax)

        # Strict validation: Terminal Growth vs WACC
        if terminal_growth >= wacc:
            raise ValuationValidationError(
                f"Terminal growth rate ({terminal_growth*100:.2f}%) must be strictly less than WACC ({wacc*100:.2f}%). "
                f"A perpetual growth rate equal to or exceeding the discount rate implies an infinite firm value."
            )

        # 4. Explicit Forecast Period Discounting (Mid-Year Convention)
        fcff_list = self.fc_stmt['fcff']
        n_years = len(fcff_list)
        discount_factors = []
        pv_fcff_list = []
        for t in range(1, n_years + 1):
            df = 1.0 / ((1.0 + wacc) ** (t - 0.5))
            discount_factors.append(df)
            pv_fcff_list.append(fcff_list[t - 1] * df)

        cumulative_pv_fcff = float(np.sum(pv_fcff_list))

        # 5. Terminal Value - Perpetual Growth Method (Gordon Growth)
        final_fcff = fcff_list[-1]
        terminal_fcff = final_fcff * (1.0 + terminal_growth)
        tv_gordon = terminal_fcff / (wacc - terminal_growth)
        pv_tv_gordon = tv_gordon / ((1.0 + wacc) ** n_years)

        # 6. Terminal Value - Exit Multiple Method
        final_ebitda = self.fc_stmt['ebitda'][-1]
        if exit_multiple is None:
            pe = float(self.kpis.get('Stock P/E', 15.0) or 15.0)
            exit_multiple = float(np.clip(pe * 0.65, 5.0, 35.0))
            
        tv_multiple = final_ebitda * exit_multiple
        pv_tv_multiple = tv_multiple / ((1.0 + wacc) ** n_years)

        # 7. Enterprise Value & Equity Value Bridge
        # Gordon Growth
        ev_gordon = cumulative_pv_fcff + pv_tv_gordon
        equity_val_gordon = ev_gordon + total_cash_and_inv - debt_val
        target_price_gordon = equity_val_gordon / shares_cr if shares_cr > 0 else cmp
        upside_gordon = ((target_price_gordon - cmp) / cmp) * 100.0 if cmp > 0 else 0.0

        # Exit Multiple
        ev_multiple = cumulative_pv_fcff + pv_tv_multiple
        equity_val_multiple = ev_multiple + total_cash_and_inv - debt_val
        target_price_multiple = equity_val_multiple / shares_cr if shares_cr > 0 else cmp
        upside_multiple = ((target_price_multiple - cmp) / cmp) * 100.0 if cmp > 0 else 0.0

        fair_price_avg = (target_price_gordon + target_price_multiple) / 2.0
        fair_upside_avg = ((fair_price_avg - cmp) / cmp) * 100.0 if cmp > 0 else 0.0

        # 8. Check Terminal Value Reliance
        tv_reliance_pct = (pv_tv_gordon / ev_gordon * 100.0) if ev_gordon > 0 else 0.0
        high_tv_warning = tv_reliance_pct > 75.0

        # 9. Sensitivity Matrix: WACC vs Terminal Growth
        wacc_range = [round(wacc + delta, 4) for delta in [-0.02, -0.01, 0.0, 0.01, 0.02]]
        g_range = [round(terminal_growth + delta, 4) for delta in [-0.015, -0.005, 0.0, 0.005, 0.015]]
        
        sensitivity_g_table = []
        for g_val in g_range:
            row_prices = []
            for w_val in wacc_range:
                if w_val <= g_val + 0.005:
                    row_prices.append(None) # Mathematically invalid
                else:
                    pv_fcf = sum(fcff_list[i] / ((1.0 + w_val) ** (i + 0.5)) for i in range(n_years))
                    tv = (final_fcff * (1.0 + g_val)) / (w_val - g_val)
                    pv_tv = tv / ((1.0 + w_val) ** n_years)
                    eq_v = pv_fcf + pv_tv + total_cash_and_inv - debt_val
                    p = eq_v / shares_cr if shares_cr > 0 else cmp
                    row_prices.append(round(p, 1))
            sensitivity_g_table.append(row_prices)

        # Sensitivity Matrix: WACC vs Exit Multiple
        mult_range = [round(exit_multiple + delta, 1) for delta in [-3.0, -1.5, 0.0, 1.5, 3.0]]
        sensitivity_mult_table = []
        for m_val in mult_range:
            row_prices = []
            for w_val in wacc_range:
                pv_fcf = sum(fcff_list[i] / ((1.0 + w_val) ** (i + 0.5)) for i in range(n_years))
                tv = final_ebitda * m_val
                pv_tv = tv / ((1.0 + w_val) ** n_years)
                eq_v = pv_fcf + pv_tv + total_cash_and_inv - debt_val
                p = eq_v / shares_cr if shares_cr > 0 else cmp
                row_prices.append(round(p, 1))
            sensitivity_mult_table.append(row_prices)

        return {
            'wacc_parameters': {
                'risk_free_rate_pct': round(risk_free_rate * 100, 2),
                'equity_risk_premium_pct': round(equity_risk_premium * 100, 2),
                'beta': round(beta, 2),
                'cost_of_equity_pct': round(cost_of_equity * 100, 2),
                'cost_of_debt_pre_tax_pct': round(cost_of_debt_pre_tax * 100, 2),
                'cost_of_debt_post_tax_pct': round(cost_of_debt_post_tax * 100, 2),
                'weight_equity_pct': round(weight_equity * 100, 2),
                'weight_debt_pct': round(weight_debt * 100, 2),
                'wacc_pct': round(wacc * 100, 2),
                'wacc_raw': wacc,
            },
            'valuation_bridge': {
                'current_market_price': round(cmp, 2),
                'market_capitalization_cr': round(market_cap, 2),
                'shares_outstanding_cr': round(shares_cr, 2),
                'total_debt_cr': round(debt_val, 2),
                'cash_and_investments_cr': round(total_cash_and_inv, 2),
                'cumulative_pv_fcff_cr': round(cumulative_pv_fcff, 2),
                'discount_factors': [round(x, 4) for x in discount_factors],
                'pv_fcff_list_cr': [round(x, 2) for x in pv_fcff_list],
            },
            'gordon_growth_method': {
                'terminal_growth_pct': round(terminal_growth * 100, 2),
                'terminal_value_cr': round(tv_gordon, 2),
                'pv_terminal_value_cr': round(pv_tv_gordon, 2),
                'enterprise_value_cr': round(ev_gordon, 2),
                'implied_equity_value_cr': round(equity_val_gordon, 2),
                'target_price_per_share': round(target_price_gordon, 2),
                'upside_pct': round(upside_gordon, 2),
                'tv_percent_of_ev': round(tv_reliance_pct, 1),
                'high_tv_warning': high_tv_warning,
            },
            'exit_multiple_method': {
                'exit_multiple_ev_ebitda': round(exit_multiple, 1),
                'terminal_value_cr': round(tv_multiple, 2),
                'pv_terminal_value_cr': round(pv_tv_multiple, 2),
                'enterprise_value_cr': round(ev_multiple, 2),
                'implied_equity_value_cr': round(equity_val_multiple, 2),
                'target_price_per_share': round(target_price_multiple, 2),
                'upside_pct': round(upside_multiple, 2),
            },
            'fair_value_summary': {
                'blended_target_price': round(fair_price_avg, 2),
                'blended_upside_pct': round(fair_upside_avg, 2),
            },
            'sensitivity_gordon': {
                'wacc_columns': [f"{round(w*100, 1)}%" for w in wacc_range],
                'growth_rows': [f"{round(g*100, 1)}%" for g in g_range],
                'matrix': sensitivity_g_table,
            },
            'sensitivity_multiple': {
                'wacc_columns': [f"{round(w*100, 1)}%" for w in wacc_range],
                'multiple_rows': [f"{m}x" for m in mult_range],
                'matrix': sensitivity_mult_table,
            }
        }
