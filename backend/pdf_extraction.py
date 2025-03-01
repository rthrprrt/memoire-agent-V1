"""
Module d'extraction de texte à partir de fichiers PDF
avec fonctionnalités d'organisation et d'analyse de contenu.
"""

import os
import re
import tempfile
from datetime import datetime
from io import BytesIO
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Tentative d'importation de PyPDF2
try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    logger.warning("PyPDF2 n'est pas installé. L'extraction PDF utilisera pdfminer si disponible.")
    PYPDF2_AVAILABLE = False

# Tentative d'importation de pdfminer.six
try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
    from pdfminer.pdfparser import PDFSyntaxError
    PDFMINER_AVAILABLE = True
except ImportError:
    logger.warning("pdfminer.six n'est pas installé. L'extraction PDF pourrait être limitée.")
    PDFMINER_AVAILABLE = False

class PDFExtractor:
    """
    Classe pour extraire et analyser le contenu de fichiers PDF.
    Prend en charge la détection de structure, de dates et d'autres métadonnées.
    """
    
    def __init__(self):
        """Initialise l'extracteur PDF."""
        self.last_error = None
        
        # Vérifier si au moins une bibliothèque d'extraction est disponible
        if not PYPDF2_AVAILABLE and not PDFMINER_AVAILABLE:
            raise ImportError("Aucune bibliothèque d'extraction PDF n'est disponible. Veuillez installer PyPDF2 ou pdfminer.six.")
    
    def extract_text(self, pdf_data):
        """
        Extrait le texte d'un fichier PDF.
        
        Args:
            pdf_data: Les données PDF sous forme de bytes ou BytesIO
            
        Returns:
            str: Le texte extrait du document PDF
            None: En cas d'erreur
        """
        self.last_error = None
        
        # Normaliser l'entrée en BytesIO
        if isinstance(pdf_data, bytes):
            pdf_data = BytesIO(pdf_data)
        
        extracted_text = ""
        
        # Essayer d'abord avec PyPDF2 s'il est disponible
        if PYPDF2_AVAILABLE:
            try:
                reader = PdfReader(pdf_data)
                texts = []
                
                for page in reader.pages:
                    texts.append(page.extract_text())
                
                extracted_text = "\n\n".join([t for t in texts if t])
                
                # Si l'extraction a réussi, retourner le texte
                if extracted_text.strip():
                    return extracted_text
                
                # Sinon, essayer avec pdfminer
                logger.info("PyPDF2 n'a pas pu extraire de texte, essai avec pdfminer...")
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Erreur lors de l'extraction avec PyPDF2: {e}")
        
        # Essayer avec pdfminer.six s'il est disponible
        if PDFMINER_AVAILABLE:
            try:
                # pdfminer nécessite un fichier, donc nous devons sauvegarder les données temporairement
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    # Revenir au début du BytesIO
                    pdf_data.seek(0)
                    tmp_file.write(pdf_data.read())
                    tmp_path = tmp_file.name
                
                try:
                    extracted_text = pdfminer_extract_text(tmp_path)
                finally:
                    # Nettoyer le fichier temporaire
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                
                return extracted_text
            
            except PDFSyntaxError as e:
                self.last_error = f"Erreur de syntaxe PDF: {str(e)}"
                logger.error(f"Erreur de syntaxe PDF: {e}")
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Erreur lors de l'extraction avec pdfminer: {e}")
        
        # Si aucune méthode n'a fonctionné, retourner None
        if not extracted_text:
            logger.error("Aucune méthode d'extraction n'a pu extraire du texte du PDF")
            if not self.last_error:
                self.last_error = "Impossible d'extraire le texte du PDF."
            return None
        
        return extracted_text
    
    def extract_entries(self, pdf_data, split_by_date=True):
        """
        Extrait des entrées de journal à partir d'un PDF, en les séparant par dates si demandé.
        
        Args:
            pdf_data: Les données PDF sous forme de bytes ou BytesIO
            split_by_date (bool): Si True, tente de diviser le contenu en entrées distinctes par date
            
        Returns:
            list: Liste des entrées sous la forme [(date, texte), ...]
            None: En cas d'erreur
        """
        # Extraire le texte complet
        text = self.extract_text(pdf_data)
        if not text:
            return None
        
        # Si on ne veut pas diviser par date, retourner le texte complet
        if not split_by_date:
            current_date = datetime.now().strftime("%Y-%m-%d")
            return [(current_date, text)]
        
        # Rechercher les dates au format français et international
        entries = []
        
        # Pattern pour les dates au format "Lundi 18 février 2025" (français)
        # Et pour les formats courants comme "2025-02-18", "18/02/2025", etc.
        date_patterns = [
            # Format français avec jour de la semaine
            r'(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})',
            # Format français sans jour de la semaine
            r'(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})',
            # Format ISO
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',
            # Format européen
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
        ]
        
        # Dictionnaire de conversion mois français -> numéro
        month_to_number = {
            'janvier': '01', 'février': '02', 'mars': '03', 'avril': '04',
            'mai': '05', 'juin': '06', 'juillet': '07', 'août': '08',
            'septembre': '09', 'octobre': '10', 'novembre': '11', 'décembre': '12'
        }
        
        # Rechercher toutes les occurrences potentielles de dates
        date_positions = []
        
        for pattern in date_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                date_str = match.group(0)
                position = match.start()
                
                # Convertir la date au format ISO (YYYY-MM-DD)
                try:
                    if 'janvier' in date_str.lower() or 'février' in date_str.lower() or 'mars' in date_str.lower():
                        # Format français avec ou sans jour de la semaine
                        parts = date_str.split()
                        
                        # Extraire les composants en fonction du format
                        if parts[0].lower() in ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']:
                            # Avec jour de la semaine
                            day = parts[1]
                            month = parts[2].lower()
                            year = parts[3]
                        else:
                            # Sans jour de la semaine
                            day = parts[0]
                            month = parts[1].lower()
                            year = parts[2]
                        
                        month_num = month_to_number.get(month, '01')
                        iso_date = f"{year}-{month_num}-{day.zfill(2)}"
                    elif '-' in date_str or '/' in date_str:
                        # Format ISO ou européen
                        separator = '-' if '-' in date_str else '/'
                        parts = date_str.split(separator)
                        
                        if len(parts[0]) == 4:
                            # Format ISO (YYYY-MM-DD)
                            year = parts[0]
                            month = parts[1].zfill(2)
                            day = parts[2].zfill(2)
                        else:
                            # Format européen (DD-MM-YYYY)
                            day = parts[0].zfill(2)
                            month = parts[1].zfill(2)
                            year = parts[2]
                        
                        iso_date = f"{year}-{month}-{day}"
                    else:
                        # Format non reconnu
                        continue
                    
                    # Vérifier si la date est valide
                    datetime.strptime(iso_date, "%Y-%m-%d")
                    date_positions.append((position, iso_date))
                    
                except ValueError:
                    # Date invalide, ignorer
                    continue
        
        # Trier les positions de dates
        date_positions.sort()
        
        # Si aucune date n'est trouvée, retourner le texte entier avec la date actuelle
        if not date_positions:
            current_date = datetime.now().strftime("%Y-%m-%d")
            return [(current_date, text)]
        
        # Diviser le texte en entrées en fonction des dates trouvées
        for i, (position, date) in enumerate(date_positions):
            # Déterminer la fin de cette entrée (début de la prochaine ou fin du texte)
            next_position = date_positions[i+1][0] if i+1 < len(date_positions) else len(text)
            
            # Extraire le contenu
            content = text[position:next_position].strip()
            
            # Ajouter l'entrée si elle a du contenu
            if content:
                entries.append((date, content))
        
        return entries
    
    def analyze_content(self, text):
        """
        Analyse le contenu du texte pour extraire des informations pertinentes,
        comme l'entreprise mentionnée, les projets, les compétences, etc.
        
        Args:
            text (str): Le texte à analyser
            
        Returns:
            dict: Un dictionnaire contenant les informations extraites
        """
        result = {
            "type_entree": "quotidien",  # valeur par défaut
            "entreprise_id": None,
            "tags": []
        }
        
        # Détection de type d'entrée
        if "formation" in text.lower() or "apprendre" in text.lower() or "cours" in text.lower():
            result["type_entree"] = "formation"
        elif "projet" in text.lower() or "développement" in text.lower() or "application" in text.lower():
            result["type_entree"] = "projet"
        elif "analyse" in text.lower() or "réflexion" in text.lower() or "pensée" in text.lower():
            result["type_entree"] = "réflexion"
        
        # Extraction simple de tags potentiels (mots clés)
        # Dans une version plus avancée, utiliser un modèle NLP serait plus précis
        common_words = ["le", "la", "les", "un", "une", "des", "et", "ou", "dans", "par", "pour", "avec", "sans", "que"]
        words = re.findall(r'\b[a-zA-ZÀ-ÿ]{4,}\b', text.lower())
        word_counts = {}
        
        for word in words:
            if word not in common_words:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Prendre les mots les plus fréquents comme tags potentiels
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        result["tags"] = [word for word, count in sorted_words[:5] if count > 1]
        
        return result

