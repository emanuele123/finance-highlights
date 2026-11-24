"""Fogli di documentazione: METODOLOGIA, FONTI, STATO, LEGGIMI."""
from __future__ import annotations

from openpyxl.styles import Alignment

from .excel import FASCIA, NERO, Libro, car, testata, titolo_foglio


def _testo(lib: Libro, nome: str, titolo: str, sotto: str, blocchi: list[tuple[str, list[str]]]):
    ws = lib.foglio(nome)
    titolo_foglio(ws, titolo, sotto)
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 150
    r = 3
    for intest, righe in blocchi:
        c = ws.cell(r, 2, intest)
        c.font, c.fill = car(NERO, True, 11), FASCIA
        r += 1
        for t in righe:
            c = ws.cell(r, 2, t)
            c.font = car()
            c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[r].height = 14 * max(1, -(-len(t) // 150))
            r += 1
        r += 1
    ws.sheet_view.showGridLines = False


def _tabella(lib: Libro, nome: str, titolo: str, sotto: str, intest: list[tuple[str, float]], righe: list[tuple]):
    ws = lib.foglio(nome)
    titolo_foglio(ws, titolo, sotto)
    for j, (h, w) in enumerate(intest, 1):
        testata(ws, 2, j, h, w)
    for i, riga in enumerate(righe):
        lunga = max(len(str(v)) / w for v, (_, w) in zip(riga, intest))
        ws.row_dimensions[3 + i].height = 14 * max(1, int(lunga) + 1)
        for j, v in enumerate(riga, 1):
            c = ws.cell(3 + i, j, v)
            c.font = car(NERO, j == 1)
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A3"


def foglio_metodologia(lib: Libro):
    _testo(lib, "METODOLOGIA", "METODOLOGIA - criteri e motivazione dei pesi",
           "Tutti i numeri citati sono nel foglio PARAMETRI e si possono cambiare.", [
        ("Principi generali", [
            "Due strategie, due punteggi, due classifiche: non vengono mai fuse, perché rispondono a domande diverse (che cosa possedere a lungo; che cosa si sta muovendo bene adesso).",
            "I punteggi ordinano i titoli secondo criteri dichiarati. Non sono previsioni e questo strumento non è consulenza finanziaria.",
            "Punteggio di una metrica: lineare tra una soglia che vale 0 punti e una che vale 100: 100 x max(0, min(1, (x - s0) / (s100 - s0))). Vale anche quando la soglia a 100 è più bassa di quella a 0 (metriche in cui meno è meglio).",
            "Un dato mancante è 'n.d.' e non vale mai punti: il pilastro è la media pesata delle sole metriche disponibili. Se i dati coprono meno del 60% del peso, il pilastro è 'Dati insufficienti' e il punteggio finale anche.",
            "Prezzo più vecchio di 5 giorni o ultimo esercizio più vecchio di 500 giorni: 'Dati insufficienti'. Completezza e freschezza si mostrano a parte (SCREENER, QUALITA_DATI) e non entrano nel punteggio.",
        ]),
        ("Strategia A - Buffett Score", [
            "Metodologia ispirata ai principi del value investing (buone aziende, solide, a un prezzo ragionevole). Nessun giudizio su singoli titoli è attribuibile a Warren Buffett.",
            "Quattro pilastri: Qualità del business (Q), Solidità finanziaria (F), Crescita e allocazione del capitale (G), Valutazione al prezzo corrente (V). Sei modelli, perché le stesse metriche non hanno senso per tutti: STD standard, CIC ciclico, UTL reti regolate, BAN banche, ASS assicurazioni, REIT immobiliare.",
            "Motivazione dei pesi dei pilastri. La Valutazione pesa 35-40% perché anche l'azienda migliore è un cattivo acquisto a qualunque prezzo; il resto va alla qualità in senso largo. Nel modello Standard la Qualità pesa il doppio della Solidità (30 contro 15) perché un'azienda con rendimenti alti e stabili ha meno bisogno di un bilancio blindato; nei ciclici, nelle reti e nelle banche la Solidità sale a 25 perché lì il debito (o il capitale) decide la sopravvivenza nei momenti difficili. La Crescita pesa poco (10-15) perché è il dato meno affidabile e più facile da pagare troppo.",
            "Motivazione dei pesi delle metriche. Nella Qualità pesano di più il rendimento sul capitale medio e nell'anno peggiore: misurano il vantaggio competitivo e la sua tenuta. Nella Solidità pesa di più la leva. Nella Valutazione il margine di sicurezza vale 60 su 100: è il confronto diretto tra prezzo e valore stimato; multipli e rendimento per l'azionista fanno da controllo.",
            "Qualità composita = media dei pilastri Q, F, G con i loro pesi. Classe A da 70, B da 55, altrimenti C.",
            "La Valutazione usata nel punteggio è min(V, Qualità composita + 20): un'azienda mediocre non scala la classifica solo perché costa poco.",
            "Buffett Score = media pesata di Qualità composita e Valutazione usata, più una correzione qualitativa manuale limitata a ±10 punti e sempre motivata (foglio GIUDIZI), arrotondato a un decimale.",
            "Verdetto: 'Comprerei' se il prezzo è sotto il prezzo d'acquisto = valore base x (1 - margine richiesto), con margine 25% per la classe A e 40% per la B; 'Aspetterei' altrimenti; 'Non comprerei: qualità insufficiente' per la classe C; 'Non comprerei: valore non stimabile' se i flussi sono negativi.",
        ]),
        ("Come sono calcolate le metriche di bilancio", [
            "Esercizi annuali disponibili: di norma 4 da Yahoo. Per le società che depositano il 10-K, la SEC allunga fino a 10 anni ricavi, utili, cassa e patrimonio, ma solo se coincidono con Yahoo sugli esercizi in comune.",
            "EBIT: voce 'EBIT' della fonte (utile ante imposte più oneri finanziari). Include proventi non operativi e svalutazioni: è il dato riportato, non rettificato.",
            "ROIC = EBIT x (1 - aliquota, tra 0 e 35%, 25% se manca) / media di (debito + patrimonio totale) a inizio e fine anno; per il primo esercizio disponibile si usa il valore di fine anno. Se il patrimonio è sotto il 10% dell'attivo (riacquisti): capitale = attivo - cassa - passività correnti non finanziarie. Banche e assicurazioni: ROE.",
            "Debito netto / EBITDA sul bilancio più recente, 99 se l'EBITDA è negativo. L'EBITDA è 'ordinario': tolte le componenti straordinarie indicate dalla fonte (svalutazioni, ristrutturazioni, plusvalenze).",
            "Copertura degli interessi = EBIT / oneri finanziari, 99 se c'è cassa netta. Stabilità dei margini = deviazione standard campionaria del margine operativo annuo (ROE per i finanziari), con almeno 3 esercizi.",
            "Flussi normalizzati: margine medio degli ultimi 3 esercizi (tutti per i ciclici) x ricavi più recenti. Standard e Ciclico: free cash flow meno compensi in azioni (se la fonte non li riporta non sono dedotti, ed è scritto nelle note). Reti: utile x 0,75. REIT: FFO (utile + ammortamenti - plusvalenze da cessioni) x 0,85. Finanziari: ROE normalizzato (media fino a 5 anni) x patrimonio.",
            "Azioni per i calcoli per azione = capitalizzazione / prezzo, così ADR e classi multiple tornano. I bilanci restano nella loro valuta per rapporti e crescite; le grandezze per azione si convertono nella valuta di quotazione al cambio più recente.",
            "P/E prospettico: prezzo / utile per azione atteso dal consenso per l'esercizio successivo, convertito dalla valuta dichiarata dalla fonte.",
            "Scelte dichiarate titolo per titolo (debito assunto zero, dividendi stimati, serie rettificate per frazionamenti...): colonna 'Note di calcolo' del foglio QUALITA_DATI.",
        ]),
        ("Valore intrinseco", [
            "Tre scenari (prudente, base, ottimistico) che cambiano: quota della crescita storica riconosciuta, fattore sugli utili, rendimento richiesto.",
            "Rendimento richiesto e crescita terminale dipendono dalla valuta di bilancio: sono IPOTESI dichiarate, non dati di mercato. Più 2 punti per l'area Emergenti. Crescita terminale mai oltre il rendimento richiesto meno 3 punti.",
            "Crescita storica = CAGR dei ricavi (reti: media tra ricavi e utile per azione), limitata tra -2% e il tetto del modello. Fase 1: crescita x quota se positiva, crescita x (2 - quota) se negativa.",
            "Modelli industriali: cinque anni alla crescita di fase 1, cinque alla media tra fase 1 e terminale, poi valore terminale di Gordon; tutto scontato al rendimento richiesto; più il 50% della cassa netta per azione se positiva. Flusso di partenza negativo: 'n.s.'.",
            "Banche e assicurazioni: patrimonio tangibile per azione + valore attuale di 10 anni di extra-rendimento (ROE - rendimento richiesto), con patrimonio che cresce di min(tetto, ROE x (1 - payout)). Mai sotto zero.",
            "Ogni passaggio è una colonna del foglio VALUTAZIONE.",
        ]),
        ("Prevedibilità a 10 anni (giudizio, non dato)", [
            "La domanda è: si può stimare con ragionevole fiducia quanto guadagnerà l'azienda tra 10 anni? I numeri passati dicono se un vantaggio competitivo c'è stato; la prevedibilità giudica se ci sarà ancora. Non dice se il titolo è caro.",
            "Alta: vantaggio durevole e comprovato, nessuna minaccia credibile in 10 anni. Media: vantaggio reale ma almeno una minaccia credibile (tecnologia, concorrenza, regolazione, brevetti, forte ciclicità). Bassa: futuro difficile da stimare (ciclo eccezionale o prezzi delle materie prime, tecnologia che cambia in fretta, rischi legali o geopolitici gravi, ristrutturazioni, scandali).",
            "Effetti (modificabili in PARAMETRI): Media = 15 punti di margine di sicurezza in più e metà della crescita futura riconosciuta; Bassa = nessuna crescita futura riconosciuta e verdetto 'Non comprerei: troppo difficile da prevedere', qualunque sia il prezzo. Il Buffett Score cambia solo attraverso la valutazione.",
            "I giudizi sono redatti da Claude dopo una ricerca su internet sui fatti recenti di ogni azienda e del suo mercato, con un criterio unico; fonti e date sono nel foglio PREVEDIBILITA. Sono opinioni: il proprio giudizio, scritto nel foglio GIUDIZI, prevale sempre.",
        ]),
        ("Catene del valore (descrizione, non entra nei punteggi)", [
            "Ogni titolo è collocato in un anello della catena del valore del suo mercato (23 catene), dal fornitore più a monte al cliente finale. Per ogni anello: che cosa succede, protagonisti, forza contrattuale verso fornitori e clienti; per ogni catena: dove si concentrano i profitti e che cosa sta cambiando.",
            "Struttura redatta da Claude; protagonisti, forza contrattuale e fatti completati con una ricerca su internet, con le fonti nel foglio MERCATI. Quote e numeri compaiono solo se trovati in una fonte.",
            "Il margine operativo e il rendimento sul capitale di ogni anello sono le mediane dei titoli dell'universo in quell'anello, calcolate con formule dai bilanci: non rappresentano l'intero mercato.",
            "Utilità: capire perché un'azienda ha margini alti o bassi (chi ha poca concorrenza nel proprio anello tiene i guadagni), da chi dipende, e se due titoli diversi dipendono dallo stesso ciclo (per esempio macchinari per chip, fabbricazione e progettazione dipendono tutti dagli investimenti dei centri dati).",
        ]),
        ("Perché questo verdetto (testo automatico)", [
            "Per ogni titolo un testo spiega il verdetto della strategia A usando solo i numeri del Buffett Score: classe e qualità composita; punti di forza (metriche con almeno 80 punti) e punti deboli (al massimo 30 punti), soglie modificabili in PARAMETRI; prezzo contro valore stimato nei tre scenari, margine di sicurezza e prezzo d'acquisto; correzione qualitativa e segnali di rischio.",
            "È scritto da formule (colonna nel foglio BUFFETT), quindi cambia da solo se cambiano parametri o giudizi, ed è controllato contro il calcolo del programma come i punteggi.",
            "Non è un'analisi: non conosce concorrenza, tecnologia, notizie o qualità del management. Un'azienda con bilanci eccellenti e prezzo sceso risulta un acquisto anche se il mercato teme che quei bilanci non si ripeteranno: è il proprio giudizio, nel foglio GIUDIZI, a dover tenere conto di queste cose.",
        ]),
        ("Strategia B - Trading Score", [
            "Indicatori sui prezzi rettificati per i frazionamenti; rendimenti e momentum sul total return, ricostruito dal programma a partire da chiusure e dividendi (la chiusura rettificata di Yahoo è sbagliata per i titoli quotati in pence e per chi paga dividendi in un'altra valuta). Finestre in sedute: 21, 63, 126, 252. Gli indici di riferimento sono indici di prezzo.",
            "Pilastri e pesi: Trend 25, Momentum 25, Forza relativa 15, Oscillatori 10, Volumi 10, Assetto e rischio 10, Catalizzatori 5. Servono Trend e Momentum e almeno il 70% del peso.",
            "Motivazione dei pesi: tendenza e momentum sono gli effetti più documentati e pesano metà del punteggio; la forza relativa li conferma rispetto a mercato e settore; oscillatori, volumi e assetto servono al momento d'ingresso; i catalizzatori pesano poco perché i dati gratuiti sono incompleti.",
            "Setup solo se prezzo > media 200 e media 50 > media 200. Rottura: massimo a 20 sedute distante al più 1 ATR, ingresso sopra quel massimo. Ritracciamento: prezzo tra le medie con RSI 40-60, ingresso al prezzo corrente. Stop = ingresso - 2 ATR. Obiettivo = ingresso + 2 volte il rischio, ridotto alla prima resistenza. Sotto 1,5 di rendimento/rischio il setup non è valido.",
            "Numero di azioni = min(capitale x 1% / rischio per azione in euro, capitale x 10% / prezzo in euro).",
            "L'obiettivo è una proiezione convenzionale, non una previsione. Nessuna probabilità: la frequenza storica del BACKTEST è mostrata solo con almeno 100 osservazioni.",
            "Una trimestrale entro 7 giorni non dà punti: genera un avviso di rischio.",
        ]),
        ("Indicatori principali (SCREENER, SCHEDA, CRUSCOTTO)", [
            "P/E sugli ultimi 12 mesi = prezzo / utile per azione degli ultimi quattro trimestri (se manca il dato a 12 mesi: ultimo esercizio annuale, con nota). P/E prospettico = prezzo / utile atteso dal consenso. 'n.d.' se l'utile è negativo o assente.",
            "Rendimento da dividendo = dividendi per azione staccati negli ultimi 12 mesi (dallo storico prezzi) / prezzo. Non si usa il dato dichiarato da Yahoo, incoerente per diversi titoli.",
            "EV/EBITDA, rendimento sul capitale, margine operativo, debito netto / EBITDA e crescita sono le metriche V3, Q1, Q3, F1 e G1 del Buffett Score: per banche e assicurazioni hanno un significato diverso (vedi le intestazioni).",
            "Per questo ogni titolo è confrontato con la mediana dei titoli dello stesso settore e dello stesso tipo (banche e assicurazioni da una parte, il resto dall'altra); i segnaposto 99 e 999 (EBITDA negativo) sono esclusi dalle mediane. Nel foglio SETTORI ci sono solo le mediane dei tre indicatori confrontabili tra tutti: i due P/E e il dividendo.",
            "Un indicatore da solo inganna: un P/E basso può voler dire 'a buon mercato' oppure 'il mercato si aspetta utili in calo'. Gli indicatori servono a capire i punteggi, non a sostituirli.",
        ]),
        ("Movimenti, portafoglio, simulatore", [
            "MOVIMENTI: parte attesa dal mercato = beta (252 sedute) x variazione dell'indice di riferimento; parte del settore = mediana, tra i titoli dello stesso settore, della variazione non spiegata dal mercato (almeno 3 titoli); parte specifica = il resto. Livello di evidenza: A evento societario documentato nella finestra; C mercato e settore spiegano almeno il 60% nello stesso verso; B notizie coincidenti; D nessuna causa individuata. Lo stacco del dividendo è elencato ma non vale come causa, perché la variazione è misurata sul total return.",
            "PORTAFOGLIO: la volatilità usa le correlazioni dei rendimenti settimanali in euro a 3 anni; lo stress applica beta x -30% e -10% sui titoli non in euro; i giorni per liquidare assumono di usare il 20% degli scambi medi giornalieri.",
            "SIMULATORE: passo annuale con ipotesi scelte dall'utente; imposte al 26% come esempio; non sostituisce un calcolo fiscale.",
        ]),
    ])


def foglio_fonti(lib: Libro):
    _tabella(lib, "FONTI", "FONTI - costi, limiti, licenze", "Tutte le fonti sono gratuite. Nessuna garantisce completezza o continuità del servizio.",
             [("Fonte", 22), ("Che cosa fornisce", 48), ("Costo", 12), ("Limiti noti", 60), ("Licenza e condizioni d'uso", 52)], [
        ("Yahoo Finance (libreria yfinance)", "Storico giornaliero a 11 anni, bilanci annuali, trimestrali e a 12 mesi, anagrafica, date degli utili, stime e revisioni, notizie.",
         "Gratuito", "Fonte non ufficiale: può cambiare o interrompersi senza preavviso e blocca chi fa troppe richieste (il programma fa una pausa tra le chiamate e ritenta). Di norma solo 4 esercizi annuali. Voci di bilancio standardizzate, a volte incomplete o classificate male; chiusura rettificata (total return) sbagliata per i titoli quotati in pence e per chi paga dividendi in un'altra valuta, quindi il programma la ricostruisce da chiusure e dividendi; rendimento da dividendo dichiarato incoerente, quindi non usato; frazionamenti recenti non sempre riportati su azioni, EPS e stime. L'ultima chiusura delle borse europee può mancare fino al consolidamento.",
         "Dati di Yahoo e dei suoi fornitori, consentiti per il solo uso personale: non ridistribuire. yfinance è software open source (licenza Apache 2.0) non affiliato a Yahoo."),
        ("Banca Centrale Europea", "Cambi di riferimento giornalieri: unità di valuta per 1 euro.", "Gratuito",
         "Un valore al giorno, solo giorni lavorativi TARGET. Alcune valute mancano (dollaro di Taiwan: preso da Yahoo, simbolo EURTWD=X).",
         "Riutilizzo libero citando la fonte (Banca Centrale Europea)."),
        ("SEC EDGAR companyfacts", "Dati XBRL dei depositi 10-K: allunga a 10 anni ricavi, utili, cassa e patrimonio delle società americane.", "Gratuito",
         "Facoltativa: richiede un User-Agent con nome ed e-mail; massimo 10 richieste al secondo. Solo società che depositano il 10-K (non gli emittenti esteri con 20-F). I concetti contabili cambiano tra società: le serie si usano solo se coincidono con Yahoo sugli esercizi in comune.",
         "Dati pubblici del governo degli Stati Uniti; rispettare la politica di accesso corretto della SEC."),
        ("GDELT DOC 2.0", "Titoli di stampa nella finestra dei movimenti: titolo, testata, link.", "Gratuito",
         "Una richiesta ogni 5 secondi; il servizio rifiuta spesso le richieste (errore 429) e può non rispondere: in quel caso il programma prosegue senza. Ricerca per nome della società: può restituire articoli non pertinenti. Usato solo per i titoli che si sono mossi.",
         "Uso libero citando la fonte (The GDELT Project). Gli articoli restano dei rispettivi editori: si riporta solo titolo e link."),
        ("LibreOffice (facoltativo)", "Ricalcolo del cruscotto senza Excel, per il controllo incrociato tra formule e calcolo Python.", "Gratuito",
         "Non è una fonte di dati. Se non è installato il controllo non viene eseguito e il programma lo dichiara.", "Software libero (MPL 2.0)."),
    ])


def foglio_stato(lib: Libro, ctx: dict):
    bt = ctx.get("backtest")
    n_gd = ctx.get("n_gdelt", 0)
    righe = [
        ("Scaricamento prezzi, bilanci, anagrafica, date utili, stime, revisioni, notizie (Yahoo)", "OPERATIVA", "Eseguito in rete sui 120 titoli; ogni errore è registrato per titolo senza fermare gli altri."),
        ("Cambi BCE e cambi mancanti da Yahoo", "OPERATIVA", "15 valute dalla BCE, dollaro di Taiwan da Yahoo."),
        ("Controlli di qualità dopo lo scarico (QUALITA_DATI)", "OPERATIVA", "Prezzi recenti, valuta e nome attesi, salti anomali, età e completezza dei bilanci."),
        ("SEC EDGAR", "OPERATIVA (facoltativa)" if ctx.get("n_sec") else "NON ATTIVA",
         f"Dati 10-K presenti per {ctx.get('n_sec', 0)} società." if ctx.get("n_sec") else "User-Agent non impostato in configurazione.ini: storico limitato agli esercizi di Yahoo."),
        ("Buffett Score, valore intrinseco, Trading Score in formule", "OPERATIVA", "Calcolo completo nei fogli BUFFETT, VALUTAZIONE, TRADING; parametri modificabili."),
        ("Controllo incrociato formule / Python", "OPERATIVA se LibreOffice è installato", "A ogni rigenerazione il file viene ricalcolato e confrontato titolo per titolo; senza LibreOffice il programma lo dichiara. Non verificato con Microsoft Excel dagli autori: solo con LibreOffice."),
        ("Conservazione delle celle gialle", "OPERATIVA", "Parametri, giudizi, posizioni, ingressi del simulatore e valutazioni dei movimenti sono riletti dal file esistente e riscritti nel nuovo."),
        ("CRUSCOTTO, SCREENER, SCHEDA, PERFORMANCE", "OPERATIVA", "Solo collegamenti e formule."),
        ("Dati manuali di banche e assicurazioni (GIUDIZI)", "PARZIALE", "Cost/income, combined ratio, CET1 e Solvency II non hanno una fonte gratuita via API: finché non sono inseriti a mano, le metriche Q3 e F5 restano 'n.d.' e il punteggio usa le altre."),
        ("MOVIMENTI: scomposizione mercato / settore / specifico ed eventi documentati", "OPERATIVA", "Eventi: risultati, stacco del dividendo, frazionamenti. Le date dei risultati di Yahoo per i titoli non americani possono essere imprecise."),
        ("MOVIMENTI: titoli di stampa da GDELT", "PARZIALE" if n_gd else "NON VERIFICATA",
         f"{n_gd} titoli raccolti da GDELT nell'archivio. Il servizio rifiuta spesso le richieste: a ogni aggiornamento si raccoglie ciò che risponde, il resto si ritenta la volta dopo. Si tengono solo i titoli che contengono il nome della società; i nomi sotto i 6 caratteri non sono cercabili." if n_gd else "Il codice c'è e la lettura delle risposte è collaudata, ma negli aggiornamenti eseguiti GDELT ha rifiutato le richieste: nessun titolo raccolto da questa fonte. Restano i titoli di Yahoo."),
        ("NOTIZIE", "OPERATIVA", "Archivio dei titoli raccolti (Yahoo: ultime notizie per titolo, quindi solo movimenti recenti hanno titoli coincidenti)."),
        ("PORTAFOGLIO", "OPERATIVA", "Pesi e limiti, volatilità da correlazioni, stress, giorni per liquidare, verifica di una nuova operazione. Fino a 30 posizioni."),
        ("SIMULATORE", "OPERATIVA", "Modello annuale semplificato; il confronto storico con i due ETF usa le chiusure di fine mese disponibili (circa 11 anni)."),
        ("BACKTEST della strategia B", "OPERATIVA" if bt else "DA ESEGUIRE",
         f"Eseguito il {bt['eseguito'][:10]}: {bt['osservazioni']} osservazioni dal {bt['dal']} al {bt['al']}. Senza il pilastro Catalizzatori; con distorsione da sopravvivenza." if bt else "Nessun risultato mostrato finché non si lancia  python avvia.py backtest"),
        ("BACKTEST della strategia A", "NON IMPLEMENTATA (per scelta)", "Mancano i bilanci 'come erano noti allora': qualunque risultato sarebbe viziato dallo sguardo al futuro."),
        ("Versione dimostrativa", "OPERATIVA", "python avvia.py demo: società e dati inventati, etichettati come tali."),
        ("Indicatori tecnici e metriche di bilancio grezze", "CALCOLATI IN PYTHON", "Medie mobili, RSI, MACD, ATR, rendimenti, ROIC, margini, CAGR sono calcolati sullo storico e scritti nel foglio DATI come dati: non si ricalcolano cambiando un parametro. In formula ci sono soglie, pesi, punteggi, valutazione, setup e verdetti."),
        ("Bilanci trimestrali e a 12 mesi", "SCARICATI, NON USATI NEI PUNTEGGI", "Sono nell'archivio; i punteggi usano gli esercizi annuali."),
        ("Prevedibilità a 10 anni (giudizi di Claude con ricerca su internet)", "OPERATIVA (opinioni, da aggiornare)",
         "Giudizi redatti il 23/11/2026 con fonti; non si aggiornano da soli con i dati: vanno rivisti periodicamente o dopo fatti rilevanti. Il giudizio dell'utente in GIUDIZI prevale."),
        ("Catene del valore", "OPERATIVA (descrizioni, da aggiornare)",
         "Struttura e testi redatti con ricerca su internet il 24/11/2026; si aggiornano solo su richiesta. I margini degli anelli si ricalcolano a ogni aggiornamento dei bilanci."),
        ("Perché questo verdetto (strategia A)", "OPERATIVA", "Testo costruito da formule a partire dai numeri del Buffett Score e controllato contro il calcolo del programma. Descrive i numeri: non considera concorrenza, tecnologia o notizie."),
        ("Promemoria dei rischi di settore", "OPERATIVA", "Testo generico modificabile in PARAMETRI; non è un'analisi del singolo titolo."),
        ("Descrizioni: cosa fa ogni società e come funziona il mercato del settore", "OPERATIVA (testi scritti a mano)", "Non provengono dalle fonti dati: sono descrizioni generali dell'attività redatte per questo strumento, da verificare e correggere se un'azienda cambia mestiere. Quelle di settore si modificano in PARAMETRI."),
    ]
    _tabella(lib, "STATO", "STATO - che cosa funziona, che cosa è parziale, che cosa manca",
             "Aggiornato a ogni rigenerazione. Una funzione non eseguita davvero è dichiarata come non verificata.",
             [("Funzione", 52), ("Stato", 26), ("Dettagli e limiti", 110)], righe)


def foglio_leggimi(lib: Libro, demo: bool):
    _testo(lib, "LEGGIMI", "LEGGIMI - manuale sintetico",
           "Strumento personale per scegliere azioni. Non è consulenza finanziaria." + (" VERSIONE DIMOSTRATIVA: società e dati inventati." if demo else ""), [
        ("In breve", [
            "Un programma scarica i dati in un archivio sul computer e rigenera questo file. Qui dentro i dati stanno nel foglio DATI; tutto il resto sono formule.",
            "Colori: blu = dato importato o inserito; nero = formula; verde = collegamento ad altro foglio; fondo giallo = cella che si può modificare.",
            "'n.d.' = dato non disponibile (non vale mai punti). 'n.s.' = valore non stimabile perché i flussi sono negativi.",
        ]),
        ("Aggiornare", [
            "Chiudere questo file. Aprire il terminale nella cartella del programma e scrivere:  python avvia.py aggiorna   (su Mac: python3). Dura circa 20 minuti.",
            "python avvia.py aggiorna --solo-prezzi   scarica solo prezzi e cambi (circa 5 minuti).",
            "python avvia.py excel   rigenera il file dall'archivio senza scaricare.   python avvia.py backtest   esegue il backtest della strategia B.   python avvia.py demo   crea la versione dimostrativa.",
            "Le celle gialle modificate vengono conservate a ogni aggiornamento. Non spostare né rinominare i fogli e non inserire colonne: il programma rilegge le celle dalla loro posizione.",
        ]),
        ("Da dove cominciare", [
            "CRUSCOTTO: indicatori di sintesi e cinque liste (migliori di valore, migliori di trading, classe A senza margine, 'Aspetterei' vicini al prezzo d'acquisto, rischi e allerte).",
            "SCREENER: una riga per titolo. Usare le frecce dei filtri nella riga di intestazione (paese, area, settore, fascia di capitalizzazione, punteggi, verdetto, segnale, livello di rischio).",
            "SETTORI: come funziona il mercato di ogni settore, i rischi tipici e i punteggi medi dei suoi titoli. In CRUSCOTTO e SCREENER ogni titolo ha accanto il settore e una riga su che cosa fa.",
            "SCHEDA: scegliere il titolo dal menu nella cella gialla in alto: compaiono che cosa fa l'azienda, il perché del verdetto secondo la strategia A, i due punteggi, il valore intrinseco, il setup, i rischi, la performance, le 19 metriche e il grafico a 5 anni.",
        ]),
        ("Capire i numeri", [
            "BUFFETT, VALUTAZIONE, TRADING: il calcolo completo, colonna per colonna. METODOLOGIA spiega criteri e pesi.",
            "PARAMETRI: tutte le soglie, i pesi e le ipotesi. Cambiando un numero giallo, punteggi e valori si ricalcolano.",
            "GIUDIZI: per banche e assicurazioni inserire a mano cost/income o combined ratio (Q3) e CET1 o Solvency II (F5), presi dai bilanci. Qui si mettono anche la correzione qualitativa (al massimo ±10 punti, sempre motivata) e la tesi personale.",
            "Indicatori principali: P/E (sugli ultimi 12 mesi e prospettico), rendimento da dividendo, EV/EBITDA, rendimento sul capitale, margine operativo, debito netto / EBITDA, crescita dei ricavi. Sono nello SCREENER (filtrabili), nella SCHEDA accanto alla mediana dei titoli confrontabili, e i due più usati (P/E prospettico e dividendo) nelle liste del CRUSCOTTO.",
            "PREVEDIBILITA: per ogni azienda il giudizio di Claude sulla prevedibilità a 10 anni (Alta, Media, Bassa) con vantaggio competitivo, minaccia principale, fatti recenti, che cosa farebbe cambiare idea e fonti. Conta subito nel verdetto della strategia A; per cambiarlo scrivere Alta, Media o Bassa nella colonna gialla del foglio GIUDIZI.",
            "MERCATI e CATENE: le 23 catene del valore con protagonisti, forza contrattuale, fatti e fonti (MERCATI), e la posizione di ogni titolo con chi sta a monte e a valle e i margini del suo anello (CATENE). Nella SCHEDA il riquadro 'Catena del valore'.",
            "QUALITA_DATI: esito dei controlli su ogni titolo e note sulle scelte fatte sui dati della fonte. Un titolo 'DA VERIFICARE' va controllato prima di fidarsi dei suoi punteggi.",
        ]),
        ("Gli altri fogli", [
            "MOVIMENTI: perché un titolo è salito o sceso. I fatti (variazione, eventi, titoli di stampa) sono distinti dalle ipotesi; l'ultima colonna gialla è per la propria valutazione sull'impatto per la tesi di lungo periodo.",
            "PORTAFOGLIO: inserire ticker, quantità e prezzo di carico nelle celle gialle. Il foglio controlla i limiti per titolo, settore, area e valuta, stima volatilità e perdita in uno scenario di stress, e verifica se una nuova operazione è compatibile con i limiti (esito separato dal giudizio sul titolo).",
            "SIMULATORE: piano di accumulo con tre ipotesi di rendimento scelte da chi lo usa, costi, imposte e inflazione; confronto con ciò che lo stesso piano avrebbe reso sui due ETF.",
            "BACKTEST: che cosa è successo in passato ai titoli nelle varie fasce di Trading Score. Leggere gli avvisi in testa al foglio.",
            "FONTI: da dove vengono i dati e con quali limiti. STATO: che cosa funziona, che cosa è parziale, che cosa manca.",
        ]),
        ("Come funziona un aggiornamento", [
            "1. Scarica i prezzi a 11 anni dei 120 titoli (sempre per intero, perché dividendi e frazionamenti cambiano i prezzi passati), i bilanci (solo se hanno più di 7 giorni), i cambi BCE, le stime degli analisti e le notizie. Se un titolo dà errore lo registra e passa al successivo.",
            "2. Controlla ogni titolo: prezzi recenti, valuta e nome attesi, nessun salto anomalo, bilanci non troppo vecchi. Alla fine stampa chi è 'DA VERIFICARE' e perché.",
            "3. Calcola indicatori tecnici e metriche di bilancio e li scrive nel foglio DATI.",
            "4. Ricrea questo file: prima legge dal file vecchio tutte le celle gialle (parametri, giudizi, portafoglio, simulatore, valutazioni dei movimenti) e le rimette nel nuovo.",
            "5. Se LibreOffice è installato, ricalcola le formule e le confronta con il calcolo del programma, titolo per titolo.",
        ]),
        ("Manutenzione", [
            "A ogni aggiornamento: le ultime righe nel terminale devono dire 'errori di formula: 0' e 'differenze: 0' (altrimenti non fidarsi del file). Guardare i titoli 'DA VERIFICARE' e il motivo (anche nel foglio QUALITA_DATI). Chiudere Excel prima di lanciare il comando.",
            "Una volta al trimestre: aggiornare in GIUDIZI i dati manuali di banche e assicurazioni (cost/income, combined ratio, CET1, Solvency II, dalle presentazioni dei risultati); rifare il backtest (python avvia.py backtest); aggiornare la libreria di Yahoo (pip install -U yfinance), che è la causa più probabile di guasti.",
            "Una volta all'anno: rivedere in PARAMETRI i rendimenti richiesti per valuta (sono ipotesi, non dati di mercato) e rileggere le descrizioni delle società e dei settori.",
            "Molti titoli senza prezzo o errori a catena: Yahoo ha cambiato qualcosa o blocca le richieste. Aggiornare yfinance e riprovare dopo qualche ora.",
            "Un titolo 'nessun prezzo scaricato': delisting, offerta pubblica o cambio di simbolo (come Roche, da ROG.SW a ROP.SW). L'elenco dei titoli va corretto nel programma (file gsi/universo.py, una riga per titolo), poi vanno rilanciati i collaudi: python -m pytest -q tests.",
            "'Ultimo esercizio vecchio': Yahoo non ha ancora caricato il bilancio nuovo; nel frattempo il titolo resta 'Dati insufficienti'.",
            "Differenze nel controllo incrociato: errore nel programma. Non usare quel file e farlo correggere.",
        ]),
        ("Cosa conservare", [
            "Questo file è l'unica copia delle proprie modifiche (parametri, giudizi, portafoglio, tesi): l'archivio dei dati e il programma si ricreano da zero, il file no. Farne una copia di sicurezza ogni tanto.",
            "Non spostare, rinominare o inserire colonne nei fogli: il programma ritrova le celle gialle dalla loro posizione. Ordinare e filtrare invece va bene.",
            "Il file configurazione.ini (nome ed e-mail per la SEC) non è su GitHub: se si cambia computer va ricreato.",
        ]),
        ("Avvertenze", [
            "I dati vengono da fonti gratuite e possono contenere errori: verificare sempre i numeri importanti sui bilanci ufficiali prima di decidere.",
            "I punteggi ordinano i titoli secondo criteri dichiarati; non dicono che cosa farà il prezzo. Obiettivi e scenari sono convenzioni di calcolo.",
            "I dati di Yahoo sono consentiti per il solo uso personale: non ridistribuire questo file.",
        ]),
    ])
