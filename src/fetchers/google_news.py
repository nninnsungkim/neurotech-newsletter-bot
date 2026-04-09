"""
Company-focused fetcher using the 580 company database.
Tracks competitors and relevant industry players.
"""

import feedparser
import requests
import json
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote
from typing import List, Dict
import time
import re


def load_companies() -> List[Dict]:
    """Load companies from config."""
    config_path = Path(__file__).parent.parent / 'config' / 'companies.json'
    with open(config_path, 'r') as f:
        return json.load(f)


def get_relevant_companies() -> List[str]:
    """Get list of companies most relevant to APEX."""
    companies = load_companies()

    # Types most relevant to APEX
    relevant_types = [
        'Wearable Medical Device',
        'Wearable Consumer',
        'Software / AI Platform',
        'BCI Software / Platform',
        'Productivity App',
    ]

    relevant = []
    for c in companies:
        ctype = c.get('type', '')
        category = c.get('category', '')

        # Include if relevant type or productivity category
        if any(t in ctype for t in relevant_types) or category == 'productivity':
            relevant.append(c['name'])

    return relevant


class CompanyNewsFetcher:
    """Fetches news about specific companies + industry trends."""

    BASE_URL = "https://news.google.com/rss/search"

    # Top priority competitors (always search)
    PRIORITY_COMPANIES = [
        'Opal', 'Muse', 'Neurable', 'Neurosity', 'Freedom',
        'EMOTIV', 'Apollo Neuro', 'Dreem', 'BrainCo',
        'Arctop', 'Flow Neuroscience', 'Elemind',
    ]

    # Industry trend searches
    INDUSTRY_QUERIES = [
        'EEG wearable',
        'EEG headband',
        'neurofeedback device',
        'brain wearable',
        'brain-sensing',
        'consumer BCI',
        'neurotech startup',
        'neurotech funding',
        'screen time app',
        'app blocker',
        'digital wellness app',
        'focus app',
        'productivity app launch',
        'phone addiction app',
        'cognitive wearable',
        'attention tracking',
        'brain health wearable',
        'mental wellness wearable',
    ]

    def __init__(self, hours: int = 12):
        self.hours = hours
        self.all_companies = get_relevant_companies()
        print(f"Loaded {len(self.all_companies)} relevant companies")

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

        raw_summary = entry.get('summary', '')
        clean_summary = re.sub(r'<[^>]+>', '', raw_summary)
        clean_summary = re.sub(r'\s+', ' ', clean_summary).strip()[:300]

        return {
            'title': title.strip(),
            'url': actual_url,
            'source': source.strip(),
            'published': pub_date,
            'summary': clean_summary,
            'query': query,
            'fetcher': 'google_news'
        }

    def fetch_query(self, query: str, max_results: int = 3) -> List[Dict]:
        url = self._search_url(query)
        articles = []
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_results]:
                article = self._parse_entry(entry, query)
                if article['title']:
                    articles.append(article)
            time.sleep(0.2)
        except Exception as e:
            pass
        return articles

    def fetch_priority_companies(self) -> List[Dict]:
        """Search for priority competitors."""
        print("Searching priority competitors...")
        articles = []
        for company in self.PRIORITY_COMPANIES:
            results = self.fetch_query(f'"{company}"', max_results=3)
            if results:
                print(f"  {company}: {len(results)}")
            articles.extend(results)
        return articles

    def fetch_sample_companies(self, sample_size: int = 30) -> List[Dict]:
        """Search a rotating sample of other relevant companies."""
        print(f"Searching {sample_size} other companies...")

        # Exclude priority companies
        other_companies = [c for c in self.all_companies if c not in self.PRIORITY_COMPANIES]

        # Rotate based on hour to get different companies each run
        hour = datetime.now().hour
        start_idx = (hour * sample_size) % len(other_companies)
        sample = other_companies[start_idx:start_idx + sample_size]

        articles = []
        for company in sample:
            results = self.fetch_query(f'"{company}"', max_results=2)
            if results:
                print(f"  {company}: {len(results)}")
            articles.extend(results)

        return articles

    def fetch_industry_trends(self) -> List[Dict]:
        """Search industry trend keywords."""
        print("Searching industry trends...")
        articles = []
        for query in self.INDUSTRY_QUERIES:
            results = self.fetch_query(query, max_results=3)
            if results:
                print(f"  {query}: {len(results)}")
            articles.extend(results)
        return articles

    def fetch_all(self) -> List[Dict]:
        """Fetch from all sources."""
        all_articles = []

        # Priority competitors (always)
        all_articles.extend(self.fetch_priority_companies())

        # Sample of other companies (rotates)
        all_articles.extend(self.fetch_sample_companies(sample_size=20))

        # Industry trends
        all_articles.extend(self.fetch_industry_trends())

        print(f"Total fetched: {len(all_articles)}")
        return all_articles


def fetch_all_news(hours: int = 12) -> List[Dict]:
    """Main fetch function."""
    fetcher = CompanyNewsFetcher(hours)
    return fetcher.fetch_all()


def fetch_neurotech_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    return fetch_all_news(hours)


def fetch_productivity_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    return []
