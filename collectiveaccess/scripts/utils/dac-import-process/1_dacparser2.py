#!/usr/bin/env python3
"""Converte uno o più fogli DAC Excel in XML per CollectiveAccess."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET

import requests

from dac_common import DISCOGS_RE, parse_responsibility, read_excel_sheets, split_responsibilities, validate_sheet, write_validation_reports


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

GEONAMES_API = "https://api.geonames.org/searchJSON"
VEL_MEANING = {
    "33 rpm": ("33 rpm", "http://www.wikidata.org/entity/Q117461697"),
    "45 rpm": ("45 rpm", "http://www.wikidata.org/entity/Q124418337"),
    "78 rpm": ("78 rpm", "http://www.wikidata.org/entity/Q117461698"),
}


class ValidationFailure(RuntimeError):
    pass


def build_isbd_string(luogo: str, etichetta: str, anno: str) -> str:
    luogo, etichetta, anno = (str(v or "").strip() for v in (luogo, etichetta, anno))
    if luogo and etichetta and anno:
        return f"{luogo} : {etichetta}, {anno}."
    if etichetta and anno:
        return f"{etichetta}, {anno}."
    if luogo and anno:
        return f"{luogo}, {anno}."
    if luogo and etichetta:
        return f"{luogo} : {etichetta}."
    return f"{luogo or etichetta or anno}." if (luogo or etichetta or anno) else ""


def lookup_geonames(query: str, username: str, session=None) -> dict | None:
    if not username:
        return None
    client = session or requests.Session()
    for attempt in range(3):
        try:
            response = client.get(GEONAMES_API, params={"q": query, "maxRows": 1, "username": username}, timeout=15)
            response.raise_for_status()
            rows = response.json().get("geonames", [])
            if not rows:
                return None
            item = rows[0]
            return {
                "id": str(item.get("geonameId", "")),
                "url": f"https://www.geonames.org/{item.get('geonameId', '')}",
                "countryName": item.get("countryName", ""),
            }
        except requests.RequestException as exc:
            if attempt == 2:
                logger.warning("GeoNames non disponibile per %r: %s", query, exc)
    return None


def add_coded_element(parent, tag: str, raw_text: str, geonames_username: str = ""):
    raw = str(raw_text or "").strip()
    element = ET.SubElement(parent, tag)
    ET.SubElement(element, "value").text = re.sub(r"[\[\]?]", "", raw).strip()
    ET.SubElement(element, "inferred").text = "yes" if raw.startswith("[") and raw.endswith("]") else "no"
    ET.SubElement(element, "uncertain").text = "yes" if "?" in raw else "no"
    if tag == "luogo_di_pubblicazione" and raw and geonames_username:
        geo = lookup_geonames(re.sub(r"[\[\]?]", "", raw).strip(), geonames_username)
        if geo:
            ET.SubElement(element, "geonames_id").text = geo["id"]
            ET.SubElement(element, "geonames_url").text = geo["url"]
    return element


def append_text(parent, tag: str, value: str):
    element = ET.SubElement(parent, tag)
    element.text = str(value or "").strip()
    return element


def append_responsibility(container, raw: str):
    item = parse_responsibility(raw)
    element = ET.SubElement(container, "responsabilita", {"type": item.entity_type, "rel_type": item.role})
    append_text(element, "label", item.label)
    append_text(element, "inferred", "yes" if item.inferred else "no")
    append_text(element, "uncertain", "yes" if item.uncertain else "no")
    if item.entity_type == "persona":
        append_text(element, "first_name", item.first_name)
        append_text(element, "last_name", item.last_name)
        if item.pseudonym:
            append_text(element, "pseudonym", item.pseudonym)
            append_text(element, "real_name", item.real_name)
    append_text(element, "responsibility_INT", "primary")


def dataframe_to_records(root, sheet_name: str, df, geonames_username: str, used_ids: dict[str, str]):
    count = 0
    for idx, row in df.iterrows():
        if not any(str(v).strip() for v in row.values):
            continue
        link = str(row.get("Link discogs", "")).strip()
        match = DISCOGS_RE.search(link)
        record_id = match.group(2) if match else f"{re.sub(r'[^A-Za-z0-9]+', '-', sheet_name).strip('-')}-{int(idx)+2}"
        if record_id in used_ids:
            raise ValidationFailure(f"ID record duplicato {record_id}: {used_ids[record_id]} e {sheet_name}:{int(idx)+2}")
        used_ids[record_id] = f"{sheet_name}:{int(idx)+2}"

        rec = ET.SubElement(root, "record", {"id": record_id, "source_sheet": sheet_name, "source_row": str(int(idx)+2)})
        if match:
            append_text(rec, f"discogs_{match.group(1).lower()}_url", link)
        append_text(rec, "titolo", row.get("Titolo album", ""))
        publication = ET.SubElement(rec, "pubblicazione")
        add_coded_element(publication, "data_pubblicazione", row.get("Anno", ""))
        add_coded_element(publication, "luogo_di_pubblicazione", row.get("Luogo di pubblicazione", ""), geonames_username)
        append_text(publication, "etichetta", row.get("Etichetta", ""))

        collana = str(row.get("Collana", "")).strip()
        if collana:
            append_text(rec, "collana", collana)
            number = re.search(r"\[(\d+)\]\s*$", collana)
            if number:
                append_text(rec, "numerazione_interno_collana", number.group(1))
        if str(row.get("Numero di catalogo", "")).strip():
            append_text(rec, "numero_di_catalogo", row.get("Numero di catalogo", ""))
        if str(row.get("Note", "")).strip():
            append_text(rec, "note", row.get("Note", ""))

        physical = ET.SubElement(rec, "descrizione_fisica")
        append_text(physical, "unita", "1")
        designation = append_text(physical, "designazione", "disco sonoro")
        designation.set("supporto", "AUC10")
        formato = str(row.get("Formato", "")).strip()
        append_text(physical, "formato", formato)
        specifics = ET.SubElement(rec, "dati_specifici")
        append_text(specifics, "tipo_supporto", "disco sonoro")
        append_text(specifics, "tecnica1", "analogico")
        groove = ET.SubElement(specifics, "spessore_solco")
        append_text(
            groove,
            "label",
            "microgroove record [http://www.wikidata.org/entity/Q86816874]  "
            "(mechanical sound recording with narrow grooves (around 100 grooves per centimeter, "
            "three times higher than in shellac records), usually stamped in 'vinyl' (PVC composite))",
        )
        append_text(groove, "url", "http://www.wikidata.org/entity/Q86816874")
        recording = ET.SubElement(specifics, "tecnica2")
        append_text(
            recording,
            "label",
            "Electrical recording - en [A recording process in which a microphone is used to convert "
            "the sound into an electrical signal that is amplified and used to actuate the recording stylus]",
        )
        append_text(recording, "url", "http://www.wikidata.org/entity/Q123556092")
        append_text(specifics, "segnale", "monofonico")
        speed = re.match(r"^(33|45|78)\s*rpm\b", formato, re.IGNORECASE)
        if speed:
            key = f"{speed.group(1)} rpm"
            vel = ET.SubElement(specifics, "velocita")
            append_text(vel, "label", VEL_MEANING[key][0])
            append_text(vel, "url", VEL_MEANING[key][1])
        elif formato:
            vel = ET.SubElement(specifics, "velocita")
            append_text(vel, "label", formato)

        relations = ET.SubElement(rec, "relazioni")
        for raw in split_responsibilities(row.get("Responsabilità", "")):
            if parse_responsibility(raw).pseudonym:
                logger.warning(
                    "Pseudonimo escluso dall'XML per revisione manuale (%s riga %d): %s",
                    sheet_name, int(idx) + 2, raw,
                )
                continue
            append_responsibility(relations, raw)
        label = str(row.get("Etichetta", "")).strip()
        if label:
            entity = ET.SubElement(relations, "responsabilita", {"type": "ente", "rel_type": "R55_100_026 Label"})
            append_text(entity, "label", label)
            append_text(entity, "inferred", "no")
            append_text(entity, "uncertain", "no")
            append_text(entity, "responsibility_INT", "production")

        isbd = build_isbd_string(row.get("Luogo di pubblicazione", ""), row.get("Etichetta", ""), row.get("Anno", ""))
        if isbd:
            append_text(rec, "isbd", isbd)
        count += 1
    return count


def write_atomic(tree: ET.ElementTree, output_path: str | Path):
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="  ")
    with tempfile.NamedTemporaryFile("wb", dir=destination.parent, delete=False) as tmp:
        temp_path = Path(tmp.name)
        tree.write(tmp, encoding="utf-8", xml_declaration=True)
    temp_path.replace(destination)


def excel_to_xml(input_xlsx, output_xml, sheets=None, geonames_username="", validation_report=None):
    loaded = list(read_excel_sheets(input_xlsx, sheets))
    issues = []
    for sheet_name, df, duplicates in loaded:
        issues.extend(validate_sheet(sheet_name, df, duplicates))
    report_path = Path(validation_report or f"{output_xml}.validation.json")
    _, html_report = write_validation_reports(issues, report_path, title=f"Validazione {Path(input_xlsx).name}")
    errors = [issue for issue in issues if issue["severity"] == "error"]
    if errors:
        raise ValidationFailure(f"Validazione fallita: {len(errors)} errori. Vedi {report_path} e {html_report}")

    root = ET.Element("records")
    used_ids: dict[str, str] = {}
    total = sum(dataframe_to_records(root, name, df, geonames_username, used_ids) for name, df, _ in loaded)
    write_atomic(ET.ElementTree(root), output_xml)
    logger.info("Creati %d record da %d fogli in %s", total, len(loaded), output_xml)
    return {"records": total, "sheets": len(loaded), "issues": len(issues)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_xlsx")
    parser.add_argument("output_xml")
    parser.add_argument("--sheet", action="append", dest="sheets", help="Foglio da elaborare; ripetibile")
    parser.add_argument("--geonames-username", default="")
    parser.add_argument("--validation-report")
    args = parser.parse_args()
    excel_to_xml(args.input_xlsx, args.output_xml, args.sheets, args.geonames_username, args.validation_report)


if __name__ == "__main__":
    main()
