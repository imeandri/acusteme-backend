#!/usr/bin/env python3
"""Audit read-only dei dati tecnici audio XML rispetto a Discogs e al profilo CA."""

from __future__ import annotations

import argparse
from html import escape
import json
import logging
import os
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv


LOG = logging.getLogger(__name__)
DISCOGS_API = "https://api.discogs.com"
WD_BASE = "http://www.wikidata.org/entity/"

# Etichette conformi all'output del servizio SPARQL del profilo CA.
LINKED_VALUES = {
    "33": f"33 rpm - en|Q117461697|{WD_BASE}Q117461697",
    "45": f"45 rpm - en|Q124418337|{WD_BASE}Q124418337",
    "78": f"78 rpm - en|Q117461698|{WD_BASE}Q117461698",
    "microgroove": f"microgroove record - en|Q86816874|{WD_BASE}Q86816874",
    "electrical": f"Electrical recording - en|Q123556092|{WD_BASE}Q123556092",
}

SIGNALS = {
    "mono": "monofonico",
    "monophonic": "monofonico",
    "stereo": "stereofonico",
    "stereophonic": "stereofonico",
    "quadraphonic": "quadrifonico",
}


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def structure_signature(element: ET.Element) -> tuple:
    """Firma strutturale: tag, nomi degli attributi e ordine dei figli."""
    return (
        element.tag,
        tuple(sorted(element.attrib)),
        tuple(structure_signature(child) for child in element),
    )


def parse_discogs_link(link: str) -> tuple[str, str]:
    match = re.search(r"/(release|master)/(\d+)", link or "", re.I)
    if not match:
        raise ValueError(f"link Discogs non riconosciuto: {link!r}")
    return match.group(1).lower(), match.group(2)


class DiscogsClient:
    def __init__(self, token: str, wait: float = 1.2, retries: int = 5):
        if not token:
            raise RuntimeError("DISCOGS_TOKEN non configurato")
        self.wait = wait
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Acusteme-DAC-Technical-Audit/1.0",
            "Authorization": f"Discogs token={token}",
        })

    def release(self, release_id: str) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            if self.wait:
                time.sleep(self.wait if attempt == 0 else self.wait * (2 ** attempt))
            try:
                response = self.session.get(f"{DISCOGS_API}/releases/{release_id}", timeout=30)
                if response.status_code == 429:
                    last_error = RuntimeError("Discogs rate limit (429)")
                    continue
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
        raise RuntimeError(f"Discogs release {release_id}: {last_error}")


def format_tokens(release: dict) -> set[str]:
    tokens: set[str] = set()
    for item in release.get("formats", []) or []:
        name = clean(item.get("name")).lower()
        if name:
            tokens.add(name)
        tokens.update(clean(value).lower() for value in (item.get("descriptions", []) or []) if clean(value))
    return tokens


def facts_from_discogs(release: dict) -> dict:
    tokens = format_tokens(release)
    speed = next((value for value in ("33", "45", "78") if any(re.search(rf"(?<!\d){value}(?:\s*[⅓1/3]*)?\s*rpm", token) for token in tokens)), None)
    signal = next((SIGNALS[token] for token in SIGNALS if token in tokens), None)
    if "cassette" in tokens:
        carrier = "cassette"
    elif tokens.intersection({"vinyl", "flexi-disc", "flexi disc"}):
        carrier = "disc"
    else:
        carrier = None
    # Le linee guida Discogs definiscono LP come 12 pollici/33 rpm.
    if speed is None and "lp" in tokens:
        speed = "33"
    return {"tokens": sorted(tokens), "speed": speed, "signal": signal, "carrier": carrier}


def facts_from_xml(record: ET.Element) -> dict:
    value = clean(record.findtext("descrizione_fisica/formato")).lower()
    match = re.search(r"\b(33|45|78)\s*rpm\b", value)
    carrier = "cassette" if value in {"mc", "audiocassetta", "music cassette", "cassette"} else ("disc" if match or any(x in value for x in ("lp", "flexi", "pollici")) else None)
    return {"raw": value, "speed": match.group(1) if match else None, "carrier": carrier}


def issue(code: str, severity: str, message: str, field: str = "") -> dict:
    return {"code": code, "severity": severity, "field": field, "message": message}


