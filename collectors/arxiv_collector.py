import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time
from utils.logger import get_logger

logger = get_logger(__name__)

ARXIV_API = "http://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivCollector:
    """Collect papers from arXiv API."""

    def __init__(self, config: dict):
        self.keywords = config.get("keywords", [])
        self.max_results = config.get("max_results", 50)
        self.categories = config.get("categories", [])

    def collect(self) -> list[dict]:
        results = []
        for keyword in self.keywords:
            try:
                records = self._fetch(keyword)
                results.extend(records)
                logger.info(f"arXiv: fetched {len(records)} records for '{keyword}'")
                time.sleep(1)  # arXiv rate limit
            except Exception as e:
                logger.error(f"arXiv fetch failed for '{keyword}': {e}")
        return results

    def _fetch(self, keyword: str) -> list[dict]:
        query_parts = [f"all:{urllib.parse.quote(keyword)}"]
        if self.categories:
            cat_query = " OR ".join(f"cat:{c}" for c in self.categories)
            query_parts.append(f"({cat_query})")

        params = urllib.parse.urlencode({
            "search_query": " AND ".join(query_parts),
            "start": 0,
            "max_results": self.max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        })

        url = f"{ARXIV_API}?{params}"
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read().decode("utf-8")

        root = ET.fromstring(data)
        records = []
        for entry in root.findall("atom:entry", NS):
            records.append({
                "source": "arxiv",
                "id": self._text(entry, "atom:id"),
                "title": self._text(entry, "atom:title"),
                "summary": self._text(entry, "atom:summary"),
                "published": self._text(entry, "atom:published"),
                "authors": [
                    a.find("atom:name", NS).text
                    for a in entry.findall("atom:author", NS)
                    if a.find("atom:name", NS) is not None
                ],
                "categories": [
                    t.attrib.get("term", "")
                    for t in entry.findall("atom:category", NS)
                ],
                "keyword": keyword,
            })
        return records

    @staticmethod
    def _text(element, tag: str) -> str:
        el = element.find(tag, NS)
        return el.text.strip() if el is not None and el.text else ""
