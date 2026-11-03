# Streaming Device Finder - Oakville, ON

Finds streaming devices (Chromecast, Roku, Fire TV, Apple TV, NVIDIA Shield) listed
for sale near Oakville, Ontario, filters the listings down to the ones worth a look,
and writes a Markdown + JSON report.

## What it does today

- Scrapes the Kijiji and Craigslist Toronto search results for streaming devices.
- Recognises the device model of each listing and drops listings that are not
  streaming devices (or are broken/irrelevant models).
- Parses the advertised price and drops listings above `--max-price`.
- Geocodes GTA location strings (Oakville, Mississauga, Burlington, Toronto, ...) and
  drops listings farther than `--radius` km from the Oakville reference point.
- Writes `reports/SEARCH_REPORT.md` and `reports/search_results.json`.
- Ships with sample listings so the whole pipeline can be run offline:
  `python search.py --samples`.

## How to run it

Requirements: Python 3.9+ and (for live scraping) Playwright with Chromium.

```bash
pip install -r requirements.txt
playwright install --with-deps chromium
```

Run the offline vertical slice (no network, uses `data/sample_listings.json`):

```bash
python search.py --samples --output-dir reports
```

Run a live search:

```bash
python search.py --site all --radius 50 --max-price 200 --output-dir reports
```

Useful options:

| Option | Meaning |
|---|---|
| `--terms` | Search terms passed to the marketplace search box. |
| `--radius` | Maximum distance from Oakville in km (default `50`). |
| `--max-price` | Maximum price in CAD (default `200`). |
| `--site` | `kijiji`, `craigslist`, `facebook`, `all` or `samples`. |
| `--samples` | Use the bundled sample listings instead of scraping. |
| `--input FILE` | Read raw listings from a JSON file instead of scraping. |
| `--output-dir DIR` | Where the reports are written (default `reports`). |

Run the tests:

```bash
python -m pytest
```

The GitHub workflow **Search Streaming Devices** (`.github/workflows/search-streaming-devices.yml`)
runs the same command on demand via `workflow_dispatch` and uploads the reports as an
artifact.

## What it does not do yet

- No Facebook Marketplace scraping: it requires a logged-in session, so the site is
  currently skipped.
- No notifications: nothing watches for new listings, you have to run it.
- Location strings are matched against a small hand-written table of GTA
  coordinates, so listings outside that table keep an `unknown` distance and are not
  distance-filtered. There is no geocoding service integration.
- No price history, seller ratings, shipping or pickup-time information.
- Scraping depends on the marketplace page layout, so selectors may break when the
  sites change, and there is no rate limiting or retry/backoff logic.
- The report is static; there is no web UI, no email/Slack output and no database.

## Layout

```
search.py                 # CLI, filtering, report generation
data/sample_listings.json # offline sample listings for the vertical slice
tests/test_search.py      # unit + end-to-end tests
```