# Fonction d'utilité pour l'importation depuis l'API
def process_pdf_file(file_content, filename=None):
    """
    Traite un fichier PDF et extrait son contenu sous forme d'entrées de journal.
    
    Args:
        file_content (bytes): Le contenu du fichier PDF
        filename (str, optional): Le nom du fichier
        
    Returns:
        list: Liste des entrées sous la forme [{date, texte, metadata}, ...]
        None: En cas d'erreur
    """
    extractor = PDFExtractor()
    entries = extractor.extract_entries(BytesIO(file_content))
    
    if not entries:
        error_msg = extractor.last_error or "Impossible d'extraire des entrées du PDF."
        logger.error(f"Erreur lors du traitement du PDF '{filename}': {error_msg}")
        return None
    
    # Analyser chaque entrée pour extraire des métadonnées
    result = []
    for date, content in entries:
        metadata = extractor.analyze_content(content)
        entry = {
            "date": date,
            "texte": content,
            "type_entree": metadata["type_entree"],
            "entreprise_id": metadata["entreprise_id"],
            "tags": metadata["tags"],
            "source_document": filename
        }
        result.append(entry)
    
    return result

# Test standalone
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    try:
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        entries = process_pdf_file(pdf_content, os.path.basename(pdf_path))
        
        if entries:
            print(f"Extraction réussie: {len(entries)} entrées trouvées.")
            for i, entry in enumerate(entries):
                print(f"\nEntrée {i+1}:")
                print(f"Date: {entry['date']}")
                print(f"Type: {entry['type_entree']}")
                print(f"Tags: {', '.join(entry['tags'])}")
                print(f"Contenu: {entry['texte'][:200]}...")
        else:
            print("Échec de l'extraction.")
    
    except Exception as e:
        print(f"Erreur: {str(e)}")
        sys.exit(1)