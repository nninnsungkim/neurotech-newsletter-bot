"""
Clean Slack delivery - Neurotech only.
"""

import os
import requests
import re
from typing import List, Dict
from datetime import datetime
import pytz


def clean_title(title: str) -> str:
    """Remove all HTML and truncate."""
    # Remove HTML completely
    clean = re.sub(r'<[^>]*>', '', title)
    # Remove any leftover attributes
    clean = re.sub(r'href=|src=|class=|rel=', '', clean)
    # Remove quotes and weird chars
    clean = re.sub(r'["""\'<>]', '', clean)
    # Clean whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    # Truncate
    if len(clean) > 80:
        clean = clean[:77] + '...'
    return clean


class SlackDelivery:
    """Clean Slack delivery."""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or os.environ.get('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL not set")

    def _format_article(self, article: Dict, index: int) -> str:
        """Format: number. title | Read more"""
        title = clean_title(article.get('title', 'Untitled'))
        url = article.get('url', '')

        # Just title + link, nothing else
        return f"{index}. {title} | <{url}|Read more>"

    def _build_message(self, articles: List[Dict]) -> str:
        """Build message."""
        now = datetime.now(pytz.timezone("America/New_York"))
        timestamp = now.strftime("%b %d, %I:%M %p %Z")

        lines = [
            f"*APEX COMPETITIVE INTEL* | {timestamp}",
            "",
            f"*NEUROTECH ({len(articles)})*"
        ]

        for i, article in enumerate(articles, 1):
            lines.append(self._format_article(article, i))

        lines.append("")
        lines.append("_Next update in 12h_")

        return "\n".join(lines)

    def send(self, articles: List[Dict]) -> bool:
        """Send to Slack."""
        message = self._build_message(articles)

        try:
            response = requests.post(
                self.webhook_url,
                json={"text": message},
                timeout=30
            )
            response.raise_for_status()
            print("Sent to Slack")
            return True
        except Exception as e:
            print(f"Failed: {e}")
            return False


def send_newsletter(articles: List[Dict], webhook_url: str = None) -> bool:
    """Send newsletter."""
    delivery = SlackDelivery(webhook_url)
    return delivery.send(articles)
