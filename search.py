#!/usr/bin/env python3
"""
Streaming device finder for Oakville, ON.

Collects marketplace listings for streaming devices (Chromecast, Roku, Fire TV,
Apple TV, NVIDIA Shield), filters them by price and distance from Oakville, and
writes a Markdown + JSON report.
"""

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path

OAKVILLE_LAT = 43.453
OAKVILLE_LON = -79.500

DEFAULT_TERMS = 'streaming device OR chromecast OR roku OR fire tv'
DEFAULT_RADIUS_KM = 50
DEFAULT_MAX_PRICE = 200
DEFAULT_OUTPUT_DIR = 'reports'

DATA_DIR = Path(__file__).resolve().parent / 'data'
SAMPLE_LISTINGS_PATH = DATA_DIR / 'sample_listings.json'

DEVICE_PATTERNS = {
    'chromecast': ['google chromecast', 'chromecast 4k', 'chromecast hd', 'chromecast ultra'],
    'roku': ['roku express', 'roku streaming stick', 'roku ultra', 'roku 4k'],
    'fire tv': ['amazon fire tv', 'fire tv stick', 'fire tv cube'],
    'apple tv': ['apple tv', 'airplay'],
    'nvidia shield': ['nvidia shield', 'shield tv'],
}

IRRELEVANT_MODELS = ['chromecast 1st gen', 'chromecast 2nd gen', 'old tv', 'dumb tv', 'broken']
IRRELEVANT_MARKERS = ['broken', 'not working', "doesn't work", 'does not work', 'for parts', 'dumb tv']

# Approximate coordinates for GTA locations that show up in listing location
# strings. Used to turn "Oakville / Peel Region" into a distance in km.
LOCATION_COORDS = {
    'oakville': (43.453, -79.500),
    'oakville downtown': (43.467, -79.688),
    'oakville north': (43.505, -79.620),
    'halton region': (43.420, -79.850),
    'peel region': (43.590, -79.640),
    'mississauga': (43.589, -79.644),
    'brampton': (43.731, -79.762),
    'etobicoke': (43.650, -79.570),
    'toronto': (43.653, -79.383),
    'north york': (43.746, -79.411),
    'east york': (43.691, -79.365),
    'scarborough': (43.776, -79.231),
    'vaughan': (43.856, -79.508),
    'richmond hill': (43.881, -79.439),
    'markham': (43.849, -79.338),
    'newmarket': (44.051, -79.417),
    'milton': (43.518, -79.877),
    'georgetown': (43.648, -79.904),
    'burlington': (43.318, -79.843),
    'hamilton': (43.255, -79.872),
    'stoney creek': (43.255, -79.721),
    'ajax': (43.850, -79.100),
    'pickering': (43.838, -79.235),
    'whitby': (43.876, -78.939),
    'oshawa': (43.900, -78.850),
    'oakville/halton': (43.453, -79.500),
}

PRICE_RE = re.compile(r'\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)')
BARE_PRICE_RE = re.compile(r'^\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*$')


