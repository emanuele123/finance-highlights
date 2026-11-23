"""Fogli di presentazione del cruscotto: SCREENER, PERFORMANCE, QUALITA_DATI, SCHEDA (con grafico),
PREZZI_5A e CRUSCOTTO. Solo collegamenti e formule: nessun dato calcolato qui."""
from __future__ import annotations
from datetime import date

from openpyxl.styles import Alignment
from openpyxl.worksheet.formula import ArrayFormula
from openpyxl.utils import get_column_letter

from .calcola import ORIZZONTI
from .excel import (BLU, F_DATA, F_INT, F_NUM, F_PCT, F_PUNTI, FASCIA, ND, NERO, R0, VERDE, Libro, Tab, car, testata,
                    titolo_foglio)
from .parametri import METRICHE_A, NOMI_METRICHE

ALLERTE = [("a_fond", "Fondamentali in deterioramento"), ("a_deb", "Debito eccessivo"),
           ("a_vol", "Volatilità o ribasso a un anno elevati"), ("a_dati", "Dati vecchi o da verificare"),
           ("a_liq", "Scambi sotto la soglia")]
# indicatori confrontabili tra tutti i titoli di un settore, anche di modello diverso (mediane nel foglio SETTORI)
CONFRONTABILI = ("pe_ttm", "pe_fwd", "div_yield")

# indicatori principali: chiave, intestazione, formula (nello SCREENER), formato, limite oltre il quale il valore
# e' un segnaposto convenzionale (99 = EBITDA negativo per la leva, 999 = EBITDA negativo per il multiplo)
# escluso dalla mediana di settore
INDICATORI = [
    ("pe_ttm", "P/E sugli utili degli ultimi 12 mesi",
     '=IF(COUNT({prezzo},{D:utile_ttm_ps})=2,IF(AND({D:utile_ttm_ps}>0,{prezzo}>0),{prezzo}/{D:utile_ttm_ps},"n.d."),"n.d.")', "0.0", None),
    ("pe_fwd", "P/E prospettico (utili attesi dal consenso)", "={B:v_V4}", "0.0", None),
    ("div_yield", "Rendimento da dividendo (dividendi degli ultimi 12 mesi / prezzo)",
     '=IF(COUNT({prezzo},{D:div_12m})=2,IF({prezzo}>0,{D:div_12m}/{prezzo},"n.d."),"n.d.")', "0.0%", None),
    ("multiplo", "EV/EBITDA (banche e assicurazioni: prezzo / patrimonio tangibile; 999 = EBITDA negativo)", "={B:v_V3}", "0.0", 999),
    ("rend_cap", "Rendimento sul capitale medio (ROIC; banche e assicurazioni: ROE)", "={B:v_Q1}", "0.0%", None),
    ("margine_op", "Margine operativo medio (banche: cost/income; assicurazioni: combined ratio, da GIUDIZI)", "={B:v_Q3}", "0.0%", None),
    ("leva", "Debito netto / EBITDA (banche e assicurazioni: patrimonio / attivo; 99 = EBITDA negativo)", "={B:v_F1}", "0.00", 99),
    ("crescita", "Crescita annua dei ricavi (banche e assicurazioni: patrimonio per azione più dividendi)", "={B:v_G1}", "0.0%", None),
]
COL_MEDIANE = 7                # prima colonna delle mediane nel foglio SETTORI (G)

NOMI_ORIZZONTI = {"1m": "1 mese", "3m": "3 mesi", "6m": "6 mesi", "1a": "1 anno", "5a": "5 anni", "10a": "10 anni"}


