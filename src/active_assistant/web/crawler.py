"""
Web crawling and search for Active Assistant.
Integrates with Brave Search API and provides web content extraction.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger

from active_assistant.core.config import get_config
from active_assistant.core.state import state


# ============================================================
# Models
# ============================================================

@dataclass
class SearchResult:
    """Single search result."""
    title: str
    url: str
    description: str
    source: str = "brave"
    rank: int = 0


@dataclass
class CrawledPage:
    """Crawled page content."""
    url: str
    title: str
    content: str
    links: List[str]
    metadata: Dict
    timestamp: datetime = datetime.now()
    depth: int = 0


# ============================================================
# Brave Search Client
# ============================================================

class BraveSearchClient:
    """Client for Brave Search API."""
    
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.base_url = "https://api.search.brave.com/res/v1/web/search"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        safe_search: bool = True,
        region: str = "US",
        freshness: str = "",  # "pd", "pw", "pm", "py"
    ) -> List[SearchResult]:
        """Perform web search."""
        if not self.api_key:
            logger.error("Brave API key not configured")
            return []
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        
        params = {
            "q": query,
            "count": min(max_results, 20),
            "safesearch": "moderate" if safe_search else "off",
            "search_lang": "en",
            "country": region.lower(),
        }
        
        if freshness:
            params["freshness"] = freshness
        
        try:
            async with self.session.get(self.base_url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error(f"Brave search error {resp.status}: {error}")
                    return []
                
                data = await resp.json()
            
            results = []
            web_results = data.get("web", {}).get("results", [])
            
            for i, r in enumerate(web_results):
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    description=r.get("description", ""),
                    source="brave",
                    rank=i + 1,
                ))
            
            state.increment_metric("api_calls")
            return results
            
        except Exception as e:
            logger.error(f"Brave search failed: {e}")
            return []


# ============================================================
# Web Crawler
# ============================================================

class WebCrawler:
    """Web crawler with depth control and politeness."""
    
    def __init__(
        self,
        max_pages: int = 10,
        max_depth: int = 2,
        timeout: int = 30,
        respect_robots_txt: bool = True,
        user_agent: str = "ActiveAssistant/2.0",
    ):
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.timeout = timeout
        self.respect_robots_txt = respect_robots_txt
        self.user_agent = user_agent
        
        self._visited: Set[str] = set()
        self._robots_cache: Dict[str, Any] = {}
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers={"User-Agent": self.user_agent},
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
    
    async def crawl(
        self,
        urls: List[str],
        extract_content: bool = True,
        follow_links: bool = True,
    ) -> List[CrawledPage]:
        """Crawl multiple URLs."""
        self._visited.clear()
        results = []
        
        for url in urls:
            if len(results) >= self.max_pages:
                break
            await self._crawl_url(url, results, depth=0, extract_content=extract_content, follow_links=follow_links)
        
        return results
    
    async def _crawl_url(
        self,
        url: str,
        results: List[CrawledPage],
        depth: int,
        extract_content: bool,
        follow_links: bool,
    ):
        """Recursively crawl a URL."""
        if len(results) >= self.max_pages:
            return
        if depth > self.max_depth:
            return
        if url in self._visited:
            return
        
        self._visited.add(url)
        
        try:
            page = await self._fetch_page(url, depth)
            if page:
                results.append(page)
                
                if follow_links and depth < self.max_depth:
                    for link in page.links[:5]:  # Limit links per page
                        if len(results) >= self.max_pages:
                            break
                        await self._crawl_url(link, results, depth + 1, extract_content, follow_links)
                        
        except Exception as e:
            logger.warning(f"Crawl error for {url}: {e}")
    
    async def _fetch_page(self, url: str, depth: int) -> Optional[CrawledPage]:
        """Fetch and parse a single page."""
        if not self._session:
            return None
        
        try:
            async with self._session.get(url) as resp:
                if resp.status != 200:
                    return None
                
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" not in content_type:
                    return None
                
                html = await resp.text()
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                element.decompose()
            
            # Extract title
            title = soup.title.string.strip() if soup.title else ""
            
            # Extract main content
            content = ""
            if extract_content:
                # Try to find main content
                main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|main|article"))
                if main:
                    content = main.get_text(separator='\n', strip=True)
                else:
                    content = soup.get_text(separator='\n', strip=True)
                
                # Clean up
                content = re.sub(r'\n{3,}', '\n\n', content)
                content = content[:10000]  # Limit content size
            
            # Extract links
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                absolute = urljoin(url, href)
                parsed = urlparse(absolute)
                if parsed.scheme in ('http', 'https'):
                    links.append(absolute)
            
            # Extract metadata
            metadata = {}
            for meta in soup.find_all('meta'):
                name = meta.get('name') or meta.get('property')
                content_val = meta.get('content')
                if name and content_val:
                    metadata[name] = content_val
            
            return CrawledPage(
                url=url,
                title=title,
                content=content,
                links=links,
                metadata=metadata,
                depth=depth,
            )
            
        except Exception as e:
            logger.warning(f"Fetch error for {url}: {e}")
            return None


# ============================================================
# Content Extractor
# ============================================================

class ContentExtractor:
    """Extract structured content from web pages."""
    
    @staticmethod
    def extract_article(soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract article content using common patterns."""
        # Try schema.org Article
        article = soup.find(itemtype=re.compile(r"Article"))
        if article:
            return ContentExtractor._extract_from_schema(article)
        
        # Try common article selectors
        selectors = [
            "article",
            "[role='article']",
            ".article-content",
            ".post-content",
            ".entry-content",
            ".content",
            "main",
            "#content",
            "#main",
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return {
                    "title": soup.title.string if soup.title else "",
                    "content": element.get_text(separator='\n', strip=True),
                    "html": str(element),
                }
        
        # Fallback to body
        body = soup.find('body')
        if body:
            return {
                "title": soup.title.string if soup.title else "",
                "content": body.get_text(separator='\n', strip=True),
                "html": str(body),
            }
        
        return {"title": "", "content": "", "html": ""}
    
    @staticmethod
    def _extract_from_schema(element) -> Dict[str, Any]:
        """Extract from schema.org markup."""
        result = {}
        for prop in element.find_all(itemprop=True):
            prop_name = prop.get('itemprop')
            if prop_name:
                if prop.name == 'meta':
                    result[prop_name] = prop.get('content', '')
                else:
                    result[prop_name] = prop.get_text(strip=True)
        return result
    
    @staticmethod
    def extract_links(soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract all valid links."""
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme in ('http', 'https'):
                # Filter out common non-content links
                if not any(skip in absolute.lower() for skip in [
                    'javascript:', 'mailto:', 'tel:', '#',
                    'facebook.com', 'twitter.com', 'linkedin.com',
                    'instagram.com', 'youtube.com', 'pinterest.com',
                ]):
                    links.append(absolute)
        return list(dict.fromkeys(links))  # Deduplicate preserving order


# ============================================================
# Web Manager
# ============================================================

class WebManager:
    """High-level web operations manager."""
    
    def __init__(self):
        self.config = get_config().web
        self._search_client: Optional[BraveSearchClient] = None
    
    async def initialize(self):
        """Initialize web components."""
        self._search_client = BraveSearchClient(self.config.brave_api_key)
        logger.info("Web manager initialized")
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        safe_search: bool = True,
        region: str = "US",
    ) -> List[SearchResult]:
        """Search the web."""
        if not self._search_client:
            await self.initialize()
        return await self._search_client.search(query, max_results, safe_search, region)
    
    async def crawl(
        self,
        urls: List[str],
        max_pages: int = 10,
        max_depth: int = 2,
    ) -> List[CrawledPage]:
        """Crawl web pages."""
        async with WebCrawler(
            max_pages=max_pages,
            max_depth=max_depth,
            timeout=self.config.crawl.timeout,
            respect_robots_txt=self.config.crawl.respect_robots_txt,
            user_agent=self.config.crawl.user_agent,
        ) as crawler:
            return await crawler.crawl(urls)
    
    async def search_and_crawl(
        self,
        query: str,
        max_results: int = 5,
        max_crawl_pages: int = 3,
    ) -> List[CrawledPage]:
        """Search and crawl top results."""
        results = await self.search(query, max_results=max_results)
        if not results:
            return []
        
        urls = [r.url for r in results]
        return await self.crawl(urls, max_pages=max_crawl_pages)
    
    async def extract_content(self, url: str) -> Optional[CrawledPage]:
        """Extract content from a single URL."""
        pages = await self.crawl([url], max_pages=1)
        return pages[0] if pages else None


# Global web manager
web_manager = WebManager()


async def initialize_web():
    """Initialize web manager."""
    await web_manager.initialize()


async def search_web(query: str, **kwargs) -> List[SearchResult]:
    """Search the web."""
    return await web_manager.search(query, **kwargs)


async def crawl_web(urls: List[str], **kwargs) -> List[CrawledPage]:
    """Crawl web pages."""
    return await web_manager.crawl(urls, **kwargs)


async def search_and_crawl(query: str, **kwargs) -> List[CrawledPage]:
    """Search and crawl."""
    return await web_manager.search_and_crawl(query, **kwargs)