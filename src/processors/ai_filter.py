"""
AI-powered article filtering using Claude.
Evaluates relevance and importance of each article for neurotech newsletter.
"""

import os
import json
from typing import List, Dict, Tuple
from anthropic import Anthropic


class AIArticleFilter:
    """Uses Claude to filter and rank articles for relevance."""

    SYSTEM_PROMPT = """You are a neurotech industry analyst filtering news for a competitive intelligence newsletter.

Your job: Evaluate each article's relevance to the NEUROTECH and BRAIN-COMPUTER INTERFACE industry.

RELEVANT topics include:
- EEG headbands, neurofeedback devices, brain sensing wearables
- BCI (brain-computer interfaces), neural implants
- tDCS/TMS brain stimulation devices
- Sleep tracking headbands, meditation devices
- Consumer neurotech products (Muse, Neurosity, EMOTIV, etc.)
- Neurotech company funding, partnerships, product launches
- Digital therapeutics for mental health, cognitive health
- Screen time/digital wellness apps that compete with hardware solutions

NOT RELEVANT:
- General semiconductor/chip news (even if "neural" is in the name)
- Stock price movements without substantive company news
- General AI/ML news (unless specifically about neural interfaces)
- Pharmaceutical/drug trials (unless for neurotech devices)
- Hospital/clinic general news
- Unrelated companies that happen to have similar names

Return a JSON response with your evaluation."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-3-haiku-20240307"

    def evaluate_batch(self, articles: List[Dict], max_select: int = 15) -> List[Dict]:
        """Evaluate a batch of articles and return the top N most relevant."""
        if not articles:
            return []

        # Process in smaller batches to avoid response truncation
        BATCH_SIZE = 30
        all_scored = []

        for batch_start in range(0, len(articles), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(articles))
            batch = articles[batch_start:batch_end]

            scored = self._evaluate_single_batch(batch, batch_start)
            all_scored.extend(scored)

        # Sort by score descending
        all_scored.sort(key=lambda x: x.get('ai_score', 0), reverse=True)

        # Limit to 1 article per company for diversity
        company_counts = {}
        final = []
        for article in all_scored:
            company = article.get('company', 'Unknown')
            if company_counts.get(company, 0) < 1:
                final.append(article)
                company_counts[company] = company_counts.get(company, 0) + 1

        print(f"AI Filter: {len(articles)} -> {len(final)} relevant (1 per company)")
        return final[:max_select]

    def _evaluate_single_batch(self, articles: List[Dict], id_offset: int = 0) -> List[Dict]:
        """Evaluate a single batch of articles."""
        # Format articles for evaluation
        article_list = []
        for i, article in enumerate(articles):
            article_list.append({
                "id": i,
                "title": article.get('title', '')[:150],
                "company": article.get('company', ''),
                "source": article.get('source', '')
            })

        prompt = f"""Evaluate these {len(article_list)} articles for a NEUROTECH competitive intelligence newsletter.

ARTICLES:
{json.dumps(article_list)}

For each article, determine:
1. Is it relevant to neurotech/BCI industry? (true/false)
2. Importance score 1-10 (10=major funding/acquisition, 8=product launch, 6=partnership, 4=research, 2=minor mention)
3. Brief reason (5 words max)

Return JSON only, no other text:
{{"evaluations": [{{"id": 0, "relevant": true, "score": 8, "reason": "product launch"}}]}}

Be STRICT. Only neurotech companies or products."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text

            # Parse JSON from response
            start = result_text.find('{')
            end = result_text.rfind('}') + 1
            if start >= 0 and end > start:
                result = json.loads(result_text[start:end])
            else:
                return []

            # Filter by relevance
            evaluations = result.get('evaluations', [])
            scored_articles = []

            for eval_item in evaluations:
                article_id = eval_item.get('id')
                if article_id is not None and article_id < len(articles):
                    if eval_item.get('relevant', False):
                        article = articles[article_id].copy()
                        article['ai_score'] = eval_item.get('score', 0)
                        article['ai_reason'] = eval_item.get('reason', '')
                        scored_articles.append(article)

            return scored_articles

        except Exception as e:
            print(f"AI batch error: {e}")
            raise


