/**
 * Copia adattata per CollectiveAccess di organico-viewer/assets/js/organico-editor.js.
 * Differenze rispetto all'originale (che rimane la fonte, aggiornare li' prima):
 *  - moduli ES -> namespace globale window.caUI.Organico (script classico via AssetLoadManager)
 *  - l'anteprima live non fa piu' fetch verso api/organico.php?format=json (dentro CA non e'
 *    raggiungibile nessun endpoint PHP arbitrario, vedi .htaccess di Providence) ma chiama
 *    window.caUI.Organico.normalizer.buildRenderPayload(...) — porting JS sincrono, vedi
 *    organico-normalizer.js
 *  - mountOrganicoEditor() accetta un payload iniziale (per pre-popolare l'editor quando si
 *    modifica un valore gia' salvato) e un callback onPayloadChange (per tenere sincronizzato
 *    l'input nascosto del campo CA)
 *  - caUI.Organico.initField() e' il nuovo punto di aggancio usato da OrganicoAttributeValue::
 *    htmlFormElement(): riassunto compatto + pulsante che apre il pannello overlay con
 *    l'editor completo (vedi fondo di questo file)
 *  - tutte le stringhe di interfaccia sono state convertite da testo italiano hardcoded a
 *    chiamate t("English source string"), che leggono window.caUI.Organico.i18n (popolato da
 *    OrganicoAttributeValue::buildI18nJson() via _t(), catalogo in
 *    app/locale/user/it_IT/messages.po). ATTENZIONE se si riporta questo file dall'originale
 *    organico-viewer (che resta in italiano semplice, senza t()): questa conversione i18n va
 *    riapplicata a mano dopo il resync, altrimenti si perde.
 */
