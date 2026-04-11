"""
Google News RSS fetcher with batch rotation.
- APEX-aligned Tier 1: ~60 companies in cognitive performance space
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

# Rotation config
NUM_BATCHES = 3
LOOKBACK_HOURS = 72  # 3 days

# URLs to SKIP (stock filings, SEC, investor noise)
SKIP_URL_PATTERNS = [
    'stocktitan.net',
    'sec-filings',
    'sec.gov',
    'benzinga.com/sec',
    'marketwatch.com/investing',
    'nasdaq.com/market-activity',
    'finance.yahoo.com/quote',
    'seekingalpha.com/symbol',
    'zacks.com/stock',
    'fool.com/quote',
    'tipranks.com',
    'gurufocus.com',
    'simplywall.st',
    'tradingview.com/symbols',
]

# Titles to SKIP
SKIP_TITLE_PATTERNS = [
    # SEC filings
    'form 3', 'form 4', 'form 8-k', 'form 10-',
    'sec filing', 'beneficial ownership',
    # Stock/finance
    'stock price', 'share price', 'stock moves', 'stock surge',
    'buy rating', 'sell rating', 'hold rating',
    'price target', 'analyst', 'zacks rank',
    'earnings call', 'quarterly results',
    'dividend', 'shareholders',
    # Investment noise
    'dilution', 'options and performance', 'performance rights',
    'all ordinaries', 'asx:', 'nasdaq:', 'nyse:',
    'if you invested', 'should you buy', 'is it time to buy',
    'sparks fresh', 'surge sparks', 'stock alert',
    # Medical procedures (not cognitive tech)
    'surgical tool', 'surgical device', 'surgery',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def load_apex_tier1() -> List[Dict]:
    """Load APEX-curated Tier 1 companies."""
    config_path = Path(__file__).parent.parent / 'config' / 'apex_tier1.json'
    with open(config_path, 'r') as f:
        data = json.load(f)

    # Flatten all tier1 categories into one list
    tier1 = []
    for key, companies in data.items():
        if key.startswith('tier1_') and isinstance(companies, list):
            tier1.extend(companies)

    return tier1


def load_all_companies() -> List[Dict]:
    """Load all companies from main config (for Tier 2)."""
    config_path = Path(__file__).parent.parent / 'config' / 'companies.json'
    with open(config_path, 'r') as f:
        return json.load(f)


def split_companies() -> Tuple[List[Dict], List[Dict]]:
    """Split into APEX Tier 1 (curated) and Tier 2 (general neurotech)."""
    tier1 = load_apex_tier1()
    tier1_names = {c['name'].lower() for c in tier1}

    # Tier 2: other neurotech companies not in Tier 1
    all_companies = load_all_companies()
    tier2 = [c for c in all_companies if c['name'].lower() not in tier1_names]

    return tier1, tier2


def should_skip_article(url: str, title: str) -> bool:
    """Check if article should be skipped (stock/SEC noise)."""
    url_lower = url.lower()
    title_lower = title.lower()

    for pattern in SKIP_URL_PATTERNS:
        if pattern in url_lower:
            return True

    for pattern in SKIP_TITLE_PATTERNS:
        if pattern in title_lower:
            return True

    return False


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

            # Skip stock/SEC noise
            if should_skip_article(link, clean_title):
                continue

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
    """Search for APEX-relevant topics - broad industry coverage."""
    queries = [
        # Core cognitive performance
        'EEG headband',
        'EEG wearable',
        'brain sensing wearable',
        'focus tracking device',
        'neurofeedback device',
        'cognitive performance technology',
        # fNIRS
        'fNIRS',
        'brain imaging wearable',
        # Neurostimulation
        'tDCS',
        'tACS',
        'brain stimulation device',
        'transcranial stimulation',
        # HRV/Recovery
        'HRV wearable',
        'recovery wearable',
        'stress tracking wearable',
        # Market signals
        'neurotech startup',
        'neurotech funding',
        'brain computer interface',
        'BCI startup',
        # Productivity/Focus
        'focus app launch',
        'productivity wearable',
        'attention tracking',
        # Sleep/Cognitive
        'sleep tracking EEG',
        'cognitive enhancement',
        'brain training app',
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

                clean_title, source = extract_source(title)
                link = entry.get('link', '')

                # Skip stock/SEC noise
                if should_skip_article(link, clean_title):
                    continue

                title_key = title.lower()[:50]
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

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
    Fetch news for APEX.
    - All 55 Tier 1 companies (no rotation needed)
    - Broad keyword searches for industry news
    """
    tier1_companies = load_apex_tier1()
    print(f"APEX Tier 1: {len(tier1_companies)} companies")

    # Search ALL Tier 1 companies (only 55, no need to batch)
    print(f"\n[COMPANY SEARCH] {len(tier1_companies)} companies")
    print(f"Lookback: {hours}h")

    company_articles = search_companies_parallel(tier1_companies, hours, max_workers=15)
    print(f"Company articles: {len(company_articles)}")

    # Broad keyword searches for industry news
    print(f"\n[TOPIC SEARCH] Broad keywords")
    topic_articles = search_neurotech_topics(hours)
    print(f"Topic articles: {len(topic_articles)}")

    # Combine (company articles first, then topics)
    all_articles = company_articles + topic_articles
    return all_articles, []


def fetch_all_news(hours: int = 12) -> List[Dict]:
    """Fetch all news (for backwards compatibility)."""
    tier1, tier2 = fetch_tiered_news(hours)
    return tier1 + tier2
