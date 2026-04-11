"""
APEX Competitive Intelligence - Tiered company research.
Tier 1: Wearable Consumer/Medical + EEG/neurofeedback/tDCS/etc (no limit)
Tier 2: Other neurotech companies (fill to 15)
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from fetchers.google_news_rss import fetch_tiered_news
from processors.deduplicator import deduplicate_and_rank, ArticleDeduplicator
from processors.ai_filter import ai_filter_articles, generate_summary
from delivery.slack import send_newsletter


def fetch_news(hours: int = 72) -> tuple:
    """Fetch from tiered company research with batch rotation."""
    print("\n" + "=" * 50)
    print("FETCHING COMPANY NEWS (BATCH ROTATION)")
    print("=" * 50)

    tier1_articles, tier2_articles = fetch_tiered_news(hours, min_total=15)

    print(f"\nTotal: {len(tier1_articles)} Tier 1 + {len(tier2_articles)} Tier 2")
    return tier1_articles, tier2_articles


def process_articles(tier1: list, tier2: list, sent_path: str = None) -> list:
    """Dedupe, AI filter, and combine articles."""
    print("\n" + "=" * 50)
    print("PROCESSING")
    print("=" * 50)

    # Combine: Tier 1 first, then Tier 2
    all_articles = tier1 + tier2

    # Deduplicate first
    unique = deduplicate_and_rank(all_articles, sent_path)
    print(f"After dedup: {len(unique)} articles")

    # AI filter for relevance and importance
    if unique:
        print("\n[AI FILTER] Evaluating articles...")
        filtered = ai_filter_articles(unique, max_select=15)
        print(f"AI selected: {len(filtered)} top articles")
        return filtered

    return unique


def run_newsletter(dry_run: bool = False, hours: int = 72):
    """Main pipeline."""
    now = datetime.now(timezone.utc)

    print("\n" + "=" * 50)
    print("APEX COMPETITIVE INTELLIGENCE")
    print(f"Time: {now.isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Lookback: {hours}h")
    print("=" * 50)

    load_dotenv()

    data_dir = Path(__file__).parent.parent / 'data'
    data_dir.mkdir(exist_ok=True)
    sent_path = str(data_dir / 'sent_articles.json')

    # Fetch
    tier1, tier2 = fetch_news(hours)

    if not tier1 and not tier2:
        print("\nNo articles found.")
        return False

    # Process
    articles = process_articles(tier1, tier2, sent_path)

    if not articles:
        print("\nNo unique articles after dedup.")
        return False

    # Generate AI summary
    print("\n" + "=" * 50)
    print("GENERATING SUMMARY")
    print("=" * 50)

    summary = generate_summary(articles)
    if summary:
        print(f"Summary ({len(summary)} chars):\n{summary[:200]}...")
    else:
        summary = "_No significant neurotech updates today._"

    # Deliver
    print("\n" + "=" * 50)
    print("DELIVERY")
    print("=" * 50)

    if dry_run:
        print(f"\n[DRY RUN] Summary:\n{summary}\n")
        print(f"Sources ({len(articles)}):")
        for a in articles:
            print(f"  - {a['title'][:60]}")
        return True

    success = send_newsletter(articles, summary)

    if success:
        deduplicator = ArticleDeduplicator(sent_path)
        deduplicator.mark_as_sent(articles)
        print("Newsletter sent!")

    return success


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--hours', type=int, default=72)

    args = parser.parse_args()
    success = run_newsletter(dry_run=args.dry_run, hours=args.hours)
    sys.exit(0 if success else 1)
