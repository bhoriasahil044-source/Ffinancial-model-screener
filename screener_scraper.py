"""
Screener.in Financial Data Scraper
Extracts audited historical financials, balance sheets, cash flows, ratios, and profile metadata
for any company URL from Screener.in with strict validation and robust error handling.
"""

import re
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np


class ScreenerScraperError(Exception):
    """Base exception for Screener scraping operations."""
    pass


class InvalidURLError(ScreenerScraperError):
    """Raised when the provided URL does not match valid Screener.in company structure."""
    pass


class CompanyNotFoundError(ScreenerScraperError):
    """Raised when Screener returns a 404 or the company does not exist."""
    pass


class ScreenerAccessError(ScreenerScraperError):
    """Raised when request is blocked, rate-limited, or times out."""
    pass


class InsufficientDataError(ScreenerScraperError):
    """Raised when extracted financial statements lack the minimum required history."""
    pass


def clean_number(text: Any) -> Optional[float]:
    """Clean and convert string representations of numbers to float."""
    if text is None:
        return None
    s = str(text).replace('\xa0', ' ').strip()
    if not s or s in ['-', '—', 'N/A', 'nan', 'NaN', '']:
        return None
    
    # Remove percentage, currency symbols, and commas
    s = s.replace('%', '').replace(',', '').replace('₹', '').replace('Rs.', '').replace('Cr.', '').strip()
    
    # Check for parentheses indicating negative numbers: (123) -> -123
    neg_match = re.match(r'^\((.*)\)$', s)
    if neg_match:
        s = '-' + neg_match.group(1).strip()
        
    try:
        val = float(s)
        return val if np.isfinite(val) else None
    except (ValueError, TypeError):
        return None


def clean_row_label(label: str) -> str:
    """Normalize row names by removing plus icons, drill-down markers, and extra whitespace."""
    if not label:
        return ""
    cleaned = label.replace('\xa0', ' ').replace('+', '').strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned


