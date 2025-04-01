"""
Module pour l'analyse de texte avancée, l'extraction de tags
et la génération de matrices de co-occurrence pour détecter les thématiques.
"""

import re
import math
import logging
from typing import List, Dict, Tuple, Set, Union, Optional, Any
from collections import Counter, defaultdict
from datetime import datetime

# Configuration du logging
logger = logging.getLogger(__name__)

# Stopwords français de base
STOPWORDS_FR = set([
    'au', 'aux', 'avec', 'ce', 'ces', 'dans', 'de', 'des', 'du', 'elle', 'en',
    'et', 'eux', 'il', 'ils', 'je', 'la', 'le', 'les', 'leur', 'lui', 'ma',
    'mais', 'me', 'même', 'mes', 'moi', 'mon', 'nos', 'notre', 'nous', 'ou',
    'par', 'pas', 'pour', 'qu', 'que', 'qui', 'sa', 'se', 'si', 'son', 'sur',
    'ta', 'te', 'tes', 'toi', 'ton', 'tu', 'un', 'une', 'votre', 'vous', 'vos',
    'comme', 'être', 'avoir', 'faire', 'dire', 'aller', 'voir', 'savoir', 'pouvoir', 
    'falloir', 'vouloir', 'venir', 'devoir', 'prendre', 'partir', 'mettre', 
    'trouver', 'donner', 'parler', 'comprendre'
])

# Mots vides supplémentaires spécifiques au contexte du mémoire
ADDITIONAL_STOPWORDS = set([
    'jour', 'journée', 'aujourd', 'hui', 'semaine', 'mois', 'année',
    'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche',
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
    'septembre', 'octobre', 'novembre', 'décembre', 'alternance', 'école', 
    'entreprise', 'travail', 'cours', 'mémoire'
])

# Combinaison des stopwords
ALL_STOPWORDS = STOPWORDS_FR.union(ADDITIONAL_STOPWORDS)

