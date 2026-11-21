"""Cruscotto Excel: i dati importati stanno nel foglio DATI, tutto il resto e' formula.

Convenzioni: carattere Arial; blu = dato importato o inserito, nero = formula, verde = collegamento
ad altro foglio, fondo giallo = cella modificabile. I collegamenti tra fogli passano dal ticker
(INDEX/MATCH), cosi' reggono filtri e ordinamenti. Nessuna funzione disponibile solo in Excel 365.
"""
from __future__ import annotations
import json
import re
import statistics
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .calcola import N_RESISTENZE, ORIZZONTI
from .parametri import (FINANZIARI, METRICHE_A, MODELLI, NOMI_METRICHE, NOMI_PILASTRI_A, PILASTRI_B)
from .universo import ESCLUSI, ETF, INDICI, PER_TICKER, SOSTITUZIONI, UNIVERSO

ND = "n.d."
BLU, NERO, VERDE, BIANCO = "0000FF", "000000", "008000", "FFFFFF"
GIALLO = PatternFill("solid", fgColor="FFFF00")
TESTATA = PatternFill("solid", fgColor="1F3864")
FASCIA = PatternFill("solid", fgColor="D9E1F2")
SOTTILE = Side(style="thin", color="BFBFBF")
R0 = 3                                  # prima riga dei dati nei fogli "una riga per titolo"
F_PCT, F_NUM, F_PUNTI, F_DATA, F_INT, F_X = "0.0%", "#,##0.00", "0.0", "dd/mm/yyyy", "#,##0", '0.0"x"'


def car(colore=NERO, grassetto=False, dim=10, corsivo=False):
    return Font(name="Arial", size=dim, color=colore, bold=grassetto, italic=corsivo)


class Libro:
    """Cartella di lavoro + registro dei parametri (nome -> indirizzo) + mappa delle celle gialle."""

    def __init__(self, n_titoli: int):
        self.wb = Workbook()
        self.wb.remove(self.wb.active)
        self.n = n_titoli
        self.r1 = R0 + n_titoli - 1
        self.prm: dict[str, str] = {}          # nome parametro -> indirizzo assoluto
        self.mappa: list[tuple] = []           # (chiave, foglio, cella, valore predefinito, ticker di riga)
        self.tab: dict[str, "Tab"] = {}
        from .parametri import predefiniti
        self._pred = predefiniti()

    def foglio(self, nome: str):
        return self.wb[nome] if nome in self.wb.sheetnames else self.wb.create_sheet(nome)

    def gialla(self, ws, cella: str, valore, chiave: str, fmt=None, ticker=None, pred=None):
        c = ws[cella]
        c.value = valore
        c.font, c.fill = car(BLU), GIALLO
        c.border = Border(left=SOTTILE, right=SOTTILE, top=SOTTILE, bottom=SOTTILE)
        if fmt:
            c.number_format = fmt
        # nella mappa va il valore predefinito DEL PROGRAMMA (non quello corrente): cosi' una modifica
        # dell'utente resta riconoscibile, e quindi conservata, a ogni rigenerazione successiva
        if chiave.startswith("P|"):
            pred = self._pred
            for k in json.loads(chiave[2:]):
                pred = pred[k]
        self.mappa.append((chiave, ws.title, cella, pred, ticker))


def titolo_foglio(ws, testo: str, sotto: str = ""):
    ws["A1"] = testo
    ws["A1"].font = car(NERO, True, 12)
    if sotto:
        ws["D1"] = sotto
        ws["D1"].font = car("595959", corsivo=True, dim=9)


def testata(ws, riga: int, col: int, testo: str, largh: float | None = None):
    c = ws.cell(riga, col, testo)
    c.font, c.fill = car(BIANCO, True, 9), TESTATA
    c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    if largh:
        ws.column_dimensions[get_column_letter(col)].width = largh


class Tab:
    """Foglio con una riga per titolo: ticker in colonna A, intestazioni in riga 2, dati dalla riga 3.

    Le formule sono modelli con segnaposto risolti riga per riga:
      {chiave}       cella della stessa riga in questo foglio
      {D:chiave}     valore dello stesso ticker in un altro foglio (D=DATI, V=VALUTAZIONE, B=BUFFETT,
                     T=TRADING, G=GIUDIZI, S=SCREENER) tramite INDEX/MATCH sul ticker
      {P:nome}       indirizzo assoluto di un parametro
      {PM:nome}      parametro per modello: INDEX(riga dei modelli, indice del modello)
      {R:chiave}     intervallo assoluto dell'intera colonna in questo foglio
    """
    SIGLE = {"D": "DATI", "V": "VALUTAZIONE", "B": "BUFFETT", "T": "TRADING", "G": "GIUDIZI", "S": "SCREENER"}

    def __init__(self, libro: Libro, nome: str, titolo: str, sotto: str = ""):
        self.libro, self.nome = libro, nome
        self.ws = libro.foglio(nome)
        self.cols: dict[str, str] = {}
        self.defs: list[tuple] = []
        libro.tab[nome] = self
        titolo_foglio(self.ws, titolo, sotto)

    def col(self, chiave: str, intest: str, modello=None, fmt=None, tipo="formula", largh=11):
        """modello: stringa-modello di formula, oppure funzione (ticker) -> valore per i dati."""
        self.cols[chiave] = get_column_letter(len(self.defs) + 1)
        self.defs.append((chiave, intest, modello, fmt, tipo, largh))

    def rng(self, chiave: str) -> str:
        L = self.cols[chiave]
        return f"{self.nome}!${L}${R0}:${L}${self.libro.r1}"

    def risolvi(self, modello: str, r: int) -> str:
        lib = self.libro

        def sost(m):
            sig, k = m.group(1), m.group(2)
            if sig is None:
                return f"{self.cols[k]}{r}"
            if sig == "P":
                return lib.prm[k]
            if sig == "PM":
                return f"INDEX({lib.prm['riga.' + k]},{self.cols['idx']}{r})"
            if sig == "R":
                return self.rng(k)
            altro = lib.tab[self.SIGLE[sig]]
            return f"INDEX({altro.rng(k)},MATCH($A{r},{altro.rng('ticker')},0))"
        return re.sub(r"\{(?:([A-Z]+):)?([^{}]+)\}", sost, modello)

    def scrivi(self, tickers: list[str], valori_gialli: dict | None = None):
        ws = self.ws
        ws.row_dimensions[2].height = 42
        for j, (chiave, intest, modello, fmt, tipo, largh) in enumerate(self.defs, 1):
            testata(ws, 2, j, intest, largh)
            for i, tk in enumerate(tickers):
                r = R0 + i
                c = ws.cell(r, j)
                if tipo == "giallo":
                    lib_val = modello(tk) if callable(modello) else modello
                    self.libro.gialla(ws, c.coordinate, lib_val, f"{self.nome}|{chiave}|{tk}", fmt, tk)
                    continue
                if callable(modello):
                    v = modello(tk)
                    c.value = ND if v is None else v
                else:
                    c.value = self.risolvi(modello, r)
                c.font = car({"dato": BLU, "link": VERDE}.get(tipo, NERO))
                if fmt:
                    c.number_format = fmt
                if c.value == ND or fmt:
                    c.alignment = Alignment(horizontal="right")
        ws.freeze_panes = ws.cell(R0, 3)
        ws.auto_filter.ref = f"A2:{get_column_letter(len(self.defs))}{self.libro.r1}"


def PUNTI(x: str, s0: str, s100: str) -> str:
    """Frammento di formula: punteggio lineare tra la soglia a 0 e quella a 100."""
    return f"100*MAX(0,MIN(1,(({x})-({s0}))/(({s100})-({s0}))))"


