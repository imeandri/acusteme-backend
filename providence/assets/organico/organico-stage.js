/**
 * Motore di rendering SVG dell'organico (ventaglio orchestrale a fasce per
 * famiglia, oppure righe per ensemble non classici). Copia vendorizzata da
 * Acusteme/frontend/special-interfaces/Organico/stage.js (il visualizzatore
 * di sola lettura, aggiornato 2026-08-05 con layout "compact instrumentation
 * viewer": geometria del ventaglio adattiva alla densita', celle uniformi in
 * modalita' ensemble, etichette troncate in modalita' compatta, seat cliccabili
 * quando hanno un mop_uri/uri) — a sua volta originato da
 * organico-viewer/assets/js/organico-stage.js. Qui riesposta come
 * window.caUI.Organico.* invece di window.AcustemeOrganico.*, perche' gli
 * script CA si caricano come <script> classici via AssetLoadManager, non
 * come moduli. Rigenerare copiando dal frontend se il motore di rendering
 * cambia ancora — MA attenzione: qui le stringhe di interfaccia sono state
 * convertite da testo italiano hardcoded a chiamate t("English source
 * string") (dizionario window.caUI.Organico.i18n, popolato da
 * OrganicoAttributeValue::buildI18nJson(), catalogo in
 * app/locale/user/it_IT/messages.po) — il frontend Acusteme resta invece in
 * italiano semplice, senza t(). Un resync da qui in poi deve riapplicare
 * questa conversione i18n a mano, altrimenti si perde.
 */
/**
 * Motore di rendering del "palco" organico. Nessuna dipendenza esterna.
 *
 * Uso tipico (lato PHP, via OrganicoRenderer::renderPartial):
 *   <div class="organico-stage" data-organico='{...}' data-icons-sprite="assets/icons/sprite.svg"></div>
 *   <script type="module">
 *     import { mountOrganicoStage } from "./assets/js/organico-stage.js";
 *     mountOrganicoStage(document.querySelector(".organico-stage"));
 *   </script>
 *
 * Oppure programmaticamente con un payload gia' in mano (es. da fetch
 * verso api/organico.php?format=json):
 *   renderOrganicoStage(container, payload, "assets/icons/sprite.svg");
 */

const SVG_NS = "http://www.w3.org/2000/svg";

// Traduzione: il dizionario window.caUI.Organico.i18n viene popolato da
// OrganicoAttributeValue::htmlFormElement() con le stesse stringhe passate a
// _t() lato PHP (vedi app/locale/user/it_IT/messages.po). La chiave inglese
// e' anche il fallback quando il dizionario manca (es. uso standalone).
function t(key, vars) {
  const dict = (window.caUI && window.caUI.Organico && window.caUI.Organico.i18n) || {};
  let str = Object.prototype.hasOwnProperty.call(dict, key) ? dict[key] : key;
  if (vars) {
    for (const k in vars) {
      str = str.split("{" + k + "}").join(vars[k]);
    }
  }
  return str;
}

// Conservato sui placement per compatibilita' con il payload editor. Il layout
// ensemble non usa questo valore per riordinare o aggregare gli strumenti: la
// sequenza visuale resta quella stabilita dal catalogatore.
const FAMILY_ROW = {
  archi: 1,
  pizzicati: 2,
  legni: 2,
  ottoni: 3,
  tastiere: 4,
  percussioni: 4,
  elettronica: 4,
  voce: 5,
  altro: 4,
};

const SEAT_W = 92;
const SEAT_H = 118;
const ICON_SIZE = 52;
const ROW_GAP = 140;
const STAGE_PADDING = 40;
const ENSEMBLE_ITEM_GAP = 16;
const ENSEMBLE_CELL_WIDTH = 168;
const ENSEMBLE_MAX_CONTENT_WIDTH = 4 * ENSEMBLE_CELL_WIDTH + 3 * ENSEMBLE_ITEM_GAP;

// ---------------------------------------------------------------------
// Layout "orchestra": ventaglio a fasce concentrice per famiglia, come
// nella disposizione orchestrale standard (podio al centro-fronte, archi
// davanti, poi legni, ottoni, percussioni; arpa/tastiere sul lato).
// ---------------------------------------------------------------------

const FAN = {
  originX: 720,
  originY: 720,
  angleMin: -84,
  angleMax: 84,
  // Il passo radiale di 120px separa icona e microlabel dalla fascia successiva.
  // Le fasce sono volutamente sottili: orientano senza diventare il contenuto.
  bandRadius: { archi: 180, legni: 300, ottoni: 420, percussioni: 540, voce: 650 },
  bandThickness: { archi: 30, legni: 28, ottoni: 28, percussioni: 30, voce: 28 },
  // spaziatura minima desiderata, in pixel, fra i centri di due icone adiacenti nella stessa fascia
  minSeatSpacingPx: 128,
  sideZoneX: 104,
  sideZoneYStart: 274,
  sideZoneStep: 116,
  width: 1440,
  height: 870,
};

const FAN_BAND_KEYS = ["archi", "legni", "ottoni", "percussioni", "voce"];

const FAN_BAND_LABEL = {
  archi: "Archi",
  legni: "Legni",
  ottoni: "Ottoni",
  percussioni: "Percussioni",
  voce: "Voci",
};

/** Ordine canonico all'interno di una fascia, sinistra -> destra (come una disposizione orchestrale reale). */
const SECTION_ORDER = {
  archi: ["violino-I", "violino-II", "viola", "violoncello", "contrabbasso"],
  legni: ["ottavino", "flauto", "oboe", "corno-inglese", "clarinetto", "clarinetto-basso", "fagotto", "sassofono", "fisarmonica"],
  ottoni: ["corno", "tromba", "trombone", "tuba"],
  percussioni: ["timpani", "xilofono", "vibrafono", "glockenspiel", "rullante", "grancassa", "piatti", "triangolo", "tamburello", "tam-tam", "elettronica", "sconosciuto"],
  voce: ["voce"],
};

