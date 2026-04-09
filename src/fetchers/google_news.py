"""
Exact company news search - NO generic keywords.
Uses site-specific searches and exact company names.
"""

import feedparser
import requests
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
from typing import List, Dict
import time
import re


def load_companies() -> List[Dict]:
    """Load companies from config."""
    config_path = Path(__file__).parent.parent / 'config' / 'companies.json'
    with open(config_path, 'r') as f:
        return json.load(f)


class ExactCompanySearch:
    """Search for exact company news only."""

    BASE_URL = "https://news.google.com/rss/search"

    # Primary competitors - use EXACT company/parent names
    PRIMARY_SEARCHES = [
        # Opal - exact
        '"Opal" "screen time"',
        '"Opal" app productivity',

        # Muse - use parent company name to avoid confusion
        '"Interaxon"',
        '"Muse S" headband',
        '"Muse 2" meditation',

        # Neurable - exact
        '"Neurable" headphones',
        '"Neurable Inc"',

        # Neurosity - exact
        '"Neurosity" Crown',
        '"Neurosity Inc"',

        # Freedom - exact
        '"Freedom.to" app',
        '"Freedom app" blocker',

        # Other specific companies
        '"EMOTIV" EEG headset',
        '"Apollo Neuroscience"',
        '"Dreem" headband',
        '"Flow Neuroscience"',
        '"BrainCo"',
        '"Kernel" neuroscience -popcorn -linux',
    ]

    def __init__(self, hours: int = 12):
        self.hours = hours

    def _search_url(self, query: str) -> str:
        encoded = quote(query)
        return f"{self.BASE_URL}?q={encoded}+when:{self.hours}h&hl=en-US&gl=US&ceid=US:en"

    def _get_real_url(self, google_url: str) -> str:
        """Follow redirect to actual URL."""
        if 'news.google.com' not in google_url:
            return google_url
        try:
            resp = requests.get(
                google_url,
                allow_redirects=True,
                timeout=10,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
            )
            if resp.url and 'google.com' not in resp.url:
                return resp.url
        except:
            pass
        return google_url

    def _parse_entry(self, entry, query: str) -> Dict:
        title = entry.get('title', '')
        if ' - ' in title:
            parts = title.rsplit(' - ', 1)
            title = parts[0]
            source = parts[1] if len(parts) > 1 else 'Unknown'
        else:
            source = 'Unknown'

        google_url = entry.get('link', '')
        actual_url = self._get_real_url(google_url)

        try:
            from dateutil import parser
            pub_date = parser.parse(entry.get('published', '')).isoformat()
        except:
            pub_date = datetime.utcnow().isoformat()

        return {
            'title': title.strip(),
            'url': actual_url,
            'source': source.strip(),
            'published': pub_date,
            'query': query,
            'fetcher': 'google_exact'
        }

    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """Search for exact query."""
        url = self._search_url(query)
        articles = []
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_results]:
                article = self._parse_entry(entry, query)
                if article['title']:
                    articles.append(article)
            time.sleep(0.3)
        except:
            pass
        return articles

    def search_all(self) -> List[Dict]:
        """Search all primary companies."""
        print("Searching exact company news...")
        all_articles = []

        for query in self.PRIMARY_SEARCHES:
            articles = self.search(query, max_results=2)
            if articles:
                print(f"  {query[:40]}: {len(articles)}")
            all_articles.extend(articles)

        print(f"Total from exact search: {len(all_articles)}")
        return all_articles


def fetch_all_news(hours: int = 12) -> List[Dict]:
    """Fetch exact company news."""
    searcher = ExactCompanySearch(hours)
    return searcher.search_all()


def fetch_neurotech_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    return fetch_all_news(hours)


def fetch_productivity_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    return []
