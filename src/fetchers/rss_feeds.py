"""
RSS feed fetcher for company blogs and tech publications.
"""

import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


# Known RSS feeds for neurotech and tech publications
PUBLICATION_FEEDS = {
    # Tech Publications
    'TechCrunch': 'https://techcrunch.com/feed/',
    'Wired': 'https://www.wired.com/feed/rss',
    'MIT Tech Review': 'https://www.technologyreview.com/feed/',
    'The Verge': 'https://www.theverge.com/rss/index.xml',
    'Ars Technica': 'https://feeds.arstechnica.com/arstechnica/technology-lab',
    'IEEE Spectrum': 'https://spectrum.ieee.org/feeds/feed.rss',
    'VentureBeat': 'https://venturebeat.com/feed/',

    # Neuroscience/Health Tech
    'Neuroscience News': 'https://neurosciencenews.com/feed/',
    'MedGadget': 'https://www.medgadget.com/feed',
    'MobiHealthNews': 'https://www.mobihealthnews.com/feed',
}

# Company blog RSS feeds (discovered or known)
COMPANY_BLOG_FEEDS = {
    'Muse': 'https://choosemuse.com/blog/feed/',
    'Neurable': 'https://neurable.com/blog/feed',
    'EMOTIV': 'https://www.emotiv.com/blog/feed/',
    'OpenBCI': 'https://openbci.com/community/feed/',
    'Apollo Neuro': 'https://apolloneuro.com/blogs/news.atom',
    'Flow Neuroscience': 'https://flowneuroscience.com/blog/feed/',
    'Opal': 'https://www.opal.so/blog/rss.xml',
}


class RSSFetcher:
    """Fetches and parses RSS feeds."""

    def __init__(self, hours_lookback: int = 12):
        self.hours_lookback = hours_lookback
        self.cutoff_time = datetime.utcnow() - timedelta(hours=hours_lookback)

    def _parse_date(self, entry) -> datetime:
        """Parse date from RSS entry."""
        try:
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                return datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                return datetime(*entry.updated_parsed[:6])
            else:
                from dateutil import parser
                date_str = entry.get('published', entry.get('updated', ''))
                return parser.parse(date_str, ignoretz=True)
        except:
            return datetime.utcnow() - timedelta(days=1)  # Default to yesterday

    def _is_relevant(self, title: str, summary: str, keywords: List[str]) -> bool:
        """Check if article is relevant to neurotech/productivity."""
        text = (title + ' ' + summary).lower()

        relevance_keywords = [
            'neuro', 'brain', 'eeg', 'bci', 'neural', 'cognitive',
            'focus', 'attention', 'meditation', 'mindfulness',
            'wearable', 'headband', 'productivity', 'screen time',
            'digital wellness', 'app blocker', 'distraction'
        ]

        return any(kw in text for kw in relevance_keywords + [k.lower() for k in keywords])

    def fetch_feed(self, name: str, url: str, relevance_keywords: List[str] = None) -> List[Dict]:
        """Fetch articles from a single RSS feed."""
        articles = []
        relevance_keywords = relevance_keywords or []

        try:
            feed = feedparser.parse(url)

            for entry in feed.entries[:20]:  # Check last 20 entries
                pub_date = self._parse_date(entry)

                # Skip old articles
                if pub_date < self.cutoff_time:
                    continue

                title = entry.get('title', '')
                summary = entry.get('summary', entry.get('description', ''))

                # For publication feeds, check relevance
                if name in PUBLICATION_FEEDS:
                    if not self._is_relevant(title, summary, relevance_keywords):
                        continue

                article = {
                    'title': title,
                    'url': entry.get('link', ''),
                    'source': name,
                    'published': pub_date.isoformat(),
                    'summary': summary[:500] if summary else '',
                    'fetcher': 'rss'
                }
                articles.append(article)

        except Exception as e:
            print(f"  Error fetching RSS from {name}: {e}")

        return articles

    def fetch_all_feeds(self, relevance_keywords: List[str] = None) -> List[Dict]:
        """Fetch from all configured RSS feeds in parallel."""
        all_articles = []
        all_feeds = {**PUBLICATION_FEEDS, **COMPANY_BLOG_FEEDS}

        print(f"Fetching from {len(all_feeds)} RSS feeds...")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.fetch_feed, name, url, relevance_keywords): name
                for name, url in all_feeds.items()
            }

            for future in as_completed(futures):
                name = futures[future]
                try:
                    articles = future.result()
                    if articles:
                        print(f"  - {name}: {len(articles)} articles")
                        all_articles.extend(articles)
                except Exception as e:
                    print(f"  - {name}: Error - {e}")

        print(f"Total RSS articles: {len(all_articles)}")
        return all_articles


def fetch_rss_news(keywords_config: Dict, hours: int = 12) -> List[Dict]:
    """Main function to fetch RSS news."""
    fetcher = RSSFetcher(hours_lookback=hours)

    # Build relevance keywords from config
    relevance_keywords = (
        keywords_config.get('neurotech', {}).get('primary', []) +
        keywords_config.get('neurotech', {}).get('companies', []) +
        keywords_config.get('productivity', {}).get('companies', [])
    )

    return fetcher.fetch_all_feeds(relevance_keywords)
