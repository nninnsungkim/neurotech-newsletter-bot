"""
Classifier to categorize articles as neurotech or productivity.
"""

from typing import List, Dict, Tuple
import re


class ArticleClassifier:
    """Classifies articles into neurotech vs productivity categories."""

    # Keywords for neurotech classification
    NEUROTECH_KEYWORDS = [
        # Hardware
        'eeg', 'bci', 'brain computer interface', 'neural interface',
        'headband', 'brain sensing', 'neurotech', 'neurotechnology',
        'brain wearable', 'neurofeedback', 'brain stimulation',
        'tdcs', 'tms', 'transcranial', 'implant', 'neural',

        # Concepts
        'brainwave', 'brain wave', 'brain activity', 'cognitive enhancement',
        'brain state', 'mental workload', 'attention monitoring',
        'focus tracking', 'meditation device', 'brain training',

        # Companies (major ones)
        'muse', 'neurable', 'emotiv', 'neurosity', 'openbci', 'kernel',
        'neuralink', 'synchron', 'paradromics', 'precision neuroscience',
        'apollo neuro', 'dreem', 'flow neuroscience', 'halo neuro',
        'cognixion', 'brainco', 'arctop', 'nextmind', 'elemind',

        # Medical
        'dbs', 'deep brain', 'vagus nerve', 'neuroprosthetic',
        'brain implant', 'neural prosthetic', 'electroceutical'
    ]

    # Keywords for productivity/digital wellness
    PRODUCTIVITY_KEYWORDS = [
        # Apps & concepts
        'screen time', 'app blocker', 'website blocker', 'digital wellness',
        'phone addiction', 'digital detox', 'distraction', 'focus app',
        'productivity app', 'time management app', 'habit app',
        'mindfulness app', 'meditation app', 'digital minimalism',

        # Companies
        'opal', 'freedom app', 'cold turkey', 'forest app', 'clearspace',
        'one sec', 'screenzen', 'brick phone', 'unpluq', 'offtime',
        'moment app', 'space app', 'flipd', 'appdetox',

        # Concepts
        'doom scrolling', 'doomscrolling', 'social media addiction',
        'notification', 'digital wellbeing', 'screen addiction',
        'internet addiction', 'tech addiction'
    ]

    # Keywords that indicate NOT relevant
    EXCLUDE_KEYWORDS = [
        'neurologist', 'neurology appointment', 'brain tumor', 'brain cancer',
        'alzheimer treatment', 'parkinson medication', 'epilepsy seizure',
        'stroke patient', 'brain surgery patient', 'clinical trial results',
        'drug trial', 'pharmaceutical'
    ]

    def __init__(self):
        # Compile patterns for faster matching
        self.neurotech_pattern = re.compile(
            '|'.join(re.escape(kw) for kw in self.NEUROTECH_KEYWORDS),
            re.IGNORECASE
        )
        self.productivity_pattern = re.compile(
            '|'.join(re.escape(kw) for kw in self.PRODUCTIVITY_KEYWORDS),
            re.IGNORECASE
        )
        self.exclude_pattern = re.compile(
            '|'.join(re.escape(kw) for kw in self.EXCLUDE_KEYWORDS),
            re.IGNORECASE
        )

    def _get_text(self, article: Dict) -> str:
        """Extract searchable text from article."""
        parts = [
            article.get('title', ''),
            article.get('summary', ''),
            article.get('source', ''),
            article.get('query', '')
        ]
        return ' '.join(parts)

    def _count_matches(self, text: str, pattern) -> int:
        """Count keyword matches in text."""
        return len(pattern.findall(text))

    def classify(self, article: Dict) -> Tuple[str, float]:
        """
        Classify an article.
        Returns: (category, confidence)
        """
        text = self._get_text(article)

        # Check exclusions first
        if self.exclude_pattern.search(text):
            return ('excluded', 0.0)

        neurotech_matches = self._count_matches(text, self.neurotech_pattern)
        productivity_matches = self._count_matches(text, self.productivity_pattern)

        # Calculate confidence
        total_matches = neurotech_matches + productivity_matches
        if total_matches == 0:
            return ('unknown', 0.0)

        if neurotech_matches > productivity_matches:
            confidence = neurotech_matches / (total_matches + 1)
            return ('neurotech', min(confidence, 1.0))
        elif productivity_matches > neurotech_matches:
            confidence = productivity_matches / (total_matches + 1)
            return ('productivity', min(confidence, 1.0))
        else:
            # Tie - default to neurotech since it's 80% of newsletter
            return ('neurotech', 0.5)

    def classify_batch(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Classify a batch of articles."""
        results = {
            'neurotech': [],
            'productivity': [],
            'excluded': [],
            'unknown': []
        }

        for article in articles:
            category, confidence = self.classify(article)
            article['category'] = category
            article['classification_confidence'] = confidence
            results[category].append(article)

        print(f"Classification: {len(results['neurotech'])} neurotech, "
              f"{len(results['productivity'])} productivity, "
              f"{len(results['excluded'])} excluded, "
              f"{len(results['unknown'])} unknown")

        return results


def classify_articles(articles: List[Dict]) -> Dict[str, List[Dict]]:
    """Main function to classify articles."""
    classifier = ArticleClassifier()
    return classifier.classify_batch(articles)
