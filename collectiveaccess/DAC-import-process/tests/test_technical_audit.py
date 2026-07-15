from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("technical_audit", ROOT / "5_technical_audit.py")
technical = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(technical)


XML = """<records><record id="1">
  <discogs_release_url>https://www.discogs.com/release/1-test</discogs_release_url>
  <descrizione_fisica><designazione supporto="AUC10">disco sonoro</designazione><formato>33 rpm LP</formato></descrizione_fisica>
  <dati_specifici><tipo_supporto>disco sonoro</tipo_supporto><tecnica1>analogico</tecnica1>
    <spessore_solco><CA_WD_string /></spessore_solco>
    <tecnica2><CA_WD_string /></tecnica2><segnale />
    <velocita><CA_WD_string>33 rpm|Q117461697|http://www.wikidata.org/entity/Q117461697</CA_WD_string></velocita>
  </dati_specifici>
</record></records>"""


class FakeClient:
    def __init__(self, formats):
        self.formats = formats

    def release(self, _release_id):
        return {"formats": self.formats}


class TechnicalAuditTests(unittest.TestCase):
    def test_audit_is_read_only_and_detects_conflict(self):
        record = ET.fromstring(XML).find("record")
        before = ET.tostring(record)
        result = technical.audit_record(record, {"formats": [{"name": "Vinyl", "descriptions": ["45 RPM"]}]})
        self.assertEqual(before, ET.tostring(record))
        self.assertEqual(result["status"], "error")
        self.assertTrue(result["requires_human_review"])
        self.assertTrue(any(item["code"] == "discogs_conflict" for item in result["issues"]))

    def test_missing_parser_nodes_are_reported(self):
        record = ET.fromstring("<record id='x'><descrizione_fisica><designazione supporto='AUC10'>disco sonoro</designazione><formato>45 rpm</formato></descrizione_fisica><dati_specifici><tipo_supporto>disco sonoro</tipo_supporto><tecnica1>analogico</tecnica1></dati_specifici></record>")
        result = technical.audit_record(record)
        missing = [item["field"] for item in result["issues"] if item["code"] == "missing_value"]
        self.assertIn("dati_specifici/velocita/CA_WD_string", missing)
        self.assertIn("dati_specifici/spessore_solco/CA_WD_string", missing)
        self.assertTrue(result["requires_human_review"])

    def test_invalid_linked_syntax_is_reported(self):
        record = ET.fromstring(XML)
        record.find(".//velocita/CA_WD_string").text = "33 rpm Q117461697"
        result = technical.audit_record(record.find("record"))
        self.assertTrue(any(item["code"] == "invalid_ca_wd_string" for item in result["issues"]))

    def test_run_writes_html_json_and_flags_missing_source(self):
        source_xml = XML.replace("<discogs_release_url>https://www.discogs.com/release/1-test</discogs_release_url>", "")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "in.xml"
            report = Path(directory) / "report.json"
            html = Path(directory) / "report.html"
            source.write_text(source_xml, encoding="utf-8")
            before = source.read_bytes()
            result = technical.run(source, report, html, FakeClient([]))
            self.assertEqual(before, source.read_bytes())
            self.assertTrue(any(item["code"] == "discogs_source_missing" for item in result["records"][0]["issues"]))
            self.assertTrue(result["records"][0]["requires_human_review"])
            self.assertEqual(result["summary"]["human_review"], 1)
            self.assertTrue(report.exists())
            rendered = html.read_text(encoding="utf-8")
            self.assertIn("Audit dati tecnici DAC", rendered)
            self.assertIn("CONTROLLO UMANO RICHIESTO", rendered)

    def test_consistent_record_needs_no_human_review(self):
        xml = XML.replace("<CA_WD_string />", "<CA_WD_string>microgroove record|Q86816874|http://www.wikidata.org/entity/Q86816874</CA_WD_string>", 1).replace("<CA_WD_string />", "<CA_WD_string>Electrical recording - en|Q123556092|http://www.wikidata.org/entity/Q123556092</CA_WD_string>", 1)
        record = ET.fromstring(xml).find("record")
        result = technical.audit_record(record, {"formats": [{"name": "Vinyl", "descriptions": ["LP", "33 ⅓ RPM"]}]})
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["requires_human_review"])


if __name__ == "__main__":
    unittest.main()