(function () {
  "use strict";
  window.caUI = window.caUI || {};
  window.caUI.Organico = window.caUI.Organico || {};

  // Traduzione: il dizionario window.caUI.Organico.i18n viene popolato da
  // OrganicoAttributeValue::htmlFormElement() con le stesse stringhe passate
  // a _t() lato PHP, cosi' il catalogo di traduzione resta unico (vedi
  // app/locale/user/it_IT/messages.po). La chiave inglese e' anche il
  // fallback quando il dizionario manca (es. pagine di test standalone).
  function t(key, vars) {
    const dict = (window.caUI.Organico && window.caUI.Organico.i18n) || {};
    let str = Object.prototype.hasOwnProperty.call(dict, key) ? dict[key] : key;
    if (vars) {
      for (const k in vars) {
        str = str.split("{" + k + "}").join(vars[k]);
      }
    }
    return str;
  }

  const PREVIEW_DEBOUNCE_MS = 150;
  const SEARCH_DEBOUNCE_MS = 120;
  const SEARCH_RESULTS_LIMIT = 40;

  // Lista chiusa dei suffissi codificati UNIMARC (Campo 145, Appendice B —
  // sottocampi $b-$d, posizione 5-6; vedi urfm.braidense.it/risorse/searchsuffix.php).
  // E' una lista fissa definita dallo standard (non un vocabolario che cresce
  // come gli strumenti), quindi qui incorporata direttamente invece che
  // generata da un file dati esterno. Il campo "Suffisso" resta comunque
  // anche testo libero ("Altro") per i casi non coperti dall'Appendice B
  // (es. tonalita': "in Sib" — vedi docs/schema.md).
  const SUFFIX_CODES = [
    { code: "p", label: "Sopracuto" }, { code: "n", label: "Sopranino" },
    { code: "s", label: "Soprano" }, { code: "a", label: "Contralto" },
    { code: "t", label: "Tenore" }, { code: "r", label: "Baritono" },
    { code: "b", label: "Basso" }, { code: "c", label: "Contrabbasso" },
    { code: "g", label: "Sub-contrabbasso" }, { code: "h", label: "Acuto, piccolo" },
    { code: "m", label: "Medio" }, { code: "l", label: "Grave, grande" },
    { code: "e", label: "Elettrico" }, { code: "x", label: "Elettronico" },
    { code: "f", label: "Amplificato" }, { code: "k", label: "Registrato" },
    { code: "d", label: "Midi" }, { code: "z", label: "Preparato" },
    { code: "y", label: "Etnico, tradizionale" }, { code: "q", label: "Antico" },
    { code: "o", label: "Una mano" }, { code: "u", label: "Tre mani" },
    { code: "v", label: "Quattro mani" }, { code: "i", label: "Sei mani" },
    { code: "j", label: "Otto mani" }, { code: "w", label: "Due esecutori su uno strumento" },
    { code: "5", label: "Quinto" }, { code: "6", label: "Sesto" },
    { code: "7", label: "Settimo" }, { code: "8", label: "Ottavo" },
    { code: "9", label: "Nono" }, { code: "10", label: "Decimo" },
    { code: "11", label: "Undicesimo" }, { code: "12", label: "Dodicesimo" },
  ];

  function mountOrganicoEditor(root, options) {
    if (!root) return null;
    options = options || {};
    const renderOrganicoStage = window.caUI.Organico.renderStage;
    const normalizer = window.caUI.Organico.normalizer;
    const parseSbnMarc = window.caUI.Organico.parseSbnMarc;

    const palette = JSON.parse(root.getAttribute("data-palette") || "[]");
    const vocabularyUrl = root.getAttribute("data-vocabulary");
    const sbnDictionaryUrl = root.getAttribute("data-sbn-dictionary");
    const spriteUrl = root.getAttribute("data-icons-sprite") || "assets/organico/sprite.svg";

    window.caUI.Organico.ensureSprite(spriteUrl);

    // vocabolario IFLA MOP completo (392 termini): caricato una volta, usato dalla ricerca
    // nella palette cosi' non ci si limita ai ~40 strumenti con icona dedicata della griglia rapida.
    let vocabulary = null;
    const vocabularyReady = vocabularyUrl
      ? fetch(vocabularyUrl)
          .then((res) => (res.ok ? res.json() : []))
          .then((data) => { vocabulary = data; })
          .catch((err) => {
            console.error("[organico-editor] vocabolario MOP non caricato", err);
            vocabulary = [];
          })
      : Promise.resolve();

    // dizionario abbreviazioni SBN MARC (vedi build/build-sbn-marc-dictionary.php),
    // usato solo dal pulsante "Importa da testo (SBN MARC)".
    let sbnDictionary = null;
    const sbnDictionaryReady = sbnDictionaryUrl
      ? fetch(sbnDictionaryUrl)
          .then((res) => (res.ok ? res.json() : {}))
          .then((data) => { sbnDictionary = data; })
          .catch((err) => {
            console.error("[organico-editor] dizionario SBN MARC non caricato", err);
            sbnDictionary = {};
          })
      : Promise.resolve();

    const state = {
      titolo: "",
      organicoSintetico: "",
      ensembleType: "auto",
      items: [],
      selected: new Set(),
      expandedId: null,
      nextId: 1,
      nextAltGroup: 1,
    };

    const el = {
      titolo: root.querySelector(".oe-titolo"),
      organicoSintetico: root.querySelector(".oe-organico-sintetico"),
      ensembleTypeRadios: root.querySelectorAll('input[name$="oe-ensemble-type"]'),
      palette: root.querySelector(".oe-palette"),
      list: root.querySelector(".oe-list"),
      empty: root.querySelector(".oe-empty"),
      toolbar: root.querySelector(".oe-toolbar"),
      btnGroup: root.querySelector(".oe-btn-group"),
      btnAlt: root.querySelector(".oe-btn-alt"),
      btnRemove: root.querySelector(".oe-btn-remove"),
      btnClearAll: root.querySelector(".oe-btn-clear-all"),
      btnImportSbn: root.querySelector(".oe-btn-import-sbn"),
      previewStage: root.querySelector(".oe-preview-stage"),
      json: root.querySelector(".oe-json"),
      btnCopy: root.querySelector(".oe-btn-copy"),
      modalBackdrop: root.querySelector(".oe-modal-backdrop"),
      modal: root.querySelector(".oe-modal"),
    };

    function makeItem(entry) {
      return {
        id: state.nextId++,
        label: entry.label,
        mezzoLabel: entry.key || entry.label,
        mopUri: entry.mopUri || entry.uri || null,
        mopCode: entry.mopCode || entry.code || mopCodeFromUri(entry.mopUri || entry.uri),
        wikidataUri: entry.mopWikidataUri || entry.wikidataUri || null,
        icon: entry.icon,
        family: entry.family,
        numero_elementi: 1,
        numero_esecutori: null,
        solo: false,
        ad_libitum: false,
        overdub: false,
        elaborazione_digitale: false,
        suffisso: "",
        sezione_parte_voce: "",
        gruppo_ensemble: null,
        numero_gruppo: null,
        alternativa_gruppo: null,
        alternativa_opzione: null,
      };
    }

    function mopCodeFromUri(uri) {
      const match = String(uri || "").match(/(?:\/|#)([a-z0-9]+)\/?$/i);
      return match ? match[1] : null;
    }

    function normalizedVocabularyLabel(value) {
      return String(value || "")
        .trim()
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/\s+/g, " ");
    }

    // Alcuni valori legacy (es. record catalogati prima dell'editor strutturato) portano
    // rumore di formattazione incollato nella label stessa invece di stare nei campi
    // dedicati: il qualificatore "(voce)" (es. "soprano (voce)") e il marcatore solista
    // "-solo"/" solo" concatenato (es. "MS-solo"). Va tolto solo per il TENTATIVO di
    // matching col dizionario/vocabolario: non tocca la label mostrata ne' il flag
    // item.solo, che restano quelli gia' presenti sul record.
    function stripKnownLabelNoise(value) {
      return String(value || "")
        .replace(/\s*\(voce\)\s*$/i, "")
        .replace(/[\s-]+solo$/i, "")
        .trim();
    }

    function canonicalMopTerm(item) {
      const terms = Array.isArray(vocabulary) ? vocabulary : [];
      if (terms.length === 0) return null;

      const existingUri = String(item.mopUri || "").trim();
      const existingCode = String(item.mopCode || mopCodeFromUri(existingUri) || "").trim().toLowerCase();
      if (existingUri || existingCode) {
        const identified = terms.find((term) =>
          (existingUri && term.uri === existingUri) ||
          (existingCode && String(term.code || "").toLowerCase() === existingCode)
        );
        if (identified) return identified;
      }

      const candidates = [item.mezzoLabel, item.label];
      for (const base of candidates.slice()) {
        const stripped = stripKnownLabelNoise(base);
        if (stripped && stripped !== base) candidates.push(stripped);
      }
      const sbnEntries = sbnDictionary || {};
      for (const candidate of candidates.slice()) {
        const direct = sbnEntries[candidate];
        const caseInsensitiveKey = Object.keys(sbnEntries).find((key) => key.toLowerCase() === String(candidate || "").toLowerCase());
        const sbnEntry = direct || (caseInsensitiveKey ? sbnEntries[caseInsensitiveKey] : null);
        if (sbnEntry && sbnEntry.label) candidates.push(sbnEntry.label);
      }

      for (const candidate of candidates) {
        const needle = normalizedVocabularyLabel(candidate);
        if (!needle) continue;
        const matched = terms.find((term) => {
          const labels = [term.label, term.labelIt, term.labelEn].concat(term.altLabels || []);
          return labels.some((label) => normalizedVocabularyLabel(label) === needle);
        });
        if (matched) return matched;
      }
      return null;
    }

    function reconcileCanonicalMopData() {
      let changed = false;
      for (const item of state.items) {
        const term = canonicalMopTerm(item);
        if (!term) continue;
        if (item.mopUri !== term.uri) {
          item.mopUri = term.uri;
          changed = true;
        }
        if (item.mopCode !== term.code) {
          item.mopCode = term.code;
          changed = true;
        }
        if (item.wikidataUri !== (term.wikidataUri || null)) {
          item.wikidataUri = term.wikidataUri || null;
          changed = true;
        }
      }
      return changed;
    }

    /** Ricostruisce un item interno a partire da un mezzo_esecuzione gia' salvato (JSON esistente):
     * l'icona/famiglia non sono nel JSON grezzo, si risolvono di nuovo dalla label. */
    function hydrateItem(raw) {
      const mezzo = raw.mezzo_esecuzione || {};
      const resolved = normalizer.resolve(mezzo.label || "");
      const numeroGruppo = (raw.numero_gruppo !== undefined) ? raw.numero_gruppo : null;
      let maxAltGroup = 0;
      if (raw.alternativa_gruppo) maxAltGroup = raw.alternativa_gruppo;
      if (maxAltGroup >= state.nextAltGroup) state.nextAltGroup = maxAltGroup + 1;
      return {
        id: state.nextId++,
        label: mezzo.label || "",
        mezzoLabel: mezzo.label || "",
        mopUri: mezzo.mop_uri || null,
        mopCode: mezzo.mop_code || mopCodeFromUri(mezzo.mop_uri),
        wikidataUri: mezzo.wikidata_uri || null,
        icon: resolved.icon,
        family: resolved.family,
        numero_elementi: raw.numero_elementi || 1,
        numero_esecutori: (raw.numero_esecutori !== undefined && raw.numero_esecutori !== null) ? raw.numero_esecutori : null,
        solo: !!raw.solo,
        ad_libitum: !!raw.ad_libitum,
        overdub: !!raw.overdub,
        elaborazione_digitale: !!raw.elaborazione_digitale,
        suffisso: raw.suffisso || "",
        sezione_parte_voce: raw.sezione_parte_voce || "",
        gruppo_ensemble: raw.gruppo_ensemble ? { label: raw.gruppo_ensemble.label, uri: raw.gruppo_ensemble.uri || null, numero_gruppo: numeroGruppo } : null,
        numero_gruppo: numeroGruppo,
        alternativa_gruppo: raw.alternativa_gruppo || null,
        alternativa_opzione: raw.alternativa_opzione || null,
      };
    }

    function loadInitialPayload(payload) {
      if (!payload) return;
      state.titolo = payload.titolo || "";
      state.organicoSintetico = payload.organico_sintetico || "";
      state.ensembleType = payload.ensemble_type || "auto";
      state.items = (payload.items || []).map(hydrateItem);
      if (el.titolo) el.titolo.value = state.titolo;
      if (el.organicoSintetico) el.organicoSintetico.value = state.organicoSintetico;
      el.ensembleTypeRadios.forEach((radio) => { radio.checked = (radio.value === state.ensembleType); });
    }

    // -------------------------------------------------------------------
    // Palette
    // -------------------------------------------------------------------

    function addFromEntry(entry) {
      const item = makeItem(entry);
      state.items.push(item);
      state.expandedId = item.id;
      onChange();
    }

    function paletteButton(entry, opts) {
      opts = opts || {};
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "oe-palette__item";
      if (entry.iconMatched === false) btn.classList.add("oe-palette__item--fallback");
      const familyHint = opts.showFamily ? `<small>${escapeHtml(familyLabel(entry.family))}</small>` : "";
      btn.title = entry.iconMatched === false ? `${entry.label} (icona generica di famiglia)` : entry.label;
      btn.innerHTML = `<svg width="26" height="26"><use href="#icon-${entry.icon}"></use></svg><span>${escapeHtml(entry.label)}</span>${familyHint}`;
      btn.addEventListener("click", () => addFromEntry(entry));
      return btn;
    }

    const FAMILY_LABELS = {};
    for (const group of palette) FAMILY_LABELS[group.family] = group.familyLabel;
    FAMILY_LABELS.altro = FAMILY_LABELS.altro || "Altro";
    function familyLabel(family) {
      return FAMILY_LABELS[family] || family;
    }

    function renderQuickPicks(container) {
      for (const group of palette) {
        const section = document.createElement("div");
        section.className = "oe-palette__group";
        const h = document.createElement("h3");
        h.textContent = group.familyLabel;
        section.appendChild(h);

        const grid = document.createElement("div");
        grid.className = "oe-palette__grid";
        for (const instrument of group.instruments) {
          grid.appendChild(paletteButton(instrument));
        }
        section.appendChild(grid);
        container.appendChild(section);
      }
    }

    function renderSearchResults(container, query) {
      if (vocabulary === null) {
        const p = document.createElement("p");
        p.className = "oe-palette__hint";
        p.textContent = t("Loading MOP vocabulary…");
        container.appendChild(p);
        return;
      }
      const norm = query.trim().toLowerCase();
      const matches = vocabulary.filter((t) => t.searchText.includes(norm));

      const summary = document.createElement("p");
      summary.className = "oe-palette__hint";
      summary.textContent = matches.length === 0
        ? t("No IFLA MOP term matches the search.")
        : t("{n} term(s) found", { n: matches.length }) + (matches.length > SEARCH_RESULTS_LIMIT ? t(" (showing the first {limit} — refine your search)", { limit: SEARCH_RESULTS_LIMIT }) : "");
      container.appendChild(summary);

      const grid = document.createElement("div");
      grid.className = "oe-palette__grid oe-palette__grid--search";
      for (const term of matches.slice(0, SEARCH_RESULTS_LIMIT)) {
        grid.appendChild(paletteButton(term, { showFamily: true }));
      }
      container.appendChild(grid);
    }

    function renderPaletteResults() {
      el.paletteResults.innerHTML = "";
      const query = el.paletteSearch.value;
      if (query.trim() === "") {
        renderQuickPicks(el.paletteResults);
      } else {
        renderSearchResults(el.paletteResults, query);
      }
    }

    let searchTimer = null;
    function initPalette() {
      el.palette.innerHTML = "";

      const searchWrap = document.createElement("div");
      searchWrap.className = "oe-palette__search";
      const searchInput = document.createElement("input");
      searchInput.type = "search";
      searchInput.placeholder = t("Search among {n} IFLA MOP terms…", { n: vocabulary ? vocabulary.length : 392 });
      searchInput.setAttribute("aria-label", t("Search instrument in the IFLA MOP vocabulary"));
      searchInput.addEventListener("input", () => {
        if (searchTimer) clearTimeout(searchTimer);
        searchTimer = setTimeout(renderPaletteResults, SEARCH_DEBOUNCE_MS);
      });
      searchWrap.appendChild(searchInput);
      el.palette.appendChild(searchWrap);

      const results = document.createElement("div");
      results.className = "oe-palette__results";
      el.palette.appendChild(results);

      el.paletteSearch = searchInput;
      el.paletteResults = results;

      renderPaletteResults();
      vocabularyReady.then(() => {
        if (el.paletteSearch.value.trim() !== "") renderPaletteResults();
      });
    }

    // -------------------------------------------------------------------
    // Lista item + pannello dettaglio
    // -------------------------------------------------------------------

    function summaryBadges(item) {
      const badges = [];
      if (item.numero_elementi >= 2) badges.push(`×${item.numero_elementi}`);
      if (item.numero_esecutori) badges.push(`${item.numero_esecutori} esec.`);
      if (item.solo) badges.push("solo");
      if (item.ad_libitum) badges.push("ad lib.");
      if (item.overdub) badges.push("overdub");
      if (item.elaborazione_digitale) badges.push("digitale");
      return badges;
    }

    function renderList() {
      el.list.innerHTML = "";
      el.empty.hidden = state.items.length > 0;

      for (const item of state.items) {
        const li = document.createElement("li");
        li.className = "oe-row";
        if (state.expandedId === item.id) li.classList.add("oe-row--expanded");

        const head = document.createElement("div");
        head.className = "oe-row__head";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = state.selected.has(item.id);
        checkbox.addEventListener("click", (e) => e.stopPropagation());
        checkbox.addEventListener("change", () => {
          if (checkbox.checked) state.selected.add(item.id);
          else state.selected.delete(item.id);
          onChange();
        });
        head.appendChild(checkbox);

        const icon = document.createElement("span");
        icon.className = "oe-row__icon";
        icon.innerHTML = `<svg width="22" height="22"><use href="#icon-${item.icon}"></use></svg>`;
        head.appendChild(icon);

        const title = document.createElement("span");
        title.className = "oe-row__title";
        const sezPrefix = item.sezione_parte_voce ? `${item.sezione_parte_voce} · ` : "";
        title.textContent = sezPrefix + item.label;
        head.appendChild(title);

        for (const b of summaryBadges(item)) {
          const tag = document.createElement("span");
          tag.className = "oe-tag";
          tag.textContent = b;
          head.appendChild(tag);
        }

        if (item.gruppo_ensemble) {
          const tag = document.createElement("span");
          tag.className = "oe-tag oe-tag--group";
          tag.textContent = item.gruppo_ensemble.label + (item.gruppo_ensemble.numero_gruppo ? ` ${item.gruppo_ensemble.numero_gruppo}` : "");
          head.appendChild(tag);
        }

        if (item.alternativa_gruppo) {
          const tag = document.createElement("span");
          tag.className = "oe-tag oe-tag--alt";
          tag.textContent = t("alternative {group} · option {option}", { group: item.alternativa_gruppo, option: item.alternativa_opzione });
          head.appendChild(tag);
        }

        const spacer = document.createElement("span");
        spacer.className = "oe-row__spacer";
        head.appendChild(spacer);

        const del = document.createElement("button");
        del.type = "button";
        del.className = "oe-row__delete";
        del.setAttribute("aria-label", t("Remove"));
        del.textContent = "✕";
        del.addEventListener("click", (e) => {
          e.stopPropagation();
          state.items = state.items.filter((it) => it.id !== item.id);
          state.selected.delete(item.id);
          if (state.expandedId === item.id) state.expandedId = null;
          onChange();
        });
        head.appendChild(del);

        head.addEventListener("click", () => {
          state.expandedId = state.expandedId === item.id ? null : item.id;
          onChange({ skipPreview: true });
        });

        li.appendChild(head);

        if (state.expandedId === item.id) {
          li.appendChild(renderDetailPanel(item));
        }

        el.list.appendChild(li);
      }
    }

    function renderDetailPanel(item) {
      const panel = document.createElement("div");
      panel.className = "oe-detail";
      panel.addEventListener("click", (e) => e.stopPropagation());

      panel.appendChild(numberField(t("Number of items"), item.numero_elementi, 1, (v) => {
        item.numero_elementi = Math.max(1, v);
        onChange();
      }));

      const esecutoriWrap = document.createElement("div");
      esecutoriWrap.className = "oe-detail__field";
      const esecutoriCheck = document.createElement("label");
      const esecutoriCheckbox = document.createElement("input");
      esecutoriCheckbox.type = "checkbox";
      esecutoriCheckbox.checked = item.numero_esecutori !== null;
      esecutoriCheck.appendChild(esecutoriCheckbox);
      esecutoriCheck.appendChild(document.createTextNode(" " + t("Number of performers differs from number of items")));
      esecutoriWrap.appendChild(esecutoriCheck);
      if (item.numero_esecutori !== null) {
        esecutoriWrap.appendChild(numberField(t("Number of performers"), item.numero_esecutori, 1, (v) => {
          item.numero_esecutori = Math.max(1, v);
          onChange();
        }));
      }
      esecutoriCheckbox.addEventListener("change", () => {
        item.numero_esecutori = esecutoriCheckbox.checked ? Math.max(1, item.numero_elementi) : null;
        onChange();
      });
      panel.appendChild(esecutoriWrap);

      const flags = document.createElement("div");
      flags.className = "oe-detail__flags";
      flags.appendChild(flagToggle(t("Solo"), item.solo, (v) => { item.solo = v; onChange(); }));
      flags.appendChild(flagToggle(t("Ad libitum"), item.ad_libitum, (v) => { item.ad_libitum = v; onChange(); }));
      flags.appendChild(flagToggle(t("Overdub"), item.overdub, (v) => { item.overdub = v; onChange(); }));
      flags.appendChild(flagToggle(t("Digital processing"), item.elaborazione_digitale, (v) => { item.elaborazione_digitale = v; onChange(); }));
      panel.appendChild(flags);

      panel.appendChild(suffixField(t("Suffix"), item.suffisso, (v) => {
        item.suffisso = v;
        onChange();
      }));
      panel.appendChild(textField(t("Section / part / voice"), item.sezione_parte_voce, t("e.g. I, II, S, A, T, B"), (v) => {
        item.sezione_parte_voce = v;
        onChange();
      }));

      if (item.gruppo_ensemble || item.alternativa_gruppo) {
        const undo = document.createElement("div");
        undo.className = "oe-detail__undo";
        if (item.gruppo_ensemble) {
          undo.appendChild(smallButton(t("Detach from ensemble group"), () => {
            item.gruppo_ensemble = null;
            item.numero_gruppo = null;
            onChange();
          }));
        }
        if (item.alternativa_gruppo) {
          undo.appendChild(smallButton(t("Remove from alternative"), () => {
            item.alternativa_gruppo = null;
            item.alternativa_opzione = null;
            onChange();
          }));
        }
        panel.appendChild(undo);
      }

      return panel;
    }

    function numberField(labelText, value, min, onInput) {
      const wrap = document.createElement("label");
      wrap.className = "oe-detail__field";
      const span = document.createElement("span");
      span.textContent = labelText;
      wrap.appendChild(span);
      const input = document.createElement("input");
      input.type = "number";
      input.min = String(min);
      input.value = String(value);
      input.addEventListener("change", () => onInput(parseInt(input.value, 10) || min));
      wrap.appendChild(input);
      return wrap;
    }

    // Select vincolato alla lista chiusa UNIMARC Appendice B (SUFFIX_CODES) con
    // via di fuga "Altro (testo libero)" per i casi non coperti (es. tonalita').
    function suffixField(labelText, value, onInput) {
      const wrap = document.createElement("label");
      wrap.className = "oe-detail__field";
      const span = document.createElement("span");
      span.textContent = labelText;
      wrap.appendChild(span);

      const select = document.createElement("select");
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = t("-- none --");
      select.appendChild(empty);
      for (const s of SUFFIX_CODES) {
        const opt = document.createElement("option");
        opt.value = s.label;
        opt.textContent = s.label;
        select.appendChild(opt);
      }
      const customOpt = document.createElement("option");
      customOpt.value = "__custom__";
      customOpt.textContent = t("Other (free text)…");
      select.appendChild(customOpt);

      const isKnown = value === "" || SUFFIX_CODES.some((s) => s.label === value);
      select.value = isKnown ? value || "" : "__custom__";
      wrap.appendChild(select);

      const customInput = document.createElement("input");
      customInput.type = "text";
      customInput.placeholder = t("e.g. in B flat");
      customInput.value = isKnown ? "" : value || "";
      customInput.hidden = isKnown;
      customInput.addEventListener("change", () => onInput(customInput.value));
      wrap.appendChild(customInput);

      select.addEventListener("change", () => {
        const isCustom = select.value === "__custom__";
        customInput.hidden = !isCustom;
        if (isCustom) {
          // non committare subito un valore vuoto: renderDetailPanel ridisegnerebbe
          // il pannello con item.suffisso === "" (isKnown=true) e nasconderebbe di
          // nuovo questo input appena mostrato. Si aspetta che l'utente scriva
          // davvero qualcosa (onChange di customInput, sopra).
          customInput.value = "";
          customInput.focus();
        } else {
          onInput(select.value);
        }
      });

      return wrap;
    }

    function textField(labelText, value, placeholder, onInput) {
      const wrap = document.createElement("label");
      wrap.className = "oe-detail__field";
      const span = document.createElement("span");
      span.textContent = labelText;
      wrap.appendChild(span);
      const input = document.createElement("input");
      input.type = "text";
      input.value = value || "";
      input.placeholder = placeholder;
      input.addEventListener("change", () => onInput(input.value));
      wrap.appendChild(input);
      return wrap;
    }

    function flagToggle(labelText, value, onChangeFlag) {
      const label = document.createElement("label");
      label.className = "oe-flag";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = value;
      input.addEventListener("change", () => onChangeFlag(input.checked));
      label.appendChild(input);
      label.appendChild(document.createTextNode(" " + labelText));
      return label;
    }

    function smallButton(text, onClick) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "oe-btn oe-btn--small";
      btn.textContent = text;
      btn.addEventListener("click", onClick);
      return btn;
    }

    // -------------------------------------------------------------------
    // Barra azioni bulk
    // -------------------------------------------------------------------

    function updateToolbar() {
      const n = state.selected.size;
      el.btnGroup.disabled = n < 2;
      el.btnAlt.disabled = n < 2;
      el.btnRemove.disabled = n < 1;
      if (el.btnClearAll) el.btnClearAll.disabled = state.items.length < 1;
    }

    el.btnRemove.addEventListener("click", () => {
      state.items = state.items.filter((it) => !state.selected.has(it.id));
      state.selected.clear();
      onChange();
    });

    function clearAllItems() {
      state.items = [];
      state.selected.clear();
      state.expandedId = null;
      state.nextAltGroup = 1;
    }

    // Cancella l'intero organico in un colpo solo, senza dover selezionare
    // strumento per strumento con "Rimuovi selezionati" — chiede conferma
    // perche' e' un'azione distruttiva e non annullabile dentro l'editor.
    function openClearAllModal() {
      const n = state.items.length;
      if (n < 1) return;

      const content = document.createElement("div");
      content.className = "oe-modal__content";

      const h = document.createElement("h3");
      h.textContent = t("Clear instrumentation");
      content.appendChild(h);

      const hint = document.createElement("p");
      hint.className = "oe-modal__hint";
      hint.textContent = t("This removes all {n} items in the instrumentation. This action cannot be undone.", { n });
      content.appendChild(hint);

      const actions = document.createElement("div");
      actions.className = "oe-modal__actions";
      actions.appendChild(smallButton(t("Cancel"), closeModal));

      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.className = "oe-btn oe-btn--danger oe-btn--primary";
      confirm.textContent = t("Clear all");
      confirm.addEventListener("click", () => {
        clearAllItems();
        closeModal();
        onChange();
      });
      actions.appendChild(confirm);

      content.appendChild(actions);
      openModal(content);
    }

    el.btnGroup.addEventListener("click", () => openGroupModal());
    el.btnAlt.addEventListener("click", () => openAlternativeModal());
    if (el.btnClearAll) el.btnClearAll.addEventListener("click", () => openClearAllModal());
    if (el.btnImportSbn) el.btnImportSbn.addEventListener("click", () => openImportSbnModal());

    // Nomi ensemble scelti da una lista chiusa (non testo libero): per compatibilita'
    // IFLA il "gruppo_ensemble" deve essere uno dei termini del vocabolario UNIMARC
    // MOP nelle due famiglie "orchestras, ensembles" (o) e "choruses" (c), non
    // un'etichetta inventata dal catalogatore - cosi' porta con se' anche la URI MOP,
    // come gia' avviene per i singoli mezzi di esecuzione.
    function ensembleTerms() {
      const list = vocabulary || [];
      return {
        instrumental: list.filter((t) => t.broader === "o"),
        choral: list.filter((t) => t.broader === "c"),
      };
    }

    function populateEnsembleSelect(select) {
      select.innerHTML = "";
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.disabled = true;
      placeholder.selected = true;
      if (vocabulary === null) {
        placeholder.textContent = t("Loading MOP vocabulary…");
        select.appendChild(placeholder);
        select.disabled = true;
        return;
      }
      placeholder.textContent = t("-- select an ensemble --");
      select.appendChild(placeholder);
      select.disabled = false;

      const { instrumental, choral } = ensembleTerms();
      const addGroup = (label, terms) => {
        if (terms.length === 0) return;
        const group = document.createElement("optgroup");
        group.label = label;
        for (const t of terms) {
          const opt = document.createElement("option");
          opt.value = t.label;
          opt.dataset.uri = t.uri;
          opt.textContent = t.label;
          group.appendChild(opt);
        }
        select.appendChild(group);
      };
      addGroup(t("Instrumental ensembles"), instrumental);
      addGroup(t("Choirs / group voices"), choral);

      // via di fuga: alcuni raggruppamenti attestati nelle norme di catalogazione (es. ICCU)
      // non sono "ensemble" in senso IFLA MOP ma raggruppamenti tecnici per esecutore/
      // realizzazione (es. "Percussioni 1"/"Percussioni 2" per due esecutori di percussioni
      // diverse, "Continuo" per la realizzazione del basso continuo) - non compaiono nella
      // lista IFLA o/c ma sono un uso legittimo e frequente. Restano distinti visivamente
      // dai termini IFLA cosi' resta chiaro cosa e' conforme e cosa no.
      const technicalGroup = document.createElement("optgroup");
      technicalGroup.label = t("Technical groupings (non-IFLA)");
      // il "value" resta la stringa canonica italiana (e' quella salvata nel payload,
      // deve restare stabile a prescindere dalla lingua dell'interfaccia); solo
      // l'etichetta visibile si traduce.
      for (const [canonical, displayKey] of [["Percussioni", "Percussion"], ["Continuo", "Continuo"]]) {
        const opt = document.createElement("option");
        opt.value = canonical;
        opt.textContent = t(displayKey);
        technicalGroup.appendChild(opt);
      }
      const customOpt = document.createElement("option");
      customOpt.value = "__custom__";
      customOpt.textContent = t("Other (free text)…");
      technicalGroup.appendChild(customOpt);
      select.appendChild(technicalGroup);
    }

    function openGroupModal() {
      const ids = Array.from(state.selected);
      const content = document.createElement("div");
      content.className = "oe-modal__content";

      const h = document.createElement("h3");
      h.textContent = t("Group into ensemble");
      content.appendChild(h);
      const hint = document.createElement("p");
      hint.className = "oe-modal__hint";
      hint.textContent = t('{n} instruments selected. The ensemble name is chosen from the IFLA MOP vocabulary, for compatibility (for non-IFLA technical groupings, e.g. "Continuo", use "Technical groupings" or "Other"). The "group number" is optional: use it when the same ensemble has multiple sub-groups (e.g. "Percussion" 1 and 2, one performer each) - the label numbers itself automatically.', { n: ids.length });
      content.appendChild(hint);

      const labelField = document.createElement("label");
      labelField.className = "oe-detail__field";
      labelField.innerHTML = `<span>${t("Ensemble name (IFLA MOP)")}</span>`;
      const labelSelect = document.createElement("select");
      labelSelect.className = "oe-ensemble-select";
      populateEnsembleSelect(labelSelect);
      labelField.appendChild(labelSelect);
      content.appendChild(labelField);
      vocabularyReady.then(() => populateEnsembleSelect(labelSelect));

      const customLabelField = document.createElement("label");
      customLabelField.className = "oe-detail__field";
      customLabelField.hidden = true;
      customLabelField.innerHTML = `<span>${t("Custom label")}</span>`;
      const customLabelInput = document.createElement("input");
      customLabelInput.type = "text";
      customLabelInput.placeholder = t("e.g. Percussion, Continuo, ...");
      customLabelField.appendChild(customLabelInput);
      content.appendChild(customLabelField);
      labelSelect.addEventListener("change", () => {
        customLabelField.hidden = labelSelect.value !== "__custom__";
        if (!customLabelField.hidden) customLabelInput.focus();
      });

      const numeroField = document.createElement("label");
      numeroField.className = "oe-detail__field";
      numeroField.innerHTML = `<span>${t("Group number (optional)")}</span>`;
      const numeroInput = document.createElement("input");
      numeroInput.type = "number";
      numeroInput.min = "1";
      numeroField.appendChild(numeroInput);
      content.appendChild(numeroField);

      const actions = document.createElement("div");
      actions.className = "oe-modal__actions";
      actions.appendChild(smallButton(t("Cancel"), closeModal));
      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.className = "oe-btn oe-btn--primary";
      confirm.textContent = t("Group");
      confirm.addEventListener("click", () => {
        const isCustom = labelSelect.value === "__custom__";
        const label = isCustom ? customLabelInput.value.trim() : labelSelect.value;
        if (!label) {
          (isCustom ? customLabelInput : labelSelect).focus();
          return;
        }
        const uri = (!isCustom && labelSelect.selectedOptions[0]) ? (labelSelect.selectedOptions[0].dataset.uri || null) : null;
        const numero = numeroInput.value ? parseInt(numeroInput.value, 10) : null;
        for (const it of state.items) {
          if (ids.includes(it.id)) {
            it.gruppo_ensemble = { label, uri, numero_gruppo: numero };
            it.numero_gruppo = numero;
          }
        }
        closeModal();
        onChange();
      });
      actions.appendChild(confirm);
      content.appendChild(actions);

      openModal(content);
    }

    function openAlternativeModal() {
      const ids = Array.from(state.selected);
      const opzioni = new Map(ids.map((id) => [id, 1]));

      const content = document.createElement("div");
      content.className = "oe-modal__content";

      const h = document.createElement("h3");
      h.textContent = t("Create alternative");
      content.appendChild(h);
      const hint = document.createElement("p");
      hint.className = "oe-modal__hint";
      hint.textContent = t('Assign the same "Option" number to instruments that should be shown together as a single bundle (e.g. flute+piccolo = option 1); use a different number for the alternative (e.g. trumpet+cornet = option 2).');
      content.appendChild(hint);

      const table = document.createElement("div");
      table.className = "oe-alt-table";
      for (const id of ids) {
        const item = state.items.find((it) => it.id === id);
        const row = document.createElement("div");
        row.className = "oe-alt-table__row";
        const label = document.createElement("span");
        label.innerHTML = `<svg width="18" height="18"><use href="#icon-${item.icon}"></use></svg> ${escapeHtml(item.label)}`;
        row.appendChild(label);
        const input = document.createElement("input");
        input.type = "number";
        input.min = "1";
        input.value = "1";
        input.addEventListener("input", () => {
          opzioni.set(id, parseInt(input.value, 10) || 1);
        });
        row.appendChild(input);
        table.appendChild(row);
      }
      content.appendChild(table);

      const error = document.createElement("p");
      error.className = "oe-modal__error";
      error.hidden = true;
      error.textContent = t("At least two different options are needed to create an alternative.");
      content.appendChild(error);

      const actions = document.createElement("div");
      actions.className = "oe-modal__actions";
      actions.appendChild(smallButton(t("Cancel"), closeModal));
      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.className = "oe-btn oe-btn--primary";
      confirm.textContent = t("Create alternative");
      confirm.addEventListener("click", () => {
        const distinctOptions = new Set(opzioni.values());
        if (distinctOptions.size < 2) {
          error.hidden = false;
          return;
        }
        const gruppo = state.nextAltGroup++;
        for (const it of state.items) {
          if (opzioni.has(it.id)) {
            it.alternativa_gruppo = gruppo;
            it.alternativa_opzione = opzioni.get(it.id);
          }
        }
        closeModal();
        onChange();
      });
      actions.appendChild(confirm);
      content.appendChild(actions);

      openModal(content);
    }

    // Importazione assistita da "Organico analitico (SBN MARC)" (vedi
    // organico-sbn-parser.js): il catalogatore incolla il testo gia'
    // catalogato, vede un'anteprima di cosa e' stato riconosciuto e cosa no,
    // e solo dopo conferma gli item vengono aggiunti allo stato — nessuna
    // scrittura automatica, il testo originale nel campo CA non viene toccato.
    function openImportSbnModal() {
      const content = document.createElement("div");
      content.className = "oe-modal__content";

      const h = document.createElement("h3");
      h.textContent = t("Import from text (SBN MARC)");
      content.appendChild(h);
      const hint = document.createElement("p");
      hint.className = "oe-modal__hint";
      hint.textContent = t('Paste here the already catalogued value of the "Analytical instrumentation (SBN MARC)" field (e.g. "pf-solo,fl,2ob,2fag,2cor,2vl,vla,vlc,cb"). The text is analyzed but not modified; after the preview you can correct each item before saving.');
      content.appendChild(hint);

      const textarea = document.createElement("textarea");
      textarea.className = "oe-sbn-import__input";
      textarea.rows = 3;
      textarea.placeholder = t("e.g.") + " pf-solo,fl,2ob,2fag,2cor,2vl,vla,vlc,cb";
      content.appendChild(textarea);

      // La scelta "aggiungi/sostituisci" ha senso solo se c'e' gia' qualcosa
      // nell'organico: importare piu' volte lo stesso testo altrimenti
      // sommava gli strumenti invece di limitarsi ad aggiornarli, ed era
      // facile farlo per sbaglio (es. ririaprire il modal e confermare di
      // nuovo). Il numero di elementi esistenti e' fissato all'apertura del
      // modal: se cambia nel frattempo (non dovrebbe, il modal e' bloccante)
      // resta comunque coerente con cio' che l'utente ha visto.
      const existingCount = state.items.length;
      let importMode = "add";
      if (existingCount > 0) {
        const modeField = document.createElement("fieldset");
        modeField.className = "oe-field oe-field--radio";
        const legend = document.createElement("legend");
        legend.textContent = t("How to import");
        modeField.appendChild(legend);

        const addLabel = document.createElement("label");
        const addRadio = document.createElement("input");
        addRadio.type = "radio";
        addRadio.name = "oe-sbn-import-mode";
        addRadio.value = "add";
        addRadio.checked = true;
        addLabel.appendChild(addRadio);
        addLabel.appendChild(document.createTextNode(" " + t("Add to the {n} existing items", { n: existingCount })));
        modeField.appendChild(addLabel);

        const replaceLabel = document.createElement("label");
        const replaceRadio = document.createElement("input");
        replaceRadio.type = "radio";
        replaceRadio.name = "oe-sbn-import-mode";
        replaceRadio.value = "replace";
        replaceLabel.appendChild(replaceRadio);
        replaceLabel.appendChild(document.createTextNode(" " + t("Replace the {n} existing items", { n: existingCount })));
        modeField.appendChild(replaceLabel);

        modeField.addEventListener("change", (e) => {
          if (e.target && e.target.name === "oe-sbn-import-mode") importMode = e.target.value;
        });
        content.appendChild(modeField);
      }

      const preview = document.createElement("div");
      preview.className = "oe-sbn-import__preview";
      preview.hidden = true;
      content.appendChild(preview);

      let parsed = null;

      const actions = document.createElement("div");
      actions.className = "oe-modal__actions";
      actions.appendChild(smallButton(t("Cancel"), closeModal));

      const analyze = document.createElement("button");
      analyze.type = "button";
      analyze.className = "oe-btn";
      analyze.textContent = t("Analyze");
      actions.appendChild(analyze);

      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.className = "oe-btn oe-btn--primary";
      confirm.textContent = t("Import items");
      confirm.hidden = true;
      actions.appendChild(confirm);

      content.appendChild(actions);

      analyze.addEventListener("click", async () => {
        await sbnDictionaryReady;
        parsed = parseSbnMarc(textarea.value, sbnDictionary || {});
        renderSbnPreview(preview, parsed);
        preview.hidden = false;
        confirm.hidden = parsed.items.length === 0;
      });

      confirm.addEventListener("click", () => {
        if (!parsed || parsed.items.length === 0) return;
        if (importMode === "replace") clearAllItems();
        const groupOffset = state.nextAltGroup;
        let maxAltGroup = 0;
        for (const entry of parsed.items) {
          const item = makeItem(entry);
          item.numero_elementi = entry.numero_elementi;
          item.solo = entry.solo;
          item.ad_libitum = entry.ad_libitum;
          item.suffisso = entry.suffisso;
          item.gruppo_ensemble = entry.gruppo_ensemble;
          if (entry.alternativa_gruppo) {
            item.alternativa_gruppo = groupOffset + entry.alternativa_gruppo - 1;
            item.alternativa_opzione = entry.alternativa_opzione;
            maxAltGroup = Math.max(maxAltGroup, entry.alternativa_gruppo);
          }
          state.items.push(item);
        }
        state.nextAltGroup = groupOffset + maxAltGroup;
        closeModal();
        onChange();
      });

      openModal(content);
    }

    function renderSbnPreview(container, parsedResult) {
      const items = parsedResult.items;
      const warnings = parsedResult.warnings;
      container.innerHTML = "";
      if (items.length === 0) {
        const p = document.createElement("p");
        p.className = "oe-modal__hint";
        p.textContent = t("No items recognized in the pasted text.");
        container.appendChild(p);
        return;
      }

      const unmatchedCount = items.filter((it) => !it.found).length;
      const summary = document.createElement("p");
      summary.className = "oe-modal__hint";
      summary.textContent = t("{n} items found", { n: items.length }) + (unmatchedCount > 0 ? t(", {m} to review (highlighted below).", { m: unmatchedCount }) : ".");
      container.appendChild(summary);

      const list = document.createElement("div");
      list.className = "oe-sbn-import__list";
      for (const it of items) {
        const row = document.createElement("div");
        row.className = "oe-sbn-import__row" + (it.found ? "" : " oe-sbn-import__row--unmatched");
        const bits = [];
        if (it.numero_elementi > 1) bits.push(`×${it.numero_elementi}`);
        if (it.solo) bits.push("solo");
        if (it.ad_libitum) bits.push("ad lib.");
        if (it.suffisso) bits.push(it.suffisso);
        if (it.gruppo_ensemble) bits.push(`gruppo: ${it.gruppo_ensemble.label}`);
        if (it.alternativa_gruppo) bits.push(`alternativa ${it.alternativa_gruppo}.${it.alternativa_opzione}`);
        row.innerHTML = `<svg width="18" height="18"><use href="#icon-${it.icon}"></use></svg>` +
          `<span>${escapeHtml(it.label)}</span>` +
          (bits.length ? `<small>${escapeHtml(bits.join(" · "))}</small>` : "") +
          (it.found ? "" : `<small class="oe-sbn-import__flag">non riconosciuto: "${escapeHtml(it.raw)}"</small>`);
        list.appendChild(row);
      }
      container.appendChild(list);

      if (warnings.length > 0) {
        const warnList = document.createElement("ul");
        warnList.className = "oe-sbn-import__warnings";
        for (const w of warnings) {
          const li = document.createElement("li");
          li.textContent = w;
          warnList.appendChild(li);
        }
        container.appendChild(warnList);
      }
    }

    function openModal(content) {
      el.modal.innerHTML = "";
      el.modal.appendChild(content);
      el.modalBackdrop.hidden = false;
    }

    function closeModal() {
      el.modalBackdrop.hidden = true;
      el.modal.innerHTML = "";
    }

    el.modalBackdrop.addEventListener("click", (e) => {
      if (e.target === el.modalBackdrop) closeModal();
    });

    // -------------------------------------------------------------------
    // Intestazione
    // -------------------------------------------------------------------

    if (el.titolo) {
      el.titolo.addEventListener("input", () => {
        state.titolo = el.titolo.value;
        onChange();
      });
    }
    if (el.organicoSintetico) {
      el.organicoSintetico.addEventListener("input", () => {
        state.organicoSintetico = el.organicoSintetico.value;
        onChange();
      });
    }
    el.ensembleTypeRadios.forEach((radio) => {
      radio.addEventListener("change", () => {
        if (radio.checked) {
          state.ensembleType = radio.value;
          onChange();
        }
      });
    });

    // -------------------------------------------------------------------
    // Payload grezzo (formato docs/schema.md) + anteprima live
    // -------------------------------------------------------------------

    function buildRawPayload() {
      // If the vocabulary has already loaded, make serialization itself the
      // final canonicalization boundary as well as the asynchronous refresh
      // below. This covers quick open/edit/save sequences without relying on
      // a prior repaint of the editor.
      reconcileCanonicalMopData();
      return {
        titolo: state.titolo,
        organico_sintetico: state.organicoSintetico,
        ensemble_type: state.ensembleType,
        items: state.items.map((it, idx) => ({
          numero_elemento: idx + 1,
          alternativa_gruppo: it.alternativa_gruppo,
          alternativa_opzione: it.alternativa_opzione,
          mezzo_esecuzione: {
            label: it.mezzoLabel,
            mop_code: it.mopCode || mopCodeFromUri(it.mopUri),
            mop_uri: it.mopUri || null,
            wikidata_uri: it.wikidataUri || null,
          },
          numero_elementi: it.numero_elementi,
          numero_esecutori: it.numero_esecutori,
          gruppo_ensemble: it.gruppo_ensemble ? { label: it.gruppo_ensemble.label, uri: it.gruppo_ensemble.uri || null } : null,
          numero_gruppo: it.numero_gruppo ?? null,
          solo: it.solo,
          ad_libitum: it.ad_libitum,
          overdub: it.overdub,
          elaborazione_digitale: it.elaborazione_digitale,
          suffisso: it.suffisso || null,
          sezione_parte_voce: it.sezione_parte_voce || null,
        })),
      };
    }

    let previewTimer = null;
    function schedulePreview() {
      if (previewTimer) clearTimeout(previewTimer);
      previewTimer = setTimeout(runPreview, PREVIEW_DEBOUNCE_MS);
    }

    function runPreview() {
      const raw = buildRawPayload();
      if (el.json) el.json.value = JSON.stringify(raw, null, 2);
      if (options.onPayloadChange) options.onPayloadChange(raw);

      if (raw.items.length === 0) {
        el.previewStage.innerHTML = `<p class="organico-stage__empty">${t("No instrumentation to display.")}</p>`;
        return;
      }
      try {
        const normalized = normalizer.buildRenderPayload(raw);
        renderOrganicoStage(el.previewStage, normalized, spriteUrl);
      } catch (err) {
        console.error("[organico-editor] anteprima non disponibile", err);
        el.previewStage.innerHTML = `<p class="organico-stage__empty">${t("Preview not available (unexpected error).")}</p>`;
      }
    }

    if (el.btnCopy) {
      el.btnCopy.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(el.json.value);
          el.btnCopy.textContent = t("Copied ✓");
          setTimeout(() => { el.btnCopy.textContent = t("Copy JSON"); }, 1200);
        } catch {
          el.json.select();
        }
      });
    }

    // -------------------------------------------------------------------
    // Ciclo di rendering
    // -------------------------------------------------------------------

    function onChange(opts) {
      opts = opts || {};
      updateToolbar();
      renderList();
      if (!opts.skipPreview) {
        schedulePreview();
      }
    }

    function escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    }

    loadInitialPayload(options.initialPayload);
    initPalette();
    updateToolbar();
    renderList();
    schedulePreview();
    Promise.all([vocabularyReady, sbnDictionaryReady]).then(() => {
      if (reconcileCanonicalMopData()) onChange();
    });

    return { getPayload: buildRawPayload };
  }

  window.caUI.Organico.mountEditor = mountOrganicoEditor;

  // ---------------------------------------------------------------------
  // Aggancio per OrganicoAttributeValue::htmlFormElement(): riassunto
  // compatto + pulsante "Modifica organico" che apre il pannello overlay
  // con l'editor completo (stile FloorplanAttributeValue: niente editor
  // grande incastrato nella cella della tabella dei bundle).
  // ---------------------------------------------------------------------

  function summarizePayload(raw) {
    if (!raw) return t("No instrumentation");
    const n = (raw.items || []).length;
    if (raw.organico_sintetico) return raw.organico_sintetico;
    if (n === 0) return t("No instrumentation");
    return n + " " + (n === 1 ? t("item") : t("items"));
  }

  /**
   * @param {string} wrapId  id del contenitore radice reso da OrganicoAttributeValue
   */
  function initField(wrapId) {
    const wrap = document.getElementById(wrapId);
    if (!wrap) return;
    const hidden = wrap.querySelector(".organico-field__value");
    const summaryText = wrap.querySelector(".organico-field__summary-text");
    const summaryStage = wrap.querySelector(".organico-field__summary-stage");
    const editBtn = wrap.querySelector(".organico-field__edit-btn");
    const panel = wrap.querySelector(".organico-field__panel");
    const closeBtn = wrap.querySelector(".organico-field__panel-close");
    const editorRoot = wrap.querySelector(".oe-app");
    const spriteUrl = editorRoot.getAttribute("data-icons-sprite");

    // Il pannello e' "position: fixed", pensato per coprire l'intero viewport: se pero'
    // un antenato nella pagina reale di CA ha transform/filter/contain (frequente nei
    // layout a griglia delle righe bundle), quell'antenato diventa il containing block
    // del fixed invece del viewport, e il pannello (bottone "Chiudi e salva" incluso,
    // sticky al suo interno) finisce disallineato/parzialmente coperto dalla toolbar
    // fissa del sito invece di ricoprire tutta la pagina. Spostare il pannello come
    // figlio diretto di <body> lo rende immune a qualunque antenato "rotto" in questo
    // modo, indipendentemente da quale sia la causa esatta nella pagina ospite.
    if (panel && panel.parentElement !== document.body) {
      document.body.appendChild(panel);
    }

    function currentPayload() {
      try {
        return hidden.value ? JSON.parse(hidden.value) : null;
      } catch (e) {
        return null;
      }
    }

    // il box compatto (fuori dal pannello di modifica) mostra sia la riga di sintesi
    // testuale (es. "fl/cl, orch(vl,vla,vlc)") sia il disegno del ventaglio/righe in
    // miniatura, cosi' la sintesi visiva e' visibile senza dover aprire il pannello.
    function refreshSummary() {
      const raw = currentPayload();
      summaryText.textContent = summarizePayload(raw);
      if (!raw || !(raw.items || []).length) {
        summaryStage.innerHTML = "";
        summaryStage.hidden = true;
        return;
      }
      summaryStage.hidden = false;
      try {
        const normalized = window.caUI.Organico.normalizer.buildRenderPayload(raw);
        window.caUI.Organico.renderStage(summaryStage, normalized, spriteUrl);
      } catch (err) {
        console.error("[organico-editor] anteprima compatta non disponibile", err);
        summaryStage.innerHTML = "";
        summaryStage.hidden = true;
      }
    }
    refreshSummary();

    let mounted = false;
    editBtn.addEventListener("click", () => {
      panel.classList.add("organico-field__panel--open");
      if (!mounted) {
        mounted = true;
        window.caUI.Organico.mountEditor(editorRoot, {
          initialPayload: currentPayload(),
          onPayloadChange: (raw) => {
            hidden.value = JSON.stringify(raw);
            hidden.dispatchEvent(new Event("change", { bubbles: true }));
            refreshSummary();
          },
        });
      }
    });

    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        panel.classList.remove("organico-field__panel--open");
      });
    }
  }

  window.caUI.Organico.initField = initField;
})();