def check_linked(record: ET.Element, path: str, expected_qid: str | None, issues: list[dict]) -> None:
    node = record.find(path)
    value = clean(node.text) if node is not None else ""
    if not value:
        issues.append(issue("missing_value", "error", "Campo linked-data mancante o vuoto", path))
        return
    parts = value.split("|")
    if len(parts) != 3 or not all(parts):
        issues.append(issue("invalid_ca_wd_string", "error", "Sintassi attesa: etichetta|QID|URL", path))
        return
    label, qid, url = parts
    if not re.fullmatch(r"Q\d+", qid) or url.rstrip("/").split("/")[-1] != qid:
        issues.append(issue("invalid_wikidata_identity", "error", f"QID e URL non coerenti: {qid} / {url}", path))
    if expected_qid and qid != expected_qid:
        issues.append(issue("wrong_wikidata_item", "error", f"Atteso {expected_qid}, trovato {qid} ({label})", path))


def audit_parser_output(record: ET.Element) -> list[dict]:
    facts = facts_from_xml(record)
    issues: list[dict] = []
    designation = record.find("descrizione_fisica/designazione")
    support_code = clean(designation.get("supporto")) if designation is not None else ""
    designation_text = clean(designation.text).lower() if designation is not None else ""
    carrier_text = clean(record.findtext("dati_specifici/tipo_supporto")).lower()
    technique = clean(record.findtext("dati_specifici/tecnica1")).lower()

    if not facts["raw"]:
        issues.append(issue("missing_format", "error", "Formato sorgente mancante", "descrizione_fisica/formato"))
    if facts["carrier"] == "disc":
        for actual, expected, field in ((support_code, "AUC10", "descrizione_fisica/designazione/@supporto"), (designation_text, "disco sonoro", "descrizione_fisica/designazione"), (carrier_text, "disco sonoro", "dati_specifici/tipo_supporto"), (technique, "analogico", "dati_specifici/tecnica1")):
            if actual != expected:
                issues.append(issue("incoherent_parser_output", "error", f"Atteso {expected!r}, trovato {actual or '[vuoto]'!r}", field))
        check_linked(record, "dati_specifici/spessore_solco/CA_WD_string", "Q86816874", issues)
        check_linked(record, "dati_specifici/tecnica2/CA_WD_string", "Q123556092", issues)
        if facts["speed"]:
            check_linked(record, "dati_specifici/velocita/CA_WD_string", {"33": "Q117461697", "45": "Q124418337", "78": "Q117461698"}[facts["speed"]], issues)
    elif facts["carrier"] == "cassette":
        for actual, expected, field in ((support_code, "AUC2", "descrizione_fisica/designazione/@supporto"), (designation_text, "audiocassetta", "descrizione_fisica/designazione"), (carrier_text, "audiocassetta", "dati_specifici/tipo_supporto"), (technique, "analogico", "dati_specifici/tecnica1")):
            if actual != expected:
                issues.append(issue("incoherent_parser_output", "error", f"Atteso {expected!r}, trovato {actual or '[vuoto]'!r}", field))
        for path in ("dati_specifici/velocita/CA_WD_string", "dati_specifici/spessore_solco/CA_WD_string"):
            if clean(record.findtext(path)):
                issues.append(issue("incompatible_value", "error", "Valore proprio del disco presente su audiocassetta", path))
    else:
        issues.append(issue("unknown_format", "warning", f"Formato non interpretabile: {facts['raw'] or '[vuoto]'}", "descrizione_fisica/formato"))

    signal = clean(record.findtext("dati_specifici/segnale")).lower()
    if signal and signal not in {"monofonico", "bicanale", "stereofonico", "quadrifonico"}:
        issues.append(issue("invalid_closed_value", "error", f"Segnale fuori dal vocabolario CA: {signal}", "dati_specifici/segnale"))
    return issues


def audit_record(record: ET.Element, release: dict | None = None, source_issue: dict | None = None) -> dict:
    xml = facts_from_xml(record)
    issues = audit_parser_output(record)
    discogs = facts_from_discogs(release) if release is not None else None
    if source_issue:
        issues.append(source_issue)
    if discogs:
        if xml["speed"] and discogs["speed"] and xml["speed"] != discogs["speed"]:
            issues.append(issue("discogs_conflict", "error", f"Velocita XML {xml['speed']} rpm, Discogs {discogs['speed']} rpm", "dati_specifici/velocita"))
        if xml["carrier"] and discogs["carrier"] and xml["carrier"] != discogs["carrier"]:
            issues.append(issue("discogs_conflict", "error", f"Supporto XML {xml['carrier']}, Discogs {discogs['carrier']}", "dati_specifici/tipo_supporto"))
        xml_signal = clean(record.findtext("dati_specifici/segnale")).lower()
        if xml_signal and discogs["signal"] and xml_signal != discogs["signal"]:
            issues.append(issue("discogs_conflict", "error", f"Segnale XML {xml_signal}, Discogs {discogs['signal']}", "dati_specifici/segnale"))
        if not discogs["carrier"] and not discogs["speed"] and not discogs["signal"]:
            issues.append(issue("discogs_no_technical_data", "warning", "La release Discogs non espone dati tecnici utilizzabili"))
    severity = "error" if any(x["severity"] == "error" for x in issues) else ("warning" if issues else "ok")
    return {"record_id": clean(record.get("id")), "source_sheet": clean(record.get("source_sheet")), "source_row": clean(record.get("source_row")), "format": xml["raw"], "discogs_tokens": discogs["tokens"] if discogs else [], "status": severity, "requires_human_review": bool(issues), "issues": issues}


