#!/bin/sh
# Demo: check the good file (passes), then the bad files (fail, on
# purpose), then the good file with a required column it does not
# have (fails). The failing runs exit 1, which is the expected
# result — the script ends with exit 0 so it can be run as a demo.
cd "$(dirname "$0")/.."
python3 src/csv_header_checker.py examples/good.csv
python3 src/csv_header_checker.py examples/bad-headers.csv || true
python3 src/csv_header_checker.py examples/wrong-width.csv || true
python3 src/csv_header_checker.py examples/missing-required.csv --require price || true
