import xml.etree.ElementTree as ET
import argparse
from collections import Counter
from html import escape
from pathlib import Path


def extract_flat_relationships(xml_path):
    """
    Estrae tutte le relazioni sotto <relationshipTypes> in formato “piatto”.
    Ritorna una lista di dizionari con:
      - table_name
      - code
      - typename_it
      - typename_reverse_it
      - typename_en
      - typename_reverse_en
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    flat_list = []

    rel_types = root.find(".//relationshipTypes")
    if rel_types is None:
        return flat_list

    for table in rel_types.findall(".//relationshipTable"):
        table_name = table.get("name")
        if not table_name:
            continue

        # Element.iter visita ogni nodo una sola volta; l'XPath precedente
        # restituiva più volte i type annidati attraverso diversi antenati <types>.
        for subtype in (node for node in table.iter() if node.tag.split("}")[-1] == "type"):
            sub_code = subtype.get("code")
            if not sub_code:
                continue

            typename_it = ""
            typename_reverse_it = ""
            typename_en = ""
            typename_reverse_en = ""

            labels_elem = subtype.find("labels")
            if labels_elem is not None:
                for label in labels_elem.findall("label"):
                    locale = label.get("locale", "").strip()
                    forward = label.find("typename")
                    reverse = label.find("typename_reverse")

                    if locale == "it_IT":
                        if forward is not None and forward.text:
                            typename_it = forward.text.strip()
                        if reverse is not None and reverse.text:
                            typename_reverse_it = reverse.text.strip()

                    elif locale == "en_US":
                        if forward is not None and forward.text:
                            typename_en = forward.text.strip()
                        if reverse is not None and reverse.text:
                            typename_reverse_en = reverse.text.strip()

            flat_list.append({
                "table_name": table_name,
                "code": sub_code,
                "typename_it": typename_it,
                "typename_reverse_it": typename_reverse_it,
                "typename_en": typename_en,
                "typename_reverse_en": typename_reverse_en
            })

    return flat_list


def extract_hierarchy(xml_path, parent_codes):
    """
    Per ciascun codice in parent_codes (es. "relator_code", "acu_relators", "RICO_relations"),
    trova l'elemento <type code="..."> e lo restituisce in un dizionario.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    result = {}

    for parent_code in parent_codes:
        node = root.find(f".//type[@code='{parent_code}']")
        result[parent_code] = node  # None se non trovato

    return result


def render_type_tree(elem):
    """
    Riceve un Element <type> e restituisce una stringa HTML <li>…</li> (con eventuali <ul> nidificati)
    che mostra:
      - code
      - forward typename (IT e/o EN) in <span class="copy-relation" data-text="…"><strong>…</strong></span>
      - reverse tra parentesi
    Senza alcun onclick, perché il JS verrà caricato separatamente.
    """
    if elem is None:
        return "<li><em>Nessun nodo trovato.</em></li>"

    def get_label_text(type_elem, locale, forward=True):
        labels_elem = type_elem.find("labels")
        if labels_elem is None:
            return ""
        for lbl in labels_elem.findall("label"):
            if lbl.get("locale", "").strip() == locale:
                t = lbl.find("typename") if forward else lbl.find("typename_reverse")
                if t is not None and t.text:
                    return t.text.strip()
        return ""

    code = elem.get("code", "")
    it_forward = get_label_text(elem, "it_IT", forward=True)
    it_reverse = get_label_text(elem, "it_IT", forward=False)
    en_forward = get_label_text(elem, "en_US", forward=True)
    en_reverse = get_label_text(elem, "en_US", forward=False)

    parts = []
    # 1) mostro il codice plain
    if code:
        parts.append(escape(code))

    # 2) se esiste typename IT, lo inserisco in <span class="copy-relation" data-text="…"><strong>…</strong></span>
    if it_forward:
        parts.append(
            f'<span class="copy-relation" data-text="{escape(it_forward, quote=True)}" '
            f'style="cursor:pointer;" title="Clicca per copiare">'
            f'<strong>{escape(it_forward)}</strong>'
            '</span>'
        )

    # 3) se esiste typename EN, stesso meccanismo
    if en_forward:
        parts.append(
            f'<span class="copy-relation" data-text="{escape(en_forward, quote=True)}" '
            f'style="cursor:pointer;" title="Clicca per copiare">'
            f'<strong>{escape(en_forward)}</strong>'
            '</span>'
        )

    # 4) i reverse (IT e/o EN) tra parentesi
    if it_reverse:
        parts.append(f"(rev IT: {escape(it_reverse)})")
    if en_reverse:
        parts.append(f"(rev EN: {escape(en_reverse)})")

    this_text = " – ".join(parts) if parts else "(n/d)"
    children = elem.findall("./types/type")

    if not children:
        return f"<li>{this_text}</li>"

    # se ci sono figli, ricorsione
    html = [f"<li>{this_text}", '<ul style="list-style-type:none;padding-left:20px;">']
    for child in children:
        html.append(render_type_tree(child))
    html.append("</ul></li>")
    return "\n".join(html)


