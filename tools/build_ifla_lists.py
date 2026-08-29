#!/usr/bin/env python3
"""Build the closed IFLA UNIMARC lists used by the Dati specifici fields.

The IFLA source is pinned to a Git commit. Official IFLA labels take priority;
reviewed ACUSTEME labels and the checked-in Wikidata snapshot fill gaps. Every
term must resolve to an explicit semantic English/Italian pair: generation
fails instead of copying an arbitrary label from the other locale.
"""

from __future__ import annotations

import argparse
import html
import io
import json
from pathlib import Path
import re
import tarfile
import urllib.request
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "ACUSTEME_profile.xml"
WIKIDATA_LABELS = ROOT / "tools" / "ifla_wikidata_labels.json"
ACUSTEME_LABELS = ROOT / "tools" / "ifla_acusteme_labels.json"
IFLA_REF = "65fb8630298498bf03c4ce567dfd1746fcf6c0a9"
IFLA_TARBALL = f"https://github.com/iflastandards/unimarc/archive/{IFLA_REF}.tar.gz"
MARKER_START = "    <!-- BEGIN generated IFLA UNIMARC controlled lists -->"
MARKER_END = "    <!-- END generated IFLA UNIMARC controlled lists -->"


FIELD_SCHEMES = {
    # Sound recordings
    "audio_Accompanyingmaterial_ME": "soundatm",
    "groove_width_ME": "soundgrw",
    "kindofcutting_ME": "soundcut",
    "recordingtechnique_ME": "soundtec",
    "specrepchar_ME": "soundrep",
    "speed_ME": "soundspe",
    "tape_config_ME": "soundtac",
    "audiotapewidth_ME": "soundtaw",
    "typeofrec_ME": "soundtyp",
    # Cartographic materials
    "sensoraltitute_ME": "altos",
    "sensorattitute_ME": "attos",
    "satellitecategory_ME": "satcat",
    "character_ME": "cartcha",
    "colourindicator_ME": "cartcol",
    "formofitem_ME": "cartfor",
    "mapprojection_ME": "cartpro",
    "nameofsatellite_ME": "satname",
    "planet_ME": "planet",
    "positionofplatform_ME": "cartpop",
    "presentationtechnique_ME": "cartprt",
    "recordingtecniqueRSI_ME": "cartret",
    "relief_ME": "cartrel",
    "typeofscale_ME": "carttos",
    # Electronic resources, realia, graphics, musical incipits, video
    "typeelecres_ME": "ter",
    "realia_spec_mat_des_ME": "3dsmd",
    "functionaldesignation_ME": "graphicsfd",
    "spec_mate_des_ME": "graphicssmd",
    "tecnique_prints_ME": "graphicstp",
    "techdrawingpaints_ME": "graphicstd",
    "mus_forminc_ME": "fom",
    "tonalityinc_ME": "key",
    "Accompanyingmaterial_ME": "visacc",
    "formofrelease_videorec_ME": "visfov",
    "formofrelease_motionpict_ME": "visfor",
    "Colour_ME": "viscol",
    "mediaforsound_ME": "vismfs",
}

EXPECTED_PUBLISHED = {
    "soundatm": 15,
    "soundgrw": 5,
    "soundcut": 4,
    "soundtec": 5,
    "soundrep": 11,
    "soundspe": 19,
    "soundtac": 11,
    "soundtaw": 9,
    "soundtyp": 11,
    "altos": 3,
    "attos": 3,
    "satcat": 3,
    "cartcha": 3,
    "cartcol": 2,
    "cartfor": 11,
    "cartpro": 47,
    "satname": 14,
    "planet": 10,
    "cartpop": 3,
    "cartprt": 22,
    "cartret": 10,
    "cartrel": 13,
    "carttos": 3,
    "ter": 13,
    "3dsmd": 34,
    "graphicsfd": 18,
    "graphicssmd": 11,
    "graphicstp": 29,
    "graphicstd": 30,
    "fom": 607,
    "key": 31,
    "visacc": 9,
    "visfov": 7,
    "visfor": 13,
    "viscol": 5,
    "vismfs": 12,
}


