import argparse
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import escape as html_escape
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from sparql_query_tools import neutralize_placeholder_regexes
from wikijs_manual_regions import build_manual_region


script_dir = Path(__file__).resolve().parent
DEFAULT_XML_SOURCE = (
    "https://raw.githubusercontent.com/imeandri/acusteme-backend/"
    "main/ACUSTEME_profile.xml"
)


ALLOWED_UI_CODES = {
    "campagna_di_ricerca",
    "cueM",
    "process",
    "Collezione_UI",
    "biblio_resource",
    "campagna_di_catalogazione",
    "descrizione_modello_3d",
    "entity_ui",
    "esemplare",
    "esposizione_ui",
    "indice_consolidato",
    "annotation_segmentation",
    "interstitial_entity_ui",
    "localizzazione_indice_cons",
    "object_ui",
    "oggetto_entita",
    "item_agent",
    "object_object_interstitial",
    "SilentFilm_object_object_interstitial1",
    "SilentFilm_object_object_interstitial2",
    "object_object_interstitial_numeration",
    "object_object_interstitial_numeration_coll",
    "record_resource",
    "wk_clusterunit",
    "expression",
    "storage_locations_ui",
    "object_representation_ui",
}


@dataclass(frozen=True)
class LanguageConfig:
    code: str
    locale: str
    wiki_prefix: str
    output_root: Path
    required_yes: str
    required_no: str
    repeat_no: str
    repeat_yes: str
    repeat_max_template: str
    required_label: str
    repeat_label: str
    linked_data_text: str
    execute_query_label: str
    complex_query_note: str
    show_query_label: str
    vocabulary_label: str
    vocabulary_text: str
    vocabulary_link_label: str
    examples_label: str
    to_be_completed: str
    built_in_datatypes: dict[str, str]
    built_in_labels: dict[str, str]


@dataclass(frozen=True)
class DocumentationElement:
    numerale: str
    code: str
    datatype: str
    label: str
    description: str
    required: str
    repeatability: str
    sparql_query: str
    vocabulary: str
    manual_region_key: str


@dataclass(frozen=True)
class GeneratedDocumentationPage:
    language: str
    ui_code: str
    screen_idno: str
    screen_index: int
    title: str
    content: str
    relative_output_path: Path
    wiki_path: str


LANGUAGES = {
    "it": LanguageConfig(
        code="it",
        locale="it_IT",
        wiki_prefix="it",
        output_root=Path("."),
        required_yes="Sì",
        required_no="No",
        repeat_no="No",
        repeat_yes="Sì",
        repeat_max_template="Sì (max {count} volte)",
        required_label="Obbligatorietà",
        repeat_label="Ripetibilità",
        linked_data_text=(
            "Campo Linked Data: Per i termini ammissibili, aggiornati al "
            '<span class="dynamic-datetime"></span>, clicca sul seguente link '
            "per eseguire la query in tempo reale:"
        ),
        execute_query_label="Esegui Query",
        complex_query_note=(
            "attenzione: per query complesse occorre attendere diversi secondi "
            "prima della restituzione dei risultati"
        ),
        show_query_label="Mostra Query",
        vocabulary_label="Vocabolario LoC (Library of Congress)",
        vocabulary_text=(
            "Per i termini di vocabolario aggiornati al "
            '<span class="dynamic-datetime"></span>, clicca sul seguente link:'
        ),
        vocabulary_link_label="Vocabolario",
        examples_label="Esempi d'uso",
        to_be_completed="to be completed",
        built_in_datatypes={
            "ca_objects": "Relazione",
            "ca_entities": "Relazione",
            "idno": "Identificativo",
            "status": "Informazione",
            "access": "Informazione",
        },
        built_in_labels={
            "ca_objects": "Relazioni a Risorse",
            "ca_entities": "Relazioni ad Agenti",
            "idno": "Identificativo",
            "status": "Informazioni sullo status della scheda",
            "access": "Informazioni di accesso sui dati della scheda",
        },
    ),
    "en": LanguageConfig(
        code="en",
        locale="en_US",
        wiki_prefix="en",
        output_root=Path("en"),
        required_yes="Yes",
        required_no="No",
        repeat_no="No",
        repeat_yes="Yes",
        repeat_max_template="Yes (max {count} times)",
        required_label="Required",
        repeat_label="Repeatability",
        linked_data_text=(
            "Linked Data field: for the allowed terms, updated on "
            '<span class="dynamic-datetime"></span>, click the following link '
            "to run the query in real time:"
        ),
        execute_query_label="Run Query",
        complex_query_note=(
            "for complex queries, wait several seconds before results are returned"
        ),
        show_query_label="Show Query",
        vocabulary_label="LoC vocabulary (Library of Congress)",
        vocabulary_text=(
            "For vocabulary terms updated on "
            '<span class="dynamic-datetime"></span>, click the following link:'
        ),
        vocabulary_link_label="Vocabulary",
        examples_label="Usage examples",
        to_be_completed="to be completed",
        built_in_datatypes={
            "ca_objects": "Relationship",
            "ca_entities": "Relationship",
            "idno": "Identifier",
            "status": "Information",
            "access": "Information",
        },
        built_in_labels={
            "ca_objects": "Related Resources",
            "ca_entities": "Related Agents",
            "idno": "Identifier",
            "status": "Record status information",
            "access": "Record data access information",
        },
    ),
}


