import urllib.request
import urllib.parse
import json
import time
from utils.logger import get_logger

logger = get_logger(__name__)


class ApiCollector:
    """Generic REST API collector with pagination support."""

    def __init__(self, config: dict):
        self.endpoints: list[dict] = config.get("endpoints", [])
        self.delay: float = config.get("delay_seconds", 1.0)
        self.timeout: int = config.get("timeout", 30)

    def collect(self) -> list[dict]:
        results = []
        for ep in self.endpoints:
            name = ep.get("name", ep.get("url", "unnamed"))
            try:
                records = self._fetch_endpoint(ep)
                results.extend(records)
                logger.info(f"API '{name}': fetched {len(records)} records")
            except Exception as e:
                logger.error(f"API '{name}' failed: {e}")
            time.sleep(self.delay)
        return results

    def _fetch_endpoint(self, ep: dict) -> list[dict]:
        url = ep["url"]
        headers = ep.get("headers", {})
        params = ep.get("params", {})
        data_path = ep.get("data_path", "")      # e.g. "results" or "data.items"
        next_page_key = ep.get("next_page_key", "")  # key in response that holds next URL
        max_pages = ep.get("max_pages", 5)

        all_records: list[dict] = []
        page = 0

        while url and page < max_pages:
            full_url = f"{url}?{urllib.parse.urlencode(params)}" if params and page == 0 else url
            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read())

            items = self._extract_path(body, data_path) if data_path else body
            if isinstance(items, list):
                for item in items:
                    item["_api_source"] = ep.get("name", url)
                    item["source"] = "api"
                all_records.extend(items)
            elif isinstance(items, dict):
                items["_api_source"] = ep.get("name", url)
                items["source"] = "api"
                all_records.append(items)

            url = self._extract_path(body, next_page_key) if next_page_key else None
            page += 1
            if url:
                time.sleep(self.delay)

        return all_records

    @staticmethod
    def _extract_path(data: dict, path: str):
        """Traverse nested keys separated by dots: 'data.results.items'"""
        current = data
        for key in path.split("."):
            if not key:
                break
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current
