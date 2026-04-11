"""
Opportunity fetcher for VC fellowships, pitch competitions, etc.
Uses Google News RSS + Google Search for broad coverage.
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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# Skip these URLs
SKIP_URL_PATTERNS = [
    'linkedin.com/jobs',
    'indeed.com',
    'glassdoor.com',
    'levels.fyi',
    'salary',
]


def load_config() -> Dict:
    """Load opportunities config."""
    config_path = Path(__file__).parent.parent / 'config' / 'opportunities.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_date(date_str: str) -> datetime:
    """Parse date from feed."""
    try:
        from dateutil import parser
        dt = parser.parse(date_str)
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except:
        return datetime.utcnow()


def extract_source(title: str) -> Tuple[str, str]:
    """Extract source from title."""
    if ' - ' in title:
        parts = title.rsplit(' - ', 1)
        return parts[0].strip(), parts[1].strip()
    return title, 'Unknown'


def should_skip(url: str, title: str, config: Dict) -> bool:
    """Check if result should be skipped."""
    url_lower = url.lower()
    title_lower = title.lower()

    # Skip job postings
    for pattern in SKIP_URL_PATTERNS:
        if pattern in url_lower:
            return True

    # Skip exclusion keywords
    for keyword in config.get('exclusion_keywords', []):
        if keyword.lower() in title_lower:
            return True

    return False


def has_priority_keyword(title: str, config: Dict) -> bool:
    """Check if title has priority keywords."""
    title_lower = title.lower()
    for keyword in config.get('priority_keywords', []):
        if keyword.lower() in title_lower:
            return True
    return False


def search_google_news(query: str, hours: int = 168) -> List[Dict]:
    """Search Google News RSS for a query."""
    articles = []

    url = f'https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en'

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []

        feed = feedparser.parse(resp.text)
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        for entry in feed.entries[:10]:
            title = entry.get('title', '')
            if not title.strip():
                continue

            pub_date = parse_date(entry.get('published', ''))

            # More lenient date filter for opportunities (they're often announced weeks ahead)
            if pub_date < cutoff:
                continue

            clean_title, source = extract_source(title)
            link = entry.get('link', '')

            articles.append({
                'title': clean_title,
                'url': link,
                'source': source,
                'published': pub_date.isoformat(),
                'query': query,
                'fetcher': 'google_news'
            })
    except Exception as e:
        pass

    return articles


def search_queries_parallel(queries: List[str], hours: int = 168, max_workers: int = 10) -> List[Dict]:
    """Search multiple queries in parallel."""
    articles = []
    seen_titles = set()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_query = {
            executor.submit(search_google_news, query, hours): query
            for query in queries
        }

        for future in as_completed(future_to_query):
            try:
                results = future.result()
                for result in results:
                    title_key = result['title'].lower()[:60]
                    if title_key not in seen_titles:
                        seen_titles.add(title_key)
                        articles.append(result)
            except:
                pass

    return articles


def search_program_news(programs: List[str], hours: int = 168) -> List[Dict]:
    """Search for specific program announcements."""
    articles = []
    seen_titles = set()

    for program in programs:
        # Search for program + fellowship/application keywords
        queries = [
            f'"{program}" fellowship application 2026',
            f'"{program}" cohort accepting applications',
            f'"{program}" spring 2026',
        ]

        for query in queries:
            results = search_google_news(query, hours)
            for result in results:
                title_key = result['title'].lower()[:60]
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    result['program'] = program
                    articles.append(result)

    return articles


def fetch_vc_fellowships(hours: int = 168) -> List[Dict]:
    """Fetch VC fellowship opportunities."""
    config = load_config()
    all_articles = []

    print("\n[VC FELLOWSHIPS - US]")

    # Search general queries
    us_config = config.get('vc_fellowships_us', {})
    queries = us_config.get('search_queries', [])
    articles = search_queries_parallel(queries, hours)
    print(f"  General queries: {len(articles)} results")
    all_articles.extend(articles)

    # Search known programs
    programs = us_config.get('known_programs', [])[:30]  # Top 30
    program_articles = search_program_news(programs, hours)
    print(f"  Program-specific: {len(program_articles)} results")
    all_articles.extend(program_articles)

    # Search healthtech/neurotech specific
    health_programs = us_config.get('healthtech_neurotech_specific', [])
    health_articles = search_program_news(health_programs, hours)
    print(f"  HealthTech/Neurotech: {len(health_articles)} results")
    all_articles.extend(health_articles)

    print("\n[VC FELLOWSHIPS - KOREA]")

    # Korea - major programs only
    korea_config = config.get('vc_fellowships_korea', {})
    korea_queries = korea_config.get('search_queries', [])
    korea_articles = search_queries_parallel(korea_queries, hours)
    print(f"  Korea queries: {len(korea_articles)} results")
    all_articles.extend(korea_articles)

    korea_programs = korea_config.get('known_programs', [])
    korea_program_articles = search_program_news(korea_programs, hours)
    print(f"  Korea programs: {len(korea_program_articles)} results")
    all_articles.extend(korea_program_articles)

    # Filter and dedupe
    filtered = []
    seen = set()
    for article in all_articles:
        if should_skip(article['url'], article['title'], config):
            continue

        title_key = article['title'].lower()[:60]
        if title_key in seen:
            continue
        seen.add(title_key)

        # Mark priority
        article['priority'] = has_priority_keyword(article['title'], config)
        article['category'] = 'vc_fellowship'
        filtered.append(article)

    # Sort by priority
    filtered.sort(key=lambda x: (not x['priority'], x['published']), reverse=True)

    print(f"\nTotal VC Fellowships: {len(filtered)}")
    return filtered


def fetch_pitch_competitions(hours: int = 168) -> List[Dict]:
    """Fetch Purdue/Indiana pitch competitions."""
    config = load_config()

    print("\n[PITCH COMPETITIONS - Purdue/Indiana]")

    local_config = config.get('pitch_competitions_local', {})
    queries = local_config.get('search_queries', [])
    articles = search_queries_parallel(queries, hours)
    print(f"  Search results: {len(articles)}")

    # Search known programs
    programs = local_config.get('known_programs', [])
    program_articles = search_program_news(programs, hours)
    print(f"  Program-specific: {len(program_articles)}")
    articles.extend(program_articles)

    # Filter and dedupe
    filtered = []
    seen = set()
    for article in articles:
        if should_skip(article['url'], article['title'], config):
            continue

        title_key = article['title'].lower()[:60]
        if title_key in seen:
            continue
        seen.add(title_key)

        article['priority'] = has_priority_keyword(article['title'], config)
        article['category'] = 'pitch_competition'
        filtered.append(article)

    print(f"Total Pitch Competitions: {len(filtered)}")
    return filtered


def fetch_all_opportunities(hours: int = 168) -> Tuple[List[Dict], List[Dict]]:
    """Fetch all opportunities."""
    vc_fellowships = fetch_vc_fellowships(hours)
    pitch_competitions = fetch_pitch_competitions(hours)

    return vc_fellowships, pitch_competitions


if __name__ == "__main__":
    # Test
    vc, pitch = fetch_all_opportunities(168)
    print(f"\n=== RESULTS ===")
    print(f"VC Fellowships: {len(vc)}")
    print(f"Pitch Competitions: {len(pitch)}")

    if vc:
        print("\nTop VC Fellowship results:")
        for a in vc[:5]:
            print(f"  - {a['title'][:70]}")