# ============================================================================ PARAMETRI
def foglio_parametri(lib: Libro, P: dict, oggi: date):
    ws = lib.foglio("PARAMETRI")
    titolo_foglio(ws, "PARAMETRI", "Le celle gialle sono modificabili: cambiando un numero, punteggi e valori si ricalcolano. "
                                  "Le modifiche vengono conservate a ogni aggiornamento.")
    for col, w in zip("ABCDEFGHIJKLMNOPQRST", (3, 46, 13, 13, 13, 13, 13, 13) + (10,) * 12):
        ws.column_dimensions[col].width = w
    stato = {"r": 3}

    def sezione(testo):
        stato["r"] += 1
        c = ws.cell(stato["r"], 2, testo)
        c.font, c.fill = car(NERO, True, 11), FASCIA
        for j in range(3, 21):
            ws.cell(stato["r"], j).fill = FASCIA
        stato["r"] += 1

    def scalare(nome, etichetta, percorso, fmt=None, nota=""):
        r = stato["r"]
        ws.cell(r, 2, etichetta).font = car()
        v = P
        for k in percorso:
            v = v[k]
        lib.gialla(ws, f"C{r}", v, "P|" + json.dumps(percorso), fmt)
        lib.prm[nome] = f"PARAMETRI!$C${r}"
        if nota:
            ws.cell(r, 4, nota).font = car("595959", corsivo=True, dim=9)
        stato["r"] += 1

    # --- data di riferimento (dato, non parametro)
    ws["B3"] = "Data di riferimento dei dati (ultimo aggiornamento)"
    ws["B3"].font = car(NERO, True)
    ws["C3"] = oggi
    ws["C3"].font, ws["C3"].number_format = car(BLU), F_DATA
    lib.prm["data_rif"] = "PARAMETRI!$C$3"

    # --- pesi dei pilastri per modello
    sezione("Strategia A - pesi dei pilastri, tetto alla crescita e quota del flusso, per modello")
    r = stato["r"]
    testata(ws, r, 2, "Voce")
    for j, m in enumerate(MODELLI):
        testata(ws, r, 3 + j, m)
    lib.prm["modelli"] = f"PARAMETRI!$C${r}:$H${r}"
    righe = [(f"Peso pilastro {L}: {NOMI_PILASTRI_A[L]}", "pesi_pilastri." + L, lambda m, L=L: ["pesi_pilastri", m, L], F_INT)
             for L in "QFGV"]
    righe += [("Tetto alla crescita di fase 1", "tetto_crescita", lambda m: ["tetto_crescita", m], F_PCT),
              ("Quota del flusso normalizzato riconosciuta (UTL quota distribuibile, REIT da FFO ad AFFO)",
               "quota_flusso", lambda m: ["quota_flusso", m], "0.00")]
    for etichetta, nome, perc, fmt in righe:
        r += 1
        ws.cell(r, 2, etichetta).font = car()
        for j, m in enumerate(MODELLI):
            pp = perc(m)
            v = P
            for k in pp:
                v = v[k]
            lib.gialla(ws, f"{get_column_letter(3 + j)}{r}", v, "P|" + json.dumps(pp), fmt)
        lib.prm["riga." + nome] = f"PARAMETRI!$C${r}:$H${r}"
    stato["r"] = r + 1

    # --- metriche
    sezione("Strategia A - metriche: peso nel pilastro, soglia a 0 punti, soglia a 100 punti (peso 0 = non usata)")
    r = stato["r"]
    testata(ws, r, 2, "Metrica")
    for j, m in enumerate(MODELLI):
        for k, t in enumerate(("peso", "0 punti", "100 punti")):
            testata(ws, r, 3 + 3 * j + k, f"{m} {t}")
    for met in METRICHE_A:
        r += 1
        ws.cell(r, 2, f"{met} - {NOMI_METRICHE[met]}").font = car()
        for j, m in enumerate(MODELLI):
            for k in range(3):
                lib.gialla(ws, f"{get_column_letter(3 + 3 * j + k)}{r}", P["metriche"][m][met][k],
                           "P|" + json.dumps(["metriche", m, met, k]), "0.###")
        lib.prm["met." + met] = f"PARAMETRI!$C${r}:$T${r}"
    stato["r"] = r + 1

    # --- tassi per valuta
    sezione("Strategia A - rendimento richiesto e crescita terminale per valuta di bilancio (ipotesi dichiarate, non dati di mercato)")
    r = stato["r"]
    for j, t in enumerate(("Valuta", "Rendimento richiesto", "Crescita terminale")):
        testata(ws, r, 2 + j, t)
    primo = r + 1
    for val in P["tassi"]:
        r += 1
        ws.cell(r, 2, val).font = car()
        lib.gialla(ws, f"C{r}", P["tassi"][val][0], "P|" + json.dumps(["tassi", val, 0]), F_PCT)
        lib.gialla(ws, f"D{r}", P["tassi"][val][1], "P|" + json.dumps(["tassi", val, 1]), F_PCT)
    lib.prm["tassi_val"] = f"PARAMETRI!$B${primo}:$B${r}"
    lib.prm["tassi_r"] = f"PARAMETRI!$C${primo}:$C${r}"
    lib.prm["tassi_g"] = f"PARAMETRI!$D${primo}:$D${r}"
    stato["r"] = r + 1

    sezione("Strategia A - scenari del valore intrinseco")
    r = stato["r"]
    for j, t in enumerate(("Scenario", "Quota della crescita storica", "Fattore sugli utili", "Variazione del tasso")):
        testata(ws, r, 2 + j, t)
    for s in P["scenari"]:
        r += 1
        ws.cell(r, 2, s).font = car()
        for k, fmt in enumerate((F_PCT, "0.00", "0.0%")):
            cella = f"{get_column_letter(3 + k)}{r}"
            lib.gialla(ws, cella, P["scenari"][s][k], "P|" + json.dumps(["scenari", s, k]), fmt)
            lib.prm[f"scenari.{s}.{k}"] = f"PARAMETRI!${cella[0]}${r}"
    stato["r"] = r + 1

    sezione("Strategia A - regole generali")
    for nome, et, fmt in [
            ("extra_emergenti", "Maggiorazione del rendimento richiesto per l'area Emergenti", "0.0%"),
            ("distanza_terminale", "Distanza minima tra rendimento richiesto e crescita terminale", "0.0%"),
            ("crescita_minima", "Limite inferiore della crescita storica riconosciuta", "0.0%"),
            ("anni_fase", "Anni di ciascuna delle due fasi di crescita", "0"),
            ("quota_cassa_netta", "Quota della cassa netta per azione aggiunta al valore", "0%"),
            ("payout_predefinito", "Payout usato per banche e assicurazioni se manca il dato", "0%"),
            ("copertura_minima", "Copertura minima del peso perché un pilastro sia calcolato", "0%"),
            ("tetto_valutazione", "Valutazione usata: al massimo Qualità composita + questi punti", "0"),
            ("correzione_massima", "Correzione qualitativa manuale: limite in punti (±)", "0"),
            ("classe_a", "Classe A da Qualità composita >=", "0"),
            ("classe_b", "Classe B da Qualità composita >=", "0"),
            ("margine_a", "Margine di sicurezza richiesto per la classe A", "0%"),
            ("margine_b", "Margine di sicurezza richiesto per la classe B", "0%"),
            ("giorni_prezzo", "Prezzo più vecchio di (giorni): dati insufficienti", "0"),
            ("giorni_esercizio", "Ultimo esercizio più vecchio di (giorni): dati insufficienti", "0"),
            ("rischio_copertura", "Segnale di rischio: copertura degli interessi sotto", "0.0"),
            ("rischio_diluizione", "Segnale di rischio: crescita annua delle azioni oltre", "0.0%"),
            ("rischio_avviamento", "Segnale di rischio: avviamento e immateriali / patrimonio oltre", "0%"),
            ("rischio_calo_margine", "Segnale di rischio: margine dell'ultimo anno sotto la media di (punti)", "0.0%"),
            ("rischio_payout", "Segnale di rischio: payout oltre", "0%")]:
        scalare(nome, et, [nome], fmt)

    sezione("Strategia B - pesi dei pilastri del Trading Score")
    for n in PILASTRI_B:
        scalare("pesi_b." + n, n, ["pesi_b", n], "0")
    scalare("copertura_b", "Copertura minima del peso (servono comunque Trend e Momentum)", ["copertura_b"], "0%")
    sezione("Strategia B - Trend")
    for i, et in enumerate(("Punti se prezzo > media 200", "Punti se media 50 > media 200", "Punti se prezzo > media 50",
                            "Punti se la media 200 è più alta di 20 sedute fa", "Punti se prezzo > media 20")):
        scalare(f"trend_punti.{i}", et, ["trend_punti", i], "0")
    scalare("trend_rialzista", "Trend rialzista da", ["trend_rialzista"], "0")
    scalare("trend_ribassista", "Trend ribassista sotto", ["trend_ribassista"], "0")
    sezione("Strategia B - Momentum e forza relativa")
    for i, et in enumerate(("Peso del rendimento a 12 mesi escluso l'ultimo", "Peso del rendimento a 6 mesi",
                            "Peso del rendimento a 3 mesi")):
        scalare(f"mom_pesi.{i}", et, ["mom_pesi", i], "0.00")
    scalare("mom_s0", "Livello assoluto del momentum che vale 0", ["mom_s0"], "0%")
    scalare("mom_s100", "Livello assoluto del momentum che vale 100", ["mom_s100"], "0%")
    scalare("fr_3m", "Extra-rendimento sull'indice a 3 mesi: ± che vale 0 / 100", ["fr_3m"], "0%")
    scalare("fr_6m", "Extra-rendimento sull'indice a 6 mesi: ± che vale 0 / 100", ["fr_6m"], "0%")
    scalare("fr_settore", "Extra-rendimento sulla mediana del settore a 3 mesi: ±", ["fr_settore"], "0%")
    scalare("fr_min_settore", "Numero minimo di titoli nel settore per usare la mediana", ["fr_min_settore"], "0")
    sezione("Strategia B - Oscillatori e volumi")
    scalare("osc_peso_rsi", "Peso dell'RSI (il resto al MACD)", ["osc_peso_rsi"], "0%")
    limiti = ("sotto", "sotto", "sotto", "sotto", "sotto")
    for i in range(6):
        if i < 5:
            scalare(f"rsi_lim.{i}", f"RSI: fascia {i + 1}, limite superiore (escluso)", ["rsi_fasce", i, 0], "0")
        scalare(f"rsi_pun.{i}", f"RSI: punti della fascia {i + 1}" + (" (oltre l'ultimo limite)" if i == 5 else ""),
                ["rsi_fasce", i, 1], "0")
    del limiti
    scalare("macd_sopra", "MACD: punti se sopra il segnale", ["macd_sopra"], "0")
    scalare("macd_isto", "MACD: punti se l'istogramma è più alto di 5 sedute fa", ["macd_isto"], "0")
    scalare("vol_peso_ud", "Peso del rapporto volumi rialzo/ribasso (il resto al volume relativo)", ["vol_peso_ud"], "0%")
    scalare("vol_ud.0", "Volumi rialzo/ribasso a 20 sedute: valore che vale 0", ["vol_ud", 0], "0.00")
    scalare("vol_ud.1", "Volumi rialzo/ribasso a 20 sedute: valore che vale 100", ["vol_ud", 1], "0.00")
    scalare("vol_rel.0", "Volume medio 20/60 sedute: valore che vale 0", ["vol_rel", 0], "0.00")
    scalare("vol_rel.1", "Volume medio 20/60 sedute: valore che vale 100", ["vol_rel", 1], "0.00")
    sezione("Strategia B - Assetto e rischio, catalizzatori")
    for i, et in enumerate(("Peso della distanza dal massimo a 52 settimane", "Peso dell'ATR in % del prezzo",
                            "Peso del rendimento/rischio del setup")):
        scalare(f"ass_pesi.{i}", et, ["ass_pesi", i], "0%")
    for nome, et, fmt in (("ass_dist", "Distanza dal massimo a 52 settimane", "0%"), ("ass_atr", "ATR in % del prezzo", "0%"),
                          ("ass_rr", "Rendimento/rischio del setup", "0.0")):
        scalare(nome + ".0", f"{et}: valore che vale 0", [nome, 0], fmt)
        scalare(nome + ".1", f"{et}: valore che vale 100", [nome, 1], fmt)
    scalare("cat_reazione", "Reazione anomala alla trimestrale: ± che vale 0 / 100", ["cat_reazione"], "0%")
    scalare("cat_giorni", "Validità della reazione alla trimestrale (giorni)", ["cat_giorni"], "0")
    scalare("cat_avviso", "Avviso di rischio se la trimestrale è entro (giorni)", ["cat_avviso"], "0")
    sezione("Strategia B - setup operativo e dimensione della posizione")
    scalare("setup_rottura_atr", "Rottura: distanza massima dal massimo a 20 sedute (in ATR)", ["setup_rottura_atr"], "0.0")
    scalare("setup_ingresso_atr", "Rottura: ingresso sopra il massimo a 20 sedute (in ATR)", ["setup_ingresso_atr"], "0.0")
    scalare("setup_fascia_atr", "Ritracciamento: tolleranza attorno alle medie (in ATR)", ["setup_fascia_atr"], "0.0")
    scalare("setup_rsi.0", "Ritracciamento: RSI minimo", ["setup_rsi", 0], "0")
    scalare("setup_rsi.1", "Ritracciamento: RSI massimo", ["setup_rsi", 1], "0")
    scalare("setup_stop_atr", "Stop sotto l'ingresso (in ATR)", ["setup_stop_atr"], "0.0")
    scalare("setup_obiettivo_r", "Obiettivo sopra l'ingresso (in multipli del rischio)", ["setup_obiettivo_r"], "0.0")
    scalare("setup_rr_min", "Rendimento/rischio minimo perché il setup sia valido", ["setup_rr_min"], "0.0")
    scalare("soglia_segnale", "Trading Score minimo per 'Setup attivo' e 'In osservazione'", ["soglia_segnale"], "0")
    scalare("capitale", "Capitale di esempio (euro)", ["capitale"], F_INT)
    scalare("rischio_operazione", "Rischio massimo per operazione (quota del capitale)", ["rischio_operazione"], "0.0%")
    scalare("peso_massimo", "Peso massimo di una posizione (quota del capitale)", ["peso_massimo"], "0%")
    sezione("Allerte, fasce di capitalizzazione e livello di rischio (SCREENER e CRUSCOTTO)")
    scalare("allerta_volatilita", "Allerta: volatilità annua oltre", ["allerta_volatilita"], "0%")
    scalare("allerta_ribasso", "Allerta: ribasso a un anno oltre", ["allerta_ribasso"], "0%")
    scalare("allerta_scambi", "Allerta: scambi medi giornalieri sotto (euro)", ["allerta_scambi"], F_INT)
    for i, et in enumerate(("Mega", "Grande", "Media")):
        scalare(f"fasce_cap.{i}", f"Capitalizzazione '{et}' da (euro); sotto l'ultima soglia: 'Piccola'", ["fasce_cap", i], F_INT)
    scalare("rischio_alto_segnali", "Livello di rischio Alto da questo numero di segnali di rischio", ["rischio_alto_segnali"], "0")
    scalare("rischio_medio_volatilita", "Livello di rischio Medio da volatilità annua oltre", ["rischio_medio_volatilita"], "0%")
    sezione("Promemoria generico dei rischi tipici del settore (testo modificabile, mostrato nella SCHEDA)")
    r = stato["r"]
    primo = r
    for sett, testo in P["rischi_settore"].items():
        ws.cell(r, 2, sett).font = car()
        lib.gialla(ws, f"C{r}", testo, "P|" + json.dumps(["rischi_settore", sett]))
        r += 1
    lib.prm["settori_nome"] = f"PARAMETRI!$B${primo}:$B${r - 1}"
    lib.prm["settori_testo"] = f"PARAMETRI!$C${primo}:$C${r - 1}"
    ws.freeze_panes = "C3"