# ============================================================================ SCREENER
def foglio_screener(lib: Libro, tickers: list[str]):
    t = Tab(lib, "SCREENER", "SCREENER - una riga per titolo",
            "Usare i filtri della riga di intestazione. Le due classifiche restano separate. "
            "Completezza e freschezza dei dati non entrano nei punteggi.")
    t.col("ticker", "Ticker", lambda tk: tk, None, "dato", 12)
    t.col("nome", "Società", "={D:nome}", None, "link", 28)
    for k, h, w in (("paese", "Paese del listino", 13), ("area", "Area", 14), ("settore", "Settore", 24),
                    ("modello", "Modello", 8), ("valuta", "Valuta", 7)):
        t.col(k, h, "={D:" + k + "}", None, "link", w)
    t.col("descrizione", "Cosa fa in breve", "={D:descrizione}", None, "link", 60)
    t.col("prezzo", "Prezzo", "={D:prezzo}", F_NUM, "link")
    t.col("cap_eur", "Capitalizzazione (milioni di euro)",
          '=IF(AND(ISNUMBER({D:azioni}),ISNUMBER({prezzo}),ISNUMBER({D:cambio_eur})),'
          '{D:azioni}*{prezzo}/{D:cambio_eur}/1000000,"n.d.")', F_INT, "formula", 13)
    t.col("fascia", "Fascia di capitalizzazione",
          '=IF(ISNUMBER({cap_eur}),IF({cap_eur}*1000000>={P:fasce_cap.0},"Mega",IF({cap_eur}*1000000>={P:fasce_cap.1},"Grande",'
          'IF({cap_eur}*1000000>={P:fasce_cap.2},"Media","Piccola"))),"n.d.")', None, "formula", 11)
    t.col("buffett", "BUFFETT SCORE", "={B:punteggio}", F_PUNTI, "link", 12)
    t.col("classe", "Classe di qualità", "={B:classe}", None, "link", 8)
    t.col("verdetto", "Verdetto", "={B:verdetto}", None, "link", 30)
    t.col("margine", "Margine di sicurezza", "={B:margine}", F_PCT, "link")
    t.col("prezzo_acq", "Prezzo d'acquisto", "={B:prezzo_acq}", F_NUM, "link")
    t.col("valore", "Valore intrinseco base", "={B:valore_base}", F_NUM, "link")
    for k, h, f, fmt, _ in INDICATORI:
        t.col(k, h, f, fmt, "link" if f.startswith("={B:") else "formula", 11)
    # mediana dei titoli confrontabili: stesso settore e stesso tipo (banche e assicurazioni da una parte, il resto dall'altra),
    # perche' per i finanziari alcuni indicatori hanno un significato diverso
    t.col("fin", "Banca o assicurazione (1 = sì)", '=IF(OR({modello}="BAN",{modello}="ASS"),1,0)', "0", "formula", 8)
    t.col("n_pari", "Titoli confrontabili (stesso settore e stesso tipo)",
          "=SUMPRODUCT(({R:settore}={settore})*({R:fin}={fin}))", "0", "formula", 9)
    for k, h, _f, fmt, lim in INDICATORI:
        x = "{R:" + k + "}"
        t.col("med_" + k, "Mediana dei confrontabili: " + h.split(" (")[0],
              f'=IF(SUMPRODUCT(({{R:settore}}={{settore}})*({{R:fin}}={{fin}})*ISNUMBER({x}))=0,"n.d.",'
              f'IFERROR(MEDIAN(IF({{R:settore}}={{settore}},IF({{R:fin}}={{fin}},IF(ISNUMBER({x}),IF({x}<{lim or "1E+99"},{x}))))),"n.d."))',
              fmt, "matrice", 11)
    t.col("trading", "TRADING SCORE", "={T:punteggio}", F_PUNTI, "link", 12)
    t.col("trend", "Trend", "={T:stato_trend}", None, "link", 10)
    t.col("segnale", "Segnale", "={T:segnale}", None, "link", 15)
    t.col("setup", "Setup", "={T:setup}", None, "link", 13)
    t.col("n_rischi", "Segnali di rischio", "={B:n_rischi}", "0", "link", 8)
    t.col("volatilita", "Volatilità annua", "={D:volatilita}", F_PCT, "link")
    t.col("r12m", "Total return a 1 anno", "={D:r12m}", F_PCT, "link")
    t.col("scambi", "Scambi medi giornalieri (euro)", "={D:controvalore_eur}", F_INT, "link", 13)
    t.col("stato", "Esito dei controlli sui dati", "={D:stato_dati}", None, "link", 14)
    t.col("livello", "Livello di rischio",
          '=IF(OR({n_rischi}>={P:rischio_alto_segnali},AND(ISNUMBER({volatilita}),{volatilita}>{P:allerta_volatilita}),'
          'AND(ISNUMBER({r12m}),{r12m}<-{P:allerta_ribasso})),"Alto",IF(OR({n_rischi}>=1,AND(ISNUMBER({volatilita}),'
          '{volatilita}>{P:rischio_medio_volatilita})),"Medio","Basso"))', None, "formula", 9)
    t.col("completezza", "Completezza dei dati (strategia A)", "={B:completezza}", "0%", "link", 11)
    t.col("eta_p", "Età del prezzo (giorni)", "={B:eta_p}", "0", "link", 8)
    t.col("eta_e", "Età dell'ultimo esercizio (giorni)", "={B:eta_e}", "0", "link", 9)
    t.col("a_fond", "Allerta: fondamentali in deterioramento", "=IF(OR({B:r_marg}=1,{B:r_ric}=1),1,0)", "0", "formula", 9)
    t.col("a_deb", "Allerta: debito eccessivo", "=IF({B:r_leva}=1,1,0)", "0", "formula", 8)
    t.col("a_vol", "Allerta: volatilità o ribasso a un anno",
          "=IF(OR(AND(ISNUMBER({volatilita}),{volatilita}>{P:allerta_volatilita}),"
          "AND(ISNUMBER({r12m}),{r12m}<-{P:allerta_ribasso})),1,0)", "0", "formula", 9)
    t.col("a_dati", "Allerta: dati vecchi o da verificare", '=IF(OR({B:vecchio}=1,{stato}<>"OK"),1,0)', "0", "formula", 9)
    t.col("a_liq", "Allerta: scambi sotto la soglia", "=IF(ISNUMBER({scambi}),IF({scambi}<{P:allerta_scambi},1,0),0)",
          "0", "formula", 9)
    t.col("n_allerte", "Numero di allerte", "=SUM({a_fond}:{a_liq})", "0", "formula", 8)
    t.col("allerte_g", "Allerte (concatenate)", "=" + "&".join(f'IF({{{k}}}=1,"{testo}; ","")' for k, testo in ALLERTE),
          None, "formula", 8)
    t.col("allerte", "Rischi e allerte", '=IF(LEN({allerte_g})>2,LEFT({allerte_g},LEN({allerte_g})-2),"-")', None, "formula", 50)
    # chiavi di ordinamento per le liste del CRUSCOTTO (il termine con ROW() scioglie le parita')
    t.col("k_all", "Chiave: allerte", '=IF({n_allerte}>0,{n_allerte}-ROW()/100000,"")', "0.00000", "formula", 8)
    t.col("o_all", "Ordine: allerte", '=IF(ISNUMBER({k_all}),RANK({k_all},{R:k_all}),"")', "0", "formula", 8)
    t.col("k_a", "Chiave: classe A senza margine sufficiente",
          '=IF(AND({classe}="A",{verdetto}="Aspetterei",ISNUMBER({margine})),{margine}-ROW()/1000000000,"")',
          "0.0000", "formula", 8)
    t.col("o_a", "Ordine: classe A senza margine", '=IF(ISNUMBER({k_a}),RANK({k_a},{R:k_a}),"")', "0", "formula", 8)
    t.col("dist", "Distanza dal prezzo d'acquisto",
          '=IF(AND({verdetto}="Aspetterei",ISNUMBER({prezzo_acq}),ISNUMBER({prezzo})),{prezzo}/{prezzo_acq}-1,"")',
          F_PCT, "formula", 10)
    t.col("k_d", "Chiave: vicinanza al prezzo d'acquisto", '=IF(ISNUMBER({dist}),-{dist}-ROW()/1000000000,"")',
          "0.0000", "formula", 8)
    t.col("o_d", "Ordine: vicinanza", '=IF(ISNUMBER({k_d}),RANK({k_d},{R:k_d}),"")', "0", "formula", 8)
    t.scrivi(tickers)
    return t


