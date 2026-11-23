"""Universo dei titoli: 120 azioni, indici di riferimento, ETF di confronto.

Colonne: ticker Yahoo | societa | area | settore | modello | valuta di
quotazione (unita) | valuta di bilancio attesa | indice di riferimento | ADR
"""
from __future__ import annotations
from dataclasses import dataclass

MODELLI = {"STD": "Standard", "CIC": "Ciclico", "UTL": "Reti regolate",
           "BAN": "Banche", "ASS": "Assicurazioni", "REIT": "Immobiliare"}

# Titoli esclusi con motivazione (verifiche dell'utente al 20/11/2026).
ESCLUSI = {"REC.MI": "Recordati: OPA chiusa oltre il 90% il 9/11/2026, azioni in revoca"}

_TABELLA = """
AAPL | Apple | USA | Tecnologia e semiconduttori | STD | USD | USD | ^GSPC | -
MSFT | Microsoft | USA | Tecnologia e semiconduttori | STD | USD | USD | ^GSPC | -
NVDA | Nvidia | USA | Tecnologia e semiconduttori | STD | USD | USD | ^GSPC | -
GOOGL | Alphabet (classe A) | USA | Tecnologia e semiconduttori | STD | USD | USD | ^GSPC | -
AMZN | Amazon | USA | Consumi e grande distribuzione | STD | USD | USD | ^GSPC | -
META | Meta Platforms | USA | Tecnologia e semiconduttori | STD | USD | USD | ^GSPC | -
AVGO | Broadcom | USA | Tecnologia e semiconduttori | STD | USD | USD | ^GSPC | -
TSM | TSMC (ADR) | Emergenti | Tecnologia e semiconduttori | STD | USD | TWD | ^GSPC | ADR: 1 ADS = 5 azioni ordinarie
ASML.AS | ASML Holding | Europa | Tecnologia e semiconduttori | STD | EUR | EUR | ^STOXX | -
SAP.DE | SAP | Europa | Tecnologia e semiconduttori | STD | EUR | EUR | ^STOXX | -
ORCL | Oracle | USA | Tecnologia e semiconduttori | STD | USD | USD | ^GSPC | -
005930.KS | Samsung Electronics | Emergenti | Tecnologia e semiconduttori | CIC | KRW | KRW | ^KS11 | -
JPM | JPMorgan Chase | USA | Banche e servizi finanziari | BAN | USD | USD | ^GSPC | -
BRK-B | Berkshire Hathaway (classe B) | USA | Assicurazioni | ASS | USD | USD | ^GSPC | -
V | Visa | USA | Banche e servizi finanziari | STD | USD | USD | ^GSPC | -
MA | Mastercard | USA | Banche e servizi finanziari | STD | USD | USD | ^GSPC | -
BAC | Bank of America | USA | Banche e servizi finanziari | BAN | USD | USD | ^GSPC | -
GS | Goldman Sachs | USA | Banche e servizi finanziari | BAN | USD | USD | ^GSPC | -
HSBA.L | HSBC Holdings | Europa | Banche e servizi finanziari | BAN | GBP (GBp) | USD | ^STOXX | -
HDFCBANK.NS | HDFC Bank | Emergenti | Banche e servizi finanziari | BAN | INR | INR | ^NSEI | -
LLY | Eli Lilly | USA | Sanità e farmaceutica | STD | USD | USD | ^GSPC | -
JNJ | Johnson & Johnson | USA | Sanità e farmaceutica | STD | USD | USD | ^GSPC | -
UNH | UnitedHealth Group | USA | Sanità e farmaceutica | STD | USD | USD | ^GSPC | -
ABBV | AbbVie | USA | Sanità e farmaceutica | STD | USD | USD | ^GSPC | -
NVO | Novo Nordisk (ADR) | Europa | Sanità e farmaceutica | STD | USD | DKK | ^GSPC | ADR: 1 ADS = 1 azione B
NOVN.SW | Novartis | Europa | Sanità e farmaceutica | STD | CHF | USD | ^STOXX | -
ROP.SW | Roche (buono di partecipazione) | Europa | Sanità e farmaceutica | STD | CHF | CHF | ^STOXX | Ex buono di godimento ROG: convertito 1:1 in buono di partecipazione ROP dal 17/3/2026
AZN | AstraZeneca | Europa | Sanità e farmaceutica | STD | USD | USD | ^GSPC | Non più ADR: azioni ordinarie quotate direttamente al NYSE dal 2/2/2026
XOM | Exxon Mobil | USA | Energia | CIC | USD | USD | ^GSPC | -
CVX | Chevron | USA | Energia | CIC | USD | USD | ^GSPC | -
SHEL | Shell (ADR) | Europa | Energia | CIC | USD | USD | ^GSPC | ADR: 1 ADS = 2 azioni ordinarie
TTE.PA | TotalEnergies | Europa | Energia | CIC | EUR | USD | ^STOXX | -
RIO | Rio Tinto (ADR) | Europa | Materie prime | CIC | USD | USD | ^GSPC | ADR: 1 ADS = 1 azione ordinaria
BHP | BHP Group (ADR) | Altri sviluppati | Materie prime | CIC | USD | USD | ^GSPC | ADR: 1 ADS = 2 azioni ordinarie
PG | Procter & Gamble | USA | Consumi e grande distribuzione | STD | USD | USD | ^GSPC | -
KO | Coca-Cola | USA | Consumi e grande distribuzione | STD | USD | USD | ^GSPC | -
PEP | PepsiCo | USA | Consumi e grande distribuzione | STD | USD | USD | ^GSPC | -
WMT | Walmart | USA | Consumi e grande distribuzione | STD | USD | USD | ^GSPC | -
COST | Costco | USA | Consumi e grande distribuzione | STD | USD | USD | ^GSPC | -
NESN.SW | Nestlé | Europa | Consumi e grande distribuzione | STD | CHF | CHF | ^STOXX | -
MC.PA | LVMH | Europa | Lusso | STD | EUR | EUR | ^STOXX | -
OR.PA | L'Oréal | Europa | Consumi e grande distribuzione | STD | EUR | EUR | ^STOXX | -
CAT | Caterpillar | USA | Industria e difesa | CIC | USD | USD | ^GSPC | -
GE | GE Aerospace | USA | Industria e difesa | STD | USD | USD | ^GSPC | -
SIE.DE | Siemens | Europa | Industria e difesa | STD | EUR | EUR | ^STOXX | -
7203.T | Toyota Motor | Giappone | Industria e difesa | CIC | JPY | JPY | ^N225 | -
6758.T | Sony Group | Giappone | Consumi e grande distribuzione | STD | JPY | JPY | ^N225 | -
BA | Boeing | USA | Industria e difesa | STD | USD | USD | ^GSPC | -
NEE | NextEra Energy | USA | Utilities e infrastrutture | UTL | USD | USD | ^GSPC | -
IBE.MC | Iberdrola | Europa | Utilities e infrastrutture | UTL | EUR | EUR | ^STOXX | -
ENEL.MI | Enel | Italia | Utilities e infrastrutture | UTL | EUR | EUR | FTSEMIB.MI | -
ENI.MI | Eni | Italia | Energia | CIC | EUR | EUR | FTSEMIB.MI | -
ISP.MI | Intesa Sanpaolo | Italia | Banche e servizi finanziari | BAN | EUR | EUR | FTSEMIB.MI | -
UCG.MI | UniCredit | Italia | Banche e servizi finanziari | BAN | EUR | EUR | FTSEMIB.MI | -
PRY.MI | Prysmian | Italia | Industria e difesa | STD | EUR | EUR | FTSEMIB.MI | -
LDO.MI | Leonardo | Italia | Industria e difesa | STD | EUR | EUR | FTSEMIB.MI | -
PST.MI | Poste Italiane | Italia | Banche e servizi finanziari | ASS | EUR | EUR | FTSEMIB.MI | -
G.MI | Assicurazioni Generali | Italia | Assicurazioni | ASS | EUR | EUR | FTSEMIB.MI | -
MONC.MI | Moncler | Italia | Lusso | STD | EUR | EUR | FTSEMIB.MI | -
TRN.MI | Terna | Italia | Utilities e infrastrutture | UTL | EUR | EUR | FTSEMIB.MI | -
SRG.MI | Snam | Italia | Utilities e infrastrutture | UTL | EUR | EUR | FTSEMIB.MI | -
NEXI.MI | Nexi | Italia | Banche e servizi finanziari | STD | EUR | EUR | FTSEMIB.MI | -
FBK.MI | FinecoBank | Italia | Banche e servizi finanziari | BAN | EUR | EUR | FTSEMIB.MI | -
FCT.MI | Fincantieri | Italia | Industria e difesa | STD | EUR | EUR | FTSEMIB.MI | -
BZU.MI | Buzzi | Italia | Materie prime | CIC | EUR | EUR | FTSEMIB.MI | -
AMP.MI | Amplifon | Italia | Sanità e farmaceutica | STD | EUR | EUR | FTSEMIB.MI | -
DIA.MI | DiaSorin | Italia | Sanità e farmaceutica | STD | EUR | EUR | FTSEMIB.MI | -
A2A.MI | A2A | Italia | Utilities e infrastrutture | UTL | EUR | EUR | FTSEMIB.MI | -
CPR.MI | Davide Campari-Milano | Italia | Consumi e grande distribuzione | STD | EUR | EUR | FTSEMIB.MI | -
SU.PA | Schneider Electric | Europa | Industria e difesa | STD | EUR | EUR | ^STOXX | -
AIR.PA | Airbus | Europa | Industria e difesa | STD | EUR | EUR | ^STOXX | -
SAN.PA | Sanofi | Europa | Sanità e farmaceutica | STD | EUR | EUR | ^STOXX | -
BNP.PA | BNP Paribas | Europa | Banche e servizi finanziari | BAN | EUR | EUR | ^STOXX | -
AI.PA | Air Liquide | Europa | Materie prime | STD | EUR | EUR | ^STOXX | -
SAN.MC | Banco Santander | Europa | Banche e servizi finanziari | BAN | EUR | EUR | ^STOXX | -
ITX.MC | Inditex | Europa | Consumi e grande distribuzione | STD | EUR | EUR | ^STOXX | -
ALV.DE | Allianz | Europa | Assicurazioni | ASS | EUR | EUR | ^STOXX | -
DTE.DE | Deutsche Telekom | Europa | Telecomunicazioni | UTL | EUR | EUR | ^STOXX | -
ENR.DE | Siemens Energy | Europa | Industria e difesa | STD | EUR | EUR | ^STOXX | -
ADS.DE | adidas | Europa | Consumi e grande distribuzione | STD | EUR | EUR | ^STOXX | -
ABBN.SW | ABB | Europa | Industria e difesa | STD | CHF | USD | ^STOXX | -
ATCO-A.ST | Atlas Copco (classe A) | Europa | Industria e difesa | STD | SEK | SEK | ^STOXX | -
VOLV-B.ST | AB Volvo (classe B) | Europa | Industria e difesa | CIC | SEK | SEK | ^STOXX | -
DSV.CO | DSV | Europa | Industria e difesa | STD | DKK | DKK | ^STOXX | -
8306.T | Mitsubishi UFJ Financial Group | Giappone | Banche e servizi finanziari | BAN | JPY | JPY | ^N225 | -
8766.T | Tokio Marine Holdings | Giappone | Assicurazioni | ASS | JPY | JPY | ^N225 | -
6861.T | Keyence | Giappone | Industria e difesa | STD | JPY | JPY | ^N225 | -
8035.T | Tokyo Electron | Giappone | Tecnologia e semiconduttori | CIC | JPY | JPY | ^N225 | -
9432.T | NTT | Giappone | Telecomunicazioni | UTL | JPY | JPY | ^N225 | -
RY.TO | Royal Bank of Canada | Altri sviluppati | Banche e servizi finanziari | BAN | CAD | CAD | ^GSPTSE | -
CNR.TO | Canadian National Railway | Altri sviluppati | Utilities e infrastrutture | STD | CAD | CAD | ^GSPTSE | -
CSL.AX | CSL | Altri sviluppati | Sanità e farmaceutica | STD | AUD | USD | ^AXJO | -
D05.SI | DBS Group Holdings | Altri sviluppati | Banche e servizi finanziari | BAN | SGD | SGD | ^STI | -
0700.HK | Tencent Holdings | Emergenti | Tecnologia e semiconduttori | STD | HKD | CNY | ^HSI | -
VALE | Vale (ADR) | Emergenti | Materie prime | CIC | USD | USD | ^GSPC | ADR: 1 ADS = 1 azione ordinaria
INFY | Infosys (ADR) | Emergenti | Tecnologia e semiconduttori | STD | USD | USD | ^GSPC | ADR: 1 ADS = 1 azione ordinaria
CS.PA | AXA | Europa | Assicurazioni | ASS | EUR | EUR | ^STOXX | -
MUV2.DE | Munich Re | Europa | Assicurazioni | ASS | EUR | EUR | ^STOXX | -
CB | Chubb | USA | Assicurazioni | ASS | USD | USD | ^GSPC | -
VZ | Verizon Communications | USA | Telecomunicazioni | UTL | USD | USD | ^GSPC | -
ORA.PA | Orange | Europa | Telecomunicazioni | UTL | EUR | EUR | ^STOXX | -
TIT.MI | Telecom Italia (TIM) | Italia | Telecomunicazioni | UTL | EUR | EUR | FTSEMIB.MI | -
BA.L | BAE Systems | Europa | Industria e difesa | STD | GBP (GBp) | GBP | ^STOXX | -
RHM.DE | Rheinmetall | Europa | Industria e difesa | STD | EUR | EUR | ^STOXX | -
LMT | Lockheed Martin | USA | Industria e difesa | STD | USD | USD | ^GSPC | -
RMS.PA | Hermès International | Europa | Lusso | STD | EUR | EUR | ^STOXX | -
CFR.SW | Compagnie Financière Richemont | Europa | Lusso | STD | CHF | EUR | ^STOXX | -
RACE.MI | Ferrari | Italia | Lusso | STD | EUR | EUR | FTSEMIB.MI | -
EL.PA | EssilorLuxottica | Europa | Sanità e farmaceutica | STD | EUR | EUR | ^STOXX | -
TXN | Texas Instruments | USA | Tecnologia e semiconduttori | STD | USD | USD | ^GSPC | -
ADBE | Adobe | USA | Tecnologia e semiconduttori | STD | USD | USD | ^GSPC | -
STMMI.MI | STMicroelectronics | Italia | Tecnologia e semiconduttori | CIC | EUR | USD | FTSEMIB.MI | -
ULVR.L | Unilever | Europa | Consumi e grande distribuzione | STD | GBP (GBp) | EUR | ^STOXX | -
AD.AS | Koninklijke Ahold Delhaize | Europa | Consumi e grande distribuzione | STD | EUR | EUR | ^STOXX | -
EQNR.OL | Equinor | Europa | Energia | CIC | NOK | USD | ^STOXX | -
NG.L | National Grid | Europa | Utilities e infrastrutture | UTL | GBP (GBp) | GBP | ^STOXX | -
DG.PA | Vinci | Europa | Utilities e infrastrutture | STD | EUR | EUR | ^STOXX | -
PLD | Prologis | USA | Immobiliare | REIT | USD | USD | ^GSPC | -
NEM | Newmont | USA | Materie prime | CIC | USD | USD | ^GSPC | -
SPGI | S&P Global | USA | Banche e servizi finanziari | STD | USD | USD | ^GSPC | -
"""