/** Famiglie/icone che vanno nella zona laterale (arpa, pianoforte...) invece che nel ventaglio. */
function fanBandForPlacement(p) {
  // per un'alternativa, il primo mezzo del bundle CORRENTEMENTE mostrato determina la fascia
  // (persistito in p.currentIndex da buildPlacement/altState): un'alternativa fra famiglie
  // diverse (es. clarinetto/viola) si sposta quindi di fascia quando si alterna.
  const seat = p.kind === "alternative" ? p.options[p.currentIndex][0] : p.seat;
  if (
    seat.icon === "arpa" ||
    seat.family === "tastiere" ||
    seat.family === "pizzicati" ||
    seat.family === "elettronica" ||
    seat.family === "altro"
  ) return "side";
  if (seat.family === "archi") return "archi";
  if (seat.family === "legni") return "legni";
  if (seat.family === "ottoni") return "ottoni";
  if (seat.family === "voce") return "voce";
  return "percussioni";
}

function fanSectionKey(p) {
  const seat = p.kind === "alternative" ? p.options[p.currentIndex][0] : p.seat;
  if (seat.icon === "violino") {
    const sezione = (seat.sezione || "").toUpperCase();
    return sezione === "II" ? "violino-II" : "violino-I";
  }
  return seat.icon;
}

function fanSectionOrderIndex(p, bandKey) {
  const order = SECTION_ORDER[bandKey] || [];
  const idx = order.indexOf(fanSectionKey(p));
  return idx === -1 ? order.length : idx;
}

// Convenzione catalografica: nelle orchestre gli archi ad arco si scrivono per
// sezione (es. "Violini I", "Violoncelli"), mai con il conteggio dei singoli
// leggii ("16 violini" non si scrive mai) - a differenza di arpe/tastiere che
// invece si contano normalmente ("2 arpe"). Si applica solo in modalita'
// ventaglio (compact): fuori dall'orchestra non e' una convenzione valida.
const BOWED_STRING_PLURAL = {
  violino: "Violini",
  viola: "Viole",
  violoncello: "Violoncelli",
  contrabbasso: "Contrabbassi",
};

function bowedStringSectionLabel(seat) {
  // un archetto segnato "solo" e' un singolo suonatore distinto, non una sezione:
  // deve restare singolare con la stella, non diventare "Violini".
  if (seat.solo) return null;
  const base = BOWED_STRING_PLURAL[seat.icon];
  if (!base) return null;
  return seat.sezione ? `${base} ${seat.sezione}` : base;
}

// Stessa convenzione per le voci di coro: "S"/"A"/"T"/"B" (e varianti) in
// modalita' ventaglio diventano "Soprani"/"Contralti"/ecc., mai col conteggio
// dei singoli coristi - a meno che non sia un solista (sezione_parte_voce puo'
// comunque indicare il registro di un ruolo solistico, es. "Soprano" per un
// personaggio, e in quel caso resta singolare con l'etichetta cosi' com'e').
const CHOIR_SECTION_PLURAL = {
  S: "Soprani",
  MS: "Mezzosoprani",
  A: "Contralti",
  C: "Contralti",
  T: "Tenori",
  BAR: "Baritoni",
  B: "Bassi",
};

function choirSectionLabel(seat) {
  if (seat.icon !== "voce" || seat.solo || !seat.sezione) return null;
  return CHOIR_SECTION_PLURAL[seat.sezione.trim().toUpperCase()] || null;
}

/** Etichetta di sezione orchestrale (archi ad arco o coro), o null se non applicabile. */
function orchestralSectionLabel(seat) {
  return bowedStringSectionLabel(seat) || choirSectionLabel(seat);
}

const spriteLoadPromises = new Map();

/** Inietta lo sprite SVG (una sola volta per url) in <body> cosi' <use href="#icon-x"> funziona sempre, anche su browser con supporto limitato ai riferimenti SVG esterni. */
function ensureSprite(spriteUrl) {
  if (spriteLoadPromises.has(spriteUrl)) {
    return spriteLoadPromises.get(spriteUrl);
  }
  const promise = fetch(spriteUrl)
    .then((res) => {
      if (!res.ok) throw new Error(`Impossibile caricare lo sprite icone: ${spriteUrl}`);
      return res.text();
    })
    .then((svgText) => {
      const holder = document.createElement("div");
      holder.setAttribute("data-organico-sprite-holder", spriteUrl);
      holder.style.position = "absolute";
      holder.style.width = "0";
      holder.style.height = "0";
      holder.style.overflow = "hidden";
      holder.innerHTML = svgText;
      document.body.appendChild(holder);
    })
    .catch((err) => {
      console.error("[organico-stage] sprite non caricato, verranno mostrati riquadri vuoti come fallback", err);
    });
  spriteLoadPromises.set(spriteUrl, promise);
  return promise;
}

function mountOrganicoStage(container) {
  if (!container) return;
  const raw = container.getAttribute("data-organico");
  const spriteUrl = container.getAttribute("data-icons-sprite") || "assets/icons/sprite.svg";
  if (!raw) {
    console.warn("[organico-stage] nessun data-organico sul container", container);
    return;
  }
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (e) {
    console.error("[organico-stage] data-organico non e' JSON valido", e);
    return;
  }
  renderOrganicoStage(container, payload, spriteUrl);
}