def label_text(element, locale, field, default="N/A"):
    return element.findtext(f"labels/label[@locale='{locale}']/{field}", default)


def extract_localized_setting(placement, locale, setting_name):
    for setting in placement.findall("settings/setting"):
        if setting.attrib.get("name") == setting_name and setting.attrib.get("locale") == locale:
            return setting.text
    return None


def extract_code_from_bundle(bundle_code):
    return bundle_code.split(".", 1)[-1]


def extract_metadata_info(root, bundle_code, lang):
    metadato = bundle_code.split(".", 1)[-1]
    metadata_element = root.find(f".//metadataElement[@code='{metadato}']")
    if metadata_element is None:
        return metadato, "N/A", "N/A", "N/A", "N/A", "N/A", "0", "N/A"

    datatype = metadata_element.attrib.get("datatype", "N/A")
    label = label_text(metadata_element, lang.locale, "name")
    description = label_text(metadata_element, lang.locale, "description")
    vocabulary = metadata_element.findtext("settings/setting[@name='vocabulary']", "N/A")
    sparql_query = metadata_element.findtext("settings/setting[@name='querySparql']", "N/A")
    require_value = metadata_element.findtext("settings/setting[@name='requireValue']", "0")
    max_attributes = metadata_element.findtext(
        "typeRestrictions/restriction/settings/setting[@name='maxAttributesPerRow']", "N/A"
    )

    return metadato, datatype, label, description, vocabulary, sparql_query, require_value, max_attributes


def list_nested_metadata(
    root,
    parent_code,
    parent_numerale,
    lang,
    region_prefix,
    metadata_path=(),
):
    nested_results = []
    container_element = root.find(f".//metadataElement[@code='{parent_code}']")
    if container_element is not None:
        child_elements = container_element.findall("elements/metadataElement")
        for k, child in enumerate(child_elements):
            child_code = child.attrib.get("code", "N/A")
            child_datatype = child.attrib.get("datatype", "N/A")
            child_path = metadata_path + (child_code,)

            if child_datatype == "Container":
                nested_results.extend(
                    list_nested_metadata(
                        root,
                        child_code,
                        parent_numerale,
                        lang,
                        region_prefix,
                        child_path,
                    )
                )
                continue

            child_label = label_text(child, lang.locale, "name")
            child_description = label_text(child, lang.locale, "description")
            child_vocabulary = "N/A"
            child_sparql_query = "N/A"

            if child_datatype == "LCSH":
                child_vocabulary = child.findtext("settings/setting[@name='vocabulary']", "N/A")
                if child_vocabulary.startswith("cs:"):
                    child_vocabulary = child_vocabulary[3:]
            elif child_datatype == "InformationService":
                child_sparql_query = child.findtext("settings/setting[@name='querySparql']", "N/A")

            numerale = f"{parent_numerale}.{k + 1}"
            nested_results.append(
                DocumentationElement(
                    numerale=numerale,
                    code=child_code,
                    datatype=child_datatype,
                    label=child_label,
                    description=child_description,
                    required="N/A",
                    repeatability="N/A",
                    sparql_query=child_sparql_query,
                    vocabulary=child_vocabulary,
                    manual_region_key=f"{region_prefix}/{'/'.join(child_path)}",
                )
            )

    return nested_results


