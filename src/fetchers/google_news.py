"""
Focused Google News fetcher - ONLY competitor-specific searches.
"""

import feedparser
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
from typing import List, Dict
import time
import re


class CompetitorFetcher:
    """Fetches news ONLY about specific competitors and products."""

    BASE_URL = "https://news.google.com/rss/search"

    # EXACT search queries for competitors
    QUERIES = [
        # Primary competitors - EXACT MATCH
        '"Opal app" OR "Opal screen time"',
        '"Muse headband" OR "Muse S headband" OR "Muse 2 headband"',
        '"Interaxon" muse',
        '"Neurable" headphones OR "Neurable" EEG',
        '"Freedom app" blocker',

        # Secondary competitors
        '"Neurosity Crown" OR "Neurosity" brain',
        '"EMOTIV" headset OR "EMOTIV" EEG',
        '"Apollo Neuro" wearable',
        '"Dreem" headband sleep',
        '"Flow Neuroscience" depression',
        '"Cold Turkey" blocker',
        '"One Sec" app addiction',

        # Product category searches
        '"EEG headband" launch OR funding OR release',
        '"neurofeedback headband" OR "neurofeedback device"',
        '"screen time app" launch OR funding',
        '"focus wearable" OR "productivity wearable"',
        '"digital wellness" app launch',
    ]

    def __init__(self, hours: int = 12):
        self.hours = hours

    def _search_url(self, query: str) -> str:
        """Build search URL."""
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
        """Parse RSS entry to article dict."""
        title = entry.get('title', '')
        # Remove source suffix
        if ' - ' in title:
            parts = title.rsplit(' - ', 1)
            title = parts[0]
            source = parts[1] if len(parts) > 1 else 'Unknown'
        else:
            source = 'Unknown'

        google_url = entry.get('link', '')
        actual_url = self._get_real_url(google_url)

        # Get publish date
        try:
            from dateutil import parser
            pub_date = parser.parse(entry.get('published', '')).isoformat()
        except:
            pub_date = datetime.utcnow().isoformat()

        # Clean summary - just extract text, no HTML
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
        """Fetch results for one query."""
        url = self._search_url(query)
        articles = []

        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_results]:
                article = self._parse_entry(entry, query)
                if article['title']:
                    articles.append(article)
            time.sleep(0.5)
        except Exception as e:
            print(f"  Error: {query[:40]}... - {e}")

        return articles

    def fetch_all(self) -> List[Dict]:
        """Fetch from all queries."""
        print("Fetching competitor news...")
        all_articles = []

        for query in self.QUERIES:
            articles = self.fetch_query(query, max_results=3)
            if articles:
                print(f"  {query[:50]}...: {len(articles)}")
            all_articles.extend(articles)

        print(f"Total fetched: {len(all_articles)}")
        return all_articles


def fetch_all_news(hours: int = 12) -> List[Dict]:
    """Main fetch function."""
    fetcher = CompetitorFetcher(hours)
    return fetcher.fetch_all()


# Compatibility
def fetch_neurotech_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    return fetch_all_news(hours)


def fetch_productivity_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    return []  # Already included in fetch_all_news
