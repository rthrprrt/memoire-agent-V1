"""
Module de détection et correction des hallucinations dans le contenu généré par le LLM.
"""

import re
from typing import Dict, List, Tuple, Optional, Set

# On suppose que MemoryManager est importé depuis le module adéquat.
# Par exemple : from memory_manager import MemoryManager

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
        
        # 4. Calculer le score de confiance
        if suspect_segments:
            results["confidence_score"] = max(0.5, 1.0 - (len(suspect_segments) / 20))
            results["has_hallucinations"] = True
        
        # 5. Corriger le contenu si nécessaire
        if results["has_hallucinations"]:
            corrected_content = content
            # On trie les segments par position décroissante pour éviter de fausser les index
            suspect_segments.sort(key=lambda x: x["position"][0], reverse=True)
            
            for segment in suspect_segments:
                start, end = segment["position"]
                original_text = segment["text"]
                
                # Correction selon le type de segment détecté
                if "%" in original_text:
                    replacement = self._create_correction(original_text, "approximatif", segment["pattern_type"])
                elif re.search(r'\d{4}', original_text):
                    replacement = self._create_correction(original_text, "période", segment["pattern_type"])
                elif "selon" in original_text or "d'après" in original_text:
                    replacement = self._create_correction(original_text, "source", segment["pattern_type"])
                else:
                    replacement = self._create_correction(original_text, "général", segment["pattern_type"])
                
                corrected_content = corrected_content[:start] + replacement + corrected_content[end:]
            
            results["corrected_content"] = corrected_content
        
        results["suspect_segments"] = suspect_segments
        results["uncertain_segments"] = uncertain_segments
        
        return results
    
    def _create_correction(self, original_text: str, correction_type: str, pattern_type: str) -> str:
        """Crée une version corrigée ou atténuée d'un segment suspect."""
        if correction_type == "approximatif":
            return re.sub(r'(\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?\s*%', 'environ \\1%', original_text)
        elif correction_type == "période":
            return re.sub(r'(en|durant|pendant|depuis) (?:les années|l\'année) (\d{4})', 
                         '\\1 les années \\2', original_text)
        elif correction_type == "source":
            if "selon" in original_text or "d'après" in original_text:
                return re.sub(r'(selon|d\'après) ([^,\.]+)', 
                             'd\'après certaines sources', original_text)
            else:
                return original_text
        else:  # "général"
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
        for entry in context.get("journal_entries", []):
            if "content" in entry:
                knowledge_base += entry["content"] + "\n\n"
        
        for segment in suspect_segments:
            if segment["text"] in knowledge_base:
                segment["verified"] = True
                verified_segments.append(segment)
                continue
            
            search_query = segment["context"]
            relevant_sections = await self.memory_manager.search_relevant_sections(search_query, limit=3)
            relevant_entries = await self.memory_manager.search_relevant_journal(search_query, limit=3)
            found = False
            
            for section in relevant_sections:
                if self._check_semantic_similarity(segment["text"], section.get("content_preview", "")):
                    segment["verified"] = True
                    segment["verification_source"] = f"Section: {section['title']}"
                    verified_segments.append(segment)
                    found = True
                    break
            
            if not found:
                for entry in relevant_entries:
                    if self._check_semantic_similarity(segment["text"], entry.get("content", "")):
                        segment["verified"] = True
                        segment["verification_source"] = f"Journal: {entry.get('date', '')}"
                        verified_segments.append(segment)
                        found = True
                        break
            
            if not found:
                still_suspect.append(segment)
        
        return verified_segments, still_suspect
    
    def _check_semantic_similarity(self, text1: str, text2: str) -> bool:
        """
        Vérifie si deux textes sont sémantiquement similaires.
        (Version simplifiée basée sur la similarité de mots significatifs.)
        """
        words1 = set(self._extract_significant_words(text1))
        words2 = set(self._extract_significant_words(text2))
        common_words = words1.intersection(words2)
        if len(words1) > 0:
            similarity = len(common_words) / len(words1)
            return similarity >= 0.4
        return False
    
    def _extract_significant_words(self, text: str) -> List[str]:
        """Extrait les mots significatifs d'un texte."""
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text.split()
        stopwords = {"le", "la", "les", "un", "une", "des", "et", "ou", "a", "à", "de", "du", "en", "est", "ce", "que", "qui", "dans", "par", "pour", "sur", "avec", "sans", "il", "elle", "ils", "elles", "nous", "vous", "je", "tu"}
        return [word for word in words if word not in stopwords and len(word) > 2]
