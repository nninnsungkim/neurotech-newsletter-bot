"""
Opportunity fetcher for VC fellowships, pitch competitions, etc.
Hybrid approach:
1. Direct scraping of known program application pages
2. Google News RSS for program announcements
"""

import feedparser
import requests
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from bs4 import BeautifulSoup
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# Direct program application URLs - these are scraped directly
PROGRAM_URLS = {
    # Top US Accelerators/Fellowships
    'Y Combinator': 'https://www.ycombinator.com/apply',
    'Techstars': 'https://www.techstars.com/accelerators',
    'On Deck': 'https://www.beondeck.com/founders',
    '500 Global': 'https://500.co/accelerators',
    'Antler': 'https://www.antler.co/apply',
    'Entrepreneur First': 'https://www.joinef.com/',
    'Pioneer': 'https://pioneer.app/',
    'Neo': 'https://neo.com/',
    'South Park Commons': 'https://www.southparkcommons.com/membership',
    'Z Fellows': 'https://www.zfellows.com/',
    'Contrary': 'https://contrary.com/talent',
    '1517 Fund': 'https://www.1517fund.com/',
    'Dorm Room Fund': 'https://www.dormroomfund.com/',
    'Rough Draft Ventures': 'https://www.roughdraft.vc/',

    # HealthTech/NeuroTech specific
    'StartUp Health': 'https://www.startuphealth.com/apply',
    'Rock Health': 'https://rockhealth.com/',
    'HAX': 'https://hax.co/apply',
    'IndieBio': 'https://indiebio.co/apply/',
    'Creative Destruction Lab': 'https://www.creativedestructionlab.com/program/',

    # Korea
    'SparkLabs': 'https://www.sparklabs.co.kr/lb/apply.php',
    'Primer': 'https://www.primer.kr/',
    'FuturePlay': 'https://futureplay.co/',
    'TIPS': 'https://www.jointips.or.kr/',
    'K-Startup Grand Challenge': 'https://www.k-startupgc.org/',

    # Purdue/Indiana
    'Purdue Foundry': 'https://www.purdue.edu/foundry/',
    'Elevate Ventures': 'https://elevateventures.com/',
}


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

    skip_urls = ['linkedin.com/jobs', 'indeed.com', 'glassdoor.com']
    for pattern in skip_urls:
        if pattern in url_lower:
            return True

    for keyword in config.get('exclusion_keywords', []):
        if keyword.lower() in title_lower:
            return True

    return False


