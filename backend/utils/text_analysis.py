from typing import List

def extract_automatic_tags(text: str) -> List[str]:
    # Implémentation simple d'extraction de tags
    common_words = ['le', 'la', 'les', 'un', 'une', 'des', 'et', 'ou', 'à', 'de', 'en']
    words = [w.lower() for w in text.split() if len(w) > 3 and w.lower() not in common_words]
    word_counts = {}
    for word in words:
        word_counts[word] = word_counts.get(word, 0) + 1
    return [word for word, count in sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:5]]