"""
Screener.in Financial Data Scraper
Extracts audited historical financials, balance sheets, cash flows, ratios, and profile metadata
for any company URL from Screener.in.
"""

import re
import urllib.parse
from typing import Dict, Any, List, Optional
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np


def clean_number(text: str) -> Optional[float]:
    """Clean and convert string representations of numbers to float."""
    if text is None:
        return None
    s = str(text).replace('\xa0', ' ').strip()
    if not s or s == '-' or s == '—' or s == '':
        return None
    
    # Remove percentage, currency symbols, and commas
    s = s.replace('%', '').replace(',', '').replace('₹', '').replace('Cr.', '').strip()
    
    # Check for parentheses indicating negative numbers: (123) -> -123
    neg_match = re.match(r'^\((.*)\)$', s)
    if neg_match:
        s = '-' + neg_match.group(1).strip()
        
    try:
        return float(s)
    except ValueError:
        return None


def clean_row_label(label: str) -> str:
    """Normalize row names by removing plus icons, drill-down markers, and extra whitespace."""
    if not label:
        return ""
    cleaned = label.replace('\xa0', ' ').replace('+', '').strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned


class ScreenerScraper:
    def __init__(self, headers: Optional[Dict[str, str]] = None):
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }

    def fetch_company_data(self, url: str) -> Dict[str, Any]:
        """Fetch and parse all financial statements and ratios from a Screener.in company URL."""
        # Ensure proper URL formatting
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme:
            url = 'https://' + url.lstrip('/')
        
        response = requests.get(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Company Name & Symbol
        name_elem = soup.find('h1')
        company_name = name_elem.text.strip() if name_elem else "Unknown Company"
        
        # Extract ticker from URL
        path_parts = [p for p in parsed.path.split('/') if p]
        ticker = path_parts[1].upper() if len(path_parts) > 1 and path_parts[0] == 'company' else "COMPANY"
        
        # 2. Company Top Ratios & KPIs
        top_kpis: Dict[str, Any] = {}
        for li in soup.select('ul#top-ratios li'):
            name_span = li.find('span', class_='name')
            val_span = li.find('span', class_='number')
            if name_span and val_span:
                kpi_name = clean_row_label(name_span.text)
                top_kpis[kpi_name] = clean_number(val_span.text)

        # Also get high/low if present
        for li in soup.select('ul#top-ratios li'):
            name_span = li.find('span', class_='name')
            if name_span and 'High / Low' in name_span.text:
                num_spans = li.find_all('span', class_='number')
                if len(num_spans) >= 2:
                    top_kpis['High'] = clean_number(num_spans[0].text)
                    top_kpis['Low'] = clean_number(num_spans[1].text)

        # 3. Extract Financial Tables
        pl_df = self._parse_table_section(soup, 'profit-loss')
        bs_df = self._parse_table_section(soup, 'balance-sheet')
        cf_df = self._parse_table_section(soup, 'cash-flow')
        ratios_df = self._parse_table_section(soup, 'ratios')
        quarters_df = self._parse_table_section(soup, 'quarters')
        shareholding_df = self._parse_table_section(soup, 'shareholding')

        # 4. About / Description
        about_div = soup.find('div', class_='about')
        about_text = about_div.text.strip() if about_div else ""

        return {
            'url': url,
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
        }

    def _parse_table_section(self, soup: BeautifulSoup, section_id: str) -> pd.DataFrame:
        """Parse an HTML table inside a section ID into a clean pandas DataFrame."""
        section = soup.find('section', id=section_id)
        if not section:
            return pd.DataFrame()
            
        table = section.find('table')
        if not table:
            return pd.DataFrame()
            
        # Extract headers (Fiscal Years)
        thead = table.find('thead')
        if not thead:
            return pd.DataFrame()
            
        headers = []
        for th in thead.find_all('th'):
            t = th.text.strip()
            if t:
                headers.append(t)
                
        # Extract rows
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
                
            # Align vals with headers length
            if len(vals) < len(headers):
                vals.extend([None] * (len(headers) - len(vals)))
            elif len(vals) > len(headers):
                vals = vals[:len(headers)]
                
            rows_data[row_label] = vals
            
        if not rows_data or not headers:
            return pd.DataFrame()
            
        df = pd.DataFrame(rows_data, index=headers).T
        return df
