"""Giudizi di prevedibilita' a 10 anni redatti da Claude dopo una ricerca su internet (opinioni, non dati).

Per ogni titolo: livello (Alta, Media, Bassa), da cosa e' fatto il vantaggio competitivo, minaccia principale, fatti
recenti trovati nella ricerca con la data, che cosa farebbe cambiare idea e le fonti. Il giudizio conta subito nel
verdetto della strategia A; l'utente lo sovrascrive nel foglio GIUDIZI.
"""
import json
from pathlib import Path

DATA_GIUDIZIO = "2026-11-23"
LIVELLI = ("Alta", "Media", "Bassa")
# ticker -> {livello, fossato, minaccia, fatti_recenti, cambierebbe_idea, fonti: [{titolo, url, data}], revisione?}
PREVEDIBILITA: dict[str, dict] = json.loads((Path(__file__).with_name("dati_prevedibilita.json")).read_text(encoding="utf-8"))


def normalizza(x):
    """'media', ' MEDIA ' -> 'Media'; qualunque altro valore -> None."""
    if isinstance(x, str) and x.strip().capitalize() in LIVELLI:
        return x.strip().capitalize()
    return None


def livello_usato(ticker: str, giudizio: dict | None, prev_claude=None):
    """-> (livello o None, fonte). Il giudizio dell'utente prevale su quello di Claude."""
    u = normalizza((giudizio or {}).get("prevedibilita"))
    if u:
        return u, "tuo giudizio"
    c = prev_claude if prev_claude is not None else (PREVEDIBILITA.get(ticker) or {}).get("livello")
    if normalizza(c):
        return normalizza(c), "giudizio di Claude"
    return None, "nessun giudizio"
