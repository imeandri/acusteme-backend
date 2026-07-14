#!/usr/bin/env python3
"""Regole condivise per la validazione dei fogli DAC e delle responsabilità."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from html import escape
import json
import re
import unicodedata
import xml.etree.ElementTree as ET

import pandas as pd


COLUMN_ALIASES = {
    "anno": "Anno",
    "luogo di pubblicazione": "Luogo di pubblicazione",
    "etichetta": "Etichetta",
    "collana": "Collana",
    "numero di catalogo": "Numero di catalogo",
    "n. catalogo": "Numero di catalogo",
    "n catalogo": "Numero di catalogo",
    "formato": "Formato",
    "responsabilita": "Responsabilità",
    "interpreti": "Responsabilità",
    "titolo album": "Titolo album",
    "titolo": "Titolo album",
    "titoli": "Titolo album",
    "note": "Note",
    "link discogs": "Link discogs",
    "info digitalizzazione": "Info digitalizzazione",
    "digitalizzazione": "Info digitalizzazione",
    "note digitalizzazione": "Note digitalizzazione",
    "notes": "notes",
}

REQUIRED_COLUMNS = {
    "Anno", "Luogo di pubblicazione", "Etichetta", "Formato",
    "Responsabilità", "Titolo album", "Link discogs",
}
RELATOR_RE = re.compile(r"^R\d+(?:_\d+)+(?:\s+.+)?$", re.IGNORECASE)
DISCOGS_RE = re.compile(r"/(master|release)/(\d+)", re.IGNORECASE)
PSEUDONYM_RE = re.compile(
    r"^\*(?P<alias>[^*]+)\*\s*\[(?P<real>[^]]+)\]\s*$"
)


def normalize_key(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = " ".join(text.replace("\u00a0", " ").strip().split()).casefold()
    return text.replace("à", "a")


def canonical_column(value: object) -> str:
    key = normalize_key(value)
    return COLUMN_ALIASES.get(key, " ".join(str(value or "").strip().split()))


def normalize_dataframe_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    renamed = [canonical_column(c) for c in df.columns]
    duplicates = [name for name, count in Counter(renamed).items() if count > 1]
    result = df.copy()
    result.columns = renamed
    return result, duplicates


def available_sheets(path: str | Path) -> list[str]:
    with pd.ExcelFile(path) as xls:
        return list(xls.sheet_names)


def read_excel_sheets(path: str | Path, selected: list[str] | None = None):
    with pd.ExcelFile(path) as xls:
        names = selected or xls.sheet_names
        missing = [name for name in names if name not in xls.sheet_names]
        if missing:
            raise ValueError(f"Fogli non trovati: {', '.join(missing)}")
        for name in names:
            df = pd.read_excel(xls, sheet_name=name, dtype=str).fillna("")
            df, duplicates = normalize_dataframe_columns(df)
            yield name, df, duplicates


def split_name(value: str) -> tuple[str, str]:
    value = " ".join(value.strip().split())
    if "," not in value:
        return value, ""
    first, last = value.split(",", 1)
    return first.strip(), last.strip()


def normalize_legacy_code(code: str) -> str:
    code = str(code or "").upper()
    return re.sub(r"^R55_26_(\d+)$", r"R55_100_\1", code)


@dataclass
class Responsibility:
    raw: str
    label: str
    role: str
    entity_type: str
    first_name: str = ""
    last_name: str = ""
    pseudonym: str = ""
    real_name: str = ""
    inferred: bool = False
    uncertain: bool = False
    errors: list[str] = field(default_factory=list)


def parse_responsibility(part: str) -> Responsibility:
    raw = " ".join(str(part).replace("\u00a0", " ").strip().split())
    errors: list[str] = []
    if raw.count("(") != raw.count(")"):
        errors.append("parentesi tonde sbilanciate")
    if raw.count("[") != raw.count("]"):
        errors.append("parentesi quadre sbilanciate")

    inferred = raw.startswith("[") and raw.endswith("]")
    uncertain = "?" in raw
    inner = raw[1:-1].strip() if inferred else raw
    inner = inner.rstrip("?").strip()
    left, right = inner.rfind("("), inner.rfind(")")
    if left >= 0 and right > left:
        name_part = inner[:left].strip()
        role = inner[left + 1:right].strip()
    else:
        name_part, role = inner, ""
        errors.append("ruolo mancante o non parsabile")

    if role and not RELATOR_RE.fullmatch(role):
        errors.append(f"ruolo non codificato: {role}")

    pseudonym = real_name = ""
    pseudo = PSEUDONYM_RE.fullmatch(name_part)
    if pseudo:
        pseudonym = pseudo.group("alias").strip()
        real_name = pseudo.group("real").strip()
        label = pseudonym
        first_name, last_name = split_name(real_name)
        entity_type = "persona"
    else:
        if "*" in name_part:
            errors.append("marcatura pseudonimo con asterischi non valida")
        label = name_part.replace(",", "").strip()
        entity_type = "ente" if name_part.isupper() else "persona"
        first_name, last_name = ("", "") if entity_type == "ente" else split_name(name_part)

    if not label:
        errors.append("nome o label mancante")
    return Responsibility(
        raw=raw, label=label, role=role, entity_type=entity_type,
        first_name=first_name, last_name=last_name,
        pseudonym=pseudonym, real_name=real_name,
        inferred=inferred, uncertain=uncertain, errors=errors,
    )


def split_responsibilities(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def validate_sheet(sheet: str, df: pd.DataFrame, duplicate_columns: list[str] | None = None):
    issues: list[dict] = []
    for col in duplicate_columns or []:
        issues.append({"sheet": sheet, "row": 1, "field": col, "severity": "error",
                       "message": "colonna duplicata dopo la normalizzazione"})
    for col in sorted(REQUIRED_COLUMNS - set(df.columns)):
        issues.append({"sheet": sheet, "row": 1, "field": col, "severity": "error",
                       "message": "colonna obbligatoria mancante"})
    if REQUIRED_COLUMNS - set(df.columns):
        return issues

    seen_ids: dict[str, int] = {}
    for idx, row in df.iterrows():
        excel_row = int(idx) + 2
        if not any(str(v).strip() for v in row.values):
            continue
        link = str(row.get("Link discogs", "")).strip()
        if link:
            match = DISCOGS_RE.search(link)
            if not match:
                issues.append({"sheet": sheet, "row": excel_row, "field": "Link discogs",
                               "severity": "error", "message": f"link Discogs non supportato: {link}"})
            else:
                did = match.group(2)
                if did in seen_ids:
                    issues.append({"sheet": sheet, "row": excel_row, "field": "Link discogs",
                                   "severity": "error",
                                   "message": f"ID Discogs duplicato; prima occorrenza riga {seen_ids[did]}: {did}"})
                else:
                    seen_ids[did] = excel_row

        for part in split_responsibilities(row.get("Responsabilità", "")):
            parsed = parse_responsibility(part)
            for message in parsed.errors:
                issues.append({"sheet": sheet, "row": excel_row, "field": "Responsabilità",
                               "severity": "error", "message": message, "value": part})
    return issues


def issue_suggestion(issue: dict) -> str:
    message = issue.get("message", "").casefold()
    if "id discogs duplicato" in message:
        return "Verificare se le righe descrivono lo stesso record; mantenere un solo ID oppure usare la release Discogs corretta."
    if "link discogs non supportato" in message:
        return "Inserire un URL Discogs contenente /release/ID o /master/ID, oppure lasciare il campo vuoto."
    if "parentesi tonde" in message:
        return "Bilanciare le parentesi tonde e mantenere il ruolo nella forma Nome (Rxx_yyy Etichetta)."
    if "parentesi quadre" in message:
        return "Bilanciare le parentesi quadre usate per valori inferiti o nomi reali."
    if "pseudonimo" in message or "asterisch" in message:
        return "Usare la forma esatta *Pseudonimo* [Nome, Cognome] (Rxx_yyy Ruolo)."
    if "ruolo mancante" in message:
        return "Aggiungere un relator tra parentesi, per esempio Nome, Cognome (R56_179 Performer)."
    if "ruolo non codificato" in message:
        return "Sostituire il ruolo libero con un codice relator presente nel profilo CollectiveAccess."
    if "codice assente dal profilo" in message:
        return "Verificare il codice nel profilo CA o correggere il valore Excel usando un relator esistente."
    if "colonna obbligatoria" in message:
        return "Aggiungere la colonna richiesta o rinominare l'intestazione con una variante riconosciuta."
    if "colonna duplicata" in message:
        return "Unire o rinominare le colonne che diventano equivalenti dopo la normalizzazione."
    if "legacy ambiguo" in message:
        return "Controllare i type del profilo che condividono lo stesso codice legacy."
    if "nome o label mancante" in message:
        return "Inserire il nome dell'entità o eliminare la componente vuota."
    return "Controllare manualmente il valore indicato prima di ripetere l'importazione."


def write_validation_reports(issues: list[dict], json_path: str | Path, html_path: str | Path | None = None,
                             title: str = "Report validazione DAC", write_json: bool = True) -> tuple[Path, Path]:
    json_destination = Path(json_path)
    html_destination = Path(html_path) if html_path else json_destination.with_suffix(".html")
    json_destination.parent.mkdir(parents=True, exist_ok=True)
    html_destination.parent.mkdir(parents=True, exist_ok=True)
    enriched = [{**issue, "suggestion": issue.get("suggestion") or issue_suggestion(issue)} for issue in issues]
    if write_json:
        json_destination.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")

    error_count = sum(issue.get("severity") == "error" for issue in enriched)
    warning_count = sum(issue.get("severity") == "warning" for issue in enriched)
    rows = []
    for issue in enriched:
        severity = escape(str(issue.get("severity", "")))
        css = "error" if severity == "error" else "warning"
        rows.append(
            "<tr>"
            f"<td>{escape(str(issue.get('sheet', '')))}</td>"
            f"<td class='num'>{escape(str(issue.get('row', '')))}</td>"
            f"<td>{escape(str(issue.get('field', '')))}</td>"
            f"<td><span class='badge {css}'>{severity}</span></td>"
            f"<td>{escape(str(issue.get('message', '')))}</td>"
            f"<td class='value'>{escape(str(issue.get('value', '')))}</td>"
            f"<td>{escape(str(issue.get('suggestion', '')))}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='7' class='ok'>Nessun errore rilevato.</td></tr>")
    document = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><title>{escape(title)}</title>
<style>
body{{font:14px system-ui,sans-serif;margin:24px;color:#17202a}}h1{{margin-bottom:6px}}
.summary{{display:flex;gap:12px;margin:18px 0}}.card{{padding:10px 16px;border-radius:8px;background:#f3f5f7}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #d7dce1;padding:8px;text-align:left;vertical-align:top}}
th{{background:#eef2f5;position:sticky;top:0}}tr:nth-child(even){{background:#fafbfc}}.num{{text-align:right}}
.badge{{display:inline-block;padding:2px 7px;border-radius:10px;color:white}}.error{{background:#b42318}}.warning{{background:#b54708}}
.value{{max-width:420px;overflow-wrap:anywhere}}.ok{{color:#067647;font-weight:700;text-align:center}}
</style></head><body><h1>{escape(title)}</h1>
<p>Report generato automaticamente prima dell'importazione. Correggere gli errori e rieseguire il controllo.</p>
<div class="summary"><div class="card"><strong>Errori:</strong> {error_count}</div><div class="card"><strong>Warning:</strong> {warning_count}</div><div class="card"><strong>Totale:</strong> {len(enriched)}</div></div>
<table><thead><tr><th>Foglio</th><th>Riga</th><th>Campo</th><th>Gravità</th><th>Errore</th><th>Valore originale</th><th>Correzione suggerita</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></body></html>"""
    html_destination.write_text(document, encoding="utf-8")
    return json_destination, html_destination