def scrape_program_page(program: str, url: str) -> Dict:
    """Scrape a program's application page for status."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text().lower()

        # Look for application status indicators
        is_open = any(phrase in text for phrase in [
            'apply now', 'applications open', 'accepting applications',
            'start your application', 'submit your application',
            'application deadline', 'apply today', 'join our',
            '지원하기', '모집', '신청'  # Korean
        ])

        is_closed = any(phrase in text for phrase in [
            'applications closed', 'no longer accepting',
            'check back', 'applications will open',
            'coming soon', 'waitlist'
        ])

        # Extract deadline if mentioned
        deadline = None
        deadline_patterns = [
            r'deadline[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
            r'apply by[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
            r'closes?[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        ]
        for pattern in deadline_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                deadline = match.group(1)
                break

        # Get page title
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else program

        if is_open and not is_closed:
            return {
                'title': f"{program} - Applications Open" + (f" (Deadline: {deadline})" if deadline else ""),
                'url': url,
                'source': program,
                'snippet': f"Apply at {url}",
                'program': program,
                'status': 'open',
                'deadline': deadline,
                'category': 'direct_scrape'
            }

        return None

    except Exception as e:
        return None


def scrape_all_programs() -> List[Dict]:
    """Scrape all known program pages."""
    results = []

    print("\n  [Checking Program Pages]")

    for program, url in PROGRAM_URLS.items():
        result = scrape_program_page(program, url)
        if result:
            results.append(result)
            status = "OPEN" if result.get('status') == 'open' else "?"
            print(f"    + {program}: {status}")
        time.sleep(0.3)  # Rate limiting

    return results


def search_google_news(query: str, hours: int = 168) -> List[Dict]:
    """Search Google News RSS."""
    articles = []
    url = f'https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en'

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []

        feed = feedparser.parse(resp.text)
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        for entry in feed.entries[:5]:
            title = entry.get('title', '')
            if not title.strip():
                continue

            pub_date = parse_date(entry.get('published', ''))
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
                'category': 'google_news'
            })
    except:
        pass

    return articles


def search_program_news(programs: List[str], hours: int = 168) -> List[Dict]:
    """Search Google News for program announcements."""
    results = []
    seen_titles = set()

    print("\n  [Searching Program Announcements]")

    for program in programs:
        queries = [
            f'"{program}" fellowship application 2026',
            f'"{program}" accelerator accepting applications',
            f'"{program}" cohort spring 2026',
        ]

        for query in queries[:1]:  # Limit queries
            articles = search_google_news(query, hours)
            for article in articles:
                title_key = article['title'].lower()[:50]
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    article['program'] = program
                    results.append(article)

        if any(a.get('program') == program for a in results):
            print(f"    + {program}: found news")

        time.sleep(0.2)

    return results


def search_general_fellowship_news(hours: int = 168) -> List[Dict]:
    """Search for general fellowship announcements."""
    queries = [
        'startup fellowship application open 2026',
        'accelerator accepting applications spring 2026',
        'VC fellowship founders program 2026',
        'pre-seed accelerator application deadline',
        'founder fellowship builders 2026',
        'healthtech accelerator application',
        'neurotech startup program 2026',
        # Korea
        '스타트업 액셀러레이터 모집 2026',
        'Korea startup accelerator application',
    ]

    results = []
    seen_titles = set()

    print("\n  [General Fellowship News]")

    for query in queries:
        articles = search_google_news(query, hours)
        added = 0
        for article in articles:
            title_key = article['title'].lower()[:50]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                results.append(article)
                added += 1
        if added:
            print(f"    + '{query[:35]}...': {added}")
        time.sleep(0.2)

    return results


def search_purdue_indiana(hours: int = 168) -> List[Dict]:
    """Search for Purdue/Indiana opportunities."""
    queries = [
        'Purdue pitch competition 2026',
        'Purdue startup competition apply',
        'Purdue Foundry entrepreneur',
        'Purdue Burton Morgan business',
        'Indiana University startup pitch',
        'Indiana startup competition 2026',
        'Indianapolis pitch competition',
        'Elevate Ventures Indiana',
    ]

    results = []
    seen_titles = set()

    print("\n  [Purdue/Indiana Opportunities]")

    for query in queries:
        articles = search_google_news(query, hours)
        for article in articles:
            # Must mention Purdue or Indiana
            text = (article['title'] + ' ' + article.get('source', '')).lower()
            if 'purdue' in text or 'indiana' in text or 'indy' in text:
                title_key = article['title'].lower()[:50]
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    article['category'] = 'pitch_competition'
                    results.append(article)

        time.sleep(0.2)

    if results:
        print(f"    Found: {len(results)} Purdue/Indiana opportunities")

    return results


def fetch_all_opportunities(hours: int = 168) -> Tuple[List[Dict], List[Dict]]:
    """Fetch all opportunities using hybrid approach."""
    config = load_config()

    print("[VC FELLOWSHIPS]")

    all_vc = []

    # 1. Direct scraping of program pages
    direct_results = scrape_all_programs()
    all_vc.extend(direct_results)
    print(f"\n  Direct scrape: {len(direct_results)} programs with open applications")

    # 2. News about known programs
    us_config = config.get('vc_fellowships_us', {})
    korea_config = config.get('vc_fellowships_korea', {})

    top_programs = us_config.get('known_programs', [])[:20]
    korea_programs = korea_config.get('known_programs', [])

    program_news = search_program_news(top_programs + korea_programs, hours)

    # 3. General fellowship news
    general_news = search_general_fellowship_news(hours)

    # Combine and filter
    all_news = program_news + general_news
    for article in all_news:
        if not should_skip(article['url'], article['title'], config):
            article['category'] = 'vc_fellowship'
            all_vc.append(article)

    # Dedupe
    seen = set()
    unique_vc = []
    for item in all_vc:
        key = item['title'].lower()[:50]
        if key not in seen:
            seen.add(key)
            unique_vc.append(item)

    print(f"\nTotal VC Fellowships: {len(unique_vc)}")

    # Pitch competitions
    print("\n[PITCH COMPETITIONS]")
    pitch_results = search_purdue_indiana(hours)

    # Filter
    unique_pitch = []
    seen_pitch = set()
    for item in pitch_results:
        if not should_skip(item['url'], item['title'], config):
            key = item['title'].lower()[:50]
            if key not in seen_pitch:
                seen_pitch.add(key)
                unique_pitch.append(item)

    print(f"\nTotal Pitch Competitions: {len(unique_pitch)}")

    return unique_vc, unique_pitch


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    vc, pitch = fetch_all_opportunities(168)
    print(f"\n=== RESULTS ===")
    print(f"VC Fellowships: {len(vc)}")
    for r in vc[:10]:
        print(f"  - [{r.get('category', '')}] {r['title'][:60]}")

    print(f"\nPitch Competitions: {len(pitch)}")
    for r in pitch[:5]:
        print(f"  - {r['title'][:60]}")
