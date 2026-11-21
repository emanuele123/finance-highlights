"""Comando `aggiorna`: scarica tutto nell'archivio e controlla la qualita' titolo per titolo.
Ogni errore e' registrato per titolo e non ferma gli altri."""
from __future__ import annotations
import sys
import time
from datetime import date, datetime, timezone

from . import config, db
from .controlli import nome_somiglia, salti_anomali, valuta_titolo, valuta_unita
from .fonti import bce, sec, yahoo
from .universo import ETF, INDICI, NOMI_ALTERNATIVI, UNIVERSO, VALUTA_BILANCIO_VERIFICATA


def _log(msg: str) -> None:
    print(msg, flush=True)


def _eta_giorni(iso: str | None) -> float:
    if not iso:
        return 1e9
    t = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() / 86400


def _prova(con, ticker, oggetto, funzione):
    """Esegue un passo; in caso di errore lo registra e restituisce None."""
    try:
        return funzione()
    except Exception as e:  # noqa: BLE001
        db.registra_errore(con, ticker, oggetto, f"{type(e).__name__}: {e}")
        return None


def salva_prezzi(con, ticker: str, righe: list[tuple]) -> None:
    """Sostituisce l'intero storico: dividendi e frazionamenti cambiano i prezzi rettificati all'indietro."""
    with con:
        con.execute("DELETE FROM prezzi WHERE ticker=?", (ticker,))
        con.executemany("INSERT OR REPLACE INTO prezzi VALUES(?,?,?,?,?,?,?,?,?,?)",
                        [(ticker, *r) for r in righe])
        db.segna_scarico(con, ticker, "prezzi", len(righe))


def scarica_prezzi(con, ticker: str, yf) -> dict:
    tk = yf.Ticker(ticker)
    esito = _prova(con, ticker, "prezzi", lambda: yahoo.scarica_storico(tk))
    if esito is None:
        return {}
    df, meta = esito
    _, cent = valuta_unita(meta.get("currency"))
    righe = yahoo.normalizza_storico(df, cent, meta)
    if not righe:
        db.registra_errore(con, ticker, "prezzi", "storico vuoto")
        return meta
    salva_prezzi(con, ticker, righe)
    return meta


def scarica_fondamentali(con, t, yf, meta: dict, forza: bool) -> None:
    tk = yf.Ticker(t.ticker)
    ana = _prova(con, t.ticker, "anagrafica", lambda: yahoo.scarica_anagrafica(tk, meta))
    if ana:
        with con:
            con.execute("INSERT OR REPLACE INTO anagrafica VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (t.ticker, ana["tipo"], ana["nome_fonte"], ana["valuta_fonte"],
                         ana["valuta_bilancio_fonte"], ana["borsa"], ana["paese"], ana["settore_fonte"],
                         ana["industria_fonte"], ana["capitalizzazione"], ana["prezzo_fonte"],
                         ana["azioni_fonte"], ana["beta"], ana["eps_atteso"], ana["eps_storico"],
                         ana["json"], db.adesso()))
            db.segna_scarico(con, t.ticker, "anagrafica", 1)
    if forza or _eta_giorni(db.ultimo_scarico(con, t.ticker, "bilanci")) >= config.GIORNI_BILANCI:
        tot, annuali_ok = 0, False
        for prospetto in yahoo.PROSPETTI:
            for freq in yahoo.FREQUENZE:
                if prospetto == "SP" and freq == "U":
                    continue
                righe = _prova(con, t.ticker, f"bilancio {prospetto}/{freq}",
                               lambda p=prospetto, f=freq: yahoo.scarica_prospetto(tk, p, f))
                if not righe:
                    if righe is not None:
                        db.registra_errore(con, t.ticker, f"bilancio {prospetto}/{freq}", "prospetto vuoto")
                    continue
                with con:
                    con.execute("DELETE FROM bilanci WHERE ticker=? AND prospetto=? AND frequenza=? AND fonte='yahoo'",
                                (t.ticker, prospetto, freq))
                    con.executemany("INSERT OR REPLACE INTO bilanci VALUES(?,?,?,?,?,?,'yahoo')",
                                    [(t.ticker, prospetto, freq, d, v, x) for d, v, x in righe])
                tot += len(righe)
                annuali_ok = annuali_ok or freq == "A"
        if annuali_ok:
            with con:
                db.segna_scarico(con, t.ticker, "bilanci", tot)
    r = _prova(con, t.ticker, "date utili", lambda: yahoo.scarica_date_utili(tk))
    if r:
        with con:
            con.executemany("INSERT OR REPLACE INTO date_utili VALUES(?,?,?,?,?,?)", [(t.ticker, *x) for x in r])
            db.segna_scarico(con, t.ticker, "date utili", len(r))
    r = _prova(con, t.ticker, "revisioni", lambda: yahoo.scarica_revisioni(tk))
    if r:
        with con:
            con.execute("DELETE FROM revisioni WHERE ticker=?", (t.ticker,))
            con.executemany("INSERT INTO revisioni VALUES(?,?,?,?,?,?,?)", [(t.ticker, *x, db.adesso()) for x in r])
            db.segna_scarico(con, t.ticker, "revisioni", len(r))
    r = _prova(con, t.ticker, "notizie", lambda: yahoo.scarica_notizie(tk))
    if r:
        with con:
            con.executemany("INSERT OR IGNORE INTO notizie VALUES(?,?,?,?,?,'yahoo',NULL,?)",
                            [(t.ticker, u, ti, te, p, db.adesso()) for u, ti, te, p in r])
            db.segna_scarico(con, t.ticker, "notizie", len(r))


