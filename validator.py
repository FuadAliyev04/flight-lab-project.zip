"""Row validation: airport list loading, single-row checks, record building."""
import math
import re
from datetime import datetime

# Why [A-Za-z0-9] and [0-9] instead of \w, \d, isalnum() or isupper():
# those also accept non-ASCII letters and digits (for example "Ā" or Arabic
# digits). The task wants ASCII only, so every character class is spelled out.
# fullmatch() is used so that a pattern must match the WHOLE string.
_FLIGHT_ID_RE = re.compile(r"[A-Za-z0-9]{2,8}")
_AIRPORT_CODE_RE = re.compile(r"[A-Z]{3}")
_DATETIME_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2}) ([0-9]{2}):([0-9]{2})")


def load_airports(path: str) -> set[str]:
    """Read an airport list file and return the set of codes.

    One code per line. Strip whitespace; skip blank lines and lines
    starting with '#'.
    """
    codes = set()
    # utf-8-sig silently drops a byte order mark, so a BOM in front of the
    # first code cannot turn it into a different string.
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            code = line.strip()
            if code and not code.startswith("#"):
                codes.add(code)  # codes are compared exactly, so no upper()
    return codes


def parse_datetime(text: str) -> datetime | None:
    """Return the datetime for text written exactly as YYYY-MM-DD HH:MM.

    Returns None when the text has another shape or is not a real date/time.
    Two steps are needed: the regular expression enforces the exact shape
    (zero padding, single space, no seconds), because strptime would also
    accept "2025-1-5 9:3". The datetime constructor then checks that the
    values exist: month 13, 30 February and hour 24 all raise ValueError.
    """
    match = _DATETIME_RE.fullmatch(text)
    if match is None:
        return None
    try:
        return datetime(*map(int, match.groups()))
    except ValueError:
        return None


def validate_row(fields: list[str], airports: set[str]) -> str | None:
    """Check one CSV row (fields as returned by csv.reader, not yet stripped).

    Return None if the row is valid, otherwise the error code of the
    FIRST failing check (checks 1-11 in the specification, in order).
    Does not check for duplicates.
    """
    # 1. The number of fields is counted before anything else, because the
    #    other checks need exactly six values to work with.
    if len(fields) != 6:
        return "WRONG_FIELD_COUNT"

    flight_id, origin, destination, departure, arrival, price = map(str.strip, fields)

    # 2. Any empty field (also one that held only spaces before stripping).
    if "" in (flight_id, origin, destination, departure, arrival, price):
        return "MISSING_FIELD"

    # 3. Flight id: 2-8 ASCII letters or digits.
    if not _FLIGHT_ID_RE.fullmatch(flight_id):
        return "INVALID_FLIGHT_ID"

    # 4-5. Airport codes: three uppercase ASCII letters AND listed in the file.
    if not _AIRPORT_CODE_RE.fullmatch(origin) or origin not in airports:
        return "INVALID_ORIGIN"
    if not _AIRPORT_CODE_RE.fullmatch(destination) or destination not in airports:
        return "INVALID_DESTINATION"

    # 6. A flight cannot start and end at the same airport.
    if origin == destination:
        return "SAME_ORIGIN_DESTINATION"

    # 7-8. Both date-times must be real and written exactly as specified.
    departure_time = parse_datetime(departure)
    if departure_time is None:
        return "INVALID_DEPARTURE"
    arrival_time = parse_datetime(arrival)
    if arrival_time is None:
        return "INVALID_ARRIVAL"

    # 9. This comparison needs both times to be valid, so it comes after 7-8.
    if arrival_time <= departure_time:
        return "ARRIVAL_NOT_AFTER_DEPARTURE"

    # 10. Price: whatever float() accepts, but nan and inf are not real prices.
    #     The finite check has to come before the sign check, because
    #     comparisons with nan are always False and would let it slip through.
    try:
        value = float(price)
    except ValueError:
        return "INVALID_PRICE"
    if not math.isfinite(value):
        return "INVALID_PRICE"

    # 11. Zero and negative prices.
    if value <= 0:
        return "NON_POSITIVE_PRICE"

    return None


def to_record(fields: list[str]) -> dict:
    """Turn a valid row into a flight record dictionary.

    Keys: flight_id, origin, destination, departure_datetime,
    arrival_datetime (stripped strings) and price (float).
    """
    flight_id, origin, destination, departure, arrival, price = map(str.strip, fields)
    return {
        "flight_id": flight_id,
        "origin": origin,
        "destination": destination,
        "departure_datetime": departure,
        "arrival_datetime": arrival,
        "price": float(price),
    }
