"""
APEX Competitive Intelligence Classifier
STRICT: Only passes articles with competitor/product names IN THE TITLE.
"""

from typing import List, Dict, Tuple
import re


class APEXClassifier:
    """Only passes articles directly relevant to APEX competitors."""

    # ONLY these terms in TITLE will pass
    MUST_MATCH_IN_TITLE = [
        # Primary competitors (exact)
        'opal',
        'muse headband', 'muse s', 'muse 2', 'interaxon',
        'neurable',
        'neurode',
        'freedom app',

        # Secondary competitors
        'neurosity', 'neurosity crown',
        'emotiv',
        'apollo neuro',
        'dreem',
        'flow neuroscience',
        'cold turkey',
        'one sec app',
        'clearspace',
        'screenzen',

        # Product terms (must be specific)
        'eeg headband',
        'eeg wearable',
        'brain-sensing headband',
        'neurofeedback headband',
        'focus headband',
        'meditation headband',
        'screen time app',
        'app blocker',
        'phone addiction app',
        'digital wellness app',
        'focus app launch',
        'productivity wearable',
    ]

    # If title contains these, auto-reject
    TITLE_REJECT = [
        'car', 'vehicle', 'motor', 'driving', 'tesla', 'toyota', 'ford',
        'police', 'arrest', 'warrant', 'crime', 'murder', 'prison', 'inmate',
        'baseball', 'football', 'basketball', 'soccer', 'nfl', 'mlb', 'nba',
        'game score', 'final score', 'gameday',
        'recipe', 'cooking', 'restaurant', 'food',
        'weather', 'forecast',
        'nra', 'gun', 'firearm',
        'forest legacy', 'forest program', 'conservation',
        'commodities', 'stock', 'trading', 'investor',
        'alzheimer', 'parkinson', 'diabetes', 'cancer', 'tumor',
        'surgery', 'surgical', 'implant', 'patient',
        'linux', 'kernel', 'risc-v', 'cpu',
        'nintendo', 'mario', 'xbox', 'playstation',
        'crypto', 'bitcoin', 'blockchain',
        'ipo', 'hong kong',
    ]

    def _title_matches(self, title: str) -> Tuple[bool, str]:
        """Check if title contains required keywords."""
        title_lower = title.lower()

        # First check rejections
        for reject in self.TITLE_REJECT:
            if reject in title_lower:
                return False, f'rejected: {reject}'

        # Then check for required matches
        for match in self.MUST_MATCH_IN_TITLE:
            if match in title_lower:
                return True, f'matched: {match}'

        return False, 'no match'

    def classify(self, article: Dict) -> Tuple[str, float, str]:
        """Classify based on TITLE ONLY."""
        title = article.get('title', '')

        matched, reason = self._title_matches(title)

        if not matched:
            return ('excluded', 0.0, reason)

        # Categorize
        title_lower = title.lower()

        # Hardware/neurotech keywords
        neurotech_terms = [
            'eeg', 'headband', 'wearable', 'neurofeedback', 'brain',
            'muse', 'neurable', 'neurode', 'neurosity', 'emotiv',
            'apollo neuro', 'dreem', 'flow neuroscience'
        ]

        for term in neurotech_terms:
            if term in title_lower:
                return ('neurotech', 1.0, reason)

        # Default to productivity
        return ('productivity', 1.0, reason)

    def classify_batch(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Classify batch - STRICT filtering."""
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

            results[category].append(article)

        print(f"STRICT Filter: {len(results['neurotech'])} neurotech, "
              f"{len(results['productivity'])} productivity, "
              f"{len(results['excluded'])} excluded")

        return results


def classify_articles(articles: List[Dict]) -> Dict[str, List[Dict]]:
    """Main classification function."""
    classifier = APEXClassifier()
    return classifier.classify_batch(articles)
