#!/usr/bin/env python3
"""Scarica cover Discogs senza modificare il workbook Excel sorgente."""

from __future__ import annotations

import argparse
import csv
import logging
import os
from pathlib import Path
import re
import tempfile
import time

import pandas as pd
import requests
from dotenv import load_dotenv

from dac_common import canonical_column


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
DISCOGS_RE = re.compile(r"/(master|release)/(\d+)", re.IGNORECASE)


def parse_discogs_link(link: str) -> tuple[str, str]:
    match = DISCOGS_RE.search(str(link or ""))
    if not match:
        raise ValueError(f"Link Discogs non supportato: {link!r}")
    return match.group(1).lower(), match.group(2)


class DiscogsClient:
    def __init__(self, token: str, wait_seconds: float = 1.0):
        self.wait_seconds = wait_seconds
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Acusteme-DAC-Importer/1.0",
            "Authorization": f"Discogs token={token}",
        })

    def get_json(self, url: str) -> dict:
        last_error = None
        for attempt in range(4):
            try:
                time.sleep(self.wait_seconds if attempt == 0 else 2 ** (attempt - 1))
                response = self.session.get(url, timeout=30)
                if response.status_code == 429:
                    raise requests.HTTPError("429 Too Many Requests", response=response)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
        raise last_error

    def images(self, kind: str, item_id: str) -> tuple[list[dict], str]:
        data = self.get_json(f"https://api.discogs.com/{kind}s/{item_id}")
        images = data.get("images", []) or []
        if kind == "master" and not any(image.get("type") == "primary" for image in images):
            versions = self.get_json(f"https://api.discogs.com/masters/{item_id}/versions").get("versions", [])
            release_id = next((str(v["id"]) for v in versions if v.get("id")), "")
            if release_id:
                data = self.get_json(f"https://api.discogs.com/releases/{release_id}")
                return data.get("images", []) or [], f"release {release_id} (fallback da master {item_id})"
        return images, f"{kind} {item_id}"


def download_atomic(client: DiscogsClient, url: str, destination: Path) -> None:
    response = client.session.get(url, timeout=45)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").lower()
    if not content_type.startswith("image/"):
        raise ValueError(f"Content-Type non immagine: {content_type or '<mancante>'}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=destination.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
        tmp.write(response.content)
    temporary.replace(destination)


def iter_links(excel_path: str, selected_sheets: list[str] | None = None):
    with pd.ExcelFile(excel_path) as xls:
        names = selected_sheets or xls.sheet_names
        for sheet in names:
            if sheet not in xls.sheet_names:
                raise ValueError(f"Foglio non trovato: {sheet}")
            df = pd.read_excel(xls, sheet_name=sheet, dtype=str).fillna("")
            df.columns = [canonical_column(c) for c in df.columns]
            if "Link discogs" not in df.columns:
                logger.warning("Foglio %s ignorato: colonna Link discogs mancante", sheet)
                continue
            for idx, value in df["Link discogs"].items():
                link = str(value or "").strip()
                if link:
                    yield sheet, int(idx) + 2, link


def run(excel_path: str, output_dir: str, manifest_path: str, token: str,
        selected_sheets: list[str] | None = None, wait_seconds: float = 1.0):
    client = DiscogsClient(token, wait_seconds)
    manifest = []
    seen: set[tuple[str, str]] = set()
    for sheet, row, link in iter_links(excel_path, selected_sheets):
        entry = {"sheet": sheet, "row": row, "link": link, "status": "", "message": "", "downloaded": 0}
        try:
            kind, item_id = parse_discogs_link(link)
            key = (kind, item_id)
            if key in seen:
                entry.update(status="skipped", message="ID Discogs duplicato nel workbook")
                manifest.append(entry)
                continue
            seen.add(key)
            images, source = client.images(kind, item_id)
            item_dir = Path(output_dir) / item_id
            expected: set[str] = set()
            for image in images:
                uri = image.get("uri")
                if not uri:
                    continue
                filename = f"{entry['downloaded'] + 1:04d}.jpg"
                download_atomic(client, uri, item_dir / filename)
                expected.add(filename)
                entry["downloaded"] += 1
            # Elimina solo file numerici obsoleti creati da questo script.
            if item_dir.exists():
                for old in item_dir.glob("[0-9][0-9][0-9][0-9].jpg"):
                    if old.name not in expected:
                        old.unlink()
            entry.update(status="ok", message=source)
        except Exception as exc:
            entry.update(status="error", message=str(exc))
        manifest.append(entry)

    destination = Path(manifest_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sheet", "row", "link", "status", "message", "downloaded"])
        writer.writeheader()
        writer.writerows(manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_xlsx")
    parser.add_argument("--output-dir", default="covers")
    parser.add_argument("--manifest", default="covers_manifest.csv")
    parser.add_argument("--sheet", action="append", dest="sheets")
    parser.add_argument("--wait", type=float, default=1.0)
    args = parser.parse_args()
    load_dotenv()
    token = os.getenv("DISCOGS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCOGS_TOKEN non configurato nel file .env o nell'ambiente")
    rows = run(args.input_xlsx, args.output_dir, args.manifest, token, args.sheets, args.wait)
    logger.info("Manifest: %s; righe elaborate: %d", args.manifest, len(rows))


if __name__ == "__main__":
    main()