# ============================================================================ DATI
def campi_dati() -> list[tuple]:
    """(chiave, intestazione, formato). L'ordine e' quello delle colonne del foglio DATI."""
    c = [("ticker", "Ticker", None), ("nome", "Società", None), ("area", "Area", None), ("settore", "Settore", None),
         ("modello", "Modello", None), ("valuta", "Valuta di quotazione", None), ("valuta_bil", "Valuta di bilancio", None),
         ("indice", "Indice di riferimento", None), ("paese", "Paese del listino", None), ("adr", "ADR / note sul titolo", None),
         ("stato_dati", "Esito dei controlli", None), ("motivi_dati", "Motivo", None), ("note_calcolo", "Note di calcolo", None),
         ("data_prezzo", "Data ultimo prezzo", F_DATA), ("prezzo", "Prezzo", F_NUM), ("azioni", "Azioni (capitalizzazione / prezzo)", F_INT),
         ("cambio_eur", "Cambio: unità di valuta per 1 euro", "0.0000"), ("controvalore_eur", "Scambi medi giornalieri a 20 sedute (euro)", F_INT),
         ("volatilita", "Volatilità annua (252 sedute)", F_PCT), ("beta_fonte", "Beta (fonte)", "0.00"),
         ("vol_3a_eur", "Volatilità annua in euro (rendimenti settimanali, 3 anni)", F_PCT),
         ("beta_mercato", "Beta sul mercato mondiale (settimanale, 3 anni, euro)", "0.00"),
         ("mm20", "Media mobile 20", F_NUM), ("mm50", "Media mobile 50", F_NUM), ("mm200", "Media mobile 200", F_NUM),
         ("mm200_20fa", "Media mobile 200 di 20 sedute fa", F_NUM), ("rsi", "RSI 14", "0.0"), ("macd", "MACD 12/26", "0.000"),
         ("macd_segnale", "MACD segnale 9", "0.000"), ("macd_isto", "MACD istogramma", "0.000"),
         ("macd_isto_5fa", "MACD istogramma 5 sedute fa", "0.000"), ("atr", "ATR 14", F_NUM),
         ("max20", "Massimo a 20 sedute", F_NUM), ("max52", "Massimo a 52 settimane", F_NUM)]
    c += [(f"res{i + 1}", f"Resistenza {i + 1} (massimo locale sopra il prezzo)", F_NUM) for i in range(N_RESISTENZE)]
    c += [("r1m", "Total return 1 mese", F_PCT), ("r3m", "Total return 3 mesi", F_PCT), ("r6m", "Total return 6 mesi", F_PCT),
          ("r12m_1", "Total return 12 mesi escluso l'ultimo", F_PCT), ("r12m", "Total return 12 mesi", F_PCT),
          ("idx_r3m", "Indice di riferimento 3 mesi", F_PCT), ("idx_r6m", "Indice di riferimento 6 mesi", F_PCT),
          ("med_settore_3m", "Mediana del settore a 3 mesi", F_PCT), ("n_settore", "Titoli del settore con il dato", "0"),
          ("vol_su_giu", "Volumi sedute al rialzo / al ribasso (20)", "0.00"), ("vol_20_60", "Volume medio 20 / 60 sedute", "0.00"),
          ("rev_su30", "Revisioni utili al rialzo a 30 giorni", "0"), ("rev_giu30", "Revisioni utili al ribasso a 30 giorni", "0"),
          ("reazione_utili", "Reazione anomala all'ultima trimestrale", F_PCT), ("data_utili", "Data ultima trimestrale", F_DATA),
          ("prossimi_utili", "Data prossima trimestrale", F_DATA),
          ("ultimo_esercizio", "Chiusura ultimo esercizio", F_DATA), ("n_anni", "Esercizi disponibili", "0")]
    c += [(m, f"{m} {NOMI_METRICHE[m]} (dato)", "0.000") for m in METRICHE_A if m[0] != "V" and m != "F5"]
    c += [("cagr_ricavi", "CAGR dei ricavi", F_PCT), ("roe_norm", "ROE normalizzato (finanziari)", F_PCT),
          ("flusso_ps", "Flusso normalizzato per azione (valuta di quotazione)", F_NUM),
          ("cassa_netta_ps", "Cassa netta per azione", F_NUM), ("tbv_ps", "Patrimonio tangibile per azione", F_NUM),
          ("debito_netto_q", "Debito netto (valuta di quotazione)", F_INT), ("ebitda_q", "EBITDA ordinario (valuta di quotazione)", F_INT),
          ("eps_atteso", "Utile per azione atteso dal consenso", F_NUM), ("margine_ultimo", "Margine operativo ultimo esercizio", F_PCT),
          ("margine_medio_prec", "Margine operativo medio precedente", F_PCT), ("var_ricavi_ultimo", "Variazione ricavi ultimo esercizio", F_PCT),
          ("fcf_ultimo", "Free cash flow ultimo esercizio (valuta di bilancio)", F_INT),
          ("avviamento_su_patr", "Avviamento e immateriali / patrimonio", F_PCT)]
    for pref, nome in (("pp", "Prezzo"), ("pt", "Total return"), ("pe", "Total return in euro")):
        c += [(f"{pref}_{o}", f"{nome} {o}", F_PCT) for o, _ in ORIZZONTI]
    return c


def valore_dato(i: dict, chiave: str, mediane: dict, titoli: dict):
    if chiave == "paese":
        return titoli[i["ticker"]].paese_listino
    if chiave == "adr":
        return titoli[i["ticker"]].adr or "-"
    if chiave == "note_calcolo":
        return "; ".join(i.get("note") or []) or "-"
    if chiave == "motivi_dati":
        return i.get("motivi_dati") or "-"
    if chiave.startswith("res") and chiave[3:].isdigit():
        lv = i.get("resistenze") or []
        k = int(chiave[3:]) - 1
        return lv[k] if k < len(lv) else None
    if chiave == "med_settore_3m":
        return mediane.get(i["settore"], (None, 0))[0]
    if chiave == "n_settore":
        return mediane.get(i["settore"], (None, 0))[1]
    v = i.get(chiave)
    if chiave in ("data_prezzo", "data_utili", "prossimi_utili", "ultimo_esercizio") and v:
        return date.fromisoformat(v)
    return v


def foglio_dati(lib: Libro, ingressi: dict, titoli: dict):
    per_settore: dict[str, list] = {}
    for i in ingressi.values():
        if i.get("r3m") is not None:
            per_settore.setdefault(i["settore"], []).append(i["r3m"])
    mediane = {s: (statistics.median(v), len(v)) for s, v in per_settore.items()}
    t = Tab(lib, "DATI", "DATI", "Dati importati dalle fonti o derivati dallo storico: non modificare a mano. "
                                 "'n.d.' = dato mancante, che non vale mai punti.")
    for chiave, intest, fmt in campi_dati():
        t.col(chiave, intest, (lambda tk, k=chiave: valore_dato(ingressi[tk], k, mediane, titoli)), fmt, "dato",
              28 if chiave in ("nome", "motivi_dati", "note_calcolo", "adr") else 12)
    t.scrivi(list(ingressi))
    return t


def foglio_giudizi(lib: Libro, ingressi: dict, giudizi: dict):
    t = Tab(lib, "GIUDIZI", "GIUDIZI", "Dati manuali (celle gialle). Per banche e assicurazioni non esiste una fonte gratuita via API "
                                       "per cost/income, combined ratio, CET1 e Solvency II: vanno copiati dai bilanci.")
    g = lambda tk, k: (giudizi.get(tk) or {}).get(k)  # noqa: E731
    t.col("ticker", "Ticker", lambda tk: tk, None, "dato", 12)
    t.col("nome", "Società", "={D:nome}", None, "link", 30)
    t.col("modello", "Modello", "={D:modello}", None, "link", 9)
    t.col("Q3", "Q3 manuale: cost/income (banche) o combined ratio (assicurazioni), es. 0,55", lambda tk: g(tk, "Q3"), "0.000", "giallo", 20)
    t.col("F5", "F5 manuale: CET1 ratio (banche, es. 0,15) o Solvency II ratio (assicurazioni, es. 2,1)", lambda tk: g(tk, "F5"), "0.000", "giallo", 20)
    t.col("correzione", "Correzione qualitativa in punti (limitata a ±10)", lambda tk: g(tk, "correzione"), "0.0", "giallo", 14)
    t.col("motivazione", "Motivazione della correzione (obbligatoria se diversa da zero)", lambda tk: g(tk, "motivazione"), None, "giallo", 45)
    t.col("tesi", "Tesi di investimento (appunti personali)", lambda tk: g(tk, "tesi"), None, "giallo", 60)
    t.col("avviso", "Controllo", '=IF(AND(ISNUMBER({correzione}),{correzione}<>0,{motivazione}=""),"Manca la motivazione",'
                                 'IF(AND(OR({modello}="BAN",{modello}="ASS"),NOT(ISNUMBER({Q3})),NOT(ISNUMBER({F5}))),'
                                 '"Dati manuali da inserire","-"))', None, "formula", 24)
    t.scrivi(list(ingressi))
    t.ws["J1"] = "Solo per i modelli BAN e ASS i campi Q3 e F5 sono usati nei punteggi."
    t.ws["J1"].font = car("595959", corsivo=True, dim=9)
    return t


