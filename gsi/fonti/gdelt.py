"""GDELT DOC 2.0: titoli di stampa (una richiesta ogni 5 secondi, solo per i titoli che si sono mossi)."""
from __future__ import annotations
import time

import requests

from .. import config

URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_ultima = 0.0


def leggi_risposta(dati: dict) -> list[tuple]:
    """JSON ArtList -> (url, titolo, testata, pubblicato ISO, lingua)."""
    righe = []
    for a in (dati or {}).get("articles") or []:
        url, titolo = a.get("url"), (a.get("title") or "").strip()
        if not url or not titolo:
            continue
        s = a.get("seendate") or ""          # 20261120T143000Z
        pub = f"{s[0:4]}-{s[4:6]}-{s[6:8]}T{s[9:11]}:{s[11:13]}:{s[13:15]}Z" if len(s) >= 15 else None
        righe.append((url, titolo, a.get("domain"), pub, a.get("language")))
    return righe


def cerca(query: str, inizio: str, fine: str, massimo: int = 25) -> list[tuple]:
    """inizio/fine nel formato AAAAMMGGHHMMSS. Solleva in caso di errore o limite superato."""
    global _ultima
    for tentativo in range(3):
        att = config.PAUSA_GDELT - (time.monotonic() - _ultima)
        if att > 0:
            time.sleep(att)
        _ultima = time.monotonic()
        r = requests.get(URL, params={"query": query, "mode": "ArtList", "format": "json",
                                      "maxrecords": massimo, "sort": "DateDesc",
                                      "startdatetime": inizio, "enddatetime": fine}, timeout=60)
        if r.status_code != 429 or tentativo == 2:
            break
        time.sleep(15 * (tentativo + 1))      # limite superato: attesa crescente
    r.raise_for_status()
    testo = r.text.strip()
    if not testo.startswith("{"):
        raise RuntimeError(f"GDELT: risposta non JSON ({testo[:120]})")
    return leggi_risposta(r.json())
