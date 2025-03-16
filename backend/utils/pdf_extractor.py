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
from typing import List, Dict, Any, Optional

# Configuration du logging
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

def extract_text_from_pdf(pdf_data: bytes) -> Optional[str]:
    """
    Extrait le texte d'un fichier PDF.
    
    Args:
        pdf_data: Les données PDF sous forme de bytes
        
    Returns:
        str: Le texte extrait du document PDF
        None: En cas d'erreur
    """
    # Normaliser l'entrée en BytesIO
    pdf_data_io = BytesIO(pdf_data)
    
    extracted_text = ""
    last_error = None
    
    # Essayer d'abord avec PyPDF2 s'il est disponible
    if PYPDF2_AVAILABLE:
        try:
            reader = PdfReader(pdf_data_io)
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
            last_error = str(e)
            logger.error(f"Erreur lors de l'extraction avec PyPDF2: {e}")
    
    # Essayer avec pdfminer.six s'il est disponible
    if PDFMINER_AVAILABLE:
        try:
            # pdfminer nécessite un fichier, donc nous devons sauvegarder les données temporairement
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                # Revenir au début du BytesIO
                pdf_data_io.seek(0)
                tmp_file.write(pdf_data_io.read())
                tmp_path = tmp_file.name
            
            try:
                extracted_text = pdfminer_extract_text(tmp_path)
            finally:
                # Nettoyer le fichier temporaire
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            
            return extracted_text
        
        except PDFSyntaxError as e:
            last_error = f"Erreur de syntaxe PDF: {str(e)}"
            logger.error(f"Erreur de syntaxe PDF: {e}")
        except Exception as e:
            last_error = str(e)
            logger.error(f"Erreur lors de l'extraction avec pdfminer: {e}")
    
    # Si aucune méthode n'a fonctionné, retourner None
    if not extracted_text:
        logger.error("Aucune méthode d'extraction n'a pu extraire du texte du PDF")
        if not last_error:
            last_error = "Impossible d'extraire le texte du PDF."
        return None
    
    return extracted_text

def extract_dates_from_text(text: str) -> List[tuple]:
    """
    Recherche et extrait les dates présentes dans le texte.
    
    Args:
        text: Le texte à analyser
        
    Returns:
        List[tuple]: Liste de tuples (position, date au format ISO)
    """
    # Pattern pour les dates au format français et international
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
    
    return date_positions

def extract_automatic_tags(text: str, threshold: float = 0.01) -> List[str]:
    """
    Extrait automatiquement des tags à partir du texte.
    
    Args:
        text: Le texte à analyser
        threshold: Seuil de fréquence pour considérer un mot comme tag
        
    Returns:
        List[str]: Liste de tags potentiels
    """
    # Extraction des mots (sans ponctuation, chiffres, etc.)
    words = re.findall(r'\b[a-zA-ZÀ-ÿ]{4,}\b', text.lower())
    
    # Filtrer les mots vides (stopwords)
    stopwords = set(['dans', 'avec', 'pour', 'cette', 'mais', 'avoir', 'faire', 
                     'plus', 'tout', 'bien', 'être', 'comme', 'nous', 'leur', 
                     'sans', 'vous', 'dont', 'alors', 'aussi', 'donc', 'cela',
                     'ceux', 'celle', 'celui', 'entre', 'pendant', 'depuis'])
    words = [w for w in words if w not in stopwords]
    
    # Compter les occurrences
    word_counts = {}
    for word in words:
        word_counts[word] = word_counts.get(word, 0) + 1
    
    total_words = len(words)
    if total_words == 0:
        return []
    
    # Sélectionner les mots qui dépassent le seuil
    potential_tags = [word for word, count in word_counts.items() 
                     if count / total_words > threshold and count > 1]
    
    # Limiter le nombre de tags
    return potential_tags[:5]

def analyze_entry_content(text: str) -> Dict[str, Any]:
    """
    Analyse le contenu d'une entrée pour en extraire des informations.
    
    Args:
        text: Le texte à analyser
        
    Returns:
        Dict: Informations extraites (type, entreprise, tags)
    """
    result = {
        "type_entree": "quotidien",  # valeur par défaut
        "entreprise_id": None,
        "tags": extract_automatic_tags(text)
    }
    
    # Détection de type d'entrée
    if re.search(r'\b(formation|cours|apprendre|étudier|apprentissage)\b', text.lower()):
        result["type_entree"] = "formation"
    elif re.search(r'\b(projet|développement|application|implémentation|feature)\b', text.lower()):
        result["type_entree"] = "projet"
    elif re.search(r'\b(réflexion|analyse|pensée|considération|bilan)\b', text.lower()):
        result["type_entree"] = "réflexion"
    
    return result

def process_pdf_file(file_content: bytes, filename: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Traite un fichier PDF et extrait son contenu sous forme d'entrées de journal.
    
    Args:
        file_content: Le contenu du fichier PDF
        filename: Le nom du fichier
        
    Returns:
        List[Dict]: Liste des entrées extraites
    """
    # Extraire le texte du PDF
    text = extract_text_from_pdf(file_content)
    
    if not text:
        logger.error(f"Impossible d'extraire du texte du PDF '{filename}'")
        return []
    
    # Rechercher les dates pour diviser le contenu
    date_positions = extract_dates_from_text(text)
    
    # Si aucune date n'est trouvée, créer une seule entrée avec la date actuelle
    if not date_positions:
        current_date = datetime.now().strftime("%Y-%m-%d")
        metadata = analyze_entry_content(text)
        return [{
            "date": current_date,
            "texte": text,
            "type_entree": metadata["type_entree"],
            "tags": metadata["tags"],
            "source_document": filename
        }]
    
    # Diviser le texte en entrées en fonction des dates trouvées
    entries = []
    for i, (position, date) in enumerate(date_positions):
        # Déterminer la fin de cette entrée (début de la prochaine ou fin du texte)
        next_position = date_positions[i+1][0] if i+1 < len(date_positions) else len(text)
        
        # Extraire le contenu
        content = text[position:next_position].strip()
        
        if content:
            # Analyser le contenu pour extraire des métadonnées
            metadata = analyze_entry_content(content)
            
            # Créer l'entrée
            entry = {
                "date": date,
                "texte": content,
                "type_entree": metadata["type_entree"],
                "tags": metadata["tags"],
                "source_document": filename
            }
            
            entries.append(entry)
    
    return entries