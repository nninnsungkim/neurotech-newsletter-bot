"""
Tiered company news search.
Tier 1: Wearable Consumer/Medical + specific tech_tags (no limit)
Tier 2: Other neurotech companies (fill to 15 by views)
"""

import feedparser
import requests
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
from typing import List, Dict, Tuple
import time
import re


# Tier 1 filter criteria
TIER1_TYPES = ["Wearable Consumer", "Wearable Medical Device"]
TIER1_TECH_TAGS = ["wearable", "eeg", "neurofeedback", "tdcs", "tacs", "neurostimulation", "fnirs"]


def load_companies() -> List[Dict]:
    """Load companies from config."""
    config_path = Path(__file__).parent.parent / 'config' / 'companies.json'
    with open(config_path, 'r') as f:
        return json.load(f)


def is_tier1_company(company: Dict) -> bool:
    """Check if company matches Tier 1 criteria."""
    # Check type
    company_type = company.get('type', '').strip()
    if company_type in TIER1_TYPES:
        return True

    # Check tech_tags
    tech_tags = company.get('tech_tags', '').lower()
    for tag in TIER1_TECH_TAGS:
        if tag in tech_tags:
            return True

    return False


def split_companies() -> Tuple[List[Dict], List[Dict]]:
    """Split companies into Tier 1 and Tier 2."""
    companies = load_companies()
    tier1 = []
    tier2 = []

    for company in companies:
        if is_tier1_company(company):
            tier1.append(company)
        else:
            tier2.append(company)

    return tier1, tier2


class CompanyNewsSearch:
    """Search for company news using Google News RSS."""

    BASE_URL = "https://news.google.com/rss/search"

    def __init__(self, hours: int = 12):
        self.hours = hours
        self.seen_companies = set()  # Track companies we've found news for

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

    def _parse_entry(self, entry, company_name: str) -> Dict:
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
            'company': company_name,
            'fetcher': 'google_company'
        }

    def search_company(self, company: Dict) -> Dict:
        """Search for a single company. Returns 1 article or None."""
        name = company.get('name', '')
        if not name:
            return None

        # Skip if we already have news for this company
        if name in self.seen_companies:
            return None

        # Search with quoted company name + neurotech
        query = f'"{name}" neurotech'
        url = self._search_url(query)

        try:
            feed = feedparser.parse(url)
            if feed.entries:
                # Take only the first (best) result
                entry = feed.entries[0]
                article = self._parse_entry(entry, name)
                if article['title']:
                    self.seen_companies.add(name)
                    return article
            time.sleep(0.2)  # Rate limiting
        except:
            pass

        return None

    def search_tier1(self, companies: List[Dict]) -> List[Dict]:
        """Search all Tier 1 companies. No limit on results."""
        print(f"\n[TIER 1] Searching {len(companies)} priority companies...")
        articles = []

        for i, company in enumerate(companies):
            article = self.search_company(company)
            if article:
                print(f"  + {company['name']}: found")
                articles.append(article)

            # Progress indicator every 20 companies
            if (i + 1) % 20 == 0:
                print(f"  ... searched {i + 1}/{len(companies)}")

        print(f"Tier 1 results: {len(articles)} articles")
        return articles

    def search_tier2(self, companies: List[Dict], needed: int) -> List[Dict]:
        """Search Tier 2 companies until we have enough articles."""
        if needed <= 0:
            print("\n[TIER 2] Skipped (Tier 1 sufficient)")
            return []

        print(f"\n[TIER 2] Searching for {needed} more articles from {len(companies)} companies...")
        articles = []

        for i, company in enumerate(companies):
            if len(articles) >= needed:
                break

            article = self.search_company(company)
            if article:
                print(f"  + {company['name']}: found")
                articles.append(article)

            # Progress indicator every 50 companies
            if (i + 1) % 50 == 0:
                print(f"  ... searched {i + 1}/{len(companies)}, found {len(articles)}/{needed}")

        print(f"Tier 2 results: {len(articles)} articles")
        return articles


def fetch_tiered_news(hours: int = 12, min_total: int = 15) -> Tuple[List[Dict], List[Dict]]:
    """
    Fetch news using tiered approach.
    Returns (tier1_articles, tier2_articles)
    """
    tier1_companies, tier2_companies = split_companies()
    print(f"Companies: {len(tier1_companies)} Tier 1, {len(tier2_companies)} Tier 2")

    searcher = CompanyNewsSearch(hours)

    # Always search all Tier 1
    tier1_articles = searcher.search_tier1(tier1_companies)

    # Search Tier 2 only if needed
    needed = min_total - len(tier1_articles)
    tier2_articles = searcher.search_tier2(tier2_companies, needed)

    return tier1_articles, tier2_articles


def fetch_all_news(hours: int = 12) -> List[Dict]:
    """Fetch all news (for backwards compatibility)."""
    tier1, tier2 = fetch_tiered_news(hours)
    return tier1 + tier2
