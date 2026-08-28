"""Safe incremental synchronization of ACUSTEME documentation to Wiki.js."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Literal

from extractor_auto2 import (
    ALLOWED_UI_CODES,
    DEFAULT_XML_SOURCE,
    GeneratedDocumentationPage,
    build_documentation_pages,
    load_xml_profile,
    parse_languages,
    script_dir,
)
from wikijs_graphql import WikiJsClient, WikiPage, WikiPageDraft
from wikijs_manual_regions import (
    ManualRegionError,
    content_hash,
    legacy_placeholder_projection,
    managed_hash,
    merge_manual_regions,
    parse_manual_regions,
    plan_three_way_sync,
)
from wikijs_sync_state import StateRecord, SyncStateError, SyncStateStore


DEFAULT_ENDPOINT = "https://wiki.acusteme.org/graphql"
DEFAULT_STATE_DIRECTORY = script_dir / ".wikijs-sync"


@dataclass(frozen=True)
class SyncDecision:
    action: Literal["create", "update", "unchanged", "conflict"]
    generated: GeneratedDocumentationPage
    remote: WikiPage | None
    target_content: str | None
    reasons: tuple[str, ...] = ()
    bootstrap: bool = False

    def report(self) -> dict[str, object]:
        return {
            "locale": self.generated.language,
            "path": self.generated.wiki_path,
            "title": self.generated.title,
            "action": self.action,
            "bootstrap": self.bootstrap,
            "reasons": list(self.reasons),
            "generated_hash": content_hash(self.generated.content),
            "remote_hash": content_hash(self.remote.content) if self.remote else None,
        }


def audit_generated_pages(
    pages: list[GeneratedDocumentationPage],
    existing_root: Path | None = None,
) -> dict[str, object]:
    seen = set()
    duplicate_pages = []
    region_count = 0
    missing_existing = []
    legacy_differences = []
    existing_formats = {"legacy": 0, "protected": 0}

    for page in pages:
        page_key = (page.language, page.wiki_path)
        if page_key in seen:
            duplicate_pages.append(f"{page.language}:{page.wiki_path}")
        seen.add(page_key)

        regions = parse_manual_regions(page.content)
        region_count += len(regions)
        legacy = legacy_placeholder_projection(page.content)

        if existing_root is not None:
            existing_path = existing_root / page.relative_output_path
            if not existing_path.exists():
                missing_existing.append(page.relative_output_path.as_posix())
            else:
                existing_content = existing_path.read_text(encoding="utf-8")
                if existing_content == page.content:
                    existing_formats["protected"] += 1
                elif existing_content == legacy:
                    existing_formats["legacy"] += 1
                else:
                    legacy_differences.append(page.relative_output_path.as_posix())

    return {
        "pages": len(pages),
        "protected_regions": region_count,
        "duplicate_pages": duplicate_pages,
        "missing_existing_files": missing_existing,
        "legacy_differences": legacy_differences,
        "existing_formats": existing_formats,
        "local_regression_clean": not (
            duplicate_pages or missing_existing or legacy_differences
        ),
    }


def plan_page(
    generated: GeneratedDocumentationPage,
    remote: WikiPage | None,
    state: SyncStateStore,
    trusted_legacy_content: str | None = None,
) -> SyncDecision:
    record = state.get_record(generated.language, generated.wiki_path)

    if remote is None:
        if record is not None:
            return SyncDecision(
                "conflict",
                generated,
                None,
                None,
                ("The previously synchronized remote page is now missing.",),
            )
        return SyncDecision("create", generated, None, generated.content)

    if remote.editor != "code":
        return SyncDecision(
            "conflict",
            generated,
            remote,
            None,
            (f"Remote editor is {remote.editor!r}, expected raw HTML editor 'code'.",),
        )

    if record is None:
        trusted_legacy_match = (
            trusted_legacy_content is not None
            and legacy_content_equivalent(remote.content, trusted_legacy_content)
        )
        if remote.title != generated.title and not trusted_legacy_match:
            return SyncDecision(
                "conflict",
                generated,
                remote,
                None,
                ("Remote title differs during first adoption.",),
                bootstrap=True,
            )
        if trusted_legacy_match:
            return SyncDecision(
                "update",
                generated,
                remote,
                generated.content,
                ("Remote page matches the trusted Git bootstrap baseline.",),
                bootstrap=True,
            )
        try:
            remote_regions = parse_manual_regions(remote.content)
            if remote_regions:
                if managed_hash(remote.content) != managed_hash(generated.content):
                    return SyncDecision(
                        "conflict",
                        generated,
                        remote,
                        None,
                        ("Marked remote managed content differs during first adoption.",),
                        bootstrap=True,
                    )
                merge = merge_manual_regions(generated.content, remote.content)
                action = "unchanged" if merge.content == remote.content else "update"
                return SyncDecision(
                    action,
                    generated,
                    remote,
                    merge.content,
                    bootstrap=True,
                )

            legacy = legacy_placeholder_projection(generated.content)
            if remote.content != legacy:
                return SyncDecision(
                    "conflict",
                    generated,
                    remote,
                    None,
                    ("Unmarked remote content differs from the legacy generated page.",),
                    bootstrap=True,
                )
            return SyncDecision(
                "update",
                generated,
                remote,
                generated.content,
                bootstrap=True,
            )
        except ManualRegionError as exc:
            return SyncDecision(
                "conflict",
                generated,
                remote,
                None,
                (str(exc),),
                bootstrap=True,
            )

    if remote.id != record.page_id:
        return SyncDecision(
            "conflict",
            generated,
            remote,
            None,
            ("Remote page ID changed since the last synchronization.",),
        )
    if remote.title != record.title:
        return SyncDecision(
            "conflict",
            generated,
            remote,
            None,
            ("Remote title changed outside the synchronizer.",),
        )

    try:
        base = state.get_base_content(record)
        plan = plan_three_way_sync(base, generated.content, remote.content)
    except SyncStateError as exc:
        return SyncDecision(
            "conflict",
            generated,
            remote,
            None,
            (str(exc),),
        )
    if plan.action == "conflict":
        return SyncDecision(
            "conflict",
            generated,
            remote,
            None,
            plan.reasons,
        )

    title_changed = generated.title != remote.title
    action = "update" if plan.action == "update" or title_changed else "unchanged"
    return SyncDecision(
        action,
        generated,
        remote,
        plan.content,
            )


def legacy_content_equivalent(left: str, right: str) -> bool:
    """Compare legacy HTML allowing only known Wiki.js editor normalizations."""

    def normalize(value):
        return (
            value.replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace("\u200b", "")
            .replace("\xa0", " ")
        )

    return normalize(left) == normalize(right)


def load_git_bootstrap_baselines(
    git_ref: str | None,
    pages: list[GeneratedDocumentationPage],
) -> dict[tuple[str, str], str]:
    if not git_ref:
        return {}
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", git_ref) or git_ref.startswith("-"):
        raise RuntimeError(f"Unsafe or invalid Git bootstrap reference {git_ref!r}.")
    verified = subprocess.run(
        ["git", "rev-parse", "--verify", f"{git_ref}^{{commit}}"],
        cwd=script_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if verified.returncode != 0:
        raise RuntimeError(f"Git bootstrap reference not found: {git_ref!r}.")

    baselines = {}
    for page in pages:
        result = subprocess.run(
            ["git", "show", f"{git_ref}:{page.relative_output_path.as_posix()}"],
            cwd=script_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode == 0:
            baselines[(page.language, page.wiki_path)] = result.stdout
    return baselines


def _load_token(token_file: str | None) -> str:
    if token_file:
        try:
            token = Path(token_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"Cannot read token file {token_file}.") from exc
    else:
        token = os.environ.get("WIKIJS_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Wiki.js token missing: set WIKIJS_API_TOKEN or use --token-file."
        )
    return token


def _read_and_plan(
    pages: list[GeneratedDocumentationPage],
    client: WikiJsClient,
    state: SyncStateStore,
    workers: int,
    git_baselines: dict[tuple[str, str], str] | None = None,
) -> list[SyncDecision]:
    baselines = git_baselines or {}

    def read_one(page):
        remote = client.get_page(page.wiki_path, page.language)
        return plan_page(
            page,
            remote,
            state,
            baselines.get((page.language, page.wiki_path)),
        )

    decisions = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(read_one, page): page for page in pages}
        for future in as_completed(futures):
            decisions.append(future.result())
    return sorted(
        decisions,
        key=lambda decision: (
            decision.generated.language,
            decision.generated.wiki_path,
        ),
    )


def _same_remote_snapshot(expected: WikiPage | None, actual: WikiPage | None) -> bool:
    return expected == actual


def apply_decisions(
    decisions: list[SyncDecision],
    client: WikiJsClient,
    state: SyncStateStore,
    progress=None,
) -> dict[str, int]:
    if any(decision.action == "conflict" for decision in decisions):
        raise RuntimeError("Refusing to apply while conflicts are present.")

    counts = {"create": 0, "update": 0, "unchanged": 0}
    total = len(decisions)
    for index, decision in enumerate(decisions, 1):
        generated = decision.generated
        if decision.action == "create":
            outcome = client.create_page(
                WikiPageDraft(
                    path=generated.wiki_path,
                    title=generated.title,
                    content=generated.content,
                    locale=generated.language,
                )
            )
            applied_page = outcome.page
        else:
            current = client.get_page(generated.wiki_path, generated.language)
            if not _same_remote_snapshot(decision.remote, current):
                raise RuntimeError(
                    f"Remote page changed after planning: "
                    f"{generated.language}:{generated.wiki_path}."
                )
            if current is None:
                raise RuntimeError(
                    f"Remote page disappeared after planning: "
                    f"{generated.language}:{generated.wiki_path}."
                )
            if decision.action == "update":
                expected = replace(
                    current,
                    title=generated.title,
                    content=decision.target_content or generated.content,
                )
                applied_page = client.update_page(expected).page
            else:
                applied_page = current

        state.record_applied(
            generated.language,
            generated.wiki_path,
            applied_page.id,
            generated.title,
            generated.content,
        )
        counts[decision.action] += 1
        if progress is not None:
            progress(index, total, decision)
    return counts


def summarize_decisions(decisions: list[SyncDecision]) -> dict[str, int]:
    counts = {"create": 0, "update": 0, "unchanged": 0, "conflict": 0}
    for decision in decisions:
        counts[decision.action] += 1
    return counts


def select_pages(
    pages: list[GeneratedDocumentationPage],
    selectors: list[str] | None,
) -> list[GeneratedDocumentationPage]:
    if not selectors:
        return pages
    selected = []
    matched_selectors = set()
    for page in pages:
        identities = {
            page.relative_output_path.as_posix(),
            page.wiki_path,
            f"{page.language}:{page.wiki_path}",
        }
        matches = identities.intersection(selectors)
        if matches:
            selected.append(page)
            matched_selectors.update(matches)
    missing = [selector for selector in selectors if selector not in matched_selectors]
    if missing:
        raise RuntimeError("Requested pages not found: " + ", ".join(missing))
    return selected


def write_report(path: str | None, report: dict[str, object]):
    if not path:
        return
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sincronizzazione incrementale sicura ACUSTEME → Wiki.js."
    )
    parser.add_argument("mode", choices=["audit", "dry-run", "apply"])
    parser.add_argument("--xml", default=DEFAULT_XML_SOURCE)
    parser.add_argument("--languages", type=parse_languages, default=["it", "en"])
    parser.add_argument(
        "--only-ui",
        action="append",
        choices=sorted(ALLOWED_UI_CODES),
    )
    parser.add_argument(
        "--only-page",
        action="append",
        help=(
            "Limita a una pagina: percorso file relativo, percorso Wiki.js, "
            "oppure locale:percorso Wiki.js. Ripetibile."
        ),
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--token-file")
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIRECTORY))
    parser.add_argument(
        "--bootstrap-git-ref",
        help=(
            "Solo per la prima adozione: considera affidabile l'HTML generato "
            "presente nel riferimento Git indicato, per esempio HEAD."
        ),
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--report")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--confirm",
        help="Per apply deve essere esattamente APPLY.",
    )
    return parser


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.workers < 1 or args.workers > 16:
        parser.error("--workers deve essere compreso tra 1 e 16")
    if args.mode == "apply" and args.confirm != "APPLY":
        parser.error("apply richiede --confirm APPLY")

    tree = load_xml_profile(args.xml)
    pages = build_documentation_pages(
        tree.getroot(),
        args.languages,
        set(args.only_ui) if args.only_ui else ALLOWED_UI_CODES,
    )
    try:
        pages = select_pages(pages, args.only_page)
    except RuntimeError as exc:
        parser.error(str(exc))
    # The public backend repository intentionally does not version generated
    # HTML pages.  The synchronization audit therefore validates the in-memory
    # corpus without expecting a local documentation export beside the tool.
    audit = audit_generated_pages(pages)
    report = {"mode": args.mode, "audit": audit}

    if args.mode == "audit":
        write_report(args.report, report)
        print(json.dumps(audit, ensure_ascii=False, indent=2))
        return 0 if not audit["duplicate_pages"] else 2

    try:
        token = _load_token(args.token_file)
        state = SyncStateStore(args.state_dir)
        client = WikiJsClient(args.endpoint, token)
        git_baselines = load_git_bootstrap_baselines(args.bootstrap_git_ref, pages)
        decisions = _read_and_plan(
            pages,
            client,
            state,
            args.workers,
            git_baselines,
        )
    except (RuntimeError, SyncStateError) as exc:
        parser.error(str(exc))

    decision_report = [decision.report() for decision in decisions]
    counts = summarize_decisions(decisions)
    report["summary"] = counts
    report["bootstrap_git_ref"] = args.bootstrap_git_ref
    report["pages"] = decision_report
    write_report(args.report, report)

    if args.verbose:
        for decision in decisions:
            reason = f" — {'; '.join(decision.reasons)}" if decision.reasons else ""
            print(
                f"[{decision.action.upper():9}] "
                f"{decision.generated.language}:{decision.generated.wiki_path}{reason}"
            )
    print(json.dumps(counts, ensure_ascii=False, indent=2))

    if args.mode == "dry-run":
        return 2 if counts["conflict"] else 0

    if counts["conflict"]:
        print("Apply annullato: risolvere prima tutti i conflitti.")
        return 2
    def show_progress(index, total, decision):
        if index == 1 or index % 10 == 0 or index == total:
            print(
                f"Applicate e verificate {index}/{total} pagine "
                f"(ultima: {decision.generated.language}:"
                f"{decision.generated.wiki_path}).",
                flush=True,
            )

    applied = apply_decisions(decisions, client, state, show_progress)
    print(json.dumps({"applied": applied}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
