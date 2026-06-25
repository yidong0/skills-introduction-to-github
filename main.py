#!/usr/bin/env python3
"""
Research Data Collector
Usage:
    python main.py                        # use default config/config.yaml
    python main.py --config myconfig.yaml
    python main.py --sources arxiv web    # run only selected sources
    python main.py --format csv           # override storage format
"""

import argparse
import sys
import os

# Allow running from project root without installing
sys.path.insert(0, os.path.dirname(__file__))

try:
    import yaml
except ImportError:
    print("PyYAML not found. Install with: pip install pyyaml")
    sys.exit(1)

from collectors import ArxivCollector, PubmedCollector, WebScraper, ApiCollector, GitHubCollector
from utils import DataStorage, get_logger

logger = get_logger("main")

SOURCE_MAP = {
    "arxiv":  (ArxivCollector,  "arxiv"),
    "pubmed": (PubmedCollector, "pubmed"),
    "web":    (WebScraper,      "web"),
    "api":    (ApiCollector,    "api"),
    "github": (GitHubCollector, "github"),
}


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(config: dict, sources: list[str] | None, fmt_override: str | None) -> None:
    storage_cfg = config.get("storage", {})
    if fmt_override:
        storage_cfg["format"] = fmt_override
    storage = DataStorage(storage_cfg)

    all_records: list[dict] = []
    active_sources = sources or list(SOURCE_MAP.keys())

    for name in active_sources:
        if name not in SOURCE_MAP:
            logger.warning(f"Unknown source '{name}', skipping.")
            continue
        cls, cfg_key = SOURCE_MAP[name]
        source_cfg = config.get(cfg_key, {})
        if not source_cfg.get("enabled", True):
            logger.info(f"Source '{name}' is disabled in config, skipping.")
            continue

        logger.info(f"Starting '{name}' collector …")
        collector = cls(source_cfg)
        records = collector.collect()
        all_records.extend(records)
        logger.info(f"'{name}' done: {len(records)} records collected.")

    if all_records:
        path = storage.save(all_records)
        logger.info(f"All done. Total {len(all_records)} records saved to: {path}")
    else:
        logger.warning("No records collected. Check your config and network.")


def main():
    parser = argparse.ArgumentParser(description="Research Data Collector")
    parser.add_argument("--config", default="config/config.yaml", help="Path to YAML config file")
    parser.add_argument("--sources", nargs="+", choices=sorted(SOURCE_MAP.keys()),
                        help="Run only these sources (default: all enabled)")
    parser.add_argument("--format", choices=["json", "csv", "sqlite"],
                        help="Override storage format from config")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)

    config = load_config(args.config)
    run(config, args.sources, args.format)


if __name__ == "__main__":
    main()