INDICI = {
    "^GSPC": ("S&P 500", "USD"), "^STOXX": ("STOXX Europe 600", "EUR"),
    "FTSEMIB.MI": ("FTSE MIB", "EUR"), "^N225": ("Nikkei 225", "JPY"),
    "^KS11": ("KOSPI", "KRW"), "^NSEI": ("Nifty 50", "INR"),
    "^GSPTSE": ("S&P/TSX Composite", "CAD"), "^AXJO": ("S&P/ASX 200", "AUD"),
    "^STI": ("Straits Times", "SGD"), "^HSI": ("Hang Seng", "HKD"),
}
# Nomi alternativi verificati: la fonte usa la ragione sociale, l'universo il nome d'uso.
NOMI_ALTERNATIVI = {
    "ITX.MC": "Industria de Diseño Textil",
    "MUV2.DE": "Münchener Rückversicherungs-Gesellschaft",
    "^STI": "STI Index",
}
# Casi in cui la valuta di bilancio dichiarata dalla fonte e' sbagliata e si usa quella attesa.
# Ogni voce va motivata con una verifica sui numeri.
VALUTA_BILANCIO_VERIFICATA = {
    "VALE": ("USD", "Yahoo dichiara BRL ma i valori sono in USD: ricavi 2024 = 38,06 miliardi, "
                    "come nel bilancio in dollari (in BRL sarebbero circa 200 miliardi)"),
}
# Sostituzioni rispetto all'elenco iniziale, con la verifica che le motiva.
SOSTITUZIONI = {
    "ROG.SW": ("ROP.SW", "Roche: l'assemblea del 10/3/2026 ha convertito 1:1 i buoni di godimento (ROG, ultimo "
                         "giorno di scambi 16/3/2026) in buoni di partecipazione ROP, quotati dal 17/3/2026. "
                         "Fonte: roche.com/investors/updates/inv-update-2026-03-16"),
}

