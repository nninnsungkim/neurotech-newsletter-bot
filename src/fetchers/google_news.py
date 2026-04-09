"""
Google News RSS fetcher for neurotech and productivity news.
Uses Google News RSS feeds which are free and don't require API keys.
"""

import feedparser
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
from typing import List, Dict
import time
import re


class GoogleNewsFetcher:
    """Fetches news from Google News RSS feeds."""

    BASE_URL = "https://news.google.com/rss/search"

    def __init__(self, hours_lookback: int = 12):
        self.hours_lookback = hours_lookback
        self.cutoff_time = datetime.utcnow() - timedelta(hours=hours_lookback)

    def _build_url(self, query: str, when: str = "12h") -> str:
        """Build Google News RSS URL with query."""
        encoded_query = quote(query)
        return f"{self.BASE_URL}?q={encoded_query}+when:{when}&hl=en-US&gl=US&ceid=US:en"

    def _parse_date(self, date_str: str) -> datetime:
        """Parse RSS date string to datetime."""
        try:
            from dateutil import parser
            return parser.parse(date_str, ignoretz=True)
        except:
            return datetime.utcnow()

    def _clean_title(self, title: str) -> str:
        """Remove source suffix from title (e.g., ' - TechCrunch')."""
        parts = title.rsplit(' - ', 1)
        return parts[0].strip()

    def _extract_source(self, title: str) -> str:
        """Extract source name from title."""
        parts = title.rsplit(' - ', 1)
        if len(parts) > 1:
            return parts[1].strip()
        return "Unknown"

    def _is_within_timeframe(self, pub_date: datetime) -> bool:
        """Check if article is within the lookback period."""
        return pub_date >= self.cutoff_time

    def fetch_for_query(self, query: str, max_results: int = 10) -> List[Dict]:
        """Fetch news articles for a single query."""
        url = self._build_url(query)
        articles = []

        try:
            feed = feedparser.parse(url)

            for entry in feed.entries[:max_results * 2]:  # Fetch extra, filter later
                pub_date = self._parse_date(entry.get('published', ''))

                if not self._is_within_timeframe(pub_date):
                    continue

                # Extract the actual article URL (not Google redirect)
                link = entry.get('link', '')

                article = {
                    'title': self._clean_title(entry.get('title', '')),
                    'url': link,
                    'source': self._extract_source(entry.get('title', '')),
                    'published': pub_date.isoformat(),
                    'summary': entry.get('summary', ''),
                    'query': query,
                    'fetcher': 'google_news'
                }
                articles.append(article)

                if len(articles) >= max_results:
                    break

            # Rate limiting
            time.sleep(0.5)

        except Exception as e:
            print(f"Error fetching Google News for '{query}': {e}")

        return articles

    def fetch_for_queries(self, queries: List[str], max_per_query: int = 5) -> List[Dict]:
        """Fetch news for multiple queries."""
        all_articles = []

        for query in queries:
            articles = self.fetch_for_query(query, max_per_query)
            all_articles.extend(articles)
            print(f"  - '{query}': {len(articles)} articles")

        return all_articles

    def fetch_for_company(self, company_name: str, max_results: int = 3) -> List[Dict]:
        """Fetch news specifically about a company."""
        # Try multiple query variations
        queries = [
            f'"{company_name}"',
            f'{company_name} news',
            f'{company_name} announcement'
        ]

        articles = []
        for query in queries:
            results = self.fetch_for_query(query, max_results=2)
            articles.extend(results)
            if len(articles) >= max_results:
                break

        return articles[:max_results]


def fetch_neurotech_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    """Main function to fetch neurotech news."""
    fetcher = GoogleNewsFetcher(hours_lookback=hours)

    print("Fetching neurotech news from Google News...")

    # Combine all neurotech keywords
    queries = (
        keywords_config['neurotech']['primary'][:8] +  # Top primary keywords
        keywords_config['neurotech']['companies'][:15] +  # Top companies
        keywords_config['neurotech']['topics'][:5]  # Top topics
    )

    articles = fetcher.fetch_for_queries(queries, max_per_query=3)
    print(f"Total neurotech articles: {len(articles)}")

    return articles


def fetch_productivity_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    """Main function to fetch productivity app news."""
    fetcher = GoogleNewsFetcher(hours_lookback=hours)

    print("Fetching productivity news from Google News...")

    queries = (
        keywords_config['productivity']['primary'][:5] +
        keywords_config['productivity']['companies']
    )

    articles = fetcher.fetch_for_queries(queries, max_per_query=3)
    print(f"Total productivity articles: {len(articles)}")

    return articles
