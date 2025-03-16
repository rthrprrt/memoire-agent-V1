import re
from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter

class AdaptiveTextSplitter:
    """
    Splitter de texte adaptatif qui prend en compte la structure
    et le contenu sémantique du texte pour un découpage intelligent.
    """
    def __init__(self):
        # Différentes stratégies de chunking selon le type de contenu
        self.splitters = {
            "default": RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                length_function=len,
                separators=["\n\n", "\n", ". ", ", ", " ", ""]
            ),
            "long_form": RecursiveCharacterTextSplitter(
                chunk_size=800,
                chunk_overlap=150,
                length_function=len,
                separators=["\n\n", "\n", ". ", ", ", " ", ""]
            ),
            "list": RecursiveCharacterTextSplitter(
                chunk_size=300,
                chunk_overlap=50,
                length_function=len,
                separators=["\n\n", "\n", ". ", ", ", " ", ""]
            ),
            "technical": RecursiveCharacterTextSplitter(
                chunk_size=400,
                chunk_overlap=100,
                length_function=len,
                separators=["\n\n", "\n", "; ", ". ", ", ", " ", ""]
            )
        }
        
        # Patterns pour détecter différents types de contenu
        self.content_patterns = {
            "list": r'(?:^|\n)(?:\d+\.\s|\*\s|-\s|\[\s?\]|\[\w\])',
            "technical": r'(?:import|def|class|function|var|const|if|for|while|try|except|\{|\}|console\.log)',
            "long_form": r'(?:(?:\w+\s){20,})'
        }
    
    def split_text(self, text: str) -> List[str]:
        """Divise le texte en chunks en fonction du type de contenu détecté"""
        content_type = self._determine_content_type(text)
        splitter = self.splitters.get(content_type, self.splitters["default"])
        return splitter.split_text(text)
    
    def split_texts(self, texts: List[str]) -> List[str]:
        """Divise plusieurs textes en chunks"""
        all_chunks = []
        for text in texts:
            chunks = self.split_text(text)
            all_chunks.extend(chunks)
        return all_chunks
    
    def _determine_content_type(self, text: str) -> str:
        """Détermine le type de contenu du texte"""
        scores = {
            "list": 0,
            "technical": 0,
            "long_form": 0,
            "default": 1
        }
        
        for content_type, pattern in self.content_patterns.items():
            matches = re.findall(pattern, text)
            scores[content_type] = len(matches)
        
        line_ratio = text.count('\n') / max(1, len(text))
        if line_ratio > 0.05:
            scores["list"] += 3
        
        sentences = re.split(r'[.!?]+', text)
        avg_sentence_length = sum(len(s) for s in sentences) / max(1, len(sentences))
        if avg_sentence_length > 150:
            scores["long_form"] += 5
        elif avg_sentence_length < 60:
            scores["list"] += 2
        
        if re.search(r'[<>$%#@{}()\[\]+=]', text):
            scores["technical"] += 3
        
        return max(scores.items(), key=lambda x: x[1])[0]

def extract_automatic_tags(text: str, threshold: float = 0.01) -> List[str]:
    """
    Extrait automatiquement des tags à partir du texte.
    
    Args:
        text: Texte à analyser
        threshold: Seuil de fréquence pour considérer un mot comme tag
        
    Returns:
        Liste de tags potentiels
    """
    import re
    from collections import Counter
    
    # Extraction des mots (sans ponctuation, chiffres, etc.)
    words = re.findall(r'\b[a-zA-ZÀ-ÿ]{4,}\b', text.lower())
    
    # Filtrer les mots vides (stopwords)
    stopwords = set(['dans', 'avec', 'pour', 'cette', 'mais', 'avoir', 'faire', 
                     'plus', 'tout', 'bien', 'être', 'comme', 'nous', 'leur', 
                     'sans', 'vous', 'dont', 'alors', 'cette', 'cette', 'cela',
                     'ceux', 'entre', 'même', 'donc', 'ainsi', 'chaque', 'tous'])
    words = [w for w in words if w not in stopwords]
    
    # Compter les occurrences
    word_counts = Counter(words)
    total_words = len(words)
    
    if total_words == 0:
        return []
    
    # Sélectionner les mots qui dépassent le seuil
    potential_tags = [word for word, count in word_counts.items() 
                    if count / total_words > threshold]
    
    # Limiter le nombre de tags
    return potential_tags[:5]