def update_documentation_url(element, ui_code, element_code, screen_idno, lang):
    doc_url_elem = element.find("settings/setting[@name='documentation_url']")
    if doc_url_elem is None:
        settings = element.find("settings")
        if settings is None:
            settings = ET.SubElement(element, "settings")
        doc_url_elem = ET.SubElement(settings, "setting", name="documentation_url")

    new_url = (
        f"https://wiki.acusteme.org/{lang.wiki_prefix}/"
        f"acusteme_data_model/DM_documentation/{ui_code}/{screen_idno}.html#{element_code}"
    )
    doc_url_elem.text = new_url
    print(f"[{lang.code}] Updated documentation URL for {element_code} to {new_url}")


def create_wikidata_query_link(query):
    commented_query = neutralize_placeholder_regexes(query)
    base_url = "https://query.wikidata.org/embed.html#"
    return base_url + quote(commented_query)


def generate_html_documentation(elements, screen_label, lang):
    html_documentation = "<html>\n<head>\n"
    html_documentation += f"<title>{screen_label}</title>\n"
    html_documentation += '<meta charset="UTF-8">\n'
    html_documentation += (
        '<link rel="stylesheet" '
        'href="https://cdnjs.cloudflare.com/ajax/libs/bulma/0.9.3/css/bulma.min.css">\n'
    )
    html_documentation += (
        '<link rel="stylesheet" '
        'href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.23.0/themes/prism.min.css">\n'
    )
    html_documentation += "</head>\n<body>\n"

    for elem in elements:
        numerale = elem.numerale
        code = elem.code
        datatype = elem.datatype
        label = elem.label
        description = elem.description
        required = elem.required
        repeatability = elem.repeatability
        sparql_query = elem.sparql_query
        vocabulary = elem.vocabulary
        heading_level = f"h{min(numerale.count('.') + 2, 5)}"

        if numerale.count(".") > 0:
            html_documentation += f'<{heading_level} class="toc-header" id="{code}">{numerale} {label}</{heading_level}>\n'
            blockquote_content = [
                f"<p><strong>Datatype:</strong> {datatype}</p>",
                f"<p><strong>CA element code:</strong> {code}</p>",
            ]

            html_documentation += f'<blockquote class="is-info">{" ".join(blockquote_content)}</blockquote>\n'

            if required == lang.required_yes:
                html_documentation += (
                    f'<blockquote class="is-warning"><p><strong>{lang.required_label}:</strong> '
                    f"{required}</p></blockquote>\n"
                )

            if numerale.count(".") == 1 and repeatability != lang.repeat_no:
                html_documentation += (
                    f'<blockquote class="is-info"><p><strong>{lang.repeat_label}:</strong> '
                    f"{repeatability}</p></blockquote>\n"
                )

            if description != "N/A":
                html_documentation += (
                    f'<blockquote class="is-success"><p><strong>Quicktip:</strong> '
                    f"{description}</p></blockquote>\n"
                )

            if sparql_query != "N/A":
                query_link = create_wikidata_query_link(sparql_query)
                html_documentation += (
                    f'<blockquote class="is-warning"><p>{lang.linked_data_text} '
                    f'<a class="is-external-link" href="{query_link}" target="_blank">'
                    f"{lang.execute_query_label}</a> "
                    f"({lang.complex_query_note}).</p></blockquote>\n"
                    f'<button class="query-toggle-button" data-target="{code}-query">{lang.show_query_label}</button>\n'
                    f'<blockquote id="{code}-query" style="display:none;"><pre v-pre="true" '
                    f'class="prismjs line-numbers"><code class="language-sparql">'
                    f"{html_escape(sparql_query)}</code></pre></blockquote>\n"
                )

            if vocabulary != "N/A":
                html_documentation += (
                    f'<blockquote class="is-warning"><p><strong>{lang.vocabulary_label}:</strong> '
                    f'{lang.vocabulary_text} <a class="is-external-link" href="{vocabulary}" '
                    f'target="_blank">{lang.vocabulary_link_label}</a>.</p></blockquote>\n'
                )

            html_documentation += (
                build_manual_region(
                    elem.manual_region_key,
                    lang.examples_label,
                    lang.to_be_completed,
                )
                + "\n"
            )

    html_documentation += "</body>\n</html>"
    return html_documentation


