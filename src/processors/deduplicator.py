"""
Deduplication and ranking for collected articles.
Uses fuzzy matching to identify similar articles.
"""

from typing import List, Dict, Set
from fuzzywuzzy import fuzz
from urllib.parse import urlparse
import hashlib
import json
import os
from datetime import datetime, timedelta


class ArticleDeduplicator:
    """Removes duplicate articles and ranks by relevance."""

    def __init__(self, sent_articles_path: str = None):
        self.sent_articles_path = sent_articles_path or 'data/sent_articles.json'
        self.sent_urls: Set[str] = set()
        self.sent_hashes: Set[str] = set()
        self._load_sent_articles()

    def _load_sent_articles(self):
        """Load previously sent articles to avoid repeats."""
        try:
            if os.path.exists(self.sent_articles_path):
                with open(self.sent_articles_path, 'r') as f:
                    data = json.load(f)

                # Only keep articles from last 7 days
                cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
                recent = [a for a in data if a.get('sent_at', '') > cutoff]

                self.sent_urls = {a['url'] for a in recent}
                self.sent_hashes = {a.get('title_hash', '') for a in recent}

                print(f"Loaded {len(self.sent_urls)} previously sent articles")
        except Exception as e:
            print(f"Could not load sent articles: {e}")

    def _save_sent_articles(self, new_articles: List[Dict]):
        """Save newly sent articles."""
        try:
            existing = []
            if os.path.exists(self.sent_articles_path):
                with open(self.sent_articles_path, 'r') as f:
                    existing = json.load(f)

            # Add new articles
            now = datetime.utcnow().isoformat()
            for article in new_articles:
                existing.append({
                    'url': article['url'],
                    'title_hash': self._hash_title(article['title']),
                    'sent_at': now
                })

            # Keep only last 7 days
            cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
            existing = [a for a in existing if a.get('sent_at', '') > cutoff]

            os.makedirs(os.path.dirname(self.sent_articles_path), exist_ok=True)
            with open(self.sent_articles_path, 'w') as f:
                json.dump(existing, f, indent=2)

        except Exception as e:
            print(f"Could not save sent articles: {e}")

    def _hash_title(self, title: str) -> str:
        """Create a hash of the title for comparison."""
        normalized = title.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        parsed = urlparse(url)
        # Remove tracking parameters
        path = parsed.path.rstrip('/')
        return f"{parsed.netloc}{path}".lower()

    def _is_similar(self, title1: str, title2: str, threshold: int = 80) -> bool:
        """Check if two titles are similar using fuzzy matching."""
        return fuzz.ratio(title1.lower(), title2.lower()) >= threshold

    def _is_previously_sent(self, article: Dict) -> bool:
        """Check if article was already sent."""
        url = article.get('url', '')
        title_hash = self._hash_title(article.get('title', ''))

        if url in self.sent_urls:
            return True
        if title_hash in self.sent_hashes:
            return True

        return False

    def deduplicate(self, articles: List[Dict]) -> List[Dict]:
        """Remove duplicate articles from the list."""
        seen_urls: Set[str] = set()
        seen_titles: List[str] = []
        unique_articles = []

        for article in articles:
            url = article.get('url', '')
            title = article.get('title', '')

            if not url or not title:
                continue

            # Skip previously sent
            if self._is_previously_sent(article):
                continue

            # Check URL duplicate
            normalized_url = self._normalize_url(url)
            if normalized_url in seen_urls:
                continue

            # Check title similarity
            is_similar = False
            for seen_title in seen_titles:
                if self._is_similar(title, seen_title):
                    is_similar = True
                    break

            if is_similar:
                continue

            # Article is unique
            seen_urls.add(normalized_url)
            seen_titles.append(title)
            unique_articles.append(article)

        print(f"Deduplicated: {len(articles)} -> {len(unique_articles)} articles")
        return unique_articles

    def mark_as_sent(self, articles: List[Dict]):
        """Mark articles as sent to avoid repeating them."""
        self._save_sent_articles(articles)


class ArticleRanker:
    """Ranks articles by relevance and quality."""

    # Source quality scores
    SOURCE_SCORES = {
        'techcrunch': 10,
        'wired': 10,
        'mit technology review': 10,
        'the verge': 9,
        'ars technica': 9,
        'ieee spectrum': 10,
        'venturebeat': 8,
        'neuroscience news': 9,
        'bloomberg': 10,
        'reuters': 10,
        'forbes': 7,
        'business insider': 6,
    }

    # Keywords that boost relevance
    BOOST_KEYWORDS = [
        'announces', 'launches', 'raises', 'funding', 'series',
        'partnership', 'acquisition', 'fda', 'approved', 'clinical',
        'breakthrough', 'first', 'new', 'release', 'update'
    ]

    def _get_source_score(self, source: str) -> int:
        """Get quality score for a source."""
        source_lower = source.lower()
        for name, score in self.SOURCE_SCORES.items():
            if name in source_lower:
                return score
        return 5  # Default score

    def _get_keyword_boost(self, title: str) -> int:
        """Get boost score based on keywords in title."""
        title_lower = title.lower()
        boost = 0
        for keyword in self.BOOST_KEYWORDS:
            if keyword in title_lower:
                boost += 2
        return min(boost, 10)  # Cap at 10

    def _get_recency_score(self, published: str) -> int:
        """Score based on how recent the article is."""
        try:
            from dateutil import parser
            pub_date = parser.parse(published)
            hours_ago = (datetime.utcnow() - pub_date.replace(tzinfo=None)).total_seconds() / 3600

            if hours_ago < 2:
                return 10
            elif hours_ago < 6:
                return 8
            elif hours_ago < 12:
                return 5
            else:
                return 2
        except:
            return 3

    def rank(self, articles: List[Dict]) -> List[Dict]:
        """Rank articles by relevance score."""
        for article in articles:
            source_score = self._get_source_score(article.get('source', ''))
            keyword_boost = self._get_keyword_boost(article.get('title', ''))
            recency_score = self._get_recency_score(article.get('published', ''))

            # Reddit posts have upvote scores
            reddit_score = min(article.get('score', 0) / 10, 10)

            article['relevance_score'] = (
                source_score * 2 +
                keyword_boost +
                recency_score +
                reddit_score
            )

        # Sort by relevance score
        ranked = sorted(articles, key=lambda x: x.get('relevance_score', 0), reverse=True)
        return ranked


def deduplicate_and_rank(articles: List[Dict], sent_path: str = None) -> List[Dict]:
    """Main function to deduplicate and rank articles."""
    deduplicator = ArticleDeduplicator(sent_path)
    ranker = ArticleRanker()

    unique = deduplicator.deduplicate(articles)
    ranked = ranker.rank(unique)

    return ranked
