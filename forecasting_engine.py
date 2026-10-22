"""
Econometric & Financial Statement Forecasting Engine
Implements Holt's Linear Damped Exponential Smoothing, Auto-Regressive (AR),
Log-Linear Trend, and Rolling Fundamental CAGR models with Walk-Forward Backtesting.
"""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd
from scipy.optimize import minimize


class ForecastingModels:
    @staticmethod
    def holt_damped(series: np.ndarray, steps: int = 5) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Holt's Linear Exponential Smoothing with Damped Trend.
        Minimizes SSE using L-BFGS-B optimization.
        """
        n = len(series)
        if n < 3:
            # Fallback to linear extrapolation if series is too short
            trend = (series[-1] - series[0]) / max(n - 1, 1)
            fc = [series[-1] + trend * (i + 1) for i in range(steps)]
            return np.array(fc), {'alpha': 0.5, 'beta': 0.2, 'phi': 0.9}

        def loss(params):
            alpha, beta, phi = params
            l = series[0]
            b = series[1] - series[0]
            sse = 0.0
            for t in range(1, n):
                y_hat = l + phi * b
                err = series[t] - y_hat
                sse += err * err
                l_new = alpha * series[t] + (1 - alpha) * (l + phi * b)
                b_new = beta * (l_new - l) + (1 - beta) * phi * b
                l, b = l_new, b_new
            return sse

        res = minimize(
            loss,
            x0=[0.5, 0.2, 0.9],
            bounds=[(0.01, 0.99), (0.01, 0.8), (0.80, 0.98)],
            method='L-BFGS-B'
        )
        alpha, beta, phi = res.x

        # Re-run filter to get final level and trend
        l = series[0]
        b = series[1] - series[0]
        for t in range(1, n):
            l_new = alpha * series[t] + (1 - alpha) * (l + phi * b)
            b_new = beta * (l_new - l) + (1 - beta) * phi * b
            l, b = l_new, b_new

        forecasts = []
        for h in range(1, steps + 1):
            # Sum of geometric damping factors: sum(phi^i for i in 1..h)
            damp_sum = sum(phi ** i for i in range(1, h + 1))
            forecasts.append(l + damp_sum * b)

        return np.maximum(0, np.array(forecasts)), {'alpha': float(alpha), 'beta': float(beta), 'phi': float(phi)}

    @staticmethod
    def ar_model(series: np.ndarray, steps: int = 5) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Autoregressive AR(1) model with drift: Y_t = c + rho * Y_{t-1}.
        """
        n = len(series)
        if n < 3:
            return ForecastingModels.holt_damped(series, steps)

        y = series[1:]
        x = series[:-1]
        x_mat = np.column_stack([np.ones_like(x), x])
        
        try:
            beta, _, _, _ = np.linalg.lstsq(x_mat, y, rcond=None)
            c, rho = beta[0], beta[1]
            # Ensure stability
            rho = np.clip(rho, -0.95, 0.98)
        except Exception:
            c = np.mean(series) * 0.1
            rho = 0.9

        forecasts = []
        curr = series[-1]
        for _ in range(steps):
            nxt = c + rho * curr
            forecasts.append(nxt)
            curr = nxt

        return np.maximum(0, np.array(forecasts)), {'constant': float(c), 'rho': float(rho)}

    @staticmethod
    def log_linear_trend(series: np.ndarray, steps: int = 5) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Log-linear exponential trend: ln(Y) = a + b * t.
        """
        n = len(series)
        # Shift series if non-positive
        min_val = np.min(series)
        shift = abs(min_val) + 1.0 if min_val <= 0 else 0.0
        log_y = np.log(series + shift)
        t = np.arange(n)
        
        A = np.column_stack([np.ones(n), t])
        coef, _, _, _ = np.linalg.lstsq(A, log_y, rcond=None)
        a, b = coef[0], coef[1]
        
        # Cap excessive annual compound growth (e.g. max 35%)
        b = np.clip(b, -0.20, 0.35)

        future_t = np.arange(n, n + steps)
        pred_log = a + b * future_t
        pred = np.exp(pred_log) - shift

        return np.maximum(0, pred), {'intercept': float(a), 'cagr_slope': float(b)}

    @staticmethod
    def rolling_cagr_mean_reversion(series: np.ndarray, steps: int = 5, gdp_anchor: float = 0.10) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Fundamental multi-year rolling CAGR that gradually mean-reverts to long-term GDP growth.
        """
        n = len(series)
        if n >= 5 and series[-5] > 0:
            cagr_5y = (series[-1] / series[-5]) ** (1 / 4) - 1.0
        else:
            cagr_5y = gdp_anchor

        if n >= 3 and series[-3] > 0:
            cagr_3y = (series[-1] / series[-3]) ** (1 / 2) - 1.0
        else:
            cagr_3y = cagr_5y

        # Blend recent 3Y and 5Y CAGR
        initial_growth = np.clip(0.6 * cagr_3y + 0.4 * cagr_5y, -0.15, 0.30)

        forecasts = []
        curr = series[-1]
        growth = initial_growth
        for h in range(1, steps + 1):
            # 20% annual reversion towards economic anchor
            growth = growth * 0.80 + gdp_anchor * 0.20
            curr = curr * (1.0 + growth)
            forecasts.append(curr)

        return np.maximum(0, np.array(forecasts)), {'initial_growth': float(initial_growth), 'anchor_gdp': float(gdp_anchor)}