def scarica_cambi(con, yf) -> None:
    servono = ({t.valuta for t in UNIVERSO} | {t.valuta_bilancio for t in UNIVERSO}
               | {r[0] for r in con.execute("SELECT DISTINCT valuta_bilancio_fonte FROM anagrafica "
                                            "WHERE valuta_bilancio_fonte IS NOT NULL")}
               | {v for _, v in INDICI.values()}) - {"EUR"}
    presenti: set[str] = set()
    grezzo = _prova(con, "BCE", "cambi", bce.scarica)
    if grezzo:
        presenti = bce.valute_disponibili(grezzo) & servono
        righe = bce.leggi_zip(grezzo, presenti)
        with con:
            con.executemany("INSERT OR REPLACE INTO cambi VALUES(?,?,?,'BCE')", [(d, v, x) for d, v, x in righe])
            db.segna_scarico(con, "BCE", "cambi", len(righe))
        _log(f"  Cambi BCE: {len(righe)} righe per {len(presenti)} valute")
    for val in sorted(servono - presenti):   # es. TWD: la BCE non lo pubblica
        simbolo = f"EUR{val}=X"
        esito = _prova(con, simbolo, "cambi", lambda s=simbolo: yahoo.scarica_storico(yf.Ticker(s)))
        righe = yahoo.normalizza_storico(esito[0], False, esito[1]) if esito else []
        if righe:
            with con:
                con.execute("DELETE FROM cambi WHERE valuta=? AND fonte='Yahoo'", (val,))
                con.executemany("INSERT OR REPLACE INTO cambi VALUES(?,?,?,'Yahoo')",
                                [(r[0], val, r[4]) for r in righe])
                db.segna_scarico(con, simbolo, "cambi", len(righe))
            _log(f"  Cambio {val} da Yahoo ({simbolo}): {len(righe)} righe")
        else:
            db.registra_errore(con, simbolo, "cambi", "cambio non disponibile")
            _log(f"  Cambio {val}: NON disponibile")


def scarica_sec(con) -> None:
    ua = config.sec_user_agent()
    if not ua:
        _log("  SEC EDGAR: non usata (User-Agent non impostato in configurazione.ini)")
        return
    mappa = _prova(con, "SEC", "elenco ticker", lambda: sec.mappa_cik(ua))
    if not mappa:
        return
    n = 0
    for t in UNIVERSO:
        if "." in t.ticker or t.valuta_bilancio != "USD":
            continue
        cik = mappa.get(t.ticker.upper())
        if not cik:
            continue
        fatti = _prova(con, t.ticker, "SEC companyfacts", lambda c=cik: sec.scarica_fatti(c, ua))
        if not fatti:
            continue
        righe = sec.estrai_annuali(fatti)
        if not righe:
            continue        # societa' senza 10-K (es. 20-F): nessun dato utile
        with con:
            con.execute("DELETE FROM bilanci WHERE ticker=? AND fonte='sec'", (t.ticker,))
            con.executemany("INSERT OR REPLACE INTO bilanci VALUES(?,?,'A',?,?,?,'sec')",
                            [(t.ticker, p, d, v, x) for p, d, v, x in righe])
            db.segna_scarico(con, t.ticker, "sec", len(righe))
        n += 1
    _log(f"  SEC EDGAR: dati 10-K per {n} societa'")


