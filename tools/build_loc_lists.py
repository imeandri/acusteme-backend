#!/usr/bin/env python3
"""Build the five closed LoC/MARC video vocabularies used in Dati specifici."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "ACUSTEME_profile.xml"
SOURCE_RETRIEVED = "2026-08-28"
MARKER_START = "    <!-- BEGIN generated LoC/MARC controlled lists -->"
MARKER_END = "    <!-- END generated LoC/MARC controlled lists -->"
IFLA_MARKER = "    <!-- BEGIN generated IFLA UNIMARC controlled lists -->"

FIELD_SCHEMES = {
    "broadcaststandard_ME": "mbroadstd",
    "videoplayback_ME": "mplayback",
    "polarity_ME": "mpolarity",
    "aspectration_ME": "maspect",
    "tecnique_ME": "mtechnique",
}

# English labels and identifiers are a pinned local snapshot of the official
# LoC vocabularies. Italian labels are ACUSTEME translations.
TERMS = {
    "mbroadstd": [
        ("hdtv", "HDTV", "HDTV"),
        ("ntsc", "NTSC", "NTSC"),
        ("pal", "PAL", "PAL"),
        ("secam", "SECAM", "SECAM"),
    ],
    "mplayback": [
        ("mix", "mixed", "misto"),
        ("mon", "mono", "mono"),
        ("ste", "stereo", "stereo"),
        ("mul", "surround", "surround"),
    ],
    "mpolarity": [
        ("mix", "mixed", "mista"),
        ("neg", "negative", "negativa"),
        ("pos", "positive", "positiva"),
    ],
    "maspect": [
        ("ana", "anamorphic", "anamorfico"),
        ("full", "full screen", "schermo intero"),
        ("fullfra", "fullframe", "fotogramma pieno"),
        ("letbox", "letterboxed", "letterbox"),
        ("mixed", "mixed aspect", "formato misto"),
        ("nonana", "non-anamorphic", "non anamorfico"),
        ("panscan", "pan and scan", "pan and scan"),
        ("redfra", "reduced frame", "fotogramma ridotto"),
        ("wide", "wide screen", "schermo panoramico"),
    ],
    "mtechnique": [
        ("anim", "animation", "animazione"),
        ("animlive", "animation and live action", "animazione e ripresa dal vivo"),
        ("live", "live action", "ripresa dal vivo"),
        ("other", "other", "altra"),
    ],
}

LIST_SETTINGS = """{i}<settings>
{i}  <setting name="render">select</setting>
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


def xml_text(value: str) -> str:
    return html.escape(value, quote=False)


def field_pattern(code: str) -> re.Pattern[str]:
    return re.compile(
        rf'(?ms)^([ \t]*)<metadataElement code="{re.escape(code)}".*?^\1</metadataElement>'
    )


def list_title(field_block: str, locale: str) -> str:
    match = re.search(
        rf'<label locale="{locale}">\s*<name>(.*?)</name>', field_block, flags=re.DOTALL
    )
    if not match:
        raise ValueError(f"Missing {locale} field label")
    return compact_space(html.unescape(match.group(1)))


def build_list(scheme: str, title_it: str, title_en: str) -> str:
    lines = [
        f'    <list code="loc_{scheme}_LS" hierarchical="0" system="0" vocabulary="1" defaultSort="1">',
        "      <labels>",
        '        <label locale="it_IT">',
        f"          <name>{xml_text(title_it)} (LoC/MARC)</name>",
        "        </label>",
        '        <label locale="en_US">',
        f"          <name>{xml_text(title_en)} (LoC/MARC)</name>",
        "        </label>",
        "      </labels>",
        "      <items>",
    ]
    for rank, (code, label_en, label_it) in enumerate(TERMS[scheme], start=1):
        source_uri = f"http://id.loc.gov/vocabulary/{scheme}/{code}"
        lines.extend(
            [
                f'        <item idno="{code}" enabled="1" default="0" value="{code}" rank="{rank}">',
                "          <labels>",
                '            <label locale="en_US" preferred="1">',
                f"              <name_singular>{xml_text(label_en)}</name_singular>",
                f"              <name_plural>{xml_text(label_en)}</name_plural>",
                f"              <description>LoC/MARC code: {code}</description>",
                "            </label>",
                '            <label locale="it_IT" preferred="1">',
                f"              <name_singular>{xml_text(label_it)}</name_singular>",
                f"              <name_plural>{xml_text(label_it)}</name_plural>",
                f"              <description>Codice LoC/MARC: {code}</description>",
                "            </label>",
                "          </labels>",
                "          <settings>",
                f'            <setting name="source_uri">{source_uri}</setting>',
                '            <setting name="label_source_en">loc</setting>',
                '            <setting name="label_source_it">acusteme</setting>',
                "          </settings>",
                "        </item>",
            ]
        )
    lines.extend(["      </items>", "    </list>"])
    return "\n".join(lines)


