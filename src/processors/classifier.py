"""
APEX Industry Classifier
BROAD coverage - only excludes obviously irrelevant content.
"""

from typing import List, Dict, Tuple
import re


class IndustryClassifier:
    """Broad industry filter - exclude garbage, keep everything else."""

    # ONLY exclude if title contains these (clearly irrelevant)
    EXCLUDE_FROM_TITLE = [
        # Automotive
        'car feature', 'car repair', 'vehicle', 'automotive', 'motor trend',
        'tesla model', 'toyota', 'ford', 'honda', 'bmw', 'mercedes',
        'driving', 'highway', 'traffic',

        # Sports
        'baseball', 'football', 'basketball', 'soccer', 'hockey',
        'nfl', 'mlb', 'nba', 'nhl', 'fifa',
        'game score', 'final score', 'gameday', 'playoffs', 'championship',
        'fantasy sports', 'fantasy baseball', 'fantasy football',

        # Crime/Police
        'police', 'arrest', 'warrant', 'murder', 'crime', 'criminal',
        'prison', 'inmate', 'jail', 'court case',

        # Politics/News
        'nra', 'gun rights', 'firearm', 'election', 'vote', 'congress',
        'senate', 'republican', 'democrat', 'trump', 'biden',

        # Nature/Environment (not relevant)
        'forest legacy', 'forest program', 'conservation', 'wildlife',
        'national park', 'hiking trail',

        # Finance (not startup funding)
        'commodities', 'stock price', 'stock market', 'trading', 'forex',
        'bitcoin', 'crypto', 'blockchain', 'nft',
        'real estate', 'housing market', 'mortgage',

        # Food/Lifestyle
        'recipe', 'cooking', 'restaurant', 'chef', 'food',
        'weather', 'forecast',

        # Gaming (not brain gaming)
        'nintendo', 'mario', 'xbox', 'playstation', 'video game',
        'fortnite', 'minecraft', 'call of duty',

        # Medical (too clinical, not consumer)
        'surgery', 'surgical', 'hospital', 'patient dies',
        'tumor', 'cancer treatment', 'chemotherapy',
        'clinical trial results', 'drug trial', 'fda approval drug',
    ]

    # Neurotech-related terms for categorization
    NEUROTECH_TERMS = [
        'eeg', 'brain', 'neural', 'neuro', 'cognitive', 'bci',
        'headband', 'neurofeedback', 'brainwave', 'meditation device',
        'muse', 'neurable', 'neurosity', 'emotiv', 'dreem', 'apollo neuro',
        'kernel', 'synchron', 'neuralink', 'openBCI',
        'brain-computer', 'brain computer', 'brain sensing', 'brain-sensing',
        'mental wellness', 'brain health', 'cognitive enhancement',
    ]

    # Productivity-related terms
    PRODUCTIVITY_TERMS = [
        'screen time', 'app blocker', 'digital wellness', 'phone addiction',
        'focus app', 'productivity app', 'distraction', 'attention',
        'opal', 'freedom app', 'cold turkey', 'one sec', 'screenzen',
        'dopamine', 'social media addiction', 'digital detox',
        'smartphone addiction', 'notification', 'mindfulness app',
    ]

    def _should_exclude(self, title: str) -> Tuple[bool, str]:
        """Check if title should be excluded."""
        title_lower = title.lower()

        for term in self.EXCLUDE_FROM_TITLE:
            if term in title_lower:
                return True, f'excluded: {term}'

        return False, ''

    def _categorize(self, title: str) -> str:
        """Categorize as neurotech or productivity."""
        title_lower = title.lower()

        for term in self.NEUROTECH_TERMS:
            if term in title_lower:
                return 'neurotech'

        for term in self.PRODUCTIVITY_TERMS:
            if term in title_lower:
                return 'productivity'

        # Default to neurotech (broader category)
        return 'neurotech'

    def classify(self, article: Dict) -> Tuple[str, float, str]:
        """Classify article."""
        title = article.get('title', '')

        excluded, reason = self._should_exclude(title)
        if excluded:
            return ('excluded', 0.0, reason)

        category = self._categorize(title)
        return (category, 1.0, 'relevant')

    def classify_batch(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Classify all articles."""
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

        print(f"Classified: {len(results['neurotech'])} neurotech, "
              f"{len(results['productivity'])} productivity, "
              f"{len(results['excluded'])} excluded")

        return results


def classify_articles(articles: List[Dict]) -> Dict[str, List[Dict]]:
    classifier = IndustryClassifier()
    return classifier.classify_batch(articles)