# ============================================================================ PERFORMANCE, QUALITA_DATI
def foglio_performance(lib: Libro, tickers: list[str]):
    t = Tab(lib, "PERFORMANCE", "PERFORMANCE",
            "Rendimenti a 1, 3, 6 mesi (21, 63, 126 sedute) e a 1, 5, 10 anni (252, 1260, 2520 sedute), non annualizzati. "
            "I rendimenti passati non anticipano quelli futuri.")
    t.col("ticker", "Ticker", lambda tk: tk, None, "dato", 12)
    t.col("nome", "Società", "={D:nome}", None, "link", 28)
    t.col("valuta", "Valuta", "={D:valuta}", None, "link", 7)
    for pref, nome in (("pp", "Prezzo"), ("pt", "Total return"), ("pe", "Total return in euro")):
        for o, _ in ORIZZONTI:
            t.col(f"{pref}_{o}", f"{nome} {NOMI_ORIZZONTI[o]}", "={D:" + f"{pref}_{o}" + "}", F_PCT, "link", 10)
    t.scrivi(tickers)
    return t


def foglio_qualita(lib: Libro, tickers: list[str], strumenti: list[tuple]):
    t = Tab(lib, "QUALITA_DATI", "QUALITÀ DEI DATI",
            "Dopo ogni scarico: prezzi recenti, valuta e nome attesi, salti anomali, età dei bilanci. "
            "'DA VERIFICARE' riporta il motivo.")
    t.col("ticker", "Ticker", lambda tk: tk, None, "dato", 12)
    t.col("nome", "Società", "={D:nome}", None, "link", 28)
    t.col("stato", "Esito dei controlli", "={D:stato_dati}", None, "link", 14)
    t.col("motivo", "Motivo", "={D:motivi_dati}", None, "link", 60)
    t.col("note", "Note di calcolo (scelte dichiarate sui dati della fonte)", "={D:note_calcolo}", None, "link", 70)
    t.col("data_prezzo", "Data ultimo prezzo", "={D:data_prezzo}", F_DATA, "link")
    t.col("eta_p", "Età del prezzo (giorni)", "={B:eta_p}", "0", "link", 9)
    t.col("esercizio", "Chiusura ultimo esercizio", "={D:ultimo_esercizio}", F_DATA, "link")
    t.col("eta_e", "Età dell'ultimo esercizio (giorni)", "={B:eta_e}", "0", "link", 9)
    t.col("n_anni", "Esercizi disponibili", "={D:n_anni}", "0", "link", 9)
    t.col("completezza", "Completezza strategia A", "={B:completezza}", "0%", "link", 11)
    t.col("cop_b", "Copertura strategia B", "={T:cop}", "0%", "link", 11)
    t.scrivi(tickers)
    ws = t.ws
    r = lib.r1 + 2
    ws.cell(r, 1, "Indici di riferimento, ETF di confronto e cambi").font = car(NERO, True)
    r += 1
    for j, h in ((1, "Ticker"), (2, "Nome"), (3, "Esito dei controlli"), (4, "Motivo"), (6, "Data ultimo dato"), (7, "Numero di dati")):
        testata(ws, r, j, h)
    for riga in strumenti:
        r += 1
        for j, v in zip((1, 2, 3, 4, 6, 7), riga):
            c = ws.cell(r, j, v if v not in (None, "") else "-")
            c.font = car(BLU)
            if isinstance(v, date):
                c.number_format = F_DATA
    return t


