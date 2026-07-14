import xml.etree.ElementTree as ET
import re
import sys
import requests
from pathlib import Path
import tempfile
import time

GEONAMES_USERNAME = 'imeandri'
GEONAMES_API = 'http://api.geonames.org/getJSON'
GEONAMES_HIERARCHY_API = 'http://api.geonames.org/hierarchyJSON'


def fetch_geoname(geoname_id: str, lang: str = 'en') -> dict:
    params = {'geonameId': geoname_id, 'username': GEONAMES_USERNAME, 'lang': lang}
    return _get_json(GEONAMES_API, params)


def fetch_hierarchy(geoname_id: str) -> list:
    params = {'geonameId': geoname_id, 'username': GEONAMES_USERNAME}
    return _get_json(GEONAMES_HIERARCHY_API, params).get('geonames', [])


def _get_json(url: str, params: dict) -> dict:
    """Richiesta GeoNames con timeout e retry per errori transitori."""
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise last_error


def get_effective_fcode(data: dict, gid: str) -> str:
    fcode = data.get('fcode', '')
    if fcode.startswith('ADM'):
        return fcode
    for node in reversed(fetch_hierarchy(gid)):
        fc = node.get('fcode', '')
        if fc.startswith('ADM'):
            return fc
    return fcode


def format_geoname(data: dict) -> str:
    gid = data.get('geonameId', '')
    fcode = get_effective_fcode(data, gid)
    name = data.get('name', '')
    admin_name1 = data.get('adminName1', '')
    country = data.get('countryName', '')
    continent = data.get('continentCode', '')
    lat = data.get('lat', '')
    lng = data.get('lng', '')

    parts = [fcode, name]
    if admin_name1 and admin_name1.lower() != name.lower():
        parts.append(admin_name1)
    parts += [country, continent]
    core = ", ".join(parts)
    return f"{core} [{lat},{lng}] [id:{gid}] "


def normalize_collana_numerazione(root) -> None:
    """
    Normalizza casi del tipo:
    <collana>Archivi Sonori [1]</collana>
    <numerazione_interno_collana>1</numerazione_interno_collana>

    in:

    <collana>Archivi Sonori</collana>
    <numerazione_interno_collana>1</numerazione_interno_collana>

    Solo se la collana termina con [numero].
    Se numerazione_interno_collana è già presente, aggiorna il valore.
    """
    pattern = re.compile(r'^(.*?)\s*\[(\d+)\]\s*$')

    for parent in root.iter():
        collana = parent.find('collana')
        if collana is None or not collana.text:
            continue

        original = collana.text.strip()
        match = pattern.match(original)
        if not match:
            continue

        collana_pulita, numero = match.groups()
        collana_pulita = collana_pulita.strip()

        if collana_pulita != original:
            print(
                f"Normalized <collana>: '{original}' -> '{collana_pulita}', "
                f"<numerazione_interno_collana>='{numero}'"
            )

        collana.text = collana_pulita

        num_tag = parent.find('numerazione_interno_collana')
        if num_tag is None:
            num_tag = ET.SubElement(parent, 'numerazione_interno_collana')
        num_tag.text = numero

def normalize_relator_codes(root) -> None:
    """
    Normalizza i codici relator:
    1) r55_26_xxx -> R55_100_xxx
    2) tutti i codici relator con iniziale r/R -> R
    Applica la normalizzazione a testo, tail e attributi.
    """
    pattern_specific = re.compile(r'r55_26_(\d+)', re.IGNORECASE)
    pattern_general = re.compile(r'\br(\d+_[0-9_]+)', re.IGNORECASE)

    def normalize_text(text: str) -> str:
        if not text:
            return text

        original = text

        # 1) r55_26_xxx -> R55_100_xxx
        text = pattern_specific.sub(r'R55_100_\1', text)

        # 2) qualunque codice relator r... -> R...
        text = pattern_general.sub(r'R\1', text)

        if text != original:
            print(f"Normalized relator text: '{original}' -> '{text}'")

        return text

    for elem in root.iter():
        # testo del nodo
        if elem.text:
            elem.text = normalize_text(elem.text)

        # testo dopo il nodo
        if elem.tail:
            elem.tail = normalize_text(elem.tail)

        # attributi
        for attr_name, attr_val in list(elem.attrib.items()):
            new_val = normalize_text(attr_val)
            if new_val != attr_val:
                print(
                    f"Normalized attribute {elem.tag}[@{attr_name}]: "
                    f"'{attr_val}' -> '{new_val}'"
                )
                elem.attrib[attr_name] = new_val

