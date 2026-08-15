"""ICAO callsign-prefix -> airline lookup, used to label nearby aircraft.

adsb.lol (and ADS-B data generally) only gives us a raw callsign like
"UAL1698" — the first three letters are the operator's ICAO code when the
aircraft is airline/commercial traffic. General-aviation aircraft squawk
their tail number instead (e.g. "N583CA"), which never matches an ICAO
prefix, so `lookup()` degrades to an all-None result for those rather than
guessing.
"""

from __future__ import annotations

import re

AIRLINES_BY_ICAO: dict[str, dict[str, str]] = {
    # US majors & low-cost
    "UAL": {"name": "United Airlines", "iata": "UA"},
    "DAL": {"name": "Delta Air Lines", "iata": "DL"},
    "AAL": {"name": "American Airlines", "iata": "AA"},
    "SWA": {"name": "Southwest Airlines", "iata": "WN"},
    "ASA": {"name": "Alaska Airlines", "iata": "AS"},
    "JBU": {"name": "JetBlue Airways", "iata": "B6"},
    "NKS": {"name": "Spirit Airlines", "iata": "NK"},
    "FFT": {"name": "Frontier Airlines", "iata": "F9"},
    "HAL": {"name": "Hawaiian Airlines", "iata": "HA"},
    "AAY": {"name": "Allegiant Air", "iata": "G4"},
    "SCX": {"name": "Sun Country Airlines", "iata": "SY"},
    "BOS": {"name": "OpenSkies", "iata": "EC"},
    # Cargo
    "UPS": {"name": "UPS Airlines", "iata": "5X"},
    "FDX": {"name": "FedEx Express", "iata": "FX"},
    "ABX": {"name": "ABX Air", "iata": "GB"},
    "ATN": {"name": "Air Transport International", "iata": "8C"},
    "GTI": {"name": "Atlas Air", "iata": "5Y"},
    "CKS": {"name": "Kalitta Air", "iata": "K4"},
    "PAC": {"name": "Polar Air Cargo", "iata": "PO"},
    "WGN": {"name": "Western Global Airlines", "iata": "KD"},
    "NCR": {"name": "National Airlines", "iata": "N8"},
    "OAE": {"name": "Omni Air International", "iata": "OY"},
    # US & North America regional
    "SKW": {"name": "SkyWest Airlines", "iata": "OO"},
    "RPA": {"name": "Republic Airways", "iata": "YX"},
    "ENY": {"name": "Envoy Air", "iata": "MQ"},
    "JIA": {"name": "PSA Airlines", "iata": "OH"},
    "EDV": {"name": "Endeavor Air", "iata": "9E"},
    "QXE": {"name": "Horizon Air", "iata": "QX"},
    "PDT": {"name": "Piedmont Airlines", "iata": "PT"},
    "ASH": {"name": "Mesa Airlines", "iata": "YV"},
    "GJS": {"name": "GoJet Airlines", "iata": "G7"},
    "UCA": {"name": "CommuteAir", "iata": "C5"},
    "SIL": {"name": "Silver Airways", "iata": "3M"},
    "CPZ": {"name": "Compass Airlines", "iata": "CP"},
    # Canada & Mexico / Latin America
    "ACA": {"name": "Air Canada", "iata": "AC"},
    "WJA": {"name": "WestJet", "iata": "WS"},
    "TSC": {"name": "Air Transat", "iata": "TS"},
    "POE": {"name": "Porter Airlines", "iata": "PD"},
    "ROU": {"name": "Air Canada Rouge", "iata": "RV"},
    "AMX": {"name": "Aeroméxico", "iata": "AM"},
    "VOI": {"name": "Volaris", "iata": "Y4"},
    "VIV": {"name": "VivaAerobus", "iata": "VB"},
    "SLI": {"name": "Aeroméxico Connect", "iata": "5D"},
    "CMP": {"name": "Copa Airlines", "iata": "CM"},
    "AVA": {"name": "Avianca", "iata": "AV"},
    "LAN": {"name": "LATAM Airlines", "iata": "LA"},
    "TAM": {"name": "LATAM Brasil", "iata": "JJ"},
    "GLO": {"name": "Gol Transportes Aéreos", "iata": "G3"},
    "AZU": {"name": "Azul Brazilian Airlines", "iata": "AD"},
    # Europe
    "BAW": {"name": "British Airways", "iata": "BA"},
    "AFR": {"name": "Air France", "iata": "AF"},
    "DLH": {"name": "Lufthansa", "iata": "LH"},
    "KLM": {"name": "KLM Royal Dutch Airlines", "iata": "KL"},
    "VIR": {"name": "Virgin Atlantic", "iata": "VS"},
    "EIN": {"name": "Aer Lingus", "iata": "EI"},
    "IBE": {"name": "Iberia", "iata": "IB"},
    "TAP": {"name": "TAP Air Portugal", "iata": "TP"},
    "SAS": {"name": "Scandinavian Airlines", "iata": "SK"},
    "RYR": {"name": "Ryanair", "iata": "FR"},
    "EZY": {"name": "easyJet", "iata": "U2"},
    "WZZ": {"name": "Wizz Air", "iata": "W6"},
    "EWG": {"name": "Eurowings", "iata": "EW"},
    "VLG": {"name": "Vueling", "iata": "VY"},
    "SWR": {"name": "Swiss International Air Lines", "iata": "LX"},
    "AUA": {"name": "Austrian Airlines", "iata": "OS"},
    "BEL": {"name": "Brussels Airlines", "iata": "SN"},
    "FIN": {"name": "Finnair", "iata": "AY"},
    "NOZ": {"name": "Norwegian Air Shuttle", "iata": "DY"},
    "LOT": {"name": "LOT Polish Airlines", "iata": "LO"},
    "ITY": {"name": "ITA Airways", "iata": "AZ"},
    "THY": {"name": "Turkish Airlines", "iata": "TK"},
    "GEC": {"name": "Lufthansa Cargo", "iata": "LH"},
    # Middle East & Africa
    "UAE": {"name": "Emirates", "iata": "EK"},
    "QTR": {"name": "Qatar Airways", "iata": "QR"},
    "ETD": {"name": "Etihad Airways", "iata": "EY"},
    "SVA": {"name": "Saudia", "iata": "SV"},
    "FDB": {"name": "flydubai", "iata": "FZ"},
    "MSR": {"name": "EgyptAir", "iata": "MS"},
    "ETH": {"name": "Ethiopian Airlines", "iata": "ET"},
    "RAM": {"name": "Royal Air Maroc", "iata": "AT"},
    "ELY": {"name": "El Al", "iata": "LY"},
    # Asia & Oceania
    "QFA": {"name": "Qantas", "iata": "QF"},
    "VOZ": {"name": "Virgin Australia", "iata": "VA"},
    "ANZ": {"name": "Air New Zealand", "iata": "NZ"},
    "FJI": {"name": "Fiji Airways", "iata": "FJ"},
    "CPA": {"name": "Cathay Pacific", "iata": "CX"},
    "ANA": {"name": "All Nippon Airways", "iata": "NH"},
    "JAL": {"name": "Japan Airlines", "iata": "JL"},
    "AAR": {"name": "Asiana Airlines", "iata": "OZ"},
    "KAL": {"name": "Korean Air", "iata": "KE"},
    "SIA": {"name": "Singapore Airlines", "iata": "SQ"},
    "MAS": {"name": "Malaysia Airlines", "iata": "MH"},
    "THA": {"name": "Thai Airways", "iata": "TG"},
    "GIA": {"name": "Garuda Indonesia", "iata": "GA"},
    "EVA": {"name": "EVA Air", "iata": "BR"},
    "CAL": {"name": "China Airlines", "iata": "CI"},
    "CCA": {"name": "Air China", "iata": "CA"},
    "CES": {"name": "China Eastern Airlines", "iata": "MU"},
    "CSN": {"name": "China Southern Airlines", "iata": "CZ"},
    "AIC": {"name": "Air India", "iata": "AI"},
    "IGO": {"name": "IndiGo", "iata": "6E"},
}

_ICAO_PREFIX = re.compile(r"^[A-Z]{3}")


def lookup(callsign: str) -> dict[str, str | None]:
    """Best-effort airline info for a raw ADS-B callsign.

    A tail-number callsign (general aviation) has no 3-letter alpha prefix
    and returns all-None. A recognized-but-unmapped ICAO prefix (foreign or
    minor carrier not in AIRLINES_BY_ICAO) still returns `airline_code` so
    the UI can show a text badge, but leaves the name/IATA fields None.
    """
    match = _ICAO_PREFIX.match(callsign)
    if match is None:
        return {"airline_code": None, "airline_name": None, "airline_iata": None}

    code = match.group(0)
    airline = AIRLINES_BY_ICAO.get(code)
    return {
        "airline_code": code,
        "airline_name": airline["name"] if airline else None,
        "airline_iata": airline["iata"] if airline else None,
    }
