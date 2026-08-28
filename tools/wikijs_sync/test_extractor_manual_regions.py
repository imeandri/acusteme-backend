import unittest
import xml.etree.ElementTree as ET

from extractor_auto2 import (
    DocumentationElement,
    LANGUAGES,
    generate_html_documentation,
    list_placements,
)
from wikijs_manual_regions import (
    is_placeholder_payload,
    parse_manual_regions,
    visible_text,
)


def profile(xml_body):
    return ET.fromstring(f"<profile>{xml_body}</profile>")


class GeneratorManualRegionTests(unittest.TestCase):
    def test_renders_localized_protected_slots(self):
        element = DocumentationElement(
            numerale="1.1",
            code="title",
            datatype="Text",
            label="Titolo",
            description="N/A",
            required="No",
            repeatability="No",
            sparql_query="N/A",
            vocabulary="N/A",
            manual_region_key="object_ui/identity::title-placement",
        )

        italian = generate_html_documentation([element], "Identità", LANGUAGES["it"])
        english = generate_html_documentation([element], "Identity", LANGUAGES["en"])

        for document, label in ((italian, "Esempi d'uso"), (english, "Usage examples")):
            regions = parse_manual_regions(document)
            self.assertEqual(list(regions), ["object_ui/identity::title-placement"])
            self.assertIn(
                label,
                visible_text(regions["object_ui/identity::title-placement"].payload),
            )
            self.assertTrue(
                is_placeholder_payload(regions["object_ui/identity::title-placement"].payload)
            )

    def test_placement_code_disambiguates_reused_bundle(self):
        root = profile(
            """
            <userInterface code="object_ui"><screens><screen idno="identity">
              <labels><label locale="it_IT"><name>Identità</name></label></labels>
              <bundlePlacements>
                <placement code="placement-one"><bundle>ca_objects.title</bundle></placement>
                <placement code="placement-two"><bundle>ca_objects.title</bundle></placement>
              </bundlePlacements>
            </screen></screens></userInterface>
            <metadataElement code="title" datatype="Text" />
            """
        )

        elements, exists, _, _ = list_placements(
            root, "object_ui", 1, LANGUAGES["it"], False
        )

        self.assertTrue(exists)
        self.assertEqual(
            [element.manual_region_key for element in elements],
            [
                "object_ui/identity::placement-one",
                "object_ui/identity::placement-two",
            ],
        )

    def test_nested_metadata_uses_full_path(self):
        root = profile(
            """
            <userInterface code="object_ui"><screens><screen idno="identity">
              <labels><label locale="it_IT"><name>Identità</name></label></labels>
              <bundlePlacements>
                <placement code="outer-placement"><bundle>ca_objects.outer</bundle></placement>
              </bundlePlacements>
            </screen></screens></userInterface>
            <metadataElement code="outer" datatype="Container">
              <elements>
                <metadataElement code="direct-leaf" datatype="Text" />
                <metadataElement code="inner" datatype="Container">
                  <elements>
                    <metadataElement code="nested-leaf" datatype="Text" />
                  </elements>
                </metadataElement>
              </elements>
            </metadataElement>
            """
        )

        elements, _, _, _ = list_placements(
            root, "object_ui", 1, LANGUAGES["it"], False
        )

        self.assertEqual(
            [element.manual_region_key for element in elements],
            [
                "object_ui/identity::outer-placement",
                "object_ui/identity::outer-placement/direct-leaf",
                "object_ui/identity::outer-placement/inner/nested-leaf",
            ],
        )

    def test_missing_placement_code_fails_closed(self):
        root = profile(
            """
            <userInterface code="object_ui"><screens><screen idno="identity">
              <bundlePlacements><placement><bundle>ca_objects.title</bundle></placement></bundlePlacements>
            </screen></screens></userInterface>
            """
        )

        with self.assertRaisesRegex(ValueError, "Placement without code"):
            list_placements(root, "object_ui", 1, LANGUAGES["it"], False)

    def test_sparql_source_is_html_escaped_without_truncation(self):
        query = (
            "SELECT * WHERE { <http://example.test/item> ?p ?o . "
            'FILTER(REGEX(?o, "***PLACEHOLDER***", "i") && BOUND(?o)) }'
        )
        element = DocumentationElement(
            numerale="1.1",
            code="linked-field",
            datatype="InformationService",
            label="Linked field",
            description="N/A",
            required="No",
            repeatability="No",
            sparql_query=query,
            vocabulary="N/A",
            manual_region_key="object_ui/identity::linked-field",
        )

        document = generate_html_documentation([element], "Identity", LANGUAGES["en"])

        self.assertIn("&lt;http://example.test/item&gt;", document)
        self.assertIn("&amp;&amp; BOUND(?o)", document)
        self.assertNotIn("<http://example.test/item>", document)

    def test_required_field_has_one_well_formed_warning(self):
        element = DocumentationElement(
            numerale="1.1",
            code="required-field",
            datatype="Text",
            label="Required field",
            description="N/A",
            required="Yes",
            repeatability="No",
            sparql_query="N/A",
            vocabulary="N/A",
            manual_region_key="object_ui/identity::required-field",
        )

        document = generate_html_documentation([element], "Identity", LANGUAGES["en"])

        self.assertEqual(document.count("<strong>Required:</strong> Yes"), 1)
        self.assertNotIn("Yes</p></blockquote>\nYes</p></blockquote>", document)


if __name__ == "__main__":
    unittest.main()