def process_file(input_path: str, output_path: str) -> None:
    """
    Elabora il file XML, applica tutte le trasformazioni e stampa log delle modifiche.
    """
    geo_pattern = re.compile(r'^(.*\[\s*-?\d+\.\d+,\s*-?\d+\.\d+\])\s*id:(\d+)\s*$')
    tree = ET.parse(input_path)
    root = tree.getroot()

    # Log iniziale
    print(f"Starting processing of {input_path}")

    # 0) Normalizzazione codici relator
    normalize_relator_codes(root)

    # 0b) Normalizzazione collana + numerazione interna tra quadre
    normalize_collana_numerazione(root)
    
    # 1) Trasforma tag GeoName, geonameurl e geoname_id
    for elem in root.iter():
        tag_l = elem.tag.lower()
        if tag_l in ('geoname', 'geonameurl', 'geoname_id'):
            text = (elem.text or '').strip()
            match = geo_pattern.match(text)
            if match and '[id:' not in text:
                coords, id_val = match.groups()
                new_text = f"{coords} [id:{id_val}] "
                print(f"Transformed <{elem.tag}>: '{text}' -> '{new_text}'")
                elem.text = new_text

    # 2) Genera geoname_city e geoname_country
    for parent in root.iter():
        for src_tag, tgt_tag in [('geonames_id', 'geoname_city'), ('country_geonames_id', 'geoname_country')]:
            src = parent.find(src_tag)
            if src is not None and src.text:
                gid = src.text.strip()
                try:
                    data = fetch_geoname(gid)
                    out_text = format_geoname(data)
                    target = parent.find(tgt_tag)
                    if target is None:
                        target = ET.SubElement(parent, tgt_tag)
                    target.text = out_text.strip()
                    print(f"Generated <{tgt_tag}> for ID {gid}: '{out_text}'")
                    # Gli identificatori sorgente vengono rimossi solo dopo il successo.
                    for t in ((src_tag, 'geonames_url') if src_tag == 'geonames_id'
                              else (src_tag, 'country_geonames_url')):
                        old = parent.find(t)
                        if old is not None:
                            print(f"Removed original tag <{t}> with value '{(old.text or '').strip()}'")
                            parent.remove(old)
                except Exception as e:
                    print(f"Error fetching GeoName for ID {gid}: {e}")

    # 3) Post-processing Wikidata semplici
    for elem in root.iter():
        lbl = elem.find('label')
        url = elem.find('url')
        if lbl is not None and url is not None:
            u = (url.text or '').strip()
            if 'wikidata.org/entity/' in u:
                lt = (lbl.text or '')
                idxs = [i for i in [lt.find('['), lt.find('('), lt.find('|')] if i != -1]
                idx = min(idxs) if idxs else len(lt)
                principal = lt[:idx].strip()
                qid = u.rstrip('/').split('/')[-1]
                ca = f"{principal}|{qid}|{u}"
                print(f"Converted WD tag: label '{principal}', QID '{qid}', URL '{u}'")
                for child in list(elem):
                    elem.remove(child)
                ET.SubElement(elem, 'CA_WD_string').text = ca

    # 4) Post-processing Hornbostel-Sachs multi
    for val in root.iter('Value'):
        cl = val.find('Classificazione_Hornbostel_Sachs_da_Wikidata')
        ur = val.find('URL')
        if cl is not None and ur is not None and cl.text and ur.text:
            labs = [x.strip() for x in cl.text.split(';') if x.strip()]
            urls = [x.strip() for x in ur.text.split(';') if x.strip()]
            if len(labs) != len(urls):
                raise ValueError(f"Hornbostel-Sachs: {len(labs)} label ma {len(urls)} URL")
            pairs = [f"{lab}|{u.rstrip('/').split('/')[-1]}|{u}" for lab, u in zip(labs, urls)]
            ca = ';'.join(pairs)
            print(f"Converted Hornbostel-Sachs: '{cl.text}' + '{ur.text}' -> '{ca}'")
            val.remove(cl)
            val.remove(ur)
            ET.SubElement(val, 'CA_WD_string').text = ca

    # 5) Post-processing keywords MIMO all languages
    for kmimo in root.iter('keywords_MIMO_all_languages'):
        labels = [e.text.strip() for e in kmimo.findall('keyword_all_languages') if e.text]
        urls = [e.text.strip() for e in kmimo.findall('URL') if e.text]
        if len(labels) != len(urls):
            raise ValueError(f"MIMO all languages: {len(labels)} label ma {len(urls)} URL")
        pairs = [f"{lab}|{u.rstrip('/').split('/')[-1]}|{u}" for lab, u in zip(labels, urls)]
        ca = ';'.join(pairs)
        print(f"Converted MIMO all_languages: {ca}")
        for child in list(kmimo):
            kmimo.remove(child)
        ET.SubElement(kmimo, 'CA_MIMO_string').text = ca

    # 6) Post-processing keywords MIMO italiano
    for kmimo in root.iter('keywords_MIMO_italiano'):
        labels = [e.text.strip() for e in kmimo.findall('keyword_italiano') if e.text]
        urls = [e.text.strip() for e in kmimo.findall('URL') if e.text]
        if len(labels) != len(urls):
            raise ValueError(f"MIMO italiano: {len(labels)} label ma {len(urls)} URL")
        pairs = [f"{lab}|{u.rstrip('/').split('/')[-1]}|{u}" for lab, u in zip(labels, urls)]
        ca = ';'.join(pairs)
        print(f"Converted MIMO italiano: {ca}")
        for child in list(kmimo):
            kmimo.remove(child)
        ET.SubElement(kmimo, 'CA_MIMO_string').text = ca

    # 7) Post-processing Materiali
    for mat in root.iter('Materiali'):
        labels = [e.text.strip() for e in mat.findall('Materiale') if e.text]
        urls = [e.text.strip() for e in mat.findall('URL') if e.text]
        if len(labels) != len(urls):
            raise ValueError(f"Materiali: {len(labels)} label ma {len(urls)} URL")
        pairs = [f"{lab}|{u.rstrip('/').split('/')[-1]}|{u}" for lab, u in zip(labels, urls)]
        ca = ';'.join(pairs)
        print(f"Converted Materiali: {ca}")
        for child in list(mat):
            mat.remove(child)
        ET.SubElement(mat, 'CA_WD_string').text = ca

    # 8) Comprimi Media_SCREEN
    for ms in root.iter('Media_SCREEN'):
        medias = ms.findall('Media')
        if medias:
            fns, urls = [], []
            for m in medias:
                fn = m.findtext('original_filename', '').strip()
                uu = m.findtext('url', '').strip()
                if fn: fns.append(fn)
                if uu: urls.append(uu)
                ms.remove(m)
            ca = fns, urls
            print(f"Compressed Media_SCREEN: filenames={fns}, urls={urls}")
            nm = ET.SubElement(ms, 'Media')
            ET.SubElement(nm, 'original_filename').text = ';'.join(fns)
            ET.SubElement(nm, 'url').text = ';'.join(urls)

    # Finito
    print(f"Finished processing. Output written to {output_path}")
    if hasattr(ET, "indent"): ET.indent(tree, space="  ")
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('wb', dir=destination.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
        tree.write(tmp, encoding='utf-8', xml_declaration=True)
    temporary.replace(destination)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python XMLpostprocess.py input.xml output.xml')
        sys.exit(1)
    process_file(sys.argv[1], sys.argv[2])
