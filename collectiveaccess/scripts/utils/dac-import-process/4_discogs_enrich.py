#!/usr/bin/env python3

import warnings
try:
    from urllib3.exceptions import NotOpenSSLWarning
    warnings.simplefilter("ignore", NotOpenSSLWarning)
except ImportError:
    pass

import os
import re
import time
import logging
import requests
import xml.etree.ElementTree as ET
from typing import Optional
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import tempfile


# =========================================================
# LOGGING / TERMINAL COLORS
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def print_red(msg: str) -> None:
    print(f"{RED}{msg}{RESET}")


def print_yellow(msg: str) -> None:
    print(f"{YELLOW}{msg}{RESET}")


# =========================================================
# CONFIG / TOKEN
# =========================================================
env_path = find_dotenv()
if env_path:
    load_dotenv(env_path)

TOKEN = os.getenv("DISCOGS_TOKEN", "").strip()

HEADERS = {
    "User-Agent": "Acusteme-DAC-Importer/1.0",
    "Authorization": f"Discogs token={TOKEN}"
}

BASE_API = "https://api.discogs.com"
BASE_WEB = "https://www.discogs.com"


# =========================================================
# HELPERS GENERALI
# =========================================================
def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def ask_float(prompt: str, default: float) -> float:
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"Valore numerico non valido: {raw!r}") from exc
    if value < 0:
        raise ValueError("Il tempo di attesa non può essere negativo")
    return value


def ask_str(prompt: str, default: str) -> str:
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw if raw else default


def normalize_track_positions(note: str) -> str:
    """
    Porta in maiuscolo il codice traccia iniziale:
    a1:  -> A1:
    b:   -> B:
    b2a: -> B2A:
    B2a: -> B2A:
    """
    if not note:
        return note

    chunks = [c.strip() for c in note.split(" ; ")]
    normalized = []

    for chunk in chunks:
        chunk = re.sub(
            r"^([A-Za-z0-9]+):",
            lambda m: m.group(1).upper() + ":",
            chunk
        )
        normalized.append(chunk)

    return " ; ".join(normalized)


# =========================================================
# CLIENT DISCOGS CON THROTTLING
# =========================================================
class DiscogsClient:
    def __init__(self, wait_seconds: float = 1.2, max_retries: int = 5):
        if not TOKEN:
            raise RuntimeError("DISCOGS_TOKEN non configurato nel file .env o nell'ambiente")
        self.wait_seconds = wait_seconds
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_json(self, url: str) -> dict:
        last_exc = None
        next_wait = self.wait_seconds

        for attempt in range(self.max_retries):
            if attempt > 0:
                print(f"Retry {attempt}/{self.max_retries - 1} dopo {next_wait:.1f}s -> {url}")
            time.sleep(next_wait)

            try:
                r = self.session.get(url, timeout=30)

                if r.status_code == 429:
                    retry_after = r.headers.get("Retry-After")
                    if retry_after:
                        try:
                            sleep_time = float(retry_after)
                        except ValueError:
                            try:
                                retry_date = parsedate_to_datetime(retry_after)
                                sleep_time = max(0.0, (retry_date - datetime.now(timezone.utc)).total_seconds())
                            except (TypeError, ValueError):
                                sleep_time = max(self.wait_seconds, 2.0)
                    else:
                        sleep_time = max(self.wait_seconds, 2.0) * (2 ** attempt)

                    print_red(f"429 Too Many Requests. Attendo {sleep_time:.1f}s")
                    last_exc = requests.HTTPError(f"429 Too Many Requests for url: {url}")
                    # Il ciclo applica l'attesa una sola volta all'inizio del retry.
                    next_wait = sleep_time
                    continue

                r.raise_for_status()
                return r.json()

            except requests.RequestException as e:
                last_exc = e
                next_wait = max(self.wait_seconds, 1.0) * (2 ** attempt)

        if last_exc:
            raise last_exc
        raise RuntimeError(f"Errore sconosciuto su {url}")

    def get_release(self, release_id: str) -> dict:
        return self.get_json(f"{BASE_API}/releases/{release_id}")

    def get_master(self, master_id: str) -> dict:
        return self.get_json(f"{BASE_API}/masters/{master_id}")

    def get_first_release_id(self, master_id: str) -> Optional[str]:
        data = self.get_json(f"{BASE_API}/masters/{master_id}/versions")
        versions = data.get("versions", []) or []
        for v in versions:
            if v.get("id"):
                return str(v["id"])
        return None


