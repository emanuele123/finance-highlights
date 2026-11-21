"""Fogli MOVIMENTI, NOTIZIE, PORTAFOGLIO (con CORRELAZIONI), SIMULATORE (con ETF_MENSILI) e BACKTEST."""
from __future__ import annotations
from datetime import date

from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import simulatore
from .excel import BLU, F_DATA, F_INT, F_NUM, F_PCT, FASCIA, ND, NERO, R0, VERDE, Libro, car, testata, titolo_foglio
from .movimenti import LIVELLI, MAX_NOTIZIE

GRIGIO = "595959"
N_POS = 30                     # righe del portafoglio
P0 = 16                        # prima riga delle posizioni


def _nota(ws, cella, testo):
    ws[cella] = testo
    ws[cella].font = car(GRIGIO, corsivo=True, dim=9)


def _dato(ws, r, c, v, fmt=None, colore=BLU, grassetto=False):
    x = ws.cell(r, c, ND if v is None else v)
    x.font = car(colore, grassetto)
    if fmt:
        x.number_format = fmt
    if v is None or fmt:
        x.alignment = Alignment(horizontal="right")
    return x


# ============================================================================ MOVIMENTI e NOTIZIE
def foglio_movimenti(lib: Libro, movimenti: list[dict], valutazioni: dict):
    ws = lib.foglio("MOVIMENTI")
    titolo_foglio(ws, "MOVIMENTI - perché sale o scende",
                  "Variazioni giornaliere (total return) di almeno il 4% o anomale oltre 2 deviazioni standard, ultime 42 sedute. "
                  "FATTI nelle colonne blu, IPOTESI etichettate, OPINIONE dell'utente nella colonna gialla. "
                  "Una coincidenza temporale non è una causa.")
    col = [("id", "Chiave", 6), ("ticker", "Ticker", 11), ("nome", "Società", 24), ("data", "Data", 11),
           ("variazione", "FATTO: variazione del titolo", 10), ("tipo", "FATTO: tipo di variazione", 16),
           ("sigma", "Deviazione standard giornaliera (252 sedute)", 10), ("beta", "Beta sull'indice (252 sedute)", 8),
           ("indice", "FATTO: variazione dell'indice", 10), ("mercato", "Parte attesa dal mercato (beta x indice)", 11),
           ("settore", "Parte del settore (mediana dei residui dei titoli del settore)", 11),
           ("specifica", "Parte specifica del titolo", 11), ("eventi", "FATTO: eventi societari documentati", 34),
           ("n_notizie", "Titoli di stampa nella finestra", 8)]
    for k in range(1, MAX_NOTIZIE + 1):
        col += [(f"t{k}", f"Titolo {k} (non verificato né riassunto)", 44), (f"s{k}", f"Testata {k}", 14), (f"l{k}", f"Link {k}", 9)]
    col += [("livello", "Livello di evidenza", 30), ("lettura", "IPOTESI: lettura possibile", 52),
            ("valutazione", "OPINIONE dell'utente: impatto sulla tesi di lungo periodo", 44)]
    L = {k: get_column_letter(j) for j, (k, _, _) in enumerate(col, 1)}
    ws.row_dimensions[2].height = 54
    for j, (_, h, w) in enumerate(col, 1):
        testata(ws, 2, j, h, w)
    for i, m in enumerate(movimenti):
        r = R0 + i
        ident = f"{m['ticker']}|{m['data']}"
        _dato(ws, r, 1, ident).font = car("BFBFBF", dim=7)
        _dato(ws, r, 2, m["ticker"])
        _dato(ws, r, 3, m["nome"])
        _dato(ws, r, 4, date.fromisoformat(m["data"]), F_DATA)
        _dato(ws, r, 5, m["variazione"], F_PCT, grassetto=True)
        _dato(ws, r, 6, m["tipo"] + (" (archiviato)" if m.get("archiviato") else ""))
        _dato(ws, r, 7, m["sigma"], "0.00%")
        _dato(ws, r, 8, m["beta"], "0.00")
        _dato(ws, r, 9, m["indice"], F_PCT)
        c = ws.cell(r, 10, f'=IF(AND(ISNUMBER({L["beta"]}{r}),ISNUMBER({L["indice"]}{r})),{L["beta"]}{r}*{L["indice"]}{r},"n.d.")')
        c.font, c.number_format = car(), F_PCT
        _dato(ws, r, 11, m["settore"], F_PCT)
        c = ws.cell(r, 12, f'={L["variazione"]}{r}-IF(ISNUMBER({L["mercato"]}{r}),{L["mercato"]}{r},0)'
                           f'-IF(ISNUMBER({L["settore"]}{r}),{L["settore"]}{r},0)')
        c.font, c.number_format = car(), F_PCT
        _dato(ws, r, 13, "; ".join(m["eventi"]) or "Nessun evento documentato nella finestra")
        _dato(ws, r, 14, m["n_notizie"], "0")
        for k in range(MAX_NOTIZIE):
            j = 15 + 3 * k
            if k < len(m["notizie"]):
                titolo, testata_, url, _fonte = m["notizie"][k]
                _dato(ws, r, j, titolo)
                _dato(ws, r, j + 1, testata_ or "-")
                if url:
                    x = ws.cell(r, j + 2, "apri")
                    x.hyperlink, x.font = url, car(BLU)
        _dato(ws, r, 15 + 3 * MAX_NOTIZIE, LIVELLI[m["livello"]])
        _dato(ws, r, 16 + 3 * MAX_NOTIZIE, m["lettura"], colore=NERO).font = car(NERO, corsivo=True)
        lib.gialla(ws, f"{L['valutazione']}{r}", valutazioni.get(ident), f"MOVIMENTI|valutazione|{ident}", ticker=ident)
    if not movimenti:
        ws["B3"] = "Nessuna variazione rilevante nelle ultime 42 sedute."
        ws["B3"].font = car()
    ws.freeze_panes = "E3"
    ws.auto_filter.ref = f"A2:{get_column_letter(len(col))}{max(R0, R0 + len(movimenti) - 1)}"


