from alphaview_common.contracts import SOURCES
from alphaview_crawler.crawl import ADAPTERS


def test_adapters_match_published_sources():
    assert set(ADAPTERS) == set(SOURCES)
