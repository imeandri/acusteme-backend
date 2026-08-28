import json
import tempfile
import unittest
from pathlib import Path

from extractor_auto2 import GeneratedDocumentationPage
from wikijs_graphql import MutationOutcome, WikiPage
from wikijs_manual_regions import (
    build_manual_region,
    legacy_placeholder_projection,
    parse_manual_regions,
)
from wikijs_sync import (
    SyncDecision,
    apply_decisions,
    audit_generated_pages,
    legacy_content_equivalent,
    plan_page,
    select_pages,
)
from wikijs_sync_state import SyncStateError, SyncStateStore


def generated(content, title="01_Test"):
    return GeneratedDocumentationPage(
        language="it",
        ui_code="object_ui",
        screen_idno="test",
        screen_index=1,
        title=title,
        content=content,
        relative_output_path=Path("object_ui/test.html"),
        wiki_path="acusteme_data_model/DM_documentation/object_ui/test",
    )


def marked_page(managed="managed", key="screen::field"):
    slot = build_manual_region(key, "Esempi d'uso")
    return f"<body>\n{managed}\n{slot}\n</body>"


def remote_page(content, title="01_Test", page_id=10, editor="code"):
    return WikiPage(
        id=page_id,
        path="acusteme_data_model/DM_documentation/object_ui/test",
        title=title,
        content=content,
        locale="it",
        editor=editor,
    )


def with_manual(document, payload="<div><p>Esempio manuale</p></div>"):
    region = next(iter(parse_manual_regions(document).values()))
    return document[: region.payload_start] + payload + document[region.payload_end :]


class SyncPlanningTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state = SyncStateStore(Path(self.temporary.name) / "state")

    def test_missing_remote_is_created_only_without_prior_state(self):
        page = generated(marked_page())
        self.assertEqual(plan_page(page, None, self.state).action, "create")

        self.state.record_applied("it", page.wiki_path, 10, page.title, page.content)
        self.assertEqual(plan_page(page, None, self.state).action, "conflict")

    def test_first_adoption_accepts_only_exact_legacy_page(self):
        page = generated(marked_page())
        legacy = legacy_placeholder_projection(page.content)

        decision = plan_page(page, remote_page(legacy), self.state)
        self.assertEqual(decision.action, "update")
        self.assertTrue(decision.bootstrap)

        changed = plan_page(page, remote_page(legacy + "manual"), self.state)
        self.assertEqual(changed.action, "conflict")

    def test_first_adoption_preserves_already_marked_manual_content(self):
        page = generated(marked_page())
        remote = remote_page(with_manual(page.content))

        decision = plan_page(page, remote, self.state)

        self.assertEqual(decision.action, "unchanged")
        self.assertIn("Esempio manuale", decision.target_content)

    def test_trusted_git_baseline_allows_known_legacy_and_title_changes(self):
        page = generated(marked_page("managed v2"), title="02_New title")
        trusted = legacy_placeholder_projection(marked_page("managed v1"))
        normalized_remote = trusted.replace(" ", "\xa0", 1) + "\u200b\u200b"
        normalized_trusted = trusted + "\u200b\u200b"
        remote = remote_page(normalized_remote, title="01_Old title")

        decision = plan_page(page, remote, self.state, normalized_trusted)

        self.assertEqual(decision.action, "update")
        self.assertTrue(decision.bootstrap)

    def test_legacy_equivalence_allows_only_editor_normalization(self):
        self.assertTrue(legacy_content_equivalent("a\xa0b\u200b", "a b"))
        self.assertFalse(legacy_content_equivalent("manual edit", "generated"))

    def test_three_way_update_preserves_manual_content(self):
        base = generated(marked_page("managed v1"))
        self.state.record_applied("it", base.wiki_path, 10, base.title, base.content)
        new = generated(marked_page("managed v2"))
        remote = remote_page(with_manual(base.content))

        decision = plan_page(new, remote, self.state)

        self.assertEqual(decision.action, "update")
        self.assertIn("managed v2", decision.target_content)
        self.assertIn("Esempio manuale", decision.target_content)

    def test_remote_managed_or_title_edits_conflict(self):
        page = generated(marked_page())
        self.state.record_applied("it", page.wiki_path, 10, page.title, page.content)

        managed_edit = plan_page(
            page,
            remote_page(page.content.replace("managed", "remote edit")),
            self.state,
        )
        title_edit = plan_page(
            page,
            remote_page(page.content, title="Manual title"),
            self.state,
        )

        self.assertEqual(managed_edit.action, "conflict")
        self.assertEqual(title_edit.action, "conflict")

    def test_non_html_editor_conflicts(self):
        page = generated(marked_page())
        decision = plan_page(page, remote_page(page.content, editor="markdown"), self.state)
        self.assertEqual(decision.action, "conflict")


class StateAndAuditTests(unittest.TestCase):
    def test_state_roundtrip_and_checksum_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state"
            state = SyncStateStore(state_path)
            page = generated(marked_page())
            record = state.record_applied(
                "it", page.wiki_path, 10, page.title, page.content
            )

            reloaded = SyncStateStore(state_path)
            loaded = reloaded.get_record("it", page.wiki_path)
            self.assertEqual(loaded, record)
            self.assertEqual(reloaded.get_base_content(loaded), page.content)

            (state_path / loaded.base_file).write_text("damaged", encoding="utf-8")
            with self.assertRaises(SyncStateError):
                reloaded.get_base_content(loaded)

    def test_local_audit_detects_legacy_equivalence(self):
        page = generated(marked_page())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / page.relative_output_path
            output.parent.mkdir(parents=True)
            output.write_text(
                legacy_placeholder_projection(page.content),
                encoding="utf-8",
            )

            audit = audit_generated_pages([page], root)

        self.assertTrue(audit["local_regression_clean"])
        self.assertEqual(audit["pages"], 1)
        self.assertEqual(audit["protected_regions"], 1)
        self.assertEqual(audit["existing_formats"]["legacy"], 1)

    def test_manifest_is_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            state = SyncStateStore(directory)
            page = generated(marked_page())
            state.record_applied("it", page.wiki_path, 10, page.title, page.content)

            manifest = json.loads(
                (Path(directory) / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(manifest["version"], 1)
        self.assertIn(f"it:{page.wiki_path}", manifest["pages"])

    def test_apply_rechecks_remote_and_records_generated_base(self):
        page = generated(marked_page("managed v2"))
        old_remote = remote_page(marked_page("managed v1"))
        planned = SyncDecision(
            action="update",
            generated=page,
            remote=old_remote,
            target_content=with_manual(page.content),
        )

        class FakeClient:
            def __init__(self):
                self.updated = None

            def get_page(self, path, locale):
                return old_remote

            def update_page(self, expected):
                self.updated = expected
                return MutationOutcome(expected, {"succeeded": True})

        with tempfile.TemporaryDirectory() as directory:
            state = SyncStateStore(directory)
            client = FakeClient()
            counts = apply_decisions([planned], client, state)
            record = state.get_record("it", page.wiki_path)

            self.assertEqual(counts["update"], 1)
            self.assertIn("Esempio manuale", client.updated.content)
            self.assertEqual(state.get_base_content(record), page.content)

    def test_selects_exact_language_page(self):
        italian = generated(marked_page())
        english = GeneratedDocumentationPage(
            **{
                **italian.__dict__,
                "language": "en",
                "relative_output_path": Path("en/object_ui/test.html"),
            }
        )

        selected = select_pages(
            [italian, english],
            [f"it:{italian.wiki_path}"],
        )

        self.assertEqual(selected, [italian])


if __name__ == "__main__":
    unittest.main()
