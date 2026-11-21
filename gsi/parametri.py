"""Tutti i numeri delle due strategie (valori iniziali del foglio PARAMETRI)."""
from __future__ import annotations
import copy

MODELLI = ["STD", "CIC", "UTL", "BAN", "ASS", "REIT"]
FINANZIARI = ("BAN", "ASS")
PILASTRI_A = ["Q", "F", "G", "V"]
NOMI_PILASTRI_A = {"Q": "Qualità del business", "F": "Solidità finanziaria",
                   "G": "Crescita e allocazione del capitale", "V": "Valutazione al prezzo corrente"}
METRICHE_A = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "F1", "F2", "F3", "F4", "F5",
              "G1", "G2", "G3", "G4", "V1", "V2", "V3", "V4"]
NOMI_METRICHE = {
    "Q1": "Rendimento sul capitale, medio", "Q2": "Rendimento sul capitale, anno peggiore",
    "Q3": "Margine operativo / efficienza", "Q4": "Stabilità dei margini", "Q5": "Stabilità dei ricavi",
    "Q6": "Margine lordo", "F1": "Leva finanziaria", "F2": "Copertura degli interessi",
    "F3": "Conversione in cassa", "F4": "Payout", "F5": "Capitale regolamentare", "G1": "Crescita",
    "G2": "Crescita dell'utile per azione", "G3": "Variazione del numero di azioni",
    "G4": "Rendimento incrementale sul capitale", "V1": "Margine di sicurezza",
    "V2": "Rendimento per l'azionista", "V3": "Multiplo", "V4": "P/E prospettico"}

# modello: pesi dei pilastri (Q, F, G, V) e tetto alla crescita di fase 1
_PESI = {"STD": (30, 15, 15, 40, 0.10), "CIC": (25, 25, 10, 40, 0.04), "UTL": (25, 25, 10, 40, 0.04),
         "BAN": (30, 25, 10, 35, 0.06), "ASS": (30, 25, 10, 35, 0.06), "REIT": (25, 25, 10, 40, 0.04)}

# metrica peso/soglia a 0 punti/soglia a 100 punti
_SOGLIE = {
    "STD": "Q1 30/0.06/0.2; Q2 20/0/0.12; Q3 15/0.05/0.25; Q4 15/0.06/0.01; Q5 10/0.5/1; Q6 10/0.2/0.6; F1 40/4/0.5; F2 20/2/12; F3 25/0.4/1; F4 15/1/0.5; G1 30/0/0.1; G2 30/0/0.12; G3 20/0.03/-0.02; G4 20/0.05/0.2; V1 60/-0.3/0.3; V2 20/0.02/0.08; V3 10/22/8; V4 10/32/12",
    "CIC": "Q1 35/0.05/0.15; Q2 25/-0.03/0.08; Q3 15/0.04/0.2; Q4 10/0.1/0.03; Q5 15/0.4/0.9; F1 45/3/0; F2 20/2/12; F3 20/0.4/1; F4 15/1/0.5; G1 35/-0.02/0.06; G2 25/0/0.1; G3 20/0.03/-0.02; G4 20/0.03/0.15; V1 60/-0.3/0.3; V2 20/0.03/0.1; V3 10/12/4; V4 10/20/8",
    "UTL": "Q1 35/0.03/0.08; Q2 25/0.02/0.06; Q3 15/0.08/0.25; Q4 10/0.05/0.01; Q5 15/0.5/1; F1 50/6/2.5; F2 30/1.5/5; F4 20/1/0.6; G1 35/-0.02/0.05; G2 40/0/0.07; G3 25/0.03/0; V1 60/-0.3/0.3; V2 20/0.03/0.07; V3 10/13/6; V4 10/22/10",
    "BAN": "Q1 35/0.05/0.15; Q2 25/0/0.1; Q3 15/0.7/0.45; Q4 15/0.06/0.01; Q5 10/0.5/1; F1 40/0.04/0.1; F4 25/0.9/0.4; F5 35/0.11/0.16; G1 45/0.02/0.12; G2 35/0/0.1; G3 20/0.03/-0.02; V1 60/-0.3/0.3; V2 20/0.05/0.12; V3 10/2.2/0.8; V4 10/16/7",
    "ASS": "Q1 35/0.05/0.15; Q2 25/0/0.09; Q3 15/1.02/0.9; Q4 15/0.06/0.01; Q5 10/0.5/1; F1 30/0.04/0.15; F4 30/0.9/0.4; F5 40/1.5/2.2; G1 45/0.02/0.1; G2 35/0/0.1; G3 20/0.03/-0.02; V1 60/-0.3/0.3; V2 20/0.05/0.11; V3 10/2.5/0.9; V4 10/18/8",
    "REIT": "Q1 35/0.02/0.06; Q2 25/0.01/0.05; Q3 15/0.2/0.5; Q4 10/0.08/0.02; Q5 15/0.5/1; F1 50/9/4.5; F2 30/1.5/5; F4 20/1/0.65; G1 45/0/0.07; G2 25/0/0.07; G3 30/0.05/0; V1 60/-0.3/0.3; V2 25/0.03/0.07; V3 15/26/14",
}

