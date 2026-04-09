"""
Direct company website/blog scraper.
Actually visits company sites to find real updates.
"""

import requests
import feedparser
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse


def load_companies() -> List[Dict]:
    """Load companies from config."""
    config_path = Path(__file__).parent.parent / 'config' / 'companies.json'
    with open(config_path, 'r') as f:
        return json.load(f)


class CompanyScraper:
    """Scrapes actual company websites for news/updates."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0'
    }

    # Known blog/news paths to check
    BLOG_PATHS = [
        '/blog', '/blog/', '/news', '/news/', '/updates', '/updates/',
        '/press', '/press/', '/newsroom', '/newsroom/',
        '/articles', '/articles/', '/insights', '/insights/',
    ]

    # Known RSS feed paths
    RSS_PATHS = [
        '/blog/feed', '/blog/rss', '/feed', '/rss', '/feed.xml', '/rss.xml',
        '/blog/feed/', '/blog/rss/', '/feed/', '/atom.xml',
        '/news/feed', '/news/rss',
    ]

    def __init__(self, hours_lookback: int = 24):
        self.hours = hours_lookback
        self.cutoff = datetime.utcnow() - timedelta(hours=hours_lookback)

    def _fetch_page(self, url: str, timeout: int = 10) -> Optional[str]:
        """Fetch page content."""
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
        except:
            pass
        return None

    def _find_blog_url(self, base_url: str) -> Optional[str]:
        """Find the blog/news page URL."""
        for path in self.BLOG_PATHS:
            url = urljoin(base_url, path)
            try:
                resp = requests.head(url, headers=self.HEADERS, timeout=5, allow_redirects=True)
                if resp.status_code == 200:
                    return resp.url
            except:
                continue
        return None

    def _find_rss_feed(self, base_url: str) -> Optional[str]:
        """Find RSS feed URL."""
        for path in self.RSS_PATHS:
            url = urljoin(base_url, path)
            try:
                resp = requests.head(url, headers=self.HEADERS, timeout=5)
                if resp.status_code == 200:
                    return url
            except:
                continue
        return None

    def _extract_articles_from_html(self, html: str, base_url: str, company_name: str) -> List[Dict]:
        """Extract article links from HTML page."""
        articles = []
        soup = BeautifulSoup(html, 'html.parser')

        # Look for article-like elements
        for tag in ['article', 'div', 'li']:
            for elem in soup.find_all(tag, class_=re.compile(r'post|article|news|blog|item', re.I)):
                # Find link
                link = elem.find('a', href=True)
                if not link:
                    continue

                href = link.get('href', '')
                if not href or href.startswith('#'):
                    continue

                full_url = urljoin(base_url, href)

                # Find title
                title_elem = elem.find(['h1', 'h2', 'h3', 'h4', 'a'])
                title = title_elem.get_text(strip=True) if title_elem else ''

                if not title or len(title) < 10:
                    continue

                # Find date if available
                date_elem = elem.find(['time', 'span', 'div'], class_=re.compile(r'date|time|posted', re.I))
                date_str = date_elem.get_text(strip=True) if date_elem else ''

                articles.append({
                    'title': title[:150],
                    'url': full_url,
                    'source': company_name,
                    'published': date_str,
                    'company': company_name,
                    'fetcher': 'company_blog'
                })

                if len(articles) >= 5:
                    break

        return articles[:3]  # Max 3 per company

    def _extract_from_rss(self, rss_url: str, company_name: str) -> List[Dict]:
        """Extract articles from RSS feed."""
        articles = []
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:5]:
                title = entry.get('title', '')
                link = entry.get('link', '')

                if not title or not link:
                    continue

                # Parse date
                pub_date = ''
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6]).isoformat()

                articles.append({
                    'title': title[:150],
                    'url': link,
                    'source': company_name,
                    'published': pub_date,
                    'company': company_name,
                    'fetcher': 'rss'
                })
        except:
            pass

        return articles[:3]

    def scrape_company(self, company: Dict) -> List[Dict]:
        """Scrape a single company's website for updates."""
        name = company.get('name', '')
        url = company.get('url', '')

        if not url:
            return []

        articles = []

        # Try RSS first (faster, more reliable)
        rss_url = self._find_rss_feed(url)
        if rss_url:
            articles = self._extract_from_rss(rss_url, name)
            if articles:
                return articles

        # Try blog page
        blog_url = self._find_blog_url(url)
        if blog_url:
            html = self._fetch_page(blog_url)
            if html:
                articles = self._extract_articles_from_html(html, blog_url, name)

        return articles

    def scrape_companies(self, companies: List[Dict], max_companies: int = 50) -> List[Dict]:
        """Scrape multiple companies."""
        all_articles = []

        # Prioritize wearable/consumer companies
        priority_types = ['Wearable Consumer', 'Wearable Medical Device', 'Productivity App']

        # Sort by priority
        def priority_sort(c):
            ctype = c.get('type', '')
            for i, pt in enumerate(priority_types):
                if pt in ctype:
                    return i
            return 99

        sorted_companies = sorted(companies, key=priority_sort)

        count = 0
        for company in sorted_companies[:max_companies]:
            articles = self.scrape_company(company)
            if articles:
                print(f"  {company['name']}: {len(articles)} articles")
                all_articles.extend(articles)
                count += 1
            time.sleep(0.3)

        print(f"Scraped {count} companies, found {len(all_articles)} articles")
        return all_articles


def scrape_company_updates(hours: int = 24, max_companies: int = 50) -> List[Dict]:
    """Main function to scrape company updates."""
    companies = load_companies()

    # Filter to relevant types
    relevant_types = ['Wearable', 'Consumer', 'Software', 'Productivity', 'BCI']
    filtered = [c for c in companies if any(t in c.get('type', '') for t in relevant_types) or c.get('category') == 'productivity']

    print(f"Scraping {min(len(filtered), max_companies)} relevant companies...")

    scraper = CompanyScraper(hours_lookback=hours)
    return scraper.scrape_companies(filtered, max_companies)