def foglio_universo(lib: Libro, universo: list, demo: bool = False):
    UNIVERSO = universo
    ws = lib.foglio("UNIVERSO")
    titolo_foglio(ws, "UNIVERSO", ("SOCIETÀ INVENTATE (versione dimostrativa). " if demo else "") + f"{len(UNIVERSO)} titoli. Modelli: STD standard, CIC ciclico, UTL reti regolate, BAN banche, "
                                  "ASS assicurazioni, REIT immobiliare.")
    intest = ("Ticker Yahoo", "Società", "Area", "Settore", "Modello", "Valuta di quotazione", "Quotato in centesimi",
              "Valuta di bilancio attesa", "Indice di riferimento", "Paese del listino", "ADR / note")
    for j, (h, w) in enumerate(zip(intest, (13, 34, 16, 30, 9, 11, 11, 11, 13, 16, 70)), 1):
        testata(ws, 2, j, h, w)
    for i, t in enumerate(UNIVERSO):
        riga = (t.ticker, t.nome, t.area, t.settore, t.modello, t.valuta, "sì (GBp)" if t.in_centesimi else "no",
                t.valuta_bilancio, t.indice, t.paese_listino, t.adr or "-")
        for j, v in enumerate(riga, 1):
            ws.cell(R0 + i, j, v).font = car(BLU)
    ws.freeze_panes = "C3"
    ws.auto_filter.ref = f"A2:K{R0 + len(UNIVERSO) - 1}"
    if demo:
        return
    r = R0 + len(UNIVERSO) + 1
    ws.cell(r, 1, "Indici di riferimento ed ETF di confronto").font = car(NERO, True)
    for k, (nome, val) in INDICI.items():
        r += 1
        for j, v in enumerate((k, nome, "Indice", "", "", val), 1):
            ws.cell(r, j, v).font = car(BLU)
    for k, (nome, val, rif) in ETF.items():
        r += 1
        for j, v in enumerate((k, nome, f"ETF ad accumulazione ({rif})", "", "", val), 1):
            ws.cell(r, j, v).font = car(BLU)
    r += 2
    ws.cell(r, 1, "Esclusioni e sostituzioni rispetto all'elenco iniziale").font = car(NERO, True)
    for k, motivo in ESCLUSI.items():
        r += 1
        ws.cell(r, 1, k).font = car(BLU)
        ws.cell(r, 2, "Escluso: " + motivo).font = car(BLU)
    for k, (nuovo, motivo) in SOSTITUZIONI.items():
        r += 1
        ws.cell(r, 1, k).font = car(BLU)
        ws.cell(r, 2, f"Sostituito da {nuovo}. {motivo}").font = car(BLU)
    ws.freeze_panes = "C3"
    ws.auto_filter.ref = f"A2:K{R0 + len(UNIVERSO) - 1}"


# ============================================================================ VALUTAZIONE
SIGLE_SCENARI = {"Prudente": "p", "Base": "b", "Ottimistico": "o"}


def foglio_valutazione(lib: Libro, tickers: list[str]):
    t = Tab(lib, "VALUTAZIONE", "VALUTAZIONE - valore intrinseco per azione in tre scenari",
            "Ogni passaggio è una colonna. 'n.s.' = flusso di partenza negativo, valore non stimabile. Ipotesi dichiarate, non previsioni.")
    t.col("ticker", "Ticker", lambda tk: tk, None, "dato", 12)
    t.col("nome", "Società", "={D:nome}", None, "link", 26)
    t.col("modello", "Modello", "={D:modello}", None, "link", 8)
    t.col("idx", "Indice del modello", "=MATCH({modello},{P:modelli},0)", "0", "formula", 7)
    t.col("fin", "Finanziario (1 = banca o assicurazione)", '=IF(OR({modello}="BAN",{modello}="ASS"),1,0)', "0", "formula", 9)
    t.col("valuta_bil", "Valuta di bilancio", "={D:valuta_bil}", None, "link", 8)
    t.col("area", "Area", "={D:area}", None, "link", 12)
    t.col("prezzo", "Prezzo", "={D:prezzo}", F_NUM, "link")
    t.col("r0", "Rendimento richiesto della valuta",
          '=IFERROR(INDEX({P:tassi_r},MATCH({valuta_bil},{P:tassi_val},0)),INDEX({P:tassi_r},MATCH("ALTRO",{P:tassi_val},0)))', F_PCT)
    t.col("g0", "Crescita terminale della valuta",
          '=IFERROR(INDEX({P:tassi_g},MATCH({valuta_bil},{P:tassi_val},0)),INDEX({P:tassi_g},MATCH("ALTRO",{P:tassi_val},0)))', F_PCT)
    t.col("extra", "Maggiorazione Emergenti", '=IF({area}="Emergenti",{P:extra_emergenti},0)', F_PCT)
    t.col("cagr_ricavi", "CAGR dei ricavi", "={D:cagr_ricavi}", F_PCT, "link")
    t.col("cagr_eps", "CAGR dell'utile per azione", "={D:G2}", F_PCT, "link")
    t.col("c0", "Crescita storica (UTL: media ricavi / EPS)",
          '=IF({modello}="UTL",IF(COUNT({cagr_ricavi},{cagr_eps})=0,"n.d.",AVERAGE({cagr_ricavi},{cagr_eps})),{cagr_ricavi})', F_PCT)
    t.col("crescita", "Crescita storica riconosciuta (tra il minimo e il tetto del modello)",
          '=IF(ISNUMBER({c0}),MAX({P:crescita_minima},MIN({PM:tetto_crescita},{c0})),"n.d.")', F_PCT)
    t.col("flusso_ps", "Flusso normalizzato per azione", "={D:flusso_ps}", F_NUM, "link")
    t.col("quota", "Quota del flusso riconosciuta", "={PM:quota_flusso}", "0.00")
    t.col("cassa_ps", "Cassa netta per azione", "={D:cassa_netta_ps}", F_NUM, "link")
    t.col("tbv", "Patrimonio tangibile per azione", "={D:tbv_ps}", F_NUM, "link")
    t.col("roe_norm", "ROE normalizzato", "={D:roe_norm}", F_PCT, "link")
    t.col("f4", "Payout (dato)", "={D:F4}", "0.00", "link")
    t.col("payout", "Payout usato (finanziari)", "=IF(ISNUMBER({f4}),MAX(0,MIN(1,{f4})),{P:payout_predefinito})", "0.00")
    t.col("attf", "Finanziario calcolabile", "=IF(AND({fin}=1,ISNUMBER({tbv}),ISNUMBER({roe_norm})),1,0)", "0", "formula", 9)
    n = "{P:anni_fase}"
    for scen, s in SIGLE_SCENARI.items():
        e = f"[{scen}] "
        q, fatt, delta = (f"{{P:scenari.{scen}.{k}}}" for k in range(3))
        c = lambda k, s=s: "{" + k + "_" + s + "}"  # noqa: E731
        t.col(f"r_{s}", e + "rendimento richiesto", f"={{r0}}+{{extra}}+{delta}", F_PCT)
        t.col(f"gT_{s}", e + "crescita terminale", f"=MIN({{g0}},{c('r')}-{{P:distanza_terminale}})", F_PCT)
        t.col(f"g1_{s}", e + "crescita fase 1",
              f'=IF(ISNUMBER({{crescita}}),IF({{crescita}}>0,{{crescita}}*{q},{{crescita}}*(2-{q})),"n.d.")', F_PCT)
        t.col(f"g2_{s}", e + "crescita fase 2", f'=IF(ISNUMBER({c("g1")}),({c("g1")}+{c("gT")})/2,"n.d.")', F_PCT)
        t.col(f"f0_{s}", e + "flusso di partenza per azione",
              f'=IF(AND({{fin}}=0,ISNUMBER({{flusso_ps}}),ISNUMBER({{crescita}})),{{flusso_ps}}*{{quota}}*{fatt},"n.d.")', F_NUM)
        t.col(f"att_{s}", e + "flusso positivo (1 = sì)", f'=IF(ISNUMBER({c("f0")}),IF({c("f0")}>0,1,0),0)', "0", "formula", 8)
        t.col(f"a_{s}", e + "fattore annuo fase 1", f'=IF({c("att")}=1,(1+{c("g1")})/(1+{c("r")}),"n.d.")', "0.0000")
        t.col(f"b_{s}", e + "fattore annuo fase 2", f'=IF({c("att")}=1,(1+{c("g2")})/(1+{c("r")}),"n.d.")', "0.0000")
        serie = lambda x: f"IF(ABS({x}-1)<1E-12,{n},{x}*(1-{x}^{n})/(1-{x}))"  # noqa: E731
        t.col(f"va1_{s}", e + "valore attuale fase 1", f'=IF({c("att")}=1,{c("f0")}*{serie(c("a"))},"n.d.")', F_NUM)
        t.col(f"va2_{s}", e + "valore attuale fase 2",
              f'=IF({c("att")}=1,{c("f0")}*{c("a")}^{n}*{serie(c("b"))},"n.d.")', F_NUM)
        t.col(f"f10_{s}", e + "flusso dell'ultimo anno",
              f'=IF({c("att")}=1,{c("f0")}*(1+{c("g1")})^{n}*(1+{c("g2")})^{n},"n.d.")', F_NUM)
        t.col(f"vt_{s}", e + "valore terminale (Gordon)",
              f'=IF({c("att")}=1,{c("f10")}*(1+{c("gT")})/({c("r")}-{c("gT")}),"n.d.")', F_NUM)
        t.col(f"vavt_{s}", e + "valore attuale del terminale", f'=IF({c("att")}=1,{c("vt")}/(1+{c("r")})^(2*{n}),"n.d.")', F_NUM)
        t.col(f"cassa_{s}", e + "cassa netta riconosciuta",
              f'=IF({c("att")}=1,{{P:quota_cassa_netta}}*MAX(0,IF(ISNUMBER({{cassa_ps}}),{{cassa_ps}},0)),"n.d.")', F_NUM)
        t.col(f"roe_{s}", e + "ROE dello scenario (finanziari)", f'=IF({{attf}}=1,{{roe_norm}}*{fatt},"n.d.")', F_PCT)
        t.col(f"gB_{s}", e + "crescita del patrimonio (finanziari)",
              f'=IF({{attf}}=1,MIN({{PM:tetto_crescita}},{c("roe")}*(1-{{payout}})),"n.d.")', F_PCT)
        t.col(f"qf_{s}", e + "fattore annuo (finanziari)", f'=IF({{attf}}=1,(1+{c("gB")})/(1+{c("r")}),"n.d.")', "0.0000")
        t.col(f"extra_{s}", e + "valore attuale dell'extra-rendimento (finanziari)",
              f'=IF({{attf}}=1,({c("roe")}-{c("r")})*{{tbv}}/(1+{c("r")})*IF(ABS({c("qf")}-1)<1E-12,2*{n},'
              f'(1-{c("qf")}^(2*{n}))/(1-{c("qf")})),"n.d.")', F_NUM)
        t.col(f"valore_{s}", e + "VALORE INTRINSECO per azione",
              f'=IF({{fin}}=1,IF({{attf}}=1,MAX(0,{{tbv}}+{c("extra")}),"n.d."),IF(ISNUMBER({c("f0")}),IF({c("f0")}>0,'
              f'{c("va1")}+{c("va2")}+{c("vavt")}+{c("cassa")},"n.s."),"n.d."))', F_NUM, "formula", 13)
    t.scrivi(tickers)
    return t


