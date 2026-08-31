/**
 * Copia adattata per CollectiveAccess di organico-viewer/assets/js/organico-sbn-parser.js
 * (stessa logica, nessuna modifica funzionale) — modulo ES sostituito da
 * namespace globale window.caUI.Organico, stesso motivo di organico-stage.js
 * (vedi il commento in quel file). Rigenerare copiando da li' se il parser
 * cambia; il dizionario usato (sbn-marc-dictionary.json) va rigenerato con
 * organico-viewer/build/build-sbn-marc-dictionary.php e ricopiato qui.
 */
/**
 * Parser per la notazione compatta "Organico analitico (SBN MARC)" (norme
 * ICCU/SBN Musica, U9B.3 - M8B3), usato dal pulsante "Importa da testo" per
 * pre-compilare l'editor a partire da un campo gia' catalogato, senza dover
 * re-inserire manualmente ogni strumento.
 *
 * Sintassi (vedi norme.iccu.sbn.it, pagina Organico, e la tabella
 * abbreviazioni di urfm.braidense.it/risorse/strument_2005.php):
 *   ","   separa elementi/gruppi allo stesso livello, es. "2fl,ob"
 *   "/"   alternativa fra elementi, es. "cl/vla" (clarinetto O viola)
 *   "/$"  separa organici interi alternativi (es. due versioni dello
 *         stesso pezzo); si importa solo il PRIMO segmento, il resto viene
 *         segnalato in `warnings` e mai scartato in silenzio.
 *   "()"  raggruppamento con nome (es. "Coro(S,A,T,B)",
 *         "2perc(tom,tambmil,timp)" — il numero prima del nome e' il
 *         numero di ESECUTORI del gruppo, non e' assegnabile a un singolo
 *         strumento del gruppo quindi resta solo come avviso).
 *   "-x"  suffisso: se il termine base + suffisso e' gia' precomposto nel
 *         dizionario (es. "fl-b" = "flauto basso") si usa quello; altrimenti
 *         si combina base+suffisso a runtime, distinguendo tre casi (vedi
 *         `resolveToken`): "-solo" -> flag `solo`; suffissi di tecnica
 *         esecutiva (preparato, amplificato, a 4 mani, ...) -> campo
 *         `suffisso`; suffissi di registro (soprano, basso, contralto, ...)
 *         -> concatenati all'etichetta, come le voci gia' precomposte.
 *   "%"   prefisso "ad libitum".
 *   "N"   prefisso numerico = numero di elementi (es. "2fl" = 2 flauti).
 *
 * Ogni token non presente nel dizionario NON viene scartato: resta come
 * etichetta libera con `found:false`, cosi' il catalogatore lo vede e lo
 * corregge nell'editor invece di perdere silenziosamente un dato.
 *
 * Uso:
 *   import { parseSbnMarc } from "./organico-sbn-parser.js";
 *   const { items, warnings } = parseSbnMarc(testo, dizionario);
 *   // dizionario: contenuto di src/data/sbn-marc-dictionary.json
 */

