"""
Slack delivery module using incoming webhooks.
"""

import os
import requests
from typing import List, Dict, Optional
from datetime import datetime
import pytz


class SlackDelivery:
    """Delivers formatted newsletter to Slack."""

    def __init__(self, webhook_url: Optional[str] = None, timezone: str = "America/New_York"):
        self.webhook_url = webhook_url or os.environ.get('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL not set")

        self.timezone = pytz.timezone(timezone)

    def _get_timestamp(self) -> str:
        """Get formatted timestamp in EST."""
        now = datetime.now(self.timezone)
        return now.strftime("%B %d, %Y • %I:%M %p %Z")

    def _truncate_title(self, title: str, max_len: int = 60) -> str:
        """Truncate title to max length."""
        if len(title) <= max_len:
            return title
        return title[:max_len-3].rsplit(' ', 1)[0] + '...'

    def _clean_bullet(self, bullet: str) -> str:
        """Clean HTML and garbage from bullet text."""
        import re
        if not bullet:
            return ''
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', bullet)
        # Remove URLs
        clean = re.sub(r'https?://\S+', '', clean)
        # Remove extra whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Skip if too short or looks like garbage
        if len(clean) < 10 or clean.startswith('CBM') or clean.startswith('AU_'):
            return ''
        return clean

    def _format_article(self, article: Dict, index: int) -> str:
        """Format a single article for Slack."""
        title = self._truncate_title(article.get('title', 'Untitled'))
        url = article.get('url', '')
        source = article.get('source', 'Unknown')
        bullets = article.get('ai_summary', [])

        # Format bullets - only include clean, valid ones
        bullet_text = ""
        for bullet in bullets:
            clean = self._clean_bullet(bullet)
            if clean:
                bullet_text += f"    • {clean}\n"

        # If no valid bullets, skip bullet section
        if not bullet_text:
            return f"*{index}. {title}*\n    <{url}|Read more> · _{source}_\n\n"

        return f"*{index}. {title}*\n{bullet_text}    <{url}|Read more> · _{source}_\n\n"

    def _build_message(self, neurotech: List[Dict], productivity: List[Dict]) -> Dict:
        """Build the full Slack message payload."""
        timestamp = self._get_timestamp()

        # Header
        header = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
:brain: *NEUROTECH & PRODUCTIVITY INTEL*
{timestamp}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

        # Neurotech section
        neurotech_section = "\n:zap: *NEUROTECH* ({} items)\n\n".format(len(neurotech))
        for i, article in enumerate(neurotech, 1):
            neurotech_section += self._format_article(article, i)

        # Divider
        divider = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        # Productivity section
        productivity_section = ":iphone: *PRODUCTIVITY SOFTWARE* ({} items)\n\n".format(len(productivity))
        for i, article in enumerate(productivity, 1):
            productivity_section += self._format_article(article, i)

        # Footer
        footer = """━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_Automated newsletter • Next update in 12 hours_"""

        # Combine all sections
        full_text = header + neurotech_section + divider + productivity_section + footer

        # Slack message payload
        return {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": header
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": neurotech_section
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": productivity_section
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": footer
                    }
                }
            ],
            "text": f"Neurotech & Productivity Intel - {timestamp}"  # Fallback
        }

    def _build_simple_message(self, neurotech: List[Dict], productivity: List[Dict]) -> Dict:
        """Build a simpler text-based message (fallback for long content)."""
        timestamp = self._get_timestamp()

        lines = [
            f"*NEUROTECH INTEL* | {timestamp}",
            "",
            f"*— HARDWARE & BCI ({len(neurotech)}) —*",
            ""
        ]

        for i, article in enumerate(neurotech, 1):
            lines.append(self._format_article(article, i))

        lines.extend([
            f"*— PRODUCTIVITY APPS ({len(productivity)}) —*",
            ""
        ])

        for i, article in enumerate(productivity, 1):
            lines.append(self._format_article(article, i))

        lines.extend([
            "---",
            "_Next update in 12 hours_"
        ])

        return {"text": "\n".join(lines)}

    def send(self, neurotech: List[Dict], productivity: List[Dict]) -> bool:
        """Send the newsletter to Slack."""
        print(f"Sending newsletter: {len(neurotech)} neurotech, {len(productivity)} productivity")

        # Use simple message format for reliability
        payload = self._build_simple_message(neurotech, productivity)

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            print("Newsletter sent successfully!")
            return True

        except requests.exceptions.RequestException as e:
            print(f"Failed to send to Slack: {e}")
            return False

    def send_error_notification(self, error_message: str) -> bool:
        """Send an error notification to Slack."""
        payload = {
            "text": f":warning: *Newsletter Bot Error*\n\n{error_message}"
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )
            return response.status_code == 200
        except:
            return False


def send_newsletter(neurotech: List[Dict], productivity: List[Dict],
                   webhook_url: Optional[str] = None) -> bool:
    """Main function to send newsletter."""
    delivery = SlackDelivery(webhook_url)
    return delivery.send(neurotech, productivity)
