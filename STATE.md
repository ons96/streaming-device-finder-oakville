# State

Last update: 2026-11-03 (task #1275, branch `work/1275`)

## Current status

Working vertical slice. `python search.py --samples` runs end to end offline and
writes `reports/SEARCH_REPORT.md` + `reports/search_results.json`.

## Done

- `search.py` rewritten into a testable CLI: argument parsing, lazy Playwright import,
  sample-file and JSON-file input modes, device-model extraction, price parsing,
  GTA location geocoding, Haversine distance filtering, deduplication, Markdown/JSON
  reporting.
- `data/sample_listings.json`: offline listings covering accept/reject cases.
- `tests/test_search.py`: unit tests plus an end-to-end sample run (9 tests).
- `README.md`: how to run it and what it does not do yet.
- `.github/workflows/search-streaming-devices.yml`: installs `requirements.txt`, runs
  the tests, runs the search and uploads the report artifact.

## Next

- Facebook Marketplace support (needs a logged-in session).
- Replace the hand-written GTA coordinate table with a real geocoder.
- Notify-on-match (option 2 in BRAINSTORM.md) once matching quality is good.

## Open questions

- Do marketplace terms of service allow automated scraping? Needs a decision before
  scheduled runs are added.
- Should listings with an unknown location be kept or dropped by default?
