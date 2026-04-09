"""
Main orchestrator for the Neurotech Newsletter Bot.
Fetches, processes, and delivers the newsletter.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from fetchers import (
    fetch_neurotech_news,
    fetch_productivity_news,
    fetch_rss_news,
    fetch_reddit_news
)
from processors import (
    deduplicate_and_rank,
    classify_articles,
    summarize_articles
)
from delivery import send_newsletter, SlackDelivery


def load_config():
    """Load configuration files."""
    config_dir = Path(__file__).parent / 'config'

    with open(config_dir / 'keywords.json', 'r') as f:
        keywords = json.load(f)

    with open(config_dir / 'companies.json', 'r') as f:
        companies = json.load(f)

    return keywords, companies


def fetch_all_news(keywords: dict, hours: int = 12) -> list:
    """Fetch news from all sources."""
    all_articles = []

    print("\n" + "="*50)
    print("FETCHING NEWS")
    print("="*50)

    # Google News
    try:
        neurotech_news = fetch_neurotech_news(keywords, hours)
        all_articles.extend(neurotech_news)
    except Exception as e:
        print(f"Error fetching neurotech news: {e}")

    try:
        productivity_news = fetch_productivity_news(keywords, hours)
        all_articles.extend(productivity_news)
    except Exception as e:
        print(f"Error fetching productivity news: {e}")

    # RSS Feeds
    try:
        rss_news = fetch_rss_news(keywords, hours)
        all_articles.extend(rss_news)
    except Exception as e:
        print(f"Error fetching RSS news: {e}")

    # Reddit - disabled due to API restrictions on GitHub Actions
    # Uncomment if running locally
    # try:
    #     reddit_news = fetch_reddit_news(hours)
    #     all_articles.extend(reddit_news)
    # except Exception as e:
    #     print(f"Error fetching Reddit news: {e}")
    print("Reddit: Skipped (API restrictions)")

    print(f"\nTotal raw articles: {len(all_articles)}")
    return all_articles


def process_articles(articles: list, sent_path: str = None) -> dict:
    """Process articles: dedupe, classify, rank."""
    print("\n" + "="*50)
    print("PROCESSING ARTICLES")
    print("="*50)

    # Deduplicate and rank
    unique_articles = deduplicate_and_rank(articles, sent_path)

    # Classify into categories
    classified = classify_articles(unique_articles)

    return classified


def select_top_articles(classified: dict, neurotech_count: int = 16,
                       productivity_count: int = 4) -> tuple:
    """Select top articles for each category."""
    neurotech = classified.get('neurotech', [])[:neurotech_count]
    productivity = classified.get('productivity', [])[:productivity_count]

    # If not enough productivity, fill with unknown that might be relevant
    if len(productivity) < productivity_count:
        unknown = classified.get('unknown', [])
        for article in unknown:
            if len(productivity) >= productivity_count:
                break
            productivity.append(article)

    # If not enough neurotech, try unknown
    if len(neurotech) < neurotech_count:
        unknown = classified.get('unknown', [])
        for article in unknown:
            if len(neurotech) >= neurotech_count:
                break
            if article not in productivity:
                neurotech.append(article)

    print(f"\nSelected: {len(neurotech)} neurotech, {len(productivity)} productivity")
    return neurotech, productivity


def summarize_selected(neurotech: list, productivity: list) -> tuple:
    """Summarize selected articles using AI."""
    print("\n" + "="*50)
    print("SUMMARIZING ARTICLES")
    print("="*50)

    all_selected = neurotech + productivity
    summarized = summarize_articles(all_selected)

    # Split back
    neurotech_summarized = summarized[:len(neurotech)]
    productivity_summarized = summarized[len(neurotech):]

    return neurotech_summarized, productivity_summarized


def run_newsletter(dry_run: bool = False, hours: int = 12):
    """Main function to run the newsletter pipeline."""
    print("\n" + "="*50)
    print(f"NEUROTECH NEWSLETTER BOT")
    print(f"Time: {datetime.utcnow().isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("="*50)

    # Load environment variables
    load_dotenv()

    # Load config
    keywords, companies = load_config()

    # Set up paths
    data_dir = Path(__file__).parent.parent / 'data'
    data_dir.mkdir(exist_ok=True)
    sent_path = str(data_dir / 'sent_articles.json')

    # Fetch
    articles = fetch_all_news(keywords, hours)

    if not articles:
        print("\nNo articles found. Exiting.")
        return False

    # Process
    classified = process_articles(articles, sent_path)

    # Select top articles
    neurotech, productivity = select_top_articles(classified)

    if not neurotech and not productivity:
        print("\nNo relevant articles after processing. Exiting.")
        return False

    # Summarize
    neurotech, productivity = summarize_selected(neurotech, productivity)

    # Deliver
    print("\n" + "="*50)
    print("DELIVERING NEWSLETTER")
    print("="*50)

    if dry_run:
        print("\n[DRY RUN] Would send the following:\n")
        print(f"NEUROTECH ({len(neurotech)} articles):")
        for i, article in enumerate(neurotech, 1):
            print(f"  {i}. {article['title'][:60]}...")
            for bullet in article.get('ai_summary', []):
                if bullet:
                    print(f"     • {bullet}")

        print(f"\nPRODUCTIVITY ({len(productivity)} articles):")
        for i, article in enumerate(productivity, 1):
            print(f"  {i}. {article['title'][:60]}...")
            for bullet in article.get('ai_summary', []):
                if bullet:
                    print(f"     • {bullet}")
        return True

    # Send to Slack
    success = send_newsletter(neurotech, productivity)

    if success:
        # Mark articles as sent
        from processors.deduplicator import ArticleDeduplicator
        deduplicator = ArticleDeduplicator(sent_path)
        deduplicator.mark_as_sent(neurotech + productivity)
        print("\nNewsletter delivered successfully!")
    else:
        print("\nFailed to deliver newsletter.")

    return success


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Neurotech Newsletter Bot")
    parser.add_argument('--dry-run', action='store_true',
                       help="Run without sending to Slack")
    parser.add_argument('--hours', type=int, default=12,
                       help="Hours of news to look back (default: 12)")

    args = parser.parse_args()

    success = run_newsletter(dry_run=args.dry_run, hours=args.hours)
    sys.exit(0 if success else 1)
