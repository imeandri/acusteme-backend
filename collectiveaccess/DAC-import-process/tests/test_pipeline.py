from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from dac_common import extract_profile_relators


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "RAW_DATA" / "TAB MANCANTI.xlsx"
PROFILE = ROOT / "ACUSTEME_profile.xml"


def load_script(name: str, alias: str):
    spec = importlib.util.spec_from_file_location(alias, ROOT / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parser = load_script("1_dacparser2.py", "dac_parser")
post = load_script("2_xmlpostprocess2.py", "dac_post")
covers = load_script("3_discogs3.py", "dac_covers")
checker = load_script("check_relators.py", "dac_checker")


class PipelineTests(unittest.TestCase):
    def test_two_real_sheets_and_pseudonyms(self):
        with tempfile.TemporaryDirectory() as directory:
            psi = Path(directory) / "psi.xml"
            lame = Path(directory) / "lame.xml"
            first = parser.excel_to_xml(WORKBOOK, psi, ["OK PSI e dintorni"])
            second = parser.excel_to_xml(WORKBOOK, lame, ["OK Canzoniere delle Lame"])
            self.assertEqual(first["records"], 10)
            self.assertEqual(second["records"], 21)
            root = ET.parse(lame).getroot()
            aliases = root.findall(".//pseudonym")
            self.assertEqual(len(aliases), 3)
            self.assertEqual(aliases[0].text, "Vitavisia")
            responsibility = next(e for e in root.findall(".//responsabilita") if e.find("pseudonym") is not None)
            self.assertEqual(responsibility.findtext("first_name"), "Giovanna")
            self.assertEqual(responsibility.findtext("last_name"), "Marini")

    def test_relators_against_profile(self):
        result = checker.audit(WORKBOOK, PROFILE, ["OK PSI e dintorni", "OK Canzoniere delle Lame"])
        self.assertEqual(result["error_count"], 0)
        self.assertGreater(len(extract_profile_relators(PROFILE)), 300)

    def test_postprocessor_preserves_geonames_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "in.xml"
            output = Path(directory) / "out.xml"
            source.write_text("<records><record><place><geonames_id>123</geonames_id><geonames_url>u</geonames_url></place></record></records>", encoding="utf-8")
            original = post.fetch_geoname
            post.fetch_geoname = lambda _gid: (_ for _ in ()).throw(RuntimeError("offline"))
            try:
                post.process_file(source, output)
            finally:
                post.fetch_geoname = original
            root = ET.parse(output).getroot()
            self.assertEqual(root.findtext(".//geonames_id"), "123")
            self.assertEqual(root.findtext(".//geonames_url"), "u")

    def test_cover_workflow_does_not_change_excel(self):
        before = hashlib.sha256(WORKBOOK.read_bytes()).hexdigest()

        class FakeClient:
            def __init__(self, *_args, **_kwargs):
                pass
            def images(self, kind, item_id):
                return [{"uri": f"mock://{item_id}"}], f"{kind} {item_id}"

        original_client = covers.DiscogsClient
        original_download = covers.download_atomic
        covers.DiscogsClient = FakeClient
        covers.download_atomic = lambda _client, _url, destination: (destination.parent.mkdir(parents=True, exist_ok=True), destination.write_bytes(b"jpeg"))
        try:
            with tempfile.TemporaryDirectory() as directory:
                manifest = covers.run(WORKBOOK, Path(directory) / "covers", Path(directory) / "manifest.csv",
                                      "fake", ["OK PSI e dintorni"], 0)
                self.assertTrue(manifest)
                self.assertTrue(all(row["status"] in {"ok", "skipped"} for row in manifest))
        finally:
            covers.DiscogsClient = original_client
            covers.download_atomic = original_download
        after = hashlib.sha256(WORKBOOK.read_bytes()).hexdigest()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
