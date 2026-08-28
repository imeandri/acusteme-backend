import unittest

from wikijs_manual_regions import (
    DuplicateManualRegion,
    InvalidManualRegionKey,
    MalformedManualRegion,
    ManualRegionConflict,
    build_manual_region,
    content_hash,
    is_placeholder_payload,
    legacy_placeholder_projection,
    managed_hash,
    merge_manual_regions,
    parse_manual_regions,
    plan_three_way_sync,
)


def page(managed_text, regions):
    return "<body>\n" + managed_text + "\n" + "\n".join(regions) + "\n</body>"


def with_manual_payload(region, payload):
    parsed = next(iter(parse_manual_regions(region).values()))
    return region[: parsed.payload_start] + "\n" + payload + "\n" + region[parsed.payload_end :]


class ManualRegionContractTests(unittest.TestCase):
    def test_builds_versioned_div_slot(self):
        region = build_manual_region("object_ui/basic::preferred_labels1", "Esempi d'uso")
        parsed = parse_manual_regions(region)

        self.assertEqual(list(parsed), ["object_ui/basic::preferred_labels1"])
        self.assertIn('class="acusteme-manual-region"', parsed[next(iter(parsed))].payload)
        self.assertIn("{to be completed}", region)
        self.assertTrue(is_placeholder_payload(parsed[next(iter(parsed))].payload))

    def test_rejects_invalid_keys(self):
        with self.assertRaises(InvalidManualRegionKey):
            build_manual_region("key with spaces", "Esempi d'uso")

    def test_projects_generated_slot_to_legacy_paragraph(self):
        region = build_manual_region("one", "Esempi d'uso")

        self.assertEqual(
            legacy_placeholder_projection(region),
            '<p>Esempi d\'uso: <span class="placeholder">'
            "{to be completed}</span></p>",
        )

        manual = with_manual_payload(region, "<p>Testo manuale</p>")
        with self.assertRaises(ManualRegionConflict):
            legacy_placeholder_projection(manual)

    def test_rejects_damaged_nested_and_duplicate_markers(self):
        valid = build_manual_region("one", "Esempi d'uso")
        with self.assertRaises(MalformedManualRegion):
            parse_manual_regions(valid.replace(":END", ":BROKEN"))
        with self.assertRaises(MalformedManualRegion):
            parse_manual_regions(valid.replace(" -->", "", 1))

        nested = valid.replace(
            '<div class="acusteme-manual-region"',
            build_manual_region("two", "Esempi d'uso")
            + '\n<div class="acusteme-manual-region"',
        )
        with self.assertRaises(MalformedManualRegion):
            parse_manual_regions(nested)

        with self.assertRaises(DuplicateManualRegion):
            parse_manual_regions(valid + "\n" + valid)


class ManualRegionMergeTests(unittest.TestCase):
    def setUp(self):
        self.slot_a = build_manual_region("screen::field-a", "Esempi d'uso")
        self.slot_b = build_manual_region("screen::field-b", "Esempi d'uso")
        self.manual_html = (
            '<div class="notification"><p>Esempio <strong>manuale</strong>.</p>'
            '<div data-extra="yes">Annidato</div></div>'
        )

    def test_preserves_arbitrary_manual_html_byte_for_byte(self):
        generated = page("generated v2", [self.slot_a])
        remote = page("generated v1", [with_manual_payload(self.slot_a, self.manual_html)])
        result = merge_manual_regions(generated, remote)

        self.assertEqual(
            parse_manual_regions(result.content)["screen::field-a"].payload.strip(),
            self.manual_html,
        )
        self.assertEqual(result.preserved_keys, ("screen::field-a",))
        self.assertIn("generated v2", result.content)

    def test_managed_hash_ignores_manual_payload_but_full_hash_does_not(self):
        original = page("managed", [self.slot_a])
        edited = page("managed", [with_manual_payload(self.slot_a, self.manual_html)])

        self.assertEqual(managed_hash(original), managed_hash(edited))
        self.assertNotEqual(content_hash(original), content_hash(edited))

    def test_new_slot_keeps_generated_placeholder(self):
        result = merge_manual_regions(
            page("managed", [self.slot_a, self.slot_b]),
            page("managed", [self.slot_a]),
        )

        self.assertEqual(result.new_keys, ("screen::field-b",))
        self.assertIn("{to be completed}", result.content)

    def test_drops_only_placeholder_orphans(self):
        result = merge_manual_regions(
            page("managed", [self.slot_a]),
            page("managed", [self.slot_a, self.slot_b]),
        )
        self.assertEqual(result.dropped_placeholder_orphans, ("screen::field-b",))

        remote_manual = page(
            "managed",
            [self.slot_a, with_manual_payload(self.slot_b, self.manual_html)],
        )
        with self.assertRaises(ManualRegionConflict) as raised:
            merge_manual_regions(page("managed", [self.slot_a]), remote_manual)
        self.assertEqual(raised.exception.keys, ("screen::field-b",))

    def test_three_way_plan_blocks_remote_edits_outside_regions(self):
        base = page("managed v1", [self.slot_a])
        remote = page("manually changed outside", [self.slot_a])
        generated = page("managed v2", [self.slot_a])

        plan = plan_three_way_sync(base, generated, remote)

        self.assertEqual(plan.action, "conflict")
        self.assertIsNone(plan.content)

    def test_three_way_plan_updates_managed_content_and_preserves_manual(self):
        base = page("managed v1", [self.slot_a])
        remote = page("managed v1", [with_manual_payload(self.slot_a, self.manual_html)])
        generated = page("managed v2", [self.slot_a])

        plan = plan_three_way_sync(base, generated, remote)

        self.assertEqual(plan.action, "update")
        self.assertIn("managed v2", plan.content)
        self.assertIn(self.manual_html, plan.content)

    def test_three_way_plan_is_idempotent(self):
        base = page("managed v2", [self.slot_a])
        remote = page("managed v2", [with_manual_payload(self.slot_a, self.manual_html)])

        plan = plan_three_way_sync(base, base, remote)

        self.assertEqual(plan.action, "unchanged")
        self.assertEqual(plan.content, remote)


if __name__ == "__main__":
    unittest.main()
