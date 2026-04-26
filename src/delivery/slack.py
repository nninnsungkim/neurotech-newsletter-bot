"""
Slack delivery - AI summary + links.
"""

import os
import requests
import re
from typing import List, Dict
from datetime import datetime
import pytz


def clean_title(title: str) -> str:
    """Remove HTML and clean up."""
    clean = re.sub(r'<[^>]*>', '', title)
    clean = re.sub(r'["""\'<>]', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:80] if len(clean) > 80 else clean


def clean_description(text: str, limit: int = 180) -> str:
    """Clean article snippets for Slack source context."""
    if not text:
        return ""

    clean = re.sub(r'<[^>]*>', ' ', text)
    clean = re.sub(r'["<>]', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    if len(clean) > limit:
        return clean[:limit - 3].rstrip() + "..."
    return clean


class SlackDelivery:
    """Slack delivery with AI summary."""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or os.environ.get('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL not set")

    def _build_summary_message(self, summary: str) -> str:
        """Build main summary message."""
        now = datetime.now(pytz.timezone("America/New_York"))
        timestamp = now.strftime("%b %d")

        return f"*APEX Neurotech Intel* | {timestamp}\n\n{summary}"

    def _build_links_message(self, articles: List[Dict]) -> str:
        """Build links message."""
        lines = ["*Sources:*"]
        for a in articles:
            title = clean_title(a.get('title', ''))[:60]
            url = a.get('url', '')
            link = f"<{url}|{title}>" if url else title
            description = clean_description(
                a.get('summary', '') or a.get('description', '') or a.get('ai_reason', '')
            )
            lines.append(f"- {link}")
            if description:
                lines.append(f"  {description}")
        return "\n".join(lines)

    def send(self, articles: List[Dict], summary: str = None) -> bool:
        """Send summary + links to Slack."""
        if not summary:
            summary = "_No significant updates today._"

        try:
            # Message 1: Summary
            resp1 = requests.post(
                self.webhook_url,
                json={"text": self._build_summary_message(summary)},
                timeout=30
            )
            resp1.raise_for_status()

            # Message 2: Links (only if we have articles)
            if articles:
                resp2 = requests.post(
                    self.webhook_url,
                    json={"text": self._build_links_message(articles)},
                    timeout=30
                )
                resp2.raise_for_status()

            print("Sent to Slack")
            return True
        except Exception as e:
            print(f"Failed: {e}")
            return False


def send_newsletter(articles: List[Dict], summary: str = None, webhook_url: str = None) -> bool:
    """Send newsletter with summary."""
    delivery = SlackDelivery(webhook_url)
    return delivery.send(articles, summary)


def send_opportunities(vc_fellowships: List[Dict], pitch_competitions: List[Dict],
                       summary: str = None, webhook_url: str = None) -> bool:
    """Send opportunities digest to Slack."""
    webhook = webhook_url or os.environ.get('SLACK_WEBHOOK_URL_OPPORTUNITIES')
    if not webhook:
        print("SLACK_WEBHOOK_URL_OPPORTUNITIES not set")
        return False

    now = datetime.now(pytz.timezone("America/New_York"))
    timestamp = now.strftime("%b %d")

    try:
        # Message 1: Summary
        header = f"*APEX Opportunity Tracker* | {timestamp}\n\n"
        summary_text = summary if summary else "_No new opportunities found today._"

        resp1 = requests.post(
            webhook,
            json={"text": header + summary_text},
            timeout=30
        )
        resp1.raise_for_status()

        # Message 2: VC Fellowship links
        if vc_fellowships:
            lines = ["*VC Fellowships & Accelerators:*"]
            for opp in vc_fellowships[:15]:
                title = clean_title(opp.get('title', ''))[:60]
                url = opp.get('url', '')
                score = opp.get('relevance_score', '')
                score_str = f" [{score}/10]" if score else ""
                lines.append(f"• <{url}|{title}>{score_str}")

            resp2 = requests.post(
                webhook,
                json={"text": "\n".join(lines)},
                timeout=30
            )
            resp2.raise_for_status()

        # Message 3: Pitch competition links
        if pitch_competitions:
            lines = ["*Pitch Competitions (Purdue/Indiana):*"]
            for opp in pitch_competitions[:10]:
                title = clean_title(opp.get('title', ''))[:60]
                url = opp.get('url', '')
                lines.append(f"• <{url}|{title}>")

            resp3 = requests.post(
                webhook,
                json={"text": "\n".join(lines)},
                timeout=30
            )
            resp3.raise_for_status()

        print("Sent to Slack #development-business")
        return True

    except Exception as e:
        print(f"Failed: {e}")
        return False
