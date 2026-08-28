"""Protected manual regions used by the ACUSTEME Wiki.js synchronizer.

Generated documentation owns everything outside ``ACUSTEME-MANUAL`` markers.
Editors own the complete payload between a matching BEGIN / END pair.  The
payload is copied byte-for-byte during a merge, so it may contain arbitrary
HTML, including nested ``div`` elements.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html import escape, unescape
from html.parser import HTMLParser
import re
from typing import Literal


MARKER_VERSION = 1
_KEY_PATTERN = r"[A-Za-z0-9_.:/-]+"
_TOKEN_RE = re.compile(
    rf'<!--\s*ACUSTEME-MANUAL:v(?P<version>\d+):(?P<kind>BEGIN|END)\s+'
    rf'key="(?P<key>{_KEY_PATTERN})"\s*-->'
)
_MARKER_PREFIX = "ACUSTEME-MANUAL:"


class ManualRegionError(ValueError):
    """Base class for malformed or unsafe protected-region documents."""


class InvalidManualRegionKey(ManualRegionError):
    pass


class MalformedManualRegion(ManualRegionError):
    pass


class DuplicateManualRegion(ManualRegionError):
    pass


class ManualRegionConflict(ManualRegionError):
    """Raised when applying a merge could discard manually authored content."""

    def __init__(self, message: str, keys: tuple[str, ...] = ()):
        super().__init__(message)
        self.keys = keys


@dataclass(frozen=True)
class ManualRegion:
    key: str
    version: int
    payload: str
    payload_start: int
    payload_end: int
    block_start: int
    block_end: int


@dataclass(frozen=True)
class MergeResult:
    content: str
    preserved_keys: tuple[str, ...]
    new_keys: tuple[str, ...]
    dropped_placeholder_orphans: tuple[str, ...]


@dataclass(frozen=True)
class SyncPlan:
    action: Literal["unchanged", "update", "conflict"]
    content: str | None
    reasons: tuple[str, ...]
    merge: MergeResult | None = None


class _VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str):
        self.parts.append(data)


def validate_region_key(key: str) -> str:
    if not re.fullmatch(_KEY_PATTERN, key):
        raise InvalidManualRegionKey(
            f"Invalid manual-region key {key!r}; allowed characters are "
            "letters, digits, '.', '_', ':', '/', and '-'."
        )
    return key


def begin_marker(key: str, version: int = MARKER_VERSION) -> str:
    validate_region_key(key)
    return f'<!-- ACUSTEME-MANUAL:v{version}:BEGIN key="{key}" -->'


def end_marker(key: str, version: int = MARKER_VERSION) -> str:
    validate_region_key(key)
    return f'<!-- ACUSTEME-MANUAL:v{version}:END key="{key}" -->'


def build_manual_region(
    key: str,
    examples_label: str,
    placeholder: str = "to be completed",
) -> str:
    """Build the generated placeholder slot for one manually editable region."""

    validate_region_key(key)
    safe_key = escape(key, quote=True)
    safe_label = escape(examples_label)
    safe_placeholder = escape(placeholder)
    return (
        f"{begin_marker(key)}\n"
        f'<div class="acusteme-manual-region" data-acusteme-key="{safe_key}">\n'
        f'<p>{safe_label}: <span class="placeholder">'
        f"{{{safe_placeholder}}}</span></p>\n"
        f"</div>\n"
        f"{end_marker(key)}"
    )


def parse_manual_regions(document: str) -> dict[str, ManualRegion]:
    """Parse and validate all protected regions in *document*.

    Regions cannot be nested and keys must be unique within a page.  Any
    comment containing the ACUSTEME marker prefix but not matching the current
    grammar is rejected, which makes damaged sentinels fail closed.
    """

    recognized = list(_TOKEN_RE.finditer(document))
    raw_prefix_positions = [
        match.start() for match in re.finditer(re.escape(_MARKER_PREFIX), document)
    ]
    recognized_prefix_positions = [
        document.index(_MARKER_PREFIX, marker.start(), marker.end())
        for marker in recognized
    ]
    if recognized_prefix_positions != raw_prefix_positions:
        raise MalformedManualRegion("Unrecognized or damaged ACUSTEME-MANUAL marker.")

    regions: dict[str, ManualRegion] = {}
    opened = None

    for token in recognized:
        version = int(token.group("version"))
        kind = token.group("kind")
        key = token.group("key")

        if version != MARKER_VERSION:
            raise MalformedManualRegion(
                f"Unsupported manual-region marker version v{version} for {key!r}."
            )

        if kind == "BEGIN":
            if opened is not None:
                raise MalformedManualRegion(
                    f"Nested manual regions are not allowed ({opened.group('key')!r}, {key!r})."
                )
            if key in regions:
                raise DuplicateManualRegion(f"Duplicate manual-region key {key!r}.")
            opened = token
            continue

        if opened is None:
            raise MalformedManualRegion(f"END marker without BEGIN for {key!r}.")
        if opened.group("key") != key or opened.group("version") != token.group("version"):
            raise MalformedManualRegion(
                f"Mismatched manual-region markers {opened.group('key')!r} and {key!r}."
            )

        regions[key] = ManualRegion(
            key=key,
            version=version,
            payload=document[opened.end() : token.start()],
            payload_start=opened.end(),
            payload_end=token.start(),
            block_start=opened.start(),
            block_end=token.end(),
        )
        opened = None

    if opened is not None:
        raise MalformedManualRegion(
            f"BEGIN marker without END for {opened.group('key')!r}."
        )

    return regions


def visible_text(fragment: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(fragment)
    parser.close()
    return " ".join(" ".join(parser.parts).split())


def is_placeholder_payload(payload: str) -> bool:
    text = visible_text(payload)
    return text in {
        "Esempi d'uso: {to be completed}",
        "Usage examples: {to be completed}",
    }


def managed_projection(document: str) -> str:
    """Return content with all manual payloads replaced by stable sentinels."""

    regions = sorted(parse_manual_regions(document).values(), key=lambda region: region.payload_start)
    parts: list[str] = []
    copied_until = 0
    for region in regions:
        parts.append(document[copied_until : region.payload_start])
        parts.append(f"\n[[ACUSTEME-MANUAL:v{region.version}:{region.key}]]\n")
        copied_until = region.payload_end
    parts.append(document[copied_until:])
    return "".join(parts)


def content_hash(document: str) -> str:
    return sha256(document.encode("utf-8")).hexdigest()


def managed_hash(document: str) -> str:
    return content_hash(managed_projection(document))


def legacy_placeholder_projection(document: str) -> str:
    """Render generated placeholder regions in the pre-marker HTML format.

    This is used only to prove that a first synchronization changes scaffolding
    and not managed documentation.  It refuses documents containing manual
    payloads or non-standard wrappers.
    """

    regions = sorted(
        parse_manual_regions(document).values(),
        key=lambda region: region.block_start,
    )
    replacements = []
    wrapper_re = re.compile(
        r'^\s*<div class="acusteme-manual-region" '
        r'data-acusteme-key="[^"]+">\s*'
        r'(?P<paragraph><p>.*?</p>)\s*</div>\s*$',
        re.DOTALL,
    )
    for region in regions:
        if not is_placeholder_payload(region.payload):
            raise ManualRegionConflict(
                f"Cannot create a legacy projection from manual region {region.key!r}.",
                (region.key,),
            )
        wrapper = wrapper_re.fullmatch(region.payload)
        if wrapper is None:
            raise MalformedManualRegion(
                f"Generated placeholder wrapper is non-standard for {region.key!r}."
            )
        replacements.append((region, unescape(wrapper.group("paragraph"))))

    parts = []
    copied_until = 0
    for region, paragraph in replacements:
        parts.append(document[copied_until : region.block_start])
        parts.append(paragraph)
        copied_until = region.block_end
    parts.append(document[copied_until:])
    return "".join(parts)


def merge_manual_regions(generated: str, remote: str) -> MergeResult:
    """Merge remote-owned payloads into newly generated content.

    Placeholder-only remote regions remain generator-owned, allowing labels or
    placeholder markup to evolve.  A remote manual region missing from the new
    generated document is an unsafe orphan and blocks the merge.
    """

    generated_regions = parse_manual_regions(generated)
    remote_regions = parse_manual_regions(remote)

    generated_keys = set(generated_regions)
    remote_keys = set(remote_regions)
    orphan_keys = sorted(remote_keys - generated_keys)
    manual_orphans = tuple(
        key for key in orphan_keys if not is_placeholder_payload(remote_regions[key].payload)
    )
    if manual_orphans:
        raise ManualRegionConflict(
            "Manual regions would become orphaned: " + ", ".join(manual_orphans),
            manual_orphans,
        )

    replacements: dict[str, str] = {}
    preserved: list[str] = []
    for key in sorted(generated_keys & remote_keys):
        remote_payload = remote_regions[key].payload
        if not is_placeholder_payload(remote_payload):
            replacements[key] = remote_payload
            preserved.append(key)

    ordered = sorted(generated_regions.values(), key=lambda region: region.payload_start)
    parts: list[str] = []
    copied_until = 0
    for region in ordered:
        parts.append(generated[copied_until : region.payload_start])
        parts.append(replacements.get(region.key, region.payload))
        copied_until = region.payload_end
    parts.append(generated[copied_until:])

    return MergeResult(
        content="".join(parts),
        preserved_keys=tuple(preserved),
        new_keys=tuple(sorted(generated_keys - remote_keys)),
        dropped_placeholder_orphans=tuple(
            key for key in orphan_keys if key not in manual_orphans
        ),
    )


def plan_three_way_sync(base: str, generated: str, remote: str) -> SyncPlan:
    """Plan a safe page update using the last applied base as an ownership guard."""

    try:
        if managed_hash(remote) != managed_hash(base):
            return SyncPlan(
                action="conflict",
                content=None,
                reasons=("Remote managed content changed outside protected regions.",),
            )
        merge = merge_manual_regions(generated, remote)
    except ManualRegionError as exc:
        return SyncPlan(action="conflict", content=None, reasons=(str(exc),))

    action: Literal["unchanged", "update"] = (
        "unchanged" if merge.content == remote else "update"
    )
    return SyncPlan(action=action, content=merge.content, reasons=(), merge=merge)
