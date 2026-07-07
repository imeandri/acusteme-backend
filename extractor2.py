import os
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote

# Path to the XML file
script_dir = os.path.dirname(os.path.abspath(__file__))
xml_file = os.path.join(script_dir, 'ACUSTEME_profile.xml')

# Load and parse the XML file
tree = ET.parse(xml_file)
root = tree.getroot()

def extract_italian_label(placement):
    for setting in placement.findall("settings/setting"):
        if setting.attrib.get('name') == 'label' and setting.attrib.get('locale') == 'it_IT':
            return setting.text
    return None

def extract_italian_description(placement):
    for setting in placement.findall("settings/setting"):
        if setting.attrib.get('name') == 'description' and setting.attrib.get('locale') == 'it_IT':
            return setting.text
    return None

def extract_code_from_bundle(bundle_code):
    return bundle_code.split('.', 1)[-1]

def extract_metadata_info(bundle_code):
    metadato = bundle_code.split('.', 1)[-1]
    metadata_element = root.find(f".//metadataElement[@code='{metadato}']")
    if metadata_element is None:
        return metadato, 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', '0', 'N/A'

    datatype = metadata_element.attrib.get('datatype', 'N/A')
    label = metadata_element.findtext("labels/label[@locale='it_IT']/name", 'N/A')
    description = metadata_element.findtext("labels/label[@locale='it_IT']/description", 'N/A')
    vocabulary = metadata_element.findtext("settings/setting[@name='vocabulary']", 'N/A')
    sparql_query = metadata_element.findtext("settings/setting[@name='querySparql']", 'N/A')
    require_value = metadata_element.findtext("settings/setting[@name='requireValue']", '0')
    max_attributes = metadata_element.findtext("typeRestrictions/restriction/settings/setting[@name='maxAttributesPerRow']", 'N/A')

    return metadato, datatype, label, description, vocabulary, sparql_query, require_value, max_attributes

def list_placements(ui_code, screen_index):
    results = []
    screen_label = 'N/A'
    screen_idno = 'N/A'
    user_interface = root.find(f".//userInterface[@code='{ui_code}']")
    if user_interface is None:
        return results, False, screen_label, screen_idno

    screens = user_interface.findall("screens/screen")
    if not (1 <= screen_index <= len(screens)):
        print(f"Screen index {screen_index} out of range.")
        return results, True, screen_label, screen_idno

    screen = screens[screen_index - 1]
    screen_label = screen.findtext("labels/label[@locale='it_IT']/name", 'N/A')
    screen_idno = screen.attrib.get('idno', 'N/A')
    placements = screen.findall("bundlePlacements/placement")
    
    for j, placement in enumerate(placements):
        label = extract_italian_label(placement) or 'N/A'
        description = extract_italian_description(placement) or 'N/A'
        bundle_code_elem = placement.find("bundle")
        vocabulary = 'N/A'
        sparql_query = 'N/A'
        require_value = '0'
        max_attributes = 'N/A'

        if bundle_code_elem is not None:
            bundle_code = extract_code_from_bundle(bundle_code_elem.text)
            if bundle_code in ["ca_objects", "ca_entities", "idno", "status", "access"]:
                datatype = {
                    "ca_objects": "Relazione",
                    "ca_entities": "Relazione",
                    "idno": "Identificativo",
                    "status": "Informazione",
                    "access": "Informazione"
                }[bundle_code]
                label = {
                    "ca_objects": "Relazioni a Risorse",
                    "ca_entities": "Relazioni ad Agenti",
                    "idno": "Identificativo",
                    "status": "Informazioni sullo status della scheda",
                    "access": "Informazioni di accesso sui dati della scheda"
                }[bundle_code]
            else:
                metadato, datatype, metadata_label, metadata_description, metadata_vocabulary, metadata_sparql_query, require_value, max_attributes = extract_metadata_info(bundle_code)
                label = label if label != 'N/A' else metadata_label
                description = description if description != 'N/A' else metadata_description
                vocabulary = metadata_vocabulary
                sparql_query = metadata_sparql_query
        else:
            bundle_code = 'N/A'

        require_value_elem = placement.find("settings/setting[@name='requireValue']")
        if require_value_elem is not None:
            require_value = require_value_elem.text

        obbligatorietà = "Sì" if require_value == '1' else "No"
        ripetibilità = {
            '1': "No",
            '2': "Sì (max 2 volte)",
            '3': "Sì (max 3 volte)",
        }.get(max_attributes, "Sì" if max_attributes != 'N/A' else "No")

        results.append((f"1.{j+1}", bundle_code, datatype, label, description, obbligatorietà, ripetibilità, sparql_query, vocabulary))

        if f"1.{j+1}".count('.') == 1:
            update_documentation_url(placement, ui_code, bundle_code, screen_idno)

        if datatype == 'Container':
            nested_results = list_nested_metadata(bundle_code, f"1.{j+1}", ui_code, screen_idno)
            results.extend(nested_results)

    return results, True, screen_label, screen_idno