def controlla_qualita(con, oggi: date | None = None) -> None:
    oggi = oggi or date.today()
    voci = [(t.ticker, t.nome, t.valuta, t.in_centesimi, t.valuta_bilancio, True, "EQUITY") for t in UNIVERSO]
    voci += [(k, v[0], v[1], False, None, False, "INDEX") for k, v in INDICI.items()]
    voci += [(k, v[0], v[1], False, None, False, "ETF") for k, v in ETF.items()]
    for ticker, nome, valuta, cent, val_bil, bilanci, tipo in voci:
        pr = con.execute("SELECT data, chiusura FROM prezzi WHERE ticker=? ORDER BY data", (ticker,)).fetchall()
        ana = con.execute("SELECT * FROM anagrafica WHERE ticker=?", (ticker,)).fetchone()
        es = [r[0] for r in con.execute(
            "SELECT DISTINCT data_chiusura FROM bilanci WHERE ticker=? AND prospetto='CE' AND frequenza='A' "
            "AND fonte='yahoo' AND voce IN ('TotalRevenue','NetIncome') ORDER BY 1", (ticker,))]
        ntrim = con.execute("SELECT COUNT(DISTINCT data_chiusura) FROM bilanci WHERE ticker=? AND prospetto='CE' "
                            "AND frequenza='T'", (ticker,)).fetchone()[0]
        ttm = con.execute("SELECT COUNT(*) FROM bilanci WHERE ticker=? AND frequenza='U'", (ticker,)).fetchone()[0]
        val_bil_fonte = ana["valuta_bilancio_fonte"] if ana else None
        note = []
        if ticker in VALUTA_BILANCIO_VERIFICATA and val_bil_fonte != VALUTA_BILANCIO_VERIFICATA[ticker][0]:
            note.append("Nota: valuta di bilancio corretta a mano. " + VALUTA_BILANCIO_VERIFICATA[ticker][1])
            val_bil_fonte = VALUTA_BILANCIO_VERIFICATA[ticker][0]
        nome_fonte = ana["nome_fonte"] if ana else None
        alt = NOMI_ALTERNATIVI.get(ticker)
        if alt and nome_fonte and nome_somiglia(alt, nome_fonte):
            nome = nome_fonte                      # ragione sociale verificata
        incompleti = [r[0] for r in con.execute(
            "SELECT DISTINCT data_chiusura FROM bilanci WHERE ticker=? AND frequenza='A' AND fonte='yahoo' "
            "AND data_chiusura>?", (ticker, es[-1] if es else ""))]
        stato, motivi = valuta_titolo(
            oggi=oggi, n_prezzi=len(pr), ultimo_prezzo=pr[-1][0] if pr else None, valuta_attesa=valuta,
            centesimi_attesi=cent, valuta_fonte=ana["valuta_fonte"] if ana else None,
            valuta_bil_attesa=val_bil, valuta_bil_fonte=val_bil_fonte,
            nome_atteso=nome, nome_fonte=nome_fonte,
            salti=salti_anomali([(r[0], r[1]) for r in pr]), richiede_bilanci=bilanci,
            ultimo_esercizio=es[-1] if es else None, n_esercizi=len(es),
            tipo_fonte=ana["tipo"] if ana else None, tipo_atteso=tipo)
        if incompleti and bilanci:
            motivi.append(f"esercizio {incompleti[-1]} presente nella fonte ma incompleto (senza ricavi e utile)")
            stato = "DA VERIFICARE" if stato == "OK" else stato
        con.execute("INSERT OR REPLACE INTO qualita VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (ticker, stato, "; ".join(motivi + note), pr[-1][0] if pr else None, len(pr),
                     es[-1] if es else None, len(es), ntrim, 1 if ttm else 0, db.adesso()))
    con.commit()


