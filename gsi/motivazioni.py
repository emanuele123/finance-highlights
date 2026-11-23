"""'Perche' questo verdetto' secondo la strategia A: testo costruito solo dai numeri del Buffett Score.

Lo stesso testo e' prodotto in due modi che devono coincidere: dalle formule del foglio BUFFETT (cosi' si aggiorna
quando cambiano parametri e giudizi) e da `motivazione()` in Python, usata dal controllo incrociato.
Il testo descrive i numeri: non considera concorrenza, tecnologia o notizie.
"""
from __future__ import annotations

from .parametri import FINANZIARI, METRICHE_A, NOMI_PILASTRI_A
from .punteggi import arrotonda

METRICHE_MOTIVO = [m for m in METRICHE_A if m[0] != "V"]


def t(x: float, d: int) -> str:
    """Numero come lo scrive Excel concatenando ROUND(x, d): niente zeri finali, punto decimale."""
    r = arrotonda(x, d)
    if r == int(r):
        return str(int(r))
    return (f"%.{d}f" % r).rstrip("0").rstrip(".")


def _pct(x):
    return t(x * 100, 0) + "%"


def _segno(x):
    return ("+" if x >= 0 else "") + t(x * 100, 1) + "%"


def frase(m: str, v: float, mod: str) -> str:
    fin = mod in FINANZIARI
    if m == "Q1":
        return ("ROE medio " if fin else "rendimento sul capitale medio ") + _pct(v)
    if m == "Q2":
        return ("ROE nell'anno peggiore " if fin else "rendimento sul capitale nell'anno peggiore ") + _pct(v)
    if m == "Q3":
        return {"BAN": "cost/income ", "ASS": "combined ratio "}.get(mod, "margine operativo medio ") + _pct(v)
    if m == "Q4":
        return ("variabilità del ROE di " if fin else "variabilità del margine operativo di ") + t(v * 100, 1) + " punti"
    if m == "Q5":
        return "ricavi in crescita nel " + _pct(v) + " degli anni"
    if m == "Q6":
        return "margine lordo " + _pct(v)
    if m == "F1":
        if fin:
            return "patrimonio pari al " + _pct(v) + " dell'attivo"
        if v >= 99:
            return "EBITDA negativo"
        if v < 0:
            return "più cassa che debiti"
        if t(v, 1) == "0":
            return "debito netto quasi nullo"
        return "debito netto pari a " + t(v, 1) + " volte l'EBITDA"
    if m == "F2":
        return "interessi coperti dalla cassa netta" if v >= 99 else "utile operativo pari a " + t(v, 1) + " volte gli interessi"
    if m == "F3":
        return "cassa generata pari al " + _pct(v) + " degli utili"
    if m == "F4":
        if v >= 9.99:
            return "dividendi non coperti"
        base = " del free cash flow" if mod in ("STD", "CIC") else " dell'FFO" if mod == "REIT" else " degli utili"
        return "dividendi pari al " + _pct(v) + base
    if m == "F5":
        return ("CET1 " if mod == "BAN" else "Solvency II ") + _pct(v)
    if m == "G1":
        return ("patrimonio per azione più dividendi " if fin else "ricavi ") + _segno(v) + " l'anno"
    if m == "G2":
        return "utile per azione " + _segno(v) + " l'anno"
    if m == "G3":
        if t(v * 100, 1) == "0":
            return "numero di azioni stabile"
        if v <= 0:
            return "azioni in calo del " + t(-v * 100, 1) + "% l'anno (riacquisti)"
        return "azioni in aumento del " + t(v * 100, 1) + "% l'anno (diluizione)"
    if m == "G4":
        return "rendimento sugli investimenti aggiuntivi " + _pct(v)
    raise KeyError(m)


