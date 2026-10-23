"""
Comprehensive Automated Test Suite for Financial Prediction & Valuation Engine
Covers number parsing, URL validation, history requirements, backtesting,
forecast alignment, DCF validation, terminal growth vs WACC, and sensitivity matrices.
"""

import unittest
import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import pandas as pd
import io
import openpyxl

from screener_scraper import clean_number, ScreenerScraper, InvalidURLError
from forecasting_engine import (
    ForecastingModels, BacktestingEngine, FinancialStatementForecaster,
    InsufficientHistoryError
)
from dcf_model import DCFValuationEngine, ValuationValidationError
from workbook_builder import WorkbookBuilder


class TestNumberParsing(unittest.TestCase):
    def test_clean_number_standard(self):
        self.assertEqual(clean_number("1,234.56"), 1234.56)
        self.assertEqual(clean_number("₹ 2,15,316 Cr."), 215316.0)
        self.assertEqual(clean_number("18.2%"), 18.2)
        self.assertEqual(clean_number("Rs. 450"), 450.0)

    def test_clean_number_negatives(self):
        self.assertEqual(clean_number("(500)"), -500.0)
        self.assertEqual(clean_number("-123.45"), -123.45)
        self.assertEqual(clean_number("(1,250.50)"), -1250.5)

    def test_clean_number_invalids(self):
        self.assertIsNone(clean_number(None))
        self.assertIsNone(clean_number(""))
        self.assertIsNone(clean_number("-"))
        self.assertIsNone(clean_number("—"))
        self.assertIsNone(clean_number("N/A"))
        self.assertIsNone(clean_number("not_a_number"))


class TestURLValidation(unittest.TestCase):
    def test_valid_screener_urls(self):
        norm_url, ticker = ScreenerScraper.validate_url("https://www.screener.in/company/TATASTEEL/consolidated/")
        self.assertEqual(ticker, "TATASTEEL")
        self.assertTrue(norm_url.startswith("https://www.screener.in/company/TATASTEEL"))

        norm_url, ticker = ScreenerScraper.validate_url("screener.in/company/HINDUNILVR")
        self.assertEqual(ticker, "HINDUNILVR")

    def test_invalid_urls(self):
        with self.assertRaises(InvalidURLError):
            ScreenerScraper.validate_url("https://google.com/search")
        with self.assertRaises(InvalidURLError):
            ScreenerScraper.validate_url("https://www.screener.in/screens/123/")
        with self.assertRaises(InvalidURLError):
            ScreenerScraper.validate_url("")
        with self.assertRaises(InvalidURLError):
            ScreenerScraper.validate_url("not a url")