def repeatability_label(max_attributes, lang):
    if max_attributes == "1":
        return lang.repeat_no
    if max_attributes in {"2", "3"}:
        return lang.repeat_max_template.format(count=max_attributes)
    if max_attributes != "N/A":
        return lang.repeat_yes
    return lang.repeat_no


def list_placements(root, ui_code, screen_index, lang, update_urls):
    results = []
    screen_label = "N/A"
    screen_idno = "N/A"
    user_interface = root.find(f".//userInterface[@code='{ui_code}']")
    if user_interface is None:
        return results, False, screen_label, screen_idno

    screens = user_interface.findall("screens/screen")
    if not (1 <= screen_index <= len(screens)):
        print(f"Screen index {screen_index} out of range.")
        return results, True, screen_label, screen_idno

    screen = screens[screen_index - 1]
    screen_label = label_text(screen, lang.locale, "name")
    screen_idno = screen.attrib.get("idno", "N/A")
    placements = screen.findall("bundlePlacements/placement")

    for j, placement in enumerate(placements):
        placement_code = placement.attrib.get("code")
        if not placement_code:
            raise ValueError(
                f"Placement without code in UI {ui_code!r}, screen {screen_idno!r}. "
                "A stable code is required for protected manual regions."
            )
        region_prefix = f"{ui_code}/{screen_idno}::{placement_code}"
        label = extract_localized_setting(placement, lang.locale, "label") or "N/A"
        description = extract_localized_setting(placement, lang.locale, "description") or "N/A"
        bundle_code_elem = placement.find("bundle")
        vocabulary = "N/A"
        sparql_query = "N/A"
        require_value = "0"
        max_attributes = "N/A"
        datatype = "N/A"

        if bundle_code_elem is not None:
            bundle_code = extract_code_from_bundle(bundle_code_elem.text)
            if bundle_code in lang.built_in_datatypes:
                datatype = lang.built_in_datatypes[bundle_code]
                label = lang.built_in_labels[bundle_code]
            else:
                (
                    metadato,
                    datatype,
                    metadata_label,
                    metadata_description,
                    metadata_vocabulary,
                    metadata_sparql_query,
                    require_value,
                    max_attributes,
                ) = extract_metadata_info(root, bundle_code, lang)
                label = label if label != "N/A" else metadata_label
                description = description if description != "N/A" else metadata_description
                vocabulary = metadata_vocabulary
                sparql_query = metadata_sparql_query
        else:
            bundle_code = "N/A"

        require_value_elem = placement.find("settings/setting[@name='requireValue']")
        if require_value_elem is not None:
            require_value = require_value_elem.text

        required = lang.required_yes if require_value == "1" else lang.required_no
        repeatability = repeatability_label(max_attributes, lang)

        numerale = f"1.{j + 1}"
        results.append(
            DocumentationElement(
                numerale=numerale,
                code=bundle_code,
                datatype=datatype,
                label=label,
                description=description,
                required=required,
                repeatability=repeatability,
                sparql_query=sparql_query,
                vocabulary=vocabulary,
                manual_region_key=region_prefix,
            )
        )

        if update_urls:
            update_documentation_url(placement, ui_code, bundle_code, screen_idno, lang)

        if datatype == "Container":
            results.extend(
                list_nested_metadata(
                    root,
                    bundle_code,
                    numerale,
                    lang,
                    region_prefix,
                )
            )

    return results, True, screen_label, screen_idno


def parse_languages(value):
    requested = [item.strip().lower() for item in value.split(",") if item.strip()]
    unknown = [item for item in requested if item not in LANGUAGES]
    if unknown:
        raise argparse.ArgumentTypeError(f"Lingue non supportate: {', '.join(unknown)}")
    return requested


