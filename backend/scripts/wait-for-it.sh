#!/bin/bash
# Script d'attente pour vérifier si un service est accessible
# Usage: ./wait-for-it.sh host:port [-s] [-t timeout] [-- command args]
# -s: mode silencieux
# -t: timeout en secondes (défaut: 15)
# -- command args: commande à exécuter après l'attente

WAITFORIT_cmdname=${0##*/}

echoerr() { if [[ $WAITFORIT_QUIET -ne 1 ]]; then echo "$@" 1>&2; fi }

usage()
{
    cat << USAGE >&2
Usage:
    $WAITFORIT_cmdname host:port [-s] [-t timeout] [-- command args]
    -h HOST | --host=HOST       Hôte ou IP à tester
    -p PORT | --port=PORT       Port TCP à tester
    -s | --strict               Mode strict : quitter avec un code d'erreur
    -q | --quiet                Ne rien afficher
    -t TIMEOUT | --timeout=TIMEOUT
                                Timeout en secondes, 0 pour désactiver (défaut: 15)
    -- COMMAND ARGS             Commande à exécuter après la connexion au service
USAGE
    exit 1
}

wait_for()
{
    if [[ $WAITFORIT_TIMEOUT -gt 0 ]]; then
        echoerr "$WAITFORIT_cmdname: attente de $WAITFORIT_HOST:$WAITFORIT_PORT pendant $WAITFORIT_TIMEOUT secondes"
    else
        echoerr "$WAITFORIT_cmdname: attente de $WAITFORIT_HOST:$WAITFORIT_PORT sans timeout"
    fi
    
    WAITFORIT_start_ts=$(date +%s)
    while :
    do
        if [[ $WAITFORIT_ISBUSY -eq 1 ]]; then
            nc -z $WAITFORIT_HOST $WAITFORIT_PORT
            WAITFORIT_result=$?
        else
            (echo -n > /dev/tcp/$WAITFORIT_HOST/$WAITFORIT_PORT) >/dev/null 2>&1
            WAITFORIT_result=$?
        fi
        if [[ $WAITFORIT_result -eq 0 ]]; then
            WAITFORIT_end_ts=$(date +%s)
            echoerr "$WAITFORIT_cmdname: $WAITFORIT_HOST:$WAITFORIT_PORT est disponible après $((WAITFORIT_end_ts - WAITFORIT_start_ts)) secondes"
            break
        fi
        sleep 1
    done
    return $WAITFORIT_result
}

wait_for_wrapper()
{
    # Dans un sous-shell, notre signal sera transmis au processus wait_for
    if [[ $WAITFORIT_QUIET -eq 1 ]]; then
        timeout $WAITFORIT_TIMEOUT $0 --quiet --child --host=$WAITFORIT_HOST --port=$WAITFORIT_PORT --timeout=$WAITFORIT_TIMEOUT &
    else
        timeout $WAITFORIT_TIMEOUT $0 --child --host=$WAITFORIT_HOST --port=$WAITFORIT_PORT --timeout=$WAITFORIT_TIMEOUT &
    fi
    WAITFORIT_PID=$!
    trap "kill -INT -$WAITFORIT_PID" INT
    wait $WAITFORIT_PID
    WAITFORIT_RESULT=$?
    if [[ $WAITFORIT_RESULT -ne 0 ]]; then
        echoerr "$WAITFORIT_cmdname: timeout atteint lors de l'attente de $WAITFORIT_HOST:$WAITFORIT_PORT"
    fi
    return $WAITFORIT_RESULT
}

# Traitement des arguments de la ligne de commande
while [[ $# -gt 0 ]]
do
    case "$1" in
        *:* )
        WAITFORIT_hostport=(${1//:/ })
        WAITFORIT_HOST=${WAITFORIT_hostport[0]}
        WAITFORIT_PORT=${WAITFORIT_hostport[1]}
        shift 1
        ;;
        --child)
        WAITFORIT_CHILD=1
        shift 1
        ;;
        -q | --quiet)
        WAITFORIT_QUIET=1
        shift 1
        ;;
        -s | --strict)
        WAITFORIT_STRICT=1
        shift 1
        ;;
        -h)
        WAITFORIT_HOST="$2"
        if [[ $WAITFORIT_HOST == "" ]]; then break; fi
        shift 2
        ;;
        --host=*)
        WAITFORIT_HOST="${1#*=}"
        shift 1
        ;;
        -p)
        WAITFORIT_PORT="$2"
        if [[ $WAITFORIT_PORT == "" ]]; then break; fi
        shift 2
        ;;
        --port=*)
        WAITFORIT_PORT="${1#*=}"
        shift 1
        ;;
        -t)
        WAITFORIT_TIMEOUT="$2"
        if [[ $WAITFORIT_TIMEOUT == "" ]]; then break; fi
        shift 2
        ;;
        --timeout=*)
        WAITFORIT_TIMEOUT="${1#*=}"
        shift 1
        ;;
        --)
        shift
        WAITFORIT_CLI=("$@")
        break
        ;;
        --help)
        usage
        ;;
        *)
        echoerr "Option inconnue: $1"
        usage
        ;;
    esac
done

if [[ "$WAITFORIT_HOST" == "" || "$WAITFORIT_PORT" == "" ]]; then
    echoerr "Erreur: vous devez spécifier un hôte et un port"
    usage
fi

WAITFORIT_TIMEOUT=${WAITFORIT_TIMEOUT:-15}
WAITFORIT_STRICT=${WAITFORIT_STRICT:-0}
WAITFORIT_CHILD=${WAITFORIT_CHILD:-0}
WAITFORIT_QUIET=${WAITFORIT_QUIET:-0}

# Vérifier si on utilise un outil externe comme netcat
WAITFORIT_ISBUSY=0
if [[ $WAITFORIT_CHILD -gt 0 ]]; then
    WAITFORIT_ISBUSY=1
    shift 1
fi

# Installer netcat s'il n'est pas disponible
if ! command -v nc >/dev/null; then
    echoerr "Installation de netcat..."
    apt-get update && apt-get install -y netcat
fi

if [[ $WAITFORIT_CHILD -gt 0 ]]; then
    wait_for
    WAITFORIT_RESULT=$?
    exit $WAITFORIT_RESULT
else
    if [[ $WAITFORIT_TIMEOUT -gt 0 ]]; then
        wait_for_wrapper
        WAITFORIT_RESULT=$?
    else
        wait_for
        WAITFORIT_RESULT=$?
    fi
fi

if [[ $WAITFORIT_CLI != "" ]]; then
    if [[ $WAITFORIT_RESULT -ne 0 && $WAITFORIT_STRICT -eq 1 ]]; then
        echoerr "$WAITFORIT_cmdname: strict mode, sortie avec le code d'erreur $WAITFORIT_RESULT"
        exit $WAITFORIT_RESULT
    fi
    exec "${WAITFORIT_CLI[@]}"
else
    exit $WAITFORIT_RESULT
fi