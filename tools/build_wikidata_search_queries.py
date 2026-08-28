#!/usr/bin/env python3
"""Normalize the generic Wikidata searches to one result row per entity."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "ACUSTEME_profile.xml"

FIELDS = (
    "videofile_extension_ME",
    "videomime_type_ME",
    "videootlformat_ME",
    "videocodec_ME",
    "videootlcodec_ME",
    "videofreq_ME",
    "videodepth_ME",
)

QUERY = """SELECT DISTINCT ?item ?itemLabel ?itemDescription ?lang
WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:endpoint "www.wikidata.org";
                    wikibase:api "EntitySearch";
                    mwapi:search "***PLACEHOLDER***";
                    mwapi:language "it".
    ?item wikibase:apiOutputItem mwapi:item.
    ?num wikibase:apiOrdinal true.
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "it, en". }
  BIND(LANG(?itemLabel) AS ?lang)
}
ORDER BY ?num"""


def field_pattern(code: str) -> re.Pattern[str]:
    return re.compile(
        rf'(?ms)^([ \t]*)<metadataElement code="{re.escape(code)}".*?^\1</metadataElement>'
    )


def transform(text: str) -> str:
    for code in FIELDS:
        matches = list(field_pattern(code).finditer(text))
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one metadata element {code}, found {len(matches)}")
        match = matches[0]
        block = match.group(0)
        block, replacements = re.subn(
            r'(?ms)(<setting name="querySparql">).*?(</setting>)',
            lambda found: found.group(1) + QUERY + found.group(2),
            block,
            count=1,
        )
        if replacements != 1:
            raise ValueError(f"Could not replace querySparql for {code}")
        text = text[: match.start()] + block + text[match.end() :]
    return text


def audit(text: str) -> None:
    for code in FIELDS:
        match = field_pattern(code).search(text)
        if not match:
            raise ValueError(f"Missing metadata element {code}")
        query_match = re.search(
            r'(?ms)<setting name="querySparql">(.*?)</setting>', match.group(0)
        )
        if not query_match or query_match.group(1) != QUERY:
            raise ValueError(f"Non-canonical generic Wikidata query in {code}")
    print(f"OK: {len(FIELDS)} generic Wikidata searches return one row per entity")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Verify without writing")
    args = parser.parse_args()
    current = PROFILE.read_text(encoding="utf-8")
    generated = transform(current)
    audit(generated)
    if args.check:
        if generated != current:
            raise SystemExit(
                "ERROR: generic Wikidata queries are stale; "
                "run tools/build_wikidata_search_queries.py"
            )
        return 0
    PROFILE.write_text(generated, encoding="utf-8")
    print(f"Updated {PROFILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
