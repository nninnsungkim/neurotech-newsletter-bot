"""
AI-powered article filtering using Claude.
Evaluates relevance and importance of each article for neurotech newsletter.
"""

import os
import json
from typing import List, Dict, Tuple
from anthropic import Anthropic
from .anthropic_utils import create_message_with_fallback, get_model_candidates, parse_json_response


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
        self.model_candidates = get_model_candidates(
            "ANTHROPIC_MODEL_FILTER",
            "ANTHROPIC_MODEL_NEWSLETTER"
        )

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
            article_summary = article.get('summary', '') or article.get('description', '')
            article_list.append({
                "id": i,
                "title": article.get('title', '')[:150],
                "company": article.get('company', ''),
                "company_type": article.get('company_type', ''),
                "source": article.get('source', ''),
                "summary": article_summary[:400],
                "tech_tags": article.get('tech_tags', ''),
                "apex_relevance": article.get('relevance', '')
            })

        prompt = f"""Evaluate these {len(article_list)} articles for a NEUROTECH competitive intelligence newsletter.

ARTICLES:
{json.dumps(article_list)}

Use the title, summary, and source to judge the actual article. The company field is only the search target; do not treat it as proof that the article is about that company.

For each article, determine:
1. Is it relevant to neurotech/BCI industry?
2. Importance score 1-10 (10=major funding/acquisition, 8=product launch, 6=partnership, 4=research, 2=minor mention)
3. Brief reason (5 words max)

Return JSON only with RELEVANT articles and omit everything else:
{{"selected": [{{"id": 0, "score": 8, "reason": "product launch"}}]}}
If nothing is relevant, return {{"selected": []}}

Reject generic articles that merely share a name with an APEX watchlist company, such as sports posts about "Muse", restaurants named "Dreem", books using "flora", or generic watch features unrelated to recovery/cognition.
Be STRICT. Only actual neurotech, cognitive performance, neurostimulation, BCI, EEG/fNIRS, or recovery/sleep wearable news."""

        try:
            response, _ = create_message_with_fallback(
                self.client,
                self.model_candidates,
                max_tokens=1500,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text

            result = parse_json_response(result_text)

            # Filter by relevance
            evaluations = result.get('selected', result.get('evaluations', []))
            scored_articles = []

            for eval_item in evaluations:
                article_id = eval_item.get('id')
                if article_id is not None and article_id < len(articles):
                    if eval_item.get('score', 0) < 5:
                        continue
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
        'smart ring', 'readiness',
        # Business signals
        'funding', 'series a', 'series b', 'raised', 'million',
        'launch', 'announces', 'partnership', 'fda',
        'feature', 'device', 'sensor',
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
        'asset turnover',
        # SEC filings
        'form 3', 'form 4', 'form 8-k', 'form 10-', 'sec filing',
        'beneficial ownership', 'insider', 'initial statement',
        # Medical procedures (not cognitive tech)
        'surgical tool', 'surgical device', 'surgery',
        'paint and corrosion', 'disc sander', 'sku ',
        # Generic tech (false positives)
        'semiconductor', 'chip', 'linux', 'kernel', 'tuxedo',
        # Sports/entertainment
        'fantasy', 'football', 'basketball', 'nba', 'nfl', 'playoff',
        'nike shoes', 'sneaker', 'world cup', 'kit', 'jersey',
        'coachella', 'sabrina carpenter', 'concert', 'tour', 'post game',
        'verstappen', 'chess',
        # Unrelated
        'temple university', 'temple mount', 'coinbase', 'crypto',
        'restaurant', 'recipe', 'real estate', 'bitcoin', 'dairy',
        'mindset', 'positive mindset',
        'public health', 'teaching', 'textbook', 'edit book', 'books highlights',
        'infosys', 'optimum healthcare it', 'weather', 'cloud stratus',
        'neurodiverse', 'neurodivergent', 'adhd tips', 'autism awareness',
        'weekly recap', 'gospel choir', 'documentary', 'chrysler', 'pacifica',
        'whatsapp support', 'reddit.cgx', 'pimining'
    ]

    # Companies with generic names that need extra verification
    GENERIC_NAMES = [
        'apollo', 'brite', 'calm', 'centered', 'clarity', 'cgx', 'dreem',
        'elevate', 'galea', 'garmin', 'headspace', 'kernel', 'meta',
        'mindset', 'muse', 'nike', 'oura', 'peak', 'stratus', 'temple'
    ]
    PRODUCT_SIGNAL_KEYWORDS = ['launch', 'feature', 'device', 'wearable', 'ring', 'watch', 'headband', 'headset', 'sensor']
    APEX_SIGNAL_KEYWORDS = [
        'eeg', 'fnirs', 'bci', 'brain', 'neuro', 'cognitive', 'focus',
        'attention', 'hrv', 'recovery', 'sleep', 'readiness', 'stress',
        'neurofeedback', 'biofeedback', 'tdcs', 'tacs'
    ]

    scored = []
    for article in articles:
        title_lower = article.get('title', '').lower()
        context_lower = " ".join(filter(None, [
            article.get('title', ''),
            article.get('summary', ''),
            article.get('description', ''),
            article.get('source', '')
        ])).lower()
        company_lower = article.get('company', '').lower()
        tech_tags = [tag.strip().lower() for tag in article.get('tech_tags', '').split(',') if tag.strip()]

        # Skip if exclude keyword found
        skip = False
        for kw in EXCLUDE_KEYWORDS:
            if kw in context_lower:
                skip = True
                break
        if skip:
            continue

        # For generic company names, require extra evidence that the hit is about the company.
        if company_lower in GENERIC_NAMES:
            has_neurotech = any(kw in context_lower for kw in NEUROTECH_KEYWORDS)
            has_company_signal = any(tag in context_lower for tag in tech_tags)
            has_product_signal = any(kw in title_lower for kw in PRODUCT_SIGNAL_KEYWORDS)
            has_apex_signal = any(kw in context_lower for kw in APEX_SIGNAL_KEYWORDS)
            if not (has_apex_signal or has_company_signal or (has_product_signal and has_neurotech)):
                continue

        # Score by neurotech relevance
        score = 0
        for kw in NEUROTECH_KEYWORDS:
            if kw in context_lower:
                score += 2

        for tag in tech_tags:
            if tag in context_lower:
                score += 1

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
        article_summary = a.get('summary', '') or a.get('description', '')
        article_data.append({
            "id": i,
            "title": a.get('title', '')[:150],
            "company": a.get('company', ''),
            "company_type": a.get('company_type', ''),
            "source": a.get('source', ''),
            "summary": article_summary[:350],
            "tech_tags": a.get('tech_tags', '')
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
- Search-result false positives where the title/summary is about a different entity with the same name
- Generic watch/app features unless they affect HRV, recovery, sleep, readiness, focus, cognition, or sensing

KEEP only articles about:
- Actual product launches, updates, or announcements
- Funding rounds, acquisitions, partnerships
- FDA approvals, clinical trial results
- New research or technology breakthroughs
- Executive hires, company expansions

Return JSON with IDs to KEEP:
{{"keep": [0, 2, 5]}}

The company field is only the watchlist search target; keep the article only when title/summary/source confirm the actual article is relevant.
Be VERY strict. When in doubt, reject."""

    try:
        client = Anthropic(api_key=api_key)
        response, _ = create_message_with_fallback(
            client,
            get_model_candidates("ANTHROPIC_MODEL_FILTER", "ANTHROPIC_MODEL_NEWSLETTER"),
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text
        result = parse_json_response(result_text)
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
        return _generate_rule_based_summary(articles)

    article_info = []
    for a in articles:
        article_info.append({
            "title": a.get('title', '')[:150],
            "company": a.get('company', ''),
            "source": a.get('source', ''),
            "ai_reason": a.get('ai_reason', ''),
            "summary": (a.get('summary', '') or a.get('description', ''))[:280]
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

1. Direct Competition - EEG/fNIRS wearables, focus tracking devices, neurofeedback
2. Adjacent Moves - HRV/recovery wearables (Whoop, Oura), neurostimulation, focus software
3. Market Signals - Funding trends, partnerships, new tech that could impact cognitive performance space
4. Strategic Watch - Anything that could affect APEX's positioning or roadmap

Guidelines:
- Be specific: "Neurosity launched X feature" not "a company released something"
- Frame through APEX lens: HOW does this affect our market position?
- Highlight: multimodal sensing advances, focus measurement tech, neurostim developments
- Skip irrelevant articles entirely
- If only minor news, say so honestly
- Tone: direct, executive-level, actionable
- NO intro like "Here is a brief" - start directly with the content
- Use plain section labels in CAPS, not markdown
- Use CAPS for company names (e.g., WHOOP, MUSE) - do NOT use ** or markdown"""

    try:
        client = Anthropic(api_key=api_key)
        response, _ = create_message_with_fallback(
            client,
            get_model_candidates("ANTHROPIC_MODEL_SUMMARY", "ANTHROPIC_MODEL_NEWSLETTER"),
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        summary = _clean_summary_output(response.content[0].text)
        return summary if summary else _generate_rule_based_summary(articles)
    except Exception as e:
        print(f"Summary generation failed: {e}")
        return _generate_rule_based_summary(articles)


def _article_text(article: Dict) -> str:
    """Concatenate article fields for lightweight rule-based analysis."""
    return " ".join(filter(None, [
        article.get('title', ''),
        article.get('company', ''),
        article.get('source', ''),
        article.get('ai_reason', ''),
        article.get('summary', ''),
        article.get('description', '')
    ])).lower()


def _clean_summary_output(summary: str) -> str:
    """Keep Slack briefs plain-text even when the model adds markdown."""
    return (summary or "").replace("**", "").strip()


def _format_article_reference(article: Dict) -> str:
    """Create a compact article reference for fallback summaries."""
    title = article.get('title', '').strip()
    company = article.get('company', '').strip()
    if company and company.lower() not in title.lower():
        return f"{company.upper()}: {title}"
    return title


def _pick_matching_articles(articles: List[Dict], keywords: List[str], limit: int = 3) -> List[str]:
    """Pick a few distinct article references matching the given keywords."""
    matches = []
    seen = set()

    for article in articles:
        text = _article_text(article)
        if any(keyword in text for keyword in keywords):
            ref = _format_article_reference(article)
            if ref not in seen:
                matches.append(ref)
                seen.add(ref)
        if len(matches) >= limit:
            break

    return matches


def _generate_rule_based_summary(articles: List[Dict]) -> str:
    """Fallback summary when the Anthropic API is unavailable."""
    top_refs = [_format_article_reference(article) for article in articles[:3]]
    signal_strength = "light" if len(articles) <= 3 else "moderate"

    direct = _pick_matching_articles(
        articles,
        ['eeg', 'fnirs', 'bci', 'headband', 'headset', 'neurofeedback', 'focus']
    )
    adjacent = _pick_matching_articles(
        articles,
        ['oura', 'whoop', 'garmin', 'hrv', 'recovery', 'sleep', 'stress', 'ring', 'watch', 'wearable']
    )
    neurostim = _pick_matching_articles(
        articles,
        ['tdcs', 'tacs', 'neurostimulation', 'stimulation']
    )
    market = _pick_matching_articles(
        articles,
        ['funding', 'raised', 'launch', 'partnership', 'fda', 'trial', 'study', 'research']
    )

    paragraphs = [
        f"Signal quality is {signal_strength} today. The main watch items are {'; '.join(top_refs)}."
    ]

    detail_sentences = []
    if direct:
        detail_sentences.append(f"Direct competition signals center on {'; '.join(direct)}")
    if adjacent:
        detail_sentences.append(f"Adjacent wearable and recovery moves include {'; '.join(adjacent)}")
    if neurostim:
        detail_sentences.append(f"Neurostimulation watch items include {'; '.join(neurostim)}")

    if detail_sentences:
        paragraphs.append(". ".join(detail_sentences) + ".")

    if market:
        paragraphs.append(
            f"Strategic watch: {'; '.join(market)}. These items are the clearest inputs for APEX positioning and roadmap monitoring."
        )
    else:
        paragraphs.append(
            "Strategic watch: this batch looks more like incremental product and category noise than a major market-moving day."
        )

    return "\n\n".join(paragraphs)
