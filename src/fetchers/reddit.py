"""
Reddit fetcher for neurotech discussions and news.
Uses public JSON API (no authentication required).
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict
import time


class RedditFetcher:
    """Fetches posts from relevant subreddits."""

    SUBREDDITS = [
        'neurotechnology',
        'BCI',
        'EEG',
        'Nootropics',
        'productivity',
        'digitalminimalism',
        'GetDisciplined',
        'biohackers'
    ]

    BASE_URL = "https://www.reddit.com/r/{subreddit}/new.json"
    HEADERS = {'User-Agent': 'NeuroNewsletter/1.0'}

    def __init__(self, hours_lookback: int = 12):
        self.hours_lookback = hours_lookback
        self.cutoff_timestamp = (datetime.utcnow() - timedelta(hours=hours_lookback)).timestamp()

    def fetch_subreddit(self, subreddit: str, limit: int = 25) -> List[Dict]:
        """Fetch recent posts from a subreddit."""
        articles = []
        url = self.BASE_URL.format(subreddit=subreddit)

        try:
            response = requests.get(
                url,
                headers=self.HEADERS,
                params={'limit': limit},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            for post in data.get('data', {}).get('children', []):
                post_data = post.get('data', {})
                created = post_data.get('created_utc', 0)

                # Skip old posts
                if created < self.cutoff_timestamp:
                    continue

                # Skip low-quality posts
                score = post_data.get('score', 0)
                if score < 5:  # Minimum upvotes
                    continue

                # Skip self-posts without meaningful content
                is_self = post_data.get('is_self', False)
                selftext = post_data.get('selftext', '')
                if is_self and len(selftext) < 100:
                    continue

                article = {
                    'title': post_data.get('title', ''),
                    'url': f"https://reddit.com{post_data.get('permalink', '')}",
                    'source': f"r/{subreddit}",
                    'published': datetime.fromtimestamp(created).isoformat(),
                    'summary': selftext[:500] if is_self else post_data.get('url', ''),
                    'score': score,
                    'fetcher': 'reddit'
                }

                # If it's a link post, use the external URL
                if not is_self and post_data.get('url'):
                    external_url = post_data.get('url', '')
                    if not external_url.startswith('https://reddit.com'):
                        article['external_url'] = external_url

                articles.append(article)

            time.sleep(1)  # Rate limiting

        except Exception as e:
            print(f"  Error fetching r/{subreddit}: {e}")

        return articles

    def fetch_all(self, max_per_subreddit: int = 10) -> List[Dict]:
        """Fetch from all configured subreddits."""
        all_articles = []

        print(f"Fetching from {len(self.SUBREDDITS)} subreddits...")

        for subreddit in self.SUBREDDITS:
            articles = self.fetch_subreddit(subreddit, limit=25)
            filtered = articles[:max_per_subreddit]

            if filtered:
                print(f"  - r/{subreddit}: {len(filtered)} posts")
                all_articles.extend(filtered)

        print(f"Total Reddit posts: {len(all_articles)}")
        return all_articles


def fetch_reddit_news(hours: int = 12) -> List[Dict]:
    """Main function to fetch Reddit posts."""
    fetcher = RedditFetcher(hours_lookback=hours)
    return fetcher.fetch_all()
