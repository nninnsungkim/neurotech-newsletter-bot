"""
Broad industry news fetcher for APEX competitive intelligence.
Searches across the neurotech and productivity app landscape.
"""

import feedparser
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
from typing import List, Dict
import time
import re


class IndustryNewsFetcher:
    """Fetches broad industry news - neurotech + productivity."""

    BASE_URL = "https://news.google.com/rss/search"

    # BROAD industry searches
    QUERIES = [
        # Neurotech hardware - broad
        'EEG wearable',
        'EEG headband',
        'EEG consumer',
        'brain wearable',
        'brain-sensing',
        'neurofeedback device',
        'neurofeedback',
        'brain computer interface consumer',
        'BCI wearable',
        'neural wearable',
        'cognitive wearable',
        'brain monitoring device',
        'brainwave headband',
        'meditation headband',
        'focus headband',
        'attention tracking device',
        'neurotech startup',
        'neurotech funding',
        'neurotech launch',

        # Specific competitors
        'Muse headband',
        'Neurable',
        'Neurosity',
        'EMOTIV',
        'Apollo Neuro',
        'Dreem sleep',
        'Opal app',
        'Freedom app',

        # Productivity / digital wellness - broad
        'screen time app',
        'app blocker',
        'digital wellness app',
        'digital wellness startup',
        'phone addiction',
        'smartphone addiction solution',
        'focus app',
        'productivity app launch',
        'distraction blocker',
        'attention economy',
        'digital detox app',
        'dopamine detox',
        'social media addiction',
        'screen addiction',

        # Industry trends
        'wearable productivity',
        'cognitive enhancement technology',
        'brain health wearable',
        'mental wellness wearable',
        'focus technology',
        'attention technology startup',
    ]

    def __init__(self, hours: int = 12):
        self.hours = hours

    def _search_url(self, query: str) -> str:
        encoded = quote(query)
        return f"{self.BASE_URL}?q={encoded}+when:{self.hours}h&hl=en-US&gl=US&ceid=US:en"

    def _get_real_url(self, google_url: str) -> str:
        """Follow redirect to get actual URL."""
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
            'query': query
        }

    def fetch_query(self, query: str, max_results: int = 5) -> List[Dict]:
        url = self._search_url(query)
        articles = []
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_results]:
                article = self._parse_entry(entry, query)
                if article['title']:
                    articles.append(article)
            time.sleep(0.3)
        except Exception as e:
            print(f"  Error: {query[:30]}... - {e}")
        return articles

    def fetch_all(self) -> List[Dict]:
        print("Fetching industry news (broad)...")
        all_articles = []

        for query in self.QUERIES:
            articles = self.fetch_query(query, max_results=3)
            if articles:
                print(f"  {query}: {len(articles)}")
            all_articles.extend(articles)

        print(f"Total fetched: {len(all_articles)}")
        return all_articles


def fetch_all_news(hours: int = 12) -> List[Dict]:
    fetcher = IndustryNewsFetcher(hours)
    return fetcher.fetch_all()

def fetch_neurotech_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    return fetch_all_news(hours)

def fetch_productivity_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    return []
