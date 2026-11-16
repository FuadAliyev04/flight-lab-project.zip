"""Flight Schedule Parser and Query Tool - command-line entry point.

Run from the project folder, for example:
    python flight_parser.py -i data/db.csv -a data/airports.txt
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime

from csv_loader import parse_files
from query import run_queries
from validator import load_airports

# Plain ASCII, no spaces or underscores (they are used in the response file name).
STUDENT_ID = "251ADB190"
FIRST_NAME = "Fuad"
LAST_NAME = "Aliyev"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flight_parser.py",
        description="Validate flight CSV files, store valid flights as JSON and run queries.",
        # No abbreviations of long options: an unknown argument must stay an error.
        allow_abbrev=False,
    )
    parser.add_argument("-i", dest="csv_file", metavar="FILE", help="parse a single CSV file")
    parser.add_argument("-d", dest="folder", metavar="FOLDER",
                        help="parse every .csv file in a folder (sorted by name)")
    parser.add_argument("-j", dest="json_db", metavar="FILE",
                        help="load an existing JSON database instead of parsing CSV files")
    parser.add_argument("-a", dest="airports", metavar="FILE",
                        help="airport list file (required with -i and -d)")
    parser.add_argument("-o", dest="output", metavar="FILE",
                        help="path of the JSON database to write (default: db.json)")
    parser.add_argument("-q", dest="queries", metavar="FILE", help="JSON file with queries to run")
    parser.add_argument("-r", dest="response_dir", metavar="FOLDER", default=".",
                        help="folder for the query response file (default: current directory)")
    return parser


def check_usage(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """The rules argparse cannot express itself. parser.error() exits with code 2."""
    sources = [args.csv_file, args.folder, args.json_db]
    if sum(source is not None for source in sources) != 1:
        parser.error("exactly one of -i, -d or -j is required")
    if args.json_db is None and args.airports is None:
        parser.error("-a is required with -i and -d")
    if args.json_db is not None and args.output is not None:
        parser.error("-o cannot be used with -j")


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_database(path: str) -> list[dict]:
    data = load_json(path)
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{path}: the database must be a JSON array of objects")
    return data


def load_queries(path: str):
    data = load_json(path)
    if not isinstance(data, (dict, list)):
        raise ValueError(f"{path}: the queries must be one object or an array of objects")
    return data


def csv_paths(args: argparse.Namespace) -> list[str]:
    if args.csv_file is not None:
        return [args.csv_file]
    # Only plain files whose name ends in .csv: no sub-folders, no other types.
    # sorted() makes the order (and so the database and the log) predictable.
    names = sorted(name for name in os.listdir(args.folder)
                   if name.endswith(".csv") and os.path.isfile(os.path.join(args.folder, name)))
    if not names:
        raise ValueError(f"no .csv files found in {args.folder}")
    return [os.path.join(args.folder, name) for name in names]


def write_error_log(log_path: str, errors: list[str], summary: str) -> None:
    """Write errors.log with the logging module (every error is one WARNING).

    The handler lives only inside this function. try/finally removes and closes
    it even when something fails, so that the next call of main() in the same
    process (as the autograder does) cannot write duplicate lines.
    """
    logger = logging.getLogger("flight_parser")
    logger.setLevel(logging.INFO)
    # mode="w" starts a fresh file on every run; the file exists even without errors.
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    try:
        logger.info(summary)
        for message in errors:
            logger.warning(message)
    finally:
        logger.removeHandler(handler)
        handler.close()


def write_response(folder: str, responses: list[dict]) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")  # current local time
    name = f"response_{STUDENT_ID}_{FIRST_NAME}_{LAST_NAME}_{stamp}.json"
    path = os.path.join(folder, name)
    write_json(path, responses)
    return path


def main(argv: list[str] | None = None) -> int:
    """Run the whole program and return the exit code (0, 1 or 2).

    argv is the argument list without the program name.
    None means use sys.argv[1:] (argparse does this for you).
    Do not call sys.exit() inside main(); return the code instead.
    """
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        check_usage(parser, args)
    except SystemExit as exit_request:
        # argparse exits by itself on usage errors (code 2) and on -h (code 0).
        # main() must return the code instead of exiting.
        return exit_request.code if isinstance(exit_request.code, int) else 2

    try:
        # The query file is read first, so a broken one stops the run before
        # any output file is written.
        queries = load_queries(args.queries) if args.queries is not None else None

        if args.json_db is not None:
            database = load_database(args.json_db)
            print(f"Loaded {len(database)} flights from {args.json_db}")
        else:
            airports = load_airports(args.airports)
            records, errors = parse_files(csv_paths(args), airports)
            database = records

            db_path = args.output if args.output is not None else "db.json"
            write_json(db_path, records)
            # errors.log goes into the same folder as the database file.
            log_path = os.path.join(os.path.dirname(os.path.abspath(db_path)), "errors.log")
            summary = f"{len(records)} valid flights, {len(errors)} invalid rows"
            write_error_log(log_path, errors, summary)
            print(f"{summary}; database written to {db_path}")

        if queries is not None:
            path = write_response(args.response_dir, run_queries(database, queries))
            print(f"Query response written to {path}")
        return 0
    except (OSError, ValueError, RecursionError) as problem:
        # A missing file, bad JSON or a wrong shape: one clean line, no traceback.
        print("Error: " + " ".join(str(problem).split()), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
