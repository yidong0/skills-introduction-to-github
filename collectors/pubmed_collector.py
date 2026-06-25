import urllib.request
import urllib.parse
import json
import time
from utils.logger import get_logger

logger = get_logger(__name__)

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


class PubmedCollector:
    """Collect biomedical literature from PubMed E-utilities (no API key required for small volumes)."""

    def __init__(self, config: dict):
        self.keywords = config.get("keywords", [])
        self.max_results = config.get("max_results", 50)
        self.api_key = config.get("api_key", "")

    def collect(self) -> list[dict]:
        results = []
        for keyword in self.keywords:
            try:
                ids = self._search(keyword)
                if ids:
                    records = self._fetch_summaries(ids, keyword)
                    results.extend(records)
                    logger.info(f"PubMed: fetched {len(records)} records for '{keyword}'")
                time.sleep(0.4)  # stay within 3 req/s for unauthenticated
            except Exception as e:
                logger.error(f"PubMed fetch failed for '{keyword}': {e}")
        return results

    def _search(self, keyword: str) -> list[str]:
        params = {
            "db": "pubmed",
            "term": keyword,
            "retmax": self.max_results,
            "retmode": "json",
            "sort": "date",
        }
        if self.api_key:
            params["api_key"] = self.api_key
        url = f"{ESEARCH}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
        return data.get("esearchresult", {}).get("idlist", [])

    def _fetch_summaries(self, ids: list[str], keyword: str) -> list[dict]:
        params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "json",
        }
        if self.api_key:
            params["api_key"] = self.api_key
        url = f"{ESUMMARY}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())

        records = []
        for pmid, item in data.get("result", {}).items():
            if pmid == "uids":
                continue
            records.append({
                "source": "pubmed",
                "id": f"pmid:{pmid}",
                "title": item.get("title", ""),
                "published": item.get("pubdate", ""),
                "authors": [a.get("name", "") for a in item.get("authors", [])],
                "journal": item.get("fulljournalname", ""),
                "doi": item.get("elocationid", ""),
                "keyword": keyword,
            })
        return records