// Pulsante schermo intero sull'header dello stage: usa la Fullscreen API nativa
// sul container stesso (l'SVG e' gia' width:100%/viewBox, quindi scala da solo).
// L'handler e' assegnato con .onfullscreenchange = invece di addEventListener
// perche' renderOrganicoStage() ricostruisce l'header a ogni rirender (es. al
// click su un'alternativa): un addEventListener si accumulerebbe a ogni giro,
// l'assegnazione diretta invece sostituisce sempre e sola quella corrente.
function makeFullscreenButton(container) {
  const requestFn = container.requestFullscreen || container.webkitRequestFullscreen;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "organico-stage__fullscreen-btn";
  if (!requestFn) btn.disabled = true;

  const isActive = () => (document.fullscreenElement || document.webkitFullscreenElement) === container;
  const update = () => {
    const active = isActive();
    btn.textContent = active ? "⤫" : "⛶";
    btn.setAttribute("aria-pressed", active ? "true" : "false");
    const label = active ? t("Exit fullscreen") : t("View fullscreen");
    btn.setAttribute("aria-label", label);
    btn.title = label;
  };
  btn.addEventListener("click", () => {
    if (isActive()) {
      const exitFn = document.exitFullscreen || document.webkitExitFullscreen;
      if (exitFn) exitFn.call(document);
      return;
    }
    if (requestFn) requestFn.call(container);
  });
  container.onfullscreenchange = update;
  container.onwebkitfullscreenchange = update;
  update();
  return btn;
}