def parse_price(text):
    """Turn '$1,200.00' or '120' into a float, or None when there is no price."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    match = PRICE_RE.search(str(text))
    if not match:
        match = BARE_PRICE_RE.match(str(text))
    if not match:
        stripped = str(text).strip().lower()
        if stripped in ('free', 'free / 0'):
            return 0.0
        return None
    try:
        return float(match.group(1).replace(',', ''))
    except ValueError:
        return None


def geocode_location(location):
    """Return (lat, lon) for a GTA location string, or None when unknown."""
    if not location:
        return None
    lowered = str(location).lower()
    for needle, coords in LOCATION_COORDS.items():
        if needle in lowered:
            return coords
    return None


class StreamingDeviceSearcher:
    def __init__(self):
        self.search_terms = DEFAULT_TERMS
        self.radius_km = DEFAULT_RADIUS_KM
        self.max_price = DEFAULT_MAX_PRICE
        self.site = 'all'
        self.output_dir = Path(DEFAULT_OUTPUT_DIR)
        self.use_samples = False
        self.input_file = None
        self.results = []
        self.rejected = []

    def parse_args(self, argv=None):
        parser = argparse.ArgumentParser(description='Search streaming devices near Oakville, ON')
        parser.add_argument('--terms', type=str, default=DEFAULT_TERMS)
        parser.add_argument('--radius', type=int, default=DEFAULT_RADIUS_KM,
                            help='Maximum distance from Oakville in km')
        parser.add_argument('--max_price', type=int, default=DEFAULT_MAX_PRICE,
                            help='Maximum price in CAD')
        parser.add_argument('--site', type=str, default='all',
                            choices=['kijiji', 'craigslist', 'facebook', 'all', 'samples'])
        parser.add_argument('--output-dir', type=str, default=DEFAULT_OUTPUT_DIR)
        parser.add_argument('--samples', action='store_true',
                            help='Use the bundled sample listings instead of scraping')
        parser.add_argument('--input', type=str, default=None,
                            help='Read raw listings from a JSON file instead of scraping')
        args = parser.parse_args(argv)
        self.search_terms = args.terms
        self.radius_km = args.radius
        self.max_price = args.max_price
        self.site = args.site
        self.output_dir = Path(args.output_dir)
        self.use_samples = args.samples or args.site == 'samples'
        self.input_file = args.input
        return args

    def calculate_distance(self, lat2, lon2):
        """Haversine distance in km from the Oakville reference point."""
        r = 6371.0
        lat1, lon1 = OAKVILLE_LAT, OAKVILLE_LON
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + (
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r * c

    def extract_device_model(self, title, description):
        """Extract a streaming device model from a title/description pair."""
        title_lower = (title or '').lower()
        description_lower = (description or '').lower()

        for model, patterns in DEVICE_PATTERNS.items():
            for pattern in patterns:
                if pattern in title_lower or pattern in description_lower:
                    return model
        return None

    def is_irrelevant_model(self, model):
        """Reject old/irrelevant models."""
        if not model:
            return False
        return any(marker in model for marker in IRRELEVANT_MODELS)

    def has_irrelevant_marker(self, text):
        """True when the listing text advertises a broken/part-only device."""
        lowered = (text or '').lower()
        return any(marker in lowered for marker in IRRELEVANT_MARKERS)

    def load_sample_listings(self):
        """Load the bundled offline sample listings."""
        return self._load_listing_file(SAMPLE_LISTINGS_PATH)

    def load_listings_from_file(self, path):
        """Load raw listings from a JSON file (list of listings or {'listings': [...]})."""
        return self._load_listing_file(Path(path))

    def _load_listing_file(self, path):
        with open(path, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            listings = payload
        elif isinstance(payload, dict):
            listings = payload.get('listings', [])
        else:
            listings = []
        for listing in listings:
            listing.setdefault('description', '')
            listing.setdefault('timestamp', datetime.now().isoformat())
        return listings

    def scrape_kijiji(self):
        """Scrape Kijiji for listings."""
        listings = []
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                search_url = (
                    f'https://www.kijiji.ca/b-streaming-devices/oakville-far-north-ontario/k0c1700'
                    f'?price=0..{self.max_price}&radius={self.radius_km}'
                )
                page.goto(search_url, wait_until='networkidle')

                cards = page.locator('.regular-ad')
                for i in range(cards.count()):
                    card = cards.nth(i)
                    link = card.locator('a').get_attribute('href')
                    listings.append({
                        'site': 'kijiji',
                        'title': self._text(card, 'a'),
                        'description': self._text(card, '.description'),
                        'price': self._text(card, '.price'),
                        'location': self._text(card, '.location'),
                        'link': link,
                        'timestamp': datetime.now().isoformat(),
                    })

                browser.close()
        except Exception as exc:
            print(f'Kijiji scrape error: {exc}')
        return listings

    def scrape_craigslist(self):
        """Scrape Craigslist for listings."""
        listings = []
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                query = self.search_terms.replace(' ', '+')
                search_url = (
                    f'https://toronto.craigslist.org/search/sss?query={query}'
                    f'&max_price={self.max_price}&radius={self.radius_km}'
                )
                page.goto(search_url, wait_until='networkidle')

                rows = page.locator('.result-row')
                for i in range(min(20, rows.count())):
                    row = rows.nth(i)
                    listings.append({
                        'site': 'craigslist',
                        'title': self._text(row, '.result-title'),
                        'description': '',
                        'price': self._text(row, '.result-price'),
                        'location': self._text(row, '.result-hood'),
                        'link': row.locator('a').get_attribute('href'),
                        'timestamp': datetime.now().isoformat(),
                    })

                browser.close()
        except Exception as exc:
            print(f'Craigslist scrape error: {exc}')
        return listings

    def scrape_facebook(self):
        """Facebook Marketplace needs a logged-in session; not automated yet."""
        print('Facebook Marketplace requires login - skipping automated scrape')
        return []

    @staticmethod
    def _text(locator, selector):
        try:
            value = locator.locator(selector).first.text_content()
        except Exception:
            return ''
        return (value or '').strip()

    def search_all_sites(self):
        """Collect raw listings from the requested source(s)."""
        if self.input_file:
            self.results.extend(self.load_listings_from_file(self.input_file))
            return self.results
        if self.use_samples:
            self.results.extend(self.load_sample_listings())
            return self.results
        if self.site in ('all', 'kijiji'):
            self.results.extend(self.scrape_kijiji())
        if self.site in ('all', 'craigslist'):
            self.results.extend(self.scrape_craigslist())
        if self.site in ('all', 'facebook'):
            self.results.extend(self.scrape_facebook())
        return self.results

    def classify(self, listing):
        """Attach model, price, distance and a keep/reject decision to a listing."""
        title = listing.get('title') or ''
        description = listing.get('description') or ''
        model = self.extract_device_model(title, description)
        price_value = parse_price(listing.get('price'))
        coords = geocode_location(listing.get('location'))
        distance = self.calculate_distance(coords[0], coords[1]) if coords else None

        enriched = dict(listing)
        enriched['model'] = model
        enriched['price_value'] = price_value
        enriched['distance_km'] = round(distance, 1) if distance is not None else None
        enriched['location_coords'] = {'lat': coords[0], 'lon': coords[1]} if coords else None

        reasons = []
        if not model:
            reasons.append('not a recognised streaming device')
        if self.is_irrelevant_model(model) or self.has_irrelevant_marker(f'{title} {description}'):
            reasons.append('irrelevant or broken device')
        if price_value is None:
            reasons.append('no price listed')
        elif price_value > self.max_price:
            reasons.append(f'price above ${self.max_price}')
        if distance is not None and distance > self.radius_km:
            reasons.append(f'farther than {self.radius_km} km from Oakville')

        enriched['relevant'] = not reasons
        enriched['reject_reasons'] = reasons
        return enriched

    def process_results(self):
        """Classify, filter and deduplicate the collected listings."""
        kept = []
        seen = set()
        for raw in self.results:
            listing = self.classify(raw)
            key = (listing.get('site'), (listing.get('title') or '').strip().lower())
            if key in seen:
                continue
            seen.add(key)
            if listing['relevant']:
                kept.append(listing)
            else:
                self.rejected.append(listing)
        self.results = kept
        return self.results

    def build_report(self):
        return {
            'search_params': {
                'terms': self.search_terms,
                'radius_km': self.radius_km,
                'max_price': self.max_price,
                'site': self.site,
                'timestamp': datetime.now().isoformat(),
                'oakville_coords': {'lat': OAKVILLE_LAT, 'lon': OAKVILLE_LON},
            },
            'listings': self.results,
            'summary': {
                'total_listings': len(self.results),
                'devices_found': len([r for r in self.results if r.get('model')]),
                'rejected_listings': len(self.rejected),
            },
        }

    def generate_report(self):
        """Generate Markdown and JSON reports in the output directory."""
        report = self.build_report()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        json_path = self.output_dir / 'search_results.json'
        with open(json_path, 'w', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2, default=str)

        md_path = self.output_dir / 'SEARCH_REPORT.md'
        with open(md_path, 'w', encoding='utf-8') as handle:
            handle.write(self.render_markdown(report))

        print(f'Report generated: {json_path} and {md_path}')
        return json_path, md_path

    def render_markdown(self, report):
        params = report['search_params']
        summary = report['summary']
        lines = [
            '# Streaming Device Search Report - Oakville, ON',
            '',
            '**Search Parameters:**',
            f"- Terms: {params['terms']}",
            f"- Radius: {params['radius_km']} km",
            f"- Max Price: ${params['max_price']} CAD",
            f"- Site: {params['site']}",
            f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            '',
            '## Listings',
            '',
            '| Title | Model | Site | Price | Distance (km) | Location | Link |',
            '|---|---|---|---|---|---|---|',
        ]
        for result in report['listings']:
            title = (result.get('title') or '').replace('|', '\\|')
            price = result.get('price_value')
            price_text = f'${price:.0f}' if isinstance(price, float) else (result.get('price') or 'n/a')
            distance = result.get('distance_km')
            distance_text = f'{distance:.0f}' if distance is not None else 'unknown'
            link = result.get('link') or ''
            lines.append(
                f"| {title} | {result.get('model') or 'n/a'} | {result.get('site') or 'n/a'} | "
                f"{price_text} | {distance_text} | {result.get('location') or 'unknown'} | "
                f"[link]({link}) |"
            )
        lines += [
            '',
            f"**Summary:** Found {summary['total_listings']} streaming device listings "
            f"({summary['devices_found']} recognised models). "
            f"{summary['rejected_listings']} listings were filtered out.",
            '',
        ]
        return '\n'.join(lines)


def main(argv=None):
    searcher = StreamingDeviceSearcher()
    searcher.parse_args(argv)
    searcher.search_all_sites()
    searcher.process_results()
    searcher.generate_report()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
