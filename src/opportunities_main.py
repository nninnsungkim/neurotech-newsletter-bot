"""
APEX Opportunity Tracker

Tracks:
- VC Fellowships (US + Korea major) - Spring builder programs, pre-seed/idea stage
- Pitch Competitions (Purdue/Indiana only)

Delivers to Slack #development-business daily
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from fetchers.opportunities import fetch_all_opportunities
from processors.opportunity_filter import filter_opportunities, generate_opportunity_summary
from processors.deduplicator import ArticleDeduplicator
from delivery.slack import send_opportunities


def run_opportunity_tracker(dry_run: bool = False, hours: int = 168):
    """Main pipeline for opportunity tracking."""
    now = datetime.now(timezone.utc)

    print("\n" + "=" * 50)
    print("APEX OPPORTUNITY TRACKER")
    print(f"Time: {now.isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Lookback: {hours}h")
    print("=" * 50)

    load_dotenv()

    data_dir = Path(__file__).parent.parent / 'data'
    data_dir.mkdir(exist_ok=True)
    sent_path = str(data_dir / 'sent_opportunities.json')

    # Fetch opportunities
    print("\n" + "=" * 50)
    print("FETCHING OPPORTUNITIES")
    print("=" * 50)

    vc_fellowships, pitch_competitions = fetch_all_opportunities(hours)

    total_raw = len(vc_fellowships) + len(pitch_competitions)
    if total_raw == 0:
        print("\nNo opportunities found.")
        return False

    # Deduplicate
    print("\n" + "=" * 50)
    print("DEDUPLICATION")
    print("=" * 50)

    deduplicator = ArticleDeduplicator(sent_path)

    vc_unique = deduplicator.deduplicate(vc_fellowships)
    pitch_unique = deduplicator.deduplicate(pitch_competitions)

    print(f"VC Fellowships: {len(vc_fellowships)} -> {len(vc_unique)} unique")
    print(f"Pitch Competitions: {len(pitch_competitions)} -> {len(pitch_unique)} unique")

    if not vc_unique and not pitch_unique:
        print("\nNo new opportunities after dedup.")
        return False

    # AI Filter
    print("\n" + "=" * 50)
    print("AI FILTERING")
    print("=" * 50)

    if vc_unique:
        print("\n[Filtering VC Fellowships...]")
        vc_filtered = filter_opportunities(vc_unique, 'vc_fellowship')
        print(f"VC Fellowships: {len(vc_unique)} -> {len(vc_filtered)} relevant")
    else:
        vc_filtered = []

    if pitch_unique:
        print("\n[Filtering Pitch Competitions...]")
        pitch_filtered = filter_opportunities(pitch_unique, 'pitch_competition')
        print(f"Pitch Competitions: {len(pitch_unique)} -> {len(pitch_filtered)} relevant")
    else:
        pitch_filtered = []

    if not vc_filtered and not pitch_filtered:
        print("\nNo relevant opportunities after filtering.")
        return False

    # Generate summary
    print("\n" + "=" * 50)
    print("GENERATING SUMMARY")
    print("=" * 50)

    summary = generate_opportunity_summary(vc_filtered, pitch_filtered)
    if summary:
        print(f"Summary ({len(summary)} chars):\n{summary[:300]}...")
    else:
        summary = "_No significant opportunities found today._"

    # Deliver
    print("\n" + "=" * 50)
    print("DELIVERY")
    print("=" * 50)

    if dry_run:
        print(f"\n[DRY RUN] Summary:\n{summary}\n")
        print(f"\nVC Fellowships ({len(vc_filtered)}):")
        for o in vc_filtered[:10]:
            score = o.get('relevance_score', '')
            print(f"  [{score}] {o['title'][:70]}")
        print(f"\nPitch Competitions ({len(pitch_filtered)}):")
        for o in pitch_filtered[:5]:
            print(f"  - {o['title'][:70]}")
        return True

    success = send_opportunities(vc_filtered, pitch_filtered, summary)

    if success:
        # Mark as sent
        all_sent = vc_filtered + pitch_filtered
        deduplicator.mark_as_sent(all_sent)
        print("Opportunities sent!")

    return success


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--hours', type=int, default=168,
                        help='Lookback hours (default 168 = 1 week)')

    args = parser.parse_args()
    success = run_opportunity_tracker(dry_run=args.dry_run, hours=args.hours)
    sys.exit(0 if success else 1)
