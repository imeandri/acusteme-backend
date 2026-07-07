# ACUSTEME Backend Documentation Package

Bozza operativa per distribuire il profilo CollectiveAccess ACUSTEME e la documentazione Wiki.js collegata.

## Contenuto

- `ACUSTEME_profile.xml`: profilo CollectiveAccess con link documentazione italiana.
- `ACUSTEME_profile_EN.xml`: profilo equivalente con link documentazione inglese.
- `extractor_auto2.py`: genera documentazione HTML IT/EN dal profilo.
- `generate_english_profile.py`: genera il profilo EN sostituendo i link Wiki.js `/it/` con `/en/`.
- `wikijs_single_upload.py`: carica le pagine HTML su Wiki.js.
- cartelle UI: documentazione HTML italiana.
- `en/`: documentazione HTML inglese.

## Flusso minimo

Generare documentazione italiana e inglese:

```bash
python3 extractor_auto2.py
```

Rigenerare il profilo inglese:

```bash
python3 generate_english_profile.py
```

Caricare tutta la documentazione italiana su Wiki.js:

```bash
venv/bin/python wikijs_single_upload.py --language it --all-ui --overwrite-existing
```

Caricare tutta la documentazione inglese su Wiki.js:

```bash
venv/bin/python wikijs_single_upload.py --language en --all-ui --overwrite-existing
```

## Credenziali

Il file reale `wikijs_upload_config.json` non va versionato. Usa `wikijs_upload_config.example.json` come modello locale.
