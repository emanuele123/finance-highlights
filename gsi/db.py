"""Archivio SQLite locale (un solo file)."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS prezzi(
  ticker TEXT NOT NULL, data TEXT NOT NULL,
  apertura REAL, massimo REAL, minimo REAL, chiusura REAL, chiusura_rett REAL,
  volume REAL, dividendo REAL DEFAULT 0, frazionamento REAL DEFAULT 0,
  PRIMARY KEY(ticker, data)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS anagrafica(
  ticker TEXT PRIMARY KEY, tipo TEXT, nome_fonte TEXT, valuta_fonte TEXT,
  valuta_bilancio_fonte TEXT, borsa TEXT, paese TEXT, settore_fonte TEXT, industria_fonte TEXT,
  capitalizzazione REAL, prezzo_fonte REAL, azioni_fonte REAL, beta REAL,
  eps_atteso REAL, eps_storico REAL, json TEXT, aggiornato TEXT);
CREATE TABLE IF NOT EXISTS bilanci(
  ticker TEXT NOT NULL, prospetto TEXT NOT NULL,   -- CE conto economico, SP stato patrimoniale, RF rendiconto
  frequenza TEXT NOT NULL,                         -- A annuale, T trimestrale, U ultimi 12 mesi
  data_chiusura TEXT NOT NULL, voce TEXT NOT NULL, valore REAL, fonte TEXT NOT NULL DEFAULT 'yahoo',
  PRIMARY KEY(ticker, prospetto, frequenza, data_chiusura, voce, fonte)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS date_utili(
  ticker TEXT NOT NULL, data TEXT NOT NULL, ora TEXT, eps_stima REAL, eps_reale REAL, sorpresa_pct REAL,
  PRIMARY KEY(ticker, data)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS revisioni(
  ticker TEXT NOT NULL, periodo TEXT NOT NULL, su_7g REAL, su_30g REAL, giu_7g REAL, giu_30g REAL,
  rilevato TEXT, PRIMARY KEY(ticker, periodo)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS notizie(
  ticker TEXT NOT NULL, url TEXT NOT NULL, titolo TEXT, testata TEXT, pubblicato TEXT,
  fonte TEXT, lingua TEXT, raccolto TEXT, PRIMARY KEY(ticker, url)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS cambi(
  data TEXT NOT NULL, valuta TEXT NOT NULL, tasso REAL NOT NULL,  -- unita di valuta per 1 euro
  fonte TEXT, PRIMARY KEY(valuta, data)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS scarichi(
  ticker TEXT NOT NULL, oggetto TEXT NOT NULL, ultimo_ok TEXT, righe INTEGER,
  PRIMARY KEY(ticker, oggetto)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS errori(
  quando TEXT, ticker TEXT, oggetto TEXT, messaggio TEXT);
CREATE TABLE IF NOT EXISTS qualita(
  ticker TEXT PRIMARY KEY, stato TEXT, motivi TEXT, ultimo_prezzo TEXT, n_prezzi INTEGER,
  ultimo_esercizio TEXT, n_esercizi INTEGER, n_trimestri INTEGER, ha_ttm INTEGER, controllato TEXT);
CREATE TABLE IF NOT EXISTS meta(chiave TEXT PRIMARY KEY, valore TEXT);
"""


def adesso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def apri(percorso: Path | str) -> sqlite3.Connection:
    if str(percorso) != ":memory:":
        Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(percorso))
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def registra_errore(con, ticker: str, oggetto: str, messaggio: str) -> None:
    con.execute("INSERT INTO errori VALUES(?,?,?,?)", (adesso(), ticker, oggetto, str(messaggio)[:500]))
    con.commit()


def segna_scarico(con, ticker: str, oggetto: str, righe: int) -> None:
    con.execute("INSERT OR REPLACE INTO scarichi VALUES(?,?,?,?)", (ticker, oggetto, adesso(), righe))


def ultimo_scarico(con, ticker: str, oggetto: str) -> str | None:
    r = con.execute("SELECT ultimo_ok FROM scarichi WHERE ticker=? AND oggetto=?", (ticker, oggetto)).fetchone()
    return r[0] if r else None
