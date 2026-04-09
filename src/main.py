"""
APEX Competitive Intelligence Newsletter Bot
Focused on tracking competitors and relevant industry news.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from fetchers.google_news import fetch_all_news
from fetchers.rss_feeds import fetch_rss_news
from processors.deduplicator import deduplicate_and_rank, ArticleDeduplicator
from processors.classifier import classify_articles
from processors.summarizer import summarize_articles
from delivery.slack import send_newsletter


def load_config():
    """Load config files."""
    config_dir = Path(__file__).parent / 'config'

    with open(config_dir / 'keywords.json', 'r') as f:
        keywords = json.load(f)

    return keywords


def fetch_news(hours: int = 12) -> list:
    """Fetch news from all sources."""
    print("\n" + "=" * 50)
    print("FETCHING COMPETITIVE INTELLIGENCE")
    print("=" * 50)

    all_articles = []

    # Google News - focused competitor searches
    try:
        google_articles = fetch_all_news(hours)
        all_articles.extend(google_articles)
    except Exception as e:
        print(f"Error fetching Google News: {e}")

    # RSS feeds - tech publications
    try:
        keywords = load_config()
        rss_articles = fetch_rss_news(keywords, hours)
        all_articles.extend(rss_articles)
    except Exception as e:
        print(f"Error fetching RSS: {e}")

    print(f"\nTotal raw articles: {len(all_articles)}")
    return all_articles


def process_articles(articles: list, sent_path: str = None) -> dict:
    """Process: dedupe, classify, filter."""
    print("\n" + "=" * 50)
    print("FILTERING FOR RELEVANCE")
    print("=" * 50)

    # Deduplicate
    unique = deduplicate_and_rank(articles, sent_path)

    # Classify with strict APEX filter
    classified = classify_articles(unique)

    return classified


def select_articles(classified: dict, neurotech_count: int = 16,
                   productivity_count: int = 4) -> tuple:
    """Select top relevant articles."""
    neurotech = classified.get('neurotech', [])[:neurotech_count]
    productivity = classified.get('productivity', [])[:productivity_count]

    # If we don't have enough neurotech, don't pad with garbage
    # Better to have fewer quality articles

    print(f"Selected: {len(neurotech)} neurotech, {len(productivity)} productivity")
    return neurotech, productivity


def summarize(neurotech: list, productivity: list) -> tuple:
    """Generate AI summaries."""
    print("\n" + "=" * 50)
    print("GENERATING SUMMARIES")
    print("=" * 50)

    all_articles = neurotech + productivity

    if not all_articles:
        return [], []

    summarized = summarize_articles(all_articles)

    neurotech_out = summarized[:len(neurotech)]
    productivity_out = summarized[len(neurotech):]

    return neurotech_out, productivity_out


def run_newsletter(dry_run: bool = False, hours: int = 12):
    """Main pipeline."""
    now = datetime.now(timezone.utc)

    print("\n" + "=" * 50)
    print("APEX COMPETITIVE INTELLIGENCE")
    print(f"Time: {now.isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 50)

    load_dotenv()

    # Paths
    data_dir = Path(__file__).parent.parent / 'data'
    data_dir.mkdir(exist_ok=True)
    sent_path = str(data_dir / 'sent_articles.json')

    # Fetch
    articles = fetch_news(hours)

    if not articles:
        print("\nNo articles found.")
        return False

    # Process
    classified = process_articles(articles, sent_path)

    # Select
    neurotech, productivity = select_articles(classified)

    if not neurotech and not productivity:
        print("\nNo relevant articles after filtering.")
        return False

    # Summarize
    neurotech, productivity = summarize(neurotech, productivity)

    # Deliver
    print("\n" + "=" * 50)
    print("DELIVERY")
    print("=" * 50)

    if dry_run:
        print("\n[DRY RUN] Would send:\n")

        print(f"NEUROTECH ({len(neurotech)}):")
        for i, a in enumerate(neurotech, 1):
            print(f"  {i}. {a['title'][:70]}")
            print(f"     URL: {a['url'][:80]}")
            print(f"     Reason: {a.get('classification_reason', 'N/A')}")
            bullets = a.get('ai_summary', [])
            for b in bullets:
                if b and len(b) > 10:
                    print(f"     • {b[:100]}")
            print()

        print(f"PRODUCTIVITY ({len(productivity)}):")
        for i, a in enumerate(productivity, 1):
            print(f"  {i}. {a['title'][:70]}")
            print(f"     URL: {a['url'][:80]}")
            print(f"     Reason: {a.get('classification_reason', 'N/A')}")
            bullets = a.get('ai_summary', [])
            for b in bullets:
                if b and len(b) > 10:
                    print(f"     • {b[:100]}")
            print()

        return True

    # Send to Slack
    success = send_newsletter(neurotech, productivity)

    if success:
        deduplicator = ArticleDeduplicator(sent_path)
        deduplicator.mark_as_sent(neurotech + productivity)
        print("\nNewsletter sent!")
    else:
        print("\nFailed to send.")

    return success


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="APEX Competitive Intelligence Bot")
    parser.add_argument('--dry-run', action='store_true', help="Don't send to Slack")
    parser.add_argument('--hours', type=int, default=12, help="Hours lookback")

    args = parser.parse_args()
    success = run_newsletter(dry_run=args.dry_run, hours=args.hours)
    sys.exit(0 if success else 1)