class BacktestingEngine:
    """Walk-forward backtester to evaluate model accuracy on recent historical data."""

    @staticmethod
    def evaluate_models(series: np.ndarray, test_horizon: int = 3) -> Dict[str, Any]:
        n = len(series)
        if n < test_horizon + 3:
            test_horizon = max(1, n - 3)

        train = series[:-test_horizon]
        test = series[-test_horizon:]

        models = {
            'Holt-Winters Damped': ForecastingModels.holt_damped,
            'Auto-Regressive (AR)': ForecastingModels.ar_model,
            'Log-Linear Trend': ForecastingModels.log_linear_trend,
            'Fundamental CAGR Mean-Reversion': ForecastingModels.rolling_cagr_mean_reversion,
        }

        results = {}
        for name, fn in models.items():
            try:
                pred, params = fn(train, steps=test_horizon)
                # Compute metrics
                abs_pct_err = np.abs((test - pred) / np.where(test == 0, 1e-6, test)) * 100.0
                mape = float(np.mean(abs_pct_err))
                rmse = float(np.sqrt(np.mean((test - pred) ** 2)))
                mae = float(np.mean(np.abs(test - pred)))
                results[name] = {
                    'mape': round(mape, 2),
                    'rmse': round(rmse, 2),
                    'mae': round(mae, 2),
                    'predictions': pred.tolist(),
                    'params': params,
                }
            except Exception as e:
                results[name] = {
                    'mape': 999.0,
                    'rmse': 999.0,
                    'mae': 999.0,
                    'error': str(e),
                }

        # Select best model based on lowest MAPE
        sorted_models = sorted(results.items(), key=lambda x: x[1]['mape'])
        best_name = sorted_models[0][0]

        return {
            'test_horizon': test_horizon,
            'actual_test_values': test.tolist(),
            'best_model': best_name,
            'model_evaluations': results,
        }


