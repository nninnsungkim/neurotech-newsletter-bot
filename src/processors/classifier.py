"""
Business-only classifier for APEX.
REJECT: Academic research, medical news, general neuroscience.
ACCEPT: Products, funding, partnerships, launches.
"""

from typing import List, Dict, Tuple


class BusinessOnlyClassifier:
    """Only passes business/product news about companies."""

    # Auto-reject if title contains these
    REJECT = [
        # Academic/research
        'study finds', 'research shows', 'scientists', 'researchers',
        'neural code', 'brain activity', 'neurons', 'synapses',
        'mental images', 'cognitive science', 'neuroscience news',
        'brain replays', 'new insights', 'discovery',

        # Medical/clinical
        'treatment', 'therapy', 'disease', 'disorder', 'patient',
        'alzheimer', 'parkinson', 'stroke', 'epilepsy', 'autism',
        'surgery', 'clinical', 'hospital', 'diagnosis',

        # Irrelevant
        'car', 'vehicle', 'baseball', 'football', 'police', 'arrest',
        'nra', 'gun', 'election', 'recipe', 'weather', 'game score',
        'forest', 'wildlife', 'bitcoin', 'crypto', 'stock price',
    ]

    # Must have at least ONE of these (business signals)
    BUSINESS_SIGNALS = [
        'launch', 'launches', 'release', 'releases', 'announce',
        'funding', 'raises', 'raised', 'series', 'seed', 'investment',
        'partnership', 'partners', 'partner with', 'collaboration',
        'acquisition', 'acquires', 'acquired', 'merger',
        'new product', 'new feature', 'update', 'version',
        'expands', 'expansion', 'opens', 'available',
        'ceo', 'hires', 'appoints', 'joins',
        'fda', 'approval', 'clearance', 'patent',
    ]

    # Company/product terms (industry relevance)
    RELEVANT_TERMS = [
        # Neurotech
        'eeg', 'headband', 'wearable', 'neurofeedback', 'bci',
        'brain-computer', 'brain sensing', 'neurotech',
        'muse', 'neurable', 'neurosity', 'emotiv', 'dreem',
        'apollo neuro', 'opal', 'freedom',

        # Productivity
        'screen time', 'app blocker', 'digital wellness',
        'focus app', 'productivity app', 'phone addiction',
        'distraction', 'attention app',
    ]

    def _should_reject(self, title: str) -> bool:
        """Check if title should be rejected."""
        title_lower = title.lower()
        for term in self.REJECT:
            if term in title_lower:
                return True
        return False

    def _has_business_signal(self, title: str) -> bool:
        """Check if has business news signal."""
        title_lower = title.lower()
        for signal in self.BUSINESS_SIGNALS:
            if signal in title_lower:
                return True
        return False

    def _is_relevant(self, title: str) -> bool:
        """Check if industry-relevant."""
        title_lower = title.lower()
        for term in self.RELEVANT_TERMS:
            if term in title_lower:
                return True
        return False

    def classify(self, article: Dict) -> Tuple[str, float, str]:
        """Classify article."""
        title = article.get('title', '')

        # Reject research/medical/irrelevant
        if self._should_reject(title):
            return ('excluded', 0.0, 'rejected')

        # Must be relevant AND have business signal
        has_signal = self._has_business_signal(title)
        is_relevant = self._is_relevant(title)

        if not (has_signal or is_relevant):
            return ('excluded', 0.0, 'not business news')

        # Categorize
        title_lower = title.lower()
        neurotech_terms = ['eeg', 'headband', 'brain', 'neuro', 'wearable', 'muse', 'neurable', 'emotiv', 'dreem']

        for term in neurotech_terms:
            if term in title_lower:
                return ('neurotech', 1.0, 'relevant business')

        return ('productivity', 1.0, 'relevant business')

    def classify_batch(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Classify all."""
        results = {'neurotech': [], 'productivity': [], 'excluded': []}

        for article in articles:
            category, score, reason = self.classify(article)
            article['category'] = category
            article['relevance_score'] = score
            results[category].append(article)

        print(f"Business filter: {len(results['neurotech'])} neurotech, "
              f"{len(results['productivity'])} software, "
              f"{len(results['excluded'])} excluded")

        return results


def classify_articles(articles: List[Dict]) -> Dict[str, List[Dict]]:
    """Classify articles."""
    classifier = BusinessOnlyClassifier()
    return classifier.classify_batch(articles)