# =========================================================
# HELPERS DISCOGS
# =========================================================
def parse_discogs_link(link: str) -> tuple[str, str]:
    pattern = re.compile(r"/(master|release)/(\d+)", re.I)
    m = pattern.search(link or "")
    if not m:
        raise ValueError(f"Link Discogs non in formato previsto: {link!r}")
    return m.group(1).lower(), m.group(2)


def make_release_url(release_id: str) -> str:
    return f"{BASE_WEB}/release/{release_id}"


def make_master_url(master_id: str) -> str:
    return f"{BASE_WEB}/master/{master_id}"


# =========================================================
# NOTE DI CONTENUTO
# =========================================================
def format_artist_name(artist: dict) -> str:
    anv = clean_text(artist.get("anv", ""))
    name = clean_text(artist.get("name", ""))
    return anv or name


def format_track_credits(track: dict) -> str:
    credits = []

    artists = track.get("artists", []) or []
    extraartists = track.get("extraartists", []) or []

    for a in artists:
        name = format_artist_name(a)
        if name:
            credits.append(name)

    for ea in extraartists:
        name = format_artist_name(ea)
        role = clean_text(ea.get("role", ""))
        if not name:
            continue
        if role:
            credits.append(f"{role}: {name}")
        else:
            credits.append(name)

    seen = set()
    uniq = []
    for c in credits:
        if c not in seen:
            uniq.append(c)
            seen.add(c)

    return " | ".join(uniq)


def build_note_di_contenuto(release_json: dict) -> str:
    tracklist = release_json.get("tracklist", []) or []
    chunks = []

    for t in tracklist:
        if t.get("type_") != "track":
            continue

        position = clean_text(t.get("position", ""))
        title = clean_text(t.get("title", ""))
        duration = clean_text(t.get("duration", ""))
        credits = format_track_credits(t)

        if not title:
            continue

        parts = []
        if position:
            parts.append(f"{position}:")
        parts.append(title)

        entry = " ".join(parts).strip()

        if duration:
            entry += f" ({duration})"

        if credits:
            entry += f" [{credits}]"

        chunks.append(entry)

    note = " ; ".join(chunks)
    note = normalize_track_positions(note)
    return note


# =========================================================
# IDENTIFICATORI
# =========================================================
def build_discogs_identifiers(
    input_type: str,
    input_id: str,
    release_id: Optional[str],
    master_id: Optional[str],
    release_was_derived: bool
) -> list[dict]:
    out = []

    out.append({
        "tipologia_identificatore": "Discogs input ID",
        "numero": str(input_id),
        "note_identificatore": str(input_type)
    })

    if master_id:
        note = ""
        if input_type == "master":
            note = "master da link Discogs"
        out.append({
            "tipologia_identificatore": "Discogs master ID",
            "numero": str(master_id),
            "note_identificatore": note
        })

    if release_id:
        note = ""
        if release_was_derived and input_type == "master":
            note = "release usata per interrogazione derivata da master"
        out.append({
            "tipologia_identificatore": "Discogs release ID",
            "numero": str(release_id),
            "note_identificatore": note
        })

    return out


def build_matrix_identifiers(release_json: dict) -> list[dict]:
    identifiers = release_json.get("identifiers", []) or []
    out = []

    for ident in identifiers:
        type_ = clean_text(ident.get("type", ""))
        if "matrix" not in type_.lower() and "runout" not in type_.lower():
            continue

        value = clean_text(ident.get("value", ""))
        description = clean_text(ident.get("description", ""))

        if not value:
            continue

        out.append({
            "tipologia_identificatore": "Numero matrice",
            "numero": value,
            "note_identificatore": description
        })

    return out

# =========================================================
# AGGIUNGE attributi all'xml su specifici identificatori
# =========================================================
def add_ca_id_type_attributes(root: ET.Element) -> None:
    """
    Aggiunge attributi id_type utili per il mapping CollectiveAccess.
    """

    # 1) numero_di_catalogo
    for el in root.iter("numero_di_catalogo"):
        el.set("id_type", "Numero_edizione_registrazioni_")

    # 2-4) tipologia_identificatore
    mapping = {
        "Discogs master ID": "discogsmasterID",
        "Discogs release ID": "discogsreleaseID",
        "Numero matrice": "Numero_matrice",
    }

    for el in root.iter("tipologia_identificatore"):
        text = clean_text(el.text)
        if text in mapping:
            el.set("id_type", mapping[text])