LIST_SETTINGS = """{i}<settings>
{i}  <setting name="render">{renderer}</setting>
{i}  <setting name="listWidth">40</setting>
{i}  <setting name="listHeight">200px</setting>
{i}  <setting name="doesNotTakeLocale">1</setting>
{i}  <setting name="singleValuePerLocale">0</setting>
{i}  <setting name="requireValue">0</setting>
{i}  <setting name="allowDuplicateValues">0</setting>
{i}  <setting name="raiseErrorOnDuplicateValue">0</setting>
{i}  <setting name="implicitNullOption">0</setting>
{i}  <setting name="nullOptionText">Not set</setting>
{i}  <setting name="useDefaultWhenNull">0</setting>
{i}  <setting name="canBeUsedInSort">1</setting>
{i}  <setting name="auto_shrink">0</setting>
{i}  <setting name="maxColumns">3</setting>
{i}  <setting name="canBeUsedInSearchForm">1</setting>
{i}  <setting name="canBeUsedInDisplay">1</setting>
{i}  <setting name="canMakePDF">0</setting>
{i}  <setting name="canMakePDFForValue">0</setting>
{i}  <setting name="displayDelimiter">; </setting>
{i}  <setting name="minimizeExistingValues">0</setting>
{i}  <setting name="deferHierarchyLoad">0</setting>
{i}  <setting name="separateDisabledValues">0</setting>
{i}  <setting name="includeSourceData">0</setting>
{i}  <setting name="displayTemplate" />
{i}  <setting name="restrictToTypes" />
{i}  <setting name="currentSelectionDisplayFormat" />
{i}</settings>"""


def compact_space(value: object) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def localized_value(value: object, language: str) -> str:
    if isinstance(value, str):
        return html.unescape(compact_space(value))
    if not isinstance(value, dict):
        return ""
    return html.unescape(compact_space(value.get(language)))


def concept_id(uri: str) -> str:
    value = uri.rsplit("#", 1)[-1] if "#" in uri else uri.rstrip("/").rsplit("/", 1)[-1]
    if not re.fullmatch(r"[\w]+", value, flags=re.UNICODE):
        raise ValueError(f"IFLA concept URI cannot be used as a list idno: {uri}")
    return value


