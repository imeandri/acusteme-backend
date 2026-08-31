/**
 * Porting JS di src/IconDictionary.php (resolve/normalizeLabel) e
 * src/OrganicoNormalizer.php (normalize/inferEnsembleType), usati
 * dall'editor per l'anteprima live dentro CollectiveAccess: qui non e'
 * raggiungibile un endpoint PHP arbitrario (vedi .htaccess di Providence,
 * solo index.php/service.php/tilepic.php sono permessi), quindi la
 * normalizzazione gira interamente lato client.
 *
 * Le TABELLE DATI (INSTRUMENTS/ALIASES/...) vengono da organico-data.js
 * (window.OrganicoData), generato da organico-viewer/build/build-normalizer-js.php
 * a partire dalla stessa fonte usata dal PHP: se cambia il dizionario,
 * rigenerare quel file, non modificare qui le tabelle a mano.
 *
 * Espone window.caUI.Organico.normalizer = { resolve, buildRenderPayload }.
 */
(function () {
  "use strict";
  window.caUI = window.caUI || {};
  window.caUI.Organico = window.caUI.Organico || {};

  const DATA = window.OrganicoData || { FAMILY_FALLBACK_ICON: {}, INSTRUMENTS: {}, ALIASES: {}, GENERIC_FAMILY_LABELS: {} };

  // ---------------------------------------------------------------------
  // IconDictionary::normalizeLabel / resolve
  // ---------------------------------------------------------------------

  function normalizeLabel(label) {
    let s = String(label || "").trim().toLowerCase();
    s = s.normalize("NFD").replace(new RegExp("[\u0300-\u036f]", "g"), ""); // rimuove diacritici, equivalente a iconv TRANSLIT
    s = s.replace(/[^a-z0-9\s-]/g, "");
    s = s.replace(/\s+/g, " ");
    return s.trim();
  }

  function resolve(label) {
    const norm = normalizeLabel(label);

    if (Object.prototype.hasOwnProperty.call(DATA.ALIASES, norm)) {
      const key = DATA.ALIASES[norm];
      return Object.assign({}, DATA.INSTRUMENTS[key], { matched: true });
    }

    const firstWord = norm.split(/[\s-]/)[0];
    if (firstWord && Object.prototype.hasOwnProperty.call(DATA.ALIASES, firstWord)) {
      const key = DATA.ALIASES[firstWord];
      return Object.assign({}, DATA.INSTRUMENTS[key], { matched: true });
    }

    if (norm !== "") {
      for (const aliasLabel in DATA.ALIASES) {
        if (norm.includes(aliasLabel) || aliasLabel.includes(norm)) {
          const key = DATA.ALIASES[aliasLabel];
          return Object.assign({}, DATA.INSTRUMENTS[key], { matched: true });
        }
      }
    }

    if (Object.prototype.hasOwnProperty.call(DATA.GENERIC_FAMILY_LABELS, norm)) {
      const family = DATA.GENERIC_FAMILY_LABELS[norm];
      return { icon: DATA.FAMILY_FALLBACK_ICON[family], family, matched: false };
    }

    return { icon: DATA.FAMILY_FALLBACK_ICON.altro || "sconosciuto", family: "altro", matched: false };
  }

  // ---------------------------------------------------------------------
  // OrganicoNormalizer::normalize (items grezzi -> units di primo livello)
  // ---------------------------------------------------------------------

  function buildSimpleUnit(raw) {
    const mezzo = raw.mezzo_esecuzione || {};
    const label = mezzo.label || "";
    const resolved = resolve(label);
    return {
      type: "simple",
      numero_elemento: parseInt(raw.numero_elemento, 10),
      label,
      uri: mezzo.uri || null,
      mop_uri: mezzo.mop_uri || null,
      wikidata_uri: mezzo.wikidata_uri || null,
      icon: resolved.icon,
      family: resolved.family,
      iconMatched: resolved.matched,
      count: Math.max(1, parseInt(raw.numero_elementi, 10) || 1),
      numero_esecutori: (raw.numero_esecutori !== undefined && raw.numero_esecutori !== null) ? parseInt(raw.numero_esecutori, 10) : null,
      gruppo_ensemble: raw.gruppo_ensemble || null,
      numero_gruppo: (raw.numero_gruppo !== undefined) ? raw.numero_gruppo : null,
      solo: !!raw.solo,
      ad_libitum: !!raw.ad_libitum,
      overdub: !!raw.overdub,
      elaborazione_digitale: !!raw.elaborazione_digitale,
      suffisso: raw.suffisso || null,
      sezione_parte_voce: raw.sezione_parte_voce || null,
    };
  }

  /** gruppo -> opzione -> [numero_elemento,...], come OrganicoNormalizer::buildAlternativeSets */
  function buildAlternativeSets(items) {
    const byGroup = new Map();
    for (const raw of items) {
      const gruppo = raw.alternativa_gruppo;
      if (gruppo === undefined || gruppo === null) continue;
      const opzione = (raw.alternativa_opzione !== undefined && raw.alternativa_opzione !== null) ? raw.alternativa_opzione : 0;
      if (!byGroup.has(gruppo)) byGroup.set(gruppo, new Map());
      const opzioni = byGroup.get(gruppo);
      if (!opzioni.has(opzione)) opzioni.set(opzione, []);
      opzioni.get(opzione).push(parseInt(raw.numero_elemento, 10));
    }
    const sets = [];
    for (const opzioni of byGroup.values()) {
      const keys = Array.from(opzioni.keys()).sort((a, b) => (a > b ? 1 : a < b ? -1 : 0));
      sets.push({ bundles: keys.map((k) => opzioni.get(k)) });
    }
    return sets;
  }

  function normalize(items) {
    if (!items || items.length === 0) return [];

    const simpleByElemento = new Map();
    for (const raw of items) {
      const unit = buildSimpleUnit(raw);
      simpleByElemento.set(unit.numero_elemento, unit);
    }

    const altSets = buildAlternativeSets(items);

    const nodes = new Map(); // numero_elemento minimo -> node
    const consumed = new Set();
    for (const set of altSets) {
      const bundles = set.bundles;
      if (bundles.length < 2) {
        for (const e of bundles[0] || []) {
          nodes.set(e, simpleByElemento.get(e));
          consumed.add(e);
        }
        continue;
      }
      const options = bundles.map((bundle) => bundle.map((e) => simpleByElemento.get(e)));
      const minElemento = Math.min(...bundles.flat());
      nodes.set(minElemento, { type: "alternative", options, primaryElemento: minElemento });
      for (const bundle of bundles) {
        for (const e of bundle) consumed.add(e);
      }
    }
    for (const [elemento, unit] of simpleByElemento) {
      if (!consumed.has(elemento)) nodes.set(elemento, unit);
    }

    const sortedKeys = Array.from(nodes.keys()).sort((a, b) => a - b);
    const orderedNodes = sortedKeys.map((k) => nodes.get(k));

    return clusterByEnsemble(orderedNodes, sortedKeys);
  }

  /** Raggruppa i nodi che condividono gruppo_ensemble.label + numero_gruppo in una unit "cluster". */
  function clusterByEnsemble(orderedNodes, sortedKeys) {
    function clusterKeyFor(node) {
      const primary = node.type === "alternative" ? node.options[0][0] : node;
      const label = primary.gruppo_ensemble ? primary.gruppo_ensemble.label : null;
      const numero = (primary.numero_gruppo !== undefined) ? primary.numero_gruppo : null;
      if (label === null || label === undefined || numero === null || numero === undefined) return null;
      return label + "::" + numero;
    }

    const clusters = new Map(); // key -> {label, numeroGruppo, uri, members:[], minElemento}
    const roots = new Map(); // elemento -> node

    orderedNodes.forEach((node, i) => {
      const elemento = sortedKeys[i];
      const key = clusterKeyFor(node);
      if (key === null) {
        roots.set(elemento, node);
        return;
      }
      if (!clusters.has(key)) {
        const primary = node.type === "alternative" ? node.options[0][0] : node;
        clusters.set(key, {
          type: "cluster",
          label: primary.gruppo_ensemble.label,
          numeroGruppo: primary.numero_gruppo,
          uri: (primary.gruppo_ensemble && primary.gruppo_ensemble.uri) || null,
          members: [],
          minElemento: elemento,
        });
      }
      const cluster = clusters.get(key);
      cluster.members.push(node);
      cluster.minElemento = Math.min(cluster.minElemento, elemento);
    });

    // convenzione "dettagliato o no": se lo stesso gruppo_ensemble.label compare con piu'
    // numero_gruppo distinti, numera automaticamente l'etichetta ("Percussioni 1", "Percussioni 2"...)
    const labelOccurrences = new Map();
    for (const cluster of clusters.values()) {
      labelOccurrences.set(cluster.label, (labelOccurrences.get(cluster.label) || 0) + 1);
    }
    for (const cluster of clusters.values()) {
      if (labelOccurrences.get(cluster.label) > 1 && cluster.numeroGruppo !== null && cluster.numeroGruppo !== undefined) {
        cluster.label = cluster.label + " " + cluster.numeroGruppo;
      }
    }

    const result = new Map(roots);
    for (const cluster of clusters.values()) {
      result.set(cluster.minElemento, cluster);
    }

    const finalKeys = Array.from(result.keys()).sort((a, b) => a - b);
    return finalKeys.map((k) => result.get(k));
  }

  // ---------------------------------------------------------------------
  // OrganicoNormalizer::inferEnsembleType
  // ---------------------------------------------------------------------

  function collectFamilies(units, families) {
    for (const unit of units) {
      if (unit.type === "simple") {
        families[unit.family] = (families[unit.family] || 0) + unit.count;
      } else if (unit.type === "alternative") {
        collectFamilies(unit.options[0], families);
      } else if (unit.type === "cluster") {
        collectFamilies(unit.members, families);
      }
    }
  }

  function inferEnsembleType(units) {
    const families = {};
    collectFamilies(units, families);
    const hasStrings = (families.archi || 0) >= 3;
    const hasWinds = (families.legni || 0) >= 2;
    const hasBrass = (families.ottoni || 0) >= 1;
    return (hasStrings && hasWinds && hasBrass) ? "orchestra" : "ensemble";
  }

  // ---------------------------------------------------------------------
  // OrganicoRenderer::buildRenderPayload
  // ---------------------------------------------------------------------

  function buildRenderPayload(payload) {
    const items = payload.items || [];
    const units = normalize(items);
    let ensembleType = payload.ensemble_type;
    if (!ensembleType || ensembleType === "auto") {
      ensembleType = inferEnsembleType(units);
    }
    return {
      titolo: payload.titolo || payload.organico_sintetico || "",
      organico_sintetico: payload.organico_sintetico || "",
      ensemble_type: ensembleType,
      units,
    };
  }

  window.caUI.Organico.normalizer = { resolve, normalize, inferEnsembleType, buildRenderPayload };
})();