# ============================================================================ PREZZI_5A e SCHEDA
def foglio_prezzi(lib: Libro, serie: dict) -> int:
    """Chiusure settimanali a 5 anni (rettificate per i frazionamenti): alimentano il grafico della SCHEDA."""
    ws = lib.foglio("PREZZI_5A")
    ws.cell(1, 1, "Data").font = car(NERO, True)
    for j, tk in enumerate(serie["tickers"], 2):
        ws.cell(1, j, tk).font = car(BLU, True)
    for i, d in enumerate(serie["date"]):
        c = ws.cell(2 + i, 1, d)
        c.font, c.number_format = car(BLU), F_DATA
        for j, tk in enumerate(serie["tickers"], 2):
            v = serie["valori"][tk][i]
            ws.cell(2 + i, j, ND if v is None else v).font = car(BLU)
    ws.freeze_panes = "B2"
    ws.column_dimensions["A"].width = 12
    return len(serie["date"])


def foglio_scheda(lib: Libro, tickers: list[str], n_sett: int, scelto: str):
    from openpyxl.chart import LineChart, Reference
    from openpyxl.worksheet.datavalidation import DataValidation
    ws = lib.foglio("SCHEDA")
    titolo_foglio(ws, "SCHEDA DEL TITOLO")
    for col, w in zip("ABCDEFGHIJKLM", (36, 24, 16, 16, 3, 38, 14, 14, 12, 3, 3, 11, 13)):
        ws.column_dimensions[col].width = w
    ws["A2"] = "Titolo (scegliere dal menu)"
    ws["A2"].font = car(NERO, True, 11)
    lib.gialla(ws, "B2", scelto, "SCHEDA|ticker", pred=tickers[0])
    dv = DataValidation(type="list", formula1=f"=UNIVERSO!$A${R0}:$A${lib.r1}", allow_blank=False)
    dv.error, dv.errorTitle = "Scegliere un ticker dall'elenco", "Ticker non valido"
    ws.add_data_validation(dv)
    dv.add("B2")
    ws["C2"] = "Non è consulenza finanziaria: i punteggi ordinano i titoli secondo criteri dichiarati, non sono previsioni."
    ws["C2"].font = car("595959", corsivo=True, dim=9)

    def look(sigla, chiave):
        tab = lib.tab[Tab.SIGLE[sigla]]
        return f"INDEX({tab.rng(chiave)},MATCH($B$2,{tab.rng('ticker')},0))"

    ws["A3"] = '="Cosa fa: "&' + look("D", "descrizione")
    ws["A3"].font = car(VERDE, True)
    ws["A3"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells("A3:I3")
    ws.row_dimensions[3].height = 30

    def sezione(r, col, testo, larg=4):
        for j in range(col, col + larg):
            ws.cell(r, j).fill = FASCIA
        ws.cell(r, col, testo).font = car(NERO, True, 10)

    def riga(r, col, etichetta, formula, fmt=None, grassetto=False):
        ws.cell(r, col, etichetta).font = car()
        c = ws.cell(r, col + 1, "=" + formula)
        c.font = car(VERDE, grassetto)
        c.alignment = Alignment(horizontal="left")
        if fmt:
            c.number_format = fmt

    r = 4
    sezione(r, 1, "Anagrafica")
    for et, f, fmt in (("Società", look("D", "nome"), None), ("Area", look("D", "area"), None),
                       ("Settore", look("D", "settore"), None), ("Modello di valutazione", look("D", "modello"), None),
                       ("Paese del listino", look("D", "paese"), None), ("Valuta di quotazione", look("D", "valuta"), None),
                       ("Valuta di bilancio", look("D", "valuta_bil"), None), ("ADR / note sul titolo", look("D", "adr"), None),
                       ("Prezzo", look("D", "prezzo"), F_NUM), ("Data del prezzo", look("D", "data_prezzo"), F_DATA),
                       ("Capitalizzazione (milioni di euro)", look("S", "cap_eur"), F_INT),
                       ("Fascia di capitalizzazione", look("S", "fascia"), None),
                       ("Esito dei controlli sui dati", look("D", "stato_dati"), None), ("Motivo", look("D", "motivi_dati"), None)):
        r += 1
        riga(r, 1, et, f, fmt)
    r += 2
    sezione(r, 1, "Indicatori principali (a confronto con i titoli dello stesso settore e dello stesso tipo)")
    ws.cell(r, 3, "Mediana dei confrontabili").font = car(NERO, True, 9)
    c = ws.cell(r, 4, '=' + look("S", "n_pari") + '&" titoli"')
    c.font = car(VERDE, dim=9)
    for k, h, _f, fmt, _lim in INDICATORI:
        r += 1
        riga(r, 1, h, look("S", k), fmt)
        ws.cell(r, 2).alignment = Alignment(horizontal="right")
        c = ws.cell(r, 3, "=" + look("S", "med_" + k))
        c.font, c.number_format = car(VERDE), fmt
        c.alignment = Alignment(horizontal="right")
    r += 1
    _n = ws.cell(r, 1, "Un indicatore da solo inganna: un P/E basso può voler dire 'a buon mercato' oppure 'il mercato si aspetta "
                       "utili in calo'. I punteggi ne combinano diciannove.")
    _n.font = car("595959", corsivo=True, dim=9)
    r += 1
    sezione(r, 1, "Strategia A - Buffett Score (qualità e valore)")
    for et, f, fmt, g in (("BUFFETT SCORE", look("B", "punteggio"), F_PUNTI, True), ("Classe di qualità", look("B", "classe"), None, True),
                          ("Verdetto", look("B", "verdetto"), None, True), ("Qualità composita", look("B", "qc"), F_PUNTI, False),
                          ("Pilastro Qualità del business", look("B", "pil_Q"), F_PUNTI, False),
                          ("Pilastro Solidità finanziaria", look("B", "pil_F"), F_PUNTI, False),
                          ("Pilastro Crescita e allocazione del capitale", look("B", "pil_G"), F_PUNTI, False),
                          ("Pilastro Valutazione al prezzo corrente", look("B", "pil_V"), F_PUNTI, False),
                          ("Valutazione usata nel punteggio", look("B", "v_usata"), F_PUNTI, False),
                          ("Correzione qualitativa (GIUDIZI)", look("B", "corr"), F_PUNTI, False),
                          ("Completezza dei dati", look("B", "completezza"), "0%", False)):
        r += 1
        riga(r, 1, et, f, fmt, g)
    r += 2
    sezione(r, 1, "Valore intrinseco per azione (ipotesi dichiarate)")
    for et, f, fmt in (("Scenario prudente", look("V", "valore_p"), F_NUM), ("Scenario base", look("V", "valore_b"), F_NUM),
                       ("Scenario ottimistico", look("V", "valore_o"), F_NUM),
                       ("Margine di sicurezza (scenario base)", look("B", "margine"), F_PCT),
                       ("Margine richiesto dalla classe", look("B", "richiesto"), "0%"),
                       ("Prezzo d'acquisto", look("B", "prezzo_acq"), F_NUM),
                       ("Rendimento richiesto (base)", look("V", "r_b"), F_PCT),
                       ("Crescita di fase 1 (base)", look("V", "g1_b"), F_PCT),
                       ("Crescita terminale (base)", look("V", "gT_b"), F_PCT)):
        r += 1
        riga(r, 1, et, f, fmt)
    r += 2
    sezione(r, 1, "Rischi")
    for et, f, fmt in (("Segnali ricavati dai dati", look("B", "rischi"), None), ("Allerte", look("S", "allerte"), None),
                       ("Livello di rischio", look("S", "livello"), None), ("Volatilità annua", look("D", "volatilita"), F_PCT),
                       ("Promemoria generico del settore",
                        f'IFERROR(INDEX({lib.prm["settori_testo"]},MATCH({look("D", "settore")},{lib.prm["settori_nome"]},0)),"-")', None),
                       ("Tesi personale (da GIUDIZI)", f'IF({look("G", "tesi")}="","-",{look("G", "tesi")})', None)):
        r += 1
        riga(r, 1, et, f, fmt)
    fine_sx = r

    r = 4
    sezione(r, 6, "Strategia B - Trading Score (tendenza e forza)")
    for et, f, fmt, g in (("TRADING SCORE", look("T", "punteggio"), F_PUNTI, True), ("Segnale", look("T", "segnale"), None, True),
                          ("Stato del trend", look("T", "stato_trend"), None, False), ("Trend", look("T", "trend"), F_PUNTI, False),
                          ("Momentum", look("T", "mom"), F_PUNTI, False), ("Forza relativa", look("T", "forza"), F_PUNTI, False),
                          ("Oscillatori", look("T", "osc"), F_PUNTI, False), ("Volumi", look("T", "vol"), F_PUNTI, False),
                          ("Assetto e rischio", look("T", "ass"), F_PUNTI, False), ("Catalizzatori", look("T", "cat"), F_PUNTI, False),
                          ("RSI a 14 sedute", look("T", "rsi"), "0.0", False)):
        r += 1
        riga(r, 6, et, f, fmt, g)
    r += 2
    sezione(r, 6, "Setup operativo (proiezione convenzionale, non previsione)")
    for et, f, fmt in (("Setup individuato", look("T", "setup"), None), ("Setup valido", look("T", "op_setup"), None),
                       ("Ingresso", look("T", "op_in"), F_NUM), ("Stop", look("T", "op_stop"), F_NUM),
                       ("Obiettivo", look("T", "op_ob"), F_NUM), ("Rendimento/rischio del setup individuato", look("T", "s_rr"), "0.00"),
                       ("Numero di azioni (capitale di esempio)", look("T", "n_azioni"), "0"),
                       ("Trimestrale imminente (1 = avviso di rischio)", look("T", "avviso"), "0"),
                       ("Giorni alla prossima trimestrale", look("T", "gg_a"), "0")):
        r += 1
        riga(r, 6, et, f, fmt)
    r += 2
    sezione(r, 6, "Performance")
    r += 1
    for j, h in enumerate(("Periodo", "Prezzo", "Total return", "TR in euro")):
        ws.cell(r, 6 + j, h).font = car(NERO, True)
    for o, _ in ORIZZONTI:
        r += 1
        ws.cell(r, 6, NOMI_ORIZZONTI[o]).font = car()
        for j, pref in enumerate(("pp", "pt", "pe")):
            c = ws.cell(r, 7 + j, "=" + look("D", f"{pref}_{o}"))
            c.font, c.number_format = car(VERDE), F_PCT
            c.alignment = Alignment(horizontal="right")
    fine_dx = r

    r = max(fine_sx, fine_dx) + 2
    sezione(r, 1, "Le 19 metriche del Buffett Score", 9)
    r += 1
    for j, h in zip((1, 2, 3, 4), ("Metrica", "Valore", "Punti (0-100)", "Peso nel pilastro")):
        ws.cell(r, j, h).font = car(NERO, True)
    for m in METRICHE_A:
        r += 1
        ws.cell(r, 1, f"{m} - {NOMI_METRICHE[m]}").font = car()
        for j, pref, fmt in ((2, "v_", "0.000"), (3, "p_", F_PUNTI), (4, "w_", "0")):
            c = ws.cell(r, j, "=" + look("B", pref + m))
            c.font, c.number_format = car(VERDE), fmt
            c.alignment = Alignment(horizontal="right")
    r += 2
    sezione(r, 1, "Come funziona il mercato di questo settore (descrizione generale, non un giudizio sul titolo)", 9)
    r += 1
    c = ws.cell(r, 1, f'=IFERROR(INDEX({lib.prm["settori_mercato"]},MATCH({look("D", "settore")},{lib.prm["settori_nome"]},0)),"-")')
    c.font = car(VERDE)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
    ws.row_dimensions[r].height = 78
    fine = r

    # serie per il grafico (colonne L:M) e grafico a 5 anni
    ws["L3"], ws["M3"] = "Data", "Chiusura settimanale"
    ws["L3"].font = ws["M3"].font = car(NERO, True, 9)
    ult = get_column_letter(1 + len(tickers))
    for i in range(n_sett):
        rr = 4 + i
        a = ws.cell(rr, 12, f"=PREZZI_5A!$A${2 + i}")
        a.font, a.number_format = car(VERDE, dim=8), "mm/yyyy"
        b = ws.cell(rr, 13, f"=INDEX(PREZZI_5A!$B${2 + i}:${ult}${2 + i},1,MATCH($B$2,PREZZI_5A!$B$1:${ult}$1,0))")
        b.font, b.number_format = car(VERDE, dim=8), F_NUM
    if n_sett > 1:
        ch = LineChart()
        ch.title = "Prezzo a 5 anni (chiusure settimanali, rettificate per i frazionamenti)"
        ch.height, ch.width = 9.5, 26
        ch.add_data(Reference(ws, min_col=13, min_row=3, max_row=3 + n_sett), titles_from_data=True)
        ch.set_categories(Reference(ws, min_col=12, min_row=4, max_row=3 + n_sett))
        ch.legend = None
        ch.roundedCorners = False
        ch.title.overlay = False
        ch.x_axis.delete = False
        ch.y_axis.delete = False
        ch.x_axis.number_format = "mm/yyyy"
        ch.x_axis.tickLblSkip = 26
        ch.x_axis.tickMarkSkip = 26
        ch.series[0].graphicalProperties.line.width = 15000
        ch.series[0].graphicalProperties.line.solidFill = "1F3864"
        ch.series[0].smooth = False
        ws.add_chart(ch, f"A{fine + 2}")
    ws.freeze_panes = "A4"


# ============================================================================ CRUSCOTTO
def foglio_cruscotto(lib: Libro, demo: bool = False):
    ws = lib.foglio("CRUSCOTTO")
    for col, w in zip("ABCDEFGHIJKL", (4, 12, 30, 13, 13, 14, 14, 26, 30, 26, 26, 26)):
        ws.column_dimensions[col].width = w
    ws["B1"] = "GLOBAL STOCK INTELLIGENCE" + (" - VERSIONE DIMOSTRATIVA: SOCIETÀ E DATI INVENTATI" if demo else "")
    ws["B1"].font = car("1F3864", True, 16)
    ws["B2"] = "Dati aggiornati al"
    ws["B2"].font = car(NERO, True)
    ws["C2"] = "=" + lib.prm["data_rif"]
    ws["C2"].font, ws["C2"].number_format = car(VERDE, True), F_DATA
    ws["C2"].alignment = Alignment(horizontal="left")
    ws["D2"] = ("Strumento personale, non è consulenza finanziaria. I punteggi ordinano i titoli secondo criteri dichiarati: "
                "non sono previsioni. Due strategie, due classifiche, mai fuse.")
    ws["D2"].font = car("595959", corsivo=True, dim=9)
    S, B, T = lib.tab["SCREENER"], lib.tab["BUFFETT"], lib.tab["TRADING"]
    profilo = [("P/E prospettico", S, "pe_fwd", "0.0"), ("Rendimento da dividendo", S, "div_yield", "0.0%"),
               ("Settore", lib.tab["DATI"], "settore", None), ("Cosa fa in breve", lib.tab["DATI"], "descrizione", None)]
    for col, w in (("M", 26), ("N", 26), ("O", 28), ("P", 60)):
        ws.column_dimensions[col].width = w

    def fascia(r, testo):
        for j in range(2, 17):
            ws.cell(r, j).fill = FASCIA
        ws.cell(r, 2, testo).font = car(NERO, True, 11)

    fascia(4, "Indicatori di sintesi")
    ind = [("Titoli nell'universo", f"=COUNTA({S.rng('ticker')})"),
           ("Con Buffett Score", f"=COUNT({S.rng('buffett')})"),
           ("Verdetto 'Comprerei'", f'=COUNTIF({S.rng("verdetto")},"Comprerei")'),
           ("Verdetto 'Aspetterei'", f'=COUNTIF({S.rng("verdetto")},"Aspetterei")'),
           ("Verdetto 'Non comprerei'", f'=COUNTIF({S.rng("verdetto")},"Non comprerei*")'),
           ("Classe di qualità A", f'=COUNTIF({S.rng("classe")},"A")'),
           ("Con Trading Score", f"=COUNT({S.rng('trading')})"),
           ("Segnale 'Setup attivo'", f'=COUNTIF({S.rng("segnale")},"Setup attivo")'),
           ("Segnale 'In osservazione'", f'=COUNTIF({S.rng("segnale")},"In osservazione")'),
           ("Segnale 'Evitare'", f'=COUNTIF({S.rng("segnale")},"Evitare")'),
           ("Titoli con almeno un'allerta", f'=COUNTIF({S.rng("n_allerte")},">0")'),
           ("Dati 'DA VERIFICARE' o in errore", f'=COUNTIF({S.rng("stato")},"<>OK")')]
    for i, (et, f) in enumerate(ind):
        r, col = 5 + i % 6, 2 + 5 * (i // 6)
        ws.cell(r, col, et).font = car()
        c = ws.cell(r, col + 2, f)
        c.font, c.number_format = car(VERDE, True), "0"

    def lista(r, titolo_, n, tab_ord, col_ord, colonne):
        """colonne: [(intestazione, foglio, chiave, formato)] dopo '#' e 'Ticker'."""
        fascia(r, titolo_)
        r += 1
        ws.cell(r, 1, "#").font = car(NERO, True, 9)
        colonne = colonne + profilo
        for j, h in enumerate(["Ticker"] + [c[0] for c in colonne]):
            testata(ws, r, 2 + j, h)
        ws.row_dimensions[r].height = 30
        for k in range(1, n + 1):
            rr = r + k
            ws.cell(rr, 1, k).font = car("7F7F7F", dim=9)
            c = ws.cell(rr, 2, f'=IFERROR(INDEX({tab_ord.rng("ticker")},MATCH({k},{tab_ord.rng(col_ord)},0)),"")')
            c.font = car(VERDE, True)
            for j, (_h, tab, chiave, fmt) in enumerate(colonne):
                c = ws.cell(rr, 3 + j, f'=IF($B{rr}="","",INDEX({tab.rng(chiave)},MATCH($B{rr},{tab.rng("ticker")},0)))')
                c.font = car(VERDE)
                if fmt:
                    c.number_format = fmt
                c.alignment = Alignment(horizontal="right" if fmt else "left", indent=0 if fmt else 1)
        return r + n + 2

    r = 12
    r = lista(r, "1. I 10 migliori di valore (Buffett Score)", 10, B, "ordine",
              [("Società", B, "nome", None), ("Buffett Score", B, "punteggio", F_PUNTI), ("Classe", B, "classe", None),
               ("Margine di sicurezza", B, "margine", F_PCT), ("Prezzo", B, "prezzo", F_NUM),
               ("Prezzo d'acquisto", B, "prezzo_acq", F_NUM), ("Verdetto", B, "verdetto", None)])
    r = lista(r, "2. I 10 migliori di trading (Trading Score) - ingresso, stop e obiettivo solo se il setup è valido", 10, T, "ordine",
              [("Società", T, "nome", None), ("Trading Score", T, "punteggio", F_PUNTI), ("Segnale", T, "segnale", None),
               ("Ingresso", T, "op_in", F_NUM), ("Stop", T, "op_stop", F_NUM), ("Obiettivo", T, "op_ob", F_NUM),
               ("Setup valido", T, "op_setup", None), ("Stato del trend", T, "stato_trend", None),
               ("Trimestrale imminente (1 = sì)", T, "avviso", "0")])
    r = lista(r, "3. Aziende di classe A senza margine di sicurezza sufficiente (dal margine più alto)", 10, S, "o_a",
              [("Società", S, "nome", None), ("Buffett Score", S, "buffett", F_PUNTI), ("Margine di sicurezza", S, "margine", F_PCT),
               ("Prezzo", S, "prezzo", F_NUM), ("Prezzo d'acquisto", S, "prezzo_acq", F_NUM), ("Valore base", S, "valore", F_NUM)])
    r = lista(r, "4. 'Aspetterei' più vicini al prezzo d'acquisto", 10, S, "o_d",
              [("Società", S, "nome", None), ("Classe", S, "classe", None), ("Distanza dal prezzo d'acquisto", S, "dist", F_PCT),
               ("Prezzo", S, "prezzo", F_NUM), ("Prezzo d'acquisto", S, "prezzo_acq", F_NUM), ("Buffett Score", S, "buffett", F_PUNTI)])
    lista(r, "5. Rischi e allerte (dal numero di allerte più alto)", 15, S, "o_all",
          [("Società", S, "nome", None), ("Numero di allerte", S, "n_allerte", "0"), ("Livello di rischio", S, "livello", None),
           ("Rischi e allerte", S, "allerte", None)])
    ws.freeze_panes = "A4"
    ws.sheet_view.showGridLines = False


# ============================================================================ SETTORI
def foglio_settori(lib: Libro, settori: list[str]):
    ws = lib.foglio("SETTORI")
    titolo_foglio(ws, "SETTORI - come funziona ogni mercato",
                  "Descrizioni generali scritte a mano, non provenienti dalle fonti dati e non riferite a un singolo titolo. "
                  "I testi si modificano nel foglio PARAMETRI. Altri indicatori (multipli, rendimento sul capitale, leva) "
                  "hanno un significato diverso per banche e assicurazioni: il confronto è nella SCHEDA, tra titoli dello stesso tipo.")
    S = lib.tab["SCREENER"]
    for j, (h, w) in enumerate((("Settore", 28), ("Titoli nell'universo", 10), ("Come funziona il mercato", 95),
                                ("Rischi tipici", 60), ("Buffett Score medio", 11), ("Trading Score medio", 11)), 1):
        testata(ws, 2, j, h, w)
    ws.row_dimensions[2].height = 66
    for j, (k, h, _f, fmt, _lim) in enumerate(i for i in INDICATORI if i[0] in CONFRONTABILI):
        testata(ws, 2, COL_MEDIANE + j, "Mediana di tutti i titoli del settore: " + h, 14)
    for i, sett in enumerate(settori):
        r = R0 + i
        ws.cell(r, 1, sett).font = car(NERO, True)
        ws.cell(r, 2, f"=COUNTIF({S.rng('settore')},$A{r})").font = car()
        for j, k in ((3, "settori_mercato"), (4, "settori_testo")):
            c = ws.cell(r, j, f'=IFERROR(INDEX({lib.prm[k]},MATCH($A{r},{lib.prm["settori_nome"]},0)),"-")')
            c.font = car(VERDE)
        for j, k in ((5, "buffett"), (6, "trading")):
            c = ws.cell(r, j, f'=IF(COUNTIFS({S.rng("settore")},$A{r},{S.rng(k)},">=0")>0,'
                              f'AVERAGEIF({S.rng("settore")},$A{r},{S.rng(k)}),"n.d.")')
            c.font, c.number_format = car(), F_PUNTI
        for j, (k, _h, _f, fmt, lim) in enumerate(i for i in INDICATORI if i[0] in CONFRONTABILI):
            col = COL_MEDIANE + j
            x = S.rng(k)
            cond = f"IF({S.rng('settore')}=$A{r},IF(ISNUMBER({x}),IF({x}<{lim or '1E+99'},{x})))"
            cella = f"{get_column_letter(col)}{r}"
            ws[cella] = ArrayFormula(cella, f'=IF(SUMPRODUCT(({S.rng("settore")}=$A{r})*ISNUMBER({x}))=0,"n.d.",'
                                            f'IFERROR(MEDIAN({cond}),"n.d."))')
            ws[cella].font, ws[cella].number_format = car(), fmt
        for j in range(1, COL_MEDIANE + len(CONFRONTABILI)):
            ws.cell(r, j).alignment = Alignment(wrap_text=True, vertical="top", horizontal="left" if j in (1, 3, 4) else "right")
        ws.row_dimensions[r].height = 92
    ws.freeze_panes = "B3"