def localname(tag: str) -> str:
    return tag.split("}")[-1]


def legacy_code_from_label(text: str) -> str:
    match = re.match(r"^(R\d+(?:_\d+)+)\b", " ".join((text or "").split()), re.IGNORECASE)
    return match.group(1).upper() if match else ""


def extract_profile_relators(xml_path: str | Path, table_name: str = "ca_objects_x_entities"):
    root = ET.parse(xml_path).getroot()
    table = next((e for e in root.iter() if localname(e.tag) == "relationshipTable"
                  and e.get("name") == table_name), None)
    if table is None:
        raise ValueError(f"relationshipTable non trovata: {table_name}")
    records: list[dict] = []

    def walk(node, parent=""):
        code = (node.get("code") or "").strip()
        labels: dict[str, str] = {}
        for label in [e for e in node.iter() if localname(e.tag) == "label"]:
            locale = label.get("locale", "")
            for child in label:
                if localname(child.tag) in {"typename", "typename_reverse"}:
                    labels[f"{locale}:{localname(child.tag)}"] = (child.text or "").strip()
        candidates = [legacy_code_from_label(v) for v in labels.values()]
        legacy = next((v for v in candidates if v), "")
        type_containers = [e for e in node if localname(e.tag) == "types"]
        has_children = any(any(localname(child.tag) == "type" for child in types) for types in type_containers)
        if code or legacy:
            records.append({"code": code, "legacy_code": legacy, "parent": parent,
                            "labels": labels, "has_children": has_children})
        for types in type_containers:
            for child in [e for e in types if localname(e.tag) == "type"]:
                walk(child, code or parent)

    types = next((e for e in table if localname(e.tag) == "types"), None)
    if types is None:
        raise ValueError(f"Nodo <types> mancante in {table_name}")
    for child in [e for e in types if localname(e.tag) == "type"]:
        walk(child)
    return records
