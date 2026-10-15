"""JSON-backed persistence for a Hugging Face Bucket mounted as a directory.

The application does not mount the Bucket itself. Configure the Bucket volume
in the Space settings and set OHAM_DATA_DIR to its mount path.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()


class BucketStore:
    def __init__(self, root: str | None = None):
        self.root = Path(root or os.getenv("OHAM_DATA_DIR", "./data")).resolve()
        self.documents_dir = self.root / "documents"
        self.history_dir = self.root / "task-history"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _document_id(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]

    def save_document(self, document: dict[str, Any]) -> dict[str, Any]:
        if not document.get("url"):
            raise ValueError("document.url is required")
        item = dict(document)
        item["document_id"] = self._document_id(item["url"])
        path = self.documents_dir / f"{item['document_id']}.json"
        temp_path = path.with_suffix(".json.tmp")
        with _LOCK:
            temp_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp_path, path)
        return item

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        if not re.fullmatch(r"[a-f0-9]{24}", document_id or ""):
            return None
        path = self.documents_dir / f"{document_id}.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def list_documents(self, query: str = "", limit: int = 10) -> list[dict[str, Any]]:
        needle = (query or "").strip().casefold()
        safe_limit = max(1, min(int(limit), 100))
        results: list[dict[str, Any]] = []
        for path in self.documents_dir.glob("*.json"):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            searchable = " ".join(str(item.get(k, "")) for k in ("title", "url", "description", "snippet")).casefold()
            if needle and needle not in searchable:
                continue
            results.append({k: v for k, v in item.items() if k != "text"})
        results.sort(key=lambda row: row.get("fetched_at", ""), reverse=True)
        return results[:safe_limit]

    def log_task(self, task_type: str, request: dict[str, Any], result: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        path = self.history_dir / f"{now:%Y-%m-%d}.jsonl"
        record = {
            "timestamp": now.isoformat(),
            "task_type": task_type,
            "request": request,
            "result": result,
        }
        with _LOCK, path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def task_history(self, limit: int = 20) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.history_dir.glob("*.jsonl"), reverse=True):
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        rows.append(json.loads(line))
            except (OSError, json.JSONDecodeError):
                continue
        rows.sort(key=lambda row: row.get("timestamp", ""), reverse=True)
        return rows[:max(1, min(int(limit), 100))]


store = BucketStore()