def write_html(report: dict, destination: Path) -> None:
    cards = []
    for row in report["records"]:
        items = "".join(f'<li class="{escape(x["severity"])}"><b>{escape(x["code"])}</b> — {escape(x["field"])} {escape(x["message"])}</li>' for x in row["issues"]) or "<li>Nessuna anomalia</li>"
        tokens = ", ".join(row["discogs_tokens"]) or "—"
        review = '<strong class="review">CONTROLLO UMANO RICHIESTO</strong>' if row["requires_human_review"] else '<strong class="clear">NESSUN CONTROLLO RICHIESTO</strong>'
        cards.append(f'<section class="record {row["status"]}"><h2>Record {escape(row["record_id"] or "[senza ID]")} · {review}</h2><p><b>Origine:</b> {escape(row["source_sheet"])} riga {escape(row["source_row"])} · <b>Formato:</b> {escape(row["format"] or "—")}</p><p><b>Discogs:</b> {escape(tokens)}</p><ul>{items}</ul></section>')
    summary = report["summary"]
    html = f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Audit dati tecnici DAC</title><style>body{{font:15px system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#222}}.summary{{display:flex;gap:1rem;flex-wrap:wrap}}.summary b{{padding:.6rem 1rem;border-radius:8px;background:#eee}}section{{border:1px solid #ccc;border-left:7px solid #398;margin:1rem 0;padding:.7rem 1rem;border-radius:6px}}section.error{{border-left-color:#b21}}section.warning{{border-left-color:#d90}}section.ok{{border-left-color:#297}}li.error,.review{{color:#9b1c1c}}li.warning{{color:#805d00}}.clear{{color:#176b45}}h2{{font-size:1.05rem;margin:.2rem 0}}p{{margin:.4rem 0}}</style></head><body><h1>Audit dati tecnici DAC</h1><p>Input: {escape(report["input"])}</p><div class="summary"><b>Totale {summary["total"]}</b><b>Controllo umano {summary["human_review"]}</b><b>Errori {summary["error"]}</b><b>Warning {summary["warning"]}</b><b>OK {summary["ok"]}</b></div>{''.join(cards)}</body></html>'''
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")


def run(input_xml: Path, report_json: Path, report_html: Path, client: DiscogsClient) -> dict:
    root = ET.parse(input_xml).getroot()
    rows = []
    for record in root.findall("record"):
        release_link = clean(record.findtext("discogs_release_url"))
        master_link = clean(record.findtext("discogs_master_url"))
        try:
            if release_link:
                kind, item_id = parse_discogs_link(release_link)
                rows.append(audit_record(record, client.release(item_id) if kind == "release" else None, None if kind == "release" else issue("discogs_not_exact", "warning", "Il link indicato non e una release esatta")))
            elif master_link:
                rows.append(audit_record(record, source_issue=issue("discogs_master_only", "warning", "Presente solo un link master; impossibile confermare il supporto della specifica edizione")))
            else:
                rows.append(audit_record(record, source_issue=issue("discogs_source_missing", "warning", "Nessuna fonte Discogs presente")))
        except Exception as exc:
            rows.append(audit_record(record, source_issue=issue("discogs_request_error", "error", str(exc))))
    report = {"input": str(input_xml.resolve()), "summary": {"total": len(rows), "human_review": sum(row["requires_human_review"] for row in rows), **{status: sum(row["status"] == status for row in rows) for status in ("error", "warning", "ok")}}, "records": rows}
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_html(report, report_html)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_xml", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--wait", type=float, default=1.2)
    args = parser.parse_args()
    load_dotenv(Path(__file__).with_name(".env"))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    report = run(args.input_xml, args.json, args.html, DiscogsClient(os.getenv("DISCOGS_TOKEN", "").strip(), args.wait))
    LOG.info("Risultato: %s", report["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
