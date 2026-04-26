"""
AI-powered opportunity filtering using Claude.
Filters VC fellowships and pitch competitions for relevance.
"""

import os
import json
from typing import List, Dict
from anthropic import Anthropic
from .anthropic_utils import create_message_with_fallback, get_model_candidates, parse_json_response


class OpportunityFilter:
    """Uses Claude to filter and evaluate opportunities."""

    SYSTEM_PROMPT = """You are helping a pre-seed startup founder find opportunities.

The founder is building APEX - a cognitive performance platform using EEG, fNIRS, PPG, EDA sensors.
They are looking for:

1. VC FELLOWSHIPS (PRIORITY):
   - Programs for builders/founders to work on their OWN startup
   - Spring 2026 cohorts or currently accepting applications
   - Pre-seed/idea stage (NOT Series A+)
   - Especially: neurotech, healthtech, hardware, consumer wearables
   - Both US and Korea (Korea = only major/well-known programs)

2. PITCH COMPETITIONS:
   - ONLY Purdue University or Indiana state related
   - Must explicitly mention Purdue, Indiana University, Indianapolis, or Indiana
   - Must be for early-stage startups

INCLUDE (score 7-10):
- Fellowship applications currently open or opening soon
- Spring 2026 cohorts
- Pre-seed/idea stage programs
- Builder/founder programs (work on own startup)
- HealthTech/NeuroTech specific accelerators
- Major Korean programs (SparkLabs, Primer, TIPS, etc.)
- Pitch competitions that EXPLICITLY mention Purdue or Indiana

EXCLUDE (score 0):
- Job postings for VC firms
- Fellowships for students (not founders)
- Series A+ programs
- Closed/expired applications
- General news about VCs (not fellowship programs)
- Pitch competitions NOT in Purdue/Indiana (Michigan, Ohio, etc. = EXCLUDE)
- MBA programs, consulting competitions
- Fashion, lifestyle, beauty, food, sports news
- Any article not about startup/founder programs

Be strict but don't miss genuine opportunities."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.client = Anthropic(api_key=self.api_key)
        self.model_candidates = get_model_candidates(
            "ANTHROPIC_MODEL_OPPORTUNITIES",
            "ANTHROPIC_MODEL_FILTER"
        )

    def filter_opportunities(self, opportunities: List[Dict], category: str) -> List[Dict]:
        """Filter opportunities by relevance."""
        if not opportunities:
            return []

        # Process in batches
        BATCH_SIZE = 25
        all_filtered = []

        for batch_start in range(0, len(opportunities), BATCH_SIZE):
            batch = opportunities[batch_start:batch_start + BATCH_SIZE]
            filtered = self._filter_batch(batch, category)
            all_filtered.extend(filtered)

        # Sort by score
        all_filtered.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

        return all_filtered

    def _filter_batch(self, opportunities: List[Dict], category: str) -> List[Dict]:
        """Filter a batch of opportunities."""
        items = []
        for i, opp in enumerate(opportunities):
            items.append({
                "id": i,
                "title": opp.get('title', '')[:150],
                "source": opp.get('source', ''),
                "program": opp.get('program', ''),
            })

        category_context = "VC FELLOWSHIP" if category == "vc_fellowship" else "PITCH COMPETITION"

        prompt = f"""Evaluate these {len(items)} {category_context} opportunities.

OPPORTUNITIES:
{json.dumps(items, indent=2)}

For each, determine:
1. Is it a genuine {category_context.lower()} opportunity for an early-stage founder?
2. Relevance score 1-10 (10=perfect match, open applications; 7=relevant; 4=maybe; 0=irrelevant)
3. Brief reason (5 words max)

Return JSON only with RELEVANT items and omit everything else:
{{"selected": [{{"id": 0, "score": 8, "reason": "spring cohort open"}}]}}
If nothing is relevant, return {{"selected": []}}

