"""Cambi di riferimento della Banca Centrale Europea: unita di valuta per 1 euro."""
from __future__ import annotations
import csv
import io
import zipfile

import requests

URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"


def leggi_zip(contenuto: bytes, valute: set[str], dal: str = "2015-01-01") -> list[tuple]:
    """-> righe (data, valuta, tasso). I valori 'N/A' o vuoti sono saltati."""
    with zipfile.ZipFile(io.BytesIO(contenuto)) as z:
        testo = z.read(z.namelist()[0]).decode("utf-8")
    righe = []
    for r in csv.DictReader(io.StringIO(testo)):
        d = (r.get("Date") or "").strip()
        if not d or d < dal:
            continue
        for val in valute:
            x = (r.get(val) or "").strip()
            if x and x != "N/A":
                try:
                    righe.append((d, val, float(x)))
                except ValueError:
                    pass
    return righe


def valute_disponibili(contenuto: bytes) -> set[str]:
    with zipfile.ZipFile(io.BytesIO(contenuto)) as z:
        prima = z.read(z.namelist()[0]).decode("utf-8").splitlines()[0]
    return {c.strip() for c in prima.split(",") if c.strip() and c.strip() != "Date"}


def scarica() -> bytes:
    r = requests.get(URL, timeout=60)
    r.raise_for_status()
    return r.content
