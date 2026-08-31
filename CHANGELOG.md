# Changelog

## 0.1.15-draft - 2026-08-31

- Added the production-derived Providence runtime package for the Organico
  datatype/editor, including its asset-loader configuration, Italian source
  catalogue, vocabularies, renderer assets, and fullscreen stage support.
- Added the authoritative production `prepopulatePHP` plugin together with its
  required dictionaries; runtime logs and backups remain excluded.
- Added exact source hashes and automated PHP, JavaScript, JSON, SVG, gettext,
  and integrity validation for the runtime package.

---

## 0.1.15-draft - 2026-08-31

- Aggiunto il pacchetto runtime Providence derivato dalla produzione per il
  datatype/editor Organico, includendo configurazione degli asset, catalogo
  sorgente italiano, vocabolari, risorse del renderer e supporto fullscreen.
- Aggiunto il plugin `prepopulatePHP` autorevole in produzione insieme ai
  dizionari richiesti; log e backup runtime restano esclusi.
- Aggiunti hash esatti della fonte e validazione automatica di PHP, JavaScript,
  JSON, SVG, gettext e integrità del pacchetto runtime.

---

## 0.1.14-draft - 2026-08-28

- Replaced the five closed LoC/MARC video Linked Data fields (`broadcaststandard_ME`, `videoplayback_ME`, `polarity_ME`, `aspectration_ME`, and `tecnique_ME`) with local bilingual controlled lists.
- Added exactly 24 terms from the official LoC vocabularies, preserving authoritative codes and URIs and documenting the ACUSTEME Italian translations.
- Added reproducible LoC generation, live-source comparison, and offline count/wiring validation. Generic Wikidata searches remain Linked Data.
- Normalized the seven generic electronic-resource Wikidata searches to return one preferred label per entity. This prevents alias multiplication from breaking `InformationService` URL/QID resolution during record saving while leaving the searches open-domain.
- Changed `mediaurl_ME` from `ExternalMedia` to `Url` as a compatibility workaround for the broken `ExternalMedia` save path in Providence 2.0.11. Online-media links remain editable and searchable; embedded previews can be restored after applying the upstream backend fix.
- Replaced every cross-locale IFLA lexical fallback with an explicit semantic English/Italian pair. The 1,057 IFLA entries now have mandatory bilingual labels sourced from IFLA, Wikidata, or the reviewed ACUSTEME supplement; generation fails if either language is missing.
- Kept the list null option text unchanged as `Not set` in both interface locales.

---

## 0.1.14-draft - 2026-08-28

- Sostituiti i cinque campi Linked Data video basati su vocabolari chiusi LoC/MARC (`broadcaststandard_ME`, `videoplayback_ME`, `polarity_ME`, `aspectration_ME` e `tecnique_ME`) con liste controllate locali bilingui.
- Aggiunti esattamente 24 termini dai vocabolari ufficiali LoC, preservando codici e URI autorevoli e documentando le traduzioni italiane ACUSTEME.
- Aggiunti generazione riproducibile, confronto con la fonte LoC live e validazione offline di conteggi e collegamenti. Le ricerche Wikidata generiche restano Linked Data.
- Normalizzate le sette ricerche Wikidata generiche delle risorse elettroniche affinché restituiscano una sola etichetta preferita per entità. La modifica evita che la moltiplicazione dovuta agli alias impedisca la risoluzione di URL/QID durante il salvataggio, mantenendo aperto il dominio delle ricerche.
- Modificato `mediaurl_ME` da `ExternalMedia` a `Url` come soluzione di compatibilità per il salvataggio `ExternalMedia` difettoso in Providence 2.0.11. I collegamenti ai media online restano modificabili e ricercabili; l'anteprima incorporata potrà essere ripristinata dopo l'applicazione della correzione upstream al backend.
- Sostituito ogni fallback lessicale IFLA tra lingue con una coppia semantica esplicita inglese/italiano. Tutte le 1.057 voci IFLA hanno ora etichette bilingui obbligatorie provenienti da IFLA, Wikidata o dal repertorio ACUSTEME revisionato; la generazione fallisce se manca una delle due lingue.
- Mantenuto invariato il testo dell'opzione nulla `Not set` in entrambe le lingue dell'interfaccia.

