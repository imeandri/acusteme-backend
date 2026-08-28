"""Independent integrity audit for generated ACUSTEME documentation."""

from __future__ import annotations

import argparse
from collections import Counter
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote

from rdflib.plugins.sparql.parser import parseQuery

from extractor_auto2 import (
    ALLOWED_UI_CODES,
    DEFAULT_XML_SOURCE,
    LANGUAGES,
    build_documentation_pages,
    list_placements,
    load_xml_profile,
    script_dir,
)
from sparql_query_tools import neutralize_placeholder_regexes
from wikijs_manual_regions import parse_manual_regions


CODE_RE = re.compile(r'<code class="language-sparql">(.*?)</code>', re.DOTALL)
QUERY_LINK_RE = re.compile(
    r'href="https://query\.wikidata\.org/embed\.html#([^"]*)"'
)


class _RenderedCodeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_query_code = False
        self.current = []
        self.queries = []
        self.nested_tags = []

    def handle_starttag(self, tag, attrs):
        if self.in_query_code:
            self.nested_tags.append(tag)
        if tag == "code" and ("class", "language-sparql") in attrs:
            self.in_query_code = True
            self.current = []

    def handle_endtag(self, tag):
        if tag == "code" and self.in_query_code:
            self.queries.append("".join(self.current))
            self.in_query_code = False
        elif self.in_query_code:
            self.nested_tags.append("/" + tag)

    def handle_data(self, data):
        if self.in_query_code:
            self.current.append(data)


def _query_code_unescaped(document: str) -> list[str]:
    return [unescape(query) for query in CODE_RE.findall(document)]


def _normalize_query_code_markup(document: str) -> str:
    return CODE_RE.sub(lambda match: unescape(match.group(0)), document)


def _structure_counts(document: str, lang) -> dict[str, int]:
    return {
        "headings": len(re.findall(r'<h[1-5] class="toc-header"', document)),
        "datatype_blocks": document.count("<strong>Datatype:</strong>"),
        "element_code_blocks": document.count("<strong>CA element code:</strong>"),
        "required_blocks": document.count(
            f"<strong>{lang.required_label}:</strong>"
        ),
        "repeatability_blocks": document.count(
            f"<strong>{lang.repeat_label}:</strong>"
        ),
        "quicktips": document.count("<strong>Quicktip:</strong>"),
        "query_buttons": document.count('class="query-toggle-button"'),
        "query_code_blocks": document.count('class="language-sparql"'),
        "query_links": len(QUERY_LINK_RE.findall(document)),
        "vocabulary_blocks": document.count(
            f"<strong>{lang.vocabulary_label}:</strong>"
        ),
        "manual_regions": len(parse_manual_regions(document)),
    }


def _expected_structure(elements, lang) -> dict[str, int]:
    visible = [element for element in elements if element.numerale.count(".") > 0]
    return {
        "headings": len(visible),
        "datatype_blocks": len(visible),
        "element_code_blocks": len(visible),
        "required_blocks": sum(
            element.required == lang.required_yes for element in visible
        ),
        "repeatability_blocks": sum(
            element.numerale.count(".") == 1
            and element.repeatability != lang.repeat_no
            for element in visible
        ),
        "quicktips": sum(element.description != "N/A" for element in visible),
        "query_buttons": sum(element.sparql_query != "N/A" for element in visible),
        "query_code_blocks": sum(
            element.sparql_query != "N/A" for element in visible
        ),
        "query_links": sum(element.sparql_query != "N/A" for element in visible),
        "vocabulary_blocks": sum(element.vocabulary != "N/A" for element in visible),
        "manual_regions": len(visible),
    }


def _syntax_error(query: str) -> str | None:
    try:
        parseQuery(query)
    except Exception as exc:  # rdflib exposes several parser exception types
        return f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
    return None