# ============================================================================ BUFFETT
RISCHI = [("r_leva", "Leva finanziaria alta"), ("r_marg", "Margini in calo"), ("r_ric", "Ricavi in calo"),
          ("r_fcf", "Free cash flow negativo"), ("r_div", "Dividendi non coperti"), ("r_dil", "Diluizione degli azionisti"),
          ("r_avv", "Avviamento elevato"), ("r_cop", "Copertura degli interessi bassa")]


def foglio_buffett(lib: Libro, tickers: list[str]):
    t = Tab(lib, "BUFFETT", "BUFFETT SCORE - strategia A (qualità e valore)",
            "Metodologia ispirata ai principi del value investing. I punteggi ordinano i titoli secondo criteri dichiarati: non sono previsioni.")
    t.col("ticker", "Ticker", lambda tk: tk, None, "dato", 12)
    t.col("nome", "Società", "={D:nome}", None, "link", 26)
    t.col("modello", "Modello", "={D:modello}", None, "link", 8)
    t.col("idx", "Indice del modello", "=MATCH({modello},{P:modelli},0)", "0", "formula", 7)
    t.col("fin", "Finanziario", '=IF(OR({modello}="BAN",{modello}="ASS"),1,0)', "0", "formula", 7)
    t.col("prezzo", "Prezzo", "={D:prezzo}", F_NUM, "link")
    t.col("eta_p", "Età del prezzo (giorni)", '=IF(ISNUMBER({D:data_prezzo}),{P:data_rif}-{D:data_prezzo},"n.d.")', "0")
    t.col("eta_e", "Età dell'ultimo esercizio (giorni)", '=IF(ISNUMBER({D:ultimo_esercizio}),{P:data_rif}-{D:ultimo_esercizio},"n.d.")', "0")
    t.col("vecchio", "Dati vecchi (1 = sì)",
          "=IF(AND(ISNUMBER({eta_p}),ISNUMBER({eta_e})),IF(OR({eta_p}>{P:giorni_prezzo},{eta_e}>{P:giorni_esercizio}),1,0),1)", "0")
    t.col("valore_base", "Valore intrinseco base", "={V:valore_b}", F_NUM, "link", 12)
    # --- valori delle 19 metriche
    for m in METRICHE_A:
        nome = f"{m} valore: {NOMI_METRICHE[m]}"
        fmt = "0.000"
        if m == "Q3":
            f = '=IF({fin}=1,IF(ISNUMBER({G:Q3}),{G:Q3},"n.d."),{D:Q3})'
        elif m == "F5":
            f = '=IF(ISNUMBER({G:F5}),{G:F5},"n.d.")'
        elif m == "V1":
            f = '=IF(AND(ISNUMBER({valore_base}),ISNUMBER({prezzo})),IF(AND({valore_base}>0,{prezzo}>0),1-{prezzo}/{valore_base},"n.d."),"n.d.")'
        elif m == "V2":
            f = '=IF(AND(ISNUMBER({D:flusso_ps}),ISNUMBER({prezzo})),IF({prezzo}>0,{D:flusso_ps}*{PM:quota_flusso}/{prezzo},"n.d."),"n.d.")'
        elif m == "V3":
            f = ('=IF(ISNUMBER({prezzo}),IF({prezzo}>0,IF({fin}=1,IF(ISNUMBER({D:tbv_ps}),IF({D:tbv_ps}>0,{prezzo}/{D:tbv_ps},"n.d."),"n.d."),'
                 'IF(AND(ISNUMBER({D:ebitda_q}),ISNUMBER({D:debito_netto_q}),ISNUMBER({D:azioni})),'
                 'IF({D:ebitda_q}>0,({D:azioni}*{prezzo}+{D:debito_netto_q})/{D:ebitda_q},999),"n.d.")),"n.d."),"n.d.")')
        elif m == "V4":
            f = '=IF(AND(ISNUMBER({D:eps_atteso}),ISNUMBER({prezzo})),IF(AND({D:eps_atteso}>0,{prezzo}>0),{prezzo}/{D:eps_atteso},"n.d."),"n.d.")'
        else:
            f = "={D:" + m + "}"
        t.col("v_" + m, nome, f, fmt, "link" if f.startswith("={D:") else "formula", 10)
    for m in METRICHE_A:
        t.col("w_" + m, f"{m} peso", "=INDEX({P:met." + m + "},{idx}*3-2)", "0", "formula", 7)
    for m in METRICHE_A:
        s0, s100 = "INDEX({P:met." + m + "},{idx}*3-1)", "INDEX({P:met." + m + "},{idx}*3)"
        t.col("p_" + m, f"{m} punti",
              "=IF(AND(ISNUMBER({v_" + m + "}),{w_" + m + "}>0," + s100 + "<>" + s0 + ")," + PUNTI("{v_" + m + "}", s0, s100) + ',"n.d.")',
              F_PUNTI, "formula", 8)
    # --- pilastri
    per_pil = {L: [m for m in METRICHE_A if m[0] == L] for L in "QFGV"}

    def blocco(pref, L):
        ms = per_pil[L]
        return "{" + pref + ms[0] + "}:{" + pref + ms[-1] + "}"
    for L in "QFGV":
        w, p = blocco("w_", L), blocco("p_", L)
        t.col("cop_" + L, f"Copertura pilastro {L}", f"=IF(SUM({w})=0,0,SUMPRODUCT(--ISNUMBER({p}),{w})/SUM({w}))", "0%", "formula", 9)
    for L in "QFGV":
        w, p = blocco("w_", L), blocco("p_", L)
        t.col("pil_" + L, f"Pilastro {L}: {NOMI_PILASTRI_A[L]}",
              "=IF(AND({cop_" + L + "}>={P:copertura_minima}-1E-9,{cop_" + L + "}>0)," +
              f"SUMPRODUCT({p},{w})/SUMPRODUCT(--ISNUMBER({p}),{w})," + '"n.d.")', F_PUNTI, "formula", 11)
    tutti_v = "{v_" + METRICHE_A[0] + "}:{v_" + METRICHE_A[-1] + "}"
    tutti_w = "{w_" + METRICHE_A[0] + "}:{w_" + METRICHE_A[-1] + "}"
    t.col("completezza", "Completezza: metriche disponibili tra quelle usate",
          f'=SUMPRODUCT(--ISNUMBER({tutti_v}),--({tutti_w}>0))/COUNTIF({tutti_w},">0")', "0%", "formula", 11)
    wq, wf, wg, wv = ("{PM:pesi_pilastri." + L + "}" for L in "QFGV")
    t.col("qc", "Qualità composita (Q, F, G)",
          "=IF(AND(ISNUMBER({pil_Q}),ISNUMBER({pil_F}),ISNUMBER({pil_G}))," +
          f"({wq}*{{pil_Q}}+{wf}*{{pil_F}}+{wg}*{{pil_G}})/({wq}+{wf}+{wg})," + '"n.d.")', F_PUNTI, "formula", 10)
    t.col("classe", "Classe", '=IF(ISNUMBER({qc}),IF({qc}>={P:classe_a},"A",IF({qc}>={P:classe_b},"B","C")),"n.d.")', None, "formula", 7)
    t.col("v_usata", "Valutazione usata = min(V, Qualità + tetto)",
          '=IF(AND(ISNUMBER({qc}),ISNUMBER({pil_V}),{vecchio}=0),MIN({pil_V},{qc}+{P:tetto_valutazione}),"n.d.")', F_PUNTI, "formula", 10)
    t.col("corr", "Correzione qualitativa (GIUDIZI, limitata)",
          "=MAX(-{P:correzione_massima},MIN({P:correzione_massima},IF(ISNUMBER({G:correzione}),{G:correzione},0)))", F_PUNTI, "formula", 10)
    t.col("grezzo", "Punteggio non arrotondato",
          "=IF(ISNUMBER({v_usata})," + f"MAX(0,MIN(100,(({wq}+{wf}+{wg})*{{qc}}+{wv}*{{v_usata}})/({wq}+{wf}+{wg}+{wv})+{{corr}}))," + '"n.d.")',
          "0.000", "formula", 10)
    t.col("punteggio", "BUFFETT SCORE", '=IF(ISNUMBER({grezzo}),ROUND({grezzo},1),"Dati insufficienti")', F_PUNTI, "formula", 12)
    t.col("margine", "Margine di sicurezza", "={v_V1}", F_PCT, "formula", 10)
    t.col("richiesto", "Margine richiesto", '=IF({classe}="A",{P:margine_a},IF({classe}="B",{P:margine_b},"n.d."))', "0%", "formula", 9)
    t.col("prezzo_acq", "Prezzo d'acquisto",
          '=IF(AND({vecchio}=0,ISNUMBER({qc}),ISNUMBER({richiesto}),ISNUMBER({valore_base}),ISNUMBER({prezzo})),'
          'IF({prezzo}>0,{valore_base}*(1-{richiesto}),"n.d."),"n.d.")', F_NUM, "formula", 11)
    t.col("verdetto", "Verdetto",
          '=IF(OR({vecchio}=1,NOT(ISNUMBER({qc}))),"Dati insufficienti",IF({classe}="C","Non comprerei: qualità insufficiente",'
          'IF({valore_base}="n.s.","Non comprerei: valore non stimabile",IF(ISNUMBER({prezzo_acq}),'
          'IF({prezzo}<{prezzo_acq},"Comprerei","Aspetterei"),"Dati insufficienti"))))', None, "formula", 32)
    # --- segnali di rischio
    t.col("r_leva", "Rischio: leva alta / patrimonio sottile", "=IF(ISNUMBER({p_F1}),IF({p_F1}=0,1,0),0)", "0", "formula", 8)
    t.col("r_marg", "Rischio: margini in calo",
          "=IF(AND(ISNUMBER({D:margine_ultimo}),ISNUMBER({D:margine_medio_prec})),"
          "IF({D:margine_ultimo}<{D:margine_medio_prec}-{P:rischio_calo_margine},1,0),0)", "0", "formula", 8)
    t.col("r_ric", "Rischio: ricavi in calo", "=IF(ISNUMBER({D:var_ricavi_ultimo}),IF({D:var_ricavi_ultimo}<0,1,0),0)", "0", "formula", 8)
    t.col("r_fcf", "Rischio: free cash flow negativo", "=IF(AND({fin}=0,ISNUMBER({D:fcf_ultimo})),IF({D:fcf_ultimo}<0,1,0),0)", "0", "formula", 8)
    t.col("r_div", "Rischio: dividendi non coperti", "=IF(ISNUMBER({v_F4}),IF({v_F4}>{P:rischio_payout},1,0),0)", "0", "formula", 8)
    t.col("r_dil", "Rischio: diluizione", "=IF(ISNUMBER({v_G3}),IF({v_G3}>{P:rischio_diluizione},1,0),0)", "0", "formula", 8)
    t.col("r_avv", "Rischio: avviamento elevato",
          "=IF(ISNUMBER({D:avviamento_su_patr}),IF({D:avviamento_su_patr}>{P:rischio_avviamento},1,0),0)", "0", "formula", 8)
    t.col("r_cop", "Rischio: copertura interessi bassa", "=IF(AND({fin}=0,ISNUMBER({v_F2})),IF({v_F2}<{P:rischio_copertura},1,0),0)", "0", "formula", 8)
    t.col("n_rischi", "Numero di segnali di rischio", "=SUM({r_leva}:{r_cop})", "0", "formula", 8)
    pezzi = ['IF({r_leva}=1,IF({fin}=1,"Patrimonio sottile rispetto all\'attivo; ","Leva finanziaria alta; "),"")']
    pezzi += [f'IF({{{k}}}=1,"{testo}; ","")' for k, testo in RISCHI[1:]]
    t.col("rischi_grezzo", "Segnali (concatenati)", "=" + "&".join(pezzi), None, "formula", 10)
    t.col("rischi", "Segnali di rischio ricavati dai dati",
          '=IF(LEN({rischi_grezzo})>2,LEFT({rischi_grezzo},LEN({rischi_grezzo})-2),"Nessun segnale")', None, "formula", 50)
    t.col("ordine", "Posizione in classifica",
          '=IF(ISNUMBER({punteggio}),RANK({punteggio},{R:punteggio})+COUNTIF(' + f"${{L}}${R0}:{{punteggio}}" + ',{punteggio})-1,"")',
          "0", "formula", 9)
    L = t.cols["punteggio"]
    i = [k for k, d in enumerate(t.defs) if d[0] == "ordine"][0]
    d = t.defs[i]
    t.defs[i] = (d[0], d[1], d[2].replace("${L}", "$" + L), d[3], d[4], d[5])
    t.scrivi(tickers)
    return t


