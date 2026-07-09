# ACUSTEME CollectiveAccess Profile

First public draft of the ACUSTEME CollectiveAccess installation profile.

ACUSTEME is a research and documentation environment developed around the needs of the Museo del Paesaggio Sonoro and related cultural heritage workflows. This repository currently publishes only the backend profile materials intended for CollectiveAccess.

## Contents

- `collectiveaccess/install-profiles/acusteme/ACUSTEME_profile.xml`  
  CollectiveAccess installation profile with Italian, English, and Romanian locales as present in the source profile. The current public review focuses primarily on the Italian and English content.
- `collectiveaccess/install-profiles/acusteme/profile.xsd`  
  XML schema used to validate the profile structure.

## Draft Status

This is a first public draft. It is published to make the work inspectable, reusable, and easier to discuss, but it should not yet be considered a stable general-purpose profile.

Important limitations:

- Not all SPARQL queries are fully configured or generally reusable.
- Several linked-data queries were designed around the specific cataloguing needs of the Museo del Paesaggio Sonoro.
- The English version was produced with automatic translation support and still needs human review.
- Not all lists, labels, terms, and controlled vocabularies have been fully reviewed or normalized.
- Some documentation references and cataloguing instructions may still reflect local workflows.

Please review and adapt the profile carefully before using it in another CollectiveAccess installation.

## Backend Documentation

Backend documentation is in preparation:

- Italian: https://wiki.acusteme.org/it/home
- English: https://wiki.acusteme.org/en/home

## Validation

The profile is XML-valid at publication time:

```sh
xmllint --noout collectiveaccess/install-profiles/acusteme/ACUSTEME_profile.xml
```

## License

Unless otherwise noted, the ACUSTEME profile and documentation in this repository are released under the Creative Commons Attribution 4.0 International License (CC BY 4.0).

You are free to share and adapt the material, including for research and institutional reuse, provided that appropriate attribution is given.

Suggested attribution:

> ACUSTEME CollectiveAccess Profile, Museo del Paesaggio Sonoro / ACUSTEME project.

If executable scripts or software components are added in future releases, they may be distributed under a software license such as MIT; this will be stated explicitly in the relevant files.

---

# Profilo CollectiveAccess ACUSTEME

Prima bozza pubblica del profilo di installazione CollectiveAccess di ACUSTEME.

ACUSTEME è un ambiente di ricerca e documentazione sviluppato a partire dalle esigenze del Museo del Paesaggio Sonoro e da flussi di lavoro legati al patrimonio culturale. Questo repository pubblica al momento solo i materiali backend destinati a CollectiveAccess.

## Contenuto

- `collectiveaccess/install-profiles/acusteme/ACUSTEME_profile.xml`  
  Profilo di installazione CollectiveAccess con localizzazioni in italiano, inglese e romeno come presenti nel profilo sorgente. La revisione pubblica attuale riguarda soprattutto i contenuti in italiano e inglese.
- `collectiveaccess/install-profiles/acusteme/profile.xsd`  
  Schema XML usato per validare la struttura del profilo.

## Stato della bozza

Questa è una prima draft pubblica. Viene pubblicata per rendere il lavoro ispezionabile, riusabile e discutibile, ma non deve ancora essere considerata un profilo stabile e generalista.

Limiti importanti:

- Non tutte le query SPARQL sono completamente configurate o riutilizzabili in modo generale.
- Diverse query Linked Open Data sono costruite sulle esigenze catalografiche specifiche del Museo del Paesaggio Sonoro.
- La versione inglese è stata prodotta con supporto di traduzione automatica e necessita ancora di revisione umana.
- Non tutte le liste, le etichette, i termini e i vocabolari controllati sono stati completamente revisionati o normalizzati.
- Alcuni riferimenti alla documentazione e alcune istruzioni catalografiche possono riflettere ancora flussi di lavoro locali.

Prima di usare il profilo in un'altra installazione CollectiveAccess, è necessario rivederlo e adattarlo con attenzione.

## Documentazione backend

La documentazione backend è in preparazione:

- Italiano: https://wiki.acusteme.org/it/home
- Inglese: https://wiki.acusteme.org/en/home

## Validazione

Alla pubblicazione il profilo risulta XML valido:

```sh
xmllint --noout collectiveaccess/install-profiles/acusteme/ACUSTEME_profile.xml
```

## Licenza

Salvo diversa indicazione, il profilo ACUSTEME e la documentazione di questo repository sono rilasciati con licenza Creative Commons Attribution 4.0 International (CC BY 4.0).

È consentito condividere e adattare il materiale, anche per riuso istituzionale e di ricerca, a condizione di fornire un'attribuzione adeguata.

Attribuzione suggerita:

> ACUSTEME CollectiveAccess Profile, Museo del Paesaggio Sonoro / progetto ACUSTEME.

Se in futuro verranno aggiunti script eseguibili o componenti software, potranno essere distribuiti con una licenza software come MIT; in quel caso la licenza sarà indicata esplicitamente nei file interessati.
