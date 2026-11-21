"""Metriche di bilancio: dagli esercizi annuali agli ingressi dei punteggi.

`calcola_fondamentali` e' una funzione pura (lista di esercizi -> dizionario), collaudata senza rete.
Un dato mancante resta None ("n.d.") e non vale mai punti. Tutti i valori sono nella valuta di bilancio.
"""
from __future__ import annotations
import statistics

from .parametri import FINANZIARI

# campo interno -> (prospetto, voci Yahoo in ordine di preferenza)
VOCI = {
    "ricavi": ("CE", ["TotalRevenue", "OperatingRevenue"]),
    "ebit": ("CE", ["EBIT", "OperatingIncome"]),
    "straord": ("CE", ["SpecialIncomeCharges"]),
    "lordo": ("CE", ["GrossProfit"]),
    "utile": ("CE", ["NetIncomeCommonStockholders", "NetIncome"]),
    "tasse": ("CE", ["TaxProvision"]),
    "ante": ("CE", ["PretaxIncome"]),
    "interessi": ("CE", ["InterestExpense", "InterestExpenseNonOperating"]),
    "da": ("CE", ["ReconciledDepreciation"]),
    "ebitda": ("CE", ["EBITDA"]),
    "eps": ("CE", ["DilutedEPS", "BasicEPS"]),
    "az_dil": ("CE", ["DilutedAverageShares", "BasicAverageShares"]),
    "debito": ("SP", ["TotalDebt"]),
    "deb_lungo": ("SP", ["LongTermDebtAndCapitalLeaseObligation", "LongTermDebt"]),
    "deb_corr": ("SP", ["CurrentDebtAndCapitalLeaseObligation", "CurrentDebt"]),
    "patr": ("SP", ["StockholdersEquity", "CommonStockEquity"]),
    "patr_tot": ("SP", ["TotalEquityGrossMinorityInterest", "StockholdersEquity"]),
    "attivo": ("SP", ["TotalAssets"]),
    "cassa": ("SP", ["CashCashEquivalentsAndShortTermInvestments", "CashAndCashEquivalents"]),
    "pass_corr": ("SP", ["CurrentLiabilities"]),
    "avviamento": ("SP", ["GoodwillAndOtherIntangibleAssets", "Goodwill"]),
    "tbv": ("SP", ["TangibleBookValue"]),
    "az_fine": ("SP", ["OrdinarySharesNumber", "ShareIssued"]),
    "fcf": ("RF", ["FreeCashFlow"]),
    "dividendi": ("RF", ["CashDividendsPaid", "CommonStockDividendPaid"]),
    "sbc": ("RF", ["StockBasedCompensation"]),
    "plus_ppe": ("RF", ["GainLossOnSaleOfPPE"]),
    "plus_att": ("RF", ["GainLossOnSaleOfBusiness"]),
    "da_rf": ("RF", ["DepreciationAndAmortization"]),
}
# voci che la SEC puo' allungare (se coerenti con Yahoo sugli esercizi in comune)
VOCI_SEC = {"ricavi": ("CE", "TotalRevenue"), "utile": ("CE", "NetIncome"),
            "cassa_sec": ("SP", "CashAndCashEquivalents"), "patr": ("SP", "StockholdersEquity")}
MAX_ANNI = 10


def _ok(*v):
    return all(x is not None for x in v)