# ============================================================================ TRADING
def foglio_trading(lib: Libro, tickers: list[str]):
    t = Tab(lib, "TRADING", "TRADING SCORE - strategia B (tendenza e forza)",
            "L'obiettivo è una proiezione convenzionale, non una previsione. Nessuna probabilità. Classifica separata da quella di valore.")
    P = lambda k: "{P:" + k + "}"  # noqa: E731
    t.col("ticker", "Ticker", lambda tk: tk, None, "dato", 12)
    t.col("nome", "Società", "={D:nome}", None, "link", 26)
    t.col("settore", "Settore", "={D:settore}", None, "link", 20)
    dati = [("prezzo", F_NUM), ("mm20", F_NUM), ("mm50", F_NUM), ("mm200", F_NUM), ("mm200_20fa", F_NUM), ("rsi", "0.0"),
            ("macd", "0.000"), ("macd_segnale", "0.000"), ("macd_isto", "0.000"), ("macd_isto_5fa", "0.000"), ("atr", F_NUM),
            ("max20", F_NUM), ("max52", F_NUM)] + [(f"res{i + 1}", F_NUM) for i in range(N_RESISTENZE)] + [
            ("r1m", F_PCT), ("r3m", F_PCT), ("r6m", F_PCT), ("r12m_1", F_PCT), ("idx_r3m", F_PCT), ("idx_r6m", F_PCT),
            ("med_settore_3m", F_PCT), ("n_settore", "0"), ("vol_su_giu", "0.00"), ("vol_20_60", "0.00"), ("rev_su30", "0"),
            ("rev_giu30", "0"), ("reazione_utili", F_PCT), ("data_utili", F_DATA), ("prossimi_utili", F_DATA), ("cambio_eur", "0.0000")]
    intest = {k: h for k, h, _ in campi_dati()}
    for k, fmt in dati:
        t.col(k, intest[k], "={D:" + k + "}", fmt, "link", 10)
    t.col("eta_p", "Età del prezzo (giorni)", '=IF(ISNUMBER({D:data_prezzo}),{P:data_rif}-{D:data_prezzo},"n.d.")', "0")
    t.col("vecchio", "Prezzo vecchio (1 = sì)", "=IF(ISNUMBER({eta_p}),IF({eta_p}>{P:giorni_prezzo},1,0),1)", "0")
    # Trend
    t.col("trend", "TREND",
          "=IF(COUNT({prezzo},{mm20},{mm50},{mm200},{mm200_20fa})=5,"
          f"{P('trend_punti.0')}*IF({{prezzo}}>{{mm200}},1,0)+{P('trend_punti.1')}*IF({{mm50}}>{{mm200}},1,0)+"
          f"{P('trend_punti.2')}*IF({{prezzo}}>{{mm50}},1,0)+{P('trend_punti.3')}*IF({{mm200}}>{{mm200_20fa}},1,0)+"
          f"{P('trend_punti.4')}*IF({{prezzo}}>{{mm20}},1,0)," + '"n.d.")', F_PUNTI)
    t.col("stato_trend", "Stato del trend",
          '=IF(ISNUMBER({trend}),IF({trend}>={P:trend_rialzista},"Rialzista",IF({trend}<{P:trend_ribassista},"Ribassista","Laterale")),"n.d.")',
          None, "formula", 11)
    # Momentum
    t.col("comp", "Momentum composito",
          f"=IF(COUNT({{r12m_1}},{{r6m}},{{r3m}})=3,{P('mom_pesi.0')}*{{r12m_1}}+{P('mom_pesi.1')}*{{r6m}}+{P('mom_pesi.2')}*{{r3m}}," + '"n.d.")', F_PCT)
    t.col("comp_num", "Composito (numerico per il rango)", "=IF(ISNUMBER({comp}),{comp},1E+99)", "0.000", "formula", 8)
    t.col("rango", "Rango percentile nell'universo",
          '=IF(ISNUMBER({comp}),IF(COUNT({R:comp})>1,SUMPRODUCT(--({R:comp_num}<{comp}))/(COUNT({R:comp})-1),0.5),"n.d.")', "0.000")
    t.col("mom", "MOMENTUM", "=IF(ISNUMBER({comp}),50*{rango}+0.5*" + PUNTI("{comp}", P("mom_s0"), P("mom_s100")) + ',"n.d.")', F_PUNTI)
    # Forza relativa
    t.col("fr1", "FR: indice a 3 mesi", "=IF(COUNT({r3m},{idx_r3m})=2," + PUNTI("{r3m}-{idx_r3m}", "-" + P("fr_3m"), P("fr_3m")) + ',"n.d.")', F_PUNTI)
    t.col("fr2", "FR: indice a 6 mesi", "=IF(COUNT({r6m},{idx_r6m})=2," + PUNTI("{r6m}-{idx_r6m}", "-" + P("fr_6m"), P("fr_6m")) + ',"n.d.")', F_PUNTI)
    t.col("fr3", "FR: mediana del settore a 3 mesi",
          "=IF(COUNT({r3m},{med_settore_3m})=2,IF({n_settore}>={P:fr_min_settore}," +
          PUNTI("{r3m}-{med_settore_3m}", "-" + P("fr_settore"), P("fr_settore")) + ',"n.d."),"n.d.")', F_PUNTI)
    t.col("forza", "FORZA RELATIVA", '=IF(COUNT({fr1},{fr2},{fr3})=0,"n.d.",AVERAGE({fr1},{fr2},{fr3}))', F_PUNTI)
    # Oscillatori
    f = P("rsi_pun.5")
    for i in range(4, -1, -1):
        f = f"IF({{rsi}}<{P(f'rsi_lim.{i}')},{P(f'rsi_pun.{i}')},{f})"
    t.col("rsi_p", "Punti RSI", "=IF(ISNUMBER({rsi})," + f + ',"n.d.")', F_PUNTI)
    t.col("macd_p", "Punti MACD",
          "=IF(COUNT({macd},{macd_segnale},{macd_isto},{macd_isto_5fa})=4,"
          f"{P('macd_sopra')}*IF({{macd}}>{{macd_segnale}},1,0)+{P('macd_isto')}*IF({{macd_isto}}>{{macd_isto_5fa}},1,0)," + '"n.d.")', F_PUNTI)
    t.col("osc", "OSCILLATORI",
          f"=IF(AND(ISNUMBER({{rsi_p}}),ISNUMBER({{macd_p}})),{P('osc_peso_rsi')}*{{rsi_p}}+(1-{P('osc_peso_rsi')})*{{macd_p}}," + '"n.d.")', F_PUNTI)
    # Volumi
    rel = PUNTI("{vol_20_60}", P("vol_rel.0"), P("vol_rel.1"))
    t.col("vol", "VOLUMI",
          "=IF(COUNT({vol_su_giu},{vol_20_60},{r1m})=3," + f"{P('vol_peso_ud')}*" + PUNTI("{vol_su_giu}", P("vol_ud.0"), P("vol_ud.1")) +
          f"+(1-{P('vol_peso_ud')})*IF({{r1m}}<0,100-{rel},{rel})," + '"n.d.")', F_PUNTI)
    # Setup operativo
    t.col("s_ok", "Setup possibile (prezzo > media 200 e media 50 > media 200)",
          "=IF(COUNT({prezzo},{atr},{mm20},{mm50},{mm200},{rsi},{max20})=7,IF(AND({atr}>0,{prezzo}>{mm200},{mm50}>{mm200}),1,0),0)", "0")
    t.col("rischio", "Rischio per azione (stop in ATR)", '=IF(ISNUMBER({atr}),{P:setup_stop_atr}*{atr},"n.d.")', F_NUM)
    res = "{res1}:{res" + str(N_RESISTENZE) + "}"

    def candidato(pref, nome, cond, ingresso):
        c = lambda k: "{" + pref + k + "}"  # noqa: E731
        t.col(pref + "c", f"{nome}: condizione", f"=IF({{s_ok}}=1,IF({cond},1,0),0)", "0", "formula", 8)
        t.col(pref + "in", f"{nome}: ingresso", f'=IF({c("c")}=1,{ingresso},"n.d.")', F_NUM)
        t.col(pref + "k", f"{nome}: resistenze non superiori all'ingresso",
              f'=IF({c("c")}=1,SUMPRODUCT(({res}<={c("in")})*ISNUMBER({res})),"n.d.")', "0", "formula", 8)
        t.col(pref + "res", f"{nome}: prima resistenza sopra l'ingresso",
              f'=IF({c("c")}=1,MIN(IF({c("k")}<COUNT({res}),INDEX({res},1,{c("k")}+1),1E+99),'
              f'IF(ISNUMBER({{max52}}),IF({{max52}}>{c("in")},{{max52}},1E+99),1E+99)),"n.d.")', F_NUM)
        t.col(pref + "ob", f"{nome}: obiettivo",
              f'=IF({c("c")}=1,MIN({c("in")}+{{P:setup_obiettivo_r}}*{{rischio}},{c("res")}),"n.d.")', F_NUM)
        t.col(pref + "rr", f"{nome}: rendimento/rischio", f'=IF({c("c")}=1,({c("ob")}-{c("in")})/{{rischio}},"n.d.")', "0.00")
        t.col(pref + "v", f"{nome}: valido", f'=IF({c("c")}=1,IF({c("rr")}>={{P:setup_rr_min}}-1E-12,1,0),0)', "0", "formula", 8)
    candidato("ro_", "Rottura", "{max20}-{prezzo}<={P:setup_rottura_atr}*{atr}", "{max20}+{P:setup_ingresso_atr}*{atr}")
    candidato("ri_", "Ritracciamento",
              "AND({prezzo}>={mm50}-{P:setup_fascia_atr}*{atr},{prezzo}<={mm20}+{P:setup_fascia_atr}*{atr},"
              "{rsi}>={P:setup_rsi.0},{rsi}<={P:setup_rsi.1})", "{prezzo}")
    t.col("setup", "Setup",
          '=IF({ro_v}=1,"Rottura",IF({ri_v}=1,"Ritracciamento",IF({ro_c}=1,"Rottura",IF({ri_c}=1,"Ritracciamento","-"))))', None, "formula", 14)
    t.col("valido", "Setup valido (1 = sì)", "=IF(OR({ro_v}=1,{ri_v}=1),1,0)", "0")
    for k, nome, fmt in (("in", "INGRESSO", F_NUM), ("ob", "OBIETTIVO (proiezione convenzionale)", F_NUM), ("rr", "Rendimento/rischio", "0.00")):
        t.col("s_" + k, nome, '=IF({setup}="Rottura",{ro_' + k + '},IF({setup}="Ritracciamento",{ri_' + k + '},"n.d."))', fmt)
    t.col("s_stop", "STOP", '=IF(ISNUMBER({s_in}),{s_in}-{rischio},"n.d.")', F_NUM)
    for k, nome in (("in", "Ingresso operativo"), ("stop", "Stop operativo"), ("ob", "Obiettivo operativo")):
        t.col("op_" + k, nome + " (solo se il setup è valido)", '=IF({valido}=1,{s_' + k + '},"-")', F_NUM)
    t.col("op_setup", "Setup valido", '=IF({valido}=1,{setup},"-")', None, "formula", 14)
    # Assetto e rischio
    t.col("ass", "ASSETTO E RISCHIO",
          "=IF(COUNT({prezzo},{max52},{atr})=3," + f"{P('ass_pesi.0')}*" + PUNTI("1-{prezzo}/{max52}", P("ass_dist.0"), P("ass_dist.1")) +
          f"+{P('ass_pesi.1')}*" + PUNTI("{atr}/{prezzo}", P("ass_atr.0"), P("ass_atr.1")) +
          f"+{P('ass_pesi.2')}*IF({{valido}}=1," + PUNTI("{s_rr}", P("ass_rr.0"), P("ass_rr.1")) + ',0),"n.d.")', F_PUNTI)
    # Catalizzatori
    t.col("cat1", "Catalizzatori: saldo revisioni a 30 giorni",
          '=IF(COUNT({rev_su30},{rev_giu30})=2,IF({rev_su30}+{rev_giu30}>0,50+50*({rev_su30}-{rev_giu30})/({rev_su30}+{rev_giu30}),"n.d."),"n.d.")', F_PUNTI)
    t.col("gg_da", "Giorni dall'ultima trimestrale", '=IF(ISNUMBER({data_utili}),{P:data_rif}-{data_utili},"n.d.")', "0")
    t.col("cat2", "Catalizzatori: reazione alla trimestrale",
          "=IF(COUNT({reazione_utili},{gg_da})=2,IF({gg_da}<={P:cat_giorni}," +
          PUNTI("{reazione_utili}", "-" + P("cat_reazione"), P("cat_reazione")) + ',"n.d."),"n.d.")', F_PUNTI)
    t.col("cat", "CATALIZZATORI", '=IF(COUNT({cat1},{cat2})=0,"n.d.",AVERAGE({cat1},{cat2}))', F_PUNTI)
    t.col("gg_a", "Giorni alla prossima trimestrale", '=IF(ISNUMBER({prossimi_utili}),{prossimi_utili}-{P:data_rif},"n.d.")', "0")
    t.col("avviso", "Avviso: trimestrale imminente (1 = sì)", "=IF(ISNUMBER({gg_a}),IF(AND({gg_a}>=0,{gg_a}<={P:cat_avviso}),1,0),0)", "0")
    # Punteggio
    pil = list(zip(("trend", "mom", "forza", "osc", "vol", "ass", "cat"), PILASTRI_B))
    disp = "+".join(f"IF(ISNUMBER({{{k}}}),{P('pesi_b.' + n)},0)" for k, n in pil)
    somma = "+".join(f"IF(ISNUMBER({{{k}}}),{P('pesi_b.' + n)}*{{{k}}},0)" for k, n in pil)
    tot = "+".join(P("pesi_b." + n) for _, n in pil)
    t.col("cop", "Copertura del peso", f"=({disp})/({tot})", "0%")
    t.col("grezzo", "Punteggio non arrotondato",
          "=IF(AND(ISNUMBER({trend}),ISNUMBER({mom}),{cop}>={P:copertura_b}-1E-9,{vecchio}=0)," + f"({somma})/({disp})," + '"n.d.")', "0.000")
    t.col("punteggio", "TRADING SCORE", '=IF(ISNUMBER({grezzo}),ROUND({grezzo},1),"Dati insufficienti")', F_PUNTI, "formula", 12)
    t.col("segnale", "Segnale",
          '=IF(NOT(ISNUMBER({punteggio})),"Dati insufficienti",IF(AND({punteggio}>={P:soglia_segnale},{valido}=1),"Setup attivo",'
          'IF({punteggio}>={P:soglia_segnale},"In osservazione",IF({stato_trend}="Ribassista","Evitare","Neutrale"))))', None, "formula", 16)
    t.col("n_azioni", "Numero di azioni (capitale di esempio)",
          '=IF(AND({valido}=1,ISNUMBER({cambio_eur})),INT(MIN({P:capitale}*{P:rischio_operazione}/(({s_in}-{s_stop})/{cambio_eur}),'
          '{P:capitale}*{P:peso_massimo}/({s_in}/{cambio_eur}))),"n.d.")', "0")
    L = "{punteggio}"
    t.col("ordine", "Posizione in classifica",
          '=IF(ISNUMBER({punteggio}),RANK({punteggio},{R:punteggio})+COUNTIF(@@:{punteggio},{punteggio})-1,"")', "0", "formula", 9)
    del L
    col_p = t.cols["punteggio"]
    i = [k for k, d in enumerate(t.defs) if d[0] == "ordine"][0]
    d = t.defs[i]
    t.defs[i] = (d[0], d[1], d[2].replace("@@", f"${col_p}${R0}"), d[3], d[4], d[5])
    t.scrivi(tickers)
    return t


