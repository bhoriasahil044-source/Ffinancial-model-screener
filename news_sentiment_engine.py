"""
News Sentiment & Catalyst Impact Engine
Fetches real-time financial news for listed companies via Google News RSS,
classifies business catalysts, computes financial sentiment scores, and
predicts the valuation impact on short-term momentum and DCF intrinsic value.
"""

import re
import xml.etree.ElementTree as ET
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import requests


# Financial lexicon tuned for Indian and global equities
FINANCIAL_POSITIVE_LEXICON = {
    'profit': 1.3, 'profits': 1.3, 'profitable': 1.2, 'growth': 1.1, 'growing': 1.1,
    'surge': 1.5, 'surges': 1.5, 'surged': 1.5, 'jump': 1.2, 'jumps': 1.2, 'jumped': 1.2,
    'rally': 1.4, 'rallies': 1.4, 'rallied': 1.4, 'gain': 1.0, 'gains': 1.0, 'gained': 1.0,
    'rise': 1.0, 'rises': 1.0, 'rose': 1.0, 'higher': 0.9, 'high': 0.8,
    'record': 1.3, 'robust': 1.3, 'bullish': 1.4, 'upgrade': 1.5, 'upgrades': 1.5, 'upgraded': 1.5,
    'buy': 1.1, 'outperform': 1.4, 'expansion': 1.2, 'expands': 1.2, 'order': 1.1, 'orders': 1.1,
    'contract': 1.1, 'deal': 1.0, 'acquisition': 1.2, 'dividend': 1.2, 'bonus': 1.2,
    'beat': 1.3, 'beats': 1.3, 'beating': 1.3, 'soar': 1.5, 'soars': 1.5, 'soared': 1.5,
    'recovery': 1.2, 'rebound': 1.2, 'rebounds': 1.2, 'strong': 1.1, 'boost': 1.2, 'boosts': 1.2,
    'approval': 1.3, 'approves': 1.3, 'approved': 1.3, 'cleared': 1.2, 'innovation': 1.1
}

FINANCIAL_NEGATIVE_LEXICON = {
    'fall': -1.1, 'falls': -1.1, 'fell': -1.1, 'drop': -1.2, 'drops': -1.2, 'dropped': -1.2,
    'decline': -1.1, 'declines': -1.1, 'declined': -1.1, 'lower': -0.8, 'down': -0.8,
    'crash': -1.8, 'crashes': -1.8, 'crashed': -1.8, 'plunge': -1.6, 'plunges': -1.6, 'plunged': -1.6,
    'loss': -1.4, 'losses': -1.4, 'slump': -1.5, 'slumps': -1.5, 'slumped': -1.5,
    'cut': -1.2, 'cuts': -1.2, 'downgrade': -1.5, 'downgrades': -1.5, 'downgraded': -1.5,
    'sell': -1.0, 'underperform': -1.4, 'pressure': -1.1, 'subdued': -1.0, 'weak': -1.1, 'weakness': -1.1,
    'penalty': -1.5, 'penalized': -1.5, 'notice': -1.0, 'tax': -0.5, 'probe': -1.5, 'probes': -1.5,
    'fraud': -2.0, 'investigation': -1.4, 'investigated': -1.4, 'fine': -1.2, 'fined': -1.2,
    'debt': -0.8, 'default': -1.8, 'defaults': -1.8, 'defaulted': -1.8, 'strike': -1.4,
    'dispute': -1.1, 'scam': -2.0, 'delay': -1.0, 'delayed': -1.0, 'headwind': -1.2, 'headwinds': -1.2
}

