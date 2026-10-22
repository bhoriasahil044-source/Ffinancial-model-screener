"""
DCF Valuation & Sensitivity Engine
Computes WACC, FCFF Discounting, Terminal Value (Gordon Growth & Exit Multiple),
Enterprise-to-Equity Value Bridge, Implied Share Price, and 2D Sensitivity Tables.
"""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd


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
        terminal_growth: float = 0.050,     # Long-term g (5.0%)
        exit_multiple: Optional[float] = None # EV/EBITDA multiple
    ) -> Dict[str, Any]:
        """Compute full DCF valuation and return summary metrics and sensitivity tables."""
        cmp = float(self.kpis.get('Current Price', 100.0) or 100.0)
        market_cap = float(self.kpis.get('Market Cap', 10000.0) or 10000.0)
        
        # Estimate shares outstanding (Market Cap in Cr / CMP)
        shares_cr = market_cap / cmp if cmp > 0 else 1.0
        
        # Latest Balance Sheet figures
        latest_col = self.forecast_results['historical_years'][-1]
        
        debt_val = 0.0
        if 'Borrowings' in self.bs_df.index:
            v = self.bs_df.loc['Borrowings', latest_col]
            debt_val = float(v) if v is not None and not np.isnan(float(v)) else 0.0
            
        cash_val = 0.0
        if 'Investments' in self.bs_df.index:
            v = self.bs_df.loc['Investments', latest_col]
            cash_val += float(v) if v is not None and not np.isnan(float(v)) else 0.0
        if 'Other Assets' in self.bs_df.index:
            # Conservative estimate: ~15% of other assets is cash/bank balances
            v = self.bs_df.loc['Other Assets', latest_col]
            cash_val += float(v) * 0.15 if v is not None and not np.isnan(float(v)) else 0.0

        # Capital Structure & WACC
        total_ev_est = market_cap + debt_val - cash_val
        weight_equity = market_cap / (market_cap + debt_val) if (market_cap + debt_val) > 0 else 0.85
        weight_debt = 1.0 - weight_equity

        cost_of_equity = risk_free_rate + beta * equity_risk_premium
        tax_rate = self.assumptions['effective_tax_rate_pct'] / 100.0
        cost_of_debt_pre_tax = self.assumptions['cost_of_debt_pct'] / 100.0
        cost_of_debt_post_tax = cost_of_debt_pre_tax * (1.0 - tax_rate)

        wacc = (weight_equity * cost_of_equity) + (weight_debt * cost_of_debt_post_tax)
        wacc = float(np.clip(wacc, 0.075, 0.18))

        # Explicit Forecast Period Discounting (Mid-Year Convention)
        fcff_list = self.fc_stmt['fcff']
        n_years = len(fcff_list)
        discount_factors = []
        pv_fcff_list = []
        for t in range(1, n_years + 1):
            df = 1.0 / ((1.0 + wacc) ** (t - 0.5))
            discount_factors.append(df)
            pv_fcff_list.append(fcff_list[t - 1] * df)

        cumulative_pv_fcff = float(np.sum(pv_fcff_list))

        # Terminal Value - Perpetual Growth Method
        final_fcff = fcff_list[-1]
        terminal_growth = min(terminal_growth, wacc - 0.02) # Prevent g >= WACC singularity
        terminal_fcff = final_fcff * (1.0 + terminal_growth)
        tv_gordon = terminal_fcff / (wacc - terminal_growth)
        pv_tv_gordon = tv_gordon / ((1.0 + wacc) ** n_years)

        # Terminal Value - Exit Multiple Method
        final_ebitda = self.fc_stmt['ebitda'][-1]
        if exit_multiple is None:
            # Estimate reasonable exit multiple based on stock P/E and margin
            pe = float(self.kpis.get('Stock P/E', 15.0) or 15.0)
            exit_multiple = float(np.clip(pe * 0.65, 5.0, 30.0))
            
        tv_multiple = final_ebitda * exit_multiple
        pv_tv_multiple = tv_multiple / ((1.0 + wacc) ** n_years)

        # Enterprise Value & Equity Value (Gordon Growth)
        ev_gordon = cumulative_pv_fcff + pv_tv_gordon
        equity_val_gordon = ev_gordon + cash_val - debt_val
        target_price_gordon = equity_val_gordon / shares_cr if shares_cr > 0 else cmp
        upside_gordon = ((target_price_gordon - cmp) / cmp) * 100.0

        # Enterprise Value & Equity Value (Exit Multiple)
        ev_multiple = cumulative_pv_fcff + pv_tv_multiple
        equity_val_multiple = ev_multiple + cash_val - debt_val
        target_price_multiple = equity_val_multiple / shares_cr if shares_cr > 0 else cmp
        upside_multiple = ((target_price_multiple - cmp) / cmp) * 100.0

        # Average Fair Value
        fair_price_avg = (target_price_gordon + target_price_multiple) / 2.0
        fair_upside_avg = ((fair_price_avg - cmp) / cmp) * 100.0

        # Sensitivity Matrix: WACC vs Terminal Growth
        wacc_range = [round(wacc + delta, 3) for delta in [-0.02, -0.01, 0.0, 0.01, 0.02]]
        g_range = [round(terminal_growth + delta, 3) for delta in [-0.015, -0.005, 0.0, 0.005, 0.015]]
        
        sensitivity_g_table = []
        for g_val in g_range:
            row_prices = []
            for w_val in wacc_range:
                if w_val <= g_val + 0.01:
                    row_prices.append(None)
                else:
                    # Recalculate PV FCFF
                    pv_fcf = sum(fcff_list[i] / ((1.0 + w_val) ** (i + 0.5)) for i in range(n_years))
                    tv = (final_fcff * (1.0 + g_val)) / (w_val - g_val)
                    pv_tv = tv / ((1.0 + w_val) ** n_years)
                    eq_v = pv_fcf + pv_tv + cash_val - debt_val
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
                eq_v = pv_fcf + pv_tv + cash_val - debt_val
                p = eq_v / shares_cr if shares_cr > 0 else cmp
                row_prices.append(round(p, 1))
            sensitivity_mult_table.append(row_prices)

        return {
            'wacc_parameters': {
                'risk_free_rate_pct': round(risk_free_rate * 100, 2),
                'equity_risk_premium_pct': round(equity_risk_premium * 100, 2),
                'beta': round(beta, 2),
                'cost_of_equity_pct': round(cost_of_equity * 100, 2),
                'cost_of_debt_post_tax_pct': round(cost_of_debt_post_tax * 100, 2),
                'weight_equity_pct': round(weight_equity * 100, 2),
                'weight_debt_pct': round(weight_debt * 100, 2),
                'wacc_pct': round(wacc * 100, 2),
            },
            'valuation_bridge': {
                'current_market_price': round(cmp, 2),
                'market_capitalization_cr': round(market_cap, 2),
                'shares_outstanding_cr': round(shares_cr, 2),
                'total_debt_cr': round(debt_val, 2),
                'cash_and_investments_cr': round(cash_val, 2),
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
