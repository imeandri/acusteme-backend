# Changelog

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