# =========================================================
# ENRICHMENT
# =========================================================
def enrich_discogs_from_link(link: str, client: DiscogsClient) -> dict:
    input_type, input_id = parse_discogs_link(link)

    release_json = None
    release_id = None
    master_id = None
    release_was_derived = False
    release_url = ""
    master_url = ""

    if input_type == "release":
        release_json = client.get_release(input_id)
        release_id = str(release_json.get("id")) if release_json.get("id") else input_id
        master_id = (
            str(release_json.get("master_id"))
            if release_json.get("master_id") not in (None, "")
            else None
        )

    elif input_type == "master":
        master_json = client.get_master(input_id)
        master_id = str(master_json.get("id")) if master_json.get("id") else input_id

        candidate_release = master_json.get("main_release") or client.get_first_release_id(input_id)
        if candidate_release:
            release_json = client.get_release(str(candidate_release))
            release_id = str(release_json.get("id")) if release_json.get("id") else str(candidate_release)
            if release_id:
                release_was_derived = True

            rel_master_id = release_json.get("master_id")
            if rel_master_id not in (None, ""):
                master_id = str(rel_master_id)

    else:
        raise ValueError(f"Tipo Discogs non gestito: {input_type}")

    if release_id:
        release_url = make_release_url(release_id)
    if master_id:
        master_url = make_master_url(master_id)

    note_di_contenuto = build_note_di_contenuto(release_json) if release_json else ""

    discogs_identifiers = build_discogs_identifiers(
        input_type=input_type,
        input_id=input_id,
        release_id=release_id,
        master_id=master_id,
        release_was_derived=release_was_derived
    )

    matrix_identifiers = build_matrix_identifiers(release_json) if release_json else []

    all_identifiers = discogs_identifiers + matrix_identifiers

    return {
        "discogs_input_type": input_type,
        "discogs_input_id": input_id,
        "discogs_release_id": release_id or "",
        "discogs_master_id": master_id or "",
        "discogs_release_url": release_url,
        "discogs_master_url": master_url,
        "release_derivata_da_master": "yes" if release_was_derived else "",
        "note_di_contenuto": note_di_contenuto,
        "identificatori_standard": all_identifiers
    }


# =========================================================
# XML HELPERS
# =========================================================
def append_text_element(parent: ET.Element, tag: str, text: str) -> Optional[ET.Element]:
    text = clean_text(text)
    if not text:
        return None
    el = ET.SubElement(parent, tag)
    el.text = text
    return el


def build_discogs_info_element(data: dict) -> ET.Element:
    discogs_info = ET.Element("discogs_info")

    append_text_element(discogs_info, "discogs_input_type", data.get("discogs_input_type", ""))
    append_text_element(discogs_info, "discogs_input_id", data.get("discogs_input_id", ""))
    append_text_element(discogs_info, "discogs_release_id", data.get("discogs_release_id", ""))
    append_text_element(discogs_info, "discogs_master_id", data.get("discogs_master_id", ""))
    append_text_element(discogs_info, "discogs_release_url", data.get("discogs_release_url", ""))
    append_text_element(discogs_info, "discogs_master_url", data.get("discogs_master_url", ""))
    append_text_element(discogs_info, "release_derivata_da_master", data.get("release_derivata_da_master", ""))
    append_text_element(discogs_info, "note_di_contenuto", data.get("note_di_contenuto", ""))

    identifiers = data.get("identificatori_standard", []) or []
    if identifiers:
        ids_container = ET.SubElement(discogs_info, "identificatori_standard")
        for ident in identifiers:
            id_el = ET.SubElement(ids_container, "identificatore_standard")
            append_text_element(id_el, "tipologia_identificatore", ident.get("tipologia_identificatore", ""))
            append_text_element(id_el, "numero", ident.get("numero", ""))
            append_text_element(id_el, "note_identificatore", ident.get("note_identificatore", ""))

    return discogs_info


def insert_before_isbd(record: ET.Element, new_element: ET.Element) -> None:
    children = list(record)
    for i, child in enumerate(children):
        if child.tag == "isbd":
            record.insert(i, new_element)
            return
    record.append(new_element)


def get_discogs_urls_from_record(record: ET.Element) -> tuple[str, str]:
    rel = clean_text(record.findtext("discogs_release_url", default=""))
    mas = clean_text(record.findtext("discogs_master_url", default=""))
    return rel, mas