# ETF ad accumulazione in euro per il confronto (da validare a ogni scarico).
ETF = {
    "CSSPX.MI": ("iShares Core S&P 500 UCITS ETF (Acc)", "EUR", "S&P 500"),
    "SWDA.MI": ("iShares Core MSCI World UCITS ETF (Acc)", "EUR", "MSCI World"),
}


@dataclass(frozen=True)
class Titolo:
    ticker: str
    nome: str
    area: str
    settore: str
    modello: str
    valuta: str          # valuta di quotazione in unita intere (GBP, non GBp)
    in_centesimi: bool   # True se la fonte quota in centesimi (GBp)
    valuta_bilancio: str
    indice: str
    adr: str

    @property
    def paese_listino(self) -> str:
        suff = self.ticker.rsplit(".", 1)[-1] if "." in self.ticker else ""
        return {"": "Stati Uniti", "MI": "Italia", "PA": "Francia", "DE": "Germania",
                "AS": "Paesi Bassi", "MC": "Spagna", "SW": "Svizzera", "L": "Regno Unito",
                "ST": "Svezia", "CO": "Danimarca", "OL": "Norvegia", "T": "Giappone",
                "TO": "Canada", "AX": "Australia", "SI": "Singapore", "HK": "Hong Kong",
                "KS": "Corea del Sud", "NS": "India"}.get(suff, "n.d.")


def carica_universo() -> list[Titolo]:
    out = []
    for riga in _TABELLA.strip().splitlines():
        c = [x.strip() for x in riga.split("|")]
        if len(c) != 9:
            raise ValueError(f"Riga universo non valida: {riga}")
        cent = "(GBp)" in c[5]
        out.append(Titolo(c[0], c[1], c[2], c[3], c[4], c[5].split()[0], cent,
                          c[6], c[7], "" if c[8] == "-" else c[8]))
    tick = [t.ticker for t in out]
    assert len(tick) == len(set(tick)), "ticker duplicati nell'universo"
    for t in out:
        assert t.modello in MODELLI and t.indice in INDICI, t
        assert t.ticker not in ESCLUSI, t
    return out


UNIVERSO = carica_universo()
PER_TICKER = {t.ticker: t for t in UNIVERSO}
