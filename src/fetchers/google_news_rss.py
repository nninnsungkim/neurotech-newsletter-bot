"""
Google News RSS fetcher with batch rotation.
- 201 Tier 1 companies split into 3 batches (~67 each)
- Each batch searched daily with 3-day lookback
- Free, no API key required
"""

import feedparser
import requests
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
import re

# Tier 1 filter criteria
TIER1_TYPES = ["Wearable Consumer", "Wearable Medical Device"]
TIER1_TECH_TAGS = ["wearable", "eeg", "neurofeedback", "tdcs", "tacs", "neurostimulation", "fnirs"]

# Rotation config
NUM_BATCHES = 3
LOOKBACK_HOURS = 72  # 3 days

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def load_companies() -> List[Dict]:
    """Load companies from config."""
    config_path = Path(__file__).parent.parent / 'config' / 'companies.json'
    with open(config_path, 'r') as f:
        return json.load(f)


def is_tier1_company(company: Dict) -> bool:
    """Check if company matches Tier 1 criteria."""
    company_type = company.get('type', '').strip()
    if company_type in TIER1_TYPES:
        return True

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


def get_todays_batch(companies: List[Dict]) -> Tuple[List[Dict], int]:
    """Get today's batch based on day rotation."""
    today = datetime.utcnow().timetuple().tm_yday  # Day of year (1-366)
    batch_index = today % NUM_BATCHES  # 0, 1, or 2

    batch_size = len(companies) // NUM_BATCHES
    remainder = len(companies) % NUM_BATCHES

    start = batch_index * batch_size + min(batch_index, remainder)
    end = start + batch_size + (1 if batch_index < remainder else 0)

    return companies[start:end], batch_index


def parse_google_date(date_str: str) -> datetime:
    """Parse Google News date format."""
    try:
        from dateutil import parser
        dt = parser.parse(date_str)
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except:
        return datetime.utcnow()


def extract_source(title: str) -> Tuple[str, str]:
    """Extract source from title (usually 'Title - Source')."""
    if ' - ' in title:
        parts = title.rsplit(' - ', 1)
        return parts[0].strip(), parts[1].strip()
    return title, 'Unknown'


def search_company(company: Dict, hours: int = 24) -> List[Dict]:
    """Search Google News for a company."""
    name = company.get('name', '')
    if not name:
        return []

    # Build Google News RSS URL
    query = quote(f'"{name}"')
    url = f'https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en'

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []

        feed = feedparser.parse(resp.text)
        if not feed.entries:
            return []

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        articles = []

        for entry in feed.entries[:5]:  # Check first 5 entries per company
            title = entry.get('title', '')
            if not title.strip():
                continue

            # Parse date
            pub_date = parse_google_date(entry.get('published', ''))

            # Skip if too old
            if pub_date < cutoff:
                continue

            # Extract source from title
            clean_title, source = extract_source(title)

            # Get the actual URL (Google News uses redirects)
            link = entry.get('link', '')

            articles.append({
                'title': clean_title,
                'url': link,
                'source': source,
                'published': pub_date.isoformat(),
                'company': name,
                'fetcher': 'google_news_rss'
            })

        return articles

    except Exception as e:
        return []


def search_companies_parallel(
    companies: List[Dict],
    hours: int = 24,
    max_workers: int = 10
) -> List[Dict]:
    """Search multiple companies in parallel."""
    articles = []
    seen_titles = set()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_company = {
            executor.submit(search_company, company, hours): company
            for company in companies
        }

        for future in as_completed(future_to_company):
            company = future_to_company[future]
            try:
                results = future.result()
                if results:
                    added = 0
                    for result in results:
                        # Dedupe by title prefix
                        title_key = result['title'].lower()[:50]
                        if title_key not in seen_titles:
                            seen_titles.add(title_key)
                            articles.append(result)
                            added += 1
                    if added > 0:
                        print(f"  + {company['name']} ({added})")
            except:
                pass

    return articles


def search_neurotech_topics(hours: int = 24) -> List[Dict]:
    """Search for broad neurotech topics."""
    queries = [
        'neurotech startup funding',
        'brain computer interface launch',
        'EEG headband new',
        'neurofeedback device',
    ]

    articles = []
    seen_titles = set()

    for query in queries:
        url = f'https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en'

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue

            feed = feedparser.parse(resp.text)
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            for entry in feed.entries[:5]:
                title = entry.get('title', '')
                pub_date = parse_google_date(entry.get('published', ''))

                if pub_date < cutoff:
                    continue

                title_key = title.lower()[:50]
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                clean_title, source = extract_source(title)

                articles.append({
                    'title': clean_title,
                    'url': entry.get('link', ''),
                    'source': source,
                    'published': pub_date.isoformat(),
                    'company': 'Industry',
                    'fetcher': 'google_news_rss_topic'
                })
        except:
            pass

    return articles


def fetch_tiered_news(hours: int = 72, min_total: int = 5) -> Tuple[List[Dict], List[Dict]]:
    """
    Fetch news with batch rotation.
    - Tier 1: 201 companies / 3 batches = ~67/day
    - 3-day lookback covers all news
    """
    tier1_companies, tier2_companies = split_companies()
    print(f"Total: {len(tier1_companies)} Tier 1, {len(tier2_companies)} Tier 2")

    # Get today's Tier 1 batch
    todays_batch, batch_idx = get_todays_batch(tier1_companies)
    print(f"\n[BATCH {batch_idx + 1}/{NUM_BATCHES}] {len(todays_batch)} Tier 1 companies")
    print(f"Lookback: {LOOKBACK_HOURS}h")

    tier1_articles = search_companies_parallel(todays_batch, LOOKBACK_HOURS, max_workers=15)
    print(f"Tier 1: {len(tier1_articles)} articles")

    # Get today's Tier 2 batch too
    tier2_batch, _ = get_todays_batch(tier2_companies)
    print(f"\n[BATCH {batch_idx + 1}/{NUM_BATCHES}] {len(tier2_batch)} Tier 2 companies")

    tier2_articles = search_companies_parallel(tier2_batch, LOOKBACK_HOURS, max_workers=15)
    print(f"Tier 2: {len(tier2_articles)} articles")

    return tier1_articles, tier2_articles


def fetch_all_news(hours: int = 12) -> List[Dict]:
    """Fetch all news (for backwards compatibility)."""
    tier1, tier2 = fetch_tiered_news(hours)
    return tier1 + tier2
