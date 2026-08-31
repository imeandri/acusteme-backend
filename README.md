# ACUSTEME CollectiveAccess Backend Profile

First public-draft package of the ACUSTEME CollectiveAccess installation profile.

This public repository contains backend/profile materials, the audited Wiki.js
GraphQL synchronization source code, and reviewed Providence runtime
customizations. It does not contain generated HTML pages, local documentation
exports, legacy browser upload scripts, frontend code, credentials, or
production data.

## Contents

- `ACUSTEME_profile.xml`  
  Italian-oriented CollectiveAccess installation profile. Its `documentation_url` settings point to the Italian ACUSTEME Wiki.js documentation branch.
- `ACUSTEME_profile_EN.xml`  
  Generated English documentation-link variant of the canonical profile. It points to the English ACUSTEME Wiki.js documentation branch and must not be edited directly.
- `profile.xsd`  
  XML schema used to validate the profile files.
- `CHANGELOG.md`  
  Release notes for the profile package.
- `tools/wikijs_sync/`
  Incremental Wiki.js GraphQL synchronizer, SPARQL/generation audit, automated
  tests, and operating instructions. Generated documentation is kept out of
  Git and built in memory from the canonical profile.
- `providence/`
  Production-derived Providence runtime customizations for the Organico
  datatype/editor and the title prepopulate plugin. Paths mirror the Providence
  installation root; provenance, deployment notes, hashes, and licensing are
  documented in `providence/README.md`.

## Authoritative source and editing workflow

`ACUSTEME_profile.xml` is the only editable profile source. Every commit that
changes it must also add a concise entry to `CHANGELOG.md`.

Regenerate the English documentation-link variant and validate both profiles
before committing:

```sh
python3 tools/build_en_profile.py
tools/validate_profiles.sh
```

The closed IFLA UNIMARC lists are generated from the pinned upstream revision
recorded in `tools/build_ifla_lists.py`. Missing upstream labels are completed
by the reviewed semantic pairs in `tools/ifla_acusteme_labels.json`, followed
by the Wikidata snapshot. Both English and Italian are mandatory; generation
fails if either label is unavailable. To rebuild or verify the lists:

```sh
python3 tools/build_ifla_lists.py
python3 tools/build_ifla_lists.py --check
```

The five closed LoC/MARC video vocabularies are maintained in the same way:

```sh
python3 tools/build_loc_lists.py
python3 tools/build_loc_lists.py --check
python3 tools/build_loc_lists.py --check-source
```

The seven open-domain Wikidata searches for electronic resources share a
canonical query that returns one row per entity. To apply or verify it:

```sh
python3 tools/build_wikidata_search_queries.py
python3 tools/build_wikidata_search_queries.py --check
```

## Backend Documentation

Backend documentation is in preparation:

- Italian: https://wiki.acusteme.org/it/home
- English: https://wiki.acusteme.org/en/home

Synchronization and canary instructions are documented in
[`tools/wikijs_sync/README.md`](tools/wikijs_sync/README.md).

## Draft Status and Disclaimer

This is an initial draft release package. It is published for review, reuse, and discussion, but it should not yet be considered a stable general-purpose CollectiveAccess profile.

Important limitations:

- Not all SPARQL queries are fully configured or generally reusable.
- Several linked-data queries are designed around the specific cataloguing needs of the Museo del Paesaggio Sonoro.
- The English profile is a documentation-link variant and includes automatically translated English content that still requires human review.
- Not all lists, labels, terms, and controlled vocabularies have been fully reviewed, normalized, or validated.
- Some cataloguing instructions and documentation references still reflect local implementation choices.

Please review and adapt the profile carefully before using it in another CollectiveAccess installation.

## Validation

At preparation time, both profile files are XML-valid:

```sh
xmllint --noout ACUSTEME_profile.xml
xmllint --noout ACUSTEME_profile_EN.xml
```

## License

Unless otherwise noted, the ACUSTEME profile and documentation in this repository are released under the Creative Commons Attribution 4.0 International License (CC BY 4.0).

Suggested attribution:

> ACUSTEME CollectiveAccess Backend Profile, Università di Torino - Dipartimento di Studi Umanistici / ACUSTEME project.

If executable scripts or software components are added in future releases, they may be distributed under a software license such as MIT; this will be stated explicitly in the relevant files.

---

# Profilo backend CollectiveAccess ACUSTEME

Prima draft del pacchetto backend del profilo di installazione CollectiveAccess di ACUSTEME.

Questo repository pubblico contiene materiali backend/profilo, il codice
verificato per la sincronizzazione GraphQL di Wiki.js e le personalizzazioni
runtime Providence revisionate. Non contiene le pagine HTML generate, gli
export locali della documentazione, i vecchi uploader via browser, frontend,
credenziali o dati di produzione.