class TagExtractor:
    """
    Classe pour l'extraction de tags pertinents à partir de texte.
    Utilise diverses méthodes statistiques et linguistiques pour identifier
    les concepts clés dans un texte.
    """
    
    def __init__(self, language: str = "fr", min_word_length: int = 3, 
                 max_tags: int = 10, min_frequency: int = 2):
        """
        Initialise l'extracteur de tags
        
        Args:
            language: La langue du texte (fr par défaut)
            min_word_length: Longueur minimale des mots à considérer
            max_tags: Nombre maximum de tags à extraire
            min_frequency: Fréquence minimale pour qu'un mot soit considéré
        """
        self.language = language
        self.min_word_length = min_word_length
        self.max_tags = max_tags
        self.min_frequency = min_frequency
        
        # Initialiser la liste des stopwords selon la langue
        self.stopwords = ALL_STOPWORDS
        
        # Ajouter des mots spécifiques à ne jamais utiliser comme tags
        self.blacklisted_tags = [
            "import", "erreur", "importerreur", "error", "date_from_filename",
            "fichier", "document", "extraction", "texte", "contenu", "analyse"
        ]
        
        self.stopwords.update(self.blacklisted_tags)
        
        # Liste de sujets techniques pertinents à rechercher prioritairement
        self.technical_subjects = [
            "microsoft", "sharepoint", "azure", "aws", "google", "cloud", "devops", 
            "kubernetes", "docker", "python", "javascript", "typescript", "react", "angular", 
            "vue", "nodejs", "database", "sql", "nosql", "mongodb", "postgresql", "mysql",
            "api", "rest", "graphql", "microservices", "backend", "frontend", "fullstack",
            "agile", "scrum", "kanban", "jira", "git", "github", "gitlab", "cicd", "jenkins",
            "terraform", "ansible", "cybersecurity", "machine learning", "intelligence artificielle",
            "ia", "data science", "big data", "hadoop", "spark", "etl", "kafka", "elasticsearch",
            "web", "mobile", "app", "application", "testing", "automation", "integration",
            "php", "java", "spring", "dotnet", "csharp", "c#", "interface", "architecture",
            "powerbi", "power automate", "power apps", "flow", "automate", "workflow", "dashboard",
            "rapport", "projet", "étude", "développement", "programmation", "application", "formation",
            "équipe", "réunion", "daily", "meeting", "présentation", "documentation", "rapport",
            "client", "ticketing", "résolution", "bug", "problème", "solution", "déploiement",
            "technique", "technologie", "innovation", "digital", "numérique", "optimisation"
        ]
        
        # Expressions régulières pour nettoyage et tokenization
        self.word_pattern = re.compile(r'\\b[a-zA-ZÀ-ÿ]{' + str(min_word_length) + r',}\\b')
        
    def extract_tags(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Extrait les tags les plus pertinents d'un texte
        
        Args:
            text: Le texte à analyser
            context: Contexte supplémentaire (date, type d'entrée, etc.)
            
        Returns:
            Liste de tags pertinents
        """
        if not text or len(text.strip()) < 10:
            return ["projet"]  # Tag par défaut
        
        # Nettoyage du texte
        text = self._preprocess_text(text)
        
        # Rechercher d'abord des termes techniques spécifiques
        technical_tags = []
        for subject in self.technical_subjects:
            if subject in text.lower() and subject not in technical_tags:
                technical_tags.append(subject)
                
        # Tokenization et filtrage des mots
        tokens = self._tokenize_text(text)
        
        # Si pas assez de tokens après filtrage mais des tags techniques trouvés, utiliser ces derniers
        if len(tokens) < 3:
            if technical_tags:
                return technical_tags[:self.max_tags]
            return ["projet"]
        
        # Calcul des scores TF-IDF pour les tokens
        word_counts = Counter(tokens)
        total_words = len(tokens)
        
        # Filtrer les mots trop peu fréquents et les termes techniques déjà identifiés
        filtered_words = {word: count for word, count in word_counts.items() 
                         if count >= self.min_frequency and word not in technical_tags}
        
        # Si pas assez de mots après filtrage de fréquence, combiner avec les tags techniques
        if len(filtered_words) < 3:
            most_common = [word for word, _ in word_counts.most_common(self.max_tags - len(technical_tags))]
            combined_tags = technical_tags + most_common
            return combined_tags[:self.max_tags]
        
        # Calcul du score pour chaque mot (fréquence normalisée)
        word_scores = {}
        for word, count in filtered_words.items():
            term_frequency = count / total_words
            word_scores[word] = term_frequency
        
        # Tri des mots par score décroissant
        sorted_words = sorted(word_scores.items(), key=lambda x: x[1], reverse=True)
        common_tags = [word for word, score in sorted_words[:(self.max_tags - len(technical_tags))]]
        
        # Combinaison des tags techniques (prioritaires) et des tags courants
        combined_tags = technical_tags + common_tags
        
        # Vérification finale pour supprimer tous les tags blacklistés
        final_tags = [tag for tag in combined_tags if tag.lower() not in self.blacklisted_tags]
        
        # S'assurer qu'il y a au moins un tag
        if not final_tags:
            return ["projet"]
            
        return final_tags[:self.max_tags]
        
    def _preprocess_text(self, text: str) -> str:
        """
        Prétraite le texte avant l'extraction (nettoyage, normalisation)
        
        Args:
            text: Le texte brut
            
        Returns:
            Texte prétraité
        """
        # Conversion en minuscules
        text = text.lower()
        
        # Suppression des URLs
        text = re.sub(r'https?://\S+', '', text)
        
        # Suppression des caractères spéciaux et ponctuation
        text = re.sub(r'[^\w\s\'-àáâäæçèéêëìíîïòóôöùúûüÿœÀÁÂÄÆÇÈÉÊËÌÍÎÏÒÓÔÖÙÚÛÜŸŒ]', ' ', text)
        
        # Normalisation des espaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
        
    def _tokenize_text(self, text: str) -> List[str]:
        """
        Découpe le texte en tokens et filtre les mots vides
        
        Args:
            text: Le texte prétraité
            
        Returns:
            Liste de tokens significatifs
        """
        # Découpage en mots
        words = text.split()
        
        # Filtrage des mots trop courts et des stopwords
        filtered_words = [
            word for word in words 
            if len(word) >= self.min_word_length 
            and word not in self.stopwords
        ]
        
        return filtered_words

class TagMatrix:
    """
    Classe pour la création et l'analyse d'une matrice de co-occurrence de tags.
    Permet d'identifier les thématiques principales et les associations entre concepts.
    """
    
    def __init__(self):
        """
        Initialise la matrice de tags
        """
        # Matrice de co-occurrence (dictionnaire imbriqué)
        self.co_occurrence = defaultdict(lambda: defaultdict(int))
        # Comptage d'occurrences individuelles
        self.tag_counts = Counter()
        # Nombre total d'entrées traitées
        self.entry_count = 0
        # Date de la première et dernière entrée
        self.first_date = None
        self.last_date = None
        
    def add_entry(self, tags: List[str], date: Optional[str] = None, 
                 weight: float = 1.0, metadata: Optional[Dict[str, Any]] = None):
        """
        Ajoute une entrée de journal à la matrice de tags
        
        Args:
            tags: Liste de tags de l'entrée
            date: Date de l'entrée (format YYYY-MM-DD)
            weight: Poids de l'entrée (1.0 par défaut)
            metadata: Métadonnées supplémentaires
        """
        if not tags:
            return
            
        # Normaliser les tags (minuscules, suppression des doublons)
        tags = [tag.lower().strip() for tag in tags]
        tags = list(set(tags))  # Supprimer les doublons
        
        # Mise à jour du compteur d'entrées
        self.entry_count += 1
        
        # Mise à jour des dates min/max si date fournie
        if date:
            try:
                entry_date = datetime.strptime(date, "%Y-%m-%d").date()
                if self.first_date is None or entry_date < self.first_date:
                    self.first_date = entry_date
                if self.last_date is None or entry_date > self.last_date:
                    self.last_date = entry_date
            except ValueError:
                # Ignorer les dates invalides
                pass
                
        # Mise à jour des compteurs individuels
        for tag in tags:
            self.tag_counts[tag] += weight
            
        # Mise à jour de la matrice de co-occurrence
        for i, tag1 in enumerate(tags):
            for tag2 in tags[i+1:]:
                self.co_occurrence[tag1][tag2] += weight
                self.co_occurrence[tag2][tag1] += weight
    
    def get_top_tags(self, limit: int = 20) -> List[Tuple[str, int]]:
        """
        Retourne les tags les plus fréquents
        
        Args:
            limit: Nombre maximum de tags à retourner
            
        Returns:
            Liste de tuples (tag, fréquence) triés par fréquence décroissante
        """
        return self.tag_counts.most_common(limit)
    
    def get_top_co_occurrences(self, limit: int = 20) -> List[Tuple[Tuple[str, str], int]]:
        """
        Retourne les paires de tags qui apparaissent le plus souvent ensemble
        
        Args:
            limit: Nombre maximum de paires à retourner
            
        Returns:
            Liste de tuples ((tag1, tag2), fréquence) triés par fréquence décroissante
        """
        co_occurrences = []
        for tag1, related in self.co_occurrence.items():
            for tag2, count in related.items():
                if tag1 < tag2:  # Évite les doublons (a,b) et (b,a)
                    co_occurrences.append(((tag1, tag2), count))
        
        return sorted(co_occurrences, key=lambda x: x[1], reverse=True)[:limit]
    
    def get_related_tags(self, tag: str, limit: int = 10) -> List[Tuple[str, int]]:
        """
        Retourne les tags les plus souvent associés à un tag donné
        
        Args:
            tag: Le tag dont on veut connaître les associations
            limit: Nombre maximum de tags à retourner
            
        Returns:
            Liste de tuples (tag, fréquence de co-occurrence) 
        """
        tag = tag.lower().strip()
        if tag not in self.co_occurrence:
            return []
            
        related = self.co_occurrence[tag]
        return sorted(related.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    def extract_themes(self, min_tags: int = 3, max_themes: int = 5) -> List[Dict[str, Any]]:
        """
        Extrait les thématiques principales à partir de la matrice de co-occurrence
        
        Args:
            min_tags: Nombre minimum de tags par thématique
            max_themes: Nombre maximum de thématiques à extraire
            
        Returns:
            Liste de thématiques, chacune contenant un nom, des tags et un score
        """
        if not self.co_occurrence:
            return []
            
        # Extraction de thématiques par clustering simple
        themes = []
        remaining_tags = set(self.tag_counts.keys())
        
        while len(themes) < max_themes and remaining_tags:
            # Prendre le tag le plus fréquent comme point de départ
            seed_tags = [tag for tag in self.tag_counts.most_common() if tag[0] in remaining_tags]
            if not seed_tags:
                break
                
            seed_tag = seed_tags[0][0]
            theme_tags = {seed_tag}
            
            # Trouver les tags fortement associés
            related = self.get_related_tags(seed_tag, limit=10)
            for tag, weight in related:
                if tag in remaining_tags and len(theme_tags) < min_tags * 2:
                    theme_tags.add(tag)
            
            # Si la thématique est trop petite, ignorer
            if len(theme_tags) < min_tags:
                remaining_tags.remove(seed_tag)
                continue
                
            # Calculer le score de la thématique (somme des fréquences des tags)
            theme_score = sum(self.tag_counts[tag] for tag in theme_tags)
            
            # Identifier les tags principaux de la thématique
            theme_key_tags = sorted(
                [(tag, self.tag_counts[tag]) for tag in theme_tags],
                key=lambda x: x[1],
                reverse=True
            )[:min_tags]
            
            # Générer un nom pour la thématique basé sur les 2-3 tags principaux
            theme_name = " / ".join([tag for tag, _ in theme_key_tags[:3]])
            
            # Ajouter la thématique à la liste
            theme = {
                "name": theme_name,
                "tags": list(theme_tags),
                "key_tags": [tag for tag, _ in theme_key_tags],
                "score": theme_score,
                "size": len(theme_tags)
            }
            themes.append(theme)
            
            # Retirer les tags utilisés
            remaining_tags -= theme_tags
        
        # Trier les thématiques par score
        return sorted(themes, key=lambda x: x["score"], reverse=True)
    
    def get_tag_evolution(self, interval: str = "month") -> Dict[str, List[Tuple[str, int]]]:
        """
        Analyse l'évolution des tags dans le temps
        
        Args:
            interval: Intervalle d'analyse ('day', 'week', 'month')
            
        Returns:
            Dictionnaire {tag: [(période, fréquence), ...]}
        """
        # Cette méthode requiert des données temporelles
        # Elle sera implémentée ultérieurement
        # avec l'ajout des dates aux entrées de journal
        return {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convertit la matrice en dictionnaire pour sérialisation
        
        Returns:
            Dictionnaire représentant la matrice
        """
        return {
            "co_occurrence": dict(self.co_occurrence),
            "tag_counts": dict(self.tag_counts),
            "entry_count": self.entry_count,
            "first_date": self.first_date.isoformat() if self.first_date else None,
            "last_date": self.last_date.isoformat() if self.last_date else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TagMatrix':
        """
        Crée une matrice à partir d'un dictionnaire sérialisé
        
        Args:
            data: Dictionnaire représentant la matrice
            
        Returns:
            Instance de TagMatrix
        """
        matrix = cls()
        
        # Restaurer les compteurs
        matrix.tag_counts = Counter(data.get("tag_counts", {}))
        matrix.entry_count = data.get("entry_count", 0)
        
        # Restaurer les dates
        if data.get("first_date"):
            matrix.first_date = datetime.fromisoformat(data["first_date"]).date()
        if data.get("last_date"):
            matrix.last_date = datetime.fromisoformat(data["last_date"]).date()
        
        # Restaurer la matrice de co-occurrence
        co_occurrence = data.get("co_occurrence", {})
        for tag1, related in co_occurrence.items():
            for tag2, count in related.items():
                matrix.co_occurrence[tag1][tag2] = count
        
        return matrix

def extract_automatic_tags(text: str, max_tags: int = 7, threshold: float = 0.01) -> List[str]:
    """
    Extrait automatiquement des tags à partir du texte en utilisant TagExtractor.
    
    Args:
        text: Le texte à analyser
        max_tags: Nombre maximum de tags à extraire
        threshold: Seuil de fréquence pour considérer un mot comme tag
        
    Returns:
        Liste de tags potentiels
    """
    # Liste de mots à ne jamais inclure comme tags car ils sont liés à l'import et pas au contenu
    blacklisted_tags = [
        "import", "erreur", "importerreur", "error", "date_from_filename",
        "fichier", "document", "extraction", "texte", "contenu", "analyse"
    ]
    
    # Utiliser l'extracteur de tags
    extractor = TagExtractor(max_tags=max_tags, min_frequency=1)
    tags = extractor.extract_tags(text)
    
    # Filtrer les tags blacklistés
    filtered_tags = [tag for tag in tags if tag.lower() not in blacklisted_tags]
    
    # Si aucun tag valide n'est trouvé, utiliser un tag par défaut
    if not filtered_tags:
        return ["projet"]
        
    return filtered_tags

def analyze_tag_relationships(entries: List[Dict[str, Any]]) -> TagMatrix:
    """
    Analyse les relations entre tags dans un ensemble d'entrées
    
    Args:
        entries: Liste d'entrées de journal avec des tags
        
    Returns:
        Matrice de tags avec les relations entre tags
    """
    matrix = TagMatrix()
    
    for entry in entries:
        tags = entry.get("tags", [])
        date = entry.get("date")
        
        if tags:
            matrix.add_entry(tags, date=date)
    
    return matrix