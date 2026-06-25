import json
import csv
import os
import sqlite3
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)


class DataStorage:
    """Save collected records to JSON, CSV, or SQLite."""

    SUPPORTED = ("json", "csv", "sqlite")

    def __init__(self, config: dict):
        self.format: str = config.get("format", "json")
        self.output_dir: str = config.get("output_dir", "output")
        self.filename_prefix: str = config.get("filename_prefix", "data")
        self.append: bool = config.get("append", False)

        if self.format not in self.SUPPORTED:
            raise ValueError(f"Unsupported format '{self.format}'. Choose from {self.SUPPORTED}.")
        os.makedirs(self.output_dir, exist_ok=True)

    def save(self, records: list[dict], tag: str = "") -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        label = f"_{tag}" if tag else ""
        filename = f"{self.filename_prefix}{label}_{timestamp}"

        if self.format == "json":
            return self._save_json(records, filename)
        elif self.format == "csv":
            return self._save_csv(records, filename)
        elif self.format == "sqlite":
            return self._save_sqlite(records, filename)

    def _save_json(self, records: list[dict], filename: str) -> str:
        path = os.path.join(self.output_dir, f"{filename}.json")
        existing = []
        if self.append and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing + records, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(records)} records → {path}")
        return path

    def _save_csv(self, records: list[dict], filename: str) -> str:
        if not records:
            return ""
        path = os.path.join(self.output_dir, f"{filename}.csv")
        all_keys = list(dict.fromkeys(k for r in records for k in r))
        mode = "a" if self.append and os.path.exists(path) else "w"
        with open(path, mode, newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
            if mode == "w":
                writer.writeheader()
            for row in records:
                flat = {k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in row.items()}
                writer.writerow(flat)
        logger.info(f"Saved {len(records)} records → {path}")
        return path

    def _save_sqlite(self, records: list[dict], filename: str) -> str:
        path = os.path.join(self.output_dir, f"{self.filename_prefix}.sqlite")
        if not records:
            return path
        all_keys = list(dict.fromkeys(k for r in records for k in r))
        con = sqlite3.connect(path)
        cur = con.cursor()
        cols = ", ".join(f'"{c}" TEXT' for c in all_keys)
        cur.execute(f'CREATE TABLE IF NOT EXISTS records ({cols})')
        for record in records:
            vals = [json.dumps(record.get(k)) if isinstance(record.get(k), (list, dict))
                    else record.get(k) for k in all_keys]
            cur.execute(
                f'INSERT INTO records VALUES ({",".join("?" * len(all_keys))})', vals
            )
        con.commit()
        con.close()
        logger.info(f"Saved {len(records)} records → {path}")
        return path
