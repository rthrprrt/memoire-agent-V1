#!/usr/bin/env python
"""
Script de diagnostic des problèmes courants d'Ollama
"""

import os
import sys
import platform
import socket
import subprocess
import psutil
import requests
import time
from typing import Dict, List, Tuple, Any, Optional

# Configuration du logging
try:
    from core.logging_config import get_logger
    logger = get_logger("ollama_diagnostics")
except ImportError:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("ollama_diagnostics")

# Configuration
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_TIMEOUT = 5  # secondes

class OllamaDiagnostics:
    """Classe de diagnostic pour Ollama"""
    
    def __init__(self):
        self.system_info = self._get_system_info()
        self.results = {
            "system": {},
            "ollama_process": {},
            "ollama_api": {},
            "models": {},
            "network": {},
            "resources": {}
        }
    
    def _get_system_info(self) -> Dict[str, str]:
        """Collecte les informations sur le système"""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
            "hostname": socket.gethostname(),
            "cpu_count": os.cpu_count(),
            "total_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2)
        }
    
    def check_ollama_process(self) -> Dict[str, Any]:
        """Vérifie si le processus Ollama est en cours d'exécution"""
        result = {"running": False, "pid": None, "command": None, "memory_usage": None}
        
        # Recherche du processus Ollama
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Sur Windows, le processus s'appelle ollama.exe
                # Sur Linux/Mac, il s'appelle ollama
                if proc.info['name'] and ('ollama' in proc.info['name'].lower()):
                    result["running"] = True
                    result["pid"] = proc.info['pid']
                    result["command"] = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else None
                    result["memory_usage"] = round(proc.memory_info().rss / (1024**2), 2)  # En MB
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        self.results["ollama_process"] = result
        return result
    
    def check_port_availability(self) -> Dict[str, Any]:
        """Vérifie si le port d'Ollama est en écoute"""
        result = {"port_open": False, "port": 11434}
        
        try:
            # Extrait le port de OLLAMA_HOST
            if ":" in OLLAMA_HOST:
                host_parts = OLLAMA_HOST.split(":")
                if len(host_parts) > 2:
                    # Cas http://localhost:11434
                    port = int(host_parts[2].split("/")[0])
                else:
                    # Cas localhost:11434
                    port = int(host_parts[1].split("/")[0])
            else:
                port = 11434
                
            result["port"] = port
            
            # Vérifie si le port est ouvert
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            connect_result = sock.connect_ex(('localhost', port))
            sock.close()
            
            result["port_open"] = connect_result == 0
            
        except Exception as e:
            result["error"] = str(e)
        
        self.results["network"]["port"] = result
        return result
    
    def check_api_health(self) -> Dict[str, Any]:
        """Vérifie si l'API Ollama répond"""
        result = {"reachable": False, "status_code": None, "response_time": None}
        
        try:
            start_time = time.time()
            response = requests.get(OLLAMA_HOST, timeout=DEFAULT_TIMEOUT)
            result["response_time"] = round((time.time() - start_time) * 1000, 2)  # En ms
            
            result["reachable"] = response.status_code == 200
            result["status_code"] = response.status_code
            
        except requests.exceptions.RequestException as e:
            result["error"] = str(e)
        
        self.results["ollama_api"]["health"] = result
        return result
    
    def check_api_endpoints(self) -> Dict[str, Any]:
        """Vérifie les principaux endpoints de l'API Ollama"""
        endpoints = {
            "/api/tags": {"method": "GET", "data": None},
            "/api/generate": {"method": "POST", "data": {"model": "mistral:7b", "prompt": "Bonjour", "stream": False}},
            "/api/embeddings": {"method": "POST", "data": {"model": "mistral:7b", "prompt": "Bonjour"}}
        }
        
        results = {}
        
        for endpoint, config in endpoints.items():
            result = {"reachable": False, "status_code": None, "response_time": None}
            
            try:
                url = f"{OLLAMA_HOST}{endpoint}"
                start_time = time.time()
                
                if config["method"] == "GET":
                    response = requests.get(url, timeout=DEFAULT_TIMEOUT)
                else:
                    response = requests.post(url, json=config["data"], timeout=DEFAULT_TIMEOUT)
                
                result["response_time"] = round((time.time() - start_time) * 1000, 2)  # En ms
                result["reachable"] = 200 <= response.status_code < 300
                result["status_code"] = response.status_code
                
                # Extraction de données spécifiques selon l'endpoint
                if endpoint == "/api/tags" and result["reachable"]:
                    models = response.json().get("models", [])
                    result["models_count"] = len(models)
                    result["models"] = [model.get("name") for model in models]
                
            except requests.exceptions.RequestException as e:
                result["error"] = str(e)
            
            results[endpoint] = result
        
        self.results["ollama_api"]["endpoints"] = results
        return results
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Vérifie les ressources système disponibles"""
        result = {}
        
        # CPU
        result["cpu"] = {
            "percent": psutil.cpu_percent(interval=1),
            "count": psutil.cpu_count(),
            "logical_count": psutil.cpu_count(logical=True)
        }
        
        # Mémoire
        mem = psutil.virtual_memory()
        result["memory"] = {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "used_percent": mem.percent
        }
        
        # Disque
        disk = psutil.disk_usage('/')
        result["disk"] = {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "used_percent": disk.percent
        }
        
        # GPU (si disponible)
        try:
            # Vérifier si nvidia-smi est disponible (NVIDIA GPUs)
            result["gpu"] = self._check_nvidia_gpu()
        except:
            result["gpu"] = {"available": False, "error": "Impossible de détecter GPU"}
        
        self.results["resources"] = result
        return result
    
    def _check_nvidia_gpu(self) -> Dict[str, Any]:
        """Vérifie la disponibilité et l'état des GPUs NVIDIA"""
        result = {"available": False}
        
        try:
            # Exécuter nvidia-smi en mode CSV pour obtenir les informations
            output = subprocess.check_output(
                ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu', 
                 '--format=csv,noheader,nounits'], 
                universal_newlines=True
            )
            
            gpus = []
            for i, line in enumerate(output.strip().split('\n')):
                parts = [part.strip() for part in line.split(',')]
                if len(parts) >= 5:
                    gpus.append({
                        "id": i,
                        "name": parts[0],
                        "memory_total_mb": float(parts[1]),
                        "memory_used_mb": float(parts[2]),
                        "memory_free_mb": float(parts[3]),
                        "temperature_c": float(parts[4])
                    })
            
            result["available"] = len(gpus) > 0
            result["count"] = len(gpus)
            result["gpus"] = gpus
            
        except (subprocess.SubprocessError, FileNotFoundError):
            result["available"] = False
            result["error"] = "nvidia-smi non disponible"
        
        return result
    
    def check_models(self) -> Dict[str, Any]:
        """Vérifie les modèles disponibles sur Ollama"""
        result = {"available": False, "count": 0, "models": []}
        
        try:
            response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=DEFAULT_TIMEOUT)
            
            if response.status_code == 200:
                models_data = response.json().get("models", [])
                result["available"] = True
                result["count"] = len(models_data)
                
                models = []
                for model in models_data:
                    model_info = {
                        "name": model.get("name"),
                        "size_gb": round(model.get("size", 0) / (1024**3), 2),
                        "modified": model.get("modified")
                    }
                    models.append(model_info)
                
                result["models"] = models
            else:
                result["error"] = f"Code de réponse: {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            result["error"] = str(e)
        
        self.results["models"] = result
        return result
    
    def diagnose(self):
        """Effectue tous les diagnostics et affiche un résumé"""
        logger.info("Début du diagnostic Ollama...")
        
        # Vérification système
        self.results["system"] = self.system_info
        logger.info(f"Système: {self.system_info['os']} {self.system_info['os_version']}")
        
        # Vérification du processus
        process_info = self.check_ollama_process()
        if process_info["running"]:
            logger.info(f"✅ Processus Ollama en cours d'exécution (PID: {process_info['pid']})")
            logger.info(f"   Utilisation mémoire: {process_info['memory_usage']} MB")
        else:
            logger.error("❌ Processus Ollama non trouvé - Ollama n'est pas en cours d'exécution")
            logger.info("   Démarrez Ollama avec: ollama serve")
        
        # Vérification du port
        port_info = self.check_port_availability()
        if port_info["port_open"]:
            logger.info(f"✅ Port {port_info['port']} ouvert et en écoute")
        else:
            logger.error(f"❌ Port {port_info['port']} fermé ou non accessible")
        
        # Vérification de l'API
        api_health = self.check_api_health()
        if api_health["reachable"]:
            logger.info(f"✅ API Ollama accessible (temps de réponse: {api_health['response_time']} ms)")
        else:
            error_msg = api_health.get("error", f"Code HTTP: {api_health.get('status_code')}")
            logger.error(f"❌ API Ollama non accessible - {error_msg}")
        
        # Vérification des endpoints si l'API est disponible
        if api_health["reachable"]:
            logger.info("Vérification des endpoints de l'API...")
            endpoints = self.check_api_endpoints()
            
            for endpoint, info in endpoints.items():
                if info["reachable"]:
                    logger.info(f"✅ Endpoint {endpoint} accessible (temps: {info['response_time']} ms)")
                    if endpoint == "/api/tags" and "models_count" in info:
                        logger.info(f"   {info['models_count']} modèles trouvés")
                else:
                    error_msg = info.get("error", f"Code HTTP: {info.get('status_code')}")
                    logger.error(f"❌ Endpoint {endpoint} non accessible - {error_msg}")
        
        # Vérification des ressources système
        logger.info("Vérification des ressources système...")
        resources = self.check_system_resources()
        
        # CPU
        cpu_info = resources["cpu"]
        logger.info(f"CPU: {cpu_info['count']} cœurs ({cpu_info['logical_count']} threads), utilisation: {cpu_info['percent']}%")
        
        # Mémoire
        mem_info = resources["memory"]
        logger.info(f"Mémoire: {mem_info['total_gb']} GB total, {mem_info['available_gb']} GB disponible ({mem_info['used_percent']}% utilisé)")
        
        # GPU
        gpu_info = resources["gpu"]
        if gpu_info.get("available", False):
            for gpu in gpu_info.get("gpus", []):
                logger.info(f"GPU {gpu['id']}: {gpu['name']}, {gpu['memory_total_mb']} MB total, {gpu['memory_free_mb']} MB libre, {gpu['temperature_c']}°C")
        else:
            logger.warning("Aucun GPU NVIDIA détecté")
        
        # Vérification des modèles
        if api_health["reachable"]:
            logger.info("Vérification des modèles disponibles...")
            models_info = self.check_models()
            
            if models_info["available"] and models_info["count"] > 0:
                logger.info(f"✅ {models_info['count']} modèles disponibles:")
                for model in models_info["models"]:
                    logger.info(f"   - {model['name']} ({model['size_gb']} GB)")
            else:
                logger.warning("❌ Aucun modèle disponible sur Ollama")
                logger.info("   Utilisez 'ollama pull mistral:7b' pour télécharger un modèle")
        
        return self.results
    
    def get_recommendations(self) -> List[str]:
        """Génère des recommandations basées sur les diagnostics"""
        recommendations = []
        
        # Vérifier si Ollama est en cours d'exécution
        if not self.results["ollama_process"].get("running", False):
            recommendations.append("Démarrez Ollama avec la commande: ollama serve")
        
        # Vérifier si le port est ouvert
        if not self.results["network"].get("port", {}).get("port_open", False):
            recommendations.append(f"Vérifiez qu'aucune autre application n'utilise le port {self.results['network']['port'].get('port', 11434)}")
        
        # Vérifier la mémoire disponible
        mem_info = self.results["resources"].get("memory", {})
        if mem_info.get("available_gb", 0) < 4:
            recommendations.append("Votre système manque de mémoire RAM disponible. Fermez d'autres applications pour libérer de la mémoire.")
        
        # Vérifier les modèles disponibles
        if not self.results["models"].get("count", 0):
            recommendations.append("Téléchargez au moins un modèle avec: ollama pull mistral:7b")
        
        # Vérifier l'API
        api_health = self.results["ollama_api"].get("health", {})
        if not api_health.get("reachable", False):
            if "connection refused" in api_health.get("error", "").lower():
                recommendations.append("Assurez-vous que Ollama est démarré et en cours d'exécution")
            elif "timeout" in api_health.get("error", "").lower():
                recommendations.append("Le temps de réponse d'Ollama est trop long, vérifiez les ressources système")
        
        return recommendations
    
    def print_summary(self):
        """Affiche un résumé des diagnostics"""
        logger.info("\n" + "=" * 50)
        logger.info("RÉSUMÉ DU DIAGNOSTIC OLLAMA")
        logger.info("=" * 50)
        
        # Statut global
        ollama_running = self.results["ollama_process"].get("running", False)
        api_reachable = self.results["ollama_api"].get("health", {}).get("reachable", False)
        models_available = self.results["models"].get("count", 0) > 0
        
        if ollama_running and api_reachable and models_available:
            logger.info("✅ OLLAMA EST OPÉRATIONNEL")
        elif ollama_running and api_reachable:
            logger.info("⚠️ OLLAMA EST PARTIELLEMENT OPÉRATIONNEL (aucun modèle disponible)")
        elif ollama_running:
            logger.info("⚠️ OLLAMA EST EN COURS D'EXÉCUTION MAIS L'API N'EST PAS ACCESSIBLE")
        else:
            logger.info("❌ OLLAMA N'EST PAS OPÉRATIONNEL")
        
        # Recommandations
        recommendations = self.get_recommendations()
        if recommendations:
            logger.info("\nRECOMMANDATIONS:")
            for i, rec in enumerate(recommendations, 1):
                logger.info(f"{i}. {rec}")
        
        logger.info("\nPour tester l'intégration avec votre application:")
        logger.info("python backend/test_ollama.py")
        
        logger.info("=" * 50)

# Point d'entrée du script
if __name__ == "__main__":
    diagnostics = OllamaDiagnostics()
    diagnostics.diagnose()
    diagnostics.print_summary()