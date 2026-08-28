# Sincronizzazione incrementale Wiki.js

`wikijs_sync.py` genera in memoria la documentazione dal profilo aureo GitHub,
confronta soltanto le pagine interessate e protegge gli esempi d'uso compilati
manualmente.

## Componenti

- `extractor_auto2.py`: genera il corpus IT/EN dal profilo XML aureo.
- `sparql_query_tools.py`: rende eseguibili i link WDQS neutralizzando soltanto
  le espressioni `REGEX` che contengono `PLACEHOLDER`, senza troncare parentesi
  o righe SPARQL.
- `audit_generated_documentation.py`: controlla sintassi SPARQL, integrità
  delle query renderizzate e struttura delle pagine.
- `wikijs_graphql.py`: client Wiki.js 2 con rilettura e verifica dopo ogni
  mutazione.
- `wikijs_manual_regions.py`: contratto e merge delle aree manuali.
- `wikijs_sync_state.py`: stato locale necessario al confronto a tre vie.
- `wikijs_sync.py`: comando operativo per audit, simulazione e applicazione.

## Installazione

È consigliato un ambiente Python dedicato:

```bash
cd tools/wikijs_sync
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python -m unittest discover -v
```

Tutti gli altri comandi di questa guida presuppongono di essere eseguiti dalla
cartella `tools/wikijs_sync`.

Il generatore legge per impostazione predefinita il profilo aureo dal branch
`main` di `imeandri/acusteme-backend`. Un profilo locale può essere indicato
con `--xml /percorso/profilo.xml`.

## Aree manuali

Ogni area modificabile è racchiusa da marker versionati e contiene un DIV con
una chiave stabile:

```html
<!-- ACUSTEME-MANUAL:v1:BEGIN key="object_ui/screen::placement" -->
<div class="acusteme-manual-region" data-acusteme-key="object_ui/screen::placement">
<p>Esempi d'uso: <span class="placeholder">{to be completed}</span></p>
</div>
<!-- ACUSTEME-MANUAL:v1:END key="object_ui/screen::placement" -->
```

Si può sostituire liberamente il contenuto compreso tra i due commenti,
incluso l'intero DIV. La classe `placeholder` non va conservata dopo avere
compilato l'esempio: è soltanto lo stile del testo iniziale. I due commenti non
devono invece essere modificati, spostati, duplicati o annidati. Il contenuto
manuale viene copiato byte per byte.

Esempio compilato valido:

```html
<!-- ACUSTEME-MANUAL:v1:BEGIN key="object_ui/screen::placement" -->
<div class="acusteme-manual-region">
  <p><strong>Esempi d'uso:</strong> Testo compilato manualmente.</p>
</div>
<!-- ACUSTEME-MANUAL:v1:END key="object_ui/screen::placement" -->
```

> **Importante:** i commenti `BEGIN` e `END` sono invisibili nella pagina ma
> sono il confine di proprietà usato dal sincronizzatore. Non eliminarli
> dall'editor HTML di Wiki.js.

## Audit della generazione e delle query

L'audit indipendente genera tutto in memoria e verifica:

- sintassi delle query sorgenti;
- sintassi delle versioni eseguibili nei link WDQS;
- corrispondenza esatta tra query XML, blocchi mostrati e link;
- assenza di troncamenti o tag HTML dentro il codice SPARQL;
- conteggio e posizione di tipi, obbligatorietà, ripetibilità, quicktip,
  vocabolari e aree manuali.

```bash
venv/bin/python audit_generated_documentation.py \
  --report /tmp/acusteme-generation-audit.json
```

Il confronto con una generazione precedente è opzionale:

```bash
venv/bin/python audit_generated_documentation.py \
  --previous-root /percorso/generazione-precedente \
  --report /tmp/acusteme-generation-comparison.json
```

## Sequenza operativa

1. Audit locale, senza credenziali e senza connessione a Wiki.js:

   ```bash
   python3 wikijs_sync.py audit --report /tmp/acusteme-audit.json
   ```

2. Fornire il token senza inserirlo nella cronologia della shell:

   ```bash
   export WIKIJS_API_TOKEN='...'
   ```

   In alternativa, salvare il solo token in `wikijs_api_token.txt`, già
   escluso da Git, e usare `--token-file wikijs_api_token.txt`.

