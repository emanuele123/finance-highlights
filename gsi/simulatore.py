"""Simulatore di accumulo: stessa logica, anno per anno, delle formule del foglio SIMULATORE.
Ipotesi di rendimento scelte dall'utente: non sono previsioni."""
from __future__ import annotations

PREDEFINITI = {"importo": 10000.0, "versamento": 200.0, "anni": 15, "rendimenti": [0.03, 0.06, 0.09],
               "dividendi": 0.02, "reinvesti": "sì", "commissione": 2.0, "costi_annui": 0.002,
               "imposte": 0.26, "inflazione": 0.02}
MAX_ANNI = 40


def simula(importo, versamento, anni, rendimento, dividendi, reinvesti, commissione, costi_annui, imposte, inflazione) -> dict:
    """Passo annuale. I versamenti dell'anno (12 rate, ciascuna al netto della commissione) maturano
    in media mezzo anno. Il rendimento ipotizzato e' totale: quota di prezzo = rendimento - dividendi.
    Le imposte colpiscono i dividendi quando sono pagati e la plusvalenza alla fine."""
    anni = int(max(0, min(MAX_ANNI, anni)))
    capitale = max(0.0, importo - (commissione if importo > 0 else 0.0))
    versato = importo
    costo_fiscale = capitale                 # quanto e' stato investito (base per la plusvalenza)
    incassati = 0.0                          # dividendi netti non reinvestiti
    g = rendimento - dividendi - costi_annui
    righe = []
    for a in range(1, anni + 1):
        rate = 12 * max(0.0, versamento - commissione) if versamento > 0 else 0.0
        div_netti = dividendi * (capitale + rate / 2) * (1 - imposte)
        capitale = capitale * (1 + g) + rate * (1 + g / 2)
        versato += 12 * versamento
        costo_fiscale += rate
        if reinvesti:
            capitale += div_netti
            costo_fiscale += div_netti
        else:
            incassati += div_netti
        righe.append({"anno": a, "capitale": capitale, "versato": versato, "incassati": incassati})
    plus = capitale - costo_fiscale
    tasse = imposte * max(0.0, plus)
    netto = capitale - tasse + incassati
    return {"righe": righe, "capitale": capitale, "versato": versato, "imposte_finali": tasse, "netto": netto,
            "reale": netto / (1 + inflazione) ** anni, "incassati": incassati}
