@echo off
echo =============================================
echo VERIFICATION DU PROCESSUS OLLAMA
echo =============================================

REM Vérifier si le processus Ollama est en cours d'exécution
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [32mOK: Ollama est en cours d'execution[0m
) else (
    echo [31mERREUR: Ollama n'est pas en cours d'execution[0m
    echo [31mVeuillez demarrer Ollama avec la commande: ollama serve[0m
    goto :check_installed
)

REM Vérifier si le port 11434 est en écoute
netstat -an | find "11434" | find "LISTENING" >NUL
if "%ERRORLEVEL%"=="0" (
    echo [32mOK: Le port 11434 est en ecoute[0m
) else (
    echo [31mERREUR: Le port 11434 n'est pas en ecoute[0m
    echo [31mOllama est peut-etre en cours de demarrage ou utilise un port different[0m
)

REM Ping sur l'API Ollama
curl -s -o nul -w "%%{http_code}" http://localhost:11434 >temp.txt
set /p HTTP_CODE=<temp.txt
del temp.txt

if "%HTTP_CODE%"=="200" (
    echo [32mOK: L'API Ollama répond (code HTTP 200)[0m
) else (
    echo [31mERREUR: L'API Ollama ne répond pas correctement (code HTTP %HTTP_CODE%)[0m
)

:check_installed
REM Vérifier l'installation d'Ollama
where ollama >NUL 2>NUL
if "%ERRORLEVEL%"=="0" (
    echo [32mOK: Ollama est installe[0m
    echo.
    echo [36mModeles disponibles:[0m
    ollama list
) else (
    echo [31mERREUR: Ollama n'est pas installe ou n'est pas dans le PATH[0m
    echo [31mInstallation: https://ollama.com/download[0m
)

echo.
echo =============================================
echo Pour tester l'integration avec votre application:
echo cd backend
echo python test_ollama.py
echo =============================================

pause