def leggi_valutati(percorso) -> list[dict]:
    """Movimenti del cruscotto esistente per i quali l'utente ha scritto una valutazione: vengono
    riportati nel nuovo file (marcati 'archiviato') anche quando escono dalla finestra osservata."""
    from openpyxl import load_workbook
    try:
        wb = load_workbook(percorso)
    except Exception:  # noqa: BLE001
        return []
    if "MOVIMENTI" not in wb.sheetnames:
        return []
    ws = wb["MOVIMENTI"]
    col_val = 17 + 3 * MAX_NOTIZIE
    num = lambda v: v if isinstance(v, (int, float)) else None  # noqa: E731
    out = []
    for r in range(R0, ws.max_row + 1):
        ident, val = ws.cell(r, 1).value, ws.cell(r, col_val).value
        if not ident or "|" not in str(ident) or val in (None, ""):
            continue
        tk, giorno = str(ident).split("|", 1)
        notizie = []
        for k in range(MAX_NOTIZIE):
            j = 15 + 3 * k
            if ws.cell(r, j).value:
                link = ws.cell(r, j + 2).hyperlink
                notizie.append((ws.cell(r, j).value, ws.cell(r, j + 1).value, link.target if link else None, None))
        liv = str(ws.cell(r, 15 + 3 * MAX_NOTIZIE).value or "D")[:1]
        eventi = ws.cell(r, 13).value or ""
        out.append({"ticker": tk, "nome": ws.cell(r, 3).value, "data": giorno, "variazione": num(ws.cell(r, 5).value),
                    "tipo": str(ws.cell(r, 6).value or "").replace(" (archiviato)", ""), "sigma": num(ws.cell(r, 7).value),
                    "beta": num(ws.cell(r, 8).value), "indice": num(ws.cell(r, 9).value), "settore": num(ws.cell(r, 11).value),
                    "eventi": [] if eventi.startswith("Nessun evento") else eventi.split("; "), "notizie": notizie,
                    "n_notizie": num(ws.cell(r, 14).value) or 0, "livello": liv if liv in LIVELLI else "D",
                    "lettura": ws.cell(r, 16 + 3 * MAX_NOTIZIE).value or "", "archiviato": True,
                    "valutazione": val})
    return out


def foglio_notizie(lib: Libro, notizie: list[tuple]):
    ws = lib.foglio("NOTIZIE")
    titolo_foglio(ws, "NOTIZIE - archivio dei titoli raccolti",
                  "Solo titolo, testata e link: il contenuto non è verificato né riassunto. Fonti: Yahoo Finance e GDELT.")
    for j, (h, w) in enumerate((("Ticker", 12), ("Pubblicato", 12), ("Testata", 22), ("Titolo", 100), ("Link", 8),
                                ("Raccolto da", 11), ("Lingua", 10)), 1):
        testata(ws, 2, j, h, w)
    for i, (tk, pub, testata_, titolo, url, fonte, lingua) in enumerate(notizie):
        r = R0 + i
        _dato(ws, r, 1, tk)
        try:
            _dato(ws, r, 2, date.fromisoformat((pub or "")[:10]), F_DATA)
        except ValueError:
            _dato(ws, r, 2, None)
        _dato(ws, r, 3, testata_ or "-")
        _dato(ws, r, 4, titolo)
        x = ws.cell(r, 5, "apri")
        x.hyperlink, x.font = url, car(BLU)
        _dato(ws, r, 6, {"yahoo": "Yahoo"}.get(fonte, fonte))
        _dato(ws, r, 7, lingua or "-")
    ws.freeze_panes = "A3"
    ws.auto_filter.ref = f"A2:G{max(R0, R0 + len(notizie) - 1)}"


# ============================================================================ PORTAFOGLIO
def foglio_correlazioni(lib: Libro, st: dict):
    ws = lib.foglio("CORRELAZIONI")
    ws["A1"] = "Correlazioni dei rendimenti settimanali in euro (3 anni)"
    ws["A1"].font = car(NERO, True, 8)
    for j, tk in enumerate(st["tickers"], 2):
        ws.cell(1, j, tk).font = car(BLU, True, 8)
        ws.cell(j, 1, tk).font = car(BLU, True, 8)
    for i, riga in enumerate(st["corr"]):
        for j, v in enumerate(riga):
            c = ws.cell(2 + i, 2 + j, ND if v is None else round(v, 4))
            c.font, c.number_format = car(BLU, dim=8), "0.00"
    ws.freeze_panes = "B2"