def riepilogo(con) -> str:
    az = [t.ticker for t in UNIVERSO]
    q = {r["ticker"]: r for r in con.execute("SELECT * FROM qualita")}
    con_prezzo = [k for k in az if k in q and q[k]["n_prezzi"]]
    con_bil = [k for k in az if k in q and q[k]["n_esercizi"]]
    righe = [f"Titoli nell'universo: {len(az)}",
             f"  con prezzi: {len(con_prezzo)}   con bilanci annuali: {len(con_bil)}",
             f"  esito OK: {sum(1 for k in az if k in q and q[k]['stato'] == 'OK')}"
             f"   DA VERIFICARE: {sum(1 for k in az if k in q and q[k]['stato'] == 'DA VERIFICARE')}"
             f"   ERRORE: {sum(1 for k in az if k not in q or q[k]['stato'] == 'ERRORE')}"]
    for k in list(az) + list(INDICI) + list(ETF):
        if k in q and q[k]["stato"] != "OK":
            righe.append(f"  {q[k]['stato']:13s} {k:12s} {q[k]['motivi']}")
    return "\n".join(righe)


def esegui(solo_prezzi: bool = False, tickers: list[str] | None = None, forza_bilanci: bool = False,
           percorso_db=None) -> int:
    try:
        import yfinance as yf
    except ImportError:
        _log("Manca la libreria yfinance: eseguire  pip install -r requirements.txt")
        return 2
    con = db.apri(percorso_db or config.FILE_DB)
    inizio = time.time()
    con.execute("INSERT OR REPLACE INTO meta VALUES('aggiornamento_inizio', ?)", (db.adesso(),))
    con.execute("INSERT OR REPLACE INTO meta VALUES('yfinance_versione', ?)", (yf.__version__,))
    con.commit()
    validi = [t.ticker for t in UNIVERSO] + list(INDICI) + list(ETF)
    segni = ",".join("?" * len(validi))
    with con:   # elimina i dati di titoli usciti dall'universo
        for tab in ("prezzi", "bilanci", "anagrafica", "date_utili", "revisioni", "qualita", "scarichi"):
            filtro = " AND ticker NOT LIKE 'EUR%=X' AND ticker NOT IN ('BCE','SEC')" if tab == "scarichi" else ""
            con.execute(f"DELETE FROM {tab} WHERE ticker NOT IN ({segni}){filtro}", validi)
    titoli = [t for t in UNIVERSO if not tickers or t.ticker in tickers]
    _log(f"Aggiornamento di {len(titoli)} titoli (yfinance {yf.__version__})"
         + (" - solo prezzi" if solo_prezzi else ""))
    for i, t in enumerate(titoli, 1):
        meta = scarica_prezzi(con, t.ticker, yf)
        if not solo_prezzi:
            scarica_fondamentali(con, t, yf, meta, forza_bilanci)
        n = con.execute("SELECT COUNT(*) FROM prezzi WHERE ticker=?", (t.ticker,)).fetchone()[0]
        nb = con.execute("SELECT COUNT(*) FROM bilanci WHERE ticker=?", (t.ticker,)).fetchone()[0]
        _log(f"[{i:3d}/{len(titoli)}] {t.ticker:12s} prezzi: {n:5d}  voci di bilancio: {nb:5d}")
    if not tickers:
        _log("Indici, ETF e cambi...")
        for k in list(INDICI) + list(ETF):
            meta = scarica_prezzi(con, k, yf)
            if meta:
                with con:
                    con.execute("INSERT OR REPLACE INTO anagrafica(ticker,tipo,nome_fonte,valuta_fonte,borsa,aggiornato)"
                                " VALUES(?,?,?,?,?,?)",
                                (k, meta.get("instrumentType"), meta.get("longName") or meta.get("shortName"),
                                 meta.get("currency"), meta.get("fullExchangeName"), db.adesso()))
        scarica_cambi(con, yf)
        if not solo_prezzi:
            scarica_sec(con)
    controlla_qualita(con)
    con.execute("INSERT OR REPLACE INTO meta VALUES('aggiornamento_fine', ?)", (db.adesso(),))
    con.commit()
    _log("")
    _log(riepilogo(con))
    _log(f"Durata: {(time.time() - inizio) / 60:.1f} minuti. Archivio: {percorso_db or config.FILE_DB}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(esegui())
