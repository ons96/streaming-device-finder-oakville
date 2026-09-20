#!/usr/bin/env python3
"""
Automated streaming device search agent for Canadian sites.
Searches Kijiji, Facebook Marketplace, Craigslist for devices near Oakville, ON.
"""

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright
import math

OAKVILLE_LAT = 43.453
OAKVILLE_LON = -79.500

class StreamingDeviceSearcher:
    def __init__(self):
        self.search_terms = None
        self.radius_km = 50
        self.max_price = 200
        self.site = 'all'
        self.results = []

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Search streaming devices')
        parser.add_argument('--terms', type=str, default='streaming device OR chromecast OR roku OR fire tv')
        parser.add_argument('--radius', type=int, default=50)
        parser.add_argument('--max_price', type=int, default=200)
        parser.add_argument('--site', type=str, default='all', choices=['kijiji', 'craigslist', 'facebook', 'all'])
        args = parser.parse_args()
        self.search_terms = args.terms
        self.radius_km = args.radius
        self.max_price = args.max_price
        self.site = args.site

    def calculate_distance(self, lat2, lon2):
        """Haversine formula for distance from Oakville"""
        R = 6371  # Earth radius in km
        lat1, lon1 = OAKVILLE_LAT, OAKVILLE_LON
        dlat = (lat2 - lat1) * (3.14159 / 180)
        dlon = (lon2 - lon1) * (3.14159 / 180)
        a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def extract_device_model(self, title, description):
        """Extract device model from title/description"""
        title_lower = title.lower()
        description_lower = description.lower()
        
        # Common models
        models = {
            'chromecast': ['google chromecast', 'chromecast 4k', 'chromecast hd', 'chromecast ultra'],
            'roku': ['roku express', 'roku streaming stick', 'roku ultra', 'roku 4k'],
            'fire tv': ['amazon fire tv', 'fire tv stick', 'fire tv cube'],
            'apple tv': ['apple tv', 'airplay'],
            'nvidia shield': ['nvidia shield', 'shield tv']
        }
        
        for model, patterns in models.items():
            for pattern in patterns:
                if pattern in title_lower or pattern in description_lower:
                    return model
        return None

    def is_irrelevant_model(self, model):
        """Reject old/irrelevant models"""
        if not model:
            return False
        old_models = ['chromecast 1st gen', 'chromecast 2nd gen', 'old tv', 'dumb tv', 'broken']
        return any(m in model for m in old_models)

    def scrape_kijiji(self):
        """Scrape Kijiji for listings"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                search_url = f"https://www.kijiji.ca/b-streaming-devices/oakville-far-north-ontario/k0c1700?price=0..{self.max_price}&radius={self.radius_km}"
                page.goto(search_url, wait_until="networkidle")
                
                listings = page.locator('.regular-ad')
                for i in range(listings.count()):
                    listing = listings.nth(i)
                    title = listing.locator('a').text_content()
                    price = listing.locator('.price').text_content()
                    location = listing.locator('.location').text_content()
                    link = listing.locator('a').get_attribute('href')
                    
                    self.results.append({
                        'site': 'kijiji',
                        'title': title,
                        'price': price,
                        'location': location,
                        'link': link,
                        'timestamp': datetime.now().isoformat()
                    })
                
                browser.close()
        except Exception as e:
            print(f"Kijiji scrape error: {e}")

    def scrape_craigslist(self):
        """Scrape Craigslist for listings"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                search_url = f"https://toronto.craigslist.org/search/sss?query={self.search_terms.replace(' ', '+')}&max_price={self.max_price}&radius={self.radius_km}"
                page.goto(search_url, wait_until="networkidle")
                
                listings = page.locator('.result-row')
                for i in range(min(20, listings.count())):
                    listing = listings.nth(i)
                    title = listing.locator('.result-title').text_content()
                    price = listing.locator('.result-price').text_content()
                    location = listing.locator('.result-hood').text_content()
                    link = listing.locator('a').get_attribute('href')
                    
                    self.results.append({
                        'site': 'craigslist',
                        'title': title,
                        'price': price,
                        'location': location,
                        'link': link,
                        'timestamp': datetime.now().isoformat()
                    })
                
                browser.close()
        except Exception as e:
            print(f"Craigslist scrape error: {e}")

    def scrape_facebook(self):
        """Scrape Facebook Marketplace (requires login)"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)  # Login browser
                page = browser.new_page()
                
                # Note: This would require Facebook login automation
                # For now, skip or note that manual login is needed
                print("Facebook Marketplace requires login - skipping automated scrape")
                
                browser.close()
        except Exception as e:
            print(f"Facebook scrape error: {e}")

    def search_all_sites(self):
        """Run searches on all sites"""
        if self.site == 'all' or self.site == 'kijiji':
            self.scrape_kijiji()
        if self.site == 'all' or self.site == 'craigslist':
            self.scrape_craigslist()
        if self.site == 'all' or self.site == 'facebook':
            self.scrape_facebook()

    def process_results(self):
        """Process and deduplicate results"""
        # Simple deduplication by title
        seen = set()
        unique_results = []
        for result in self.results:
            key = result['title'].lower()
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        self.results = unique_results

    def generate_report(self):
        """Generate Markdown and JSON reports"""
        report = {
            'search_params': {
                'terms': self.search_terms,
                'radius_km': self.radius_km,
                'max_price': self.max_price,
                'site': self.site,
                'timestamp': datetime.now().isoformat(),
                'oakville_coords': {'lat': OAKVILLE_LAT, 'lon': OAKVILLE_LON}
            },
            'listings': self.results,
            'summary': {
                'total_listings': len(self.results),
                'devices_found': len([r for r in self.results if 'device' in r['title'].lower()])
            }
        }
        
        # Save JSON
        json_path = Path('search_results.json')
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Generate Markdown
        md = f"""# Streaming Device Search Report - Oakville, ON

**Search Parameters:**
- Terms: {self.search_terms}
- Radius: {self.radius_km} km
- Max Price: ${self.max_price} CAD
- Site: {self.site}
- Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Listings

{'| Title | Site | Price | Location | Link |' + '\\n' + '|' + '-'*40 + '|'*4 + '\\n'}
"""
        
        for result in self.results:
            md += f"| {result['title'][:50]}... | {result['site']} | {result['price']} | {result['location']} | [link]({result['link']}) |\n"
        
        md += f"""
**Summary:** Found {len(self.results)} listings. {len([r for r in self.results if 'device' in r['title'].lower()])} devices.

**Note:** Distance calculations would be performed for each listing using Haversine formula from Oakville coordinates (43.453, -79.500).
"""
        
        with open('SEARCH_REPORT.md', 'w') as f:
            f.write(md)
        
        print(f"Report generated: {json_path} and SEARCH_REPORT.md")

if __name__ == "__main__":
    searcher = StreamingDeviceSearcher()
    searcher.parse_args()
    searcher.search_all_sites()
    searcher.process_results()
    searcher.generate_report()