class TestForecastingAndHistory(unittest.TestCase):
    def test_insufficient_history_rejection(self):
        short_series = np.array([100.0, 110.0, 120.0]) # Only 3 periods
        with self.assertRaises(InsufficientHistoryError):
            BacktestingEngine.evaluate_models(short_series, test_horizon=1)

    def test_backtesting_model_selection(self):
        # 8 historical periods
        series = np.array([100.0, 110.0, 121.0, 133.1, 146.4, 161.0, 177.1, 194.8])
        res = BacktestingEngine.evaluate_models(series, test_horizon=3)
        self.assertIn(res['best_model'], [
            'Auto-Regressive (AR)', 'Log-Linear Trend', 'Holt-Winters Damped', 'Fundamental CAGR Mean-Reversion'
        ])
        best_eval = res['model_evaluations'][res['best_model']]
        self.assertTrue(best_eval['is_valid'])
        self.assertLess(best_eval['mape'], 900.0)

    def test_forecast_output_alignment(self):
        # Create minimal synthetic company raw_data
        years = ['Mar 2021', 'Mar 2022', 'Mar 2023', 'Mar 2024', 'Mar 2025']
        pl_data = {
            'Sales': [1000.0, 1100.0, 1250.0, 1400.0, 1550.0],
            'Expenses': [800.0, 880.0, 1000.0, 1120.0, 1240.0],
            'Operating Profit': [200.0, 220.0, 250.0, 280.0, 310.0],
            'OPM %': [20.0, 20.0, 20.0, 20.0, 20.0],
            'Depreciation': [50.0, 55.0, 60.0, 65.0, 70.0],
            'Interest': [30.0, 30.0, 28.0, 25.0, 20.0],
            'Other Income': [10.0, 12.0, 15.0, 14.0, 16.0],
            'Profit before tax': [130.0, 147.0, 177.0, 204.0, 236.0],
            'Tax %': [25.0, 25.0, 25.0, 25.0, 25.0],
            'Net Profit': [97.5, 110.2, 132.7, 153.0, 177.0],
            'Dividend Payout %': [20.0, 20.0, 20.0, 20.0, 20.0]
        }
        bs_data = {
            'Equity Capital': [50.0, 50.0, 50.0, 50.0, 50.0],
            'Reserves': [400.0, 480.0, 580.0, 700.0, 840.0],
            'Borrowings': [300.0, 280.0, 250.0, 220.0, 180.0],
            'Fixed Assets': [500.0, 540.0, 590.0, 650.0, 710.0],
            'Investments': [100.0, 120.0, 140.0, 160.0, 180.0],
            'Other Assets': [150.0, 160.0, 170.0, 180.0, 190.0],
        }
        cf_data = {
            'Cash from Operating Activity': [180.0, 200.0, 220.0, 250.0, 280.0],
            'Cash from Investing Activity': [-100.0, -110.0, -120.0, -130.0, -140.0],
            'Cash from Financing Activity': [-50.0, -60.0, -60.0, -70.0, -80.0],
        }
        ratios_data = {
            'Debtor Days': [30.0, 32.0, 31.0, 29.0, 30.0],
            'Inventory Days': [45.0, 46.0, 44.0, 45.0, 45.0],
            'Days Payable': [40.0, 42.0, 41.0, 40.0, 40.0],
        }
        raw = {
            'url': 'https://www.screener.in/company/TESTCO/',
            'company_name': 'Test Company Ltd',
            'ticker': 'TESTCO',
            'kpis': {'Current Price': 100.0, 'Market Cap': 2500.0, 'Face Value': 2.0, 'Stock P/E': 15.0},
            'profit_loss': pd.DataFrame(pl_data, index=years).T,
            'balance_sheet': pd.DataFrame(bs_data, index=years).T,
            'cash_flow': pd.DataFrame(cf_data, index=years).T,
            'ratios': pd.DataFrame(ratios_data, index=years).T,
        }

        forecaster = FinancialStatementForecaster(raw)
        fc_res = forecaster.run_forecast(forecast_years=5)

        self.assertEqual(len(fc_res['future_years']), 5)
        stmt = fc_res['forecast_statements']
        self.assertEqual(len(stmt['sales']), 5)
        self.assertEqual(len(stmt['fcff']), 5)
        # Verify revenue positivity
        for s in stmt['sales']:
            self.assertGreater(s, 0)
        # Scenario monotonicity: Bull >= Base >= Bear
        scen = fc_res['scenarios']
        for i in range(5):
            self.assertGreaterEqual(scen['bull']['sales'][i], scen['base']['sales'][i])
            self.assertGreaterEqual(scen['base']['sales'][i], scen['bear']['sales'][i])


