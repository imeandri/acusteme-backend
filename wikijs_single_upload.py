from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import argparse
import getpass
import json
import os
import time
import re
from html import unescape
import xml.etree.ElementTree as ET


WIKI_URL = "https://wiki.acusteme.org"
DOC_BASE_PATH = "acusteme_data_model/DM_documentation"
SLOW_MO = 250
HEADLESS = False

XML_PROFILE_PATH = Path("ACUSTEME_profile.xml")
CONFIG_PATH = Path("wikijs_upload_config.json")

DEFAULT_TEMPLATE_HTML = "<h1>Title</h1>\n\n<p>Some text here</p>"

LANGUAGE_OUTPUT_ROOTS = {
    "it": Path("."),
    "en": Path("en"),
}


def wait_a_bit(seconds=1.2):
    time.sleep(seconds)


def slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", text)


def ui_root_for_language(language: str) -> Path:
    return LANGUAGE_OUTPUT_ROOTS[language]


def list_available_ui_dirs(language: str):
    excluded = {"venv", "__pycache__", "wikijs_debug"}
    root = ui_root_for_language(language)
    if not root.exists():
        return []

    return sorted(
        [
            p
            for p in root.iterdir()
            if p.is_dir() and p.name not in excluded and list(p.glob("*.html"))
        ]
    )


def get_screen_order_from_xml(ui_code: str) -> dict[str, int]:
    if not XML_PROFILE_PATH.exists():
        raise FileNotFoundError(f"Profilo XML non trovato: {XML_PROFILE_PATH}")

    tree = ET.parse(XML_PROFILE_PATH)
    root = tree.getroot()

    user_interface = root.find(f".//userInterface[@code='{ui_code}']")
    if user_interface is None:
        raise ValueError(f"UserInterface '{ui_code}' non trovata nel profilo XML.")

    screens = user_interface.findall("screens/screen")

    screen_order = {}
    for idx, screen in enumerate(screens, start=1):
        screen_idno = screen.attrib.get("idno")
        if screen_idno:
            screen_order[screen_idno] = idx

    return screen_order

def choose_ui_interactively(language: str):
    ui_dirs = list_available_ui_dirs(language)

    if not ui_dirs:
        root = ui_root_for_language(language)
        raise FileNotFoundError(f"Nessuna cartella UI con file HTML trovata in {root}.")

    print(f"User interfaces disponibili per lingua '{language}':\n")
    for i, ui_dir in enumerate(ui_dirs, start=1):
        html_count = len(list(ui_dir.glob("*.html")))
        print(f"{i}. {ui_dir.name} ({html_count} file HTML)")

    while True:
        choice = input("\nScegli il numero della UI da caricare: ").strip()

        if not choice.isdigit():
            print("Inserisci un numero valido.")
            continue

        idx = int(choice)
        if 1 <= idx <= len(ui_dirs):
            selected = ui_dirs[idx - 1].name
            print(f"\nHai scelto: {selected}")
            return selected

        print("Numero fuori intervallo.")


def choose_ui_sequence(language: str, all_ui: bool, selected_ui: list[str] | None):
    available_dirs = list_available_ui_dirs(language)
    available_by_name = {p.name: p for p in available_dirs}

    if selected_ui:
        missing = [ui for ui in selected_ui if ui not in available_by_name]
        if missing:
            root = ui_root_for_language(language)
            raise FileNotFoundError(f"UI non trovate in {root}: {', '.join(missing)}")
        return selected_ui

    if all_ui:
        if not available_dirs:
            root = ui_root_for_language(language)
            raise FileNotFoundError(f"Nessuna cartella UI con file HTML trovata in {root}.")
        return [p.name for p in available_dirs]

    return [choose_ui_interactively(language)]


def get_html_files_for_ui(ui_code: str, language: str):
    ui_dir = ui_root_for_language(language) / ui_code
    if not ui_dir.exists() or not ui_dir.is_dir():
        raise FileNotFoundError(f"Cartella UI non trovata: {ui_dir}")
    return sorted(ui_dir.glob("*.html"))


def page_path_for(ui_code: str, html_file: Path, language: str) -> str:
    return f"{DOC_BASE_PATH}/{ui_code}/{html_file.stem}"


