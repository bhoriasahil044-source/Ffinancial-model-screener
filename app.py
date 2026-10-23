"""
Universal Screener.in Financial Prediction & Valuation Web Application
Built with Streamlit, Plotly, and OpenPyXL.
"""

import os
import io
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

try:
    from src.scraper.screener_scraper import (
        ScreenerScraper, ScreenerScraperError, InvalidURLError, CompanyNotFoundError,
        ScreenerAccessError, InsufficientDataError
    )
    from src.prediction.forecasting_engine import (
        FinancialStatementForecaster, ForecastingError, InsufficientHistoryError
    )
    from src.valuation.dcf_model import DCFValuationEngine, ValuationValidationError
    from src.excel.workbook_builder import WorkbookBuilder
except ImportError:
    from screener_scraper import (
        ScreenerScraper, ScreenerScraperError, InvalidURLError, CompanyNotFoundError,
        ScreenerAccessError, InsufficientDataError
    )
    from forecasting_engine import (
        FinancialStatementForecaster, ForecastingError, InsufficientHistoryError
    )
    from dcf_model import DCFValuationEngine, ValuationValidationError
    from workbook_builder import WorkbookBuilder

# Page configuration
st.set_page_config(
    page_title="Universal Financial Prediction & DCF Valuation Engine",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Wall Street style styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1F4E78;
        margin-bottom: 0.1rem;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #555555;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background-color: #F8F9FA;
        border-radius: 8px;
        padding: 14px;
        border-left: 4px solid #1F4E78;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .disclaimer-box {
        background-color: #F8F9FA;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        padding: 12px 16px;
        font-size: 0.85rem;
        color: #64748B;
        margin-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📈 Universal Screener.in Financial Prediction & DCF Valuation Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Institutional 3-Statement Dynamic Forecasting, Out-of-Sample Backtesting & 8-Sheet Excel Valuation Model</div>', unsafe_allow_html=True)

# Sidebar Inputs & Controls
st.sidebar.header("🎯 Input Company URL")
default_url = "https://www.screener.in/company/TATASTEEL/consolidated/"
url_input = st.sidebar.text_input("Enter Screener.in Company URL:", value=default_url)

st.sidebar.markdown("**Quick Preset Companies:**")
col_b1, col_b2 = st.sidebar.columns(2)
with col_b1:
    if st.button("Tata Steel (Metals)", use_container_width=True):
        url_input = "https://www.screener.in/company/TATASTEEL/consolidated/"
with col_b2:
    if st.button("HUL (FMCG)", use_container_width=True):
        url_input = "https://www.screener.in/company/HINDUNILVR/"

col_b3, col_b4 = st.sidebar.columns(2)
with col_b3:
    if st.button("TCS (IT Services)", use_container_width=True):
        url_input = "https://www.screener.in/company/TCS/"
with col_b4:
    if st.button("Reliance (Energy)", use_container_width=True):
        url_input = "https://www.screener.in/company/RELIANCE/consolidated/"

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Valuation Parameters")
rf_rate = st.sidebar.slider("Risk-Free Rate (Rf %)", min_value=5.0, max_value=9.0, value=7.0, step=0.1) / 100.0
erp = st.sidebar.slider("Equity Risk Premium (ERP %)", min_value=4.0, max_value=8.0, value=5.5, step=0.1) / 100.0
beta_val = st.sidebar.slider("Beta (β)", min_value=0.4, max_value=2.0, value=1.0, step=0.05)
term_g = st.sidebar.slider("Terminal Growth Rate (g %)", min_value=2.5, max_value=6.0, value=4.5, step=0.25) / 100.0

st.sidebar.markdown("---")
run_button = st.sidebar.button("🚀 Run Prediction & Build Model", type="primary", use_container_width=True)


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


if url_input:
    with st.spinner("Extracting audited financials, backtesting econometric models, and running DCF valuation..."):
        try:
            raw_data, fc_results, val_results = fetch_and_compute(url_input, rf_rate, erp, beta_val, term_g)
        except InvalidURLError as e:
            st.error(f"❌ **Invalid URL**: {e}")
            st.info("💡 **Format Tip**: Use a direct company URL from Screener.in, such as `https://www.screener.in/company/TATASTEEL/consolidated/` or `https://www.screener.in/company/HINDUNILVR/`.")
            st.stop()
        except CompanyNotFoundError as e:
            st.error(f"❌ **Company Not Found**: {e}")
            st.info("💡 Please verify the ticker symbol in the URL.")
            st.stop()
        except InsufficientDataError as e:
            st.error(f"❌ **Data Extraction Issue**: {e}")
            st.stop()
        except InsufficientHistoryError as e:
            st.error(f"❌ **Insufficient Historical Data**: {e}")
            st.stop()
        except ValuationValidationError as e:
            st.error(f"❌ **Valuation Constraint Error**: {e}")
            st.warning("💡 Ensure that your Terminal Growth Rate ($g$) is strictly lower than WACC.")
            st.stop()
        except Exception as e:
            st.error(f"❌ **Unexpected Error**: {str(e)}")
            st.stop()

    company_name = raw_data['company_name']
    ticker = raw_data['ticker']
    kpis = raw_data['kpis']
    cmp = float(val_results['valuation_bridge']['current_market_price'])
    mcap = float(val_results['valuation_bridge']['market_capitalization_cr'])
    
    # Header KPIs
    st.subheader(f"🏢 {company_name} ({ticker})")
    kpi_cols = st.columns(6)
    kpi_cols[0].metric("Current Market Price", f"₹{cmp:,.1f}" if cmp > 0 else "N/A")
    kpi_cols[1].metric("Market Cap", f"₹{mcap:,.0f} Cr." if mcap > 0 else "N/A")
    kpi_cols[2].metric("Stock P/E", f"{kpis.get('Stock P/E', 'N/A')}")
    kpi_cols[3].metric("Book Value", f"₹{kpis.get('Book Value', 'N/A')}")
    kpi_cols[4].metric("ROCE", f"{kpis.get('ROCE', 'N/A')}%")
    kpi_cols[5].metric("ROE", f"{kpis.get('ROE', 'N/A')}%")

    # Data Quality & Provenance Expander
    with st.expander("🔍 Data Quality, Audit & Provenance Information", expanded=False):
        prov = raw_data.get('provenance', {})
        p_col1, p_col2, p_col3 = st.columns(3)
        p_col1.markdown(f"**Source URL**: [{prov.get('source_url', url_input)}]({prov.get('source_url', url_input)})")
        p_col1.markdown(f"**Reporting Scope**: {prov.get('reporting_type', 'Audited')}")
        p_col2.markdown(f"**Cash Flow Statement Available**: {'✅ Yes' if prov.get('has_cash_flow') else '⚠️ Not Found'}")
        p_col2.markdown(f"**Financial Ratios Available**: {'✅ Yes' if prov.get('has_ratios') else '⚠️ Not Found'}")
        p_col3.markdown(f"**Historical Fiscal Years**: {len(prov.get('historical_years_available', []))} years")
        p_col3.markdown(f"**Extraction Timestamp**: {prov.get('extracted_at_utc', 'Real-time')}")

    st.markdown("---")

    # Main Tabs
    tab_pred, tab_val, tab_sens, tab_stmts, tab_excel = st.tabs([
        "🔮 Prediction Engine & Backtesting",
        "💰 DCF Valuation & Fair Value",
        "📊 Sensitivity Heatmaps",
        "📑 Financial Statements & Drivers",
        "📥 Download Institutional Excel Model"
    ])

    # ==========================================
    # TAB 1: PREDICTION & BACKTESTING
    # ==========================================
    with tab_pred:
        st.markdown("### 🏆 Multi-Model Walk-Forward Backtest Accuracy")
        st.write("To ensure genuine out-of-sample accuracy, the engine trains an ensemble of 4 econometric and statistical models on earlier historical periods, tests predictions against the most recent actual reported periods, and selects the model with the lowest Mean Absolute Percentage Error (MAPE).")
        
        backtest = fc_results['backtest']
        best_model = backtest['best_model']

        eval_data = []
        for name, res in backtest['model_evaluations'].items():
            is_best = "👑 Selected (Lowest Error)" if name == best_model else ("⚠️ Invalid" if not res.get('is_valid', True) else "")
            eval_data.append({
                "Forecasting Model": name,
                "Backtest MAPE (%)": f"{res.get('mape', 'N/A')}%" if res.get('is_valid', True) else "Failed",
                "RMSE (₹ Cr.)": f"₹{res.get('rmse', 'N/A'):,.0f}" if res.get('is_valid', True) else "N/A",
                "MAE (₹ Cr.)": f"₹{res.get('mae', 'N/A'):,.0f}" if res.get('is_valid', True) else "N/A",
                "Status": is_best
            })
        df_eval = pd.DataFrame(eval_data)
        st.dataframe(df_eval, hide_index=True, use_container_width=True)

        st.markdown("---")
        st.markdown("### 📈 Revenue Trajectory: Historical vs. 5-Year Forecast Scenarios")

        hist_years = fc_results['historical_years']
        future_years = fc_results['future_years']

        pl_df = raw_data['profit_loss']
        sales_hist = [float(pl_df.loc['Sales', y]) if 'Sales' in pl_df.index and y in pl_df.columns else 0.0 for y in hist_years]
        ebitda_hist = [float(pl_df.loc['Operating Profit', y]) if 'Operating Profit' in pl_df.index and y in pl_df.columns else 0.0 for y in hist_years]

        sales_fc_base = fc_results['forecast_statements']['sales']
        ebitda_fc_base = fc_results['forecast_statements']['ebitda']
        sales_bull = fc_results['scenarios']['bull']['sales']
        sales_bear = fc_results['scenarios']['bear']['sales']

        fig_sales = go.Figure()
        # Historical
        fig_sales.add_trace(go.Scatter(
            x=hist_years, y=sales_hist, mode='lines+markers', name='Audited Historical Sales',
            line=dict(color='#1F4E78', width=3), marker=dict(size=7)
        ))
        # Base Forecast
        fig_sales.add_trace(go.Scatter(
            x=future_years, y=sales_fc_base, mode='lines+markers', name=f'Base Forecast ({best_model})',
            line=dict(color='#0070C0', width=3, dash='dash'), marker=dict(size=7)
        ))
        # Bull & Bear
        fig_sales.add_trace(go.Scatter(
            x=future_years, y=sales_bull, mode='lines', name='Bull Case (+0.5σ)',
            line=dict(color='rgba(46, 204, 113, 0.8)', width=1.5, dash='dot')
        ))
        fig_sales.add_trace(go.Scatter(
            x=future_years, y=sales_bear, mode='lines', name='Bear Case (-0.5σ)',
            line=dict(color='rgba(231, 76, 60, 0.8)', width=1.5, dash='dot'),
            fill='tonexty', fillcolor='rgba(0, 112, 192, 0.08)'
        ))

        fig_sales.update_layout(
            title="Revenue Projections with Scenario Uncertainty Bands (₹ Cr.)",
            xaxis_title="Fiscal Period",
            yaxis_title="Sales (₹ Cr.)",
            hovermode="x unified",
            template="plotly_white",
            height=420
        )
        st.plotly_chart(fig_sales, use_container_width=True)

        col_fc1, col_fc2 = st.columns(2)
        with col_fc1:
            fig_ebitda = go.Figure()
            fig_ebitda.add_trace(go.Bar(x=hist_years[-5:], y=ebitda_hist[-5:], name='Historical EBITDA', marker_color='#1F4E78'))
            fig_ebitda.add_trace(go.Bar(x=future_years, y=ebitda_fc_base, name='Forecast EBITDA', marker_color='#2CA02C'))
            fig_ebitda.update_layout(title="Operating Profit (EBITDA) Profile (₹ Cr.)", template="plotly_white", height=350)
            st.plotly_chart(fig_ebitda, use_container_width=True)

        with col_fc2:
            fcff_vals = fc_results['forecast_statements']['fcff']
            fig_fcff = go.Figure()
            fig_fcff.add_trace(go.Bar(x=future_years, y=fcff_vals, name='Projected FCFF', marker_color='#008080'))
            fig_fcff.update_layout(title="Unlevered Free Cash Flow (FCFF) Conversion (₹ Cr.)", template="plotly_white", height=350)
            st.plotly_chart(fig_fcff, use_container_width=True)

    # ==========================================
    # TAB 2: DCF VALUATION & FAIR VALUE
    # ==========================================
    with tab_val:
        st.markdown("### 🎯 Valuation Summary & Target Prices")

        g_data = val_results['gordon_growth_method']
        g_target = g_data['target_price_per_share']
        g_upside = g_data['upside_pct']
        m_target = val_results['exit_multiple_method']['target_price_per_share']
        m_upside = val_results['exit_multiple_method']['upside_pct']
        fair_target = val_results['fair_value_summary']['blended_target_price']
        fair_upside = val_results['fair_value_summary']['blended_upside_pct']
        wacc_pct = val_results['wacc_parameters']['wacc_pct']

        v_cols = st.columns(4)
        v_cols[0].metric("CMP", f"₹{cmp:,.1f}" if cmp > 0 else "N/A")
        v_cols[1].metric("Gordon Growth Target", f"₹{g_target:,.1f}", delta=f"{g_upside:+.1f}%")
        v_cols[2].metric("Exit Multiple Target", f"₹{m_target:,.1f}", delta=f"{m_upside:+.1f}%")
        v_cols[3].metric("Blended Fair Value", f"₹{fair_target:,.1f}", delta=f"{fair_upside:+.1f}%")

        if g_data.get('high_tv_warning', False):
            st.warning(
                f"⚠️ **High Terminal Value Reliance**: The Present Value of Terminal Value accounts for "
                f"**{g_data['tv_percent_of_ev']}%** of Enterprise Value. Valuation results are particularly sensitive to "
                f"the terminal growth rate ({g_data['terminal_growth_pct']}%) and WACC ({wacc_pct}%)."
            )

        st.markdown("---")
        st.markdown("### 🌉 Enterprise Value to Equity Value Bridge (Gordon Growth)")

        cum_fcf = val_results['valuation_bridge']['cumulative_pv_fcff_cr']
        pv_tv = g_data['pv_terminal_value_cr']
        ev = g_data['enterprise_value_cr']
        cash = val_results['valuation_bridge']['cash_and_investments_cr']
        debt = val_results['valuation_bridge']['total_debt_cr']
        eq_val = g_data['implied_equity_value_cr']

        fig_waterfall = go.Figure(go.Waterfall(
            name="Valuation Bridge",
            orientation="v",
            measure=["relative", "relative", "total", "relative", "relative", "total"],
            x=["5-Yr PV FCFF", "PV Terminal Value", "Enterprise Value", "(+) Cash & Inv.", "(-) Total Debt", "Equity Value"],
            textposition="outside",
            text=[f"₹{cum_fcf:,.0f}", f"₹{pv_tv:,.0f}", f"₹{ev:,.0f}", f"₹{cash:,.0f}", f"-₹{debt:,.0f}", f"₹{eq_val:,.0f}"],
            y=[cum_fcf, pv_tv, ev, cash, -debt, eq_val],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
        ))
        fig_waterfall.update_layout(title="Bridge: PV of Operating Cash Flows to Equity Value (₹ Cr.)", template="plotly_white", height=400)
        st.plotly_chart(fig_waterfall, use_container_width=True)

        col_w1, col_w2 = st.columns(2)
        with col_w1:
            st.markdown("#### ⚖️ Cost of Capital (WACC) Breakdown")
            w_params = val_results['wacc_parameters']
            w_df = pd.DataFrame([
                {"Component": "Risk-Free Rate (Rf)", "Value": f"{w_params['risk_free_rate_pct']}%"},
                {"Component": "Equity Risk Premium (ERP)", "Value": f"{w_params['equity_risk_premium_pct']}%"},
                {"Component": "Beta (β)", "Value": f"{w_params['beta']}"},
                {"Component": "Cost of Equity (Ke)", "Value": f"{w_params['cost_of_equity_pct']}%"},
                {"Component": "Pre-Tax Cost of Debt (Kd)", "Value": f"{w_params['cost_of_debt_pre_tax_pct']}%"},
                {"Component": "Post-Tax Cost of Debt (Kd post-tax)", "Value": f"{w_params['cost_of_debt_post_tax_pct']}%"},
                {"Component": "Weight of Equity (We)", "Value": f"{w_params['weight_equity_pct']}%"},
                {"Component": "Weight of Debt (Wd)", "Value": f"{w_params['weight_debt_pct']}%"},
                {"Component": "Calculated WACC", "Value": f"{w_params['wacc_pct']}%"},
            ])
            st.dataframe(w_df, hide_index=True, use_container_width=True)

        with col_w2:
            st.markdown("#### 📌 Key Valuation Outputs & Bridge Metrics")
            out_df = pd.DataFrame([
                {"Metric": "Discounting Convention", "Value": "Mid-Year Convention (t - 0.5)"},
                {"Metric": "5-Year Cumulative PV of FCFF", "Value": f"₹{cum_fcf:,.1f} Cr."},
                {"Metric": "PV of Terminal Value", "Value": f"₹{pv_tv:,.1f} Cr."},
                {"Metric": "% Terminal Value of Total EV", "Value": f"{g_data['tv_percent_of_ev']}%"},
                {"Metric": "Enterprise Value (EV)", "Value": f"₹{ev:,.1f} Cr."},
                {"Metric": "(+) Cash & Liquid Investments", "Value": f"₹{cash:,.1f} Cr."},
                {"Metric": "(-) Total Borrowings (Debt)", "Value": f"₹{debt:,.1f} Cr."},
                {"Metric": "Implied Equity Value", "Value": f"₹{eq_val:,.1f} Cr."},
                {"Metric": "Diluted Shares Outstanding", "Value": f"{val_results['valuation_bridge']['shares_outstanding_cr']:,.1f} Cr."},
                {"Metric": "Target Price Per Share", "Value": f"₹{g_target:,.1f}"},
            ])
            st.dataframe(out_df, hide_index=True, use_container_width=True)

    # ==========================================
    # TAB 3: SENSITIVITY HEATMAPS
    # ==========================================
    with tab_sens:
        st.markdown("### 🗺️ Two-Way Valuation Sensitivity Heatmaps")
        st.write("Examine how target share price responds to varying Cost of Capital (WACC), Terminal Growth Rates ($g$), and Exit Multiples. Combinations where $WACC \le g$ are labeled as unavailable.")

        sens_g = val_results['sensitivity_gordon']
        sens_m = val_results['sensitivity_multiple']

        col_hm1, col_hm2 = st.columns(2)
        with col_hm1:
            st.markdown("#### Table 1: WACC vs. Terminal Growth Rate (g)")
            matrix_g = np.array([[val if val is not None else np.nan for val in row] for row in sens_g['matrix']], dtype=float)
            fig_hm1 = px.imshow(
                matrix_g,
                x=sens_g['wacc_columns'],
                y=sens_g['growth_rows'],
                labels=dict(x="WACC", y="Terminal Growth (g)", color="Target Price (₹)"),
                color_continuous_scale="RdYlGn",
                text_auto=True
            )
            fig_hm1.update_layout(height=420)
            st.plotly_chart(fig_hm1, use_container_width=True)

        with col_hm2:
            st.markdown("#### Table 2: WACC vs. Exit Multiple (EV/EBITDA)")
            matrix_m = np.array(sens_m['matrix'], dtype=float)
            fig_hm2 = px.imshow(
                matrix_m,
                x=sens_m['wacc_columns'],
                y=sens_m['multiple_rows'],
                labels=dict(x="WACC", y="Exit Multiple", color="Target Price (₹)"),
                color_continuous_scale="RdYlGn",
                text_auto=True
            )
            fig_hm2.update_layout(height=420)
            st.plotly_chart(fig_hm2, use_container_width=True)

    # ==========================================
    # TAB 4: FINANCIAL STATEMENTS
    # ==========================================
    with tab_stmts:
        st.markdown("### 📑 Forecasted 5-Year Financial Statements (₹ Cr.)")
        fc_stmt = fc_results['forecast_statements']
        
        df_forecast_display = pd.DataFrame({
            "Revenue (Sales)": fc_stmt['sales'],
            "Operating Expenses": fc_stmt['expenses'],
            "EBITDA": fc_stmt['ebitda'],
            "D&A": fc_stmt['depreciation'],
            "EBIT": fc_stmt['ebit'],
            "Interest": fc_stmt['interest'],
            "Other Income": fc_stmt['other_income'],
            "Profit Before Tax (PBT)": fc_stmt['pbt'],
            "Tax Provision": fc_stmt['tax'],
            "Net Profit (PAT)": fc_stmt['pat'],
            "Net PP&E Block": fc_stmt['fixed_assets'],
            "Capex": fc_stmt['capex'],
            "Total Borrowings": fc_stmt['debt'],
            "Free Cash Flow (FCFF)": fc_stmt['fcff'],
        }, index=fc_results['future_years']).T

        st.dataframe(df_forecast_display.style.format("{:,.1f}"), use_container_width=True)

    # ==========================================
    # TAB 5: DOWNLOAD EXCEL MODEL
    # ==========================================
    with tab_excel:
        st.markdown("### 📥 Download Institutional 8-Worksheet Excel Financial Model")
        st.write("Click below to download the complete, formula-linked `.xlsx` workbook containing:")
        
        col_list1, col_list2 = st.columns(2)
        with col_list1:
            st.markdown("""
            * **1. Read_Me**: Comprehensive model guide, color coding standard, dynamic integrity checks.
            * **2. Raw_Data**: Audited historical statements extracted verbatim from filings.
            * **3. Historical_Financials**: Standardized 5-year financials and common-size margin analysis.
            * **4. Assumptions**: Econometric drivers, working capital cycle, and WACC parameters.
            """)
        with col_list2:
            st.markdown("""
            * **5. Forecast**: 5-Year 3-statement forecast with zero hardcoded forecast values.
            * **6. DCF_Valuation**: FCFF discounting, Terminal Value, and Enterprise-to-Equity bridge.
            * **7. Sensitivity_Analysis**: Two-way sensitivity grids for WACC and growth/multiples.
            * **8. Dashboard**: Executive KPI cards, DuPont metrics, and audit check status lights.
            """)

        out_filename = f"{ticker}_Institutional_Financial_Model.xlsx"
        builder = WorkbookBuilder(raw_data, fc_results, val_results)
        file_bytes = builder.generate_bytes()

        st.download_button(
            label=f"⬇️ Download {ticker} Financial Model (.xlsx)",
            data=file_bytes,
            file_name=out_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )
        st.success(f"Workbook generated successfully! Ready for download: `{out_filename}`")

    # Visible Institutional Disclaimer
    st.markdown("""
    <div class="disclaimer-box">
        <strong>⚠️ Institutional Research Disclaimer:</strong> This application is an automated quantitative financial modeling and valuation tool 
        developed for academic, research, and equity analysis purposes. Financial statement projections and intrinsic values are estimated 
        using econometric algorithms and Discounted Cash Flow (DCF) frameworks based on historical filings. This model does not constitute 
        financial, investment, or legal advice, nor a recommendation to buy or sell any security.
    </div>
    """, unsafe_allow_html=True)