def load_schemes(ifla_dir: Path | None) -> dict[str, dict]:
    requested = list(dict.fromkeys(FIELD_SCHEMES.values()))
    if ifla_dir:
        return {
            scheme: json.loads((ifla_dir / f"{scheme}.jsonld").read_text(encoding="utf-8"))
            for scheme in requested
        }

    request = urllib.request.Request(
        IFLA_TARBALL,
        headers={
            "User-Agent": "ACUSTEME-profile-builder/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
    except OSError as error:
        raise RuntimeError(f"Cannot fetch pinned IFLA archive: {error}") from error

    schemes = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        members = {
            Path(member.name).name: member
            for member in archive.getmembers()
            if "/jsonld/ns/unimarc/terms/" in member.name
        }
        for scheme in requested:
            member = members.get(f"{scheme}.jsonld")
            if member is None:
                raise RuntimeError(f"Pinned IFLA archive is missing {scheme}.jsonld")
            stream = archive.extractfile(member)
            if stream is None:
                raise RuntimeError(f"Cannot read {scheme}.jsonld from pinned IFLA archive")
            schemes[scheme] = json.loads(stream.read().decode("utf-8"))
    return schemes


def select_label(
    scheme: str,
    item_id: str,
    pref_labels: dict,
    target: str,
    wikidata: dict,
    acusteme: dict,
) -> tuple[str, str]:
    official = localized_value(pref_labels, target)
    if official:
        return official, "ifla"
    reviewed = acusteme.get(f"{scheme}:{item_id}", {}).get(target)
    if reviewed:
        return compact_space(reviewed), "acusteme"
    supplement = wikidata.get(f"{scheme}:{item_id}", {}).get(target)
    if supplement:
        return compact_space(supplement), "wikidata"
    raise ValueError(
        f"Missing required semantic {target} label for IFLA term {scheme}:{item_id}"
    )


def list_title_from_field(field_block: str, locale: str) -> str:
    match = re.search(
        rf'<label locale="{locale}">\s*<name>(.*?)</name>', field_block, flags=re.DOTALL
    )
    if not match:
        raise ValueError(f"Missing {locale} field label")
    return compact_space(html.unescape(match.group(1)))


def xml_text(value: str) -> str:
    return html.escape(value, quote=False)


def build_list(
    scheme: str,
    data: dict,
    title_it: str,
    title_en: str,
    wikidata: dict,
    acusteme: dict,
) -> tuple[str, dict[str, int]]:
    graph = data.get("@graph", [])
    concepts = [node for node in graph if node.get("@type") == "Concept"]
    hierarchy = "1" if scheme == "fom" else "0"
    lines = [
        f'    <list code="ifla_{scheme}_LS" hierarchical="{hierarchy}" system="0" vocabulary="1" defaultSort="1">',
        "      <labels>",
        '        <label locale="it_IT">',
        f"          <name>{xml_text(title_it)} (IFLA UNIMARC)</name>",
        "        </label>",
        '        <label locale="en_US">',
        f"          <name>{xml_text(title_en)} (IFLA UNIMARC)</name>",
        "        </label>",
        "      </labels>",
        "      <items>",
    ]
    stats = {
        "published": 0,
        "deprecated": 0,
        "ifla_en": 0,
        "ifla_it": 0,
        "wikidata_en": 0,
        "wikidata_it": 0,
        "acusteme_en": 0,
        "acusteme_it": 0,
    }
    seen: set[str] = set()
    for rank, concept in enumerate(concepts, start=1):
        uri = compact_space(concept.get("@id"))
        item_id = concept_id(uri)
        if item_id in seen:
            raise ValueError(f"Duplicate IFLA concept id {scheme}:{item_id}")
        seen.add(item_id)
        notation = localized_value(concept.get("notation", {}), "en") or item_id
        status = compact_space(concept.get("status"))
        enabled = "1" if status == "Published" else "0"
        stats["published" if enabled == "1" else "deprecated"] += 1
        label_en, source_en = select_label(
            scheme, item_id, concept.get("prefLabel", {}), "en", wikidata, acusteme
        )
        label_it, source_it = select_label(
            scheme, item_id, concept.get("prefLabel", {}), "it", wikidata, acusteme
        )
        stats[f"{source_en}_en"] += 1
        stats[f"{source_it}_it"] += 1
        lines.extend(
            [
                f'        <item idno="{xml_text(item_id)}" enabled="{enabled}" default="0" value="{html.escape(notation, quote=True)}" rank="{rank}">',
                "          <labels>",
                '            <label locale="en_US" preferred="1">',
                f"              <name_singular>{xml_text(label_en)}</name_singular>",
                f"              <name_plural>{xml_text(label_en)}</name_plural>",
                f"              <description>IFLA UNIMARC code: {xml_text(notation)}</description>",
                "            </label>",
                '            <label locale="it_IT" preferred="1">',
                f"              <name_singular>{xml_text(label_it)}</name_singular>",
                f"              <name_plural>{xml_text(label_it)}</name_plural>",
                f"              <description>Codice IFLA UNIMARC: {xml_text(notation)}</description>",
                "            </label>",
                "          </labels>",
                "          <settings>",
                f'            <setting name="source_uri">{xml_text(uri)}</setting>',
                f'            <setting name="label_source_en">{source_en}</setting>',
                f'            <setting name="label_source_it">{source_it}</setting>',
                "          </settings>",
                "        </item>",
            ]
        )
    lines.extend(["      </items>", "    </list>"])
    return "\n".join(lines), stats


def field_pattern(code: str) -> re.Pattern[str]:
    return re.compile(
        rf'(?ms)^([ \t]*)<metadataElement code="{re.escape(code)}".*?^\1</metadataElement>'
    )


def replace_field(text: str, code: str, scheme: str) -> str:
    pattern = field_pattern(code)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one metadata element {code}, found {len(matches)}")
    block = matches[0].group(0)
    indent = matches[0].group(1)
    opening = re.match(r"[^\n]+", block).group(0)
    replacement_opening = (
        f'{indent}<metadataElement code="{code}" datatype="List" list="ifla_{scheme}_LS">'
    )
    block = replacement_opening + block[len(opening) :]
    renderer = "horiz_hierbrowser_with_search" if scheme == "fom" else "select"
    settings = LIST_SETTINGS.format(i=indent + "  ", renderer=renderer)
    block, replacements = re.subn(
        r"(?ms)^[ \t]*<settings>.*?^[ \t]*</settings>",
        settings,
        block,
        count=1,
    )
    if replacements != 1:
        raise ValueError(f"Could not replace settings for {code}")
    block = block.replace("Campo Linked Data.", "Lista controllata IFLA.")
    block = block.replace("Linked Data field.", "IFLA controlled list.")
    block = block.replace(
        "Campo Linked Data: viene codificata secondo terminologia standardizzata mappata su Wikidata o vocabolari IFLA.",
        "Lista controllata: viene codificata secondo il vocabolario IFLA UNIMARC.",
    )
    block = block.replace(
        "Linked Data field: coded according to standardized terminology mapped to Wikidata or IFLA vocabularies.",
        "Controlled list: coded according to the IFLA UNIMARC vocabulary.",
    )
    return text[: matches[0].start()] + block + text[matches[0].end() :]


def remove_generated_lists(text: str) -> str:
    return re.sub(
        rf"(?ms)^{re.escape(MARKER_START)}\n.*?^{re.escape(MARKER_END)}\n",
        "",
        text,
        count=1,
    )


def build_profile(
    text: str, schemes: dict[str, dict], wikidata: dict, acusteme: dict
) -> tuple[str, dict]:
    original_blocks = {}
    for field, scheme in FIELD_SCHEMES.items():
        match = field_pattern(field).search(text)
        if not match:
            raise ValueError(f"Missing metadata element {field}")
        original_blocks[field] = match.group(0)

    generated = []
    stats = {}
    for field, scheme in FIELD_SCHEMES.items():
        title_it = list_title_from_field(original_blocks[field], "it_IT")
        title_en = list_title_from_field(original_blocks[field], "en_US")
        list_xml, list_stats = build_list(
            scheme, schemes[scheme], title_it, title_en, wikidata, acusteme
        )
        generated.append(list_xml)
        stats[scheme] = list_stats

    text = remove_generated_lists(text)
    insertion = MARKER_START + "\n" + "\n".join(generated) + "\n" + MARKER_END + "\n"
    if text.count("  </lists>") != 1:
        raise ValueError("Expected exactly one closing lists element")
    text = text.replace("  </lists>", insertion + "  </lists>", 1)
    for field, scheme in FIELD_SCHEMES.items():
        text = replace_field(text, field, scheme)
    return text, stats


def audit_profile(text: str, stats: dict) -> None:
    root = ET.fromstring(text)
    lists = {node.get("code"): node for node in root.find("lists").findall("list")}
    elements = {node.get("code"): node for node in root.iter("metadataElement")}
    published_total = 0
    deprecated_total = 0
    for field, scheme in FIELD_SCHEMES.items():
        list_code = f"ifla_{scheme}_LS"
        element = elements[field]
        if element.get("datatype") != "List" or element.get("list") != list_code:
            raise ValueError(f"{field} is not connected to {list_code}")
        if any(setting.get("name") == "querySparql" for setting in element.iter("setting")):
            raise ValueError(f"{field} still contains a SPARQL query")
        if list_code not in lists:
            raise ValueError(f"Missing list {list_code}")
        items = lists[list_code].find("items").findall("item")
        enabled = sum(item.get("enabled") == "1" for item in items)
        disabled = sum(item.get("enabled") == "0" for item in items)
        if enabled != stats[scheme]["published"] or disabled != stats[scheme]["deprecated"]:
            raise ValueError(f"Count mismatch for {list_code}")
        for item in items:
            labels = {label.get("locale"): label for label in item.find("labels").findall("label")}
            if labels.get("en_US") is None or labels.get("it_IT") is None:
                raise ValueError(f"Missing bilingual labels for {list_code}:{item.get('idno')}")
            for locale in ("en_US", "it_IT"):
                if not compact_space(labels[locale].findtext("name_singular")):
                    raise ValueError(f"Empty {locale} label for {list_code}:{item.get('idno')}")
            sources = {
                setting.get("name"): compact_space(setting.text)
                for setting in item.findall("./settings/setting")
            }
            for language in ("en", "it"):
                source = sources.get(f"label_source_{language}")
                if source not in {"ifla", "wikidata", "acusteme"}:
                    raise ValueError(
                        f"Invalid {language} label source for {list_code}:{item.get('idno')}: {source}"
                    )
        published_total += enabled
        deprecated_total += disabled
    if len({f"ifla_{scheme}_LS" for scheme in FIELD_SCHEMES.values()}) != len(FIELD_SCHEMES):
        raise ValueError("IFLA scheme mapping is not one-to-one")
    print(
        f"OK: {len(FIELD_SCHEMES)} IFLA fields, {published_total} published terms, "
        f"{deprecated_total} deprecated term(s)"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ifla-dir",
        type=Path,
        help="Directory containing the pinned IFLA term JSON-LD files",
    )
    parser.add_argument("--check", action="store_true", help="Audit without writing")
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Audit field wiring and pinned counts without fetching source data",
    )
    args = parser.parse_args()
    if args.ifla_dir and not args.ifla_dir.is_dir():
        parser.error(f"not a directory: {args.ifla_dir}")

    current = PROFILE.read_text(encoding="utf-8")
    if args.audit_only:
        expected_stats = {
            scheme: {
                "published": count,
                "deprecated": 1 if scheme == "visfor" else 0,
            }
            for scheme, count in EXPECTED_PUBLISHED.items()
        }
        audit_profile(current, expected_stats)
        return 0

    supplements = json.loads(WIKIDATA_LABELS.read_text(encoding="utf-8"))["entries"]
    acusteme = json.loads(ACUSTEME_LABELS.read_text(encoding="utf-8"))["entries"]
    schemes = load_schemes(args.ifla_dir)
    generated, stats = build_profile(current, schemes, supplements, acusteme)
    audit_profile(generated, stats)
    if args.check:
        if generated != current:
            raise SystemExit("ERROR: generated IFLA lists are stale; run tools/build_ifla_lists.py")
        print(f"OK: IFLA lists match pinned revision {IFLA_REF}")
        return 0
    PROFILE.write_text(generated, encoding="utf-8")
    print(f"Generated {PROFILE} from IFLA revision {IFLA_REF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
