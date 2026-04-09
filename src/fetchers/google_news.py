"""
Google News fetcher focused on APEX competitive intelligence.
Searches for specific competitors and relevant business news.
"""

import feedparser
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
from typing import List, Dict
import time
import re


def extract_real_url(google_url: str) -> str:
    """Extract actual article URL from Google News redirect."""
    if not google_url or 'news.google.com' not in google_url:
        return google_url

    try:
        # Follow redirect to get actual URL
        response = requests.get(
            google_url,
            allow_redirects=True,
            timeout=10,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        final_url = response.url

        # Make sure we got a real URL, not Google
        if final_url and 'google.com' not in final_url:
            return final_url
    except Exception as e:
        pass

    # Fallback: return original (will show Google URL)
    return google_url


class CompetitorNewsFetcher:
    """Fetches news specifically about APEX competitors and relevant topics."""

    BASE_URL = "https://news.google.com/rss/search"

    # Direct competitor searches - these are PRIORITY
    COMPETITOR_QUERIES = [
        # Primary competitors
        '"Opal" screen time app',
        '"Opal" app productivity',
        '"Muse headband"',
        '"Muse S" meditation',
        '"Interaxon" Muse',
        '"Neurable" headphones',
        '"Neurable" EEG',
        '"Freedom" app blocker',
        # Secondary competitors
        '"Neurosity" Crown',
        '"EMOTIV" headset',
        '"Apollo Neuro"',
        '"Dreem" headband sleep',
        '"Cold Turkey" blocker',
        '"One Sec" app',
    ]

    # Topic searches for industry news
    TOPIC_QUERIES = [
        'EEG headband consumer',
        'EEG wearable productivity',
        'neurofeedback device launch',
        'brain sensing wearable',
        'focus tracking wearable',
        'screen time app funding',
        'digital wellness app launch',
        'productivity wearable startup',
        'attention tracking technology',
    ]

    def __init__(self, hours_lookback: int = 12):
        self.hours_lookback = hours_lookback
        self.cutoff_time = datetime.utcnow() - timedelta(hours=hours_lookback)

    def _build_url(self, query: str, when: str = "12h") -> str:
        """Build Google News RSS URL."""
        encoded = quote(query)
        return f"{self.BASE_URL}?q={encoded}+when:{when}&hl=en-US&gl=US&ceid=US:en"

    def _parse_date(self, date_str: str) -> datetime:
        """Parse RSS date."""
        try:
            from dateutil import parser
            return parser.parse(date_str, ignoretz=True)
        except:
            return datetime.utcnow()

    def _clean_title(self, title: str) -> str:
        """Remove source from title."""
        parts = title.rsplit(' - ', 1)
        return parts[0].strip()

    def _extract_source(self, title: str) -> str:
        """Extract source name."""
        parts = title.rsplit(' - ', 1)
        return parts[1].strip() if len(parts) > 1 else "Unknown"

    def _clean_summary(self, summary: str) -> str:
        """Clean HTML from summary."""
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', summary)
        # Remove extra whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean[:500]

    def fetch_query(self, query: str, max_results: int = 5) -> List[Dict]:
        """Fetch articles for a query."""
        when = f"{self.hours_lookback}h"
        url = self._build_url(query, when)
        articles = []

        try:
            feed = feedparser.parse(url)

            for entry in feed.entries[:max_results]:
                pub_date = self._parse_date(entry.get('published', ''))

                # Get actual URL
                google_url = entry.get('link', '')
                actual_url = extract_real_url(google_url)

                article = {
                    'title': self._clean_title(entry.get('title', '')),
                    'url': actual_url,
                    'source': self._extract_source(entry.get('title', '')),
                    'published': pub_date.isoformat(),
                    'summary': self._clean_summary(entry.get('summary', '')),
                    'query': query,
                    'fetcher': 'google_news'
                }
                articles.append(article)

            time.sleep(0.3)  # Rate limit

        except Exception as e:
            print(f"  Error fetching '{query}': {e}")

        return articles

    def fetch_competitor_news(self) -> List[Dict]:
        """Fetch news about direct competitors."""
        print("Fetching competitor news...")
        all_articles = []

        for query in self.COMPETITOR_QUERIES:
            articles = self.fetch_query(query, max_results=3)
            if articles:
                print(f"  {query}: {len(articles)}")
            all_articles.extend(articles)

        return all_articles

    def fetch_topic_news(self) -> List[Dict]:
        """Fetch news about relevant topics."""
        print("Fetching topic news...")
        all_articles = []

        for query in self.TOPIC_QUERIES:
            articles = self.fetch_query(query, max_results=3)
            if articles:
                print(f"  {query}: {len(articles)}")
            all_articles.extend(articles)

        return all_articles


def fetch_all_news(hours: int = 12) -> List[Dict]:
    """Main function to fetch all relevant news."""
    fetcher = CompetitorNewsFetcher(hours_lookback=hours)

    # Fetch competitor news (priority)
    competitor_articles = fetcher.fetch_competitor_news()

    # Fetch topic news
    topic_articles = fetcher.fetch_topic_news()

    all_articles = competitor_articles + topic_articles
    print(f"Total fetched: {len(all_articles)}")

    return all_articles


# Keep old function names for compatibility
def fetch_neurotech_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    """Fetch neurotech news (uses new focused fetcher)."""
    fetcher = CompetitorNewsFetcher(hours_lookback=hours)
    return fetcher.fetch_competitor_news()


def fetch_productivity_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    """Fetch productivity news (uses new focused fetcher)."""
    fetcher = CompetitorNewsFetcher(hours_lookback=hours)
    return fetcher.fetch_topic_news()