def motivazione(ing: dict, a: dict, P: dict, giudizio: dict | None = None) -> dict:
    mod, val, pun = ing["modello"], a["valori"], a["punti"]
    forti = [frase(m, val[m], mod) for m in METRICHE_MOTIVO if pun.get(m) is not None and pun[m] >= P["motivo_forte"] - 1e-9]
    deboli = [frase(m, val[m], mod) for m in METRICHE_MOTIVO if pun.get(m) is not None and pun[m] <= P["motivo_debole"] + 1e-9]
    qc = a["qualita_composita"]
    q = (f"Qualità: classe {a['classe']} ({t(qc, 1)}/100)." if qc is not None else "Qualità: non valutabile (dati insufficienti).")
    q += " Punti di forza: " + ("; ".join(forti) or "nessuno in particolare") + "."
    q += " Punti deboli: " + ("; ".join(deboli) or "nessuno in particolare") + "."
    ver, prezzo, base = a["verdetto"], ing.get("prezzo"), a["valore_base"]
    if ver in ("Comprerei", "Aspetterei"):
        vp, vo = a["scenari"]["Prudente"]["valore"], a["scenari"]["Ottimistico"]["valore"]
        v = (f"Valutazione: prezzo {t(prezzo, 2)} contro un valore stimato di {t(base, 2)} (scenario base; prudente "
             f"{t(vp, 2)}, ottimistico {t(vo, 2)}). Margine di sicurezza {_pct(a['margine_sicurezza'])}, ")
        req = P["margine_a"] if a["classe"] == "A" else P["margine_b"]
        if ver == "Comprerei":
            v += (f"sopra il {_pct(req)} richiesto per la classe {a['classe']}: il prezzo è sotto il prezzo d'acquisto di "
                  f"{t(a['prezzo_acquisto'], 2)}, quindi per questa strategia è un acquisto.")
        else:
            v += (f"sotto il {_pct(req)} richiesto per la classe {a['classe']}: per comprare il prezzo dovrebbe scendere a "
                  f"{t(a['prezzo_acquisto'], 2)} ({t((a['prezzo_acquisto'] / prezzo - 1) * 100, 0)}% da oggi).")
        if vp < prezzo:
            v += f" Attenzione: nello scenario prudente il valore ({t(vp, 2)}) è sotto il prezzo attuale."
    elif ver == "Non comprerei: qualità insufficiente":
        v = (f"Valutazione: non rilevante. La qualità composita ({t(qc, 1)}) è sotto la soglia di {t(P['classe_b'], 1)} "
             "della classe B: per questa strategia l'azienda non è abbastanza buona a nessun prezzo.")
    elif ver == "Non comprerei: valore non stimabile":
        v = ("Valutazione: il flusso di cassa normalizzato è negativo, quindi il valore intrinseco non è stimabile "
             "e la strategia non compra.")
    elif ing.get("prezzo_vecchio") or ing.get("esercizio_vecchio"):
        v = "Valutazione: non eseguita, perché il prezzo o l'ultimo bilancio sono troppo vecchi."
    else:
        manca = [NOMI_PILASTRI_A[L] for L in "QFGV" if a["pilastri"][L] is None]
        v = ("Valutazione: non eseguita, perché mancano troppi dati nei pilastri: " + ", ".join(manca) + "."
             if manca else "Valutazione: non eseguita, perché manca il valore intrinseco.")
    righe = [q, v]
    if a["correzione"]:
        mot = (giudizio or {}).get("motivazione") or "senza motivazione"
        righe.append(f"Correzione qualitativa: {'+' if a['correzione'] > 0 else ''}{t(a['correzione'], 1)} punti ({mot}).")
    if a["rischi"]:
        righe.append("Segnali di rischio: " + "; ".join(a["rischi"]) + ".")
    return {"forti": "; ".join(forti), "deboli": "; ".join(deboli), "testo": "\n".join(righe)}


# ------------------------------------------------------------------ le stesse frasi come formule del foglio BUFFETT
def _xpct(c):
    return f'ROUND({c}*100,0)&"%"'


def _xsegno(c):
    return f'IF({c}>=0,"+","")&ROUND({c}*100,1)&"%"'


def formula_frase(m: str) -> str:
    v = "{v_" + m + "}"
    fin = "{fin}=1"
    f = {
        "Q1": f'IF({fin},"ROE medio ","rendimento sul capitale medio ")&{_xpct(v)}',
        "Q2": f'IF({fin},"ROE nell\'anno peggiore ","rendimento sul capitale nell\'anno peggiore ")&{_xpct(v)}',
        "Q3": f'IF({{modello}}="BAN","cost/income ",IF({{modello}}="ASS","combined ratio ","margine operativo medio "))&{_xpct(v)}',
        "Q4": f'IF({fin},"variabilità del ROE di ","variabilità del margine operativo di ")&ROUND({v}*100,1)&" punti"',
        "Q5": f'"ricavi in crescita nel "&{_xpct(v)}&" degli anni"',
        "Q6": f'"margine lordo "&{_xpct(v)}',
        "F1": f'IF({fin},"patrimonio pari al "&{_xpct(v)}&" dell\'attivo",IF({v}>=99,"EBITDA negativo",IF({v}<0,'
              f'"più cassa che debiti",IF(ROUND({v},1)=0,"debito netto quasi nullo","debito netto pari a "&ROUND({v},1)&" volte l\'EBITDA"))))',
        "F2": f'IF({v}>=99,"interessi coperti dalla cassa netta","utile operativo pari a "&ROUND({v},1)&" volte gli interessi")',
        "F3": f'"cassa generata pari al "&{_xpct(v)}&" degli utili"',
        "F4": f'IF({v}>=9.99,"dividendi non coperti","dividendi pari al "&{_xpct(v)}&IF(OR({{modello}}="STD",{{modello}}="CIC"),'
              f'" del free cash flow",IF({{modello}}="REIT"," dell\'FFO"," degli utili")))',
        "F5": f'IF({{modello}}="BAN","CET1 ","Solvency II ")&{_xpct(v)}',
        "G1": f'IF({fin},"patrimonio per azione più dividendi ","ricavi ")&{_xsegno(v)}&" l\'anno"',
        "G2": f'"utile per azione "&{_xsegno(v)}&" l\'anno"',
        "G3": f'IF(ROUND({v}*100,1)=0,"numero di azioni stabile",IF({v}<=0,"azioni in calo del "&ROUND(-{v}*100,1)&"% l\'anno (riacquisti)",'
              f'"azioni in aumento del "&ROUND({v}*100,1)&"% l\'anno (diluizione)"))',
        "G4": f'"rendimento sugli investimenti aggiuntivi "&{_xpct(v)}',
    }[m]
    return f'=IF(ISNUMBER({v}),{f},"")'