---

## 0.1.13-draft - 2026-08-28

- Added a dedicated `Contained resources` bundle to the Record set relationships screen. It displays R220 (`set_includes_isIncludedIn`) links to archival records, archival parts, musical instruments, and bibliographic resources, using a paginated list suitable for large sets.
- Kept the canonical and generated English profile variants synchronized and XSD-valid.
- Replaced the 36 closed IFLA UNIMARC Linked Data fields in `Dati specifici` with local controlled lists, preserving the existing metadata-element codes and placements for a later data migration.
- Added 36 bilingual IFLA lists containing exactly 1,056 published terms; the single deprecated `visfor` term is retained but disabled. Official IFLA labels take precedence, followed by unambiguous Wikidata labels and a documented IFLA lexical fallback when a translation is unavailable.
- Pinned generation to IFLA UNIMARC revision `65fb8630298498bf03c4ce567dfd1746fcf6c0a9`, added reproducible generation/audit tooling, and enabled a searchable browser for the 607-term musical-form list.
- Left every non-IFLA SPARQL field unchanged and added the IFLA count/wiring audit to profile validation.

---

## 0.1.13-draft - 2026-08-28

- Aggiunto il bundle dedicato `Risorse contenute` alla schermata relazioni dei Record set. Visualizza i collegamenti R220 (`set_includes_isIncludedIn`) a materiali d'archivio record, materiali d'archivio part, strumenti musicali e risorse bibliografiche, mediante una lista paginata adatta ai set numerosi.
- Mantenute sincronizzate e valide rispetto all'XSD le varianti canonica e inglese del profilo.
- Sostituiti i 36 campi Linked Data IFLA UNIMARC chiusi dei `Dati specifici` con liste controllate locali, mantenendo invariati i codici e i placement dei metadata element in vista della successiva migrazione dei dati.
- Aggiunte 36 liste bilingui IFLA contenenti esattamente 1.056 termini pubblicati; l'unico termine `visfor` deprecato è conservato ma disabilitato. Hanno priorità le etichette ufficiali IFLA, seguite dalle etichette Wikidata non ambigue e, quando manca una traduzione, da un fallback lessicale IFLA documentato.
- Fissata la generazione alla revisione IFLA UNIMARC `65fb8630298498bf03c4ce567dfd1746fcf6c0a9`, aggiunti strumenti riproducibili di generazione/audit e attivato un browser con ricerca per la lista delle forme musicali, composta da 607 termini.
- Lasciati invariati tutti i campi SPARQL non-IFLA e aggiunto alla validazione del profilo l'audit dei conteggi e dei collegamenti IFLA.

---

## 0.1.12-draft - 2026-08-27

- Fixed a duplicate relationship-type code: `cnd` was assigned to two distinct types ("R56_042 Choral conductor" and "R56_061 Conductor"). Renamed the choral-conductor type to `dac_choral_conductor`; the other keeps `cnd`.

---

## 0.1.12-draft - 2026-08-27

- Corretto un codice di relationship-type duplicato: `cnd` era assegnato a due type distinti ("R56_042 Choral conductor" e "R56_061 Conductor"). Rinominato il type "choral conductor" in `dac_choral_conductor`; l'altro mantiene `cnd`.

---

## 0.1.11-draft - 2026-08-26

- Added the `Organico` datatype to the schema and introduced `organico_CN`, an interactive icon-based instrumentation editor (orchestral fan chart or ensemble rows) built on the IFLA UNIMARC Medium of Performance vocabulary. Its "Create alternative" feature handles alternation between individual instruments within the same instrumentation (e.g. flute/oboe).
- Added `organico_alt_CN`, a second independent field using the same editor, for an instrumentation entirely alternative to the main one (e.g. a full-orchestra version vs. a reduced chamber-ensemble version) — distinct from the item-level alternation already supported inside `organico_CN`.
- Removed `analyticinstrum_CN` and `analyticinstrum_CN2` (the granular UNIMARC/IFLA "Organico analitico" and "Organico alternativo (/$)" containers) and their screen placements, replaced by `organico_CN` and `organico_alt_CN`. Existing catalogued data in these fields is unaffected; they are simply no longer part of the installable schema.
- Kept the canonical and generated English profile variants synchronized and XSD-valid.

