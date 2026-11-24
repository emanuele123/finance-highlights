"""Catene del valore: come funziona il mercato di ogni azienda, dai fornitori ai clienti finali, e chi si tiene i guadagni.

Struttura (catene, anelli, posizione dei 120 titoli) redatta da Claude; protagonisti, forza contrattuale, fatti e fonti
completati con una ricerca su internet il 24/11/2026. Testi descrittivi: non entrano nei punteggi. I margini degli anelli
sono invece calcolati con formule dai bilanci dei titoli dell'universo (foglio CATENE).
"""
import json
from pathlib import Path

DATA_RICERCA = "2026-11-24"
_FILE = Path(__file__).with_name("dati_catene.json")
CATENE: dict[str, dict] = json.loads(_FILE.read_text(encoding="utf-8")) if _FILE.exists() else {}


def posizione(ticker: str):
    """-> (id catena, indice dell'anello) oppure (None, None)."""
    for cid, c in CATENE.items():
        for i, a in enumerate(c["anelli"]):
            if ticker in a.get("titoli", []):
                return cid, i
    return None, None


def testo_catena(cid: str, idx: int) -> str:
    """'Macchinari → Fabbricazione → [PROGETTAZIONE] → Cloud → Clienti' con l'anello del titolo evidenziato."""
    return " → ".join(f"[{a['nome'].upper()}]" if i == idx else a["nome"] for i, a in enumerate(CATENE[cid]["anelli"]))


def _anello(a: dict) -> str:
    p = a.get("protagonisti") or ""
    return a["nome"] + (f" ({p})" if p else "")


def profilo(ticker: str) -> dict:
    """Testi per il foglio CATENE e la SCHEDA (stringhe; None se il titolo non e' in alcuna catena)."""
    cid, i = posizione(ticker)
    if cid is None:
        return {}
    c, an = CATENE[cid], CATENE[cid]["anelli"]
    a = an[i]
    altri = [f"{t} ({x['nome']})" for x in an for t in x.get("titoli", []) if t != ticker]
    forza = a.get("forza")
    return {"catena_id": cid, "catena": c["nome"], "anello_id": f"{cid}|{a['id']}", "anello": a["nome"], "cosa": a["cosa"],
            "testo": testo_catena(cid, i),
            "a_monte": _anello(an[i - 1]) if i > 0 else "Nessuno: è il primo anello della catena",
            "a_valle": _anello(an[i + 1]) if i + 1 < len(an) else "Nessuno: è l'ultimo anello della catena",
            "forza": (f"{forza}: {a.get('perche', '')}".strip().rstrip(":") if forza else None),
            "protagonisti": a.get("protagonisti"), "fatti": a.get("fatti") or None,
            "chi_cattura": c.get("chi_cattura"), "tendenza": c.get("tendenza"),
            "altri": "; ".join(altri) or "Nessun altro titolo dell'universo"}