def formula_lista(confronto: str, soglia: str) -> str:
    soglia = f"({soglia}-1E-9)" if confronto == ">=" else f"({soglia}+1E-9)"   # stessa tolleranza del calcolo Python
    parti = [f'IF(ISNUMBER({{p_{m}}}),IF({{p_{m}}}{confronto}{soglia},{{fr_{m}}}&"; ",""),"")' for m in METRICHE_MOTIVO]
    return "=" + "&".join(parti)


def formula_qualita() -> str:
    return ('=IF(ISNUMBER({qc}),"Qualità: classe "&{classe}&" ("&ROUND({qc},1)&"/100).","Qualità: non valutabile (dati insufficienti).")'
            '&" Punti di forza: "&IF({forti}="","nessuno in particolare",{forti})&"."'
            '&" Punti deboli: "&IF({deboli}="","nessuno in particolare",{deboli})&"."')


def formula_valutazione() -> str:
    prima = ('"Valutazione: prezzo "&ROUND({prezzo},2)&" contro un valore stimato di "&ROUND({valore_base},2)'
             '&" (scenario base; prudente "&ROUND({V:valore_p},2)&", ottimistico "&ROUND({V:valore_o},2)'
             '&"). Margine di sicurezza "&ROUND({margine}*100,0)&"%, "')
    compra = ('"sopra il "&ROUND({richiesto}*100,0)&"% richiesto per la classe "&{classe}&": il prezzo è sotto il prezzo '
              'd\'acquisto di "&ROUND({prezzo_acq},2)&", quindi per questa strategia è un acquisto."')
    aspetta = ('"sotto il "&ROUND({richiesto}*100,0)&"% richiesto per la classe "&{classe}&": per comprare il prezzo dovrebbe '
               'scendere a "&ROUND({prezzo_acq},2)&" ("&ROUND(({prezzo_acq}/{prezzo}-1)*100,0)&"% da oggi)."')
    prud = ('IF({V:valore_p}<{prezzo}," Attenzione: nello scenario prudente il valore ("&ROUND({V:valore_p},2)'
            '&") è sotto il prezzo attuale.","")')
    manca = ('IF(ISNUMBER({pil_Q}),"","' + NOMI_PILASTRI_A["Q"] + ', ")&IF(ISNUMBER({pil_F}),"","' + NOMI_PILASTRI_A["F"]
             + ', ")&IF(ISNUMBER({pil_G}),"","' + NOMI_PILASTRI_A["G"] + ', ")&IF(ISNUMBER({pil_V}),"","'
             + NOMI_PILASTRI_A["V"] + ', ")')
    return ('=IF(OR({verdetto}="Comprerei",{verdetto}="Aspetterei"),' + prima + '&IF({verdetto}="Comprerei",' + compra + ','
            + aspetta + ')&' + prud + ',IF({verdetto}="Non comprerei: qualità insufficiente","Valutazione: non rilevante. '
            'La qualità composita ("&ROUND({qc},1)&") è sotto la soglia di "&ROUND({P:classe_b},1)&" della classe B: per questa '
            'strategia l\'azienda non è abbastanza buona a nessun prezzo.",IF({verdetto}="Non comprerei: valore non stimabile",'
            '"Valutazione: il flusso di cassa normalizzato è negativo, quindi il valore intrinseco non è stimabile e la strategia '
            'non compra.",IF({vecchio}=1,"Valutazione: non eseguita, perché il prezzo o l\'ultimo bilancio sono troppo vecchi.",'
            'IF(LEN(' + manca + ')>0,"Valutazione: non eseguita, perché mancano troppi dati nei pilastri: "&LEFT(' + manca
            + ',LEN(' + manca + ')-2)&".","Valutazione: non eseguita, perché manca il valore intrinseco.")))))')


def formula_testo() -> str:
    return ('={mot_q}&CHAR(10)&{mot_v}&IF({corr}<>0,CHAR(10)&"Correzione qualitativa: "&IF({corr}>0,"+","")&ROUND({corr},1)'
            '&" punti ("&IF({G:motivazione}="","senza motivazione",{G:motivazione})&").","")'
            '&IF({n_rischi}>0,CHAR(10)&"Segnali di rischio: "&{rischi}&".","")')
