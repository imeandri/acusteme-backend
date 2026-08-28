"""Crash-safe local state for three-way Wiki.js synchronization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Mapping

from wikijs_manual_regions import content_hash, managed_hash


STATE_VERSION = 1


class SyncStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class StateRecord:
    locale: str
    path: str
    page_id: int
    title: str
    base_file: str
    content_hash: str
    managed_hash: str
    recorded_at: str


class SyncStateStore:
    def __init__(self, directory: Path | str):
        self.directory = Path(directory)
        self.manifest_path = self.directory / "manifest.json"
        self.base_directory = self.directory / "base"
        self._records = self._load_manifest()

    @staticmethod
    def key(locale: str, path: str) -> str:
        return f"{locale}:{path}"

    def _load_manifest(self) -> dict[str, StateRecord]:
        if not self.manifest_path.exists():
            return {}
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if payload.get("version") != STATE_VERSION:
                raise SyncStateError(
                    f"Unsupported sync-state version {payload.get('version')!r}."
                )
            raw_records = payload.get("pages", {})
            if not isinstance(raw_records, Mapping):
                raise TypeError("pages must be an object")
            return {
                key: StateRecord(**record)
                for key, record in raw_records.items()
            }
        except SyncStateError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise SyncStateError(f"Cannot read sync state {self.manifest_path}.") from exc

    def get_record(self, locale: str, path: str) -> StateRecord | None:
        return self._records.get(self.key(locale, path))

    def get_base_content(self, record: StateRecord) -> str:
        base_path = self.directory / record.base_file
        try:
            content = base_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SyncStateError(f"Cannot read sync base {base_path}.") from exc
        if content_hash(content) != record.content_hash:
            raise SyncStateError(f"Sync base checksum mismatch for {base_path}.")
        return content

    def record_applied(
        self,
        locale: str,
        path: str,
        page_id: int,
        title: str,
        generated_content: str,
    ) -> StateRecord:
        digest = content_hash(generated_content)
        relative_base = Path("base") / f"{digest}.html"
        base_path = self.directory / relative_base
        self.base_directory.mkdir(parents=True, exist_ok=True)
        if not base_path.exists():
            temporary_base = base_path.with_suffix(".tmp")
            temporary_base.write_text(generated_content, encoding="utf-8")
            os.replace(temporary_base, base_path)

        record = StateRecord(
            locale=locale,
            path=path,
            page_id=page_id,
            title=title,
            base_file=relative_base.as_posix(),
            content_hash=digest,
            managed_hash=managed_hash(generated_content),
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
        self._records[self.key(locale, path)] = record
        self._write_manifest()
        return record

    def _write_manifest(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": STATE_VERSION,
            "pages": {
                key: asdict(record)
                for key, record in sorted(self._records.items())
            },
        }
        temporary_manifest = self.manifest_path.with_suffix(".tmp")
        temporary_manifest.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_manifest, self.manifest_path)
