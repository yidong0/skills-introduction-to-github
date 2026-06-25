import urllib.request
import urllib.parse
import json
import time
import os
from utils.logger import get_logger

logger = get_logger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubCollector:
    """Collect GitHub repository metadata, issues, and PRs via REST API."""

    def __init__(self, config: dict):
        self.repos: list[str] = config.get("repos", [])        # "owner/repo"
        self.search_queries: list[str] = config.get("search_queries", [])
        self.collect_issues: bool = config.get("collect_issues", True)
        self.collect_prs: bool = config.get("collect_prs", False)
        self.collect_commits: bool = config.get("collect_commits", False)
        self.max_items: int = config.get("max_items", 30)
        self.token: str = config.get("token", "") or os.environ.get("GITHUB_TOKEN", "")
        self.delay: float = config.get("delay_seconds", 1.5)

    @property
    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def collect(self) -> list[dict]:
        results = []

        for query in self.search_queries:
            try:
                records = self._search_repos(query)
                results.extend(records)
                logger.info(f"GitHub search '{query}': {len(records)} repos")
                time.sleep(self.delay)
            except Exception as e:
                logger.error(f"GitHub search failed for '{query}': {e}")

        for repo in self.repos:
            try:
                meta = self._fetch_repo(repo)
                if meta:
                    results.append(meta)
                if self.collect_issues:
                    issues = self._fetch_items(repo, "issues")
                    results.extend(issues)
                if self.collect_prs:
                    prs = self._fetch_items(repo, "pulls")
                    results.extend(prs)
                if self.collect_commits:
                    commits = self._fetch_commits(repo)
                    results.extend(commits)
                logger.info(f"GitHub repo '{repo}': collected {len(results)} total records so far")
                time.sleep(self.delay)
            except Exception as e:
                logger.error(f"GitHub repo '{repo}' failed: {e}")

        return results

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        url = f"{GITHUB_API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=self._headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def _search_repos(self, query: str) -> list[dict]:
        data = self._get("/search/repositories", {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": min(self.max_items, 100),
        })
        items = data.get("items", [])
        return [self._flatten_repo(r, source_query=query) for r in items]

    def _fetch_repo(self, repo: str) -> dict | None:
        data = self._get(f"/repos/{repo}")
        return self._flatten_repo(data) if data else None

    def _flatten_repo(self, r: dict, source_query: str = "") -> dict:
        return {
            "source": "github",
            "type": "repository",
            "id": f"repo:{r.get('full_name', '')}",
            "full_name": r.get("full_name", ""),
            "description": r.get("description", ""),
            "language": r.get("language", ""),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "open_issues": r.get("open_issues_count", 0),
            "topics": r.get("topics", []),
            "created_at": r.get("created_at", ""),
            "updated_at": r.get("updated_at", ""),
            "url": r.get("html_url", ""),
            "search_query": source_query,
        }

    def _fetch_items(self, repo: str, kind: str) -> list[dict]:
        path = f"/repos/{repo}/{kind}"
        params = {"state": "all", "per_page": min(self.max_items, 100)}
        items = self._get(path, params)
        if not isinstance(items, list):
            return []
        type_label = "issue" if kind == "issues" else "pull_request"
        result = []
        for item in items[: self.max_items]:
            result.append({
                "source": "github",
                "type": type_label,
                "id": f"{type_label}:{repo}#{item.get('number')}",
                "repo": repo,
                "number": item.get("number"),
                "title": item.get("title", ""),
                "state": item.get("state", ""),
                "body": (item.get("body") or "")[:2000],
                "labels": [lb["name"] for lb in item.get("labels", [])],
                "created_at": item.get("created_at", ""),
                "updated_at": item.get("updated_at", ""),
                "url": item.get("html_url", ""),
            })
        return result

    def _fetch_commits(self, repo: str) -> list[dict]:
        items = self._get(f"/repos/{repo}/commits", {"per_page": min(self.max_items, 100)})
        if not isinstance(items, list):
            return []
        result = []
        for item in items[: self.max_items]:
            commit = item.get("commit", {})
            result.append({
                "source": "github",
                "type": "commit",
                "id": f"commit:{item.get('sha', '')[:12]}",
                "repo": repo,
                "sha": item.get("sha", ""),
                "message": commit.get("message", "")[:500],
                "author": commit.get("author", {}).get("name", ""),
                "date": commit.get("author", {}).get("date", ""),
                "url": item.get("html_url", ""),
            })
        return result