class FinancialStatementForecaster:
    """Orchestrates historical data, selects optimal models, and produces integrated 5-year forecasts."""

    def __init__(self, raw_data: Dict[str, Any]):
        self.raw_data = raw_data
        self.pl_df = raw_data['profit_loss']
        self.bs_df = raw_data['balance_sheet']
        self.cf_df = raw_data['cash_flow']
        self.ratios_df = raw_data['ratios']
        self.kpis = raw_data['kpis']

        # Determine aligned closed historical fiscal years (excluding TTM)
        pl_cols = [c for c in self.pl_df.columns if c != 'TTM']
        bs_cols = list(self.bs_df.columns)
        self.hist_years = [c for c in pl_cols if c in bs_cols]
        if not self.hist_years:
            self.hist_years = pl_cols

    def run_forecast(self, forecast_years: int = 5) -> Dict[str, Any]:
        """Generate 5-year dynamic forecast with backtesting validation and scenarios."""
        # 1. Historical Sales Series
        sales_row = self._get_row(self.pl_df, ['Sales', 'Revenue'])
        sales_hist = np.array([float(sales_row[y]) if y in sales_row and sales_row[y] is not None else 0.0 for y in self.hist_years])

        # 2. Backtest and Select Best Top-Line Model
        backtest_results = BacktestingEngine.evaluate_models(sales_hist, test_horizon=min(3, max(1, len(sales_hist) - 3)))
        best_model_name = backtest_results['best_model']

        # Fit best model on entire history
        model_fns = {
            'Holt-Winters Damped': ForecastingModels.holt_damped,
            'Auto-Regressive (AR)': ForecastingModels.ar_model,
            'Log-Linear Trend': ForecastingModels.log_linear_trend,
            'Fundamental CAGR Mean-Reversion': ForecastingModels.rolling_cagr_mean_reversion,
        }
        chosen_fn = model_fns.get(best_model_name, ForecastingModels.holt_damped)
        sales_forecast_base, model_params = chosen_fn(sales_hist, steps=forecast_years)

        # Generate future year labels (e.g. Mar 2027 to Mar 2031)
        last_yr_str = self.hist_years[-1]
        try:
            last_yr_num = int(''.join(filter(str.isdigit, last_yr_str)))
        except ValueError:
            last_yr_num = 2026
        future_years = [f"FY{last_yr_num + i + 1}E" for i in range(forecast_years)]

        # 3. Margins & Cost Structure
        opm_row = self._get_row(self.pl_df, ['OPM %', 'Operating Margin'])
        hist_opm = np.array([float(opm_row[y]) if y in opm_row and opm_row[y] is not None else 15.0 for y in self.hist_years])
        
        # Clean OPM (if stored as 0.15 vs 15)
        if np.nanmedian(hist_opm) < 1.0:
            hist_opm = hist_opm * 100.0

        median_opm = float(np.nanmedian(hist_opm))
        last_opm = float(hist_opm[-1])
        std_opm = float(np.nanstd(hist_opm)) if len(hist_opm) > 1 else 2.0

        # Mean reversion for base OPM % (30% annual convergence towards median)
        base_opm_forecast = []
        curr_opm = last_opm
        for _ in range(forecast_years):
            curr_opm = curr_opm * 0.70 + median_opm * 0.30
            base_opm_forecast.append(curr_opm)
        base_opm_forecast = np.array(base_opm_forecast)

        # 4. Depreciation & Net Block Schedule
        dep_row = self._get_row(self.pl_df, ['Depreciation'])
        fa_row = self._get_row(self.bs_df, ['Fixed Assets'])
        hist_fa = np.array([float(fa_row[y]) if y in fa_row and fa_row[y] is not None else 1000.0 for y in self.hist_years])
        hist_dep = np.array([float(dep_row[y]) if y in dep_row and dep_row[y] is not None else 50.0 for y in self.hist_years])
        dep_rates = hist_dep / np.where(hist_fa == 0, 1.0, hist_fa)
        dep_rate_median = float(np.clip(np.nanmedian(dep_rates), 0.03, 0.15))

        # Capex as % of Sales
        cf_inv_row = self._get_row(self.cf_df, ['Cash from Investing Activity'])
        hist_capex = np.abs(np.array([float(cf_inv_row[y]) if y in cf_inv_row and cf_inv_row[y] is not None else 0.0 for y in self.hist_years]))
        capex_to_sales = hist_capex / np.where(sales_hist == 0, 1.0, sales_hist)
        capex_ratio_median = float(np.clip(np.nanmedian(capex_to_sales), 0.03, 0.18))

        # 5. Interest Rate & Borrowings
        int_row = self._get_row(self.pl_df, ['Interest'])
        debt_row = self._get_row(self.bs_df, ['Borrowings'])
        hist_debt = np.array([float(debt_row[y]) if y in debt_row and debt_row[y] is not None else 0.0 for y in self.hist_years])
        hist_int = np.array([float(int_row[y]) if y in int_row and int_row[y] is not None else 0.0 for y in self.hist_years])
        cost_of_debt_hist = hist_int / np.where(hist_debt <= 0, 1.0, hist_debt)
        cost_of_debt_median = float(np.clip(np.nanmedian(cost_of_debt_hist), 0.06, 0.12))

        # 6. Tax Rate
        tax_row = self._get_row(self.pl_df, ['Tax %'])
        hist_tax = np.array([float(tax_row[y]) if y in tax_row and tax_row[y] is not None else 25.0 for y in self.hist_years])
        if np.nanmedian(hist_tax) < 1.0:
            hist_tax = hist_tax * 100.0
        effective_tax_rate = float(np.clip(np.nanmedian(hist_tax) / 100.0, 0.20, 0.28))

        # 7. Working Capital Days
        debtor_days = float(self._get_ratio_median('Debtor Days', 30.0))
        inventory_days = float(self._get_ratio_median('Inventory Days', 60.0))
        payable_days = float(self._get_ratio_median('Days Payable', 60.0))
        wc_days = debtor_days + inventory_days - payable_days

        # 8. Scenarios (Base, Bull, Bear)
        sales_std = float(np.std(sales_hist) / np.mean(sales_hist)) if len(sales_hist) > 1 else 0.10
        bull_sales = sales_forecast_base * (1.0 + sales_std * 0.5)
        bear_sales = sales_forecast_base * (1.0 - sales_std * 0.5)

        bull_opm = base_opm_forecast + min(std_opm, 2.5)
        bear_opm = np.maximum(2.0, base_opm_forecast - min(std_opm, 2.5))

        # 9. Build 5-Year Financial Statements Projections
        forecast_data = self._generate_full_statements(
            sales_forecast=sales_forecast_base,
            opm_forecast=base_opm_forecast,
            dep_rate=dep_rate_median,
            capex_ratio=capex_ratio_median,
            cost_of_debt=cost_of_debt_median,
            tax_rate=effective_tax_rate,
            wc_days=wc_days,
            hist_fa_last=hist_fa[-1],
            hist_debt_last=hist_debt[-1],
            future_years=future_years
        )

        return {
            'historical_years': self.hist_years,
            'future_years': future_years,
            'backtest': backtest_results,
            'assumptions': {
                'best_sales_model': best_model_name,
                'model_parameters': model_params,
                'median_opm_pct': round(median_opm, 2),
                'depreciation_rate_pct': round(dep_rate_median * 100, 2),
                'capex_to_sales_pct': round(capex_ratio_median * 100, 2),
                'cost_of_debt_pct': round(cost_of_debt_median * 100, 2),
                'effective_tax_rate_pct': round(effective_tax_rate * 100, 2),
                'debtor_days': round(debtor_days, 1),
                'inventory_days': round(inventory_days, 1),
                'payable_days': round(payable_days, 1),
                'working_capital_days': round(wc_days, 1),
            },
            'scenarios': {
                'base': {'sales': sales_forecast_base.tolist(), 'opm': base_opm_forecast.tolist()},
                'bull': {'sales': bull_sales.tolist(), 'opm': bull_opm.tolist()},
                'bear': {'sales': bear_sales.tolist(), 'opm': bear_opm.tolist()},
            },
            'forecast_statements': forecast_data,
        }

    def _generate_full_statements(
        self,
        sales_forecast: np.ndarray,
        opm_forecast: np.ndarray,
        dep_rate: float,
        capex_ratio: float,
        cost_of_debt: float,
        tax_rate: float,
        wc_days: float,
        hist_fa_last: float,
        hist_debt_last: float,
        future_years: List[str]
    ) -> Dict[str, Any]:
        """Generate integrated 5-year P&L, Balance Sheet, and Free Cash Flows."""
        n_years = len(future_years)
        
        # P&L line items
        sales = sales_forecast
        ebitda = sales * (opm_forecast / 100.0)
        expenses = sales - ebitda
        
        # PP&E & Depreciation Schedule
        fixed_assets = []
        deprecations = []
        capex = []
        curr_fa = hist_fa_last
        for i in range(n_years):
            cpx = sales[i] * capex_ratio
            dep = curr_fa * dep_rate
            curr_fa = curr_fa + cpx - dep
            fixed_assets.append(curr_fa)
            deprecations.append(dep)
            capex.append(cpx)
        
        fixed_assets = np.array(fixed_assets)
        deprecations = np.array(deprecations)
        capex = np.array(capex)
        
        # EBIT
        ebit = ebitda - deprecations
        
        # Debt & Interest (assume gradual 5% annual debt reduction)
        debt = []
        interest = []
        curr_debt = hist_debt_last
        for i in range(n_years):
            curr_debt = curr_debt * 0.95
            debt.append(curr_debt)
            interest.append(curr_debt * cost_of_debt)
        debt = np.array(debt)
        interest = np.array(interest)
        
        # Other income (historical median or modest yield)
        other_inc_row = self._get_row(self.pl_df, ['Other Income'])
        hist_other_inc = [float(other_inc_row[y]) if y in other_inc_row and other_inc_row[y] is not None else 0.0 for y in self.hist_years]
        median_other_inc = float(np.nanmedian(hist_other_inc)) if hist_other_inc else 0.0
        other_income = np.full(n_years, median_other_inc)
        
        # PBT, Tax, PAT
        pbt = np.maximum(0, ebit + other_income - interest)
        tax = pbt * tax_rate
        pat = pbt - tax
        
        # Dividend Payout
        payout_row = self._get_row(self.pl_df, ['Dividend Payout %'])
        hist_payout = [float(payout_row[y]) if y in payout_row and payout_row[y] is not None else 20.0 for y in self.hist_years]
        payout_ratio = float(np.clip(np.nanmedian(hist_payout) / 100.0, 0.10, 0.50))
        dividends = pat * payout_ratio
        retained_earnings_add = pat - dividends
        
        # Working Capital Schedule (NWC ~ Sales * wc_days / 365)
        nwc = sales * (wc_days / 365.0)
        # Delta NWC
        sales_hist_last = float(self._get_row(self.pl_df, ['Sales', 'Revenue'])[self.hist_years[-1]])
        prior_nwc = sales_hist_last * (wc_days / 365.0)
        delta_nwc = []
        curr_prior_nwc = prior_nwc
        for i in range(n_years):
            d_nwc = nwc[i] - curr_prior_nwc
            delta_nwc.append(d_nwc)
            curr_prior_nwc = nwc[i]
        delta_nwc = np.array(delta_nwc)
        
        # Unlevered Free Cash Flow to Firm (FCFF)
        # FCFF = EBIT * (1 - t) + D&A - Capex - Delta NWC
        nopat = ebit * (1.0 - tax_rate)
        fcff = nopat + deprecations - capex - delta_nwc
        
        return {
            'years': future_years,
            'sales': sales.tolist(),
            'expenses': expenses.tolist(),
            'ebitda': ebitda.tolist(),
            'opm_pct': opm_forecast.tolist(),
            'depreciation': deprecations.tolist(),
            'ebit': ebit.tolist(),
            'interest': interest.tolist(),
            'other_income': other_income.tolist(),
            'pbt': pbt.tolist(),
            'tax': tax.tolist(),
            'pat': pat.tolist(),
            'dividends': dividends.tolist(),
            'retained_earnings_add': retained_earnings_add.tolist(),
            'fixed_assets': fixed_assets.tolist(),
            'capex': capex.tolist(),
            'debt': debt.tolist(),
            'nwc': nwc.tolist(),
            'delta_nwc': delta_nwc.tolist(),
            'nopat': nopat.tolist(),
            'fcff': fcff.tolist(),
        }

    def _get_row(self, df: pd.DataFrame, aliases: List[str]) -> pd.Series:
        for alias in aliases:
            if alias in df.index:
                return df.loc[alias]
            for idx in df.index:
                if alias.lower() in idx.lower():
                    return df.loc[idx]
        return pd.Series(dtype=float)

    def _get_ratio_median(self, ratio_name: str, default_val: float) -> float:
        if ratio_name in self.ratios_df.index:
            row = self.ratios_df.loc[ratio_name]
            vals = [float(v) for v in row if v is not None and not np.isnan(float(v))]
            if vals:
                return float(np.median(vals))
        return default_val
