"""Web module for Active Assistant."""
from .crawler import (
    web_manager, WebManager, BraveSearchClient, WebCrawler, ContentExtractor,
    SearchResult, CrawledPage,
    initialize_web, search_web, crawl_web, search_and_crawl
)
from .stream import create_streaming_routes

__all__ = [
    "web_manager", "WebManager", "BraveSearchClient", "WebCrawler", "ContentExtractor",
    "SearchResult", "CrawledPage",
    "initialize_web", "search_web", "crawl_web", "search_and_crawl",
    "create_streaming_routes",
]