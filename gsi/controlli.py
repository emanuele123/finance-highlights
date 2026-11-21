"""Controlli di qualita' dopo ogni scarico: prezzi recenti, valuta attesa, nome somigliante,
salti anomali dello storico, eta' dei bilanci. Esito: OK / DA VERIFICARE / ERRORE con motivo."""
from __future__ import annotations
import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher

from . import config

CENTESIMI = {"GBp": "GBP", "GBX": "GBP", "ZAc": "ZAR", "ILA": "ILS"}
_RUMORE = {"inc", "plc", "sa", "spa", "ag", "se", "nv", "the", "adr", "co", "corp", "corporation",
           "company", "ltd", "limited", "ab", "asa", "as", "group", "holding", "holdings", "and",
           "of", "de", "di", "classe", "class", "publ", "sab", "kk", "oyj", "cie", "compagnie",
           "societa", "per", "azioni", "international", "a", "b", "s", "p"}


def valuta_unita(valuta_fonte: str | None) -> tuple[str | None, bool]:
    """'GBp' -> ('GBP', True): la fonte quota in centesimi e i prezzi vanno divisi per 100."""
    if valuta_fonte in CENTESIMI:
        return CENTESIMI[valuta_fonte], True
    return valuta_fonte, False


def _parole(nome: str) -> list[str]:
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\([^)]*\)", " ", s).replace("&", " ")
    s = re.sub(r"[^a-z0-9 ]", "", s.replace("-", " ").replace(".", "").replace("'", ""))
    return [p for p in s.split() if p]


def nome_somiglia(atteso: str, fonte: str | None) -> bool:
    """Vero se il nome della fonte e' compatibile con quello atteso (parola significativa in
    comune, sigla formata dalle iniziali, oppure somiglianza complessiva >= 0,6)."""
    if not fonte:
        return False
    pa, pf = _parole(atteso), _parole(fonte)
    sa = [p for p in pa if p not in _RUMORE] or pa
    unito = "".join(pf)
    for p in sa:
        if p in pf or (len(p) >= 4 and p in unito):
            return True
    iniziali_tutte = "".join(p[0] for p in pf)
    iniziali = "".join(p[0] for p in pf if p not in _RUMORE)
    for p in sa:
        if len(p) >= 3 and (iniziali.startswith(p) or iniziali_tutte.startswith(p)):
            return True
    return SequenceMatcher(None, " ".join(pa), " ".join(pf)).ratio() >= 0.6


def salti_anomali(chiusure: list[tuple[str, float]], soglia: float = 0.45) -> list[str]:
    """Variazioni giornaliere oltre la soglia su chiusure gia' rettificate per i frazionamenti:
    indizio di un'operazione sul capitale non rettificata dalla fonte."""
    out = []
    for (d0, c0), (d1, c1) in zip(chiusure, chiusure[1:]):
        if c0 and c1 and c0 > 0 and abs(c1 / c0 - 1) > soglia:
            out.append(f"salto del {100 * (c1 / c0 - 1):+.0f}% il {d1}")
    return out


def valuta_titolo(*, oggi: date, n_prezzi: int, ultimo_prezzo: str | None, valuta_attesa: str | None,
                  centesimi_attesi: bool, valuta_fonte: str | None, valuta_bil_attesa: str | None,
                  valuta_bil_fonte: str | None, nome_atteso: str, nome_fonte: str | None,
                  salti: list[str], richiede_bilanci: bool, ultimo_esercizio: str | None,
                  n_esercizi: int, tipo_fonte: str | None = None, tipo_atteso: str | None = None
                  ) -> tuple[str, list[str]]:
    motivi: list[str] = []
    if n_prezzi == 0 or not ultimo_prezzo:
        return "ERRORE", ["nessun prezzo scaricato"]
    eta = (oggi - date.fromisoformat(ultimo_prezzo)).days
    if eta > config.GIORNI_PREZZO_VECCHIO:
        motivi.append(f"ultimo prezzo vecchio di {eta} giorni ({ultimo_prezzo})")
    if n_prezzi < 250:
        motivi.append(f"storico corto: {n_prezzi} sedute")
    unita, cent = valuta_unita(valuta_fonte)
    if valuta_attesa and unita != valuta_attesa:
        motivi.append(f"valuta di quotazione {valuta_fonte or 'n.d.'} diversa da quella attesa {valuta_attesa}")
    elif cent != centesimi_attesi:
        motivi.append(f"unita' di quotazione inattesa ({valuta_fonte}): controllare centesimi/unita'")
    if not nome_somiglia(nome_atteso, nome_fonte):
        motivi.append(f"nome della fonte '{nome_fonte or 'n.d.'}' diverso da quello atteso '{nome_atteso}'")
    if tipo_atteso and tipo_fonte and tipo_fonte != tipo_atteso:
        motivi.append(f"tipo di strumento {tipo_fonte} diverso da {tipo_atteso}")
    if salti:
        motivi.append("storico da controllare: " + "; ".join(salti[:3]))
    if richiede_bilanci:
        if n_esercizi == 0:
            motivi.append("nessun bilancio annuale")
        else:
            eta_b = (oggi - date.fromisoformat(ultimo_esercizio)).days
            if eta_b > config.GIORNI_BILANCIO_VECCHIO:
                motivi.append(f"ultimo esercizio vecchio di {eta_b} giorni ({ultimo_esercizio})")
            if n_esercizi < 3:
                motivi.append(f"solo {n_esercizi} esercizi annuali")
        if valuta_bil_fonte is None:
            motivi.append("valuta di bilancio non dichiarata dalla fonte")
        elif valuta_bil_attesa and valuta_bil_fonte != valuta_bil_attesa:
            motivi.append(f"valuta di bilancio {valuta_bil_fonte} diversa da quella attesa {valuta_bil_attesa}")
    return ("DA VERIFICARE" if motivi else "OK"), motivi
