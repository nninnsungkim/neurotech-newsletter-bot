"""
Clean Slack delivery - NO HTML, NO emojis.
"""

import os
import re
import requests
from typing import List, Dict, Optional
from datetime import datetime
import pytz


def clean_text(text: str) -> str:
    """Remove ALL HTML and garbage from text."""
    if not text:
        return ''

    # Remove HTML tags
    clean = re.sub(r'<[^>]*>', '', text)
    # Remove href/src attributes
    clean = re.sub(r'href="[^"]*"', '', clean)
    clean = re.sub(r'src="[^"]*"', '', clean)
    # Remove base64 garbage
    clean = re.sub(r'CBM[a-zA-Z0-9_/-]+', '', clean)
    clean = re.sub(r'AU_[a-zA-Z0-9_/-]+', '', clean)
    # Remove URLs
    clean = re.sub(r'https?://\S+', '', clean)
    # Remove rel, class, title attributes
    clean = re.sub(r'rel="[^"]*"', '', clean)
    clean = re.sub(r'class="[^"]*"', '', clean)
    clean = re.sub(r'title="[^"]*"', '', clean)
    # Remove any remaining HTML-like stuff
    clean = re.sub(r'[<>]', '', clean)
    # Remove dots and ellipsis at start
    clean = re.sub(r'^[\s.…]+', '', clean)
    # Clean whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()

    return clean


def truncate(text: str, max_len: int = 70) -> str:
    """Truncate text to max length."""
    if len(text) <= max_len:
        return text
    return text[:max_len-3].rsplit(' ', 1)[0] + '...'


class SlackDelivery:
    """Sends clean newsletter to Slack."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.environ.get('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL not set")
        self.tz = pytz.timezone("America/New_York")

    def _format_article(self, article: Dict, index: int) -> str:
        """Format single article - CLEAN."""
        title = clean_text(article.get('title', 'Untitled'))
        title = truncate(title, 70)

        url = article.get('url', '')
        source = clean_text(article.get('source', ''))

        # Get clean bullets
        bullets = article.get('ai_summary', [])
        bullet_lines = []
        for b in bullets:
            clean_b = clean_text(b)
            if clean_b and len(clean_b) > 15:
                bullet_lines.append(f"  - {clean_b[:120]}")

        # Build article block
        lines = [f"*{index}. {title}*"]

        if bullet_lines:
            lines.extend(bullet_lines)

        lines.append(f"  <{url}|Read> | _{source}_")
        lines.append("")  # Empty line between articles

        return "\n".join(lines)

    def _build_message(self, neurotech: List[Dict], productivity: List[Dict]) -> str:
        """Build full message text."""
        now = datetime.now(self.tz)
        timestamp = now.strftime("%b %d, %Y %I:%M %p %Z")

        lines = [
            f"*APEX INTEL* | {timestamp}",
            "",
            f"*HARDWARE & NEUROTECH ({len(neurotech)})*",
            ""
        ]

        for i, article in enumerate(neurotech, 1):
            lines.append(self._format_article(article, i))

        if productivity:
            lines.extend([
                f"*PRODUCTIVITY APPS ({len(productivity)})*",
                ""
            ])

            for i, article in enumerate(productivity, 1):
                lines.append(self._format_article(article, i))

        lines.append("---")
        lines.append("_Next update in 12 hours_")

        return "\n".join(lines)

    def send(self, neurotech: List[Dict], productivity: List[Dict]) -> bool:
        """Send to Slack."""
        print(f"Sending: {len(neurotech)} neurotech, {len(productivity)} productivity")

        message = self._build_message(neurotech, productivity)

        try:
            response = requests.post(
                self.webhook_url,
                json={"text": message},
                timeout=30
            )
            response.raise_for_status()
            print("Sent successfully!")
            return True
        except Exception as e:
            print(f"Send failed: {e}")
            return False


def send_newsletter(neurotech: List[Dict], productivity: List[Dict],
                   webhook_url: Optional[str] = None) -> bool:
    """Main send function."""
    delivery = SlackDelivery(webhook_url)
    return delivery.send(neurotech, productivity)
