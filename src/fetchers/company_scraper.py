"""
Company blog/LinkedIn scraper.
Only scrapes actual blog POSTS, not navigation/shop links.
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


class BlogScraper:
    """Scrapes actual blog POSTS only."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0'
    }

    # URLs to SKIP (not blog posts)
    SKIP_PATTERNS = [
        '/shop', '/store', '/cart', '/checkout', '/account', '/login',
        '/contact', '/about', '/team', '/careers', '/jobs', '/privacy',
        '/terms', '/faq', '/help', '/support', '/pricing', '/demo',
        '/subscribe', '/signup', '/sign-up', '/register',
        '#', 'javascript:', 'mailto:', 'tel:',
        '/tag/', '/category/', '/author/', '/page/',
        '.pdf', '.jpg', '.png', '.gif', '.mp4',
    ]

    # Blog paths
    BLOG_PATHS = ['/blog', '/news', '/updates', '/press', '/newsroom', '/insights', '/articles']

    # RSS paths
    RSS_PATHS = ['/blog/feed', '/feed', '/rss', '/feed.xml', '/blog/rss.xml', '/atom.xml']

    def __init__(self, hours: int = 48):
        self.hours = hours
        self.cutoff = datetime.utcnow() - timedelta(hours=hours)

    def _is_valid_post_url(self, url: str) -> bool:
        """Check if URL looks like a blog post (not nav/shop)."""
        url_lower = url.lower()

        # Skip obvious non-posts
        for pattern in self.SKIP_PATTERNS:
            if pattern in url_lower:
                return False

        # Must have a path (not just homepage)
        parsed = urlparse(url)
        if not parsed.path or parsed.path == '/':
            return False

        # Should have multiple path segments (like /blog/my-post-title)
        segments = [s for s in parsed.path.split('/') if s]
        if len(segments) < 2:
            return False

        return True

    def _extract_posts_from_rss(self, rss_url: str, company: str) -> List[Dict]:
        """Extract posts from RSS feed."""
        posts = []
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:10]:
                title = entry.get('title', '').strip()
                link = entry.get('link', '')

                if not title or not link or len(title) < 15:
                    continue

                if not self._is_valid_post_url(link):
                    continue

                # Get date
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6])

                posts.append({
                    'title': title[:150],
                    'url': link,
                    'source': company,
                    'published': pub_date.isoformat() if pub_date else '',
                    'fetcher': 'rss'
                })

        except Exception as e:
            pass

        return posts[:5]

    def _extract_posts_from_html(self, html: str, base_url: str, company: str) -> List[Dict]:
        """Extract blog posts from HTML - strict filtering."""
        posts = []
        soup = BeautifulSoup(html, 'html.parser')

        # Look for article elements with dates (more likely to be real posts)
        for article in soup.find_all(['article', 'div'], class_=re.compile(r'post|article|entry|blog-item|news-item', re.I)):
            # Must have a link
            link_elem = article.find('a', href=True)
            if not link_elem:
                continue

            href = link_elem.get('href', '')
            full_url = urljoin(base_url, href)

            if not self._is_valid_post_url(full_url):
                continue

            # Must have a title (h1, h2, h3, or link text)
            title_elem = article.find(['h1', 'h2', 'h3', 'h4'])
            if title_elem:
                title = title_elem.get_text(strip=True)
            else:
                title = link_elem.get_text(strip=True)

            if not title or len(title) < 15 or len(title) > 200:
                continue

            # Skip if title looks like navigation
            skip_titles = ['read more', 'learn more', 'view all', 'see all', 'shop', 'buy', 'contact']
            if any(skip in title.lower() for skip in skip_titles):
                continue

            # Look for date
            date_elem = article.find(['time', 'span', 'div'], class_=re.compile(r'date|time|posted|published', re.I))
            date_str = date_elem.get('datetime', date_elem.get_text(strip=True)) if date_elem else ''

            posts.append({
                'title': title[:150],
                'url': full_url,
                'source': company,
                'published': date_str,
                'fetcher': 'blog'
            })

            if len(posts) >= 5:
                break

        return posts

    def _find_and_scrape_blog(self, base_url: str, company: str) -> List[Dict]:
        """Find and scrape blog page."""
        # Try RSS first
        for rss_path in self.RSS_PATHS:
            rss_url = urljoin(base_url, rss_path)
            try:
                resp = requests.head(rss_url, headers=self.HEADERS, timeout=5)
                if resp.status_code == 200:
                    posts = self._extract_posts_from_rss(rss_url, company)
                    if posts:
                        return posts
            except:
                continue

        # Try blog pages
        for blog_path in self.BLOG_PATHS:
            blog_url = urljoin(base_url, blog_path)
            try:
                resp = requests.get(blog_url, headers=self.HEADERS, timeout=10)
                if resp.status_code == 200:
                    posts = self._extract_posts_from_html(resp.text, blog_url, company)
                    if posts:
                        return posts
            except:
                continue

        return []

    def scrape_companies(self, companies: List[Dict], max_companies: int = 60) -> List[Dict]:
        """Scrape blog posts from companies."""
        all_posts = []

        # Prioritize relevant company types
        priority_types = ['Wearable Consumer', 'Wearable Medical', 'Software', 'Productivity']

        def sort_key(c):
            for i, pt in enumerate(priority_types):
                if pt in c.get('type', ''):
                    return i
            return 99

        sorted_companies = sorted(companies, key=sort_key)

        for company in sorted_companies[:max_companies]:
            name = company.get('name', '')
            url = company.get('url', '')

            if not url:
                continue

            posts = self._find_and_scrape_blog(url, name)
            if posts:
                print(f"  {name}: {len(posts)} posts")
                all_posts.extend(posts)

            time.sleep(0.3)

        print(f"Total blog posts: {len(all_posts)}")
        return all_posts


