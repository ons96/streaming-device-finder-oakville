# Brainstorm

Task #1275 / #1125 triage for `ons96/streaming-device-finder-oakville`.

## Problem

Find streaming devices (Chromecast, Roku, Fire TV, Apple TV, NVIDIA Shield) for sale
within a radius of Oakville, ON, without manually scrolling through Kijiji and
Craigslist every day.

## Options considered

1. **CLI scraper + static report (chosen).** Scrapes marketplace result pages, filters
   listings by device model, price and distance from Oakville, writes a Markdown + JSON
   report. No API keys, no accounts, no server to run.
2. **Notify-on-match service.** A watcher that emails on a new match. Strictly more
   moving parts (mail credentials, scheduler, state store) and needs the matching
   heuristics to be good first.
3. **Hosted web app.** Bigger surface area than the problem deserves at this stage.

Option 1 gives a usable vertical slice in one sitting and leaves 2 as a follow-up.

## Verdict for #1125

```
BUILD: worth building.
The Oakville streaming-device search is a small, self-contained tool with a clear user loop.
A runnable vertical slice exists: offline sample listings flow through model, price and distance filtering into a Markdown + JSON report.
No auth, no third-party API keys and no external service accounts are needed, so the CI check stays cheap.
Kill criteria not met: the repo is no longer an auto-generated stub and the README documents the remaining gaps.
```
