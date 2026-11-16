"""Reading CSV files into flight records and error messages."""
import csv
import os

from validator import to_record, validate_row


def parse_files(paths: list[str], airports: set[str]) -> tuple[list[dict], list[str]]:
    """Process the CSV files in the order given.

    Return (records, errors):
      records - valid flight records, in input order
      errors  - one message per invalid row, in input order, formatted as
                "<file name>:<line number>: <ERROR_CODE> | <free text>"
                (base file name only, no timestamp or level, no newline)

    Also performs the DUPLICATE_FLIGHT check across all the files.
    Does not write any files and does not log anything itself.
    """
    records: list[dict] = []
    errors: list[str] = []
    # One set for the whole run, so a duplicate is also found when the first
    # flight is in an earlier file. Only VALID rows are added to it, so an
    # invalid row can never make a later valid row a "duplicate".
    seen: set[tuple[str, str]] = set()

    for path in paths:
        name = os.path.basename(path)
        # Iterating over the file reads one line at a time, so even a file of
        # many megabytes never has to be held in memory as a whole.
        # newline=None (the default) turns \r\n into \n, so Windows files work.
        with open(path, encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                if line_number == 1:
                    continue  # the header is always line 1 and is not validated
                text = line.rstrip("\r\n")
                stripped = text.strip()
                # Blank and comment lines are skipped silently. They still
                # count as lines, because enumerate() numbers every line.
                if not stripped or stripped.startswith("#"):
                    continue

                if '"' not in text:
                    # Without a double quote the csv module does nothing but
                    # cut at the commas, so split() gives the same fields much
                    # faster (creating a csv.reader per line is the slow part
                    # of reading a file with hundreds of thousands of rows).
                    fields = text.split(",")
                else:
                    try:
                        fields = next(csv.reader([text]))
                    except csv.Error:
                        fields = []  # a line csv cannot split gets WRONG_FIELD_COUNT

                code = validate_row(fields, airports)
                if code is not None:
                    errors.append(f"{name}:{line_number}: {code} | {text}")
                    continue

                record = to_record(fields)
                key = (record["flight_id"], record["departure_datetime"])
                if key in seen:
                    errors.append(f"{name}:{line_number}: DUPLICATE_FLIGHT | {text}")
                    continue
                seen.add(key)
                records.append(record)

    return records, errors