class TestDCFValuationAndSensitivity(unittest.TestCase):
    def setUp(self):
        years = ['Mar 2021', 'Mar 2022', 'Mar 2023', 'Mar 2024', 'Mar 2025']
        pl_data = {
            'Sales': [1000.0, 1100.0, 1250.0, 1400.0, 1550.0],
            'Operating Profit': [200.0, 220.0, 250.0, 280.0, 310.0],
            'OPM %': [20.0, 20.0, 20.0, 20.0, 20.0],
            'Depreciation': [50.0, 55.0, 60.0, 65.0, 70.0],
            'Interest': [30.0, 30.0, 28.0, 25.0, 20.0],
            'Other Income': [10.0, 12.0, 15.0, 14.0, 16.0],
            'Tax %': [25.0, 25.0, 25.0, 25.0, 25.0],
        }
        bs_data = {
            'Equity Capital': [50.0, 50.0, 50.0, 50.0, 50.0],
            'Borrowings': [300.0, 280.0, 250.0, 220.0, 180.0],
            'Fixed Assets': [500.0, 540.0, 590.0, 650.0, 710.0],
            'Investments': [100.0, 120.0, 140.0, 160.0, 180.0],
            'Other Assets': [150.0, 160.0, 170.0, 180.0, 190.0],
        }
        self.raw = {
            'url': 'https://www.screener.in/company/TESTCO/',
            'company_name': 'Test Company Ltd',
            'ticker': 'TESTCO',
            'kpis': {'Current Price': 100.0, 'Market Cap': 2500.0, 'Face Value': 2.0, 'Stock P/E': 15.0},
            'profit_loss': pd.DataFrame(pl_data, index=years).T,
            'balance_sheet': pd.DataFrame(bs_data, index=years).T,
            'cash_flow': pd.DataFrame({}, index=years).T,
            'ratios': pd.DataFrame({}, index=years).T,
        }
        forecaster = FinancialStatementForecaster(self.raw)
        self.fc_res = forecaster.run_forecast(forecast_years=5)

    def test_terminal_growth_vs_wacc_constraint(self):
        dcf = DCFValuationEngine(self.raw, self.fc_res)
        # Terminal growth >= WACC should raise ValuationValidationError
        with self.assertRaises(ValuationValidationError):
            dcf.calculate_valuation(terminal_growth=0.15) # 15% is higher than WACC (~10-12%)

    def test_valid_dcf_computation(self):
        dcf = DCFValuationEngine(self.raw, self.fc_res)
        val = dcf.calculate_valuation(terminal_growth=0.04)
        self.assertGreater(val['wacc_parameters']['wacc_pct'], 4.0)
        self.assertGreater(val['gordon_growth_method']['enterprise_value_cr'], 0)
        self.assertGreater(val['gordon_growth_method']['target_price_per_share'], 0)
        self.assertGreater(val['exit_multiple_method']['target_price_per_share'], 0)

    def test_sensitivity_matrix_bounds(self):
        dcf = DCFValuationEngine(self.raw, self.fc_res)
        val = dcf.calculate_valuation(terminal_growth=0.04)
        sens_g = val['sensitivity_gordon']
        # Check that matrix dimensions match columns and rows
        self.assertEqual(len(sens_g['matrix']), len(sens_g['growth_rows']))
        self.assertEqual(len(sens_g['matrix'][0]), len(sens_g['wacc_columns']))

    def test_excel_in_memory_generation(self):
        dcf = DCFValuationEngine(self.raw, self.fc_res)
        val = dcf.calculate_valuation(terminal_growth=0.04)
        builder = WorkbookBuilder(self.raw, self.fc_res, val)
        excel_bytes = builder.generate_bytes()
        self.assertIsInstance(excel_bytes, bytes)
        self.assertGreater(len(excel_bytes), 5000)

        # Validate that openpyxl can load the generated workbook from bytes
        wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
        expected_sheets = [
            'Read_Me', 'Raw_Data', 'Historical_Financials', 'Assumptions',
            'Forecast', 'DCF_Valuation', 'Sensitivity_Analysis', 'Dashboard'
        ]
        self.assertEqual(wb.sheetnames, expected_sheets)


class TestNewsSentimentEngine(unittest.TestCase):
    def test_sentiment_scoring(self):
        from news_sentiment_engine import NewsSentimentEngine
        engine = NewsSentimentEngine()
        score_pos, label_pos, pos_w, _ = engine._score_sentiment("Company reports record profit jump and margin expansion")
        self.assertGreater(score_pos, 0.2)
        self.assertEqual(label_pos, "Positive")

        score_neg, label_neg, _, neg_w = engine._score_sentiment("Stock falls 5% as SEBI issues penalty notice after profit crash")
        self.assertLess(score_neg, -0.2)
        self.assertEqual(label_neg, "Negative")

    def test_catalyst_detection(self):
        from news_sentiment_engine import NewsSentimentEngine
        engine = NewsSentimentEngine()
        self.assertEqual(engine._detect_catalyst("Q2 financial results show strong EBITDA"), "Earnings & Margins")
        self.assertEqual(engine._detect_catalyst("Wins Rs 5,000 crore contract for plant expansion"), "Orders & Capex")
        self.assertEqual(engine._detect_catalyst("SEBI initiates probe into board governance"), "Regulatory & Governance")

    def test_catalyst_impact_calculation(self):
        from news_sentiment_engine import NewsSentimentEngine
        engine = NewsSentimentEngine()
        sample_articles = [
            {
                'title': 'Company beats profit estimates with record margins',
                'source': 'Economic Times',
                'link': 'https://example.com',
                'pub_date': 'Today',
                'sentiment_score': 0.8,
                'sentiment_label': 'Positive',
                'catalyst': 'Earnings & Margins',
                'positive_signals': ['profit', 'record'],
                'negative_signals': []
            }
        ]
        impact = engine.evaluate_catalyst_impact(sample_articles, base_target_price=500.0, wacc_pct=11.0)
        self.assertTrue(impact['has_news'])
        self.assertGreater(impact['catalyst_score'], 0)
        self.assertGreater(impact['sentiment_adjusted_target'], 500.0)
        self.assertIn("Bullish", impact['sentiment_bias'])


if __name__ == '__main__':
    unittest.main()