def list_nested_metadata(parent_code, parent_numerale, ui_code, screen_idno):
    nested_results = []
    container_element = root.find(f".//metadataElement[@code='{parent_code}']")
    if container_element is not None:
        child_elements = container_element.findall("elements/metadataElement")
        for k, child in enumerate(child_elements):
            child_code = child.attrib.get('code', 'N/A')
            child_datatype = child.attrib.get('datatype', 'N/A')

            # Skip nested containers
            if child_datatype == 'Container':
                nested_results.extend(list_nested_metadata(child_code, parent_numerale, ui_code, screen_idno))
                continue

            child_label = child.findtext("labels/label[@locale='it_IT']/name", 'N/A')
            child_description = child.findtext("labels/label[@locale='it_IT']/description", 'N/A')
            child_vocabulary = 'N/A'
            child_sparql_query = 'N/A'

            if child_datatype == 'LCSH':
                child_vocabulary = child.findtext("settings/setting[@name='vocabulary']", 'N/A')
                if child_vocabulary.startswith("cs:"):
                    child_vocabulary = child_vocabulary[3:]
            elif child_datatype == 'InformationService':
                child_sparql_query = child.findtext("settings/setting[@name='querySparql']", 'N/A')

            numerale = f"{parent_numerale}.{k+1}"
            nested_results.append((numerale, child_code, child_datatype, child_label, child_description, 'N/A', 'N/A', child_sparql_query, child_vocabulary))

    return nested_results

def update_documentation_url(element, ui_code, element_code, screen_idno):
    doc_url_elem = element.find("settings/setting[@name='documentation_url']")
    if doc_url_elem is None:
        settings = element.find("settings")
        if settings is None:
            settings = ET.SubElement(element, "settings")
        doc_url_elem = ET.SubElement(settings, "setting", name="documentation_url")

    new_url = f"https://wiki.acusteme.org/it/{ui_code}/{screen_idno}.html#{element_code}"
    doc_url_elem.text = new_url

    # Debugging: Print the updated element
    print(f"Updated documentation URL for {element_code} to {new_url}")
    print(f"Placement updated: {ET.tostring(element, 'unicode')}")

def comment_regex_placeholders(query):
    lines = query.split('\n')
    commented_lines = []
    for line in lines:
        if 'REGEX' in line and 'PLACEHOLDER' in line:
            commented_lines.append('# ' + line)
        else:
            commented_lines.append(line)
    return '\n'.join(commented_lines)

def create_wikidata_query_link(query):
    commented_query = comment_regex_placeholders(query)
    base_url = "https://query.wikidata.org/embed.html#"
    return base_url + quote(commented_query)