Be strict. Only genuine opportunities for founders."""

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

            evaluations = result.get('selected', result.get('evaluations', []))
            filtered = []

            for eval_item in evaluations:
                idx = eval_item.get('id')
                if idx is not None and idx < len(opportunities):
                    if eval_item.get('score', 0) >= 5:
                        opp = opportunities[idx].copy()
                        opp['relevance_score'] = eval_item.get('score', 0)
                        opp['relevance_reason'] = eval_item.get('reason', '')
                        filtered.append(opp)

            return filtered

        except Exception as e:
            print(f"Filter error: {e}")
            return []


def generate_opportunity_summary(vc_fellowships: List[Dict], pitch_competitions: List[Dict]) -> str:
    """Generate summary of opportunities."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return _generate_opportunity_fallback_summary(vc_fellowships, pitch_competitions)

    # Prepare data
    vc_data = [{"title": o['title'][:100], "source": o.get('source', ''), "reason": o.get('relevance_reason', '')}
               for o in vc_fellowships[:15]]
    pitch_data = [{"title": o['title'][:100], "source": o.get('source', '')}
                  for o in pitch_competitions[:10]]

    prompt = f"""Write a brief opportunity digest for a startup founder.

VC FELLOWSHIPS & ACCELERATORS ({len(vc_fellowships)} found):
{json.dumps(vc_data, indent=2)}

PITCH COMPETITIONS - Purdue/Indiana ({len(pitch_competitions)} found):
{json.dumps(pitch_data, indent=2)}

Write a concise summary (2-3 paragraphs):

1. VC Fellowships: List the most relevant programs with application status
2. Pitch Competitions: Any Purdue/Indiana opportunities
3. Action Items: What to apply to this week

Guidelines:
- Be specific with program names
- Note if applications are open/deadlines
- Use CAPS for program names (not ** markdown)
- NO intro like "Here's your digest" - start directly
- If few results, say so honestly
- Prioritize builder/founder programs for pre-seed stage"""

    try:
        client = Anthropic(api_key=api_key)
        response, _ = create_message_with_fallback(
            client,
            get_model_candidates("ANTHROPIC_MODEL_OPPORTUNITIES", "ANTHROPIC_MODEL_SUMMARY"),
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        summary = response.content[0].text.strip()
        return summary if summary else _generate_opportunity_fallback_summary(vc_fellowships, pitch_competitions)
    except Exception as e:
        print(f"Summary error: {e}")
        return _generate_opportunity_fallback_summary(vc_fellowships, pitch_competitions)


def filter_opportunities(opportunities: List[Dict], category: str) -> List[Dict]:
    """Main filter function."""
    try:
        filter = OpportunityFilter()
        return filter.filter_opportunities(opportunities, category)
    except Exception as e:
        print(f"Filter unavailable: {e}")
        # Fallback: return all with priority flag
        return [o for o in opportunities if o.get('priority', False)]


def _generate_opportunity_fallback_summary(vc_fellowships: List[Dict], pitch_competitions: List[Dict]) -> str:
    """Fallback digest when Anthropic is unavailable."""
    vc_titles = [opp.get('title', '').strip() for opp in vc_fellowships[:3] if opp.get('title')]
    pitch_titles = [opp.get('title', '').strip() for opp in pitch_competitions[:3] if opp.get('title')]

    paragraphs = []

    if vc_titles:
        paragraphs.append(
            f"VC fellowships and accelerators worth a closer look: {'; '.join(vc_titles)}."
        )
    else:
        paragraphs.append(
            "VC fellowship flow looks light right now, with no especially strong founder-program signals in this batch."
        )

    if pitch_titles:
        paragraphs.append(
            f"Purdue and Indiana pitch competition watchlist: {'; '.join(pitch_titles)}."
        )
    else:
        paragraphs.append(
            "No clear Purdue or Indiana pitch competition items stood out in this batch."
        )

    if vc_titles or pitch_titles:
        paragraphs.append(
            "Action item: prioritize anything with an active application window or a near-term deadline, then verify eligibility directly on the program page."
        )
    else:
        paragraphs.append(
            "Action item: keep monitoring for newly opened applications rather than forcing low-signal programs into the funnel."
        )

    return "\n\n".join(paragraphs)
