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

from fetchers.google_news import fetch_tiered_news
from processors.deduplicator import deduplicate_and_rank, ArticleDeduplicator
from delivery.slack import send_newsletter


def fetch_news(hours: int = 12) -> tuple:
    """Fetch from tiered company research."""
    print("\n" + "=" * 50)
    print("FETCHING COMPANY NEWS")
    print("=" * 50)

    tier1_articles, tier2_articles = fetch_tiered_news(hours, min_total=15)

    print(f"\nTotal: {len(tier1_articles)} Tier 1 + {len(tier2_articles)} Tier 2")
    return tier1_articles, tier2_articles


def process_articles(tier1: list, tier2: list, sent_path: str = None) -> list:
    """Dedupe and combine articles."""
    print("\n" + "=" * 50)
    print("PROCESSING")
    print("=" * 50)

    # Combine: Tier 1 first, then Tier 2
    all_articles = tier1 + tier2

    # Deduplicate
    unique = deduplicate_and_rank(all_articles, sent_path)

    print(f"After dedup: {len(unique)} articles")
    return unique


def run_newsletter(dry_run: bool = False, hours: int = 12):
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

    # Deliver
    print("\n" + "=" * 50)
    print("DELIVERY")
    print("=" * 50)

    if dry_run:
        print(f"\n[DRY RUN] Would send {len(articles)} articles:\n")

        for i, a in enumerate(articles, 1):
            print(f"  {i}. {a['title'][:70]}")
            print(f"     Company: {a.get('company', 'Unknown')}")
            print(f"     URL: {a['url'][:80]}")
            print()

        return True

    success = send_newsletter(articles)

    if success:
        deduplicator = ArticleDeduplicator(sent_path)
        deduplicator.mark_as_sent(articles)
        print("Newsletter sent!")

    return success


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--hours', type=int, default=12)

    args = parser.parse_args()
    success = run_newsletter(dry_run=args.dry_run, hours=args.hours)
    sys.exit(0 if success else 1)