def generate_html_documentation(elements, screen_label, ui_code, screen_idno):
    html_documentation = "<html>\n<head>\n"
    html_documentation += f"<title>{screen_label}</title>\n"
    html_documentation += '<meta charset="UTF-8">\n'
    html_documentation += '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/bulma/0.9.3/css/bulma.min.css">\n'
    html_documentation += '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.23.0/themes/prism.min.css">\n'
    html_documentation += "</head>\n<body>\n"

    for elem in elements:
        numerale, code, datatype, label, description, obbligatorietà, ripetibilità, sparql_query, vocabulary = elem
        heading_level = f"h{min(numerale.count('.') + 2, 5)}"

        if numerale.count('.') > 0:
            html_documentation += f'<{heading_level} class="toc-header" id="{code}">{numerale} {label}</{heading_level}>\n'
            blockquote_content = []

            blockquote_content.append(f'<p><strong>Datatype:</strong> {datatype}</p>')
            blockquote_content.append(f'<p><strong>CA element code:</strong> {code}</p>')

            if blockquote_content:
                html_documentation += f'<blockquote class="is-info">{" ".join(blockquote_content)}</blockquote>\n'

            if obbligatorietà == "Sì":
                html_documentation += f'<blockquote class="is-warning"><p><strong>Obbligatorietà:</strong> {obbligatorietà}</p></blockquote>\n'

            if numerale.count('.') == 1 and ripetibilità != "No":
                html_documentation += f'<blockquote class="is-info"><p><strong>Ripetibilità:</strong> {ripetibilità}</p></blockquote>\n'
            
            if description != 'N/A':
                html_documentation += f'<blockquote class="is-success"><p><strong>Quicktip:</strong> {description}</p></blockquote>\n'
            
            if sparql_query != 'N/A':
                query_link = create_wikidata_query_link(sparql_query)
                html_documentation += (
                    f'<blockquote class="is-warning"><p>Campo Linked Data: '
                    f'Per i termini ammissibili, aggiornati al <span class="dynamic-datetime"></span>, clicca sul seguente link per eseguire la query in tempo reale: '
                    f'<a class="is-external-link" href="{query_link}" target="_blank">Esegui Query</a> '
                    f'(attenzione: per query complesse occorre attendere diversi secondi prima della restituzione dei risultati).</p></blockquote>\n'
                    f'<button class="query-toggle-button" data-target="{code}-query">Mostra Query</button>\n'
                    f'<blockquote id="{code}-query" style="display:none;"><pre v-pre="true" class="prismjs line-numbers"><code class="language-sparql">{sparql_query}</code></pre></blockquote>\n'
                )
            
            if vocabulary != 'N/A':
                html_documentation += (
                    f'<blockquote class="is-warning"><p><strong>Vocabolario LoC (Library of Congress):</strong> '
                    f'Per i termini di vocabolario aggiornati al <span class="dynamic-datetime"></span>, clicca sul seguente link: '
                    f'<a class="is-external-link" href="{vocabulary}" target="_blank">Vocabolario</a>.</p></blockquote>\n'
                )
            
            html_documentation += f'<p>Esempi d\'uso: <span class="placeholder">{{to be completed}}</span></p>\n'

    html_documentation += "</body>\n</html>"
    return html_documentation

def main():
    while True:
        ui_code = input("Inserisci il codice della user interface (o 'exit' per uscire): ").strip()
        if ui_code.lower() == 'exit':
            break

        user_interface = root.find(f".//userInterface[@code='{ui_code}']")
        if user_interface is None:
            print(f"User Interface '{ui_code}' non trovata. Riprova.")
            continue

        screens = user_interface.findall("screens/screen")
        print(f"Screens disponibili per '{ui_code}':")
        for i, screen in enumerate(screens):
            screen_name = screen.findtext("labels/label[@locale='it_IT']/name", 'N/A')
            print(f"{i + 1}. {screen_name}")

        while True:
            try:
                screen_index = int(input("Inserisci il numero dello screen: "))
                if 1 <= screen_index <= len(screens):
                    break
                else:
                    print("Numero dello screen fuori dall'intervallo disponibile. Riprova.")
            except ValueError:
                print("Input non valido. Inserisci un numero intero valido per lo screen.")

        placements, ui_exists, screen_label, screen_idno = list_placements(ui_code, screen_index)
        if not ui_exists:
            print(f"Screen '{screen_index}' non trovato nella User Interface '{ui_code}'.")
            continue

        for placement in placements:
            print(f"\033[33mPlacement {placement[0]} - Code: {placement[1]}, Label: {placement[3]}, Description: {placement[4]}\033[0m")
            if placement[7] != 'N/A':
                print(f"  SPARQL query: {placement[7]}")
            if placement[8] != 'N/A':
                print(f"  Vocabulary: {placement[8]}")
            if placement[5] == "Sì":
                print(f"  Obbligatorio: Sì")
            else:
                print(f"  Obbligatorio: No")
            if placement[6] != "No" and placement[0].count('.') == 1:
                print(f"  Ripetibilità: {placement[6]}")
            print("--------------------------------------------------")

        generate_choice = input("Vuoi generare la documentazione per questo screen? (Sì/NO): ").strip().lower()
        if generate_choice in ['sì', 'si', 'yes', 'y']:
            html_doc = generate_html_documentation(placements, screen_label, ui_code, screen_idno)
            html_filename = f"{screen_idno}.html"
            with open(html_filename, "w", encoding='utf-8') as file:
                file.write(html_doc)
            print(f"Documentazione generata: {html_filename}")

            # Save the updated XML
            tree.write(xml_file, encoding='utf-8', xml_declaration=True)
            print(f"XML aggiornato salvato in {xml_file}")

if __name__ == "__main__":
    main()
