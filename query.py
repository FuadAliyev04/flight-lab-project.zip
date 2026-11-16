"""Running queries against the flight database."""
import math

from validator import parse_datetime

RECORD_KEYS = ("flight_id", "origin", "destination",
               "departure_datetime", "arrival_datetime", "price")

_TEXT_KEYS = ("flight_id", "origin", "destination")
_DATETIME_KEYS = ("departure_datetime", "arrival_datetime")
_NUMBER_KEYS = ("price", "min_price")


def _is_number(value) -> bool:
    """True for ints and floats, but not for booleans (bool is a subclass of int)."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True  # also very large ints, for which math.isfinite would fail
    return isinstance(value, float) and math.isfinite(value)


def _is_valid(query) -> bool:
    """Check keys, value types and the rule that 'order' needs 'sort_by'."""
    if not isinstance(query, dict):
        return False
    for key, value in query.items():
        if key in _TEXT_KEYS:
            if not isinstance(value, str):
                return False
        elif key in _DATETIME_KEYS:
            if not isinstance(value, str) or parse_datetime(value) is None:
                return False
        elif key in _NUMBER_KEYS:
            if not _is_number(value):
                return False
        elif key == "sort_by":
            if not isinstance(value, str) or value not in RECORD_KEYS:
                return False
        elif key == "order":
            if value not in ("asc", "desc"):
                return False
        elif key == "limit":
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return False
        else:
            return False  # unknown key
    return not ("order" in query and "sort_by" not in query)


def _matches(flight: dict, query: dict) -> bool:
    """A flight matches when it passes EVERY filter in the query (AND)."""
    for key, value in query.items():
        if key in _TEXT_KEYS and flight[key] != value:
            return False
        # Date-times have a fixed width and are zero padded, so comparing the
        # strings gives the same answer as comparing real datetimes.
        if key == "departure_datetime" and flight[key] < value:
            return False  # must depart at or after the given time
        if key == "arrival_datetime" and flight[key] > value:
            return False  # must arrive at or before the given time
        if key == "price" and flight["price"] > value:
            return False
        if key == "min_price" and flight["price"] < value:
            return False
    return True


def run_query(db: list[dict], query: dict) -> dict:
    """Return one response entry for one query object.

    Valid query:   {"query": query, "matches": [...]}
    Invalid query: {"query": query, "error": "INVALID_QUERY", "matches": []}
    """
    if not _is_valid(query):
        return {"query": query, "error": "INVALID_QUERY", "matches": []}

    matches = [flight for flight in db if _matches(flight, query)]

    if "sort_by" in query:
        # sorted() is stable, also with reverse=True: flights with equal sort
        # values keep their database order in both directions.
        matches = sorted(matches, key=lambda flight: flight[query["sort_by"]],
                         reverse=query.get("order", "asc") == "desc")

    if "limit" in query:
        matches = matches[:query["limit"]]  # limit is applied AFTER sorting

    # Copies, so a caller that changes the response cannot change the database.
    return {"query": query, "matches": [dict(flight) for flight in matches]}


def run_queries(db: list[dict], queries: dict | list) -> list[dict]:
    """Accept one query object or a list of them; always return a list."""
    if isinstance(queries, dict):
        queries = [queries]
    if not isinstance(queries, list):
        raise ValueError("queries must be one object or an array of objects")
    return [run_query(db, query) for query in queries]
