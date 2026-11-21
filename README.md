# Global Stock Intelligence

Strumento personale per scegliere azioni: un programma Python scarica i dati di 120 titoli
in un archivio locale e genera un cruscotto Excel con formule.

**Non è consulenza finanziaria.** I punteggi ordinano i titoli secondo criteri dichiarati, non sono previsioni.
I dati Yahoo sono consentiti per il solo uso personale.

## Stato del progetto

| Fase | Contenuto | Stato |
|------|-----------|-------|
| 1 | Universo e scaricamento dei dati | fatta |
| 2 | Indicatori, metriche e punteggi in Python | fatta |
| 3 | Cruscotto Excel con formule | da fare |
| 4 | Movimenti, portafoglio, simulatore, backtest, manuale | da fare |

Oggi funzionano `aggiorna` (scarica i dati) e `punteggi` (calcola le due classifiche e le scrive in un file CSV
apribile con Excel). **Il cruscotto Excel con le formule non viene ancora creato.**

## Installazione (una volta sola)

1. Installare Python 3.10 o successivo da https://www.python.org/downloads/
   (su Windows spuntare "Add Python to PATH").
2. Scaricare questa cartella sul computer (pulsante verde "Code" > "Download ZIP" su GitHub, poi estrarre).
3. Aprire il terminale nella cartella (Windows: clic destro nella cartella > "Apri nel terminale") e scrivere:

       pip install -r requirements.txt

## Uso

    python avvia.py aggiorna                 scarica prezzi, bilanci, cambi, notizie (circa 20 minuti)
    python avvia.py aggiorna --solo-prezzi   scarica solo prezzi e cambi (circa 5 minuti)
    python avvia.py aggiorna --titoli AAPL,ENEL.MI   prova su pochi titoli

    python avvia.py punteggi                 calcola Buffett Score e Trading Score; tabella in dati/punteggi.csv

Su Mac scrivere `python3` al posto di `python`.

Alla fine compare un riepilogo: quanti titoli hanno prezzi e bilanci e quali sono "DA VERIFICARE", con il motivo.
I dati finiscono in `dati/archivio.sqlite`. I bilanci si riscaricano solo dopo 7 giorni; i prezzi ogni volta.

I comandi `excel`, `backtest` e `demo` arriveranno con le fasi successive.

### SEC EDGAR (facoltativo)

Per allungare a 10 anni la storia delle società americane, creare nella cartella un file
`configurazione.ini` con il proprio nome ed e-mail (lo richiede la SEC):

    [sec]
    user_agent = Nome Cognome nome@esempio.it

Verificata in rete il 21/11/2026: dati 10-K per 36 società. Le serie SEC si usano solo se coincidono
con Yahoo sugli esercizi in comune.

## Collaudi

    python -m pytest -q tests