def extract_html_title(html_content: str) -> str | None:
    match = re.search(r"<title>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    if not match:
        return None

    title = unescape(match.group(1)).strip()
    title = re.sub(r"\s+", " ", title)

    if title == "":
        return None

    return title


def page_title_for(html_file: Path, html_content: str, screen_order: dict[str, int]) -> str:
    extracted_title = extract_html_title(html_content)
    base_title = extracted_title if extracted_title else html_file.stem

    screen_id = html_file.stem
    index = screen_order.get(screen_id)

    if index is None:
        # fallback: se lo screen non è nel profilo XML, niente numerazione
        return base_title

    return f"{index:02d}_{base_title}"


def debug_dump(page, label: str):
    debug_dir = Path("wikijs_debug")
    debug_dir.mkdir(exist_ok=True)

    safe = slugify(label)
    png_path = debug_dir / f"{safe}.png"
    html_path = debug_dir / f"{safe}.html"

    try:
        page.screenshot(path=str(png_path), full_page=True)
        print(f"[DEBUG] Screenshot salvato: {png_path}")
    except Exception as e:
        print(f"[DEBUG] Errore screenshot: {e}")

    try:
        html = page.content()
        html_path.write_text(html, encoding="utf-8")
        print(f"[DEBUG] HTML salvato: {html_path}")
    except Exception as e:
        print(f"[DEBUG] Errore dump HTML: {e}")


def wiki_home_url(language: str | None = None) -> str:
    return WIKI_URL


def wiki_login_url() -> str:
    return f"{WIKI_URL}/login"


def open_home(page, language: str):
    page.goto(wiki_home_url(language), wait_until="domcontentloaded")
    wait_a_bit(1.5)


def open_login(page):
    page.goto(wiki_login_url(), wait_until="domcontentloaded")
    wait_a_bit(1.5)


def load_config() -> dict:
    config = {}
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    env_username = os.getenv("WIKIJS_USERNAME") or os.getenv("WIKIJS_EMAIL")
    env_password = os.getenv("WIKIJS_PASSWORD")
    if env_username:
        config["username"] = env_username
    if env_password:
        config["password"] = env_password

    return config


def is_logged_in(page) -> bool:
    try:
        if page.get_by_role("button", name="Nuova pagina").is_visible(timeout=1500):
            return True
    except Exception:
        pass

    try:
        if page.get_by_role("button", name="New Page").is_visible(timeout=1500):
            return True
    except Exception:
        pass

    return False


def fill_first_matching_input(page, selectors, value: str) -> bool:
    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() > 0:
                loc.first.fill(value)
                return True
        except Exception:
            continue
    return False


def click_login_entrypoint(page) -> bool:
    candidates = [
        page.get_by_role("link", name=re.compile("login|log in|accedi|accesso", re.I)),
        page.get_by_role("button", name=re.compile("login|log in|accedi|accesso", re.I)),
        page.get_by_text(re.compile("login|log in|accedi|accesso", re.I)),
    ]

    for candidate in candidates:
        try:
            candidate.first.wait_for(state="visible", timeout=2500)
            candidate.first.click()
            wait_a_bit(1.0)
            return True
        except Exception:
            continue

    return False


def submit_login_form(page) -> bool:
    candidates = [
        page.get_by_role("button", name=re.compile("login|log in|accedi|entra|sign in", re.I)),
        page.locator("button[type='submit']"),
        page.locator("input[type='submit']"),
    ]

    for candidate in candidates:
        try:
            candidate.first.wait_for(state="visible", timeout=2500)
            candidate.first.click()
            wait_a_bit(2.0)
            return True
        except Exception:
            continue

    return False


def automatic_login(page, username: str, password: str) -> bool:
    if is_logged_in(page):
        return True

    open_login(page)

    try:
        if page.locator("input[type='password']:visible").count() == 0:
            click_login_entrypoint(page)
    except Exception:
        click_login_entrypoint(page)

    username_ok = fill_first_matching_input(
        page,
        [
            "input[type='email']:visible",
            "input[name='email']:visible",
            "input[name='username']:visible",
            "input[autocomplete='username']:visible",
            "input[type='text']:visible",
        ],
        username,
    )
    password_ok = fill_first_matching_input(
        page,
        [
            "input[type='password']:visible",
            "input[name='password']:visible",
            "input[autocomplete='current-password']:visible",
        ],
        password,
    )

    if not username_ok or not password_ok:
        return False

    if not submit_login_form(page):
        return False

    open_home(page, None)
    return is_logged_in(page)


def ensure_login(page, language: str, config: dict, manual_login: bool):
    open_home(page, language)

    username = config.get("username")
    password = config.get("password")
    if username and password and not manual_login:
        print("\nLogin automatico da configurazione/env...")
        if automatic_login(page, username, password):
            print("Login automatico riuscito.")
            return

        print("Login automatico non riuscito; passo al login manuale.")

    if config.get("prompt_for_missing_credentials") and not manual_login:
        username = username or input("Wiki.js username/email: ").strip()
        password = password or getpass.getpass("Wiki.js password: ")
        if username and password and automatic_login(page, username, password):
            print("Login automatico riuscito.")
            return

    print(f"\nFai login manualmente su {wiki_login_url()} oppure sulla home {wiki_home_url(language)}.")
    input("Quando sei loggato e nella home, premi INVIO...")


def open_new_page(page):
    print("  - clic su 'Nuova pagina' / 'New Page'")
    candidates = [
        page.get_by_role("button", name="Nuova pagina"),
        page.get_by_role("button", name="New Page"),
        page.get_by_role("link", name="Nuova pagina"),
        page.get_by_role("link", name="New Page"),
    ]

    for btn in candidates:
        try:
            btn.wait_for(state="visible", timeout=3000)
            btn.click()
            return
        except Exception:
            continue

    raise RuntimeError("Non trovo il bottone Nuova pagina/New Page.")


def fill_new_page_path(page, page_path: str):
    print(f"  - compilo path: {page_path}")
    inputs = page.locator("input:visible")
    count = inputs.count()

    if count == 0:
        raise RuntimeError("Nessun input visibile trovato per il path.")

    filled = False
    for i in range(count - 1, -1, -1):
        try:
            candidate = inputs.nth(i)
            candidate.fill(page_path)
            filled = True
            break
        except Exception:
            continue

    if not filled:
        raise RuntimeError("Non sono riuscito a compilare il path.")


def click_select(page):
    print("  - clic su 'SELEZIONA' / 'SELECT'")
    candidates = [
        page.get_by_role("button", name="SELEZIONA"),
        page.get_by_role("button", name="SELECT"),
        page.get_by_role("button", name="Select"),
    ]

    for btn in candidates:
        try:
            btn.wait_for(state="visible", timeout=3000)
            btn.click()
            return
        except Exception:
            continue

    raise RuntimeError("Non trovo il bottone SELEZIONA/SELECT.")


def is_editor_choice_visible(page) -> bool:
    try:
        return page.get_by_text("Quale editor vuoi utilizzare per questa pagina?").is_visible(timeout=1500)
    except Exception:
        pass

    try:
        return page.get_by_text("Which editor do you want to use for this page?").is_visible(timeout=1500)
    except Exception:
        return False


def choose_code_editor(page):
    print("  - scelgo editor 'Code'")
    choice = page.get_by_text("Code", exact=True)
    choice.wait_for(state="visible", timeout=10000)
    choice.click()


def is_title_dialog_visible(page) -> bool:
    try:
        return page.get_by_role("button", name="OK").is_visible(timeout=1500)
    except Exception:
        return False


def fill_title_and_confirm(page, page_title: str):
    print(f"  - compilo titolo: {page_title}")
    title_filled = False

    try:
        page.locator("label").filter(has_text="Titolo").locator("..").locator("input").fill(page_title)
        title_filled = True
    except Exception:
        pass

    if not title_filled:
        try:
            page.locator("label").filter(has_text="Title").locator("..").locator("input").fill(page_title)
            title_filled = True
        except Exception:
            pass

    if not title_filled:
        try:
            visible_inputs = page.locator("input:visible")
            count = visible_inputs.count()
            for i in range(count):
                try:
                    visible_inputs.nth(i).fill(page_title)
                    title_filled = True
                    break
                except Exception:
                    continue
        except Exception:
            pass

    if not title_filled:
        raise RuntimeError("Non sono riuscito a compilare il titolo.")

    print("  - clic su 'OK'")
    ok_btn = page.get_by_role("button", name="OK")
    ok_btn.wait_for(state="visible", timeout=10000)
    ok_btn.click()


def monaco_available(page) -> bool:
    try:
        return page.evaluate(
            """() => {
                return !!(
                    window.monaco &&
                    window.monaco.editor &&
                    window.monaco.editor.getModels &&
                    window.monaco.editor.getModels().length > 0
                );
            }"""
        )
    except Exception:
        return False


def ace_available(page) -> bool:
    try:
        return page.evaluate(
            """() => {
                return !!(
                    window.ace ||
                    document.querySelector('.ace_editor')
                );
            }"""
        )
    except Exception:
        return False


def wait_for_code_editor(page, timeout_ms=15000) -> str:
    start = time.time()
    timeout_sec = timeout_ms / 1000

    while time.time() - start < timeout_sec:
        if monaco_available(page):
            return "monaco"
        if ace_available(page):
            return "ace"

        try:
            if page.locator("textarea:visible").count() > 0:
                return "textarea"
        except Exception:
            pass

        try:
            if page.locator('[contenteditable="true"]').count() > 0:
                return "contenteditable"
        except Exception:
            pass

        time.sleep(0.5)

    return "none"


def get_current_editor_content(page) -> str:
    # Monaco
    try:
        content = page.evaluate(
            """() => {
                if (window.monaco && window.monaco.editor) {
                    const models = window.monaco.editor.getModels();
                    if (models && models.length > 0) {
                        return models[0].getValue();
                    }
                }
                return null;
            }"""
        )
        if content is not None:
            return content
    except Exception:
        pass

    # Ace
    try:
        content = page.evaluate(
            """() => {
                try {
                    if (window.ace) {
                        const el = document.querySelector('.ace_editor');
                        if (el) {
                            const editor = window.ace.edit(el);
                            return editor.getValue();
                        }
                    }
                } catch (e) {}
                return null;
            }"""
        )
        if content is not None:
            return content
    except Exception:
        pass

    # textarea
    try:
        loc = page.locator("textarea:visible")
        if loc.count() > 0:
            return loc.first.input_value()
    except Exception:
        pass

    # contenteditable
    try:
        loc = page.locator('[contenteditable="true"]')
        if loc.count() > 0:
            txt = loc.first.inner_text()
            return txt if txt is not None else ""
    except Exception:
        pass

    return ""


def normalize_html_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()


def is_default_template_content(content: str) -> bool:
    if content is None:
        return True

    # pulizia caratteri invisibili e newline
    cleaned = content.replace("\u200b", "").replace("\xa0", " ").replace("\r", "\n")

    # rimuove righe che sono solo numeri (numeri di riga dell'editor)
    lines = []
    for line in cleaned.split("\n"):
        stripped = line.strip()
        if stripped.isdigit():
            continue
        if stripped == "":
            continue
        lines.append(stripped)

    normalized = "\n".join(lines).strip()
    compact = " ".join(normalized.split()).strip().lower()

    if compact == "":
        return True

    # forma HTML standard
    if compact in {
        "<h1>title</h1> <p>some text here</p>",
        "<h1>title</h1><p>some text here</p>",
    }:
        return True

    # forma testuale standard
    if compact == "title some text here":
        return True

    # ulteriore tolleranza: togli i tag base e ricontrolla
    reduced = compact
    reduced = reduced.replace("<h1>", "").replace("</h1>", "")
    reduced = reduced.replace("<p>", "").replace("</p>", "")
    reduced = " ".join(reduced.split()).strip()

    if reduced == "title some text here":
        return True

    return False

def ask_populated_editor_action(page_path: str) -> str:
    while True:
        choice = input(
            f"L'editor per '{page_path}' contiene già contenuto non standard. "
            f"[s]kip / [o]verwrite / [q]uit: "
        ).strip().lower()

        if choice in {"s", "o", "q"}:
            return choice

        print("Scelta non valida. Usa s, o oppure q.")


def write_html_to_monaco(page, html_content: str) -> bool:
    try:
        inserted = page.evaluate(
            """(content) => {
                if (window.monaco && window.monaco.editor) {
                    const models = window.monaco.editor.getModels();
                    if (models && models.length > 0) {
                        models[0].setValue(content);
                        return true;
                    }
                }
                return false;
            }""",
            html_content
        )
        return bool(inserted)
    except Exception:
        return False


def write_html_to_ace(page, html_content: str) -> bool:
    try:
        inserted = page.evaluate(
            """(content) => {
                try {
                    if (window.ace) {
                        const el = document.querySelector('.ace_editor');
                        if (el) {
                            const editor = window.ace.edit(el);
                            editor.setValue(content, -1);
                            return true;
                        }
                    }

                    const aceEl = document.querySelector('.ace_editor');
                    if (aceEl && window.ace) {
                        const editor = window.ace.edit(aceEl);
                        editor.setValue(content, -1);
                        return true;
                    }

                    return false;
                } catch (e) {
                    return false;
                }
            }""",
            html_content
        )
        return bool(inserted)
    except Exception:
        return False


def write_html_to_textarea(page, html_content: str) -> bool:
    try:
        loc = page.locator("textarea:visible")
        if loc.count() > 0:
            loc.first.fill(html_content)
            return True
    except Exception:
        pass
    return False


def write_html_to_contenteditable(page, html_content: str) -> bool:
    try:
        loc = page.locator('[contenteditable="true"]')
        if loc.count() > 0:
            loc.first.click()
            wait_a_bit(0.3)
            page.keyboard.press("Meta+A")
            wait_a_bit(0.2)
            page.keyboard.press("Backspace")
            wait_a_bit(0.2)
            page.keyboard.insert_text(html_content)
            return True
    except Exception:
        pass
    return False


def write_html_with_keyboard_fallback(page, html_content: str) -> bool:
    try:
        print("  - fallback editor: click nell'area codice")
        candidates = [
            ".ace_content",
            ".ace_text-input",
            ".ace_editor",
            ".monaco-editor",
            ".view-lines",
            ".CodeMirror",
            ".cm-content",
            "pre",
            "code"
        ]

        clicked = False
        for selector in candidates:
            loc = page.locator(selector)
            if loc.count() > 0:
                try:
                    loc.first.click(timeout=2000)
                    clicked = True
                    print(f"  - fallback editor: cliccato selettore {selector}")
                    break
                except Exception:
                    continue

        if not clicked:
            print("  - fallback editor: nessun selettore cliccabile")
            return False

        wait_a_bit(0.5)
        page.keyboard.press("Meta+A")
        wait_a_bit(0.2)
        page.keyboard.press("Backspace")
        wait_a_bit(0.3)
        page.keyboard.insert_text(html_content)
        wait_a_bit(0.5)
        return True
    except Exception:
        return False


def write_html_to_editor(page, html_content: str) -> bool:
    editor_type = wait_for_code_editor(page, timeout_ms=12000)
    print(f"  - editor rilevato: {editor_type}")

    if editor_type == "monaco":
        ok = write_html_to_monaco(page, html_content)
        if ok:
            return True

    if editor_type == "ace":
        ok = write_html_to_ace(page, html_content)
        if ok:
            return True

    if editor_type == "textarea":
        ok = write_html_to_textarea(page, html_content)
        if ok:
            return True

    if editor_type == "contenteditable":
        ok = write_html_to_contenteditable(page, html_content)
        if ok:
            return True

    return write_html_with_keyboard_fallback(page, html_content)


def click_create(page):
    print("  - clic su 'CREA' / 'CREATE'")
    possible = [
        page.get_by_role("button", name="CREA"),
        page.get_by_role("button", name="CREATE"),
        page.get_by_role("button", name="Create"),
    ]

    for btn in possible:
        try:
            btn.wait_for(state="visible", timeout=3000)
            btn.click()
            return
        except Exception:
            continue

    raise RuntimeError("Non trovo il bottone CREA/Create.")


def click_save(page):
    print("  - clic su 'SALVA' / 'Save'")
    possible = [
        page.get_by_role("button", name="SALVA"),
        page.get_by_role("button", name="Save"),
    ]

    for btn in possible:
        try:
            btn.wait_for(state="visible", timeout=3000)
            btn.click()
            return
        except Exception:
            continue

    raise RuntimeError("Non trovo il bottone SALVA/Save.")


def prepare_editor(page, page_title: str):
    wait_a_bit(1.5)

    print(f"  - editor choice visible: {is_editor_choice_visible(page)}")
    print(f"  - title dialog visible: {is_title_dialog_visible(page)}")
    print(f"  - monaco available: {monaco_available(page)}")
    print(f"  - ace available: {ace_available(page)}")

    if is_editor_choice_visible(page):
        print("  - rilevata schermata scelta editor")
        choose_code_editor(page)
        wait_a_bit(1.5)

        print(f"  - dopo scelta editor, title dialog visible: {is_title_dialog_visible(page)}")
        print(f"  - dopo scelta editor, monaco available: {monaco_available(page)}")
        print(f"  - dopo scelta editor, ace available: {ace_available(page)}")

        if is_title_dialog_visible(page):
            print("  - rilevata finestra titolo dopo scelta editor")
            fill_title_and_confirm(page, page_title)
            wait_a_bit(2.0)
            return "create"

        wait_a_bit(2.0)

        if is_title_dialog_visible(page):
            print("  - rilevata finestra titolo dopo attesa aggiuntiva")
            fill_title_and_confirm(page, page_title)
            wait_a_bit(2.0)
            return "create"

    if is_title_dialog_visible(page):
        print("  - rilevato flusso nuova pagina (titolo diretto)")
        fill_title_and_confirm(page, page_title)
        wait_a_bit(2.0)
        return "create"

    if monaco_available(page) or ace_available(page):
        print("  - rilevato editor già aperto")
        return "existing_editor"

    wait_a_bit(2.0)

    print(f"  - secondo tentativo, editor choice visible: {is_editor_choice_visible(page)}")
    print(f"  - secondo tentativo, title dialog visible: {is_title_dialog_visible(page)}")
    print(f"  - secondo tentativo, monaco available: {monaco_available(page)}")
    print(f"  - secondo tentativo, ace available: {ace_available(page)}")

    if is_editor_choice_visible(page):
        print("  - schermata scelta editor ancora visibile")
        return "unknown"

    if is_title_dialog_visible(page):
        print("  - rilevato flusso nuova pagina al secondo tentativo")
        fill_title_and_confirm(page, page_title)
        wait_a_bit(2.0)
        return "create"

    if monaco_available(page) or ace_available(page):
        print("  - rilevato editor già aperto al secondo tentativo")
        return "existing_editor"

    # Anche se non identifichiamo Monaco/Ace, potrebbe esserci comunque un editor attivo
    editor_type = wait_for_code_editor(page, timeout_ms=3000)
    if editor_type != "none":
        print(f"  - rilevato editor tramite fallback: {editor_type}")
        return "existing_editor"

    return "unknown"


def resolve_existing_content_action(page_path: str, existing_action: str, run_state: dict) -> str:
    if existing_action == "overwrite":
        print("  - contenuto già popolato: sovrascrittura automatica (--overwrite-existing)")
        return "o"

    if existing_action == "skip":
        print("  - contenuto già popolato: salto automatico (--existing-action skip)")
        return "s"

    if existing_action == "ask-once" and run_state.get("existing_action"):
        action = run_state["existing_action"]
        print(f"  - contenuto già popolato: riuso scelta globale '{action}'")
        return action

    action = ask_populated_editor_action(page_path)
    if existing_action == "ask-once" and action in {"s", "o"}:
        run_state["existing_action"] = action
        print(f"  - scelta salvata per il resto del run: {action}")

    return action


def upload_ui(page, ui_code: str, language: str, existing_action: str, run_state: dict) -> bool:
    html_files = get_html_files_for_ui(ui_code, language)
    screen_order = get_screen_order_from_xml(ui_code)

    print(f"\nTrovati {len(html_files)} screen HTML in {ui_code} [{language}]")
    print(f"Ordine screen caricato dal profilo XML: {len(screen_order)} screen")

    if not html_files:
        print("Nessun file trovato.")
        return True

    for idx, html_file in enumerate(html_files, start=1):
        html_content = html_file.read_text(encoding="utf-8")
        page_path = page_path_for(ui_code, html_file, language)
        page_title = page_title_for(html_file, html_content, screen_order)

        print(f"\n[{idx}/{len(html_files)}] Upload {html_file}")
        print(f"Path Wiki.js [{language}]: /{language}/{page_path}")
        print(f"Titolo: {page_title}")

        try:
            open_home(page, language)
            open_new_page(page)
            wait_a_bit(1.2)

            fill_new_page_path(page, page_path)
            wait_a_bit(0.5)

            click_select(page)

            state = prepare_editor(page, page_title)

            if state == "unknown":
                print("  - stato pagina non riconosciuto")
                debug_dump(page, f"unknown_state_{language}_{ui_code}_{html_file.stem}")
                input("Controlla il browser. Premi INVIO per continuare al prossimo file...")
                continue

            current_content = get_current_editor_content(page)
            is_default = is_default_template_content(current_content)

            print(f"  - contenuto editor letto: {len(current_content)} caratteri")
            print(f"  - preview contenuto editor: {repr(current_content[:200])}")
            print(f"  - contenuto standard di default: {is_default}")

            if not is_default:
                action = resolve_existing_content_action(
                    f"/{language}/{page_path}",
                    existing_action,
                    run_state,
                )

                if action == "q":
                    print("Interrotto su richiesta.")
                    return False

                if action == "s":
                    print("  - pagina saltata")
                    continue

                print("  - sovrascrivo contenuto già popolato")

            else:
                print("  - editor con template standard: sovrascrittura automatica")

            inserted = write_html_to_editor(page, html_content)
            print(f"  - HTML inserito nell'editor: {inserted}")

            if not inserted:
                debug_dump(page, f"write_failed_{language}_{ui_code}_{html_file.stem}")
                input("Inserimento HTML non riuscito. Correggi manualmente e premi INVIO...")
                continue

            wait_a_bit(0.8)

            if state == "create":
                click_create(page)
                print("  - pagina creata")
            else:
                click_save(page)
                print("  - pagina salvata")

            wait_a_bit(2.0)

        except PlaywrightTimeoutError as e:
            print(f"Timeout su {html_file.name}: {e}")
            debug_dump(page, f"timeout_{language}_{ui_code}_{html_file.stem}")
            input("Sistema manualmente o controlla la pagina, poi premi INVIO per continuare...")
        except Exception as e:
            print(f"Errore su {html_file.name}: {e}")
            debug_dump(page, f"error_{language}_{ui_code}_{html_file.stem}")
            input("Sistema manualmente o controlla la pagina, poi premi INVIO per continuare...")

    print(f"\nUpload UI completato: {ui_code} [{language}]")
    return True


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Carica su Wiki.js la documentazione HTML generata per una o più UI."
    )
    parser.add_argument("--language", choices=sorted(LANGUAGE_OUTPUT_ROOTS), default="it")
    parser.add_argument("--ui", action="append", help="UI da caricare. Ripeti l'opzione per più UI.")
    parser.add_argument("--all-ui", action="store_true", help="Carica tutte le UI trovate per la lingua scelta.")
    parser.add_argument(
        "--continue-between-ui",
        action="store_true",
        help="Chiede conferma prima di passare alla UI successiva.",
    )
    parser.add_argument(
        "--manual-login",
        action="store_true",
        help="Ignora credenziali config/env e usa il login manuale.",
    )
    parser.add_argument(
        "--existing-action",
        choices=["ask", "ask-once", "overwrite", "skip"],
        default="ask",
        help=(
            "Cosa fare quando una pagina esistente contiene contenuto non standard. "
            "Default: ask."
        ),
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Alias rapido per --existing-action overwrite.",
    )
    parser.add_argument("--headless", action="store_true", help="Avvia Chromium in modalità headless.")
    return parser


def main():
    args = build_arg_parser().parse_args()
    if args.overwrite_existing:
        args.existing_action = "overwrite"

    ui_codes = choose_ui_sequence(args.language, args.all_ui, args.ui)
    config = load_config()
    run_state = {}

    print(f"\nLingua Wiki.js: {args.language}")
    print(f"UI da caricare: {', '.join(ui_codes)}")
    print(f"Policy contenuti esistenti: {args.existing_action}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless or HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context()
        page = context.new_page()

        ensure_login(page, args.language, config, args.manual_login)

        for idx, ui_code in enumerate(ui_codes, start=1):
            if idx > 1 and args.continue_between_ui:
                choice = input(f"\nContinua all'interfaccia successiva ({ui_code})? [S/n/q]: ").strip().lower()
                if choice == "q":
                    print("Interrotto su richiesta.")
                    break
                if choice in {"n", "no"}:
                    print(f"UI saltata: {ui_code}")
                    continue

            keep_going = upload_ui(page, ui_code, args.language, args.existing_action, run_state)
            if not keep_going:
                break

        print("\nUpload completato.")
        print("Il browser resta aperto. Chiudilo manualmente quando hai finito.")
        input("Premi INVIO per terminare lo script...")


if __name__ == "__main__":
    main()
