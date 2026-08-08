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
    # US majors
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
    # Cargo
    "UPS": {"name": "UPS Airlines", "iata": "5X"},
    "FDX": {"name": "FedEx Express", "iata": "FX"},
    "ABX": {"name": "ABX Air", "iata": "GB"},
    "ATN": {"name": "Air Transport International", "iata": "8C"},
    # US regional
    "SKW": {"name": "SkyWest Airlines", "iata": "OO"},
    "RPA": {"name": "Republic Airways", "iata": "YX"},
    "ENY": {"name": "Envoy Air", "iata": "MQ"},
    "JIA": {"name": "PSA Airlines", "iata": "OH"},
    "EDV": {"name": "Endeavor Air", "iata": "9E"},
    "QXE": {"name": "Horizon Air", "iata": "QX"},
    # International
    "BAW": {"name": "British Airways", "iata": "BA"},
    "ACA": {"name": "Air Canada", "iata": "AC"},
    "AFR": {"name": "Air France", "iata": "AF"},
    "DLH": {"name": "Lufthansa", "iata": "LH"},
    "KLM": {"name": "KLM Royal Dutch Airlines", "iata": "KL"},
    "VIR": {"name": "Virgin Atlantic", "iata": "VS"},
    "QFA": {"name": "Qantas", "iata": "QF"},
    "CPA": {"name": "Cathay Pacific", "iata": "CX"},
    "ANA": {"name": "All Nippon Airways", "iata": "NH"},
    "JAL": {"name": "Japan Airlines", "iata": "JL"},
    "AAR": {"name": "Asiana Airlines", "iata": "OZ"},
    "EIN": {"name": "Aer Lingus", "iata": "EI"},
    "IBE": {"name": "Iberia", "iata": "IB"},
    "TAP": {"name": "TAP Air Portugal", "iata": "TP"},
    "SAS": {"name": "Scandinavian Airlines", "iata": "SK"},
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
