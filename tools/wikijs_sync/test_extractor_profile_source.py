import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from extractor_auto2 import (
    DEFAULT_XML_SOURCE,
    build_arg_parser,
    is_remote_xml_source,
    load_xml_profile,
)


SAMPLE_PROFILE = b'<profile code="test"><metadataElements /></profile>'


class ProfileSourceTests(unittest.TestCase):
    def test_defaults_to_read_only_github_profile(self):
        args = build_arg_parser().parse_args([])

        self.assertEqual(args.xml, DEFAULT_XML_SOURCE)
        self.assertEqual(args.update_documentation_url_for, "none")

    def test_detects_only_http_sources_as_remote(self):
        self.assertTrue(is_remote_xml_source("https://example.test/profile.xml"))
        self.assertTrue(is_remote_xml_source("http://example.test/profile.xml"))
        self.assertFalse(is_remote_xml_source("ACUSTEME_profile.xml"))

    def test_loads_local_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.xml"
            profile.write_bytes(SAMPLE_PROFILE)

            tree = load_xml_profile(str(profile))

        self.assertEqual(tree.getroot().tag, "profile")
        self.assertEqual(tree.getroot().attrib["code"], "test")

    def test_loads_remote_profile(self):
        response = io.BytesIO(SAMPLE_PROFILE)

        with patch("extractor_auto2.urlopen", return_value=response) as mocked:
            tree = load_xml_profile("https://example.test/profile.xml")

        self.assertEqual(tree.getroot().tag, "profile")
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.test/profile.xml")
        self.assertEqual(mocked.call_args.kwargs["timeout"], 30)


if __name__ == "__main__":
    unittest.main()
