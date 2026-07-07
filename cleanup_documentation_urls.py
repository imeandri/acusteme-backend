import os
import argparse
import xml.etree.ElementTree as ET

# Path al file XML
script_dir = os.path.dirname(os.path.abspath(__file__))
default_xml_file = os.path.join(script_dir, "ACUSTEME_profile.xml")

# UI per cui documentation_url deve essere vuoto
BLOCKED_UI_CODES = {
    "standard_storage_locations_ui",
    "occurrences_ui",
    "places_ui",
    "collections_ui",
    "object_lots_ui",
    "ui_editor",
    "ui_screen_editor"
}

def ensure_empty_documentation_url(placement):
    """
    Se esiste <setting name="documentation_url"> lo svuota.
    Se non esiste, non fa nulla.
    """
    doc_url_elem = placement.find("settings/setting[@name='documentation_url']")
    if doc_url_elem is not None:
        doc_url_elem.text = ""

def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Svuota documentation_url per le UI in cui il campo deve restare vuoto."
    )
    parser.add_argument("--xml", default=default_xml_file, help="Path del profilo XML.")
    return parser


def main():
    args = build_arg_parser().parse_args()
    xml_file = args.xml

    tree = ET.parse(xml_file)
    root = tree.getroot()

    cleaned_count = 0
    cleaned_ui = {}

    user_interfaces = root.findall(".//userInterface")

    for user_interface in user_interfaces:
        ui_code = user_interface.attrib.get("code", "N/A")

        if ui_code not in BLOCKED_UI_CODES:
            continue

        cleaned_ui[ui_code] = 0

        screens = user_interface.findall("screens/screen")
        for screen in screens:
            placements = screen.findall("bundlePlacements/placement")
            for placement in placements:
                doc_url_elem = placement.find("settings/setting[@name='documentation_url']")
                if doc_url_elem is not None and (doc_url_elem.text is None or doc_url_elem.text != ""):
                    doc_url_elem.text = ""
                    cleaned_count += 1
                    cleaned_ui[ui_code] += 1
                elif doc_url_elem is not None:
                    # Esiste già ma è già vuoto
                    cleaned_ui[ui_code] += 0

    backup_file = os.path.join(script_dir, "ACUSTEME_profile_before_cleanup.xml")
    if not os.path.exists(backup_file):
        tree_backup = ET.parse(xml_file)
        tree_backup.write(backup_file, encoding="utf-8", xml_declaration=True)

    tree.write(xml_file, encoding="utf-8", xml_declaration=True)

    print("Cleanup completato.")
    print(f"documentation_url svuotati: {cleaned_count}")
    print("\nDettaglio per UI:")
    for ui_code in sorted(cleaned_ui.keys()):
        print(f" - {ui_code}: {cleaned_ui[ui_code]} campi modificati")

if __name__ == "__main__":
    main()
