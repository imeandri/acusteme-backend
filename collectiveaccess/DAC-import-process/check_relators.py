#!/usr/bin/env python3
"""Valida responsabilità Excel e codici legacy contro il profilo CollectiveAccess."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from dac_common import extract_profile_relators, normalize_legacy_code, parse_responsibility, read_excel_sheets, split_responsibilities, validate_sheet, write_validation_reports


def audit(excel_path: str, profile_path: str, selected_sheets: list[str] | None = None):
    profile_records = extract_profile_relators(profile_path)
    legacy_map: dict[str, set[str]] = defaultdict(set)
    for item in profile_records:
        if item["legacy_code"] and not item.get("has_children"):
            legacy_map[item["legacy_code"]].add(item["code"])

    issues = []
    used_codes = Counter()
    for sheet, df, duplicates in read_excel_sheets(excel_path, selected_sheets):
        issues.extend(validate_sheet(sheet, df, duplicates))
        if "Responsabilità" not in df.columns:
            continue
        for idx, value in df["Responsabilità"].items():
            for part in split_responsibilities(value):
                parsed = parse_responsibility(part)
                if not parsed.role:
                    continue
                code = normalize_legacy_code(parsed.role.split()[0])
                used_codes[code] += 1
                if code not in legacy_map:
                    issues.append({"sheet": sheet, "row": int(idx) + 2, "field": "Responsabilità",
                                   "severity": "error", "message": f"codice assente dal profilo: {code}",
                                   "value": part})

    duplicates = {code: sorted(values) for code, values in legacy_map.items() if len(values) > 1}
    for code, values in duplicates.items():
        issues.append({"sheet": "<profile>", "row": 0, "field": "legacy_code", "severity": "error",
                       "message": f"codice legacy ambiguo {code}: {', '.join(values)}"})

    return {
        "excel": str(Path(excel_path)),
        "profile": str(Path(profile_path)),
        "profile_relationship_types": len(profile_records),
        "profile_legacy_codes": len(legacy_map),
        "used_legacy_codes": dict(sorted(used_codes.items())),
        "unused_profile_codes": sorted(set(legacy_map) - set(used_codes)),
        "ambiguous_profile_codes": duplicates,
        "issues": issues,
        "error_count": sum(1 for issue in issues if issue.get("severity") == "error"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("excel", nargs="?", default="RAW_DATA/ada1.xlsx")
    parser.add_argument("profile", nargs="?", default="ACUSTEME_profile.xml")
    parser.add_argument("--sheet", action="append", dest="sheets")
    parser.add_argument("--output", default="report_relators_check.json")
    parser.add_argument("--html", help="Percorso report HTML; default: stesso nome del JSON")
    args = parser.parse_args()
    result = audit(args.excel, args.profile, args.sheets)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _, html_output = write_validation_reports(
        result["issues"], args.output, args.html,
        title=f"Controllo relator — {Path(args.excel).name}",
        write_json=False,
    )
    print(f"Relator nel profilo: {result['profile_legacy_codes']}")
    print(f"Codici usati: {len(result['used_legacy_codes'])}")
    print(f"Errori: {result['error_count']}")
    print(f"Report: {args.output}")
    print(f"Report HTML: {html_output}")
    raise SystemExit(1 if result["error_count"] else 0)


if __name__ == "__main__":
    main()
