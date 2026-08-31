#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

shasum -a 256 -c providence/MANIFEST.sha256

php -l providence/app/lib/Attributes/Values/Organico/IconDictionary.php >/dev/null
php -l providence/app/lib/Attributes/Values/OrganicoAttributeValue.php >/dev/null
php -l providence/app/plugins/prepopulatePHP/dictionaries.php >/dev/null
php -l providence/app/plugins/prepopulatePHP/prepopulatePHPPlugin.php >/dev/null

for script in providence/assets/organico/*.js; do
    node --check "$script"
done

python3 -m json.tool providence/assets/organico/mop-vocabulary.json >/dev/null
python3 -m json.tool providence/assets/organico/sbn-marc-dictionary.json >/dev/null
python3 -c 'import xml.etree.ElementTree as ET; ET.parse("providence/assets/organico/sprite.svg")'

if command -v msgfmt >/dev/null 2>&1; then
    msgfmt --check -o /dev/null providence/app/locale/user/it_IT/messages.po
fi

echo "Providence runtime validation passed."
