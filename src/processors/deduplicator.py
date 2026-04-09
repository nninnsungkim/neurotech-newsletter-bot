"""
Deduplication with source quality ranking.
When similar articles exist, picks the more trustworthy source.
"""

from typing import List, Dict, Set
from fuzzywuzzy import fuzz
from urllib.parse import urlparse
import hashlib
import json
import os
from datetime import datetime, timedelta


# Source trustworthiness ranking (higher = better)
SOURCE_QUALITY = {
    # Tier 1: Major tech publications
    'techcrunch': 10,
    'wired': 10,
    'the verge': 10,
    'mit technology review': 10,
    'ieee spectrum': 10,
    'venturebeat': 9,
    'ars technica': 9,
    'bloomberg': 10,
    'reuters': 10,
    'forbes': 8,

    # Tier 2: Health tech / industry specific
    'mobihealthnews': 8,
    'medgadget': 8,
    'fiercebiotech': 8,
    'medical device network': 8,
    'neuroscience news': 7,

    # Tier 3: Company blogs (direct source)
    'blog': 7,
    'rss': 7,
    'linkedin': 6,

    # Tier 4: Default
    'default': 5,
}


def get_source_score(source: str) -> int:
    """Get quality score for a source."""
    source_lower = source.lower()
    for name, score in SOURCE_QUALITY.items():
        if name in source_lower:
            return score
    return SOURCE_QUALITY['default']


class ArticleDeduplicator:
    """Deduplicates and picks best sources."""

    def __init__(self, sent_path: str = None):
        self.sent_path = sent_path or 'data/sent_articles.json'
        self.sent_urls: Set[str] = set()
        self.sent_hashes: Set[str] = set()
        self._load_sent()

    def _load_sent(self):
        """Load previously sent articles."""
        try:
            if os.path.exists(self.sent_path):
                with open(self.sent_path, 'r') as f:
                    data = json.load(f)
                cutoff = (datetime.utcnow() - timedelta(days=3)).isoformat()
                recent = [a for a in data if a.get('sent_at', '') > cutoff]
                self.sent_urls = {a['url'] for a in recent}
                self.sent_hashes = {a.get('hash', '') for a in recent}
        except:
            pass

    def _hash_title(self, title: str) -> str:
        """Hash title for comparison."""
        clean = title.lower().strip()
        return hashlib.md5(clean.encode()).hexdigest()[:12]

    def _normalize_url(self, url: str) -> str:
        """Normalize URL."""
        parsed = urlparse(url)
        return f"{parsed.netloc}{parsed.path}".lower().rstrip('/')

    def _is_similar(self, t1: str, t2: str, threshold: int = 70) -> bool:
        """Check if titles are similar."""
        return fuzz.ratio(t1.lower(), t2.lower()) >= threshold

    def _was_sent(self, article: Dict) -> bool:
        """Check if already sent."""
        url = self._normalize_url(article.get('url', ''))
        title_hash = self._hash_title(article.get('title', ''))
        return url in self.sent_urls or title_hash in self.sent_hashes

    def deduplicate(self, articles: List[Dict]) -> List[Dict]:
        """Remove duplicates, keeping best source for similar content."""
        # First, remove exact URL duplicates
        seen_urls: Set[str] = set()
        unique = []

        for article in articles:
            url = self._normalize_url(article.get('url', ''))
            if url in seen_urls:
                continue
            if self._was_sent(article):
                continue
            seen_urls.add(url)
            unique.append(article)

        # Now handle similar titles - keep the better source
        final = []
        used_indices = set()

        for i, article in enumerate(unique):
            if i in used_indices:
                continue

            title = article.get('title', '')
            best = article
            best_score = get_source_score(article.get('source', ''))

            # Check remaining articles for similarity
            for j in range(i + 1, len(unique)):
                if j in used_indices:
                    continue

                other = unique[j]
                other_title = other.get('title', '')

                if self._is_similar(title, other_title):
                    other_score = get_source_score(other.get('source', ''))
                    if other_score > best_score:
                        best = other
                        best_score = other_score
                    used_indices.add(j)

            final.append(best)
            used_indices.add(i)

        print(f"Deduplication: {len(articles)} -> {len(final)} articles")
        return final

    def mark_as_sent(self, articles: List[Dict]):
        """Mark articles as sent."""
        try:
            existing = []
            if os.path.exists(self.sent_path):
                with open(self.sent_path, 'r') as f:
                    existing = json.load(f)

            now = datetime.utcnow().isoformat()
            for article in articles:
                existing.append({
                    'url': self._normalize_url(article.get('url', '')),
                    'hash': self._hash_title(article.get('title', '')),
                    'sent_at': now
                })

            # Keep last 3 days
            cutoff = (datetime.utcnow() - timedelta(days=3)).isoformat()
            existing = [a for a in existing if a.get('sent_at', '') > cutoff]

            os.makedirs(os.path.dirname(self.sent_path), exist_ok=True)
            with open(self.sent_path, 'w') as f:
                json.dump(existing, f)
        except Exception as e:
            print(f"Error saving sent: {e}")


class ArticleRanker:
    """Ranks articles by relevance and quality."""

    def rank(self, articles: List[Dict]) -> List[Dict]:
        """Rank articles."""
        for article in articles:
            source_score = get_source_score(article.get('source', ''))
            article['quality_score'] = source_score

        return sorted(articles, key=lambda x: x.get('quality_score', 0), reverse=True)


def deduplicate_and_rank(articles: List[Dict], sent_path: str = None) -> List[Dict]:
    """Main function."""
    dedup = ArticleDeduplicator(sent_path)
    ranker = ArticleRanker()

    unique = dedup.deduplicate(articles)
    ranked = ranker.rank(unique)

    return ranked