def audit_documentation(
    xml_source: str = DEFAULT_XML_SOURCE,
    previous_root: Path | None = None,
) -> dict[str, object]:
    root = load_xml_profile(xml_source).getroot()
    pages = build_documentation_pages(root, ("it", "en"), ALLOWED_UI_CODES)
    page_issues = []
    previous_format_differences = []
    previous_structure_differences = []
    previous_dom_issues = []
    query_occurrences = []

    for page in pages:
        lang = LANGUAGES[page.language]
        elements, _, _, _ = list_placements(
            root,
            page.ui_code,
            page.screen_index,
            lang,
            False,
        )
        expected_queries = [
            element.sparql_query
            for element in elements
            if element.sparql_query != "N/A"
        ]
        query_occurrences.extend(expected_queries)

        raw_queries = _query_code_unescaped(page.content)
        links = [unquote(fragment) for fragment in QUERY_LINK_RE.findall(page.content)]
        runnable_queries = [
            neutralize_placeholder_regexes(query) for query in expected_queries
        ]
        parser = _RenderedCodeParser()
        parser.feed(page.content)

        expected_structure = _expected_structure(elements, lang)
        actual_structure = _structure_counts(page.content, lang)
        expected_region_keys = [element.manual_region_key for element in elements]
        actual_region_keys = list(parse_manual_regions(page.content))

        checks = {
            "source_to_code_exact": raw_queries == expected_queries,
            "source_to_link_exact": links == runnable_queries,
            "rendered_code_exact": parser.queries == expected_queries,
            "no_nested_tags_in_query_code": not parser.nested_tags,
            "structure_exact": actual_structure == expected_structure,
            "manual_region_keys_exact": actual_region_keys == expected_region_keys,
        }
        if not all(checks.values()):
            page_issues.append(
                {
                    "page": page.relative_output_path.as_posix(),
                    "checks": checks,
                    "nested_query_tags": parser.nested_tags,
                    "expected_structure": expected_structure,
                    "actual_structure": actual_structure,
                }
            )

        if previous_root is not None:
            previous_path = previous_root / page.relative_output_path
            if previous_path.exists():
                previous = previous_path.read_text(encoding="utf-8")
                if (
                    _normalize_query_code_markup(previous)
                    != _normalize_query_code_markup(page.content)
                ):
                    previous_format_differences.append(
                        page.relative_output_path.as_posix()
                    )
                if _structure_counts(previous, lang) != actual_structure:
                    previous_structure_differences.append(
                        page.relative_output_path.as_posix()
                    )
                previous_parser = _RenderedCodeParser()
                previous_parser.feed(previous)
                if previous_parser.queries != expected_queries or previous_parser.nested_tags:
                    previous_dom_issues.append(page.relative_output_path.as_posix())

    unique_queries = list(dict.fromkeys(query_occurrences))
    source_syntax_errors = []
    runnable_syntax_errors = []
    for index, query in enumerate(unique_queries):
        source_error = _syntax_error(query)
        runnable = neutralize_placeholder_regexes(query)
        runnable_error = _syntax_error(runnable)
        if source_error:
            source_syntax_errors.append({"query_index": index, "error": source_error})
        if runnable_error:
            runnable_syntax_errors.append(
                {"query_index": index, "error": runnable_error}
            )

    query_counts = Counter(query_occurrences)
    summary = {
        "pages": len(pages),
        "query_occurrences": len(query_occurrences),
        "unique_queries": len(unique_queries),
        "queries_with_placeholder": sum(
            "PLACEHOLDER" in query for query in unique_queries
        ),
        "most_reused_query_occurrences": max(query_counts.values(), default=0),
        "source_syntax_errors": len(source_syntax_errors),
        "runnable_syntax_errors": len(runnable_syntax_errors),
        "page_integrity_issues": len(page_issues),
        "previous_format_differences": len(previous_format_differences),
        "previous_structure_differences": len(previous_structure_differences),
        "previous_dom_query_issues": len(previous_dom_issues),
        "passed": not (
            source_syntax_errors
            or runnable_syntax_errors
            or page_issues
            or previous_format_differences
            or previous_structure_differences
        ),
    }
    return {
        "summary": summary,
        "source_syntax_errors": source_syntax_errors,
        "runnable_syntax_errors": runnable_syntax_errors,
        "page_issues": page_issues,
        "previous_format_differences": previous_format_differences,
        "previous_structure_differences": previous_structure_differences,
        "previous_dom_query_issues": previous_dom_issues,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", default=DEFAULT_XML_SOURCE)
    parser.add_argument(
        "--previous-root",
        help=(
            "Cartella di una generazione precedente da confrontare. Se omessa, "
            "l'audit controlla soltanto il nuovo output generato in memoria."
        ),
    )
    parser.add_argument("--report")
    args = parser.parse_args(argv)

    previous_root = Path(args.previous_root) if args.previous_root else None
    report = audit_documentation(args.xml, previous_root)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