class LinkedInScraper:
    """Scrapes LinkedIn company posts."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0'
    }

    def scrape_company_posts(self, linkedin_url: str, company: str) -> List[Dict]:
        """Try to get LinkedIn posts (limited without auth)."""
        posts = []

        if not linkedin_url or 'linkedin.com' not in linkedin_url:
            return []

        # LinkedIn's public posts feed (limited)
        try:
            # Try the company's posts page
            posts_url = linkedin_url.rstrip('/') + '/posts/'

            resp = requests.get(posts_url, headers=self.HEADERS, timeout=10)
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Look for post content
            for post in soup.find_all('div', class_=re.compile(r'update|post|activity', re.I))[:5]:
                text_elem = post.find(['p', 'span', 'div'], class_=re.compile(r'content|text|body', re.I))
                if not text_elem:
                    continue

                text = text_elem.get_text(strip=True)[:150]
                if len(text) < 20:
                    continue

                posts.append({
                    'title': f"{company}: {text}",
                    'url': posts_url,
                    'source': f"{company} LinkedIn",
                    'published': '',
                    'fetcher': 'linkedin'
                })

        except Exception as e:
            pass

        return posts[:3]

    def scrape_companies(self, companies: List[Dict], max_companies: int = 20) -> List[Dict]:
        """Scrape LinkedIn posts."""
        all_posts = []

        for company in companies[:max_companies]:
            name = company.get('name', '')
            linkedin = company.get('linkedin', '')

            if linkedin:
                posts = self.scrape_company_posts(linkedin, name)
                if posts:
                    print(f"  {name} LinkedIn: {len(posts)} posts")
                    all_posts.extend(posts)

            time.sleep(0.5)

        print(f"Total LinkedIn posts: {len(all_posts)}")
        return all_posts


def scrape_company_updates(hours: int = 48, max_companies: int = 60) -> List[Dict]:
    """Main function: scrape blogs + LinkedIn."""
    companies = load_companies()

    # Filter to relevant types
    relevant = [c for c in companies if
                any(t in c.get('type', '') for t in ['Wearable', 'Consumer', 'Software', 'BCI']) or
                c.get('category') == 'productivity']

    print(f"Scraping {min(len(relevant), max_companies)} companies...")

    all_posts = []

    # Blog scraping
    print("\n[Blog scraping]")
    blog_scraper = BlogScraper(hours)
    all_posts.extend(blog_scraper.scrape_companies(relevant, max_companies))

    # LinkedIn scraping
    print("\n[LinkedIn scraping]")
    linkedin_scraper = LinkedInScraper()
    all_posts.extend(linkedin_scraper.scrape_companies(relevant[:20], 20))

    return all_posts
