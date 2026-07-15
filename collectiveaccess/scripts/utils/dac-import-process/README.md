# DAC importer — utility di importazione

Pipeline per validare i fogli discografici DAC, generare XML destinato a
CollectiveAccess, arricchirlo tramite GeoNames e Discogs e scaricare le cover.

La documentazione estesa del caso di studio **Discografia antagonista**, con
descrizione della pipeline, esempi XML e ulteriori dettagli sul mapping, è
disponibile nella wiki ACUSTEME:

<https://wiki.acusteme.org/it/acusteme_data_model/case_studies/discografia_antagonista>

Gli esempi XML pubblicati nella wiki costituiscono il riferimento da verificare
quando si interviene sulla struttura prodotta dagli script: modifiche a nomi,
ordine, attributi o cardinalità dei nodi possono richiedere un aggiornamento del
mapping CollectiveAccess.

## File e responsabilità

| File | Funzione |
|---|---|
| `dac_common.py` | Regole condivise per intestazioni, pseudonimi, responsabilità, relator e report di errore. |
| `check_relators.py` | Controllo preliminare Excel/profilo CA; produce JSON completo e report HTML leggibile. |
| `1_dacparser2.py` | Validazione bloccante e conversione di uno o più fogli Excel in XML. |
| `2_xmlpostprocess2.py` | Normalizzazione relator, collane, GeoNames, Wikidata, MIMO, materiali e media. |
| `3_discogs3.py` | Download non distruttivo delle cover e manifest CSV; non riscrive Excel. |
| `4_discogs_enrich.py` | Arricchimento XML live con release/master, tracce e identificatori Discogs. |
| `5_technical_audit.py` | Audit read-only dei dati tecnici XML rispetto al parser, al profilo CA e alle release Discogs; produce HTML e JSON. |
| `xmlrel_extractor.py` | Documentazione HTML delle relationship table del profilo CA. |

Il profilo usato per i controlli è l'unica copia pubblica mantenuta in
`../../../install-profiles/acusteme/ACUSTEME_profile.xml`. Workbook, mapping,
output, cover e altri dati di lavoro devono restare fuori dal repository.

Gli output XML e i report generati durante le esecuzioni non sono versionati:
devono essere prodotti localmente usando i comandi descritti di seguito.

## Installazione

Creare un ambiente virtuale e installare:

```bash
python -m pip install -r requirements.txt
```

Per le operazioni Discogs creare un `.env` locale, mai versionato:

```text
DISCOGS_TOKEN=...
```

## Ordine consigliato

1. Validare relator, struttura e codifiche del foglio:

   ```bash
   python check_relators.py /percorso/privato/dati.xlsx \
     --sheet "Nome foglio" --output relators.json
   ```

   Vengono creati `relators.json` e `relators.html`. Il report HTML contiene
   foglio, riga Excel, campo, gravità, valore originale e correzione suggerita.

2. Generare l'XML. La generazione si interrompe se esistono errori di validazione,
   ma salva comunque i report `.validation.json` e `.validation.html`:

   ```bash
   python 1_dacparser2.py /percorso/privato/dati.xlsx output.xml \
     --sheet "Nome foglio"
   ```

   `--sheet` può essere ripetuto. Senza `--sheet` vengono elaborati tutti i fogli.
   GeoNames è disabilitato per default; per abilitarlo usare `--geonames-username`.

3. Post-processare l'XML:

   ```bash
   python 2_xmlpostprocess2.py output.xml output_post.xml
   ```

   Per compatibilita con la pipeline originale, il parser genera sempre il
   blocco tecnico `spessore_solco`, `tecnica2`, `segnale` prima di `velocita`.
   Il post-processore converte le coppie Wikidata `label`/`url` nei valori
   `CA_WD_string` richiesti dal mapping CollectiveAccess.

4. Arricchire con Discogs, dopo avere configurato `DISCOGS_TOKEN` in `.env`:

   ```bash
   python 4_discogs_enrich.py
   ```

5. Controllare i dati tecnici senza modificare l'XML:

   ```bash
   python 5_technical_audit.py output_post.xml \
     --json technical_report.json --html technical_report.html
   ```

   Lo script non salva alcun XML. Segnala l'assenza di una fonte Discogs, i link
   che puntano soltanto a un master, i conflitti con una release esatta, i campi
   mancanti e le codifiche incoerenti prodotte dal parser. Le correzioni restano
   intenzionalmente manuali. Ogni record anomalo espone nel JSON
   `requires_human_review: true` ed è marcato chiaramente nell'HTML; il riepilogo
   conta separatamente tutti i record che richiedono controllo umano.

   I campi linked-data sono serializzati nel formato richiesto da
   CollectiveAccess `etichetta|QID|URL`. `segnale`, `tipo_supporto` e `tecnica1`
   sono invece liste chiuse del profilo e non usano `CA_WD_string`.

6. Scaricare le cover senza modificare Excel:

   ```bash
   python 3_discogs3.py /percorso/privato/dati.xlsx \
     --sheet "Nome foglio" --output-dir covers --manifest covers_manifest.csv
   ```

7. Generare la documentazione delle relationship table:

   ```bash
   python xmlrel_extractor.py
   ```

## Pseudonimi

La forma ammessa è `*Pseudonimo* [Nome, Cognome] (Rxx codice)`. Nell'XML:

- `label` e `pseudonym` contengono lo pseudonimo;
- `first_name`, `last_name` e `real_name` contengono il nome reale.

Un solo asterisco, virgolette al posto dell'asterisco o parentesi sbilanciate sono
errori bloccanti e vengono riportati nel JSON di validazione.

## Errori bloccanti

La generazione XML viene fermata in presenza di colonne obbligatorie mancanti,
ID Discogs duplicati, link non supportati, parentesi sbilanciate, pseudonimi
malformati, responsabilità senza ruolo o ruoli non codificati. Questo evita di
produrre XML formalmente valido ma semanticamente incompleto.

Le codifiche legacy `R55_26_xxx` vengono confrontate con la forma corrente
`R55_100_xxx` del profilo. Le anomalie del profilo, inclusi codici duplicati o
ambigui, vengono riportate separatamente.
