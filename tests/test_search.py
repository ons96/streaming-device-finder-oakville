import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search import StreamingDeviceSearcher, geocode_location, parse_price


def make_searcher(**kwargs):
    searcher = StreamingDeviceSearcher()
    for key, value in kwargs.items():
        setattr(searcher, key, value)
    return searcher


def test_device_model_extraction():
    searcher = StreamingDeviceSearcher()
    assert searcher.extract_device_model("Google Chromecast 4K", "") == "chromecast"
    assert searcher.extract_device_model("Roku Ultra 4K", "") == "roku"
    assert searcher.extract_device_model("Old TV", "") is None


def test_irrelevant_model_rejection():
    searcher = StreamingDeviceSearcher()
    assert searcher.is_irrelevant_model("chromecast") is False
    assert searcher.is_irrelevant_model("roku") is False
    assert searcher.is_irrelevant_model("old tv") is True


def test_distance_calculation():
    searcher = StreamingDeviceSearcher()
    assert searcher.calculate_distance(43.453, -79.500) == 0
    assert searcher.calculate_distance(43.5, -79.48) < 10


def test_parse_price():
    assert parse_price("$55") == 55.0
    assert parse_price("$1,200.00") == 1200.0
    assert parse_price("90") == 90.0
    assert parse_price("Free") == 0.0
    assert parse_price("") is None
    assert parse_price(None) is None


def test_geocode_location():
    assert geocode_location("Oakville / Peel Region") == (43.453, -79.5)
    assert geocode_location("Mississauga") == (43.589, -79.644)
    assert geocode_location("Somewhere else") is None


def test_classify_flags_relevant_listing():
    searcher = make_searcher(max_price=200, radius_km=50)
    listing = searcher.classify({
        'site': 'kijiji',
        'title': 'Google Chromecast 4K',
        'description': '',
        'price': '$55',
        'location': 'Oakville',
    })
    assert listing['relevant'] is True
    assert listing['model'] == 'chromecast'
    assert listing['price_value'] == 55.0
    assert listing['distance_km'] == 0


def test_classify_rejects_non_device_and_out_of_range():
    searcher = make_searcher(max_price=200, radius_km=50)
    not_a_device = searcher.classify({
        'site': 'craigslist',
        'title': 'Webcam and monitor',
        'description': '',
        'price': '$75',
        'location': 'Oakville',
    })
    assert not_a_device['relevant'] is False
    assert 'not a recognised streaming device' in not_a_device['reject_reasons']

    too_far = searcher.classify({
        'site': 'kijiji',
        'title': 'Roku Ultra',
        'description': '',
        'price': '$90',
        'location': 'Oshawa',
    })
    assert too_far['relevant'] is False
    assert any('farther than' in reason for reason in too_far['reject_reasons'])

    too_expensive = searcher.classify({
        'site': 'kijiji',
        'title': 'Apple TV 4K',
        'description': '',
        'price': '$480',
        'location': 'Oakville',
    })
    assert too_expensive['relevant'] is False
    assert any('price above' in reason for reason in too_expensive['reject_reasons'])


def test_classify_rejects_broken_listing():
    searcher = make_searcher(max_price=200, radius_km=50)
    listing = searcher.classify({
        'site': 'kijiji',
        'title': 'Broken old TV for parts',
        'description': 'Screen is cracked.',
        'price': 'Free',
        'location': 'Oakville',
    })
    assert listing['relevant'] is False
    assert 'irrelevant or broken device' in listing['reject_reasons']
    assert listing['price_value'] == 0.0


def test_unknown_location_keeps_listing_with_unknown_distance():
    searcher = make_searcher(max_price=200, radius_km=50)
    listing = searcher.classify({
        'site': 'craigslist',
        'title': 'Apple TV 4K',
        'description': '',
        'price': '$120',
        'location': 'Somewhere else',
    })
    assert listing['relevant'] is True
    assert listing['distance_km'] is None


def test_process_results_filters_and_deduplicates():
    searcher = make_searcher(max_price=200, radius_km=50)
    searcher.results = [
        {'site': 'kijiji', 'title': 'Chromecast 4K', 'price': '$50', 'location': 'Oakville'},
        {'site': 'kijiji', 'title': 'chromecast 4k', 'price': '$50', 'location': 'Oakville'},
        {'site': 'kijiji', 'title': 'Old broken TV', 'price': '$10', 'location': 'Oakville'},
        {'site': 'kijiji', 'title': 'Apple TV 4K', 'price': '$400', 'location': 'Oakville'},
    ]
    kept = searcher.process_results()
    assert len(kept) == 1
    assert kept[0]['title'] == 'Chromecast 4K'
    assert len(searcher.rejected) == 2


def test_end_to_end_sample_run(tmp_path):
    searcher = make_searcher(output_dir=tmp_path)
    searcher.parse_args(['--samples', '--output-dir', str(tmp_path)])
    searcher.search_all_sites()
    searcher.process_results()
    json_path, md_path = searcher.generate_report()

    assert json_path.exists()
    assert md_path.exists()

    payload = json.loads(json_path.read_text())
    titles = [listing['title'] for listing in payload['listings']]
    assert 'Google Chromecast 4K - brand new, still boxed' in titles
    assert 'Broken old TV for parts' not in titles
    assert 'Webcam and monitor for streaming' not in titles
    assert 'Roku Streaming Stick 4K (new in box)' not in titles
    assert 'Apple TV 4K 32GB' in titles
    assert payload['summary']['total_listings'] >= 4

    markdown = md_path.read_text()
    assert '# Streaming Device Search Report - Oakville, ON' in markdown
    assert '| Title | Model | Site | Price | Distance (km) | Location | Link |' in markdown
    assert 'chromecast' in markdown
