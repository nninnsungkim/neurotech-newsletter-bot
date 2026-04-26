"""
AI-powered summarization using Claude Haiku.
Generates concise 3-bullet summaries for each article.
"""

import os
from typing import List, Dict, Optional
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential
import time
from .anthropic_utils import create_message_with_fallback, get_model_candidates


class ArticleSummarizer:
    """Summarizes articles using Claude Haiku."""

    SYSTEM_PROMPT = """You are a concise tech news summarizer for a neurotech and productivity newsletter.

Your task: Summarize the article in EXACTLY 3 bullet points.

Rules:
- Each bullet must be ONE sentence, max 20 words
- Focus on: What happened, why it matters, key numbers/facts
- Use active voice and present tense
- NO fluff words (revolutionary, groundbreaking, exciting)
- If the article is about funding: include amount, round, and use case
- If it's a product launch: include key feature and target user
- If it's a partnership: include both companies and purpose

Format your response as exactly 3 lines starting with "• "
"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = Anthropic(api_key=self.api_key)
        self.model_candidates = get_model_candidates("ANTHROPIC_MODEL_SUMMARY")

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and clean text."""
        import re
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', text)
        # Remove URLs that look like garbage
        clean = re.sub(r'https?://\S+', '[link]', clean)
        # Remove extra whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_api(self, title: str, content: str) -> str:
        """Call Claude API with retry logic."""
        # Clean HTML from content
        clean_content = self._clean_html(content)

        prompt = f"""Article Title: {title}

Article Content/Summary: {clean_content[:1500]}

Summarize this in exactly 3 bullet points:"""

        response, _ = create_message_with_fallback(
            self.client,
            self.model_candidates,
            max_tokens=200,
            system=self.SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return response.content[0].text

    def _parse_bullets(self, text: str) -> List[str]:
        """Parse bullet points from response."""
        bullets = []
        for line in text.strip().split('\n'):
            line = line.strip()
            if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                # Remove bullet character
                bullet = line.lstrip('•-* ').strip()
                if bullet:
                    bullets.append(bullet)

        # Ensure exactly 3 bullets
        if len(bullets) < 3:
            bullets.extend([''] * (3 - len(bullets)))
        return bullets[:3]

    def summarize(self, article: Dict) -> Dict:
        """Summarize a single article."""
        title = article.get('title', '')
        content = article.get('summary', '') or article.get('description', '')

        # If no content, use title only
        if not content:
            content = title

        try:
            response = self._call_api(title, content)
            bullets = self._parse_bullets(response)
            article['ai_summary'] = bullets
            article['summarized'] = True
        except Exception as e:
            print(f"  Error summarizing '{title[:50]}...': {e}")
            # Fallback: use original summary truncated
            article['ai_summary'] = [
                content[:100] + '...' if len(content) > 100 else content,
                '',
                ''
            ]
            article['summarized'] = False

        return article

    def summarize_batch(self, articles: List[Dict], delay: float = 0.2) -> List[Dict]:
        """Summarize multiple articles with rate limiting."""
        print(f"Summarizing {len(articles)} articles with Claude Haiku...")

        for i, article in enumerate(articles):
            self.summarize(article)

            # Progress indicator
            if (i + 1) % 5 == 0:
                print(f"  Summarized {i + 1}/{len(articles)}")

            # Rate limiting
            time.sleep(delay)

        success_count = sum(1 for a in articles if a.get('summarized', False))
        print(f"Successfully summarized: {success_count}/{len(articles)}")

        return articles


class FallbackSummarizer:
    """Fallback summarizer when API is unavailable - extracts key sentences."""

    def summarize(self, article: Dict) -> Dict:
        """Create a basic summary without AI."""
        content = article.get('summary', '') or article.get('title', '')

        # Split into sentences
        sentences = [s.strip() for s in content.replace('\n', ' ').split('.') if s.strip()]

        # Take first 3 sentences
        bullets = []
        for s in sentences[:3]:
            if len(s) > 100:
                s = s[:97] + '...'
            bullets.append(s)

        # Pad if needed
        while len(bullets) < 3:
            bullets.append('')

        article['ai_summary'] = bullets[:3]
        article['summarized'] = False

        return article


def summarize_articles(articles: List[Dict], api_key: Optional[str] = None) -> List[Dict]:
    """Main function to summarize articles."""
    try:
        summarizer = ArticleSummarizer(api_key)
        return summarizer.summarize_batch(articles)
    except ValueError as e:
        print(f"API key error: {e}")
        print("Using fallback summarizer...")
        fallback = FallbackSummarizer()
        return [fallback.summarize(a) for a in articles]