class ScreenerScraper:
    VALID_DOMAINS = ['www.screener.in', 'screener.in']

    def __init__(self, headers: Optional[Dict[str, str]] = None, timeout: int = 15):
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.timeout = timeout

    @classmethod
    def validate_url(cls, url: str) -> Tuple[str, str]:
        """
        Validate URL format and extract company ticker.
        Returns normalized URL and ticker.
        Raises InvalidURLError if format is invalid.
        """
        if not url or not isinstance(url, str):
            raise InvalidURLError("URL must be a non-empty string.")

        s = url.strip()
        if not s.startswith(('http://', 'https://')):
            s = 'https://' + s.lstrip('/')

        try:
            parsed = urllib.parse.urlparse(s)
        except Exception as e:
            raise InvalidURLError(f"Malformed URL: {e}")

        if parsed.netloc.lower() not in cls.VALID_DOMAINS:
            raise InvalidURLError(
                f"Domain '{parsed.netloc}' is not supported. URL must be from screener.in "
                f"(e.g., https://www.screener.in/company/TATASTEEL/consolidated/)."
            )

        # Path must be /company/<TICKER>/ or /company/<TICKER>/consolidated/
        path_parts = [p for p in parsed.path.split('/') if p]
        if len(path_parts) < 2 or path_parts[0].lower() != 'company':
            raise InvalidURLError(
                f"Invalid Screener path '{parsed.path}'. "
                f"Expected format: https://www.screener.in/company/<TICKER>/ or .../consolidated/"
            )

        ticker = path_parts[1].upper()
        if not re.match(r'^[A-Z0-9_\-\.&]+$', ticker):
            raise InvalidURLError(f"Invalid ticker symbol '{ticker}' in URL.")

        # Reconstruct clean normalized HTTPS URL
        subpath = '/'.join(path_parts)
        normalized_url = f"https://www.screener.in/{subpath}/"

        return normalized_url, ticker

    def fetch_company_data(self, url: str) -> Dict[str, Any]:
        """Fetch and parse all financial statements and ratios from a Screener.in company URL."""
        normalized_url, ticker = self.validate_url(url)
        is_consolidated = 'consolidated' in normalized_url.lower()

        try:
            response = requests.get(normalized_url, headers=self.headers, timeout=self.timeout)
        except requests.exceptions.Timeout:
            raise ScreenerAccessError(f"Request timed out connecting to Screener.in for {ticker}. Please try again.")
        except requests.exceptions.ConnectionError:
            raise ScreenerAccessError("Network connection error. Check your internet connection.")
        except Exception as e:
            raise ScreenerAccessError(f"Failed to fetch data from Screener.in: {e}")

        if response.status_code == 404:
            raise CompanyNotFoundError(f"Company '{ticker}' not found on Screener.in (HTTP 404).")
        elif response.status_code in [403, 429]:
            raise ScreenerAccessError(f"Screener.in temporarily rate-limited or blocked the request (HTTP {response.status_code}).")
        elif response.status_code != 200:
            raise ScreenerAccessError(f"Screener.in returned unexpected HTTP status {response.status_code}.")

        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Company Name & Profile
        name_elem = soup.find('h1')
        company_name = name_elem.text.strip() if name_elem else ticker

        # 2. Company Top Ratios & KPIs
        top_kpis: Dict[str, Any] = {}
        for li in soup.select('ul#top-ratios li'):
            name_span = li.find('span', class_='name')
            val_span = li.find('span', class_='number')
            if name_span and val_span:
                kpi_name = clean_row_label(name_span.text)
                top_kpis[kpi_name] = clean_number(val_span.text)

        for li in soup.select('ul#top-ratios li'):
            name_span = li.find('span', class_='name')
            if name_span and 'High / Low' in name_span.text:
                num_spans = li.find_all('span', class_='number')
                if len(num_spans) >= 2:
                    top_kpis['High'] = clean_number(num_spans[0].text)
                    top_kpis['Low'] = clean_number(num_spans[1].text)

        # 3. Extract Financial Statement Tables
        pl_df = self._parse_table_section(soup, 'profit-loss')
        bs_df = self._parse_table_section(soup, 'balance-sheet')
        cf_df = self._parse_table_section(soup, 'cash-flow')
        ratios_df = self._parse_table_section(soup, 'ratios')
        quarters_df = self._parse_table_section(soup, 'quarters')
        shareholding_df = self._parse_table_section(soup, 'shareholding')

        # Validate that essential tables exist
        if pl_df.empty:
            raise InsufficientDataError(f"No Profit & Loss statement found on Screener.in for {company_name}.")
        if bs_df.empty:
            raise InsufficientDataError(f"No Balance Sheet found on Screener.in for {company_name}.")

        # 4. About / Business Description
        about_div = soup.find('div', class_='about')
        about_text = about_div.text.strip() if about_div else ""

        # 5. Provenance Metadata
        provenance = {
            'source_url': normalized_url,
            'ticker': ticker,
            'extracted_at_utc': datetime.now(timezone.utc).isoformat(),
            'reporting_type': 'Consolidated' if is_consolidated else 'Standalone',
            'has_cash_flow': not cf_df.empty,
            'has_ratios': not ratios_df.empty,
            'historical_years_available': [c for c in pl_df.columns if c != 'TTM']
        }

        return {
            'url': normalized_url,
            'company_name': company_name,
            'ticker': ticker,
            'kpis': top_kpis,
            'about': about_text,
            'profit_loss': pl_df,
            'balance_sheet': bs_df,
            'cash_flow': cf_df,
            'ratios': ratios_df,
            'quarters': quarters_df,
            'shareholding': shareholding_df,
            'provenance': provenance,
        }

    def _parse_table_section(self, soup: BeautifulSoup, section_id: str) -> pd.DataFrame:
        """Parse an HTML table inside a section ID into a clean pandas DataFrame."""
        section = soup.find('section', id=section_id)
        if not section:
            return pd.DataFrame()
            
        table = section.find('table')
        if not table:
            return pd.DataFrame()
            
        thead = table.find('thead')
        if not thead:
            return pd.DataFrame()
            
        headers = []
        for th in thead.find_all('th'):
            t = th.text.strip()
            if t:
                headers.append(t)
                
        tbody = table.find('tbody')
        if not tbody:
            return pd.DataFrame()
            
        rows_data = {}
        for tr in tbody.find_all('tr'):
            tds = tr.find_all('td')
            if not tds:
                continue
            row_label = clean_row_label(tds[0].text)
            if not row_label:
                continue
                
            vals = []
            for td in tds[1:]:
                vals.append(clean_number(td.text))
                
            if len(vals) < len(headers):
                vals.extend([None] * (len(headers) - len(vals)))
            elif len(vals) > len(headers):
                vals = vals[:len(headers)]
                
            rows_data[row_label] = vals
            
        if not rows_data or not headers:
            return pd.DataFrame()
            
        df = pd.DataFrame(rows_data, index=headers).T
        return df
