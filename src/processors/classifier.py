"""
Simple classifier - most content from company sites is relevant.
Just basic categorization and exclusion of obvious garbage.
"""

from typing import List, Dict, Tuple


class BusinessOnlyClassifier:
    """Simple classifier for company-sourced content."""

    # Only exclude obvious garbage (rare from direct company sources)
    GARBAGE_TERMS = [
        'cookie policy', 'privacy policy', 'terms of service',
        'subscribe to newsletter', 'sign up', 'login',
    ]

    # Neurotech indicators
    NEUROTECH_TERMS = [
        'eeg', 'brain', 'neuro', 'headband', 'wearable', 'bci',
        'neural', 'cognitive', 'focus', 'meditation', 'attention',
        'muse', 'neurable', 'neurosity', 'emotiv', 'dreem', 'apollo',
        'brainco', 'kernel', 'flow neuroscience', 'interaxon',
    ]

    # Productivity/software indicators
    PRODUCTIVITY_TERMS = [
        'app', 'screen time', 'blocker', 'digital wellness',
        'productivity', 'distraction', 'opal', 'freedom',
        'phone addiction', 'notification', 'focus app',
    ]

    def classify(self, article: Dict) -> Tuple[str, float, str]:
        """Classify article."""
        title = article.get('title', '').lower()
        source = article.get('source', '').lower()
        company = article.get('company', '').lower()

        combined = f"{title} {source} {company}"

        # Check garbage
        for term in self.GARBAGE_TERMS:
            if term in combined:
                return ('excluded', 0.0, 'garbage')

        # Check neurotech
        for term in self.NEUROTECH_TERMS:
            if term in combined:
                return ('neurotech', 1.0, f'matched: {term}')

        # Check productivity
        for term in self.PRODUCTIVITY_TERMS:
            if term in combined:
                return ('productivity', 1.0, f'matched: {term}')

        # Default to neurotech (since most companies are neurotech)
        return ('neurotech', 0.5, 'default')

    def classify_batch(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Classify all."""
        results = {'neurotech': [], 'productivity': [], 'excluded': []}

        for article in articles:
            category, score, reason = self.classify(article)
            article['category'] = category
            article['relevance_score'] = score
            results[category].append(article)

        # Sort by score
        results['neurotech'] = sorted(results['neurotech'], key=lambda x: x['relevance_score'], reverse=True)
        results['productivity'] = sorted(results['productivity'], key=lambda x: x['relevance_score'], reverse=True)

        print(f"Classified: {len(results['neurotech'])} neurotech, "
              f"{len(results['productivity'])} software, "
              f"{len(results['excluded'])} excluded")

        return results


def classify_articles(articles: List[Dict]) -> Dict[str, List[Dict]]:
    """Classify articles."""
    classifier = BusinessOnlyClassifier()
    return classifier.classify_batch(articles)
