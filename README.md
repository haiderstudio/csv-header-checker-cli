# csv-header-checker-cli

Check CSV headers are clean and match the rows, fail CI on a bad header.

[![CI](https://github.com/haiderstudio/csv-header-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/csv-header-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`csv_header_checker` reads the CSV files and folders you name and
checks the header row of each one: no empty column names, no
duplicate column names, no leading or trailing spaces in a column
name, and every row has the same number of fields as the header.
Every problem names the file and line. It exits 1 on any problem, so
it can fail a CI run before a bad CSV ships.

- `--require NAME` asks for a column that must be in the header
  (repeatable). A file that is otherwise clean but misses a required
  column fails.
- Folders are walked recursively unless `--no-recursive` is given.
  `.git` folders are never walked, and folder links are never
  followed. `--exclude PATTERN` skips files by glob (repeatable).
- `--json` prints the result as JSON instead of plain text, for
  scripts. The summary line goes to standard error, so standard
  output stays clean JSON.
- A file that is empty, has no header row, or cannot be read as
  UTF-8 is reported as a problem, not skipped silently.
- Blank lines are skipped, and quoted fields that hold commas or
  line breaks are read properly — a row inside quotes is one row,
  and the line numbers point at the real lines.

## What it does NOT do

- It does not check the data in the rows — only the header names
  and the number of fields per row. Checking that a column holds
  numbers or dates is a different tool's job.
- It does not check that two CSV files agree with each other. That
  is the job of [csv-diff-cli](https://github.com/haiderstudio/csv-diff-cli),
  which diffs two CSVs by a key column.
- It does not fix or rewrite a file. A bad header is reported, not
  repaired.
- It does not fetch files from the network. Every input is a local
  file or folder.

## Who it is for

Anyone who keeps CSV files around and wants a quick, scriptable
check that the header row is well formed: a developer adding a CI
step that fails the build on a broken export, someone hand-editing a
spreadsheet export before importing it, or anyone piping a CSV
through a checker before committing it. If the header is clean, you
get a plain OK line; if it is not, the report says exactly which
line broke.

## How this differs from similar tools

CSV header checks already exist, but none of them is this exact
tool. The exact name `csv-header-checker-cli` matches 0 repositories
on GitHub. The closest same-named repo,
funnyhcat-dotcom/csv-header-doctor (0 stars, JavaScript), audits
headers for duplicates, empty columns, unsafe formulas, and messy
names — it also checks formulas, which this tool does not, and it is
a JavaScript tool, not a Python one. josezuma/csv-validator (0
stars, Python) is a CLI that checks column count, data types, and
header consistency — broader than this slice, because it also checks
data types. daviaquino87/validator-csv (5 stars, JavaScript) checks
the integrity and quality of CSV files as a package, not as a
single-purpose CLI. The wider field is mostly noise: HTTP security
header checkers and tools that take a CSV list of targets. This tool
does a narrower job: a Python standard-library-only CLI that checks
one file's header row, reports every problem with a file and line,
checks required columns when you ask, and exits 1 on a bad header
for CI — no install beyond Python, no data-type checks, no network.

## Install

Python standard library only — no packages to download. You need
Python 3.8 or newer. Clone the repo and run it in place:

```
git clone https://github.com/haiderstudio/csv-header-checker-cli.git
cd csv-header-checker-cli
python3 src/csv_header_checker.py examples/good.csv
```

```
OK — 1 file(s) checked, headers are clean.
```

## Usage

Check one file:

```
python3 src/csv_header_checker.py examples/good.csv
```

Check several files at once:

```
python3 src/csv_header_checker.py examples/good.csv examples/bad-headers.csv
```

```
FAIL examples/bad-headers.csv:1: column 2 ' name ' has leading or trailing spaces
FAIL examples/bad-headers.csv:1: column 4 has an empty name
FAIL examples/bad-headers.csv:1: duplicate column name 'id'
Checked 2 file(s), 3 problem(s) in 1 file(s).
```

Check a whole folder:

```
python3 src/csv_header_checker.py examples/
```

Ask for a column that must be there:

```
python3 src/csv_header_checker.py examples/missing-required.csv --require price
```

```
FAIL examples/missing-required.csv:1: required column 'price' is missing
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Machine-readable output with `--json` (the summary goes to
standard error, so standard output is clean JSON):

```
python3 src/csv_header_checker.py examples/good.csv --json
```

```
{
  "files": [
    {
      "file": "examples/good.csv",
      "ok": true,
      "problems": []
    }
  ],
  "summary": {
    "checked": 1,
    "ok": 1,
    "failed": 0,
    "problems": 0
  }
}
```

Exit codes: 0 when every header is clean, 1 when any file has a
problem, 2 for a usage problem (no files given, a bad flag).

## Examples

### 1. A bad header — spaces, an empty name, and a duplicate

`examples/bad-headers.csv` has a header with all three header
problems at once:

```
python3 src/csv_header_checker.py examples/bad-headers.csv
```

```
FAIL examples/bad-headers.csv:1: column 2 ' name ' has leading or trailing spaces
FAIL examples/bad-headers.csv:1: column 4 has an empty name
FAIL examples/bad-headers.csv:1: duplicate column name 'id'
Checked 1 file(s), 3 problem(s) in 1 file(s).
```

### 2. Rows with the wrong number of fields

`examples/wrong-width.csv` has a clean header, but one row is short
and one is long:

```
python3 src/csv_header_checker.py examples/wrong-width.csv
```

```
FAIL examples/wrong-width.csv:2: row has 2 field(s), header has 3
FAIL examples/wrong-width.csv:3: row has 4 field(s), header has 3
Checked 1 file(s), 2 problem(s) in 1 file(s).
```

### 3. The bundled examples, all at once

```
sh examples/run-example.sh
```

The script checks the good file (passes), then the bad-headers and
wrong-width files (both fail, on purpose), then the
missing-required file with `--require price` (fails, on purpose).
Its full output is in `examples/sample-output.txt`. The failing runs
exit 1, which is the expected result — the script ends with exit 0
so it can be run as a demo.

## How it is tested

43 tests, standard library `unittest` only, no packages to install:

```
python3 tests/test_csv_header_checker.py
```

The tests cover: clean files and header-only files, empty column
names, leading and trailing spaces, duplicate names (exact and after
trimming spaces), required columns (present, missing, matching a
trimmed name), rows with too few and too many fields, blank lines
skipped, blank lines before the header, quoted fields with commas
and line breaks (with the real line number), empty files, files with
no header row, missing files, non-UTF-8 files, folder walking
(recursive, `--no-recursive`, `.git` skipped, `--exclude`), `--json`
output, `--version`, input files left unchanged, the bundled
examples (sample output compared byte-for-byte against a fresh run,
and the README-quoted outputs checked against it), and hygiene
checks (no placeholder text, no absolute paths, stdlib imports only,
`.env` first in `.gitignore`).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea of
checking CSV headers is not new — the similar tools named above
(funnyhcat-dotcom/csv-header-doctor, josezuma/csv-validator,
daviaquino87/validator-csv) are listed in "How this differs" — but
every line of code here is original, and the tool builds on nothing
but Python's standard library.
