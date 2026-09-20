import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search import StreamingDeviceSearcher


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