def get_primary_discogs_link_from_record(record: ET.Element) -> str:
    rel, mas = get_discogs_urls_from_record(record)
    return rel or mas


# =========================================================
# CONTROLLI COERENZA
# =========================================================
def record_id_matches_discogs_link(record: ET.Element) -> tuple[bool, str]:
    """
    Controlla che record/@id coincida con almeno uno degli ID Discogs presenti
    nei link del record.
    """
    record_id = clean_text(record.get("id", ""))
    rel_url, mas_url = get_discogs_urls_from_record(record)

    if not record_id:
        return False, "record/@id mancante"

    candidate_ids = []

    if rel_url:
        try:
            rel_type, rel_id = parse_discogs_link(rel_url)
            candidate_ids.append((rel_type, rel_id, rel_url))
        except Exception as e:
            return False, f"link release non parsabile: {rel_url} ({e})"

    if mas_url:
        try:
            mas_type, mas_id = parse_discogs_link(mas_url)
            candidate_ids.append((mas_type, mas_id, mas_url))
        except Exception as e:
            return False, f"link master non parsabile: {mas_url} ({e})"

    if not candidate_ids:
        return False, "nessun link Discogs nel record"

    for typ, did, _url in candidate_ids:
        if record_id == did:
            return True, ""

    details = " | ".join([f"{typ}={did}" for typ, did, _ in candidate_ids])
    return False, f"mismatch: record/@id={record_id} ma link Discogs contiene {details}"


# =========================================================
# MAIN
# =========================================================
def main():
    input_xml = ask_str("File XML di input", "output.xml")
    output_xml = ask_str("File XML di output", "output_with_discogs.xml")
    wait_seconds = ask_float("Secondi di attesa tra richieste", 1.5)

    client = DiscogsClient(wait_seconds=wait_seconds, max_retries=5)

    tree = ET.parse(input_xml)
    root = tree.getroot()

    if root.tag != "records":
        raise RuntimeError(f"Root inattesa: {root.tag!r}. Mi aspettavo 'records'.")

    records = root.findall("record")
    print(f"Trovati {len(records)} record")

    ids = [clean_text(record.get("id", "")) for record in records]
    duplicates = sorted({record_id for record_id in ids if record_id and ids.count(record_id) > 1})
    if duplicates:
        raise RuntimeError(f"ID record duplicati nell'XML: {', '.join(duplicates[:20])}")

    enriched_count = 0
    skipped_count = 0
    error_count = 0
    warning_count = 0

    for idx, record in enumerate(records, start=1):
        record_id = clean_text(record.get("id", ""))
        link = get_primary_discogs_link_from_record(record)

        print("\n" + "=" * 80)
        print(f"RECORD {idx}/{len(records)} | id={record_id}")

        if not link:
            print("Nessun link Discogs nel record -> salto")
            skipped_count += 1
            continue

        print(f"Link Discogs: {link}")

        ok, msg = record_id_matches_discogs_link(record)
        if not ok:
            print_red(f"WARNING: {msg} -> salto record")
            warning_count += 1
            skipped_count += 1
            continue

        try:
            old = record.find("discogs_info")
            if old is not None:
                record.remove(old)

            enriched = enrich_discogs_from_link(link, client)
            discogs_info_el = build_discogs_info_element(enriched)
            insert_before_isbd(record, discogs_info_el)

            print(f"discogs_input_type: {enriched['discogs_input_type']}")
            print(f"discogs_input_id: {enriched['discogs_input_id']}")
            print(f"discogs_release_id: {enriched['discogs_release_id']}")
            print(f"discogs_master_id: {enriched['discogs_master_id']}")
            preview = enriched["note_di_contenuto"][:220]
            if len(enriched["note_di_contenuto"]) > 220:
                preview += "..."
            print(f"note_di_contenuto: {preview}")

            enriched_count += 1

        except Exception as e:
            print_red(f"ERRORE su record id={record_id}: {e}")
            error_count += 1

    add_ca_id_type_attributes(root)

    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass

    destination = Path(output_xml).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=destination.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
        tree.write(tmp, encoding="utf-8", xml_declaration=True)
    temporary.replace(destination)

    print("\n" + "=" * 80)
    print(f"Salvato: {output_xml}")
    print(f"Arricchiti: {enriched_count}")
    print(f"Saltati: {skipped_count}")
    print(f"Errori: {error_count}")
    if warning_count:
        print_red(f"Warning: {warning_count}")
    else:
        print("Warning: 0")


if __name__ == "__main__":
    main()
