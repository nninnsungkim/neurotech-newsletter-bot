"""
APEX Competitive Intelligence - Company-focused approach.
Scrapes actual company websites + exact Google searches.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from fetchers.google_news import fetch_all_news
from fetchers.company_scraper import scrape_company_updates
from processors.deduplicator import deduplicate_and_rank, ArticleDeduplicator
from processors.classifier import classify_articles
from delivery.slack import send_newsletter


def fetch_news(hours: int = 24) -> list:
    """Fetch from company sites + exact searches."""
    print("\n" + "=" * 50)
    print("FETCHING COMPANY UPDATES")
    print("=" * 50)

    all_articles = []

    # 1. Scrape actual company websites/blogs
    try:
        print("\n[1] Scraping company websites...")
        company_articles = scrape_company_updates(hours=hours, max_companies=40)
        all_articles.extend(company_articles)
    except Exception as e:
        print(f"Error scraping companies: {e}")

    # 2. Exact company Google searches
    try:
        print("\n[2] Exact company Google searches...")
        google_articles = fetch_all_news(hours)
        all_articles.extend(google_articles)
    except Exception as e:
        print(f"Error with Google search: {e}")

    print(f"\nTotal raw articles: {len(all_articles)}")
    return all_articles


def process_articles(articles: list, sent_path: str = None) -> dict:
    """Dedupe and classify."""
    print("\n" + "=" * 50)
    print("PROCESSING")
    print("=" * 50)

    unique = deduplicate_and_rank(articles, sent_path)
    classified = classify_articles(unique)
    return classified


def select_articles(classified: dict, neurotech_count: int = 11, software_count: int = 4) -> tuple:
    """Select top articles."""
    neurotech = classified.get('neurotech', [])[:neurotech_count]
    software = classified.get('productivity', [])[:software_count]

    print(f"Selected: {len(neurotech)} neurotech, {len(software)} software")
    return neurotech, software


def run_newsletter(dry_run: bool = False, hours: int = 24):
    """Main pipeline."""
    now = datetime.now(timezone.utc)

    print("\n" + "=" * 50)
    print("APEX COMPETITIVE INTELLIGENCE")
    print(f"Time: {now.isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 50)

    load_dotenv()

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

    # Select best 15
    neurotech, software = select_articles(classified)

    if not neurotech and not software:
        print("\nNo relevant articles.")
        return False

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
            print(f"     Source: {a.get('source', a.get('company', 'Unknown'))}")
            print()

        print(f"SOFTWARE ({len(software)}):")
        for i, a in enumerate(software, 1):
            print(f"  {i}. {a['title'][:70]}")
            print(f"     URL: {a['url'][:80]}")
            print()

        return True

    success = send_newsletter(neurotech, software)

    if success:
        deduplicator = ArticleDeduplicator(sent_path)
        deduplicator.mark_as_sent(neurotech + software)
        print("Newsletter sent!")

    return success


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--hours', type=int, default=24)

    args = parser.parse_args()
    success = run_newsletter(dry_run=args.dry_run, hours=args.hours)
    sys.exit(0 if success else 1)
