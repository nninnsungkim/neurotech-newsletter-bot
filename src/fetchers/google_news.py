"""
Tiered company news search - Using Bing News RSS (parallel).
Tier 1: Wearable Consumer/Medical + specific tech_tags (no limit)
Tier 2: Other neurotech companies (fill to 15)
"""

import feedparser
import requests
import json
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


# Tier 1 filter criteria
TIER1_TYPES = ["Wearable Consumer", "Wearable Medical Device"]
TIER1_TECH_TAGS = ["wearable", "eeg", "neurofeedback", "tdcs", "tacs", "neurostimulation", "fnirs"]

# Keywords to filter relevant articles
RELEVANCE_KEYWORDS = [
    'neuro', 'brain', 'eeg', 'bci', 'neural', 'cognit', 'mental', 'sleep',
    'headband', 'headset', 'wearable', 'implant', 'stimulat', 'therapy',
    'device', 'fda', 'clinical', 'trial', 'patient', 'health', 'medical',
    'research', 'study', 'treatment', 'diagnos', 'monitor', 'sensor',
    'alzheimer', 'parkinson', 'epilep', 'depress', 'anxiety', 'adhd',
    'funding', 'series', 'raised', 'investment', 'launch', 'release',
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def is_relevant_article(title: str, company_name: str) -> bool:
    """Check if article is relevant to neurotech."""
    title_lower = title.lower()
    company_lower = company_name.lower()

    # Must mention the company name
    if company_lower not in title_lower and company_lower.split()[0] not in title_lower:
        return False

    # Check for relevance keywords
    for keyword in RELEVANCE_KEYWORDS:
        if keyword in title_lower:
            return True

    return False


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


def _search_single_company(company: Dict, hours: int) -> Dict:
    """Search for a single company using Bing News RSS."""
    name = company.get('name', '')
    if not name:
        return None

    # Search just company name (already filtered to neurotech companies)
    query = name
    url = f'https://www.bing.com/news/search?q={quote(query)}&format=rss'

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None

        feed = feedparser.parse(resp.text)
        if not feed.entries:
            return None

        # Check if article is within time window
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        for entry in feed.entries[:3]:  # Check first 3 entries
            title = entry.get('title', '')
            if not title.strip():
                continue

            # Parse publish date
            pub_date = None
            try:
                from dateutil import parser
                pub_date = parser.parse(entry.get('published', ''))
                if pub_date.tzinfo:
                    pub_date = pub_date.replace(tzinfo=None)
            except:
                pub_date = datetime.utcnow()

            # Skip if too old
            if pub_date < cutoff:
                continue

            # Extract source from title (usually "Title - Source")
            source = 'Unknown'
            if ' - ' in title:
                parts = title.rsplit(' - ', 1)
                title = parts[0]
                source = parts[1] if len(parts) > 1 else 'Unknown'

            # Check relevance
            if not is_relevant_article(title, name):
                continue

            return {
                'title': title.strip(),
                'url': entry.get('link', ''),
                'source': source.strip(),
                'published': pub_date.isoformat(),
                'company': name,
                'fetcher': 'bing_news'
            }

    except Exception as e:
        pass

    return None


def search_companies_parallel(companies: List[Dict], hours: int, max_workers: int = 10) -> List[Dict]:
    """Search multiple companies in parallel."""
    articles = []
    seen_titles = set()  # Avoid duplicates

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_company = {
            executor.submit(_search_single_company, company, hours): company
            for company in companies
        }

        for future in as_completed(future_to_company):
            company = future_to_company[future]
            try:
                result = future.result()
                if result:
                    # Skip duplicate titles
                    title_key = result['title'].lower()[:50]
                    if title_key not in seen_titles:
                        seen_titles.add(title_key)
                        print(f"  + {company['name']}")
                        articles.append(result)
            except:
                pass

    return articles


def fetch_tiered_news(hours: int = 12, min_total: int = 15) -> Tuple[List[Dict], List[Dict]]:
    """Fetch news using tiered approach with parallel processing."""
    tier1_companies, tier2_companies = split_companies()
    print(f"Companies: {len(tier1_companies)} Tier 1, {len(tier2_companies)} Tier 2")

    # Tier 1: Search all in parallel
    print(f"\n[TIER 1] Searching {len(tier1_companies)} priority companies...")
    tier1_articles = search_companies_parallel(tier1_companies, hours, max_workers=15)
    print(f"Tier 1 results: {len(tier1_articles)} articles")

    # Tier 2: Only if needed
    needed = min_total - len(tier1_articles)
    tier2_articles = []

    if needed > 0:
        print(f"\n[TIER 2] Searching {len(tier2_companies)} companies for {needed} more...")
        tier2_articles = search_companies_parallel(tier2_companies, hours, max_workers=15)
        tier2_articles = tier2_articles[:needed]
        print(f"Tier 2 results: {len(tier2_articles)} articles")
    else:
        print("\n[TIER 2] Skipped (Tier 1 sufficient)")

    return tier1_articles, tier2_articles


def fetch_all_news(hours: int = 12) -> List[Dict]:
    """Fetch all news (for backwards compatibility)."""
    tier1, tier2 = fetch_tiered_news(hours)
    return tier1 + tier2