def keyword_filter_articles(articles: List[Dict], max_select: int = 15) -> List[Dict]:
    """Fallback keyword-based filter when AI is unavailable."""
    NEUROTECH_KEYWORDS = [
        'neuro', 'brain', 'eeg', 'bci', 'neural', 'cognitive',
        'headband', 'headset', 'wearable', 'implant', 'stimulat', 'therapy',
        'fda', 'clinical', 'medical', 'device', 'patient',
        'funding', 'series a', 'series b', 'raised', 'million',
        'sleep track', 'meditation', 'neurofeedback', 'biofeedback',
        'dbs', 'tms', 'tdcs', 'deep brain', 'vagus nerve'
    ]

    EXCLUDE_KEYWORDS = [
        'semiconductor', 'chip', 'linux', 'kernel', 'tuxedo',
        'stock price', 'earnings', 'moves higher', 'rises', 'falls',
        'book value', 'per share', 'stock dividend', 'preferred stock',
        'buy rating', 'sell rating', 'zacks', 'still a buy', '12-month high',
        'price target', 'decreased by', 'increased by', 'equity incentive',
        'add stock', 'portfolio', 'strong share', '% decline', '% drop',
        'right time to', 'too late to', 'consider buying', 'consider adding',
        'after its', 'decline --', 'rise --', 'a look at', 'is it time',
        'class a common stock', 'ny:', 'nasdaq:', 'one-year', 'fallen too far',
        'shareholders', 'deadline soon', 'class action', 'lawsuit', 'settlement',
        'fantasy', 'football', 'basketball', 'nba', 'nfl', 'playoff',
        'nike shoes', 'sneaker', 'world cup', 'kit', 'jersey',
        'temple university', 'temple mount', 'coinbase', 'crypto',
        'restaurant', 'recipe', 'real estate', 'bitcoin',
        'mindset', 'positive mindset', 'verstappen', 'chess',
        'coachella', 'sabrina carpenter', 'concert', 'tour',
        'public health', 'teaching', 'textbook', 'edit book',
        'infosys', 'optimum healthcare it', 'weather', 'cloud stratus',
        'neurodiverse', 'neurodivergent', 'adhd tips', 'autism awareness'
    ]

    # Companies with generic names that need extra verification
    GENERIC_NAMES = ['kernel', 'clarity', 'mindset', 'temple', 'nike', 'oura', 'araya', 'galea', 'stratus', 'meta']

    scored = []
    for article in articles:
        title_lower = article.get('title', '').lower()
        company_lower = article.get('company', '').lower()

        # Skip if exclude keyword found
        skip = False
        for kw in EXCLUDE_KEYWORDS:
            if kw in title_lower:
                skip = True
                break
        if skip:
            continue

        # For generic company names, require neurotech keyword in title
        if company_lower in GENERIC_NAMES:
            has_neurotech = False
            for kw in NEUROTECH_KEYWORDS:
                if kw in title_lower:
                    has_neurotech = True
                    break
            if not has_neurotech:
                continue

        # Score by neurotech relevance
        score = 0
        for kw in NEUROTECH_KEYWORDS:
            if kw in title_lower:
                score += 2

        # Boost if company name is in title
        if company_lower in title_lower:
            score += 1

        article['relevance_score'] = score
        if score > 0:
            scored.append(article)

    # Sort by score descending
    scored.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

    # Limit to 1 article per company to ensure diversity and avoid duplicate stories
    company_counts = {}
    final = []
    for article in scored:
        company = article.get('company', 'Unknown')
        if company_counts.get(company, 0) < 1:
            final.append(article)
            company_counts[company] = company_counts.get(company, 0) + 1

    print(f"Keyword filter: {len(articles)} -> {len(final)} relevant (max 1 per company)")
    return final[:max_select]


def ai_filter_articles(articles: List[Dict], max_select: int = 15) -> List[Dict]:
    """Filter and rank articles using AI, with keyword fallback."""
    try:
        filter = AIArticleFilter()
        return filter.evaluate_batch(articles, max_select)
    except Exception as e:
        print(f"AI filter unavailable: {e}")
        print("Using keyword filter as fallback...")
        return keyword_filter_articles(articles, max_select)


def generate_summary(articles: List[Dict]) -> str:
    """Generate a concise summary of the articles."""
    if not articles:
        return ""

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return ""

    # Prepare article info
    article_info = []
    for a in articles:
        article_info.append({
            "title": a.get('title', '')[:100],
            "company": a.get('company', ''),
            "source": a.get('source', '')
        })

    prompt = f"""Write a brief neurotech news digest (2-3 sentences per major story, max 3 stories).

ARTICLES:
{json.dumps(article_info, indent=2)}

Rules:
- ONLY include genuinely significant news: funding rounds, product launches, FDA approvals, major partnerships
- Skip stock price updates, minor mentions, generic articles
- Start directly with the news, no intro
- Be very concise - each story is 1-2 sentences max
- If nothing truly significant, respond with just: "No major neurotech news today."
- Format: bullet points with company name bold
- NEVER start with "Here is" or any intro phrase - start directly with the first bullet"""

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"Summary generation failed: {e}")
        return ""