function renderOrganicoStage(container, payload, spriteUrl) {
  container.classList.add("organico-stage");
  container.innerHTML = "";

  const units = payload.units || [];
  const ensembleType = payload.ensemble_type === "orchestra" ? "orchestra" : "ensemble";

  // stato delle alternative (quale opzione e' mostrata), tenuto sul container cosi' da
  // sopravvivere a un rirender completo: un'alternativa fra famiglie diverse (es. "cl/vla",
  // clarinetto=legni o viola=archi) deve spostarsi di fascia quando si alterna, e l'unico
  // modo corretto e' ricalcolare tutto il layout, non solo ridisegnare l'icona sul posto.
  container.__organicoAltState = container.__organicoAltState || new Map();
  const altState = container.__organicoAltState;
  const rerender = () => renderOrganicoStage(container, payload, spriteUrl);

  const placements = buildPlacements(units, altState);
  container.style.setProperty("--organico-placement-count", String(placements.length));

  if (payload.titolo || placements.length > 0) {
    const header = document.createElement("div");
    header.className = "organico-stage__header";
    const h = document.createElement("div");
    h.className = "organico-stage__title";
    h.textContent = payload.titolo || t("Instrumentation");
    header.appendChild(h);
    if (placements.length > 0) {
      const total = document.createElement("span");
      total.className = "organico-stage__total";
      total.textContent = String(totalPlacementCount(placements));
      total.setAttribute("aria-label", t("{n} instruments or sections", { n: total.textContent }));
      header.appendChild(total);
    }
    header.appendChild(makeFullscreenButton(container));
    container.appendChild(header);
  }

  if (placements.length === 0) {
    const empty = document.createElement("div");
    empty.className = "organico-stage__empty";
    empty.textContent = t("No instrumentation to display.");
    container.appendChild(empty);
    return;
  }

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "organico-stage__svg");

  const layout = ensembleType === "orchestra"
    ? layoutOrchestraFan(placements)
    : layoutEnsemble(placements);

  svg.setAttribute("viewBox", `0 0 ${layout.width} ${layout.height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", payload.organico_sintetico || payload.titolo || t("Work instrumentation"));

  if (ensembleType === "orchestra") {
    for (const arc of layout.bandArcs) {
      svg.appendChild(makeBandArc(layout.origin, arc, layout.angleMin, layout.angleMax));
    }
    svg.appendChild(makePodium(layout.origin));
  }

  for (const p of layout.placements) {
    svg.appendChild(renderPlacement(p, ensembleType === "orchestra", rerender, altState));
  }

  container.appendChild(svg);
  container.classList.toggle("organico-stage--orchestra", ensembleType === "orchestra");
  container.classList.toggle("organico-stage--ensemble", ensembleType !== "orchestra");

  if (ensembleType === "orchestra" && layout.legend.length > 0) {
    container.appendChild(buildLegend(layout.legend));
  }

  ensureSprite(spriteUrl);
}

function totalPlacementCount(placements) {
  const seatCount = (seat) => Math.max(1, Number(seat && seat.count) || 1);
  const placementCount = (placement) => {
    if (placement.kind === "cluster") {
      return placement.members.reduce((sum, member) => sum + placementCount(member), 0);
    }
    if (placement.kind === "alternative") {
      const bundle = placement.options[placement.currentIndex] || [];
      return bundle.reduce((sum, seat) => sum + seatCount(seat), 0);
    }
    return seatCount(placement.seat);
  };
  return placements.reduce((sum, placement) => sum + placementCount(placement), 0);
}

function buildLegend(bandKeys) {
  const legend = document.createElement("div");
  legend.className = "organico-stage__legend";
  for (const key of bandKeys) {
    const item = document.createElement("span");
    item.className = "organico-stage__legend-item";
    const swatch = document.createElement("i");
    swatch.className = `organico-stage__legend-swatch organico-stage__legend-swatch--${key}`;
    item.appendChild(swatch);
    item.appendChild(document.createTextNode(FAN_BAND_LABEL[key] || key));
    legend.appendChild(item);
  }
  return legend;
}

// ---------------------------------------------------------------------
// Costruzione dei "placement" (una voce sul palco: simple/alternative/cluster)
// ---------------------------------------------------------------------

function buildPlacements(units, altState) {
  const placements = [];
  for (const unit of units) {
    placements.push(buildPlacement(unit, altState));
  }
  return placements;
}

function buildPlacement(unit, altState) {
  if (unit.type === "cluster") {
    const members = unit.members.map((m) => buildPlacement(m, altState));
    const family = members[0] ? members[0].family : "altro";
    return {
      kind: "cluster",
      family,
      row: FAMILY_ROW[family] ?? 4,
      label: unit.label,
      members,
      widthUnits: Math.max(1, members.length),
    };
  }
  if (unit.type === "alternative") {
    // ogni opzione e' un "bundle" (uno o piu' mezzi mostrati insieme), non un singolo mezzo:
    // es. "flauto+ottavino" oppure "tromba+cornetta". L'opzione correntemente mostrata
    // (persistita in altState per sopravvivere al rirender) determina famiglia/fascia: cosi'
    // un'alternativa fra famiglie diverse (es. "clarinetto/viola") si sposta di fascia quando
    // si alterna, invece di restare fissa alla famiglia della prima opzione.
    const options = unit.options.map((bundle) => bundle.map((o) => buildSeatData(o)));
    const altKey = unit.primaryElemento;
    const currentIndex = (altState && altState.has(altKey)) ? altState.get(altKey) : 0;
    const activeFamily = options[currentIndex][0].family;
    return {
      kind: "alternative",
      family: activeFamily,
      row: FAMILY_ROW[activeFamily] ?? 4,
      options,
      currentIndex,
      altKey,
      widthUnits: Math.max(1, ...options.map((bundle) => bundle.length)),
    };
  }
  return {
    kind: "simple",
    family: unit.family,
    row: FAMILY_ROW[unit.family] ?? 4,
    seat: buildSeatData(unit),
    widthUnits: 1,
  };
}

function buildSeatData(unit) {
  return {
    icon: unit.icon,
    iconMatched: unit.iconMatched,
    family: unit.family,
    label: unit.label,
    count: unit.count || 1,
    numeroEsecutori: unit.numero_esecutori,
    solo: !!unit.solo,
    adLibitum: !!unit.ad_libitum,
    overdub: !!unit.overdub,
    elaborazioneDigitale: !!unit.elaborazione_digitale,
    suffisso: unit.suffisso,
    sezione: unit.sezione_parte_voce,
    uri: unit.uri,
    mopUri: unit.mop_uri,
    wikidataUri: unit.wikidata_uri,
  };
}

// ---------------------------------------------------------------------
// Layout: modalita' "orchestra" (ventaglio a fasce concentriche)
// ---------------------------------------------------------------------

/** I membri di un cluster diventano piazzamenti di primo livello nel ventaglio: la fascia/raggio li raggruppa gia' visivamente, il riquadro esplicito del cluster non serve piu'. */
function flattenForFan(placements) {
  const flat = [];
  for (const p of placements) {
    if (p.kind === "cluster") {
      for (const m of p.members) flat.push(m);
    } else {
      flat.push(p);
    }
  }
  return flat;
}

function layoutOrchestraFan(placements) {
  const flat = flattenForFan(placements);

  // La geometria conserva le proporzioni della disposizione orchestrale, ma
  // avvicina le fasce al podio quando l'organico e' piccolo. In questo modo lo
  // stage cresce con il contenuto invece di riservare sempre l'altezza di una
  // grande orchestra sinfonica.
  const densityScale = Math.min(1, Math.max(0.68, 0.62 + flat.length * 0.035));
  const scaledRadius = (key) => FAN.bandRadius[key] * densityScale;

  const bands = { archi: [], legni: [], ottoni: [], percussioni: [], voce: [], side: [] };
  for (const p of flat) {
    bands[fanBandForPlacement(p)].push(p);
  }
  for (const key of FAN_BAND_KEYS) {
    bands[key].sort((a, b) => fanSectionOrderIndex(a, key) - fanSectionOrderIndex(b, key));
  }

  const originX = FAN.originX;
  const activeOuterRadius = Math.max(
    0,
    ...FAN_BAND_KEYS.map((key) => (
      bands[key].length > 0 ? scaledRadius(key) : 0
    ))
  );
  const sideExtent = bands.side.length > 0
    ? FAN.sideZoneYStart + (bands.side.length - 1) * FAN.sideZoneStep + SEAT_H
    : 0;
  const originY = Math.max(
    430,
    activeOuterRadius + 112,
    sideExtent + 64
  );

  // le alternative multi-elemento (bundle) occupano piu' di 1 "unita' larghezza": la spaziatura
  // minima di una fascia deve tener conto del suo elemento piu' largo, altrimenti un bundle da
  // 2-3 icone potrebbe sconfinare sui vicini.
  const labelWidthForPlacement = (p) => {
    const seat = p.kind === "alternative" ? p.options[p.currentIndex][0] : p.seat;
    const sectionLabel = seat ? orchestralSectionLabel(seat) : null;
    const label = sectionLabel || (seat && seat.label) || "";
    return Math.min(156, Math.max(SEAT_W, String(label).length * 6.1 + 20));
  };
  const spacingPxForBand = (list) => {
    const maxWidthUnits = Math.max(1, ...list.map((p) => p.widthUnits || 1));
    const labelWidth = Math.max(SEAT_W, ...list.map(labelWidthForPlacement));
    return Math.max(FAN.minSeatSpacingPx, labelWidth + 12) + (maxWidthUnits - 1) * SEAT_W;
  };

  // l'apertura del ventaglio si adatta alla fascia piu' affollata: ogni fascia userebbe,
  // isolatamente, il proprio passo ideale (spaziatura minima in pixel al suo raggio); l'apertura
  // condivisa e' la piu' ampia fra queste necessita', entro un minimo e un massimo ragionevoli.
  let dynamicHalfAngle = 58;
  for (const key of FAN_BAND_KEYS) {
    const n = bands[key].length;
    if (n < 2) continue;
    const radius = scaledRadius(key);
    const idealStepDeg = (spacingPxForBand(bands[key]) / radius) * (180 / Math.PI);
    const neededHalfSpread = (idealStepDeg * (n - 1)) / 2;
    dynamicHalfAngle = Math.max(dynamicHalfAngle, neededHalfSpread);
  }
  dynamicHalfAngle = Math.min(dynamicHalfAngle, 88);
  const angleMin = -dynamicHalfAngle;
  const angleMax = dynamicHalfAngle;

  const positioned = [];

  for (const key of FAN_BAND_KEYS) {
    const list = bands[key];
    const n = list.length;
    if (n === 0) continue;
    const radius = scaledRadius(key);
    const idealStepDeg = (spacingPxForBand(list) / radius) * (180 / Math.PI);
    const idealHalfSpread = (idealStepDeg * (n - 1)) / 2;
    // se il passo ideale di questa fascia eccede l'apertura condivisa (caso limite: piu' fasce
    // molto affollate insieme), si stringe solo quel tanto che basta per restare nei limiti.
    const halfSpread = Math.min(idealHalfSpread, dynamicHalfAngle);
    const step = n > 1 ? (halfSpread * 2) / (n - 1) : 0;
    list.forEach((p, i) => {
      const angleDeg = step * (i - (n - 1) / 2);
      const angleRad = (angleDeg * Math.PI) / 180;
      const x = originX + radius * Math.sin(angleRad);
      const y = originY - radius * Math.cos(angleRad);
      positioned.push({ ...p, x, y, w: (p.widthUnits || 1) * SEAT_W, band: key });
    });
  }

  bands.side.forEach((p, i) => {
    const x = FAN.sideZoneX;
    const y = FAN.sideZoneYStart + i * FAN.sideZoneStep;
    positioned.push({ ...p, x, y, w: (p.widthUnits || 1) * SEAT_W, band: "side" });
  });

  const bandArcs = FAN_BAND_KEYS
    .filter((key) => key !== "voce" && bands[key].length > 0)
    .map((key) => ({
      key,
      r0: scaledRadius(key) - FAN.bandThickness[key] / 2,
      r1: scaledRadius(key) + FAN.bandThickness[key] / 2,
    }));
  if (bands.voce.length > 0) {
    bandArcs.push({
      key: "voce",
      r0: scaledRadius("voce") - FAN.bandThickness.voce / 2,
      r1: scaledRadius("voce") + FAN.bandThickness.voce / 2,
    });
  }

  const legend = FAN_BAND_KEYS.filter((key) => bands[key].length > 0);

  // la tela si allarga in orizzontale se l'apertura dinamica supera quella nominale (orchestre molto numerose)
  const outerRadius = activeOuterRadius;
  const rightEdge = originX + outerRadius * Math.sin((dynamicHalfAngle * Math.PI) / 180) + 120;
  const width = Math.max(FAN.width, rightEdge);
  const height = Math.max(500, originY + 118);

  return {
    width,
    height,
    placements: positioned,
    origin: { x: originX, y: originY },
    bandArcs,
    legend,
    angleMin,
    angleMax,
  };
}

// ---------------------------------------------------------------------
// Layout: modalita' "ensemble" (workspace uniforme, senza aggregazioni per famiglia)
// ---------------------------------------------------------------------

function layoutEnsemble(placements) {
  const placementWidth = (p) => {
    const contentWidth = Math.max(1, p.widthUnits || 1) * SEAT_W;
    if (p.kind !== "cluster") return Math.max(ENSEMBLE_CELL_WIDTH, contentWidth);

    // Un cluster e' un raggruppamento esplicito del catalogatore, non una
    // aggregazione automatica per famiglia. Mantiene quindi il proprio bordo,
    // ma occupa multipli della stessa cella usata dagli altri strumenti.
    const labelWidth = p.label ? Math.min(260, String(p.label).length * 6.4 + 28) : 0;
    return Math.max(ENSEMBLE_CELL_WIDTH, contentWidth + 20, labelWidth);
  };

  // Partiziona in righe sulla larghezza realmente renderizzata, non soltanto
  // sul numero di strumenti. Questo mantiene separati anche cluster con label
  // lunghe o alternative composte da piu' mezzi.
  const rows = [];
  let current = [];
  let currentWidth = 0;
  for (const p of placements) {
    const pWidth = placementWidth(p);
    const nextWidth = currentWidth + (current.length > 0 ? ENSEMBLE_ITEM_GAP : 0) + pWidth;
    if (nextWidth > ENSEMBLE_MAX_CONTENT_WIDTH && current.length > 0) {
      rows.push(current);
      current = [];
      currentWidth = 0;
    }
    current.push({ ...p, ensembleWidth: pWidth });
    currentWidth += (current.length > 1 ? ENSEMBLE_ITEM_GAP : 0) + pWidth;
  }
  if (current.length > 0) rows.push(current);

  const rowWidth = (row) => (
    row.reduce((sum, p) => sum + p.ensembleWidth, 0)
    + Math.max(0, row.length - 1) * ENSEMBLE_ITEM_GAP
  );
  // Una viewBox sufficientemente ampia impedisce alle tessere di ingrandirsi
  // quando il diagramma occupa una colonna larga: l'ensemble deve restare un
  // workspace compatto, non una sequenza di card dominanti.
  const width = Math.max(1120, ...rows.map((row) => rowWidth(row) + STAGE_PADDING * 2));

  const positioned = [];
  rows.forEach((rowPlacements, rowIndex) => {
    const totalWidthPx = rowWidth(rowPlacements);
    let cursor = width / 2 - totalWidthPx / 2;
    const y = STAGE_PADDING + 60 + rowIndex * ROW_GAP;
    for (const p of rowPlacements) {
      const wPx = p.ensembleWidth;
      const x = cursor + wPx / 2;
      cursor += wPx + ENSEMBLE_ITEM_GAP;
      positioned.push({ ...p, x, y, w: wPx });
    }
  });

  const height = rows.length * ROW_GAP + STAGE_PADDING * 2;
  return { width, height, placements: positioned };
}

// ---------------------------------------------------------------------
// Rendering SVG di un placement
// ---------------------------------------------------------------------

function renderPlacement(p, compact = false, rerender = null, altState = null) {
  const g = document.createElementNS(SVG_NS, "g");
  g.setAttribute("class", `organico-placement organico-placement--${p.kind} organico-placement--family-${p.family || "altro"}`);
  g.setAttribute("transform", `translate(${p.x - p.w / 2}, ${p.y - SEAT_H / 2})`);

  if (!compact && p.kind !== "cluster") {
    const tile = document.createElementNS(SVG_NS, "rect");
    tile.setAttribute("x", "4");
    tile.setAttribute("y", "2");
    tile.setAttribute("width", String(p.w - 8));
    tile.setAttribute("height", String(SEAT_H - 8));
    tile.setAttribute("rx", "8");
    tile.setAttribute("class", "organico-ensemble-tile");
    g.appendChild(tile);
  }

  if (p.kind === "cluster") {
    g.appendChild(renderClusterBox(p));
    const memberWidths = p.members.map((member) => Math.max(1, member.widthUnits || 1) * SEAT_W);
    const membersWidth = memberWidths.reduce((sum, width) => sum + width, 0);
    let memberCursor = (p.w - membersWidth) / 2;
    p.members.forEach((m, i) => {
      const memberWidth = memberWidths[i];
      g.appendChild(renderMember(
        { ...m, w: memberWidth },
        memberCursor,
        20,
        compact,
        rerender,
        altState
      ));
      memberCursor += memberWidth;
    });
    return g;
  }

  if (p.kind === "alternative") {
    g.appendChild(renderAlternativeSeat(p, 0, 0, compact, rerender, altState));
    return g;
  }

  g.appendChild(renderSeatGroup(p.seat, (p.w - SEAT_W) / 2, 0, false, compact));
  return g;
}

/** Rende un membro di un cluster (puo' essere un semplice mezzo o un'alternativa). */
function renderMember(m, offsetX, offsetY, compact = false, rerender = null, altState = null) {
  if (m.kind === "alternative") {
    return renderAlternativeSeat(m, offsetX, offsetY, compact, rerender, altState);
  }
  return renderSeatGroup(m.seat, offsetX, offsetY, false, compact);
}

function renderClusterBox(p) {
  const box = document.createElementNS(SVG_NS, "g");
  const rect = document.createElementNS(SVG_NS, "rect");
  rect.setAttribute("x", "4");
  rect.setAttribute("y", "10");
  rect.setAttribute("width", String(p.w - 8));
  rect.setAttribute("height", String(SEAT_H - 12));
  rect.setAttribute("rx", "12");
  rect.setAttribute("class", "organico-cluster-box");
  box.appendChild(rect);

  const label = document.createElementNS(SVG_NS, "text");
  label.setAttribute("x", String(p.w / 2));
  label.setAttribute("y", "6");
  label.setAttribute("class", "organico-cluster-label");
  label.setAttribute("text-anchor", "middle");
  label.textContent = p.label;
  box.appendChild(label);

  const title = document.createElementNS(SVG_NS, "title");
  title.textContent = p.label;
  label.appendChild(title);

  return box;
}

/** Disegna il bundle (uno o piu' mezzi) dell'opzione correntemente mostrata, affiancati. */
function renderBundleGroup(bundle, compact) {
  const g = document.createElementNS(SVG_NS, "g");
  bundle.forEach((seat, i) => {
    g.appendChild(renderSeatGroup(seat, i * SEAT_W, 0, true, compact));
  });
  return g;
}

function renderAlternativeSeat(p, offsetX = 0, offsetY = 0, compact = false, rerender = null, altState = null) {
  const wrap = document.createElementNS(SVG_NS, "g");
  wrap.setAttribute("class", "organico-alternative");
  wrap.setAttribute("transform", `translate(${offsetX}, ${offsetY})`);

  const slotWidth = p.w || SEAT_W;
  const seatHolder = document.createElementNS(SVG_NS, "g");
  wrap.appendChild(seatHolder);

  const toggle = document.createElementNS(SVG_NS, "g");
  toggle.setAttribute("class", "organico-alt-toggle");
  toggle.style.cursor = "pointer";
  const circle = document.createElementNS(SVG_NS, "circle");
  circle.setAttribute("r", "12");
  circle.setAttribute("class", "organico-alt-toggle__bg");
  const sym = document.createElementNS(SVG_NS, "text");
  sym.setAttribute("text-anchor", "middle");
  sym.setAttribute("y", "4");
  sym.setAttribute("class", "organico-alt-toggle__icon");
  sym.textContent = "⇄";
  toggle.appendChild(circle);
  toggle.appendChild(sym);

  const titleEl = document.createElementNS(SVG_NS, "title");
  titleEl.textContent = t("or: ") + p.options.map((bundle) => bundle.map((s) => s.label).join(" + ")).join(" / ");
  toggle.appendChild(titleEl);

  // il bundle corrente puo' essere piu' stretto dello slot riservato (larghezza = bundle piu'
  // largo fra le opzioni): si centra e il pulsante ⇄ segue il bordo destro del bundle mostrato.
  const layoutCurrent = () => {
    const bundle = p.options[p.currentIndex];
    const bundleWidth = bundle.length * SEAT_W;
    const startX = (slotWidth - bundleWidth) / 2;
    while (seatHolder.firstChild) seatHolder.removeChild(seatHolder.firstChild);
    seatHolder.setAttribute("transform", `translate(${startX}, 0)`);
    seatHolder.appendChild(renderBundleGroup(bundle, compact));
    toggle.setAttribute("transform", `translate(${startX + bundleWidth - 18}, 4)`);
  };
  layoutCurrent();

  toggle.addEventListener("click", () => {
    const nextIndex = (p.currentIndex + 1) % p.options.length;
    // se opzioni diverse appartengono a famiglie diverse (es. clarinetto/viola), la nuova
    // scelta puo' richiedere una fascia/posizione diversa: non basta ridisegnare il bundle
    // sul posto, serve un rirender completo dello stage. Lo stato si salva prima di rirenderare
    // cosi' la nuova chiamata a renderOrganicoStage lo ritrova invece di ripartire da 0.
    if (altState && p.altKey !== undefined && rerender) {
      altState.set(p.altKey, nextIndex);
      rerender();
      return;
    }
    p.currentIndex = nextIndex;
    layoutCurrent();
  });

  wrap.appendChild(toggle);
  return wrap;
}

function renderSeatGroup(seat, offsetX, offsetY, isAlternativeOption = false, compact = false) {
  // Preferiamo il link a Wikidata (interoperabile, con una pagina vera): l'URI
  // IFLA (namespace iflastandards.info) resta come fallback per i termini che
  // non hanno ancora una corrispondenza Wikidata via P11214, ma di fatto oggi
  // quel dominio risponde "Server Error" su ogni URI provata — meglio comunque
  // lasciarlo come ultima risorsa piuttosto che non avere alcun link.
  const linkTarget = seat.wikidataUri || seat.mopUri || seat.uri || "";
  const g = document.createElementNS(SVG_NS, linkTarget ? "a" : "g");
  g.setAttribute("class", "organico-seat");
  g.setAttribute("transform", `translate(${offsetX}, ${offsetY})`);
  if (linkTarget) {
    g.setAttribute("href", linkTarget);
    g.setAttributeNS("http://www.w3.org/1999/xlink", "href", linkTarget);
    g.setAttribute("target", "_blank");
    g.setAttribute("rel", "noopener noreferrer");
    g.setAttribute("class", "organico-seat organico-seat--linked");
    g.setAttribute(
      "aria-label",
      seat.wikidataUri
        ? t("{label}: open the Wikidata page", { label: seat.label })
        : seat.mopUri
        ? t("{label}: open the term in the IFLA vocabulary", { label: seat.label })
        : t("{label}: open the linked term", { label: seat.label })
    );
  }

  const title = document.createElementNS(SVG_NS, "title");
  title.textContent = buildTooltip(seat);
  g.appendChild(title);

  const cx = SEAT_W / 2;
  const iconTop = 8;

  if (seat.solo) {
    const ring = document.createElementNS(SVG_NS, "circle");
    ring.setAttribute("cx", String(cx));
    ring.setAttribute("cy", String(iconTop + ICON_SIZE / 2));
    ring.setAttribute("r", String(ICON_SIZE / 2 + 8));
    ring.setAttribute("class", "organico-seat__solo-ring");
    g.appendChild(ring);
  }

  if (seat.overdub) {
    g.appendChild(makeIconUse(seat.icon, cx - 5 + 4, iconTop + 4, "organico-seat__ghost"));
  }

  const wrapAttrs = seat.adLibitum ? " organico-seat__icon--adlib" : "";
  const iconEl = makeIconUse(seat.icon, cx, iconTop, "organico-seat__icon" + wrapAttrs);
  g.appendChild(iconEl);

  if (!seat.iconMatched) {
    const fbMark = document.createElementNS(SVG_NS, "text");
    fbMark.setAttribute("x", String(cx + ICON_SIZE / 2 - 4));
    fbMark.setAttribute("y", String(iconTop + 12));
    fbMark.setAttribute("class", "organico-seat__fallback-mark");
    fbMark.textContent = "*";
    g.appendChild(fbMark);
  }

  if (seat.solo) {
    g.appendChild(makeBadge(cx + ICON_SIZE / 2 - 2, iconTop - 4, "★", "organico-badge organico-badge--solo"));
  }

  const sectionLabel = compact ? orchestralSectionLabel(seat) : null;

  if (seat.count >= 2 && !sectionLabel) {
    g.appendChild(makeBadge(cx - ICON_SIZE / 2 + 4, iconTop - 4, "×" + seat.count, "organico-badge organico-badge--count", true));
  }

  const lines = [];
  const fullMainLine = sectionLabel || (seat.sezione ? `${seat.sezione} · ${seat.label}` : seat.label);
  const mainLine = compact ? compactLabel(fullMainLine, 19) : fullMainLine;
  lines.push(mainLine);
  // in modalita' compatta (ventaglio orchestrale) i dettagli suffisso/ad libitum/digitale
  // restano solo nel tooltip, per non far collidere le etichette fra fasce vicine.
  if (!compact) {
    const subParts = [];
    if (seat.suffisso) subParts.push(seat.suffisso);
    if (seat.adLibitum) subParts.push("ad lib.");
    if (subParts.length) lines.push(subParts.join(", "));
  }

  const textY = iconTop + ICON_SIZE + 16;
  lines.forEach((line, i) => {
    const t = document.createElementNS(SVG_NS, "text");
    t.setAttribute("x", String(cx));
    t.setAttribute("y", String(textY + i * 13));
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("class", i === 0 ? "organico-seat__label" : "organico-seat__sublabel");
    t.textContent = line;
    g.appendChild(t);
  });

  if (seat.elaborazioneDigitale && !compact) {
    const chip = document.createElementNS(SVG_NS, "text");
    chip.setAttribute("x", String(cx));
    chip.setAttribute("y", String(textY + lines.length * 13 + 2));
    chip.setAttribute("text-anchor", "middle");
    chip.setAttribute("class", "organico-chip organico-chip--digitale");
    chip.textContent = t("digital");
    g.appendChild(chip);
  }

  return g;
}

function compactLabel(value, maxLength) {
  const text = String(value || "").trim();
  if (text.length <= maxLength) return text;
  return text.slice(0, Math.max(1, maxLength - 1)).trimEnd() + "…";
}

function makeIconUse(iconKey, cx, top, className) {
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", "#icon-" + iconKey);
  use.setAttributeNS("http://www.w3.org/1999/xlink", "href", "#icon-" + iconKey);
  use.setAttribute("x", String(cx - ICON_SIZE / 2));
  use.setAttribute("y", String(top));
  use.setAttribute("width", String(ICON_SIZE));
  use.setAttribute("height", String(ICON_SIZE));
  use.setAttribute("class", className);
  return use;
}

function makeBadge(x, y, text, className, isCount = false) {
  const g = document.createElementNS(SVG_NS, "g");
  g.setAttribute("transform", `translate(${x}, ${y})`);
  g.setAttribute("class", className);
  if (isCount) {
    const rect = document.createElementNS(SVG_NS, "rect");
    rect.setAttribute("x", "-14");
    rect.setAttribute("y", "-8");
    rect.setAttribute("width", "28");
    rect.setAttribute("height", "16");
    rect.setAttribute("rx", "8");
    g.appendChild(rect);
    const t = document.createElementNS(SVG_NS, "text");
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("y", "4");
    t.textContent = text;
    g.appendChild(t);
  } else {
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("r", "8");
    g.appendChild(circle);
    const t = document.createElementNS(SVG_NS, "text");
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("y", "3.5");
    t.textContent = text;
    g.appendChild(t);
  }
  return g;
}

function buildTooltip(seat) {
  const parts = [seat.label];
  if (seat.sezione) parts.push(t("section/part: {value}", { value: seat.sezione }));
  if (seat.count >= 2) parts.push(t("{n} items", { n: seat.count }));
  if (seat.numeroEsecutori && seat.numeroEsecutori !== seat.count) {
    parts.push(t("{n} performers", { n: seat.numeroEsecutori }));
  }
  if (seat.suffisso) parts.push(seat.suffisso);
  if (seat.solo) parts.push(t("solo"));
  if (seat.adLibitum) parts.push(t("ad libitum"));
  if (seat.overdub) parts.push(t("overdub"));
  if (seat.elaborazioneDigitale) parts.push(t("digital processing"));
  if (!seat.iconMatched) parts.push(t("(generic family icon)"));
  if (seat.wikidataUri) parts.push(t("Wikidata: {uri}", { uri: seat.wikidataUri }));
  else if (seat.mopUri) parts.push(t("MOP: {uri}", { uri: seat.mopUri }));
  if (seat.uri) parts.push(seat.uri);
  return parts.join(" — ");
}

function makePodium(origin) {
  const g = document.createElementNS(SVG_NS, "g");
  g.setAttribute("class", "organico-podium");
  const rect = document.createElementNS(SVG_NS, "rect");
  rect.setAttribute("x", String(origin.x - 16));
  rect.setAttribute("y", String(origin.y - 6));
  rect.setAttribute("width", "32");
  rect.setAttribute("height", "12");
  rect.setAttribute("rx", "2");
  g.appendChild(rect);
  const titleEl = document.createElementNS(SVG_NS, "title");
  titleEl.textContent = t("conductor's podium");
  g.appendChild(titleEl);
  return g;
}

/** Converte coordinate polari (origine, raggio, angolo in gradi da 0=davanti) in punto cartesiano. */
function polarPoint(origin, radius, angleDeg) {
  const rad = (angleDeg * Math.PI) / 180;
  return [origin.x + radius * Math.sin(rad), origin.y - radius * Math.cos(rad)];
}

/** Path di un settore d'anello (fascia colorata di una famiglia) fra due raggi e l'ampiezza angolare del ventaglio. */
function makeBandArc(origin, arc, angleMin, angleMax) {
  const a0 = angleMin;
  const a1 = angleMax;
  const [x1, y1] = polarPoint(origin, arc.r1, a0);
  const [x2, y2] = polarPoint(origin, arc.r1, a1);
  const [x3, y3] = polarPoint(origin, arc.r0, a1);
  const [x4, y4] = polarPoint(origin, arc.r0, a0);
  const largeArc = a1 - a0 > 180 ? 1 : 0;
  const d = [
    `M ${x1} ${y1}`,
    `A ${arc.r1} ${arc.r1} 0 ${largeArc} 1 ${x2} ${y2}`,
    `L ${x3} ${y3}`,
    `A ${arc.r0} ${arc.r0} 0 ${largeArc} 0 ${x4} ${y4}`,
    "Z",
  ].join(" ");

  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", d);
  path.setAttribute("class", `organico-band organico-band--${arc.key}`);
  return path;
}


window.caUI = window.caUI || {};
window.caUI.Organico = window.caUI.Organico || {};
window.caUI.Organico.ensureSprite = ensureSprite;
window.caUI.Organico.mountStage = mountOrganicoStage;
window.caUI.Organico.renderStage = renderOrganicoStage;