def is_remote_xml_source(source):
    return source.startswith(("https://", "http://"))


def load_xml_profile(source):
    if not is_remote_xml_source(source):
        return ET.parse(Path(source))

    request = Request(
        source,
        headers={"User-Agent": "ACUSTEME-documentation-generator/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        return ET.ElementTree(ET.fromstring(response.read()))


def build_documentation_pages(
    root,
    language_codes=("it", "en"),
    target_ui_codes=None,
    update_documentation_url_for="none",
):
    """Generate the complete documentation corpus without writing files."""

    selected_ui_codes = set(target_ui_codes or ALLOWED_UI_CODES)
    pages = []
    for language_code in language_codes:
        lang = LANGUAGES[language_code]
        update_urls = update_documentation_url_for == lang.code
        for user_interface in root.findall(".//userInterface"):
            ui_code = user_interface.attrib.get("code", "N/A")
            if ui_code not in selected_ui_codes:
                continue

            screens = user_interface.findall("screens/screen")
            for screen_index in range(1, len(screens) + 1):
                elements, ui_exists, screen_label, screen_idno = list_placements(
                    root,
                    ui_code,
                    screen_index,
                    lang,
                    update_urls,
                )
                if not ui_exists:
                    continue
                content = generate_html_documentation(elements, screen_label, lang)
                pages.append(
                    GeneratedDocumentationPage(
                        language=lang.code,
                        ui_code=ui_code,
                        screen_idno=screen_idno,
                        screen_index=screen_index,
                        title=f"{screen_index:02d}_{screen_label}",
                        content=content,
                        relative_output_path=(
                            lang.output_root / ui_code / f"{screen_idno}.html"
                        ),
                        wiki_path=(
                            "acusteme_data_model/DM_documentation/"
                            f"{ui_code}/{screen_idno}"
                        ),
                    )
                )
    return pages


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Genera la documentazione HTML ACUSTEME in italiano e/o inglese."
    )
    parser.add_argument(
        "--xml",
        default=DEFAULT_XML_SOURCE,
        help=(
            "Profilo XML locale o URL. Default: profilo aureo sul branch main "
            "del repository GitHub ACUSTEME."
        ),
    )
    parser.add_argument(
        "--xml-output",
        help=(
            "File locale in cui salvare il profilo modificato. Obbligatorio "
            "quando --xml è un URL e si aggiornano i documentation_url."
        ),
    )
    parser.add_argument(
        "--languages",
        type=parse_languages,
        default=["it", "en"],
        help="Lingue da generare, separate da virgola. Default: it,en",
    )
    parser.add_argument(
        "--update-documentation-url-for",
        choices=["it", "en", "none"],
        default="none",
        help="Lingua per cui aggiornare documentation_url nel profilo XML. Default: none",
    )
    parser.add_argument(
        "--only-ui",
        action="append",
        choices=sorted(ALLOWED_UI_CODES),
        help="Limita la generazione a una o più UI. Ripeti l'opzione per più UI.",
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if (
        args.update_documentation_url_for != "none"
        and is_remote_xml_source(args.xml)
        and not args.xml_output
    ):
        parser.error(
            "--xml-output è obbligatorio quando il profilo XML è remoto e "
            "si aggiornano i documentation_url"
        )

    tree = load_xml_profile(args.xml)
    root = tree.getroot()
    target_ui_codes = set(args.only_ui) if args.only_ui else ALLOWED_UI_CODES
    pages = build_documentation_pages(
        root,
        args.languages,
        target_ui_codes,
        args.update_documentation_url_for,
    )

    for page in pages:
        html_filename = script_dir / page.relative_output_path
        html_filename.parent.mkdir(parents=True, exist_ok=True)
        html_filename.write_text(page.content, encoding="utf-8")
        print(f"[{page.language}] Documentazione generata: {html_filename}")

    if args.update_documentation_url_for != "none":
        xml_output = Path(args.xml_output or args.xml)
        tree.write(xml_output, encoding="utf-8", xml_declaration=True)
        print(f"\nXML aggiornato salvato in {xml_output}")
    else:
        print(f"\nProfilo sorgente non modificato: {args.xml}")


if __name__ == "__main__":
    main()