def build_html_page(xml_path, html_path):
    parent_codes = ["relator_code", "acu_relators", "RICO_relations"]
    hierarchies = extract_hierarchy(xml_path, parent_codes)
    flat = extract_flat_relationships(xml_path)
    duplicate_pairs = [pair for pair, count in Counter((row["table_name"], row["code"]) for row in flat).items() if count > 1]

    html_parts = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append("<html lang='it'>")
    html_parts.append("<head>")
    html_parts.append("  <meta charset='utf-8'>")
    html_parts.append("  <title>Relazioni ACUSTEME – Struttura e Tabelle</title>")
    html_parts.append("</head>")
    html_parts.append("<body style=\"font-family:Arial,sans-serif;margin:20px;background:#fafafa;\">")

    html_parts.append("  <h1 style=\"color:#333;\">Relazioni ACUSTEME</h1>")
    if duplicate_pairs:
        preview = ", ".join(f"{escape(table)}:{escape(code)}" for table, code in duplicate_pairs[:20])
        html_parts.append(
            '<p style="padding:10px;border-left:4px solid #c00;background:#fee;">'
            f'<strong>Attenzione:</strong> codici duplicati nel profilo: {preview}</p>'
        )
    html_parts.append("  <p style=\"font-size:0.9em;color:#666;margin-bottom:20px;\">"
                      "Qui di seguito trovi:")
    html_parts.append("    <ul>")
    html_parts.append("      <li>La <strong>gerarchia</strong> dei tre gruppi principali "
                      "(<code>relator_code</code>, <code>acu_relators</code>, <code>RICO_relations</code>), "
                      "visualizzata come mini-albero espandibile.</li>")
    html_parts.append("      <li>Una <strong>tabella globale</strong> con tutte le "
                      "<code>relationshipTable</code> estratte, in formato “piatto”.</li>")
    html_parts.append("    </ul>")
    html_parts.append("  </p>")

    # STILI INLINE PER I TRE GRUPPI
    relator_style = ("background-color:#ffeaea;"
                     "border-left:4px solid #e03e3e;"
                     "padding:10px 15px;"
                     "margin-bottom:30px;"
                     "border-radius:4px;")
    acu_style     = ("background-color:#eaffea;"
                     "border-left:4px solid #3ea03e;"
                     "padding:10px 15px;"
                     "margin-bottom:30px;"
                     "border-radius:4px;")
    rico_style    = ("background-color:#eaeaff;"
                     "border-left:4px solid #3e3ee0;"
                     "padding:10px 15px;"
                     "margin-bottom:30px;"
                     "border-radius:4px;")

    # 1) RELATOR CODE
    node_rel = hierarchies.get("relator_code")
    html_parts.append(f'  <details open style="{relator_style}">')
    html_parts.append('    <summary style="font-size:1.1em;font-weight:bold;cursor:pointer;">'
                      'Relator Code</summary>')
    if node_rel is None:
        html_parts.append('    <p><em>Nessun nodo trovato per relator_code.</em></p>')
    else:
        html_parts.append('    <ul style="list-style-type:none;padding-left:20px;">')
        html_parts.append(render_type_tree(node_rel))
        html_parts.append('    </ul>')
    html_parts.append('  </details>')

    # 2) ACU RELATORS
    node_acu = hierarchies.get("acu_relators")
    html_parts.append(f'  <details open style="{acu_style}">')
    html_parts.append('    <summary style="font-size:1.1em;font-weight:bold;cursor:pointer;">'
                      'ACU Relators</summary>')
    if node_acu is None:
        html_parts.append('    <p><em>Nessun nodo trovato per acu_relators.</em></p>')
    else:
        html_parts.append('    <ul style="list-style-type:none;padding-left:20px;">')
        html_parts.append(render_type_tree(node_acu))
        html_parts.append('    </ul>')
    html_parts.append('  </details>')

    # 3) RICO RELATIONS
    node_rico = hierarchies.get("RICO_relations")
    html_parts.append(f'  <details open style="{rico_style}">')
    html_parts.append('    <summary style="font-size:1.1em;font-weight:bold;cursor:pointer;">'
                      'RICO Relations</summary>')
    if node_rico is None:
        html_parts.append('    <p><em>Nessun nodo trovato per RICO_relations.</em></p>')
    else:
        html_parts.append('    <ul style="list-style-type:none;padding-left:20px;">')
        html_parts.append(render_type_tree(node_rico))
        html_parts.append('    </ul>')
    html_parts.append('  </details>')

    # 4) TABELLA “PIATTA”
    html_parts.append('  <h2 style="border-bottom:2px solid #444;padding-bottom:4px;color:#333;'
                      'margin-top:40px;">'
                      'Tabella Completa delle <code>relationshipTable</code></h2>')
    html_parts.append('  <table style="width:100%;border-collapse:collapse;margin-bottom:40px;'
                      'box-shadow:0 2px 5px rgba(0,0,0,0.1);background:#fff;">')
    html_parts.append('    <thead>')
    html_parts.append('      <tr>')
    html_parts.append('        <th style="border:1px solid #ddd;padding:8px;text-align:left;'
                      'background:#f0f0f0;color:#222;">Tabella</th>')
    html_parts.append('        <th style="border:1px solid #ddd;padding:8px;text-align:left;'
                      'background:#f0f0f0;color:#222;">Code</th>')
    html_parts.append('        <th style="border:1px solid #ddd;padding:8px;text-align:left;'
                      'background:#f0f0f0;color:#222;">Typename (IT)</th>')
    html_parts.append('        <th style="border:1px solid #ddd;padding:8px;text-align:left;'
                      'background:#f0f0f0;color:#222;">Typename Reverse (IT)</th>')
    html_parts.append('        <th style="border:1px solid #ddd;padding:8px;text-align:left;'
                      'background:#f0f0f0;color:#222;">Typename (EN)</th>')
    html_parts.append('        <th style="border:1px solid #ddd;padding:8px;text-align:left;'
                      'background:#f0f0f0;color:#222;">Typename Reverse (EN)</th>')
    html_parts.append('      </tr>')
    html_parts.append('    </thead>')
    html_parts.append('    <tbody>')

    for item in flat:
        html_parts.append('      <tr>')
        html_parts.append(f'        <td style="border:1px solid #ddd;padding:8px;">'
                          f'{escape(item["table_name"])}</td>')
        html_parts.append(f'        <td style="border:1px solid #ddd;padding:8px;">'
                          f'{escape(item["code"])}</td>')
        html_parts.append(f'        <td style="border:1px solid #ddd;padding:8px;">'
                          f'{escape(item["typename_it"])}</td>')
        html_parts.append(f'        <td style="border:1px solid #ddd;padding:8px;">'
                          f'{escape(item["typename_reverse_it"])}</td>')
        html_parts.append(f'        <td style="border:1px solid #ddd;padding:8px;">'
                          f'{escape(item["typename_en"])}</td>')
        html_parts.append(f'        <td style="border:1px solid #ddd;padding:8px;">'
                          f'{escape(item["typename_reverse_en"])}</td>')
        html_parts.append('      </tr>')

    html_parts.append('    </tbody>')
    html_parts.append('  </table>')

    html_parts.append('</body>')
    html_parts.append('</html>')

    # Scrivo il file HTML
    destination = Path(html_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Estrae e documenta le relationship table del profilo CA")
    default_profile = Path(__file__).resolve().parents[3] / "install-profiles" / "acusteme" / "ACUSTEME_profile.xml"
    parser.add_argument("profile", nargs="?", default=default_profile)
    parser.add_argument("output", nargs="?", default="relationships.html")
    args = parser.parse_args()
    build_html_page(args.profile, args.output)
    print(f"Creato file HTML: {args.output}")