3. Leggere tutte le pagine e produrre il piano senza effettuare scritture:

   ```bash
   python3 wikijs_sync.py dry-run --report /tmp/acusteme-dry-run.json
   ```

   Per la sola prima adozione di una wiki già caricata dal repository, si può
   indicare esplicitamente la versione Git verificata come baseline:

   ```bash
   python3 wikijs_sync.py dry-run --bootstrap-git-ref HEAD \
     --report /tmp/acusteme-bootstrap-dry-run.json
   ```

   Sono tollerate esclusivamente le normalizzazioni note dell'editor Wiki.js:
   fine riga, spazi non separabili e caratteri zero-width. Ogni altra modifica
   continua a produrre un conflitto.

4. Applicare soltanto un piano senza conflitti:

   ```bash
   python3 wikijs_sync.py apply --confirm APPLY \
     --report /tmp/acusteme-apply.json
   ```

È possibile limitare l'operazione con `--languages it`, `--languages en` e con
una o più opzioni `--only-ui object_ui`. Per una simulazione puntuale si può
usare più volte `--only-page`, preferibilmente specificando anche la lingua:

```bash
python3 wikijs_sync.py dry-run \
  --only-page it:acusteme_data_model/DM_documentation/object_ui/classificazione
```

Per un canary completo, simulare e applicare esattamente le stesse pagine:

```bash
venv/bin/python wikijs_sync.py dry-run \
  --token-file wikijs_api_token.txt \
  --only-page it:acusteme_data_model/DM_documentation/object_ui/classificazione \
  --report /tmp/acusteme-canary-dry-run.json

venv/bin/python wikijs_sync.py apply --confirm APPLY \
  --token-file wikijs_api_token.txt \
  --only-page it:acusteme_data_model/DM_documentation/object_ui/classificazione \
  --report /tmp/acusteme-canary-apply.json
```

Ripetendo subito il `dry-run`, la pagina deve risultare `unchanged`. Una
regione manuale compilata può produrre un hash completo diverso da quello
generato senza costituire un conflitto: il confronto di proprietà esclude
appositamente il contenuto tra i marker.

## Regole di sicurezza

- La prima adozione di una pagina senza marker è automatica solo se il suo HTML
  coincide esattamente con l'output precedente del generatore.
- Una modifica remota fuori dalle aree manuali produce un conflitto.
- Una modifica remota del titolo, dell'editor o dell'identità della pagina
  produce un conflitto.
- Una regione manuale rimossa dal profilo produce un conflitto; un vecchio
  placeholder non compilato può invece essere eliminato.
- Prima di ogni scrittura la pagina viene riletta. Dopo la mutazione viene
  riletta e verificata integralmente.
- Le mutazioni non vengono ritentate automaticamente.
- Se esiste anche un solo conflitto, `apply` non avvia alcuna scrittura.
- `--only-page` è ripetibile e consente di limitare con precisione un canary;
  senza filtri il comando considera l'intero corpus IT/EN.

## Stato locale

Dopo ogni pagina applicata viene salvata in `.wikijs-sync/` la versione
generata di riferimento. Questo permette il confronto a tre vie nelle
esecuzioni successive. Lo stato non contiene il token ed è escluso da Git.

È opportuno includere `.wikijs-sync/` nei backup operativi: cancellarlo non
elimina pagine, ma fa perdere la base necessaria per distinguere le modifiche
manuali da quelle generate.

## Errori e ripristino

L'applicazione non elimina pagine e non modifica il profilo aureo. In caso di
interruzione, lo stato viene registrato dopo ogni pagina verificata e una nuova
modalità `dry-run` mostra ciò che resta da fare.

Per ripristinare una pagina usare la cronologia di Wiki.js. Il successivo
`dry-run` segnalerà correttamente la divergenza come conflitto: prima di
riprendere l'aggiornamento occorre decidere se mantenere il ripristino remoto o
rigenerare e riapplicare la versione gestita.

## Procedura raccomandata per il rilascio completo

1. Eseguire i test Python.
2. Eseguire `audit_generated_documentation.py` e conservare il report JSON.
3. Eseguire un `dry-run` globale e risolvere ogni conflitto.
4. Applicare prima una o due pagine canary.
5. Verificare visivamente query ed esempi manuali.
6. Ripetere il `dry-run` sulle canary: devono risultare invariate.
7. Eseguire l'`apply` globale e infine un ultimo `dry-run` globale.