def foglio_portafoglio(lib: Libro, settori: list[str], aree: list[str], gialle: dict):
    ws = lib.foglio("PORTAFOGLIO")
    titolo_foglio(ws, "PORTAFOGLIO",
                  "Inserire le posizioni nelle celle gialle (ticker dal menu, quantità, prezzo medio di carico nella valuta "
                  "di quotazione). Esempio: ENEL.MI | 500 | 6,20. La verifica dei limiti è separata dal giudizio sul titolo.")
    for col, w in zip("ABCDEFGHIJKLMNOPQRSTUVW", (13, 13, 13, 26, 24, 15, 8, 11, 10, 14, 9, 16, 11, 8, 10, 13, 10, 13, 26, 15, 9, 9, 3)):
        ws.column_dimensions[col].width = w
    D, n = lib.tab["DATI"], lib.r1 - R0 + 1
    g = lambda k, pred: gialle.get("PORT|" + k, pred)  # noqa: E731
    PZ = f"$A${P0}:$A${P0 + N_POS - 1}"
    JZ = f"$J${P0}:$J${P0 + N_POS - 1}"
    TOT = "$F$4"

    def et(cella, testo, grassetto=False):
        ws[cella] = testo
        ws[cella].font = car(NERO, grassetto)

    def form(cella, f, fmt=None, grassetto=False, colore=NERO):
        ws[cella] = f
        ws[cella].font = car(colore, grassetto)
        if fmt:
            ws[cella].number_format = fmt
        ws[cella].alignment = Alignment(horizontal="right")

    # --- ingressi
    for r, (k, testo, pred, fmt) in enumerate((
            ("liquidita", "Liquidità (euro)", 0, F_INT), ("lim_titolo", "Limite per singolo titolo", 0.10, "0%"),
            ("lim_settore", "Limite per settore", 0.30, "0%"), ("lim_area", "Limite per area", 0.50, "0%"),
            ("lim_valuta", "Limite per valute diverse dall'euro", 0.40, "0%"),
            ("shock_mercato", "Stress: variazione del mercato", -0.30, "0%"),
            ("shock_valute", "Stress: variazione delle valute estere", -0.10, "0%"),
            ("quota_volumi", "Liquidazione: quota degli scambi giornalieri utilizzabile", 0.20, "0%")), 4):
        et(f"A{r}", testo)
        ws.merge_cells(f"A{r}:B{r}")
        lib.gialla(ws, f"C{r}", g(k, pred), "PORT|" + k, fmt, pred=pred)
    LIQ, LT, LS, LA, LV, SM, SV, QV = (f"$C${r}" for r in range(4, 12))

    # --- sintesi
    et("D3", "Sintesi del portafoglio", True)
    et("D4", "Patrimonio totale (euro)")
    form("F4", f"=SUM({JZ})+IF(ISNUMBER({LIQ}),{LIQ},0)", F_INT, True)
    et("D5", "Investito in titoli (euro)")
    form("F5", f"=SUM({JZ})", F_INT)
    et("D6", "Volatilità annua stimata del patrimonio")
    form("F6", f'=IF({TOT}>0,SQRT(MAX(0,SUM($AB${P0}:${get_column_letter(27 + N_POS)}${P0 + N_POS - 1}))),"n.d.")', "0.0%", True)
    et("D7", "Perdita nello scenario di stress (euro)")
    form("F7", f"=SUM($P${P0}:$P${P0 + N_POS - 1})", F_INT, True)
    et("D8", "Perdita nello scenario di stress (% del patrimonio)")
    form("F8", f'=IF({TOT}>0,F7/{TOT},"n.d.")', "0.0%")
    et("D9", "Giorni per liquidare la posizione più lenta")
    form("F9", f'=IF(COUNT($Q${P0}:$Q${P0 + N_POS - 1})>0,MAX($Q${P0}:$Q${P0 + N_POS - 1}),"n.d.")', "0.0")
    et("D10", "Peso delle valute diverse dall'euro")
    form("F10", f'=IF({TOT}>0,SUMIF($G${P0}:$G${P0 + N_POS - 1},"<>EUR",{JZ})/{TOT},"n.d.")', "0.0%")
    et("D11", "Esito dei limiti del portafoglio")
    form("F11", f'=IF({TOT}>0,IF(AND(COUNTIF($L${P0}:$L${P0 + N_POS - 1},"Oltre il limite")=0,'
                f'COUNTIF($D${P0 + N_POS + 4}:$D${P0 + N_POS + 3 + len(settori)},"Oltre il limite")=0,'
                f'COUNTIF($I${P0 + N_POS + 4}:$I${P0 + N_POS + 3 + len(aree)},"Oltre il limite")=0,F10<={LV}),'
                f'"Entro i limiti","Oltre almeno un limite"),"n.d.")', None, True)
    ws["F11"].alignment = Alignment(horizontal="left")
    _nota(ws, "D12", "Volatilità: correlazioni dei rendimenti settimanali in euro a 3 anni; la liquidità non ha volatilità. "
                     "Stress: beta x variazione del mercato, più la variazione delle valute per i titoli non in euro (beta mancante = 1).")

    # --- verifica di una nuova operazione
    et("H3", "Verifica di una nuova operazione (esito separato dal giudizio sul titolo)", True)
    et("H4", "Ticker")
    lib.gialla(ws, "K4", g("op_ticker", None), "PORT|op_ticker")
    et("H5", "Importo in euro (acquisto +, vendita -)")
    lib.gialla(ws, "K5", g("op_importo", None), "PORT|op_importo", F_INT)
    dv = DataValidation(type="list", formula1=f"=UNIVERSO!$A${R0}:$A${lib.r1}", allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("K4")
    dv.add(f"A{P0}:A{P0 + N_POS - 1}")
    look = lambda k, cella: f"INDEX({D.rng(k)},MATCH({cella},{D.rng('ticker')},0))"  # noqa: E731
    ok = 'AND($K$4<>"",ISNUMBER($K$5),' + TOT + ">0)"
    righe = [("H6", "Peso del titolo dopo l'operazione", f'=IF({ok},(SUMIF({PZ},$K$4,{JZ})+$K$5)/{TOT},"n.d.")', "K6", LT),
             ("H7", "Peso del settore dopo l'operazione",
              f'=IF({ok},(SUMIF($E${P0}:$E${P0 + N_POS - 1},{look("settore", "$K$4")},{JZ})+$K$5)/{TOT},"n.d.")', "K7", LS),
             ("H8", "Peso dell'area dopo l'operazione",
              f'=IF({ok},(SUMIF($F${P0}:$F${P0 + N_POS - 1},{look("area", "$K$4")},{JZ})+$K$5)/{TOT},"n.d.")', "K8", LA),
             ("H9", "Peso delle valute non euro dopo l'operazione",
              f'=IF({ok},(SUMIF($G${P0}:$G${P0 + N_POS - 1},"<>EUR",{JZ})+IF({look("valuta", "$K$4")}<>"EUR",$K$5,0))/{TOT},"n.d.")', "K9", LV)]
    for cella, testo, f, dest, _lim in righe:
        et(cella, testo)
        form(dest, f, "0.0%")
    et("H10", "ESITO DI COMPATIBILITÀ con i limiti", True)
    motivi = "&".join(f'IF({dest}>{lim},"{nome}; ","")' for (_, _, _, dest, lim), nome in zip(
        righe, ("limite per titolo", "limite per settore", "limite per area", "limite per valute non euro")))
    form("K10", f'=IF({ok},IF(AND(K6<={LT},K7<={LS},K8<={LA},K9<={LV},$K$5<=IF(ISNUMBER({LIQ}),{LIQ},0)),"Compatibile",'
                f'"Non compatibile: "&{motivi}&IF($K$5>IF(ISNUMBER({LIQ}),{LIQ},0),"liquidità insufficiente; ","")),'
                f'"Inserire ticker e importo (serve un patrimonio maggiore di zero)")', None, True)
    ws["K10"].alignment = Alignment(horizontal="left")
    B, T = lib.tab["BUFFETT"], lib.tab["TRADING"]
    et("H11", "Giudizio sul titolo - strategia A (separato)")
    form("K11", f'=IF($K$4<>"",IFERROR(INDEX({B.rng("verdetto")},MATCH($K$4,{B.rng("ticker")},0)),"n.d."),"-")', None, False, VERDE)
    et("H12", "Giudizio sul titolo - strategia B (separato)")
    form("K12", f'=IF($K$4<>"",IFERROR(INDEX({T.rng("segnale")},MATCH($K$4,{T.rng("ticker")},0)),"n.d."),"-")', None, False, VERDE)
    for c in ("K11", "K12"):
        ws[c].alignment = Alignment(horizontal="left")

    for r in range(4, 12):
        ws.merge_cells(f"D{r}:E{r}")
    for r in range(4, 13):
        ws.merge_cells(f"H{r}:J{r}")
    # --- posizioni
    r = P0 - 1
    intest = ("Ticker", "Quantità", "Prezzo medio di carico", "Società", "Settore", "Area", "Valuta", "Prezzo", "Cambio (per 1 euro)",
              "Controvalore (euro)", "Peso", "Limite per titolo", "Risultato sul carico", "Beta sul mercato mondiale",
              "Volatilità annua (3 anni, euro)", "Perdita nello stress (euro)", "Giorni per liquidare",
              "Scambi medi giornalieri (euro)", "Verdetto strategia A", "Segnale strategia B", "Peso x volatilità",
              "Posizione nella matrice")
    ws.row_dimensions[r].height = 42
    for j, h in enumerate(intest, 1):
        testata(ws, r, j, h)
    for i in range(N_POS):
        r = P0 + i
        for col, k, fmt in (("A", "ticker", None), ("B", "quantita", "#,##0.####"), ("C", "carico", F_NUM)):
            lib.gialla(ws, f"{col}{r}", g(f"pos|{i}|{k}", None), f"PORT|pos|{i}|{k}", fmt)
        vuoto = f'$A{r}=""'
        for col, k, fmt in (("D", "nome", None), ("E", "settore", None), ("F", "area", None), ("G", "valuta", None),
                            ("H", "prezzo", F_NUM), ("I", "cambio_eur", "0.0000"), ("N", "beta_mercato", "0.00"),
                            ("O", "vol_3a_eur", "0.0%"), ("R", "controvalore_eur", F_INT)):
            form(f"{col}{r}", f'=IF({vuoto},"",IFERROR({look(k, f"$A{r}")},"n.d."))', fmt, False, VERDE)
            if fmt is None:
                ws[f"{col}{r}"].alignment = Alignment(horizontal="left")
        form(f"J{r}", f'=IF(OR({vuoto},NOT(ISNUMBER($B{r})),NOT(ISNUMBER(H{r})),NOT(ISNUMBER(I{r}))),"",$B{r}*H{r}/I{r})', F_INT)
        form(f"K{r}", f'=IF(AND(ISNUMBER(J{r}),{TOT}>0),J{r}/{TOT},"")', "0.0%")
        form(f"L{r}", f'=IF(ISNUMBER(K{r}),IF(SUMIF({PZ},$A{r},{JZ})/{TOT}>{LT},"Oltre il limite","Entro il limite"),"")')
        form(f"M{r}", f'=IF(AND(ISNUMBER(H{r}),ISNUMBER($C{r})),IF($C{r}>0,H{r}/$C{r}-1,""),"")', "0.0%")
        form(f"P{r}", f'=IF(ISNUMBER(J{r}),J{r}*(IF(ISNUMBER(N{r}),N{r},1)*{SM}+IF(G{r}<>"EUR",{SV},0)),"")', F_INT)
        form(f"Q{r}", f'=IF(AND(ISNUMBER(J{r}),ISNUMBER(R{r})),IF(R{r}*{QV}>0,J{r}/(R{r}*{QV}),""),"")', "0.0")
        form(f"S{r}", f'=IF({vuoto},"",IFERROR(INDEX({B.rng("verdetto")},MATCH($A{r},{B.rng("ticker")},0)),"n.d."))', None, False, VERDE)
        form(f"T{r}", f'=IF({vuoto},"",IFERROR(INDEX({T.rng("segnale")},MATCH($A{r},{T.rng("ticker")},0)),"n.d."))', None, False, VERDE)
        form(f"U{r}", f"=IF(AND(ISNUMBER(K{r}),ISNUMBER(O{r})),K{r}*O{r},0)", "0.0000")
        form(f"V{r}", f'=IF({vuoto},"",IFERROR(MATCH($A{r},CORRELAZIONI!$A$2:$A${n + 1},0),""))', "0")
        for c in ("L", "S", "T"):
            ws[f"{c}{r}"].alignment = Alignment(horizontal="left")
        # blocco per la varianza: w_i s_i w_j s_j rho_ij
        ult = get_column_letter(n + 1)
        for j in range(N_POS):
            rj = P0 + j
            cella = f"{get_column_letter(28 + j)}{r}"
            ws[cella] = (f'=IF(AND(ISNUMBER($V{r}),ISNUMBER($V${rj})),IF(ISNUMBER(INDEX(CORRELAZIONI!$B$2:${ult}${n + 1},$V{r},$V${rj})),'
                         f'$U{r}*$U${rj}*INDEX(CORRELAZIONI!$B$2:${ult}${n + 1},$V{r},$V${rj}),0),0)')
            ws[cella].font = car("A6A6A6", dim=7)
    ws.cell(P0 - 1, 28, "Blocco di calcolo della varianza (pesi x volatilità x correlazione)").font = car(GRIGIO, corsivo=True, dim=8)

    # --- pesi per settore e per area
    r0 = P0 + N_POS + 2
    et(f"A{r0}", "Pesi per settore", True)
    et(f"F{r0}", "Pesi per area", True)
    for j, h in zip((1, 2, 3, 4), ("Settore", "Controvalore (euro)", "Peso", "Esito")):
        testata(ws, r0 + 1, j, h)
    for j, h in zip((6, 7, 8, 9), ("Area", "Controvalore (euro)", "Peso", "Esito")):
        testata(ws, r0 + 1, j, h)
    for i, s in enumerate(settori):
        r = r0 + 2 + i
        _dato(ws, r, 1, s, colore=NERO)
        form(f"B{r}", f"=SUMIF($E${P0}:$E${P0 + N_POS - 1},$A{r},{JZ})", F_INT)
        form(f"C{r}", f'=IF({TOT}>0,B{r}/{TOT},"n.d.")', "0.0%")
        form(f"D{r}", f'=IF(ISNUMBER(C{r}),IF(C{r}>{LS},"Oltre il limite","Entro il limite"),"n.d.")')
    for i, a in enumerate(aree):
        r = r0 + 2 + i
        _dato(ws, r, 6, a, colore=NERO)
        form(f"G{r}", f"=SUMIF($F${P0}:$F${P0 + N_POS - 1},$F{r},{JZ})", F_INT)
        form(f"H{r}", f'=IF({TOT}>0,G{r}/{TOT},"n.d.")', "0.0%")
        form(f"I{r}", f'=IF(ISNUMBER(H{r}),IF(H{r}>{LA},"Oltre il limite","Entro il limite"),"n.d.")')
    ws.freeze_panes = f"A{P0}"


# ============================================================================ SIMULATORE
S0 = 22                        # riga dell'anno 0 nella tabella


def foglio_etf(lib: Libro, etf: dict | None) -> int:
    """Chiusure di fine mese dei due ETF di confronto (dati) e loro reciproco (formula)."""
    if not etf or len(etf["date"]) < 13:
        return 0
    ws = lib.foglio("ETF_MENSILI")
    for j, h in enumerate(("Fine mese", etf["nomi"][0], etf["nomi"][1], "1 / prezzo", "1 / prezzo"), 1):
        ws.cell(1, j, h).font = car(NERO, True, 9)
    for i, d in enumerate(etf["date"]):
        r = 2 + i
        _dato(ws, r, 1, d, F_DATA)
        _dato(ws, r, 2, etf["a"][i], F_NUM)
        _dato(ws, r, 3, etf["b"][i], F_NUM)
        ws.cell(r, 4, f"=1/B{r}").font = car()
        ws.cell(r, 5, f"=1/C{r}").font = car()
    ws.column_dimensions["A"].width = 12
    return len(etf["date"])


def foglio_simulatore(lib: Libro, gialle: dict, etf: dict | None, n_mesi: int):
    ws = lib.foglio("SIMULATORE")
    titolo_foglio(ws, "SIMULATORE", "Le tre ipotesi di rendimento sono scelte dall'utente: non sono previsioni. "
                                    "Imposte al 26% come esempio modificabile (regime italiano semplificato).")
    for col, w in zip("ABCDEFGHIJK", (48, 15, 15, 15, 15, 14, 14, 14, 14, 14, 14)):
        ws.column_dimensions[col].width = w
    d = simulatore.PREDEFINITI
    g = lambda k, pred: gialle.get("SIM|" + k, pred)  # noqa: E731
    ing = [("importo", "Importo iniziale (euro)", d["importo"], F_INT), ("versamento", "Versamento mensile (euro)", d["versamento"], F_INT),
           ("anni", "Orizzonte (anni, massimo 40)", d["anni"], "0"), ("r0", "Rendimento annuo totale - ipotesi prudente", d["rendimenti"][0], "0.0%"),
           ("r1", "Rendimento annuo totale - ipotesi base", d["rendimenti"][1], "0.0%"),
           ("r2", "Rendimento annuo totale - ipotesi ottimistica", d["rendimenti"][2], "0.0%"),
           ("dividendi", "Di cui dividendi (rendimento da dividendo annuo)", d["dividendi"], "0.0%"),
           ("reinvesti", "Dividendi reinvestiti (sì / no)", d["reinvesti"], None),
           ("commissione", "Commissione per ogni versamento (euro)", d["commissione"], F_NUM),
           ("costi_annui", "Costi annui (% del capitale)", d["costi_annui"], "0.00%"),
           ("imposte", "Imposte su dividendi e plusvalenze", d["imposte"], "0%"),
           ("inflazione", "Inflazione annua", d["inflazione"], "0.0%")]
    A = {}
    for i, (k, testo, pred, fmt) in enumerate(ing):
        r = 4 + i
        ws.cell(r, 1, testo).font = car()
        lib.gialla(ws, f"B{r}", g(k, pred), "SIM|" + k, fmt, pred=pred)
        A[k] = f"$B${r}"
    dv = DataValidation(type="list", formula1='"sì,no"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add(A["reinvesti"].replace("$", ""))
    # celle di servizio
    ws["D4"], ws["D5"] = "Anni usati", "Versamenti netti dell'anno"
    ws["D4"].font = ws["D5"].font = car()
    ws["E4"] = f"=MAX(0,MIN({simulatore.MAX_ANNI},INT(IF(ISNUMBER({A['anni']}),{A['anni']},0))))"
    ws["E5"] = f"=IF({A['versamento']}>0,12*MAX(0,{A['versamento']}-{A['commissione']}),0)"
    ws["E4"].font = ws["E5"].font = car()
    ws["E5"].number_format = F_INT
    ANNI, RATE, REINV = "$E$4", "$E$5", f'{A["reinvesti"]}="sì"'
    # tabella anno per anno
    r = S0 - 1
    intest = ("Anno", "Capitale - prudente", "Capitale - base", "Capitale - ottimistica", "Totale versato",
              "Investito ai fini fiscali - prudente", "Investito ai fini fiscali - base", "Investito ai fini fiscali - ottimistica",
              "Dividendi netti incassati - prudente", "Dividendi netti incassati - base", "Dividendi netti incassati - ottimistica")
    ws.row_dimensions[r].height = 40
    for j, h in enumerate(intest, 1):
        testata(ws, r, j, h)
    cap0 = f"MAX(0,{A['importo']}-IF({A['importo']}>0,{A['commissione']},0))"
    for a in range(simulatore.MAX_ANNI + 1):
        r = S0 + a
        ws.cell(r, 1, a).font = car()
        for s in range(3):
            cc, ci, cd = get_column_letter(2 + s), get_column_letter(6 + s), get_column_letter(9 + s)
            gg = f"({A['r' + str(s)]}-{A['dividendi']}-{A['costi_annui']})"
            if a == 0:
                f_cap, f_inv, f_div = f"={cap0}", f"={cap0}", "=0"
            else:
                p = r - 1
                divn = f"{A['dividendi']}*({cc}{p}+{RATE}/2)*(1-{A['imposte']})"
                att = f"$A{r}<={ANNI}"
                f_cap = f'=IF({att},{cc}{p}*(1+{gg})+{RATE}*(1+{gg}/2)+IF({REINV},{divn},0),"")'
                f_inv = f'=IF({att},{ci}{p}+{RATE}+IF({REINV},{divn},0),"")'
                f_div = f'=IF({att},{cd}{p}+IF({REINV},0,{divn}),"")'
            for col, f in ((cc, f_cap), (ci, f_inv), (cd, f_div)):
                c = ws[f"{col}{r}"]
                c.value, c.font, c.number_format = f, car(), F_INT
        c = ws.cell(r, 5, f"={A['importo']}" if a == 0 else f'=IF($A{r}<={ANNI},E{r - 1}+12*{A["versamento"]},"")')
        c.font, c.number_format = car(), F_INT
    # risultati
    ws["D7"] = "Risultati alla fine dell'orizzonte"
    ws["D7"].font = car(NERO, True)
    for j, h in enumerate(("Prudente", "Base", "Ottimistica")):
        testata(ws, 8, 5 + j, h)
    righe = ("Capitale finale lordo", "Totale versato", "Imposte sulla plusvalenza finale", "Netto dopo le imposte (con i dividendi incassati)",
             "Netto in potere d'acquisto di oggi")
    for i, testo in enumerate(righe):
        ws.cell(9 + i, 4, testo).font = car()
    for s in range(3):
        col = get_column_letter(5 + s)
        cc, ci, cd = get_column_letter(2 + s), get_column_letter(6 + s), get_column_letter(9 + s)
        fin = lambda x: f"INDEX(${x}${S0}:${x}${S0 + simulatore.MAX_ANNI},{ANNI}+1)"  # noqa: E731
        for i, f in enumerate((f"={fin(cc)}", f"={fin('E')}", f"={A['imposte']}*MAX(0,{fin(cc)}-{fin(ci)})",
                               f"={col}9-{col}11+{fin(cd)}", f"={col}12/(1+{A['inflazione']})^{ANNI}")):
            c = ws[f"{col}{9 + i}"]
            c.value, c.font, c.number_format = f, car(NERO, i in (3, 4)), F_INT
    _nota(ws, "D15", "Passo annuale: i versamenti dell'anno maturano in media mezzo anno. Le imposte colpiscono i dividendi quando "
                     "sono pagati e la plusvalenza alla fine. Modello semplificato: non sostituisce un calcolo fiscale.")
    # confronto storico con i due ETF
    r = S0 + simulatore.MAX_ANNI + 3
    ws.cell(r, 1, "Confronto storico: lo stesso piano negli anni passati sui due ETF ad accumulazione in euro").font = car(NERO, True)
    if not n_mesi:
        ws.cell(r + 1, 1, "Non disponibile: serie mensili degli ETF assenti (versione dimostrativa o ETF non scaricati).").font = car()
        ws.freeze_panes = "A4"
        return
    M = f"$B${r + 1}"
    ws.cell(r + 1, 1, "Mesi usati (orizzonte limitato dallo storico disponibile)").font = car()
    c = ws.cell(r + 1, 2, f"=MIN({ANNI}*12,{n_mesi - 1})")
    c.font = car()
    for j, h in enumerate(("ETF", "Valore finale (euro)", "Totale versato (euro)", "Guadagno (euro)", "Rendimento annuo composto dell'ETF nel periodo"), 1):
        testata(ws, r + 2, j, h)
    for i, (nome, cp, ci_) in enumerate(((etf["nomi"][0], "B", "D"), (etf["nomi"][1], "C", "E"))):
        rr = r + 3 + i
        ult = n_mesi + 1
        pf, pi = f"ETF_MENSILI!${cp}${ult}", f"INDEX(ETF_MENSILI!${cp}$2:${cp}${ult},{n_mesi}-{M})"
        somma = f"SUM(INDEX(ETF_MENSILI!${ci_}$2:${ci_}${ult},{n_mesi}-{M}+1):ETF_MENSILI!${ci_}${ult})"
        ws.cell(rr, 1, nome).font = car(BLU)
        for j, (f, fmt) in enumerate(((f'=IF({M}>0,{pf}*({A["importo"]}/{pi}+{A["versamento"]}*{somma}),"n.d.")', F_INT),
                                      (f'=IF({M}>0,{A["importo"]}+{M}*{A["versamento"]},"n.d.")', F_INT),
                                      (f'=IF({M}>0,B{rr}-C{rr},"n.d.")', F_INT),
                                      (f'=IF({M}>0,({pf}/{pi})^(12/{M})-1,"n.d.")', "0.0%")), 2):
            c = ws.cell(rr, j, f)
            c.font, c.number_format = car(), fmt
    _nota(ws, f"A{r + 5}", "Senza commissioni né imposte: i costi di gestione sono già nel prezzo dell'ETF. "
                           "I rendimenti passati non anticipano quelli futuri.")
    ws.freeze_panes = "A4"


# ============================================================================ BACKTEST
def foglio_backtest(lib: Libro, b: dict | None):
    ws = lib.foglio("BACKTEST")
    titolo_foglio(ws, "BACKTEST - solo strategia B (Trading Score)",
                  "Senza sguardo al futuro: a ogni data il punteggio usa solo i prezzi fino a quella data. Risultati passati, non previsioni.")
    for col, w in zip("ABCDEFGH", (34, 14, 14, 14, 14, 18, 14, 14)):
        ws.column_dimensions[col].width = w
    avvisi = ["DISTORSIONE DA SOPRAVVIVENZA: l'universo è quello di oggi; le società fallite, delistate o uscite non ci sono, "
              "quindi i rendimenti storici sono sovrastimati.",
              "Il pilastro Catalizzatori non è ricostruibile nel passato: il punteggio storico usa gli altri sei pilastri (95% del peso).",
              "Nessun costo di negoziazione né imposta. Le finestre a 63 sedute rilevate ogni 21 si sovrappongono: le osservazioni "
              "non sono indipendenti.",
              "Per la strategia A (Buffett Score) il backtest NON viene fatto: mancano i bilanci 'come erano noti allora'."]
    for i, t in enumerate(avvisi):
        ws.cell(3 + i, 1, t).font = car("C00000" if i == 0 else NERO, i == 0)
    if not b:
        ws["A8"] = "Backtest non ancora eseguito: nessun risultato da mostrare. Lanciare  python avvia.py backtest"
        ws["A8"].font = car(NERO, True)
        return
    r = 8
    for et, v, fmt in (("Eseguito il", b["eseguito"][:10], None), ("Prima rilevazione", b["dal"], None), ("Ultima rilevazione", b["al"], None),
                       ("Date di rilevazione (una ogni 21 sedute)", b["rilevazioni"], "0"), ("Titoli nell'universo", b["titoli"], "0"),
                       ("Osservazioni (titolo x data)", b["osservazioni"], F_INT)):
        ws.cell(r, 1, et).font = car()
        _dato(ws, r, 2, v, fmt)
        r += 1
    for h, fasce in b["fasce"].items():
        r += 1
        ws.cell(r, 1, f"Rendimento (total return) nelle {h} sedute successive, per fascia di Trading Score").font = car(NERO, True)
        for j in range(1, 7):
            ws.cell(r, j).fill = FASCIA
        r += 1
        for j, t in enumerate(("Fascia di punteggio", "Osservazioni", "Rendimento medio", "Rendimento mediano", "Quota di casi positivi",
                               "Extra-rendimento medio sull'universo alla stessa data"), 1):
            testata(ws, r, j, t)
        ws.row_dimensions[r].height = 40
        for nome, s in fasce.items():
            r += 1
            _dato(ws, r, 1, "Tutte le fasce" if nome == "tutti" else nome)
            _dato(ws, r, 2, s.get("n", 0), F_INT)
            abbastanza = s.get("n", 0) >= b["min_osservazioni"]
            for j, k in enumerate(("media", "mediana", "positivi", "extra_media"), 3):
                if k == "positivi" and not abbastanza:
                    _dato(ws, r, j, "n.d. (meno di 100 oss.)")
                else:
                    _dato(ws, r, j, s.get(k) if s.get("n") else None, "0.00%" if k != "positivi" else "0%")
        r += 1
    st = b["setup"]
    r += 1
    ws.cell(r, 1, "Simulazione dei setup (segnale 'Setup attivo')").font = car(NERO, True)
    for j in range(1, 9):
        ws.cell(r, j).fill = FASCIA
    r += 1
    for et, v in (("Segnali rilevati", st["segnali"]), ("Non eseguiti (rottura non scattata in 5 sedute, o apertura oltre i livelli)", st["non_eseguiti"]),
                  ("Ancora in corso alla fine dello storico (non contati)", st["in_corso"]), ("Operazioni chiuse", st["chiuse"])):
        ws.cell(r, 1, et).font = car()
        _dato(ws, r, 2, v, F_INT)
        r += 1
    for j, t in enumerate(("Tipo di setup", "Operazioni", "Chiuse all'obiettivo", "Chiuse allo stop", "Chiuse a tempo (63 sedute)",
                           "Risultato medio in multipli del rischio (R)", "Rendimento medio", "Durata media (sedute)"), 1):
        testata(ws, r, j, t)
    ws.row_dimensions[r].height = 40
    for tipo, s in st["per_tipo"].items():
        r += 1
        _dato(ws, r, 1, tipo)
        _dato(ws, r, 2, s.get("n", 0), F_INT)
        if not s.get("n"):
            continue
        abbastanza = s["n"] >= b["min_osservazioni"]
        for j, k in enumerate(("obiettivo", "stop", "tempo"), 3):
            _dato(ws, r, j, s[k] if abbastanza else "n.d. (meno di 100 oss.)", "0%")
        _dato(ws, r, 6, s["r_medio"], "0.00")
        _dato(ws, r, 7, s["rendimento_medio"], "0.00%")
        _dato(ws, r, 8, s["sedute_medie"], "0")
    _nota(ws, f"A{r + 2}", "Regole: rottura = ordine d'acquisto al livello d'ingresso valido 5 sedute; ritracciamento = ingresso all'apertura "
                           "successiva; se nella stessa seduta sono toccati stop e obiettivo vale lo stop; uscita a tempo dopo 63 sedute. "
                           "Le frequenze storiche sono mostrate solo con almeno 100 osservazioni e non sono probabilità.")
    ws.freeze_panes = "A8"
