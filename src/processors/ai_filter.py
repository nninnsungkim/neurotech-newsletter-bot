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

    SYSTEM_PROMPT = """You are a competitive intelligence analyst for APEX, a cognitive performance company.

APEX builds a multimodal platform (EEG + fNIRS + PPG + EDA + behavioral data) to help knowledge workers:
- Measure and improve FOCUS
- Support CREATIVE THINKING
- Enable FASTER LEARNING
- Future: NEUROSTIMULATION (tDCS/tACS)

PRIORITY (score 8-10):
- Product launches from: EEG wearables, fNIRS devices, neurostimulation (tDCS/tACS), focus tracking, HRV/recovery wearables
- Funding rounds, acquisitions in cognitive performance space
- FDA approvals, clinical results for focus/cognition devices
- New features: focus tracking, cognitive assessment, neurofeedback
- Partnerships with productivity/learning platforms

RELEVANT (score 5-7):
- Research on: attention measurement, cognitive enhancement, neurostimulation for focus/learning
- Company expansions, executive hires at direct competitors
- Conference demos of relevant tech (CES, neuroscience conferences)
- Sleep/recovery tech with cognitive performance angle

LOWER PRIORITY (score 3-4):
- General wellness/meditation apps without tech differentiation
- Pure fitness wearables without cognitive angle
- Medical implants (DBS, cochlear) - different market

EXCLUDE (score 0):
- Stock prices, SEC filings, "buy/sell" ratings, beneficial ownership
- Generic product reviews without news
- Unrelated companies (Nike, Temple University, crypto)
- Neurodiversity tips, mental health advice articles
- Old event recaps, opinion pieces

Be STRICT. Focus on cognitive performance market."""

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

        # Keep all relevant articles (no per-company limit)
        print(f"AI Filter: {len(articles)} -> {len(all_scored)} relevant")
        return all_scored[:max_select]

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
    # APEX-aligned keywords - cognitive performance focus
    NEUROTECH_KEYWORDS = [
        # Core tech
        'eeg', 'fnirs', 'fNIRS', 'ppg', 'hrv', 'eda',
        'neurofeedback', 'biofeedback', 'brain-sensing',
        # Neurostimulation
        'tdcs', 'tacs', 'neurostimulation', 'transcranial',
        # Cognitive performance
        'focus', 'attention', 'cognitive', 'concentration',
        'learning', 'memory', 'creativity',
        # Wearables
        'headband', 'wearable', 'headset', 'earbuds',
        # Business signals
        'funding', 'series a', 'series b', 'raised', 'million',
        'launch', 'announces', 'partnership', 'fda',
        # Recovery/stress (supporting)
        'recovery', 'stress', 'sleep track', 'meditation'
    ]

    EXCLUDE_KEYWORDS = [
        # Stock/financial noise
        'stock price', 'share price', 'earnings', 'moves higher', 'rises', 'falls',
        'book value', 'per share', 'stock dividend', 'preferred stock',
        'buy rating', 'sell rating', 'zacks', 'still a buy', '12-month high',
        'price target', 'decreased by', 'increased by', 'equity incentive',
        'add stock', 'portfolio', 'strong share', '% decline', '% drop',
        'right time to', 'too late to', 'consider buying', 'consider adding',
        'class a common stock', 'ny:', 'nasdaq:', 'nyse:', 'asx:', 'one-year', 'fallen too far',
        'shareholders', 'deadline soon', 'class action', 'lawsuit', 'settlement',
        'dilution', 'options and performance', 'performance rights',
        'if you invested', 'should you buy', 'is it time to buy',
        'stock surge', 'surge sparks', 'sparks fresh', 'stock alert', 'all ordinaries',
        # SEC filings
        'form 3', 'form 4', 'form 8-k', 'form 10-', 'sec filing',
        'beneficial ownership', 'insider', 'initial statement',
        # Medical procedures (not cognitive tech)
        'surgical tool', 'surgical device', 'surgery',
        # Generic tech (false positives)
        'semiconductor', 'chip', 'linux', 'kernel', 'tuxedo',
        # Sports/entertainment
        'fantasy', 'football', 'basketball', 'nba', 'nfl', 'playoff',
        'nike shoes', 'sneaker', 'world cup', 'kit', 'jersey',
        'coachella', 'sabrina carpenter', 'concert', 'tour',
        'verstappen', 'chess',
        # Unrelated
        'temple university', 'temple mount', 'coinbase', 'crypto',
        'restaurant', 'recipe', 'real estate', 'bitcoin',
        'mindset', 'positive mindset',
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


def qa_filter_articles(articles: List[Dict]) -> List[Dict]:
    """Second-pass QA filter with Haiku to remove false positives."""
    if not articles:
        return []

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return articles

    # Prepare for QA
    article_data = []
    for i, a in enumerate(articles):
        article_data.append({
            "id": i,
            "title": a.get('title', '')[:150],
            "company": a.get('company', ''),
            "source": a.get('source', '')
        })

    prompt = f"""You are a strict QA filter for a neurotech competitive intelligence newsletter.

ARTICLES TO REVIEW:
{json.dumps(article_data, indent=2)}

REJECT articles that are:
- Stock price updates, market analysis, "should you buy" articles
- Generic company mentions without actual news
- Unrelated products (Nike shoes, Temple University, etc.)
- Neurodiversity/ADHD tips, mental health advice articles
- Old news or event announcements
- Duplicate stories about the same event

KEEP only articles about:
- Actual product launches, updates, or announcements
- Funding rounds, acquisitions, partnerships
- FDA approvals, clinical trial results
- New research or technology breakthroughs
- Executive hires, company expansions

Return JSON with IDs to KEEP:
{{"keep": [0, 2, 5]}}

Be VERY strict. When in doubt, reject."""

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text
        start = result_text.find('{')
        end = result_text.rfind('}') + 1
        if start >= 0 and end > start:
            result = json.loads(result_text[start:end])
            keep_ids = result.get('keep', [])
            filtered = [articles[i] for i in keep_ids if i < len(articles)]
            print(f"QA Filter: {len(articles)} -> {len(filtered)} kept")
            return filtered
    except Exception as e:
        print(f"QA filter error: {e}")

    return articles


def generate_summary(articles: List[Dict]) -> str:
    """Generate competitive intelligence summary."""
    if not articles:
        return "_No significant neurotech updates in the last 3 days._"

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return ""

    article_info = []
    for a in articles:
        article_info.append({
            "title": a.get('title', '')[:150],
            "company": a.get('company', ''),
            "source": a.get('source', ''),
            "ai_reason": a.get('ai_reason', '')
        })

    prompt = f"""You are writing a competitive intelligence brief for APEX leadership.

APEX CONTEXT:
- Multimodal cognitive performance platform (EEG + fNIRS + PPG + EDA + behavioral)
- Core focus: FOCUS measurement, CREATIVE THINKING support, FASTER LEARNING
- Future roadmap: NEUROSTIMULATION (tDCS/tACS)
- Target: knowledge workers, students, founders - people who need peak cognition

ARTICLES FROM LAST 3 DAYS:
{json.dumps(article_info, indent=2)}

Write a brief (3-5 paragraphs) organized by APEX relevance:

1. **Direct Competition** - EEG/fNIRS wearables, focus tracking devices, neurofeedback
2. **Adjacent Moves** - HRV/recovery wearables (Whoop, Oura), neurostimulation, focus software
3. **Market Signals** - Funding trends, partnerships, new tech that could impact cognitive performance space
4. **Strategic Watch** - Anything that could affect APEX's positioning or roadmap

Guidelines:
- Be specific: "Neurosity launched X feature" not "a company released something"
- Frame through APEX lens: HOW does this affect our market position?
- Highlight: multimodal sensing advances, focus measurement tech, neurostim developments
- Skip irrelevant articles entirely
- If only minor news, say so honestly
- Tone: direct, executive-level, actionable
- NO intro like "Here is a brief" - start directly with the content
- Use CAPS for company names (e.g., WHOOP, MUSE) - do NOT use ** or markdown"""

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"Summary generation failed: {e}")
        return ""