## Contenuto

- `ACUSTEME_profile.xml`  
  Profilo di installazione CollectiveAccess orientato alla documentazione italiana. Le impostazioni `documentation_url` puntano alla branch italiana della documentazione ACUSTEME su Wiki.js.
- `ACUSTEME_profile_EN.xml`  
  Variante generata automaticamente dal profilo canonico, con link alla documentazione inglese. Non deve essere modificata direttamente.
- `profile.xsd`  
  Schema XML usato per validare i file del profilo.
- `CHANGELOG.md`  
  Note di rilascio del pacchetto profilo.
- `tools/wikijs_sync/`
  Sincronizzatore incrementale GraphQL per Wiki.js, audit della generazione e
  delle query SPARQL, test automatici e istruzioni operative. La documentazione
  generata non viene versionata ed è costruita in memoria dal profilo canonico.
- `providence/`
  Personalizzazioni runtime Providence derivate dalla produzione per il
  datatype/editor Organico e per il plugin di prepopolamento del titolo. I
  percorsi rispecchiano la root dell'installazione Providence; provenienza,
  distribuzione, hash e licenza sono documentati in `providence/README.md`.

## Fonte autorevole e flusso di modifica

`ACUSTEME_profile.xml` è l'unica fonte modificabile. Ogni commit che lo cambia
deve aggiungere anche una voce sintetica a `CHANGELOG.md`.

Prima del commit, rigenerare la variante con link inglesi e validare entrambi i
profili:

```sh
python3 tools/build_en_profile.py
tools/validate_profiles.sh
```

Le liste chiuse IFLA UNIMARC sono generate dalla revisione upstream fissata in
`tools/build_ifla_lists.py`. Le etichette mancanti nella fonte sono completate
dalle coppie semantiche revisionate in `tools/ifla_acusteme_labels.json` e poi
dallo snapshot Wikidata. Inglese e italiano sono entrambi obbligatori: la
generazione fallisce se manca una delle due etichette. Per rigenerarle o
verificarle:

```sh
python3 tools/build_ifla_lists.py
python3 tools/build_ifla_lists.py --check
```

I cinque vocabolari video chiusi LoC/MARC sono gestiti nello stesso modo:

```sh
python3 tools/build_loc_lists.py
python3 tools/build_loc_lists.py --check
python3 tools/build_loc_lists.py --check-source
```

Le sette ricerche Wikidata a dominio aperto per le risorse elettroniche usano
una query canonica che restituisce una riga per entità. Per applicarla o
verificarla:

```sh
python3 tools/build_wikidata_search_queries.py
python3 tools/build_wikidata_search_queries.py --check
```

## Documentazione backend

La documentazione backend è in preparazione:

- Italiano: https://wiki.acusteme.org/it/home
- Inglese: https://wiki.acusteme.org/en/home

La procedura di sincronizzazione e canary è descritta in
[`tools/wikijs_sync/README.md`](tools/wikijs_sync/README.md).

## Stato della draft e disclaimer

Questa è una release draft iniziale. Viene preparata per revisione, riuso e discussione, ma non deve ancora essere considerata un profilo CollectiveAccess stabile e generalista.

Limiti importanti:

- Non tutte le query SPARQL sono completamente configurate o riutilizzabili in modo generale.
- Diverse query Linked Open Data sono costruite sulle esigenze catalografiche specifiche del Museo del Paesaggio Sonoro.
- Il profilo inglese è una variante con link di documentazione in inglese e include contenuti tradotti automaticamente che richiedono ancora revisione umana.
- Non tutte le liste, le etichette, i termini e i vocabolari controllati sono stati completamente revisionati, normalizzati o validati.
- Alcune istruzioni catalografiche e alcuni riferimenti alla documentazione riflettono ancora scelte locali di implementazione.

Prima di usare il profilo in un'altra installazione CollectiveAccess, è necessario rivederlo e adattarlo con attenzione.

## Validazione

Al momento della preparazione entrambi i profili risultano XML validi:

```sh
xmllint --noout ACUSTEME_profile.xml
xmllint --noout ACUSTEME_profile_EN.xml
```

## Licenza

Salvo diversa indicazione, il profilo ACUSTEME e la documentazione di questo repository sono rilasciati con licenza Creative Commons Attribution 4.0 International (CC BY 4.0).

Attribuzione suggerita:

> ACUSTEME CollectiveAccess Backend Profile, Università di Torino - Dipartimento di Studi Umanistici / progetto ACUSTEME.

Se in futuro verranno aggiunti script eseguibili o componenti software, potranno essere distribuiti con una licenza software come MIT; in quel caso la licenza sarà indicata esplicitamente nei file interessati.