/** Divide `str` su `sep` solo al livello 0 di annidamento delle parentesi tonde. */
function splitTopLevel(str, sep) {
  const parts = [];
  let depth = 0;
  let current = "";
  for (let i = 0; i < str.length; i++) {
    const ch = str[i];
    if (ch === "(") depth++;
    else if (ch === ")") depth--;
    if (depth <= 0 && str.startsWith(sep, i)) {
      parts.push(current);
      current = "";
      i += sep.length - 1;
      continue;
    }
    current += ch;
  }
  parts.push(current);
  return parts;
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

/**
 * Risolve un singolo token (senza prefissi %/numero, gia' rimossi) in
 * {label, icon, family, found, solo?, suffisso?}. Prova prima il token
 * intero, poi — se contiene un trattino — la combinazione base+suffisso.
 * Non ricorre mai al matching per alias in linguaggio naturale (quello di
 * IconDictionary): le sigle SBN sono troppo corte e genererebbero falsi
 * positivi, quindi qui SOLO il dizionario ufficiale e' fonte di verita'.
 */
/**
 * Toglie un indice di leggio/desk finale (cifre arabe o numerale romano
 * I/II/III/IV, con o senza trattino davanti), es. "vl1"/"vlI" -> "vl",
 * "cl-b1" -> "cl-b". Stessa regola di stripDeskIndex() nel plugin Titolo
 * Uniforme (PHP) — qui serve perche' l'indice di leggio non identifica uno
 * strumento diverso, e senza toglierlo il token non trova mai una voce nel
 * dizionario (nessuno registra "vl1", "vl2", "vl3", ... uno per uno).
 */
function stripDeskIndex(token) {
  return String(token || "")
    .replace(/-?(?:[1-9][0-9]*|I{1,3}|IV)$/, "")
    .replace(/-+$/, "");
}

/**
 * Alcune chiavi del dizionario SBN hanno una capitalizzazione specifica per
 * distinguere sigle diverse (es. "S" voce vs "s" suffisso soprano, "mS"
 * mezzosoprano, "Coro"), ma un catalogatore puo' aver scritto "MS" o "COOR"
 * — la stessa tolleranza gia' applicata nella riconciliazione MOP lato
 * editor (canonicalMopTerm) va applicata anche qui, altrimenti il parser
 * segnala "non riconosciuto" pur avendo gia' la voce giusta a disposizione.
 * Prova prima la chiave esatta (piu' veloce, ed e' quella che decide quando
 * due sigle differiscono solo per maiuscole/minuscole), poi un fallback
 * case-insensitive.
 */
function dictionaryLookup(dictionary, key) {
  if (!key) return undefined;
  if (Object.prototype.hasOwnProperty.call(dictionary, key)) return dictionary[key];
  const lower = key.toLowerCase();
  const caseInsensitiveKey = Object.keys(dictionary).find((k) => k.toLowerCase() === lower);
  return caseInsensitiveKey ? dictionary[caseInsensitiveKey] : undefined;
}

function resolveToken(token, dictionary) {
  if (!token) return { label: "", icon: "sconosciuto", family: "altro", found: false };

  const direct = dictionaryLookup(dictionary, token);
  if (direct && (direct.category === "strumento" || direct.category === "organico_sintetico")) {
    return { label: direct.label, icon: direct.icon, family: direct.family, found: true };
  }

  const lastHyphen = token.lastIndexOf("-");
  if (lastHyphen > 0) {
    const base = token.slice(0, lastHyphen);
    const suffixCode = "-" + token.slice(lastHyphen + 1);
    const baseEntry = dictionaryLookup(dictionary, base);
    const suffixEntry = dictionaryLookup(dictionary, suffixCode);
    if (
      baseEntry && (baseEntry.category === "strumento" || baseEntry.category === "organico_sintetico") &&
      suffixEntry && suffixEntry.category === "suffisso"
    ) {
      if (suffixEntry.role === "solo") {
        return { label: baseEntry.label, icon: baseEntry.icon, family: baseEntry.family, found: true, solo: true };
      }
      if (suffixEntry.role === "technique") {
        return { label: baseEntry.label, icon: baseEntry.icon, family: baseEntry.family, found: true, suffisso: capitalize(suffixEntry.label) };
      }
      return { label: `${baseEntry.label} ${suffixEntry.label}`, icon: baseEntry.icon, family: baseEntry.family, found: true };
    }
  }

  const deskStripped = stripDeskIndex(token);
  if (deskStripped && deskStripped !== token) {
    const strippedResolved = resolveToken(deskStripped, dictionary);
    if (strippedResolved.found) return strippedResolved;
  }

  return { label: token, icon: "sconosciuto", family: "altro", found: false };
}

function parseSbnMarc(text, dictionary) {
  const warnings = [];
  const items = [];
  let nextAltGroup = 1;

  const raw = String(text || "").trim();
  if (!raw) return { items, warnings };

  const wholeSegments = splitTopLevel(raw, "/$");
  if (wholeSegments.length > 1) {
    const dropped = wholeSegments.length - 1;
    warnings.push(
      `Il testo contiene ${wholeSegments.length} organici alternativi separati da "/$": importato solo il primo, ` +
      `${dropped === 1 ? "l'altro non e' stato importato" : "gli altri " + dropped + " non sono stati importati"} ` +
      `(se servono, ripeti l'importazione incollando solo quel segmento).`
    );
  }
  const segment = wholeSegments[0].trim();
  if (!segment) return { items, warnings };

  function parseSimple(token, groupLabel, altGroupId, altOptionId) {
    let t = token.trim();
    if (!t) return;

    let adLibitum = false;
    if (t.startsWith("%")) {
      adLibitum = true;
      t = t.slice(1).trim();
    }

    let numeroElementi = 1;
    const numMatch = t.match(/^(\d+)(.*)$/);
    if (numMatch && numMatch[2]) {
      numeroElementi = parseInt(numMatch[1], 10);
      t = numMatch[2];
    }

    const resolved = resolveToken(t, dictionary);
    if (!resolved.found) {
      warnings.push(`Termine "${token}" non riconosciuto nel dizionario SBN: aggiunto come etichetta libera "${t}", da correggere manualmente.`);
    }

    items.push({
      label: resolved.label,
      key: null,
      icon: resolved.icon,
      family: resolved.family,
      mopUri: null,
      numero_elementi: numeroElementi,
      solo: resolved.solo || false,
      ad_libitum: adLibitum,
      suffisso: resolved.suffisso || "",
      gruppo_ensemble: groupLabel ? { label: groupLabel, numero_gruppo: null } : null,
      alternativa_gruppo: altGroupId,
      alternativa_opzione: altOptionId,
      found: resolved.found,
      raw: token,
    });
  }

  function parseEntry(entry, groupLabel) {
    const t = entry.trim();
    if (!t) return;

    const groupMatch = t.match(/^(\d*)([A-Za-z][\w'-]*)\((.+)\)$/);
    if (groupMatch) {
      const [, execCountStr, nameToken, inner] = groupMatch;
      const resolvedName = resolveToken(nameToken, dictionary);
      const label = capitalize(resolvedName.label || nameToken);
      if (!resolvedName.found) {
        warnings.push(`Nome gruppo "${nameToken}" non riconosciuto nel dizionario SBN: usato come etichetta libera "${label}".`);
      }
      if (execCountStr) {
        warnings.push(
          `Gruppo "${label}": ${execCountStr} esecutori dichiarati nel testo originale, non assegnabili automaticamente ai singoli strumenti del gruppo — ` +
          `verifica se suddividere il gruppo in sotto-gruppi (Numero gruppo) per rappresentarli con precisione.`
        );
      }
      const innerEntries = splitTopLevel(inner, ",").map((s) => s.trim()).filter(Boolean);
      for (const innerEntry of innerEntries) {
        parseEntry(innerEntry, label);
      }
      return;
    }

    const altOptions = splitTopLevel(t, "/").map((s) => s.trim()).filter(Boolean);
    if (altOptions.length > 1) {
      const groupId = nextAltGroup++;
      altOptions.forEach((opt, idx) => parseSimple(opt, groupLabel, groupId, idx + 1));
      return;
    }

    parseSimple(t, groupLabel, null, null);
  }

  const topEntries = splitTopLevel(segment, ",").map((s) => s.trim()).filter(Boolean);
  for (const entry of topEntries) {
    parseEntry(entry, null);
  }

  return { items, warnings };
}

window.caUI = window.caUI || {};
window.caUI.Organico = window.caUI.Organico || {};
window.caUI.Organico.parseSbnMarc = parseSbnMarc;
