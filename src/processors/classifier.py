"""
Strict classifier for APEX competitive intelligence.
Only passes articles directly relevant to:
- Direct competitors (Opal, Muse, Neurable, Neurode, Freedom)
- EEG/neurotech wearables for productivity
- Productivity/focus apps
"""

from typing import List, Dict, Tuple
import re
import json
from pathlib import Path


class APEXClassifier:
    """Strictly classifies articles for APEX competitive intelligence."""

    # Direct competitors - MUST track these
    COMPETITORS = {
        'opal': 'competitor',
        'muse headband': 'competitor',
        'muse meditation': 'competitor',
        'muse s': 'competitor',
        'interaxon': 'competitor',
        'neurable': 'competitor',
        'neurode': 'competitor',
        'freedom app': 'competitor',
    }

    # Secondary competitors
    SECONDARY = [
        'neurosity', 'emotiv', 'apollo neuro', 'dreem', 'elemind',
        'flow neuroscience', 'cold turkey', 'one sec', 'clearspace',
        'screenzen', 'brick app', 'brainco'
    ]

    # Required keywords - article MUST contain at least one
    REQUIRED_KEYWORDS = [
        # Hardware
        'eeg', 'fnirs', 'headband', 'wearable', 'neurofeedback',
        'brain sensing', 'brain-sensing', 'neurotech', 'brain computer',
        # Software
        'screen time', 'app blocker', 'focus app', 'productivity app',
        'digital wellness', 'phone addiction', 'distraction block',
        'attention track', 'focus track'
    ]

    # Business signals that boost relevance
    BUSINESS_SIGNALS = [
        'launch', 'announce', 'release', 'funding', 'raise', 'series a',
        'series b', 'seed', 'partner', 'acquire', 'fda', 'patent',
        'hire', 'appoint', 'ceo', 'cto', 'expand'
    ]

    # Hard excludes - if present, reject article
    HARD_EXCLUDE = [
        'car', 'vehicle', 'automotive', 'driving', 'tesla',
        'police', 'arrest', 'warrant', 'crime',
        'fantasy baseball', 'fantasy football', 'fantasy sports',
        'video game', 'nintendo', 'mario', 'xbox', 'playstation',
        'linux', 'risc-v', 'kernel', 'cpu',
        'surgery', 'implant', 'surgical',
        'alzheimer', 'parkinson', 'epilepsy', 'seizure',
        'clinical trial', 'drug trial', 'pharma',
        'chatgpt', 'openai', 'llama', 'large language model',
        'cryptocurrency', 'bitcoin', 'blockchain',
        'real estate', 'housing', 'mortgage',
        'recipe', 'cooking', 'restaurant',
        'weather', 'sports score', 'election'
    ]

    def __init__(self):
        pass

    def _get_text(self, article: Dict) -> str:
        """Get searchable text from article."""
        parts = [
            article.get('title', ''),
            article.get('summary', ''),
            article.get('source', '')
        ]
        return ' '.join(parts).lower()

    def _is_excluded(self, text: str) -> bool:
        """Check if article should be excluded."""
        for term in self.HARD_EXCLUDE:
            if term in text:
                return True
        return False

    def _is_competitor_mention(self, text: str) -> Tuple[bool, str]:
        """Check if article mentions a direct competitor."""
        for comp, cat in self.COMPETITORS.items():
            if comp in text:
                return True, comp
        for comp in self.SECONDARY:
            if comp in text:
                return True, comp
        return False, ''

    def _has_required_keyword(self, text: str) -> bool:
        """Check if article has required relevance keywords."""
        for kw in self.REQUIRED_KEYWORDS:
            if kw in text:
                return True
        return False

    def _count_business_signals(self, text: str) -> int:
        """Count business signal keywords."""
        count = 0
        for signal in self.BUSINESS_SIGNALS:
            if signal in text:
                count += 1
        return count

    def classify(self, article: Dict) -> Tuple[str, float, str]:
        """
        Classify article for APEX relevance.
        Returns: (category, score, reason)
        """
        text = self._get_text(article)

        # Step 1: Hard exclude
        if self._is_excluded(text):
            return ('excluded', 0.0, 'contains excluded term')

        # Step 2: Check competitor mention
        is_competitor, comp_name = self._is_competitor_mention(text)

        # Step 3: Check required keywords
        has_required = self._has_required_keyword(text)

        # Step 4: Count business signals
        signal_count = self._count_business_signals(text)

        # Scoring logic
        score = 0.0
        category = 'excluded'
        reason = ''

        if is_competitor:
            # Direct competitor mention = always relevant
            score = 0.8 + (signal_count * 0.05)
            category = 'neurotech' if any(x in comp_name for x in ['muse', 'neurable', 'neurode', 'emotiv', 'neurosity']) else 'productivity'
            reason = f'competitor: {comp_name}'
        elif has_required and signal_count >= 1:
            # Has relevant keywords + business signal
            score = 0.5 + (signal_count * 0.1)
            # Categorize based on keywords
            if any(x in text for x in ['eeg', 'headband', 'wearable', 'neurofeedback', 'brain sens']):
                category = 'neurotech'
            else:
                category = 'productivity'
            reason = f'relevant topic with {signal_count} business signals'
        elif has_required:
            # Has relevant keywords but no business signal - lower score
            score = 0.3
            if any(x in text for x in ['eeg', 'headband', 'wearable', 'neurofeedback', 'brain sens']):
                category = 'neurotech'
            else:
                category = 'productivity'
            reason = 'relevant topic'
        else:
            # Not relevant
            category = 'excluded'
            score = 0.0
            reason = 'no relevant keywords'

        return (category, min(score, 1.0), reason)

    def classify_batch(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Classify batch and return only relevant articles."""
        results = {
            'neurotech': [],
            'productivity': [],
            'excluded': []
        }

        for article in articles:
            category, score, reason = self.classify(article)
            article['category'] = category
            article['relevance_score'] = score
            article['classification_reason'] = reason

            if category != 'excluded' and score >= 0.3:
                results[category].append(article)
            else:
                results['excluded'].append(article)

        # Sort by relevance score
        results['neurotech'] = sorted(results['neurotech'], key=lambda x: x['relevance_score'], reverse=True)
        results['productivity'] = sorted(results['productivity'], key=lambda x: x['relevance_score'], reverse=True)

        print(f"Classification: {len(results['neurotech'])} neurotech, "
              f"{len(results['productivity'])} productivity, "
              f"{len(results['excluded'])} excluded")

        return results


def classify_articles(articles: List[Dict]) -> Dict[str, List[Dict]]:
    """Main function to classify articles for APEX."""
    classifier = APEXClassifier()
    return classifier.classify_batch(articles)