# ============================================================================ celle gialle
def foglio_mappa(lib: Libro):
    """Foglio nascosto: chiave | foglio | cella | valore predefinito | ticker della riga."""
    ws = lib.foglio("_MAPPA")
    ws.append(["chiave", "foglio", "cella", "predefinito", "ticker"])
    for chiave, foglio, cella, pred, ticker in lib.mappa:
        ws.append([chiave, foglio, cella, pred, ticker])
    ws.sheet_state = "hidden"


def leggi_gialle(percorso) -> dict:
    """Legge da un cruscotto esistente i valori delle celle gialle che l'utente ha cambiato.
    -> {chiave: valore}. Per le righe legate a un ticker la cella viene cercata sul ticker in colonna A,
    cosi' un ordinamento fatto dall'utente non sposta i dati manuali su un altro titolo."""
    from openpyxl import load_workbook
    try:
        wb = load_workbook(percorso)
    except Exception:  # noqa: BLE001 - file assente o illeggibile: nessun valore da conservare
        return {}
    if "_MAPPA" not in wb.sheetnames:
        return {}
    out = {}
    righe_ticker: dict[str, dict] = {}
    for chiave, foglio, cella, pred, ticker in wb["_MAPPA"].iter_rows(min_row=2, values_only=True):
        if not chiave or foglio not in wb.sheetnames:
            continue
        ws = wb[foglio]
        if ticker:
            if foglio not in righe_ticker:
                righe_ticker[foglio] = {ws.cell(r, 1).value: r for r in range(1, ws.max_row + 1)}
            r = righe_ticker[foglio].get(ticker)
            if r is None:
                continue
            col = re.match(r"[A-Z]+", cella).group(0)
            v = ws[f"{col}{r}"].value
        else:
            v = ws[cella].value
        if isinstance(v, str) and v.startswith("="):
            continue                      # l'utente ha messo una formula: non si conserva
        if v != pred and not (v in (None, "") and pred in (None, "")):
            out[chiave] = v
    return out


