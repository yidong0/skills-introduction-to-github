import urllib.request
import urllib.parse
import re
import time
from html.parser import HTMLParser
from utils.logger import get_logger

logger = get_logger(__name__)


class _TextExtractor(HTMLParser):
    """Strip HTML tags and extract visible text."""

    SKIP_TAGS = {"script", "style", "head", "meta", "link", "noscript"}

    def __init__(self):
        super().__init__()
        self._skip = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in self.SKIP_TAGS:
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if self._skip == 0:
            text = data.strip()
            if text:
                self.chunks.append(text)

    def get_text(self) -> str:
        return " ".join(self.chunks)


class WebScraper:
    """Scrape structured text content from a list of URLs."""

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; ResearchDataCollector/1.0; "
            "+https://github.com/research-collector)"
        )
    }

    def __init__(self, config: dict):
        self.urls: list[str] = config.get("urls", [])
        self.delay: float = config.get("delay_seconds", 2.0)
        self.timeout: int = config.get("timeout", 30)
        self.extract_links: bool = config.get("extract_links", False)

    def collect(self) -> list[dict]:
        results = []
        for url in self.urls:
            try:
                record = self._scrape(url)
                if record:
                    results.append(record)
                    logger.info(f"Web: scraped {url} ({len(record.get('text',''))} chars)")
                time.sleep(self.delay)
            except Exception as e:
                logger.error(f"Web scrape failed for {url}: {e}")
        return results

    def _scrape(self, url: str) -> dict | None:
        req = urllib.request.Request(url, headers=self.DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                logger.warning(f"Skipping non-text content at {url}")
                return None
            raw_html = resp.read().decode("utf-8", errors="replace")

        title = self._extract_title(raw_html)
        extractor = _TextExtractor()
        extractor.feed(raw_html)
        text = extractor.get_text()

        record: dict = {
            "source": "web",
            "url": url,
            "title": title,
            "text": text[:10000],  # cap at 10k chars per page
        }

        if self.extract_links:
            record["links"] = self._extract_links(raw_html, url)

        return record

    @staticmethod
    def _extract_title(html: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_links(html: str, base_url: str) -> list[str]:
        links = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        base = urllib.parse.urlparse(base_url)
        resolved = []
        for link in links:
            parsed = urllib.parse.urlparse(link)
            if parsed.scheme in ("http", "https"):
                resolved.append(link)
            elif not parsed.scheme and parsed.path:
                resolved.append(urllib.parse.urljoin(base_url, link))
        return list(dict.fromkeys(resolved))[:50]  # deduplicate, cap at 50