def replace_field(text: str, code: str, scheme: str) -> str:
    matches = list(field_pattern(code).finditer(text))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one metadata element {code}, found {len(matches)}")
    match = matches[0]
    block = match.group(0)
    indent = match.group(1)
    opening = re.match(r"[^\n]+", block).group(0)
    replacement_opening = (
        f'{indent}<metadataElement code="{code}" datatype="List" list="loc_{scheme}_LS">'
    )
    block = replacement_opening + block[len(opening) :]
    settings = LIST_SETTINGS.format(i=indent + "  ")
    block, replacements = re.subn(
        r"(?ms)^[ \t]*<settings>.*?^[ \t]*</settings>", settings, block, count=1
    )
    if replacements != 1:
        raise ValueError(f"Could not replace settings for {code}")
    if code == "tecnique_ME":
        block = block.replace(
            "in conformità a IFLA/UNIMARC per proiezioni visive",
            "secondo il vocabolario LoC/MARC per le risorse audiovisive",
        ).replace(
            "in accordance with IFLA/UNIMARC for visual projections",
            "according to the LoC/MARC vocabulary for audiovisual resources",
        )
    return text[: match.start()] + block + text[match.end() :]


def remove_generated_lists(text: str) -> str:
    return re.sub(
        rf"(?ms)^{re.escape(MARKER_START)}\n.*?^{re.escape(MARKER_END)}\n",
        "",
        text,
        count=1,
    )


def build_profile(text: str) -> str:
    original_blocks = {}
    for field in FIELD_SCHEMES:
        match = field_pattern(field).search(text)
        if not match:
            raise ValueError(f"Missing metadata element {field}")
        original_blocks[field] = match.group(0)

    lists = []
    for field, scheme in FIELD_SCHEMES.items():
        lists.append(
            build_list(
                scheme,
                list_title(original_blocks[field], "it_IT"),
                list_title(original_blocks[field], "en_US"),
            )
        )
    generated = MARKER_START + "\n" + "\n".join(lists) + "\n" + MARKER_END + "\n"
    text = remove_generated_lists(text)
    if IFLA_MARKER in text:
        text = text.replace(IFLA_MARKER, generated + IFLA_MARKER, 1)
    elif text.count("  </lists>") == 1:
        text = text.replace("  </lists>", generated + "  </lists>", 1)
    else:
        raise ValueError("Could not locate controlled-list insertion point")
    for field, scheme in FIELD_SCHEMES.items():
        text = replace_field(text, field, scheme)
    return text


def audit_profile(text: str) -> None:
    root = ET.fromstring(text)
    lists = {node.get("code"): node for node in root.find("lists").findall("list")}
    elements = {node.get("code"): node for node in root.iter("metadataElement")}
    count = 0
    for field, scheme in FIELD_SCHEMES.items():
        list_code = f"loc_{scheme}_LS"
        element = elements[field]
        if element.get("datatype") != "List" or element.get("list") != list_code:
            raise ValueError(f"{field} is not connected to {list_code}")
        if any(setting.get("name") == "querySparql" for setting in element.iter("setting")):
            raise ValueError(f"{field} still contains a SPARQL query")
        items = lists[list_code].find("items").findall("item")
        if len(items) != len(TERMS[scheme]):
            raise ValueError(f"Count mismatch for {list_code}")
        for item in items:
            locales = {label.get("locale") for label in item.find("labels").findall("label")}
            if not {"en_US", "it_IT"}.issubset(locales):
                raise ValueError(f"Missing bilingual labels for {list_code}:{item.get('idno')}")
        count += len(items)
    print(f"OK: {len(FIELD_SCHEMES)} LoC fields, {count} controlled terms")


def official_terms(scheme: str) -> dict[str, str]:
    request = urllib.request.Request(
        f"https://id.loc.gov/vocabulary/{scheme}.json",
        headers={"Accept": "application/json", "User-Agent": "ACUSTEME-profile-builder/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.load(response)
    prefix = f"http://id.loc.gov/vocabulary/{scheme}/"
    label_property = "http://www.loc.gov/mads/rdf/v1#authoritativeLabel"
    return {
        node["@id"][len(prefix) :]: compact_space(node[label_property][0]["@value"])
        for node in data
        if node.get("@id", "").startswith(prefix) and node.get(label_property)
    }


def check_source() -> None:
    for scheme, terms in TERMS.items():
        expected = {code: label_en for code, label_en, _ in terms}
        actual = official_terms(scheme)
        if actual != expected:
            raise ValueError(f"Official LoC vocabulary changed for {scheme}: {actual!r}")
    print(f"OK: embedded LoC snapshot still matches the official source ({SOURCE_RETRIEVED})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Verify generated content")
    parser.add_argument("--audit-only", action="store_true", help="Audit wiring and counts")
    parser.add_argument("--check-source", action="store_true", help="Compare against live LoC JSON")
    args = parser.parse_args()
    current = PROFILE.read_text(encoding="utf-8")
    if args.check_source:
        check_source()
        if not args.check and not args.audit_only:
            return 0
    if args.audit_only:
        audit_profile(current)
        return 0
    generated = build_profile(current)
    audit_profile(generated)
    if args.check:
        if generated != current:
            raise SystemExit("ERROR: generated LoC lists are stale; run tools/build_loc_lists.py")
        print("OK: LoC lists match the embedded authoritative snapshot")
        return 0
    PROFILE.write_text(generated, encoding="utf-8")
    print(f"Generated {PROFILE} with LoC snapshot retrieved {SOURCE_RETRIEVED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