def parametri_da_gialle(P: dict, gialle: dict) -> dict:
    """Applica ai parametri i valori conservati (chiavi 'P|[percorso]')."""
    for chiave, v in gialle.items():
        if not chiave.startswith("P|"):
            continue
        percorso = json.loads(chiave[2:])
        if not isinstance(v, (int, float)) and percorso[0] != "rischi_settore":
            continue                      # un parametro numerico svuotato o reso testo: resta il predefinito
        x = P
        try:
            for k in percorso[:-1]:
                x = x[k]
            x[percorso[-1]] = v
        except (KeyError, IndexError, TypeError):
            continue                      # parametro non piu' esistente
    return P


def giudizi_da_gialle(gialle: dict) -> dict:
    out: dict[str, dict] = {}
    for chiave, v in gialle.items():
        p = chiave.split("|")
        if len(p) == 3 and p[0] == "GIUDIZI":
            out.setdefault(p[2], {})[p[1]] = v
    return out


# ============================================================================ assemblaggio
ORDINE_FOGLI = ["CRUSCOTTO", "SCREENER", "SCHEDA", "BUFFETT", "VALUTAZIONE", "TRADING", "MOVIMENTI", "NOTIZIE",
                "PORTAFOGLIO", "SIMULATORE", "BACKTEST", "PERFORMANCE", "GIUDIZI", "PARAMETRI", "UNIVERSO", "DATI",
                "QUALITA_DATI", "METODOLOGIA", "FONTI", "STATO", "LEGGIMI", "PREZZI_5A", "CORRELAZIONI", "ETF_MENSILI",
                "_MAPPA"]


def costruisci(ingressi: dict, P: dict, giudizi: dict, oggi: date, serie5a: dict | None = None,
               strumenti: list | None = None, scelto: str | None = None, universo: list | None = None,
               demo: bool = False, ctx: dict | None = None) -> Libro:
    universo = universo or UNIVERSO
    from .excel_viste import (foglio_cruscotto, foglio_performance, foglio_prezzi, foglio_qualita, foglio_scheda,
                              foglio_screener)
    lib = Libro(len(ingressi))
    for nome in ORDINE_FOGLI:
        lib.foglio(nome)
    tickers = list(ingressi)
    foglio_parametri(lib, P, oggi)
    foglio_dati(lib, ingressi, {t.ticker: t for t in universo})
    foglio_giudizi(lib, ingressi, giudizi)
    foglio_universo(lib, universo, demo)
    foglio_valutazione(lib, tickers)
    foglio_buffett(lib, tickers)
    foglio_trading(lib, tickers)
    foglio_screener(lib, tickers)
    foglio_performance(lib, tickers)
    foglio_qualita(lib, tickers, strumenti or [])
    if serie5a:
        n_sett = foglio_prezzi(lib, serie5a)
        foglio_scheda(lib, tickers, n_sett, scelto if scelto in ingressi else tickers[0])
    if ctx is not None:
        from . import excel_doc, excel_fase4 as f4
        f4.foglio_movimenti(lib, ctx["movimenti"], ctx["valutazioni"])
        f4.foglio_notizie(lib, ctx["notizie"])
        f4.foglio_correlazioni(lib, ctx["stat"])
        f4.foglio_portafoglio(lib, ctx["settori"], ctx["aree"], ctx["gialle"])
        f4.foglio_simulatore(lib, ctx["gialle"], ctx["etf"], f4.foglio_etf(lib, ctx["etf"]))
        f4.foglio_backtest(lib, ctx["backtest"])
        excel_doc.foglio_metodologia(lib)
        excel_doc.foglio_fonti(lib)
        excel_doc.foglio_stato(lib, ctx)
        excel_doc.foglio_leggimi(lib, demo)
    foglio_cruscotto(lib, demo)
    foglio_mappa(lib)
    for nome in list(lib.wb.sheetnames):          # fogli non costruiti: non si lasciano vuoti
        if lib.wb[nome].max_row == 1 and lib.wb[nome]["A1"].value is None and nome != "_MAPPA":
            lib.wb.remove(lib.wb[nome])
    lib.wb.active = 0
    lib.wb.calculation.fullCalcOnLoad = True      # Excel ricalcola tutto all'apertura
    return lib


def serie_settimanali(con, tickers: list[str], anni: int = 5) -> dict:
    """Ultima chiusura di ogni settimana negli ultimi `anni` anni, per ticker (i vuoti si riempiono
    con l'ultima chiusura nota)."""
    from datetime import timedelta
    fine = con.execute("SELECT MAX(data) FROM prezzi").fetchone()[0]
    if not fine:
        return {"date": [], "tickers": tickers, "valori": {t: [] for t in tickers}}
    inizio = (date.fromisoformat(fine) - timedelta(days=int(365.25 * anni))).isoformat()
    per_t, settimane = {}, set()
    for tk in tickers:
        d = {}
        for g, c in con.execute("SELECT data, chiusura FROM prezzi WHERE ticker=? AND data>=? ORDER BY data", (tk, inizio)):
            a, s, _ = date.fromisoformat(g).isocalendar()
            d[(a, s)] = c                 # resta l'ultima seduta della settimana
        per_t[tk] = d
        settimane |= set(d)
    ordinate = sorted(settimane)
    valori = {}
    for tk in tickers:
        v, ultimo = [], None
        for s in ordinate:
            ultimo = per_t[tk].get(s, ultimo)
            v.append(ultimo)
        primo = next((x for x in v if x is not None), None)
        valori[tk] = [primo if x is None else x for x in v]
    date_ = [date.fromisocalendar(a, s, 5) for a, s in ordinate]
    return {"date": date_, "tickers": tickers, "valori": valori}


def strumenti_di_confronto(con) -> list[tuple]:
    out = []
    nomi = {**{k: v[0] for k, v in INDICI.items()}, **{k: v[0] for k, v in ETF.items()}}
    for k, nome in nomi.items():
        q = con.execute("SELECT stato, motivi, ultimo_prezzo, n_prezzi FROM qualita WHERE ticker=?", (k,)).fetchone()
        out.append((k, nome, q[0] if q else "ERRORE", (q[1] if q else "nessun dato") or "-",
                    date.fromisoformat(q[2]) if q and q[2] else None, q[3] if q else 0))
    for val, d, fonte, n in con.execute("SELECT valuta, MAX(data), fonte, COUNT(*) FROM cambi GROUP BY valuta"):
        out.append((f"EUR/{val}", f"Cambio di riferimento ({fonte})", "OK", "-", date.fromisoformat(d), n))
    return out


def etf_mensili(con) -> dict | None:
    """Chiusure di fine mese dei due ETF di confronto, nelle date in cui esistono entrambe."""
    k = list(ETF)
    serie = []
    for tk in k:
        d = {}
        for g, c in con.execute("SELECT data, chiusura FROM prezzi WHERE ticker=? ORDER BY data", (tk,)):
            d[g[:7]] = (g, c)             # resta l'ultima seduta del mese
        serie.append(d)
    mesi = sorted(set(serie[0]) & set(serie[1]))
    if len(mesi) < 13:
        return None
    return {"nomi": [f"{ETF[x][2]} ({x})" for x in k], "date": [date.fromisoformat(serie[0][m][0]) for m in mesi],
            "a": [serie[0][m][1] for m in mesi], "b": [serie[1][m][1] for m in mesi]}


def contesto(con, universo: list, ingressi: dict, gialle: dict, percorso, demo: bool) -> dict:
    """Dati per i fogli MOVIMENTI, NOTIZIE, PORTAFOGLIO, SIMULATORE, BACKTEST, STATO."""
    from . import backtest, movimenti, portafoglio
    from .excel_fase4 import leggi_valutati
    mercato = universo[0].indice if demo else "SWDA.MI"
    stat = portafoglio.statistiche(con, universo, mercato)
    for tk, i in ingressi.items():
        i["vol_3a_eur"], i["beta_mercato"] = stat["vol"].get(tk), stat["beta"].get(tk)
    mov = movimenti.calcola_movimenti(con, universo)
    presenti = {f"{m['ticker']}|{m['data']}" for m in mov}
    valutazioni = {k.split("|", 2)[2]: v for k, v in gialle.items() if k.startswith("MOVIMENTI|valutazione|")}
    # i movimenti gia' valutati dall'utente restano nel foglio anche quando escono dalla finestra
    for m in leggi_valutati(percorso):
        valutazioni.setdefault(f"{m['ticker']}|{m['data']}", m["valutazione"])
        if f"{m['ticker']}|{m['data']}" not in presenti:
            mov.append(m)
    tickers = [t.ticker for t in universo]
    segni = ",".join("?" * len(tickers))
    notizie = con.execute(f"SELECT ticker, pubblicato, testata, titolo, url, fonte, lingua FROM notizie WHERE ticker IN ({segni}) "
                          "ORDER BY pubblicato DESC LIMIT 4000", tickers).fetchall()
    return {"movimenti": mov, "valutazioni": valutazioni, "notizie": [tuple(r) for r in notizie], "stat": stat,
            "settori": sorted({t.settore for t in universo}), "aree": sorted({t.area for t in universo}),
            "gialle": gialle, "etf": None if demo else etf_mensili(con), "backtest": backtest.leggi(con),
            "n_sec": con.execute("SELECT COUNT(DISTINCT ticker) FROM bilanci WHERE fonte='sec'").fetchone()[0],
            "n_gdelt": con.execute("SELECT COUNT(*) FROM notizie WHERE fonte='GDELT'").fetchone()[0]}


def genera(con, percorso, oggi: date | None = None, universo: list | None = None,
           demo: bool = False) -> tuple[Libro, dict, dict, dict]:
    """Rigenera il cruscotto dall'archivio conservando le celle gialle del file esistente.
    -> (libro, ingressi, parametri, giudizi)"""
    from . import calcola
    from .parametri import predefiniti
    oggi = oggi or date.today()
    gialle = leggi_gialle(percorso)
    P = parametri_da_gialle(predefiniti(), gialle)
    giudizi = giudizi_da_gialle(gialle)
    ingressi, _, _ = calcola.calcola_tutto(con, oggi, P, giudizi, universo)
    tickers = list(ingressi)
    ctx = contesto(con, universo or UNIVERSO, ingressi, gialle, percorso, demo)
    lib = costruisci(ingressi, P, giudizi, oggi, serie_settimanali(con, tickers),
                     [] if demo else strumenti_di_confronto(con), gialle.get("SCHEDA|ticker"), universo, demo, ctx)
    lib.wb.save(percorso)
    return lib, ingressi, P, giudizi
