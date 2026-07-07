import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "ACUSTEME_profile.xml"
DEFAULT_OUTPUT = SCRIPT_DIR / "ACUSTEME_profile_EN.xml"


def localized_documentation_url(url, source_lang, target_lang):
    parsed = urlsplit(url)
    path_parts = parsed.path.split("/")

    if len(path_parts) < 2 or path_parts[1] != source_lang:
        return None

    path_parts[1] = target_lang
    new_path = "/".join(path_parts)
    return urlunsplit((parsed.scheme, parsed.netloc, new_path, parsed.query, parsed.fragment))


def generate_profile(input_path, output_path, source_lang, target_lang, host):
    tree = ET.parse(input_path)
    root = tree.getroot()

    stats = {
        "total_documentation_url": 0,
        "empty": 0,
        "changed": 0,
        "already_target": 0,
        "skipped_other_host": 0,
        "skipped_other_language": 0,
    }

    for setting in root.findall(".//setting[@name='documentation_url']"):
        stats["total_documentation_url"] += 1
        current_url = setting.text or ""

        if current_url == "":
            stats["empty"] += 1
            continue

        parsed = urlsplit(current_url)
        if parsed.netloc != host:
            stats["skipped_other_host"] += 1
            continue

        if parsed.path.startswith(f"/{target_lang}/"):
            stats["already_target"] += 1
            continue

        new_url = localized_documentation_url(current_url, source_lang, target_lang)
        if new_url is None:
            stats["skipped_other_language"] += 1
            continue

        setting.text = new_url
        stats["changed"] += 1

    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return stats


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Genera un profilo CollectiveAccess con documentation_url puntati "
            "alla lingua Wiki.js inglese, senza modificare il profilo sorgente."
        )
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Profilo XML sorgente.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Profilo XML EN da scrivere.")
    parser.add_argument("--source-lang", default="it", help="Segmento lingua sorgente nei path Wiki.js.")
    parser.add_argument("--target-lang", default="en", help="Segmento lingua destinazione nei path Wiki.js.")
    parser.add_argument("--host", default="wiki.acusteme.org", help="Host Wiki.js da aggiornare.")
    return parser


def main():
    args = build_arg_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    stats = generate_profile(
        input_path=input_path,
        output_path=output_path,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        host=args.host,
    )

    print(f"Profilo sorgente: {input_path}")
    print(f"Profilo generato: {output_path}")
    print("Risultato documentation_url:")
    for key, value in stats.items():
        print(f" - {key}: {value}")


if __name__ == "__main__":
    main()
