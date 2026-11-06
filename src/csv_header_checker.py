"""Check CSV headers are clean and match the rows.

Reads one or more CSV files and checks the header row of each one:
no empty column names, no duplicate column names, no leading or
trailing spaces in a column name, and every row has the same number
of fields as the header. `--require NAME` asks for a column that must
be present. Every problem names the file and line; exits 1 on any
problem, so it can fail a CI run, and 0 when every header is clean.

Report-only: it never writes to an input file.
Standard library only — no packages to install.
"""

import argparse
import csv
import fnmatch
import json
import sys
from pathlib import Path

VERSION = "1.0.0"


def check_file(path, required):
    """Check one CSV file.

    Returns a list of "path:line: message" problem strings; an empty
    list means the file's headers are clean.
    """
    problems = []
    try:
        handle = open(path, newline="", encoding="utf-8")
    except OSError as exc:
        return [f"{path}: {exc.strerror or exc}"]
    with handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            return [f"{path}: file is empty"]
        except csv.Error as exc:
            return [f"{path}: {exc}"]
        except UnicodeDecodeError:
            return [f"{path}: file is not valid UTF-8"]
        header_line = reader.line_num
        # Skip blank lines before the header; the header is the first
        # record with any content.
        while not header or all(field == "" for field in header):
            try:
                header = next(reader)
            except StopIteration:
                return [f"{path}: file has no header row"]
            except csv.Error as exc:
                return [f"{path}: {exc}"]
            except UnicodeDecodeError:
                return [f"{path}: file is not valid UTF-8"]
            header_line = reader.line_num
        stripped = [name.strip() for name in header]
        for index, name in enumerate(header, start=1):
            if name == "":
                problems.append(
                    f"{path}:{header_line}: column {index} has an "
                    f"empty name"
                )
            elif name != name.strip():
                problems.append(
                    f"{path}:{header_line}: column {index} {name!r} "
                    f"has leading or trailing spaces"
                )
        seen = {}
        for name in stripped:
            if name == "":
                continue
            if name in seen:
                problems.append(
                    f"{path}:{header_line}: duplicate column "
                    f"name {name!r}"
                )
            else:
                seen[name] = True
        for name in required:
            if name not in stripped:
                problems.append(
                    f"{path}:{header_line}: required column "
                    f"{name!r} is missing"
                )
        try:
            for fields in reader:
                line_no = reader.line_num
                if not fields or all(field == "" for field in fields):
                    continue  # blank line
                if len(fields) != len(header):
                    problems.append(
                        f"{path}:{line_no}: row has {len(fields)} "
                        f"field(s), header has {len(header)}"
                    )
        except csv.Error as exc:
            problems.append(f"{path}: {exc}")
        except UnicodeDecodeError:
            problems.append(f"{path}: file is not valid UTF-8")
    return problems


def collect(paths, recursive, excludes):
    """Turn the named files and folders into a list of CSV files.

    Returns (files, problems) where problems are fatal
    "path: message" strings for inputs that do not exist.
    """
    files = []
    problems = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            pattern = "**/*.csv" if recursive else "*.csv"
            for found in sorted(path.glob(pattern)):
                if (
                    found.is_file()
                    and ".git" not in found.parts
                    and not _excluded(found, excludes)
                ):
                    files.append(found)
        else:
            problems.append(f"{raw}: no such file or folder")
    return files, problems


def _excluded(path, excludes):
    return any(
        fnmatch.fnmatch(path.name, pattern)
        or fnmatch.fnmatch(str(path), pattern)
        for pattern in excludes
    )


def run(argv=None):
    """Run the checker. Returns an exit code: 0 clean, 1 problems,
    2 usage error."""
    parser = argparse.ArgumentParser(
        prog="csv_header_checker",
        description="Check CSV headers are clean and match the rows.",
    )
    parser.add_argument("paths", nargs="*", help="CSV files or folders")
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        metavar="NAME",
        help="column that must be in the header (repeatable)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="do not walk folders below the top level",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="skip files matching this glob (repeatable)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the result as JSON instead of plain text",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {VERSION}"
    )
    args = parser.parse_args(argv)
    if not args.paths:
        parser.error("no files or folders given")
    files, collect_problems = collect(
        args.paths, not args.no_recursive, args.exclude
    )
    results = []
    for path in files:
        found = check_file(path, args.require)
        results.append((str(path), found))
    all_problems = collect_problems + [
        problem for _, found in results for problem in found
    ]
    failed = [name for name, found in results if found]
    if args.json:
        payload = {
            "files": [
                {"file": name, "ok": not found, "problems": found}
                for name, found in results
            ],
            "summary": {
                "checked": len(results),
                "ok": len(results) - len(failed),
                "failed": len(failed),
                "problems": len(all_problems),
            },
        }
        if collect_problems:
            payload["errors"] = collect_problems
        print(json.dumps(payload, indent=2))
        print(
            f"Checked {len(results)} file(s), "
            f"{len(all_problems)} problem(s).",
            file=sys.stderr,
        )
    else:
        for problem in all_problems:
            print(f"FAIL {problem}")
        if all_problems:
            print(
                f"Checked {len(results)} file(s), "
                f"{len(all_problems)} problem(s) in "
                f"{len(failed) + len(collect_problems)} "
                f"file(s)."
            )
        else:
            print(
                f"OK — {len(results)} file(s) checked, "
                f"headers are clean."
            )
    return 1 if all_problems else 0


def main(argv=None):
    try:
        return run(argv)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