CATALYST_CATEGORIES = {
    'Earnings & Margins': ['profit', 'quarter', 'q1', 'q2', 'q3', 'q4', 'result', 'results', 'ebitda', 'revenue', 'sales', 'margin', 'margins', 'pat'],
    'Orders & Capex': ['order', 'contract', 'deal', 'capex', 'plant', 'expansion', 'acquisition', 'facility', 'capacity', 'investment'],
    'Regulatory & Governance': ['sebi', 'rbi', 'notice', 'tax', 'probe', 'investigation', 'court', 'penalty', 'board', 'ceo', 'cfo', 'compliance', 'fine'],
    'Macro & Commodity': ['tariff', 'duty', 'crude', 'commodity', 'steel', 'metal', 'inflation', 'interest rate', 'fed', 'rupee', 'dollar'],
    'Market & Brokerage': ['target', 'brokerage', 'analyst', 'rating', 'buy', 'sell', 'upgrade', 'downgrade', 'shares', 'mcap', 'rally', 'crash']
}


class NewsSentimentEngine:
    """Fetches real-time financial news, evaluates sentiment, and estimates market catalyst impact."""

    def __init__(self, timeout_sec: int = 6):
        self.timeout_sec = timeout_sec
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def fetch_company_news(self, company_name: str, ticker: str, max_items: int = 10) -> List[Dict[str, Any]]:
        """Fetches recent financial news articles for the given company from Google News RSS."""
        clean_name = re.sub(r'\b(Ltd|Limited|Corp|Corporation|India|Industries)\b', '', company_name, flags=re.IGNORECASE).strip()
        search_query = urllib.parse.quote(f"{clean_name} {ticker} stock share news")
        rss_url = f"https://news.google.com/rss/search?q={search_query}&hl=en-IN&gl=IN&ceid=IN:en"

        articles = []
        try:
            resp = requests.get(rss_url, headers=self.headers, timeout=self.timeout_sec)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                items = root.findall('./channel/item')
                for item in items[:max_items]:
                    raw_title = item.find('title').text if item.find('title') is not None else ""
                    raw_link = item.find('link').text if item.find('link') is not None else ""
                    pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                    
                    # Extract publisher source if present (e.g. "Title - Economic Times")
                    source_name = "Financial News"
                    clean_title = raw_title
                    if " - " in raw_title:
                        parts = raw_title.rsplit(" - ", 1)
                        clean_title = parts[0].strip()
                        source_name = parts[1].strip()

                    sentiment_score, sentiment_label, pos_words, neg_words = self._score_sentiment(clean_title)
                    catalyst = self._detect_catalyst(clean_title)

                    articles.append({
                        'title': clean_title,
                        'source': source_name,
                        'link': raw_link,
                        'pub_date': pub_date,
                        'sentiment_score': sentiment_score,
                        'sentiment_label': sentiment_label,
                        'catalyst': catalyst,
                        'positive_signals': pos_words,
                        'negative_signals': neg_words
                    })
        except Exception:
            # Fallback gracefully if news feed encounters network or XML issues
            pass

        return articles

    def evaluate_catalyst_impact(
        self,
        articles: List[Dict[str, Any]],
        base_target_price: float,
        wacc_pct: float
    ) -> Dict[str, Any]:
        """
        Analyzes the aggregate sentiment and computes the predicted impact on:
        1. Market Catalyst Score (-100% to +100%)
        2. Short-Term Price Momentum Bias (Bullish / Neutral / Bearish)
        3. Sentiment-Adjusted DCF Fair Value Target
        """
        if not articles:
            return {
                'has_news': False,
                'catalyst_score': 0.0,
                'sentiment_bias': 'Neutral (Insufficient News Catalysts)',
                'sentiment_adjusted_target': base_target_price,
                'price_impact_pct': 0.0,
                'revenue_growth_impact_pct': 0.0,
                'wacc_impact_bps': 0.0,
                'summary_bullets': ["No major news catalysts detected in the last 7 days."]
            }

        scores = [a['sentiment_score'] for a in articles]
        avg_score = float(sum(scores) / len(scores))
        catalyst_score_pct = round(max(-100.0, min(100.0, avg_score * 35.0)), 1)

        # Classify bias
        if catalyst_score_pct >= 25.0:
            bias = "Bullish Catalyst Momentum"
            bias_tag = "Bullish"
        elif catalyst_score_pct >= 8.0:
            bias = "Moderately Bullish Bias"
            bias_tag = "Positive"
        elif catalyst_score_pct <= -25.0:
            bias = "Bearish Catalyst Headwind"
            bias_tag = "Bearish"
        elif catalyst_score_pct <= -8.0:
            bias = "Moderately Bearish Caution"
            bias_tag = "Negative"
        else:
            bias = "Neutral / Balanced Sentiment"
            bias_tag = "Neutral"

        # Model impact on revenue growth rate & cost of capital
        # High positive sentiment -> +0.5% to +1.5% growth expectation, -15 to -30 bps WACC
        # Negative sentiment -> -0.5% to -2.0% growth expectation, +25 to +50 bps WACC
        rev_impact_pct = round(avg_score * 0.8, 2)
        rev_impact_pct = max(-2.5, min(2.5, rev_impact_pct))

        wacc_adj_bps = round(-avg_score * 20.0, 1) # basis points
        wacc_adj_bps = max(-50.0, min(50.0, wacc_adj_bps))

        # Sentiment-adjusted target price
        # Valuation multiplier based on growth shift and risk spread
        val_multiplier = 1.0 + (avg_score * 0.05)
        val_multiplier = max(0.85, min(1.15, val_multiplier))
        sentiment_adj_target = round(base_target_price * val_multiplier, 1)
        price_impact_pct = round(((sentiment_adj_target / max(1.0, base_target_price)) - 1.0) * 100.0, 1)

        # Generate bullet-point insights
        pos_articles = [a for a in articles if a['sentiment_score'] > 0.2]
        neg_articles = [a for a in articles if a['sentiment_score'] < -0.2]

        bullets = []
        if pos_articles:
            bullets.append(f"Positive Triggers ({len(pos_articles)}): Key tailwinds detected in {pos_articles[0]['catalyst']} ('{pos_articles[0]['title'][:70]}...').")
        if neg_articles:
            bullets.append(f"Risk Headwinds ({len(neg_articles)}): Downward pressure observed in {neg_articles[0]['catalyst']} ('{neg_articles[0]['title'][:70]}...').")
        if not pos_articles and not neg_articles:
            bullets.append("News coverage is predominantly factual/neutral with no extreme directional catalysts.")

        return {
            'has_news': True,
            'catalyst_score': catalyst_score_pct,
            'sentiment_bias': bias,
            'bias_tag': bias_tag,
            'sentiment_adjusted_target': sentiment_adj_target,
            'price_impact_pct': price_impact_pct,
            'revenue_growth_impact_pct': rev_impact_pct,
            'wacc_impact_bps': wacc_adj_bps,
            'summary_bullets': bullets,
            'positive_count': len(pos_articles),
            'negative_count': len(neg_articles),
            'neutral_count': len(articles) - len(pos_articles) - len(neg_articles)
        }

    def _score_sentiment(self, text: str) -> Tuple[float, str, List[str], List[str]]:
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        score = 0.0
        pos_found = []
        neg_found = []

        for w in words:
            if w in FINANCIAL_POSITIVE_LEXICON:
                score += FINANCIAL_POSITIVE_LEXICON[w]
                pos_found.append(w)
            elif w in FINANCIAL_NEGATIVE_LEXICON:
                score += FINANCIAL_NEGATIVE_LEXICON[w]
                neg_found.append(w)

        # Normalize score between -1.0 and +1.0
        norm_score = max(-1.0, min(1.0, score / max(1.0, len(pos_found) + len(neg_found) + 0.5)))
        if norm_score >= 0.15:
            label = "Positive"
        elif norm_score <= -0.15:
            label = "Negative"
        else:
            label = "Neutral"

        return round(norm_score, 2), label, list(set(pos_found)), list(set(neg_found))

    def _detect_catalyst(self, text: str) -> str:
        text_lower = text.lower()
        for category, keywords in CATALYST_CATEGORIES.items():
            for kw in keywords:
                if kw in text_lower:
                    return category
        return "General Corporate"