# valuta di bilancio: rendimento richiesto, crescita terminale (ipotesi dichiarate, non dati di mercato)
_TASSI = {"USD": (0.09, 0.025), "EUR": (0.085, 0.02), "GBP": (0.09, 0.02), "CHF": (0.07, 0.01),
          "JPY": (0.07, 0.01), "SEK": (0.085, 0.02), "DKK": (0.085, 0.02), "NOK": (0.09, 0.02),
          "CAD": (0.085, 0.02), "AUD": (0.09, 0.025), "SGD": (0.08, 0.02), "HKD": (0.09, 0.025),
          "KRW": (0.095, 0.02), "TWD": (0.09, 0.02), "CNY": (0.10, 0.03), "INR": (0.12, 0.05),
          "BRL": (0.14, 0.045), "ALTRO": (0.10, 0.025)}

# scenario: quota della crescita storica riconosciuta, fattore sugli utili, variazione del tasso
_SCENARI = {"Prudente": (0.25, 0.85, 0.01), "Base": (0.60, 1.0, 0.0), "Ottimistico": (0.90, 1.1, -0.005)}

PILASTRI_B = ["Trend", "Momentum", "Forza relativa", "Oscillatori", "Volumi", "Assetto e rischio", "Catalizzatori"]


def _leggi_soglie() -> dict:
    out = {}
    for mod, testo in _SOGLIE.items():
        out[mod] = {m: (0.0, 0.0, 0.0) for m in METRICHE_A}
        for pezzo in testo.split(";"):
            nome, numeri = pezzo.split()
            out[mod][nome] = tuple(float(x) for x in numeri.split("/"))
    return out


PREDEFINITI = {
    "pesi_pilastri": {m: dict(zip(PILASTRI_A, v[:4])) for m, v in _PESI.items()},
    "tetto_crescita": {m: v[4] for m, v in _PESI.items()},
    "metriche": _leggi_soglie(),                    # modello -> metrica -> (peso, s0, s100)
    "tassi": _TASSI, "scenari": _SCENARI,
    "extra_emergenti": 0.02, "distanza_terminale": 0.03, "crescita_minima": -0.02,
    "quota_flusso": {"STD": 1.0, "CIC": 1.0, "UTL": 0.75, "REIT": 0.85, "BAN": 1.0, "ASS": 1.0},
    "quota_cassa_netta": 0.5, "payout_predefinito": 0.5, "anni_fase": 5,
    "copertura_minima": 0.60, "tetto_valutazione": 20.0, "correzione_massima": 10.0,
    "classe_a": 70.0, "classe_b": 55.0, "margine_a": 0.25, "margine_b": 0.40,
    "giorni_prezzo": 5, "giorni_esercizio": 500,
    # segnali di rischio
    "rischio_copertura": 3.0, "rischio_diluizione": 0.02, "rischio_avviamento": 0.6,
    "rischio_calo_margine": 0.02, "rischio_payout": 1.0,
    # strategia B
    "pesi_b": dict(zip(PILASTRI_B, (25, 25, 15, 10, 10, 10, 5))), "copertura_b": 0.70,
    "trend_punti": (30, 25, 20, 15, 10), "trend_rialzista": 70, "trend_ribassista": 40,
    "mom_pesi": (0.4, 0.3, 0.3), "mom_s0": -0.15, "mom_s100": 0.35,
    "fr_3m": 0.10, "fr_6m": 0.15, "fr_settore": 0.10, "fr_min_settore": 4,
    "osc_peso_rsi": 0.6, "rsi_fasce": ((30, 10), (45, 35), (55, 65), (70, 100), (80, 60), (1e9, 25)),
    "macd_sopra": 60, "macd_isto": 40,
    "vol_peso_ud": 0.7, "vol_ud": (0.7, 1.5), "vol_rel": (0.7, 1.3),
    "ass_pesi": (0.5, 0.25, 0.25), "ass_dist": (0.30, 0.05), "ass_atr": (0.06, 0.02), "ass_rr": (1.0, 3.0),
    "cat_reazione": 0.05, "cat_giorni": 60, "cat_avviso": 7,
    "setup_rottura_atr": 1.0, "setup_ingresso_atr": 0.1, "setup_fascia_atr": 0.5,
    "setup_rsi": (40, 60), "setup_stop_atr": 2.0, "setup_obiettivo_r": 2.0, "setup_rr_min": 1.5,
    "soglia_segnale": 65, "capitale": 50000.0, "rischio_operazione": 0.01, "peso_massimo": 0.10,
}


def predefiniti() -> dict:
    return copy.deepcopy(PREDEFINITI)
