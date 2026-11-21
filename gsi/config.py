"""Configurazione: percorsi e parametri di scarico (file configurazione.ini facoltativo)."""
from __future__ import annotations
import configparser
import os
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
CARTELLA_DATI = RADICE / "dati"
FILE_DB = CARTELLA_DATI / "archivio.sqlite"
FILE_EXCEL = RADICE / "Global_Stock_Intelligence.xlsx"
FILE_CONFIG = RADICE / "configurazione.ini"

ANNI_STORICO = 11            # i prezzi si riscaricano sempre per intero
GIORNI_BILANCI = 7           # i bilanci si riscaricano dopo 7 giorni
PAUSA_YAHOO = 0.6            # secondi tra due chiamate a Yahoo
TENTATIVI = 4                # tentativi per chiamata, con attese crescenti
ATTESA_BASE = 5.0            # secondi: 5, 15, 45 ...
PAUSA_GDELT = 5.5            # GDELT: una richiesta ogni 5 secondi
PAUSA_SEC = 0.15             # SEC: massimo 10 richieste al secondo
GIORNI_PREZZO_VECCHIO = 5
GIORNI_BILANCIO_VECCHIO = 500


def leggi_config() -> configparser.ConfigParser:
    c = configparser.ConfigParser()
    if FILE_CONFIG.exists():
        c.read(FILE_CONFIG, encoding="utf-8")
    return c


def sec_user_agent() -> str | None:
    """User-Agent per SEC EDGAR ("Nome Cognome email"). Senza, SEC non viene usata."""
    ua = os.environ.get("GSI_SEC_USER_AGENT") or leggi_config().get("sec", "user_agent", fallback="")
    ua = ua.strip()
    return ua or None
