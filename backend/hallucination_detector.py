"""
Module de détection et correction des hallucinations dans le contenu généré par le LLM.
"""

import re
import json
import logging
from typing import Dict, List, Tuple, Optional, Set, Any
import asyncio
from collections import Counter

# Configuration du logging
logger = logging.getLogger(__name__)

class HallucinationDetector:
    """
    Détecte et vérifie les potentielles hallucinations 
    dans le contenu généré par le LLM.
    """
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
        
        # Patterns qui pourraient indiquer des hallucinations
        self.suspect_patterns = [
            r"(?:en|selon|d'après) (\w+ et al\., \d{4})",  # Citations académiques
            r"((?:une|des|l[ae]s?) (?:étude|recherche|analyse).+(?:a|ont) (?:démontré|montré|prouvé|suggéré|indiqué))",  # Références à des études non spécifiées
            r"((?:selon|d'après) (?:les|des) (?:statistiques|chiffres|données))",  # Références à des statistiques vagues
            r"((?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?\s*%)",  # Pourcentages spécifiques
            r"((?:en|durant|pendant|depuis) (?:les années|l'année) \d{4})"  # Années spécifiques
        ]
        
        # Expressions souvent associées à des incertitudes
        self.uncertainty_markers = [
            "probablement", "peut-être", "possiblement", "il est possible que",
            "il semble que", "on pourrait dire que", "on peut supposer que",
            "généralement", "typiquement", "en règle générale"
        ]
        
        # Dictionnaire pour mettre en cache les résultats de vérification
        self._verification_cache = {}
    
    async def check_content(self, content: str, context: Dict = None) -> Dict:
        """
        Vérifie le contenu généré pour détecter les potentielles hallucinations.
        
        Args:
            content: Le texte à vérifier.
            context: Contexte optionnel (données connues pour vérification).
            
        Returns:
            Un dictionnaire contenant les résultats de la vérification.
        """
        results = {
            "has_hallucinations": False,
            "confidence_score": 1.0,  # 1.0 = confiance totale
            "suspect_segments": [],    # Segments suspects détectés
            "verified_facts": [],      # Faits vérifiés comme corrects
            "uncertain_segments": [],  # Segments avec marqueurs d'incertitude
            "corrected_content": content,  # Version éventuellement corrigée du contenu
        }
        
        # Si le contenu est vide ou trop court, le considérer comme valide
        if not content or len(content) < 50:
            return results
        
        # 1. Détecter les segments potentiellement suspects
        suspect_segments = []
        for pattern in self.suspect_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                start, end = match.span()
                context_start = max(0, start - 50)
                context_end = min(len(content), end + 50)
                
                suspect_segments.append({
                    "text": match.group(0),
                    "context": content[context_start:context_end],
                    "position": (start, end),
                    "pattern_type": pattern,
                    "verified": False
                })
        
        # 2. Détecter les marqueurs d'incertitude
        uncertain_segments = []
        for marker in self.uncertainty_markers:
            for match in re.finditer(r'\b' + re.escape(marker) + r'\b', content, re.IGNORECASE):
                start, end = match.span()
                context_start = max(0, start - 30)
                context_end = min(len(content), end + 30)
                
                uncertain_segments.append({
                    "text": match.group(0),
                    "context": content[context_start:context_end],
                    "position": (start, end)
                })
        
        # 3. Vérifier les segments suspects par rapport au contenu connu
        if context and "sections" in context and "journal_entries" in context:
            verified_segments, suspect_segments = await self._verify_against_context(
                suspect_segments, context
            )
            results["verified_facts"] = verified_segments
        else:
            # Si pas de contexte fourni, on le reconstruit à partir du journal et des sections
            try:
                constructed_context = await self._construct_context(content)
                verified_segments, suspect_segments = await self._verify_against_context(
                    suspect_segments, constructed_context
                )
                results["verified_facts"] = verified_segments
            except Exception as e:
                logger.error(f"Erreur lors de la construction du contexte: {str(e)}")
                # En cas d'erreur, garder tous les segments comme suspects
                verified_segments = []
        
        # 4. Calculer le score de confiance
        if suspect_segments:
            # Le score diminue avec le nombre de segments suspects
            base_confidence = max(0.5, 1.0 - (len(suspect_segments) / 20))
            
            # Ajuster en fonction de l'importance des segments et de leur concentration
            total_chars = len(content)
            suspect_chars = sum(len(s["text"]) for s in suspect_segments)
            concentration = suspect_chars / total_chars if total_chars > 0 else 0
            
            # Formule: Plus grande concentration = moins de confiance
            confidence_score = base_confidence * (1 - (concentration * 0.7))
            
            results["confidence_score"] = max(0.1, confidence_score)
            results["has_hallucinations"] = True
        
        # 5. Corriger le contenu si nécessaire
        if results["has_hallucinations"]:
            corrected_content = self._correct_hallucinations(content, suspect_segments)
            results["corrected_content"] = corrected_content
        
        results["suspect_segments"] = suspect_segments
        results["uncertain_segments"] = uncertain_segments
        
        return results
    
    async def _construct_context(self, content: str) -> Dict:
        """
        Construit un contexte de vérification en recherchant les sections et entrées de journal pertinentes.
        
        Args:
            content: Le contenu à vérifier
            
        Returns:
            Un dictionnaire de contexte avec sections et entrées de journal pertinentes
        """
        # Extraire des mots-clés du contenu pour la recherche
        keywords = self._extract_keywords(content)
        search_query = " ".join(keywords[:10])  # Utiliser les 10 mots-clés les plus pertinents
        
        # Rechercher des sections pertinentes
        sections = await self.memory_manager.search_relevant_sections(search_query, limit=5)
        
        # Rechercher des entrées de journal pertinentes
        journal_entries = await self.memory_manager.search_relevant_journal(search_query, limit=10)
        
        return {
            "sections": sections,
            "journal_entries": journal_entries
        }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extrait les mots-clés les plus pertinents d'un texte"""
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text.split()
        
        # Filtrer les mots vides
        stopwords = {"le", "la", "les", "un", "une", "des", "et", "ou", "a", "à", "de", "du", "en", "est", 
                    "ce", "que", "qui", "dans", "par", "pour", "sur", "avec", "sans", "il", "elle", 
                    "ils", "elles", "nous", "vous", "je", "tu", "se", "sa", "son", "ses"}
        
        words = [word for word in words if word not in stopwords and len(word) > 3]
        
        # Compter les occurrences
        word_counts = Counter(words)
        
        # Retourner les mots les plus fréquents
        most_common = [word for word, _ in word_counts.most_common(20)]
        return most_common
    
    def _correct_hallucinations(self, content: str, suspect_segments: List[Dict]) -> str:
        """
        Corrige les segments suspects en les remplaçant par des formulations plus prudentes.
        
        Args:
            content: Le contenu original
            suspect_segments: Liste des segments suspects avec leurs positions
            
        Returns:
            Le contenu corrigé
        """
        # Si aucun segment suspect, retourner le contenu original
        if not suspect_segments:
            return content
        
        # Trier les segments par position décroissante pour éviter de fausser les positions
        segments_to_correct = sorted(suspect_segments, key=lambda x: x["position"][0], reverse=True)
        
        corrected_content = content
        for segment in segments_to_correct:
            start, end = segment["position"]
            original_text = segment["text"]
            
            # Sélectionner le type de correction selon le type de segment
            pattern_type = segment["pattern_type"]
            
            if "%" in original_text:
                # Pourcentages précis -> approximatifs
                replacement = self._create_correction(original_text, "approximatif", pattern_type)
            elif re.search(r'\d{4}', original_text):
                # Années précises -> périodes plus générales
                replacement = self._create_correction(original_text, "période", pattern_type)
            elif "selon" in original_text.lower() or "d'après" in original_text.lower():
                # Sources précises -> plus générales
                replacement = self._create_correction(original_text, "source", pattern_type)
            else:
                # Autres cas
                replacement = self._create_correction(original_text, "général", pattern_type)
            
            corrected_content = corrected_content[:start] + replacement + corrected_content[end:]
        
        return corrected_content
    
    def _create_correction(self, original_text: str, correction_type: str, pattern_type: str) -> str:
        """
        Crée une version corrigée ou atténuée d'un segment suspect.
        
        Args:
            original_text: Le texte original à corriger
            correction_type: Le type de correction à appliquer
            pattern_type: Le type de pattern détecté
            
        Returns:
            La version corrigée du texte
        """
        if correction_type == "approximatif":
            # Remplacer les pourcentages précis par des approximations
            return re.sub(r'(\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?\s*%', 'environ \\1%', original_text)
        
        elif correction_type == "période":
            # Atténuer les références temporelles précises
            if re.search(r'en \d{4}', original_text):
                return re.sub(r'en (\d{4})', 'vers \\1', original_text)
            else:
                return re.sub(r'(en|durant|pendant|depuis) (?:les années|l\'année) (\d{4})', 
                            '\\1 cette période', original_text)
        
        elif correction_type == "source":
            # Généraliser les références à des sources spécifiques
            if "selon" in original_text.lower():
                return re.sub(r'[Ss]elon ([^,\.]+)', 'selon certaines sources', original_text)
            elif "d'après" in original_text.lower():
                return re.sub(r'd\'après ([^,\.]+)', 'd\'après certaines analyses', original_text)
            else:
                return original_text
        
        else:  # "général"
            # Ajouter un marqueur d'incertitude
            return "il semblerait que " + original_text

    async def _verify_against_context(
        self, 
        suspect_segments: List[Dict],
        context: Dict
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Vérifie les segments suspects par rapport au contexte connu.
        
        Args:
            suspect_segments: Liste des segments suspects.
            context: Contexte connu (sections, entrées journal).
            
        Returns:
            Tuple (segments vérifiés, segments toujours suspects).
        """
        verified_segments = []
        still_suspect = []
        
        # Construction de la base de connaissances
        knowledge_base = ""
        for section in context.get("sections", []):
            if "content" in section:
                knowledge_base += section["content"] + "\n\n"
            elif "content_preview" in section:
                knowledge_base += section["content_preview"] + "\n\n"
                
        for entry in context.get("journal_entries", []):
            if "content" in entry:
                knowledge_base += entry["content"] + "\n\n"
        
        # Vérifier chaque segment suspect
        for segment in suspect_segments:
            # Générer une clé de cache unique pour ce segment
            cache_key = hashlib.md5((segment["text"] + knowledge_base[:500]).encode()).hexdigest()
            
            # Vérifier si ce segment a déjà été vérifié récemment
            if cache_key in self._verification_cache:
                cached_result = self._verification_cache[cache_key]
                if cached_result["verified"]:
                    segment["verified"] = True
                    segment["verification_source"] = cached_result.get("verification_source", "Cache")
                    verified_segments.append(segment)
                else:
                    still_suspect.append(segment)
                continue
            
            # Vérification littérale
            if segment["text"] in knowledge_base:
                segment["verified"] = True
                segment["verification_source"] = "Base de connaissances (correspondance exacte)"
                verified_segments.append(segment)
                
                # Mettre en cache ce résultat
                self._verification_cache[cache_key] = {
                    "verified": True,
                    "verification_source": "Base de connaissances (correspondance exacte)"
                }
                continue
            
            # Recherche plus approfondie
            search_query = segment["context"]
            found = False
            
            # Rechercher dans les sections pertinentes
            relevant_sections = await self.memory_manager.search_relevant_sections(search_query, limit=3)
            for section in relevant_sections:
                if self._check_semantic_similarity(segment["text"], section.get("content_preview", "")):
                    segment["verified"] = True
                    segment["verification_source"] = f"Section: {section['titre']}"
                    verified_segments.append(segment)
                    found = True
                    
                    # Mettre en cache ce résultat
                    self._verification_cache[cache_key] = {
                        "verified": True,
                        "verification_source": f"Section: {section['titre']}"
                    }
                    break
            
            if not found:
                # Rechercher dans les entrées de journal
                relevant_entries = await self.memory_manager.search_relevant_journal(search_query, limit=3)
                for entry in relevant_entries:
                    if self._check_semantic_similarity(segment["text"], entry.get("content", "")):
                        segment["verified"] = True
                        segment["verification_source"] = f"Journal: {entry.get('date', '')}"
                        verified_segments.append(segment)
                        found = True
                        
                        # Mettre en cache ce résultat
                        self._verification_cache[cache_key] = {
                            "verified": True,
                            "verification_source": f"Journal: {entry.get('date', '')}"
                        }
                        break
            
            if not found:
                still_suspect.append(segment)
                
                # Mettre en cache ce résultat négatif
                self._verification_cache[cache_key] = {
                    "verified": False
                }
        
        return verified_segments, still_suspect
    
    def _check_semantic_similarity(self, text1: str, text2: str) -> bool:
        """
        Vérifie si deux textes sont sémantiquement similaires.
        Version améliorée avec extraction d'entités et comparaison de contexte.
        
        Args:
            text1: Premier texte à comparer
            text2: Second texte à comparer
            
        Returns:
            bool: True si les textes sont sémantiquement similaires
        """
        # Extraire les mots significatifs de chaque texte
        words1 = set(self._extract_significant_words(text1))
        words2 = set(self._extract_significant_words(text2))
        
        # Pas de mots significatifs, considérer comme non similaire
        if not words1:
            return False
        
        # Calculer l'intersection des mots significatifs
        common_words = words1.intersection(words2)
        
        # Calculer le ratio de similarité
        similarity = len(common_words) / len(words1)
        
        # Extraire les entités nommées (personnes, lieux, organisations, dates)
        entities1 = self._extract_entities(text1)
        entities2 = self._extract_entities(text2)
        
        # Si les textes contiennent des entités en commun, augmenter la similarité
        common_entities = entities1.intersection(entities2)
        entity_boost = len(common_entities) * 0.1  # Chaque entité commune augmente la similarité
        
        # Score final
        final_score = min(1.0, similarity + entity_boost)
        
        # Seuil de décision
        return final_score >= 0.4
    
    def _extract_significant_words(self, text: str) -> List[str]:
        """
        Extrait les mots significatifs d'un texte en filtrant les mots vides
        et en normalisant.
        
        Args:
            text: Texte à analyser
            
        Returns:
            Liste des mots significatifs
        """
        # Nettoyer le texte
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text.split()
        
        # Filtrer les mots vides
        stopwords = {
            "le", "la", "les", "un", "une", "des", "et", "ou", "a", "à", "de", "du", "en", 
            "est", "ce", "que", "qui", "dans", "par", "pour", "sur", "avec", "sans", "il", 
            "elle", "ils", "elles", "nous", "vous", "je", "tu", "au", "aux", "se", "sa", 
            "son", "ses", "ce", "cette", "ces", "mon", "ton", "son", "ma", "ta", "sa"
        }
        
        # Retourner les mots significatifs (non-stopwords et longueur > 2)
        return [word for word in words if word not in stopwords and len(word) > 2]
    
    def _extract_entities(self, text: str) -> Set[str]:
        """
        Extrait les entités nommées d'un texte.
        Version simplifiée basée sur des patterns.
        
        Args:
            text: Texte à analyser
            
        Returns:
            Ensemble des entités détectées
        """
        entities = set()
        
        # Pattern pour les dates
        date_patterns = [
            r'\b\d{1,2}(?:er)?\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}\b',
            r'\b(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}\b',
            r'\b\d{4}\b'  # Années seules
        ]
        
        for pattern in date_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.add(match.group(0).lower())
        
        # Pattern pour les noms propres (simplifiés)
        name_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        for match in re.finditer(name_pattern, text):
            # Vérifier que ce n'est pas simplement le début d'une phrase
            if match.start() > 0 and text[match.start()-1] not in ".!?\n":
                entities.add(match.group(0).lower())
        
        # Pattern pour les pourcentages
        percentage_pattern = r'\b\d+(?:[,.]\d+)?%\b'
        for match in re.finditer(percentage_pattern, text):
            entities.add(match.group(0))
        
        return entities

    async def get_verification_status(self) -> Dict[str, Any]:
        """
        Retourne des statistiques sur les vérifications effectuées.
        
        Returns:
            Dictionnaire contenant les statistiques de vérification
        """
        return {
            "cache_size": len(self._verification_cache),
            "verified_ratio": sum(1 for v in self._verification_cache.values() if v.get("verified", False)) / max(1, len(self._verification_cache)),
            "last_verification_time": getattr(self, "_last_verification_time", None)
        }
    
    def clear_cache(self) -> None:
        """
        Vide le cache de vérifications.
        """
        self._verification_cache.clear()

# Fonction auxiliaire pour calculer le hachage MD5 (utilisée dans la classe)
import hashlib
def hashlib_md5(text: str) -> str:
    """Calcule le hachage MD5 d'un texte"""
    return hashlib.md5(text.encode()).hexdigest()