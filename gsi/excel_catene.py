"""Fogli CATENE (posizione di ogni titolo nella catena del valore del suo mercato) e MERCATI (le 23 catene)."""
from __future__ import annotations

from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.formula import ArrayFormula

from . import catene as cat
from .excel import BLU, FASCIA, ND, NERO, R0, VERDE, Libro, Tab, car, testata, titolo_foglio

# mediane per anello calcolate con formule: (chiave, intestazione, colonna dei dati, formato)
MEDIANE_ANELLO = [("med_marg", "Margine operativo mediano dell'anello (titoli dell'universo; non per banche e assicurazioni)", "marg", "0.0%"),
                  ("med_rend", "Rendimento sul capitale mediano dell'anello (ROIC; banche e assicurazioni: ROE)", "rend", "0.0%")]


def foglio_catene(lib: Libro, tickers: list[str], scrivi: bool = True) -> Tab:
    t = Tab(lib, "CATENE", "CATENA DEL VALORE DI OGNI TITOLO",
            "Struttura redatta da Claude, protagonisti e fatti da una ricerca su internet (foglio MERCATI, con le fonti). "
            "Descrizione del mercato: non entra nei punteggi. I margini dell'anello sono calcolati dai bilanci.")
    pf = {tk: cat.profilo(tk) for tk in tickers}
    v = lambda k: (lambda tk: pf[tk].get(k))  # noqa: E731
    t.col("ticker", "Ticker", lambda tk: tk, None, "dato", 11)
    t.col("nome", "Società", "={D:nome}", None, "link", 22)
    t.col("catena", "Mercato (catena del valore)", v("catena"), None, "dato", 26)
    t.col("anello", "Anello dell'azienda", v("anello"), None, "dato", 26)
    t.col("anello_id", "Codice dell'anello", v("anello_id"), None, "dato", 10)
    t.col("testo", "La catena, dal fornitore al cliente finale (anello dell'azienda tra parentesi quadre)", v("testo"), None, "dato", 80)
    t.col("cosa", "Che cosa succede in questo anello", v("cosa"), None, "dato", 45)
    t.col("forza", "Forza contrattuale dell'anello", v("forza"), None, "dato", 45)
    t.col("a_monte", "Da chi dipende (anello a monte)", v("a_monte"), None, "dato", 40)
    t.col("a_valle", "Chi dipende da lei (anello a valle)", v("a_valle"), None, "dato", 40)
    t.col("chi_cattura", "Chi cattura il valore nella catena", v("chi_cattura"), None, "dato", 50)
    t.col("tendenza", "Che cosa sta cambiando", v("tendenza"), None, "dato", 45)
    t.col("fatti", "Fatti sull'anello dalla ricerca", v("fatti"), None, "dato", 45)
    t.col("altri", "Altri titoli dell'universo nella stessa catena", v("altri"), None, "dato", 50)
    t.col("marg", "Margine operativo medio del titolo", "={D:Q3}", "0.0%", "link", 9)
    t.col("rend", "Rendimento sul capitale medio del titolo", "={D:Q1}", "0.0%", "link", 9)
    t.col("n_anello", "Titoli dell'universo nell'anello", "=COUNTIF({R:anello_id},{anello_id})", "0", "formula", 8)
    for k, h, col, fmt in MEDIANE_ANELLO:
        x = "{R:" + col + "}"
        t.col(k, h, f'=IF(SUMPRODUCT(({{R:anello_id}}={{anello_id}})*ISNUMBER({x}))=0,"n.d.",'
                    f'MEDIAN(IF({{R:anello_id}}={{anello_id}},IF(ISNUMBER({x}),{x}))))', fmt, "matrice", 12)
    if scrivi:
        t.scrivi(tickers)
    return t


def foglio_mercati(lib: Libro):
    ws = lib.foglio("MERCATI")
    titolo_foglio(ws, "MERCATI - le catene del valore",
                  f"Struttura redatta da Claude; protagonisti, forza contrattuale e fatti da una ricerca su internet del "
                  f"{cat.DATA_RICERCA[8:10]}/{cat.DATA_RICERCA[5:7]}/{cat.DATA_RICERCA[:4]} (fonti in fondo a ogni catena). "
                  "Descrizioni, non dati verificati dal programma.")
    for col, w in zip("ABCDEFGH", (34, 42, 34, 10, 42, 42, 26, 14)):
        ws.column_dimensions[col].width = w
    CA = lib.tab["CATENE"]
    r = 3
    if not cat.CATENE:
        ws.cell(r, 1, "Nessuna catena disponibile.").font = car()
        return
    for cid, c in cat.CATENE.items():
        for j in range(1, 9):
            ws.cell(r, j).fill = FASCIA
        ws.cell(r, 1, c["nome"].upper()).font = car(NERO, True, 11)
        r += 1
        for et, k in (("Chi cattura il valore", "chi_cattura"), ("Che cosa sta cambiando", "tendenza")):
            ws.cell(r, 1, et).font = car(NERO, True)
            x = ws.cell(r, 2, c.get(k) or ND)
            x.font, x.alignment = car(BLU), Alignment(wrap_text=True, vertical="top")
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
            ws.row_dimensions[r].height = 30
            r += 1
        for j, h in enumerate(("Anello (dal fornitore al cliente finale)", "Che cosa succede", "Protagonisti", "Forza",
                               "Perché", "Fatti dalla ricerca", "Titoli dell'universo", "Margine operativo mediano"), 1):
            testata(ws, r, j, h)
        ws.row_dimensions[r].height = 30
        for i, a in enumerate(c["anelli"]):
            r += 1
            for j, v in enumerate((f"{i + 1}. {a['nome']}", a["cosa"], a.get("protagonisti") or ND, a.get("forza") or ND,
                                   a.get("perche") or ND, a.get("fatti") or "-", ", ".join(a.get("titoli", [])) or "-"), 1):
                x = ws.cell(r, j, v)
                x.font, x.alignment = car(BLU, j == 1), Alignment(wrap_text=True, vertical="top")
            aid = f"{cid}|{a['id']}"
            x = ws.cell(r, 8, f'=IFERROR(INDEX({CA.rng("med_marg")},MATCH("{aid}",{CA.rng("anello_id")},0)),"-")')
            x.font, x.number_format = car(VERDE), "0.0%"
            x.alignment = Alignment(horizontal="right", vertical="top")
            ws.row_dimensions[r].height = 58
        r += 1
        fonti = "; ".join(f"{f.get('titolo', '')} ({f.get('data', 'senza data')}): {f.get('url', '')}" for f in c.get("fonti", []))
        ws.cell(r, 1, "Fonti").font = car(NERO, True, 9)
        x = ws.cell(r, 2, fonti or "-")
        x.font, x.alignment = car("595959", dim=8), Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        ws.row_dimensions[r].height = 40
        if c.get("nota_struttura"):
            r += 1
            ws.cell(r, 1, "Nota sulla struttura").font = car(NERO, True, 9)
            x = ws.cell(r, 2, c["nota_struttura"])
            x.font = car("595959", corsivo=True, dim=9)
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        r += 3
    ws.freeze_panes = "A3"
