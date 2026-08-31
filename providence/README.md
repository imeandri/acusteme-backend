# ACUSTEME Providence runtime customizations

This directory mirrors the paths of the ACUSTEME production Providence root.
The files were imported from the running production instance on 2026-08-31,
which is the authoritative source for this snapshot.

## Included components

- `app/lib/Attributes/Values/OrganicoAttributeValue.php` and
  `app/lib/Attributes/Values/Organico/IconDictionary.php`: custom `Organico`
  attribute datatype and its icon dictionary.
- `assets/organico/`: editor, normalizer, SBN parser, stage, styles,
  vocabularies, and SVG sprite used by the datatype.
- `app/conf/assets.conf`: production asset-loader configuration, including the
  `organico` bundle. This is a complete production snapshot; reconcile it with
  upstream Providence changes during upgrades rather than copying it blindly
  over a newer upstream version.
- `app/locale/user/it_IT/messages.po`: Italian strings used by the editor. The
  generated `messages.mo` is intentionally not versioned.
- `app/plugins/prepopulatePHP/`: the production prepopulate plugin and its
  required dictionaries. Runtime backups and `prepopulate_debug.log` are not
  versioned.

`MANIFEST.sha256` records the exact production hashes. Run the repository
validator after any update:

```sh
tools/validate_providence_runtime.sh
```

## Deployment notes

The paths below `providence/` are relative to the Providence installation
root. After deploying the reviewed files, compile the Italian catalogue and
clear the application caches through the normal Providence maintenance flow:

```sh
msgfmt -o app/locale/user/it_IT/messages.mo app/locale/user/it_IT/messages.po
```

The production instance remains authoritative until an explicit deployment
workflow promotes this repository to the canonical source.

## License

The software in this directory is distributed under the MIT License; see
`LICENSE`.
