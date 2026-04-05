import time, logging, threading
from urllib.parse import urljoin, urlparse
from collections import deque

import requests
from bs4 import BeautifulSoup
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

log = logging.getLogger(__name__)

_SKIP_PATHS = frozenset([
    "/wp-admin", "/login", "/logout", "/admin", "/api/",
    "/.git", "/cdn-cgi/", "/static/", "/__",
])


class CrawlerAgent:
    def __init__(
        self,
        topic: str,
        seed_urls: list,
        extra_allowed_domains: list | None = None,
        max_pages: int | None = None,
        max_depth: int | None = None,
        delay: float | None  = None,
        timeout: int | None  = None,
        stop_event: threading.Event | None = None,
        on_page=None,
    ):
        self.topic      = topic
        self.seed_urls  = seed_urls
        self.max_pages  = max_pages  or config.CRAWLER_MAX_PAGES
        self.max_depth  = max_depth  or config.CRAWLER_MAX_DEPTH
        self.delay      = delay      if delay  is not None else config.CRAWLER_DELAY_SECONDS
        self.timeout    = timeout    or config.CRAWLER_TIMEOUT_SECONDS
        self.stop_event = stop_event
        self.on_page    = on_page    # callable(page_data, pages_done) — called from worker thread

        self.allowed_domains = set(config.ALLOWED_DOMAINS_ALWAYS)
        for url in seed_urls:
            self.allowed_domains.add(urlparse(url).netloc)
        if extra_allowed_domains:
            self.allowed_domains.update(extra_allowed_domains)

        self.visited = set()
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.CRAWLER_USER_AGENT

    # ── Helpers ────────────────────────────────────────────────────────────

    def _is_allowed(self, url: str) -> bool:
        try:
            domain = urlparse(url).netloc
            return any(domain == a or domain.endswith("." + a) for a in self.allowed_domains)
        except Exception:
            return False

    def _is_clean_path(self, url: str) -> bool:
        path = urlparse(url).path
        return not any(path.startswith(p) for p in _SKIP_PATHS)

    def _fetch(self, url: str) -> str | None:
        try:
            r = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
                return r.text
        except Exception as e:
            log.debug(f"Fetch failed {url}: {e}")
        return None

    def _extract_links(self, html: str, base_url: str) -> list:
        soup  = BeautifulSoup(html, "html.parser")
        links = []
        for tag in soup.find_all("a", href=True):
            href = urljoin(base_url, tag["href"]).split("#")[0].split("?")[0]
            if (
                href.startswith("http")
                and self._is_allowed(href)
                and self._is_clean_path(href)
            ):
                links.append(href)
        return links

    def _extract_text(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script","style","nav","footer","header","aside","form","noscript","iframe"]):
            tag.decompose()
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        main  = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id="content")
            or soup.find(class_="content")
            or soup.find("body")
        )
        if not main:
            return None
        text  = main.get_text(separator="\n", strip=True)
        words = text.split()
        if len(words) < 100:
            return None
        return {"url": url, "title": title, "text": text, "word_count": len(words)}

    # ── Main crawl generator ───────────────────────────────────────────────

    def crawl(self):
        queue         = deque([(url, 0) for url in self.seed_urls])
        pages_crawled = 0

        while queue and pages_crawled < self.max_pages:
            if self.stop_event and self.stop_event.is_set():
                log.info("Crawl stopped via stop_event.")
                break

            url, depth = queue.popleft()
            if url in self.visited:
                continue
            self.visited.add(url)

            html = self._fetch(url)
            if not html:
                continue

            page = self._extract_text(html, url)
            if page:
                pages_crawled += 1
                yield page
                if self.on_page:
                    self.on_page(page, pages_crawled)
                if depth < self.max_depth:
                    for link in self._extract_links(html, url):
                        if link not in self.visited:
                            queue.append((link, depth + 1))

            time.sleep(self.delay)