def media(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None


def cagr(primo, ultimo, anni):
    if not _ok(primo, ultimo) or anni <= 0 or primo <= 0 or ultimo <= 0:
        return None
    return (ultimo / primo) ** (1.0 / anni) - 1.0


def anni_tra(d0: str, d1: str) -> float:
    return (int(d1[:4]) - int(d0[:4])) + (int(d1[5:7]) - int(d0[5:7])) / 12.0


def rettifica_frazionamenti(date: list[str], valori: list, fraz: list[tuple[str, float]], per_azione: bool):
    """Uniforma una serie annuale (numero di azioni, o grandezza per azione) quando la fonte ha
    rettificato per un frazionamento solo alcuni esercizi.

    Si corregge solo se il rapporto tra due esercizi consecutivi coincide (entro il 12%) con il
    fattore di un frazionamento avvenuto dopo la chiusura del primo dei due. -> (valori, note)
    """
    v = list(valori)
    note = []
    for i in range(len(v) - 2, -1, -1):
        if not _ok(v[i], v[i + 1]) or v[i] <= 0 or v[i + 1] <= 0:
            continue
        rapporto = v[i + 1] / v[i]
        for d, f in fraz:
            if d <= date[i] or abs(f - 1) < 0.3:
                continue
            atteso = 1.0 / f if per_azione else f
            if abs(rapporto / atteso - 1) < 0.12:
                for j in range(i + 1):
                    if v[j] is not None:
                        v[j] = v[j] / f if per_azione else v[j] * f
                note.append(f"esercizi fino al {date[i]} rettificati per il frazionamento {f:g} del {d}")
                break
    return v, note


def calcola_fondamentali(anni: list[dict], modello: str, fraz: list[tuple[str, float]] | None = None) -> dict:
    """anni: esercizi in ordine di data, ciascuno {"data": ..., campo: valore|None} (vedi VOCI).
    Gli esercizi piu' vecchi possono avere solo ricavi/utile/cassa/patrimonio (da SEC)."""
    fin = modello in FINANZIARI
    fraz = fraz or []
    A = [dict(a) for a in anni][-MAX_ANNI - 1:]
    g = lambda a, k: a.get(k)  # noqa: E731
    out: dict = {"note": []}
    validi = [a for a in A if _ok(g(a, "ricavi")) or _ok(g(a, "utile"))]
    out["n_anni"] = len(validi)
    out["ultimo_esercizio"] = validi[-1]["data"] if validi else None
    if not validi:
        return out
    U = validi[-1]
    date = [a["data"] for a in A]
    for campo, per_azione in (("az_dil", False), ("az_fine", False), ("eps", True)):
        nuovi, note = rettifica_frazionamenti(date, [g(a, campo) for a in A], fraz, per_azione)
        for a, x in zip(A, nuovi):
            a[campo] = x
        out["note"] += [f"{campo}: {n}" for n in note]

    # debito: TotalDebt, altrimenti somma delle componenti presenti; se lo stato patrimoniale c'e'
    # ma la fonte non riporta alcuna voce di debito in nessun esercizio, il debito si assume zero (nota)
    nessun_debito = not any(_ok(g(a, k)) for a in A for k in ("debito", "deb_lungo", "deb_corr"))
    for a in A:
        if a.get("debito") is None and (_ok(g(a, "deb_lungo")) or _ok(g(a, "deb_corr"))):
            a["debito"] = (g(a, "deb_lungo") or 0.0) + (g(a, "deb_corr") or 0.0)
        if a.get("debito") is None and nessun_debito and _ok(g(a, "attivo"), g(a, "patr_tot")):
            a["debito"] = 0.0
        if a.get("da") is None:
            a["da"] = g(a, "da_rf")
        if a.get("ebitda") is None and _ok(g(a, "ebit"), g(a, "da")):
            a["ebitda"] = a["ebit"] + a["da"]
        # EBITDA ordinario: prima delle componenti straordinarie indicate dalla fonte (svalutazioni,
        # ristrutturazioni, plusvalenze), che altrimenti falsano leva e multiplo
        if _ok(g(a, "ebitda"), g(a, "straord")):
            a["ebitda"] = a["ebitda"] - a["straord"]
    if nessun_debito and any(a.get("debito") == 0.0 for a in A):
        out["note"].append("debito finanziario non riportato dalla fonte in nessun esercizio: assunto pari a zero")

    # ---- rendimento sul capitale
    def aliquota(a):
        if _ok(g(a, "tasse"), g(a, "ante")) and a["ante"] > 0:
            return max(0.0, min(0.35, a["tasse"] / a["ante"]))
        return 0.25

    quasi_zero = any(_ok(g(a, "patr_tot"), g(a, "attivo")) and a["attivo"] > 0 and a["patr_tot"] / a["attivo"] < 0.10
                     for a in A) and not fin
    out["capitale_alternativo"] = quasi_zero

    def capitale(a):
        if quasi_zero:
            if not _ok(g(a, "attivo"), g(a, "cassa"), g(a, "pass_corr")):
                return None
            return a["attivo"] - a["cassa"] - (a["pass_corr"] - (g(a, "deb_corr") or 0.0))
        if not _ok(g(a, "debito"), g(a, "patr_tot")):
            return None
        return a["debito"] + a["patr_tot"]

    rend, nopat_s, cap_s = [], [], []
    for i, a in enumerate(A):
        prec = A[i - 1] if i > 0 else None
        if fin:
            if not _ok(g(a, "utile"), g(a, "patr")):
                continue
            base = (a["patr"] + prec["patr"]) / 2 if prec and _ok(g(prec, "patr")) else a["patr"]
            if base > 0:
                rend.append(a["utile"] / base)
        else:
            c = capitale(a)
            if not _ok(g(a, "ebit"), c):
                continue
            n = a["ebit"] * (1 - aliquota(a))
            cp = capitale(prec) if prec else None
            base = (c + cp) / 2 if cp is not None else c
            if base > 0:
                rend.append(n / base)
                nopat_s.append(n)
                cap_s.append(c)
    out["rend_n"] = len(rend)
    out["Q1"] = media(rend)
    out["Q2"] = min(rend) if rend else None
    out["roe_norm"] = media(rend[-5:]) if fin else None

    # ---- margini e ricavi
    marg = [a["ebit"] / a["ricavi"] for a in A if _ok(g(a, "ebit"), g(a, "ricavi")) and a["ricavi"] > 0]
    out["Q3"] = None if fin else media(marg)            # finanziari: dato manuale (GIUDIZI)
    serie_q4 = rend if fin else marg
    out["Q4"] = statistics.stdev(serie_q4) if len(serie_q4) >= 3 else None
    ric = [(a["data"], a["ricavi"]) for a in A if _ok(g(a, "ricavi"))]
    su = [1 if b[1] > a[1] else 0 for a, b in zip(ric, ric[1:])]
    out["Q5"] = sum(su) / len(su) if len(su) >= 2 else None
    lordi = [a["lordo"] / a["ricavi"] for a in A if _ok(g(a, "lordo"), g(a, "ricavi")) and a["ricavi"] > 0]
    out["Q6"] = media(lordi) if modello == "STD" else None
    out["margine_ultimo"] = marg[-1] if marg else None
    out["margine_medio_prec"] = media(marg[:-1]) if len(marg) >= 2 else None
    out["var_ricavi_ultimo"] = ric[-1][1] / ric[-2][1] - 1 if len(ric) >= 2 and ric[-2][1] > 0 else None

    # ---- solidita'
    deb_netto = U["debito"] - U["cassa"] if _ok(g(U, "debito"), g(U, "cassa")) else None
    out["debito_netto"] = deb_netto
    out["ebitda"] = g(U, "ebitda")
    if fin:
        out["F1"] = U["patr"] / U["attivo"] if _ok(g(U, "patr"), g(U, "attivo")) and U["attivo"] > 0 else None
        out["F2"] = None
    else:
        if _ok(deb_netto, g(U, "ebitda")):
            out["F1"] = 99.0 if U["ebitda"] <= 0 else deb_netto / U["ebitda"]
        else:
            out["F1"] = None
        if deb_netto is not None and deb_netto <= 0:
            out["F2"] = 99.0
        elif _ok(g(U, "ebit"), g(U, "interessi")) and abs(U["interessi"]) > 0:
            out["F2"] = min(99.0, U["ebit"] / abs(U["interessi"]))
        else:
            out["F2"] = None

    def ffo(a):
        if not _ok(g(a, "utile"), g(a, "da")):
            return None
        # nel rendiconto le plusvalenze da cessione sono rettifiche col segno meno
        return a["utile"] + a["da"] + (g(a, "plus_ppe") or 0.0) + (g(a, "plus_att") or 0.0)

    Y = [a for a in A if _ok(g(a, "fcf"))]                # esercizi con rendiconto (fonte Yahoo)
    s_fcf = sum(a["fcf"] for a in Y if _ok(g(a, "utile")))
    s_ut = sum(a["utile"] for a in Y if _ok(g(a, "utile")))
    out["F3"] = s_fcf / s_ut if Y and s_ut > 0 and modello in ("STD", "CIC") else None
    s_div = sum(abs(a["dividendi"]) for a in Y if _ok(g(a, "dividendi")))
    if modello in ("STD", "CIC"):
        den = sum(a["fcf"] for a in Y)
    elif modello == "REIT":
        den = sum(ffo(a) or 0.0 for a in Y)
    else:
        den = sum(a["utile"] for a in Y if _ok(g(a, "utile")))
    if s_div <= 0:
        out["F4"] = None                                 # non paga dividendi
    else:
        out["F4"] = 9.99 if den <= 0 else min(9.99, s_div / den)
    out["F5"] = None                                     # dato manuale (GIUDIZI)
    out["fcf_ultimo"] = Y[-1]["fcf"] if Y else None
    out["avviamento_su_patr"] = (U["avviamento"] / U["patr_tot"] if _ok(g(U, "avviamento"), g(U, "patr_tot"))
                                 and U["patr_tot"] > 0 else None)

    # ---- crescita
    out["cagr_ricavi"] = cagr(ric[0][1], ric[-1][1], anni_tra(ric[0][0], ric[-1][0])) if len(ric) >= 2 else None
    out["cagr_ricavi_anni"] = anni_tra(ric[0][0], ric[-1][0]) if len(ric) >= 2 else None
    if fin:
        B = [a for a in A if _ok(g(a, "patr"), g(a, "az_fine")) and a["az_fine"] > 0]
        if len(B) >= 2:
            dps = sum(abs(a["dividendi"]) / a["az_fine"] for a in B[1:] if _ok(g(a, "dividendi")))
            out["G1"] = cagr(B[0]["patr"] / B[0]["az_fine"], B[-1]["patr"] / B[-1]["az_fine"] + dps,
                             anni_tra(B[0]["data"], B[-1]["data"]))
        else:
            out["G1"] = None
    else:
        out["G1"] = out["cagr_ricavi"]
    E = [a for a in A if _ok(g(a, "eps"))]
    out["G2"] = cagr(E[0]["eps"], E[-1]["eps"], anni_tra(E[0]["data"], E[-1]["data"])) if len(E) >= 2 else None
    Z = [a for a in A if _ok(g(a, "az_dil")) and a["az_dil"] > 0]
    out["G3"] = cagr(Z[0]["az_dil"], Z[-1]["az_dil"], anni_tra(Z[0]["data"], Z[-1]["data"])) if len(Z) >= 2 else None
    if not fin and len(cap_s) >= 2 and cap_s[-1] - cap_s[0] > 0.01 * abs(cap_s[0]):
        out["G4"] = (nopat_s[-1] - nopat_s[0]) / (cap_s[-1] - cap_s[0])
    else:
        out["G4"] = None

    # ---- flusso normalizzato (margine medio degli ultimi 3 esercizi, tutti per i ciclici, x ricavi recenti)
    def flusso(a):
        if modello in ("STD", "CIC"):
            return a["fcf"] - (g(a, "sbc") or 0.0) if _ok(g(a, "fcf")) else None
        if modello == "REIT":
            return ffo(a)
        return g(a, "utile")

    if fin:
        out["flusso_norm"] = out["roe_norm"] * U["patr"] if _ok(out["roe_norm"], g(U, "patr")) else None
    else:
        R = [a for a in A if _ok(flusso(a), g(a, "ricavi")) and a["ricavi"] > 0 and _ok(g(a, "ebit"))]
        if modello != "CIC":
            R = R[-3:]
        m = media([flusso(a) / a["ricavi"] for a in R])
        out["flusso_norm"] = m * U["ricavi"] if _ok(m, g(U, "ricavi")) else None
        out["flusso_anni"] = len(R)
    out["sbc_disponibile"] = any(_ok(g(a, "sbc")) for a in Y)
    out["tbv"] = g(U, "tbv") if g(U, "tbv") is not None else (
        U["patr"] - U["avviamento"] if _ok(g(U, "patr"), g(U, "avviamento")) else None)
    out["patr"] = g(U, "patr")
    out["utile_ultimo"] = g(U, "utile")
    out["cassa_netta"] = -deb_netto if deb_netto is not None else None
    return out


# ------------------------------------------------------------------ lettura dall'archivio
def carica_esercizi(con, ticker: str) -> tuple[list[dict], list[str]]:
    """Esercizi annuali da Yahoo, allungati con SEC dove coerente. -> (anni, note)"""
    righe = con.execute("SELECT prospetto, data_chiusura, voce, valore, fonte FROM bilanci "
                        "WHERE ticker=? AND frequenza='A'", (ticker,)).fetchall()
    y: dict[tuple, float] = {}
    s: dict[tuple, float] = {}
    for p, d, v, x, f in righe:
        (y if f == "yahoo" else s)[(p, d, v)] = x
    date_y = sorted({d for (p, d, v) in y})
    anni: dict[str, dict] = {}
    for d in date_y:
        a = {"data": d}
        for campo, (p, voci) in VOCI.items():
            a[campo] = next((y[(p, d, v)] for v in voci if (p, d, v) in y), None)
        anni[d] = a
    note = []
    for campo, (p, voce) in VOCI_SEC.items():
        ser = {d: x for (pp, d, v), x in s.items() if pp == p and v == voce}
        if not ser:
            continue
        campo_y = "cassa" if campo == "cassa_sec" else campo
        voce_y = VOCI[campo_y][1] if campo != "cassa_sec" else ["CashAndCashEquivalents"]
        if campo == "utile":
            voce_y = ["NetIncome"]
        comuni = [(ser[d], next((y[(p, d, v)] for v in voce_y if (p, d, v) in y), None)) for d in ser if d in anni]
        scarti = sorted(abs(a / b - 1) for a, b in comuni if b)
        if len(scarti) < 2 or scarti[len(scarti) // 2] > 0.02:
            note.append(f"SEC {voce}: non usata (non coerente con Yahoo sugli esercizi in comune)")
            continue
        primo_y = min(d for d in anni if anni[d].get(campo_y) is not None) if any(
            anni[d].get(campo_y) is not None for d in anni) else "9999"
        for d, x in ser.items():
            if d < primo_y:
                anni.setdefault(d, {"data": d})[campo_y] = x
    ordinati = [anni[d] for d in sorted(anni)]
    # tiene solo gli esercizi contigui annuali (scarta date SEC fuori calendario)
    if ordinati:
        mese = ordinati[-1]["data"][5:7]
        ordinati = [a for a in ordinati if a["data"][5:7] == mese]
    return ordinati[-(MAX_ANNI + 1):], note


def dividendi_da_prezzi(con, ticker: str, anni: list[dict], k_quot_a_bil: float) -> None:
    """Se il rendiconto non riporta i dividendi pagati, li stima dai dividendi per azione staccati
    nell'esercizio (storico prezzi) x azioni a fine esercizio, convertiti nella valuta di bilancio."""
    for i, a in enumerate(anni):
        if a.get("dividendi") is not None or a.get("fcf") is None or not a.get("az_fine"):
            continue
        inizio = anni[i - 1]["data"] if i > 0 else f"{int(a['data'][:4]) - 1}{a['data'][4:]}"
        dps = con.execute("SELECT SUM(dividendo) FROM prezzi WHERE ticker=? AND data>? AND data<=?",
                          (ticker, inizio, a["data"])).fetchone()[0]
        if dps:
            a["dividendi"] = -dps * a["az_fine"] * k_quot_a_bil
            a["dividendi_stimati"] = True