---

## 0.1.11-draft - 2026-08-26

- Aggiunto il datatype `Organico` allo schema e introdotto `organico_CN`, un editor interattivo dell'organico a icone (ventaglio orchestrale o righe per ensemble) basato sul vocabolario IFLA UNIMARC Medium of Performance. La sua funzione "Crea alternativa" gestisce l'alternanza tra singoli strumenti all'interno dello stesso organico (es. flauto/oboe).
- Aggiunto `organico_alt_CN`, un secondo campo indipendente con lo stesso editor, per un organico interamente alternativo a quello principale (es. versione per grande orchestra vs. versione per organico da camera ridotto) — distinto dall'alternanza a livello di singolo strumento già supportata dentro `organico_CN`.
- Rimossi `analyticinstrum_CN` e `analyticinstrum_CN2` (i container granulari UNIMARC/IFLA "Organico analitico" e "Organico alternativo (/$)") e i relativi placement nelle schermate, sostituiti da `organico_CN` e `organico_alt_CN`. I dati già catalogati in questi campi non vengono toccati: semplicemente non fanno più parte dello schema installabile.
- Mantenute sincronizzate e valide rispetto all'XSD le varianti canonica e inglese del profilo.

---

## 0.1.10-draft - 2026-08-09

- Restricted the collection navigation browser to bibliographic resources, keeping collection-to-collection relationships in their dedicated placement.
- Prevented duplicate collection relationships across the two frontend relationship families.
- Kept the canonical and generated English profile variants synchronized and XSD-valid.

---

## 0.1.9-draft - 2026-08-04

- Standardized the user-facing terminology for the bibliographic Item entity in Italian and English labels and help texts.
- Preserved the existing `esemplare` technical identifiers and type restrictions for backward compatibility.
- Kept the canonical and English profile variants synchronized and XSD-valid.

---

## 0.1.8-draft - 2026-07-26

- Corrected the Italian locale of the unique process identifier label.
- Kept the canonical and English profile variants synchronized and XSD-valid.

---

## 0.1.7-draft - 2026-07-21

- Corrected the relationships screen type restriction for bibliographic resource records (`biblio_resource_record`).
- Kept the canonical and English profile variants synchronized and XSD-valid.

---

## 0.1.7-draft - 2026-07-21

- Corretta la restrizione tipologica dello screen relazioni per le risorse bibliografiche (`biblio_resource_record`).
- Mantenute sincronizzate e valide rispetto all'XSD le varianti canonica e inglese del profilo.

---

## 0.1.6-draft - 2026-07-18

- Consolidated the reviewed Italian and English labels and backend help texts.
- Corrected semantic inconsistencies, mistranslations, and cataloguing-text typos.
- Removed obsolete UI placements identified during frontend validation.
- Established `ACUSTEME_profile.xml` as the canonical editable profile; the English documentation-link variant is now generated from it.

---

## 0.1.6-draft - 2026-07-18

- Consolidate le etichette italiane e inglesi e gli help backend sottoposti a revisione.
- Corrette incoerenze semantiche, traduzioni errate e refusi nei testi catalografici.
- Rimossi i placement UI obsoleti individuati durante la validazione del frontend.
- Stabilito `ACUSTEME_profile.xml` come unico profilo modificabile; la variante con link alla documentazione inglese viene ora generata automaticamente.

---

## 0.1.5-draft - 2026-07-09

- Published the initial draft package of the ACUSTEME CollectiveAccess backend profile.
- Added Italian and English documentation-link profile variants.
- Removed generated Wiki.js HTML pages, CSS/assets, local documentation exports, and upload scripts from the repository package.

---

## 0.1.5-draft - 2026-07-09

- Pubblicata la versione draft iniziale del pacchetto backend del profilo CollectiveAccess ACUSTEME.
- Aggiunte le varianti del profilo con link di documentazione in italiano e in inglese.
- Rimossi dal pacchetto repository pagine HTML generate per Wiki.js, CSS/assets, export locali della documentazione e script di upload.
