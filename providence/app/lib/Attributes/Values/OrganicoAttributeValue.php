<?php
/** ---------------------------------------------------------------------
 * app/lib/Attributes/Values/OrganicoAttributeValue.php :
 * ----------------------------------------------------------------------
 * CollectiveAccess / AcusTeme custom datatype.
 *
 * Stores the "organico" (instrumentation) of a musical work as a single
 * JSON blob (see organico-viewer/docs/schema.md for the exact shape:
 * {titolo, organico_sintetico, ensemble_type, items[]}) in value_longtext1,
 * the same storage pattern used by FloorplanAttributeValue/ColorAttributeValue.
 *
 * The editing widget renders a compact summary + "Modifica organico" button;
 * clicking it opens an overlay panel (same idea as FloorplanAttributeValue's
 * media panel — a rich three-column editor doesn't belong squeezed into a
 * bundle table cell) containing the full icon-based editor from
 * organico-viewer (palette search over the 392-term IFLA MOP vocabulary,
 * item list with bulk group/alternative actions, live SVG preview). See
 * assets/organico/organico-editor.js (adapted copy of organico-viewer's
 * assets/js/organico-editor.js — same source, global namespace instead of
 * ES modules since CA loads scripts classically via AssetLoadManager) and
 * assets/organico/organico-normalizer.js (JS port of OrganicoNormalizer.php/
 * IconDictionary.php, needed because CA's .htaccess only allows
 * index.php/service.php/tilepic.php to be reached directly — no arbitrary
 * PHP preview endpoint — so the live preview normalizes entirely client-side).
 * ----------------------------------------------------------------------
 */
define("__CA_ATTRIBUTE_VALUE_ORGANICO__", 35);

require_once(__CA_LIB_DIR__.'/Attributes/Values/IAttributeValue.php');
require_once(__CA_LIB_DIR__.'/Attributes/Values/AttributeValue.php');
require_once(__CA_LIB_DIR__.'/BaseModel.php');	// FT_*/DT_* constants
require_once(__DIR__.'/Organico/IconDictionary.php');

global $_ca_attribute_settings;
$_ca_attribute_settings['OrganicoAttributeValue'] = array(
	'doesNotTakeLocale' => array(
		'formatType' => FT_NUMBER,
		'displayType' => DT_CHECKBOXES,
		'default' => 1,
		'width' => 1, 'height' => 1,
		'label' => _t('Does not use locale setting'),
		'description' => _t('Check this option if you don\'t want the value to be locale-specific. (The default is to be.)'),
	),
	'fieldWidth' => array(
		'formatType' => FT_NUMBER,
		'displayType' => DT_FIELD,
		'default' => 90,
		'width' => 5, 'height' => 1,
		'label' => _t('Width of data entry field in user interface'),
		'description' => _t('Width, in characters, of the field when displayed in a user interface.')
	),
	'fieldHeight' => array(
		'formatType' => FT_NUMBER,
		'displayType' => DT_FIELD,
		'default' => 10,
		'width' => 5, 'height' => 1,
		'label' => _t('Height of data entry field in user interface'),
		'description' => _t('Height, in characters, of the field when displayed in a user interface.')
	),
	'canBeUsedInDisplay' => array(
		'formatType' => FT_NUMBER,
		'displayType' => DT_CHECKBOXES,
		'default' => 1,
		'width' => 1, 'height' => 1,
		'label' => _t('Can be used in display'),
		'description' => _t('Check this option if this attribute value can be used for display in search results. (The default is to be.)')
	),
);

class OrganicoAttributeValue extends AttributeValue implements IAttributeValue {
	# ------------------------------------------------------------------
	protected $ops_text_value;
	# ------------------------------------------------------------------
	public function __construct($pa_value_array=null) {
		parent::__construct($pa_value_array);
	}
	# ------------------------------------------------------------------
	public function loadTypeSpecificValueFromRow($pa_value_array) {
		$this->ops_text_value = $pa_value_array['value_longtext1'];
	}
	# ------------------------------------------------------------------
	/**
	 * IMPORTANT: CollectiveAccess reuses this same method both (a) to populate
	 * the editing widget's initial value (ca_attributes.php builds
	 * $va_initial_values from getDisplayValue() and substitutes it into the
	 * {{element_id}} token in htmlFormElement()'s output) and (b) for plain-text
	 * display in search results/detail views. Returning a human summary here
	 * (as an earlier version of this method did) breaks the edit round-trip:
	 * the summary — not the JSON — gets shown back for editing, and re-saving
	 * without noticing would fail JSON validation or clobber the real value.
	 * So this MUST return the raw stored value, exactly like ColorAttributeValue/
	 * FloorplanAttributeValue do for their (simpler) stored values. A nicer
	 * human-readable summary for read-only contexts is a separate concern to
	 * solve later (e.g. a dedicated display bundle), not this method.
	 *
	 * @param array $pa_options
	 * @return string
	 */
	public function getDisplayValue($pa_options=null) {
		return (string) $this->ops_text_value;
	}
	# ------------------------------------------------------------------
	/**
	 * @param string $ps_value JSON string: {titolo, organico_sintetico, ensemble_type, items[]}
	 * @param array $pa_element_info
	 * @param array $pa_options
	 * @return array|bool|null
	 */
	public function parseValue($ps_value, $pa_element_info, $pa_options=null) {
		$ps_value = trim((string) $ps_value);
		if ($ps_value === '') {
			return array('value_longtext1' => '');
		}

		$va_decoded = json_decode($ps_value, true);
		if (!is_array($va_decoded) || json_last_error() !== JSON_ERROR_NONE) {
			$this->postError(1970, _t('Organico is not valid JSON'), 'OrganicoAttributeValue->parseValue()');
			return false;
		}
		if (isset($va_decoded['items']) && !is_array($va_decoded['items'])) {
			$this->postError(1970, _t('Organico "items" must be a list'), 'OrganicoAttributeValue->parseValue()');
			return false;
		}

		return array(
			'value_longtext1' => $ps_value,
		);
	}
	# ------------------------------------------------------------------
	/**
	 * @param array $pa_element_info
	 * @param array $pa_options
	 * @return string
	 */
	public function htmlFormElement($pa_element_info, $pa_options=null) {
		AssetLoadManager::register('organico', 'data');
		AssetLoadManager::register('organico', 'normalizer');
		AssetLoadManager::register('organico', 'sbnParser');
		AssetLoadManager::register('organico', 'stage');
		AssetLoadManager::register('organico', 'editor');
		AssetLoadManager::register('organico', 'stageCss');
		AssetLoadManager::register('organico', 'editorCss');

		$id = '{fieldNamePrefix}'.$pa_element_info['element_id'].'_{n}';
		$wrapId = 'organicoField'.$pa_element_info['element_id'].'_{n}';

		$assetsBase = $this->getAssetsBaseUrl();
		$spriteUrl = $assetsBase.'/organico/sprite.svg';
		$vocabularyUrl = $assetsBase.'/organico/mop-vocabulary.json';
		$sbnDictionaryUrl = $assetsBase.'/organico/sbn-marc-dictionary.json';
		$paletteJson = htmlspecialchars($this->buildPaletteJson(), ENT_QUOTES, 'UTF-8');
		$i18nJson = htmlspecialchars($this->buildI18nJson(), ENT_QUOTES, 'UTF-8');

		ob_start();
		?>
<div class="organico-field" id="<?= $wrapId ?>">
	<textarea name="<?= $id ?>" id="<?= $id ?>" class="organico-field__value" style="display:none"><?= '{{'.$pa_element_info['element_id'].'}}' ?></textarea>
	<div class="organico-stage organico-field__summary-stage" data-icons-sprite="<?= htmlspecialchars($spriteUrl, ENT_QUOTES, 'UTF-8') ?>" hidden></div>
	<div class="organico-field__summary">
		<span class="organico-field__summary-text"></span>
		<button type="button" class="organico-field__edit-btn"><?= htmlspecialchars(_t('Edit instrumentation'), ENT_QUOTES, 'UTF-8') ?></button>
	</div>

	<div class="organico-field__panel">
		<div class="organico-field__panel-inner">
			<div class="oe-app" data-palette='<?= $paletteJson ?>' data-vocabulary="<?= htmlspecialchars($vocabularyUrl, ENT_QUOTES, 'UTF-8') ?>" data-sbn-dictionary="<?= htmlspecialchars($sbnDictionaryUrl, ENT_QUOTES, 'UTF-8') ?>" data-icons-sprite="<?= htmlspecialchars($spriteUrl, ENT_QUOTES, 'UTF-8') ?>">
				<header class="oe-header">
					<div class="oe-header__fields">
						<label class="oe-field"><span><?= htmlspecialchars(_t('Title'), ENT_QUOTES, 'UTF-8') ?></span><input type="text" class="oe-titolo"></label>
						<label class="oe-field"><span><?= htmlspecialchars(_t('Synthetic instrumentation'), ENT_QUOTES, 'UTF-8') ?></span><input type="text" class="oe-organico-sintetico"></label>
						<fieldset class="oe-field oe-field--radio">
							<legend><?= htmlspecialchars(_t('Ensemble type'), ENT_QUOTES, 'UTF-8') ?></legend>
							<label><input type="radio" name="<?= $wrapId ?>-oe-ensemble-type" value="auto" checked> <?= htmlspecialchars(_t('Automatic'), ENT_QUOTES, 'UTF-8') ?></label>
							<label><input type="radio" name="<?= $wrapId ?>-oe-ensemble-type" value="orchestra"> <?= htmlspecialchars(_t('Orchestra (fan chart)'), ENT_QUOTES, 'UTF-8') ?></label>
							<label><input type="radio" name="<?= $wrapId ?>-oe-ensemble-type" value="ensemble"> <?= htmlspecialchars(_t('Ensemble (rows)'), ENT_QUOTES, 'UTF-8') ?></label>
						</fieldset>
						<button type="button" class="organico-field__panel-close" aria-label="<?= htmlspecialchars(_t('Close and save'), ENT_QUOTES, 'UTF-8') ?>">&#10003; <?= htmlspecialchars(_t('Close and save'), ENT_QUOTES, 'UTF-8') ?></button>
					</div>
				</header>
				<div class="oe-body">
					<aside class="oe-palette" aria-label="<?= htmlspecialchars(_t('Instrument palette'), ENT_QUOTES, 'UTF-8') ?>"></aside>
					<main class="oe-main">
						<div class="oe-toolbar">
							<button type="button" class="oe-btn oe-btn-group" disabled><?= htmlspecialchars(_t('Group into ensemble'), ENT_QUOTES, 'UTF-8') ?></button>
							<button type="button" class="oe-btn oe-btn-alt" disabled><?= htmlspecialchars(_t('Create alternative'), ENT_QUOTES, 'UTF-8') ?></button>
							<button type="button" class="oe-btn oe-btn--danger oe-btn-remove" disabled><?= htmlspecialchars(_t('Remove selected'), ENT_QUOTES, 'UTF-8') ?></button>
							<button type="button" class="oe-btn oe-btn--danger oe-btn-clear-all" disabled><?= htmlspecialchars(_t('Clear all'), ENT_QUOTES, 'UTF-8') ?></button>
							<button type="button" class="oe-btn oe-btn-import-sbn"><?= htmlspecialchars(_t('Import from text (SBN MARC)'), ENT_QUOTES, 'UTF-8') ?></button>
						</div>
						<ul class="oe-list" aria-label="<?= htmlspecialchars(_t('Instrumentation items'), ENT_QUOTES, 'UTF-8') ?>"></ul>
						<p class="oe-empty"><?= htmlspecialchars(_t('No instruments added. Click an icon in the palette on the left to start.'), ENT_QUOTES, 'UTF-8') ?></p>
					</main>
					<section class="oe-preview" aria-label="<?= htmlspecialchars(_t('Preview'), ENT_QUOTES, 'UTF-8') ?>">
						<h2><?= htmlspecialchars(_t('Preview'), ENT_QUOTES, 'UTF-8') ?></h2>
						<div class="organico-stage oe-preview-stage"></div>
						<details>
							<summary><?= htmlspecialchars(_t('JSON payload'), ENT_QUOTES, 'UTF-8') ?></summary>
							<textarea class="oe-json" readonly rows="8"></textarea>
							<button type="button" class="oe-btn oe-btn-copy"><?= htmlspecialchars(_t('Copy JSON'), ENT_QUOTES, 'UTF-8') ?></button>
						</details>
					</section>
				</div>
				<div class="oe-modal-backdrop" hidden>
					<div class="oe-modal" role="dialog" aria-modal="true"></div>
				</div>
			</div>
		</div>
	</div>
</div>
<script type="text/javascript">
window.caUI = window.caUI || {};
window.caUI.Organico = window.caUI.Organico || {};
window.caUI.Organico.i18n = window.caUI.Organico.i18n || <?= $i18nJson ?>;
jQuery(document).ready(function() {
	caUI.Organico.initField('<?= $wrapId ?>');
});
</script>
		<?php
		return ob_get_clean();
	}
	# ------------------------------------------------------------------
	/**
	 * Dizionario delle stringhe usate lato JS (organico-editor.js,
	 * organico-stage.js), tradotto tramite lo stesso _t() usato dal template
	 * PHP sopra — cosi' il catalogo di traduzione resta unico (vedi
	 * app/locale/user/it_IT/messages.po). Le chiavi sono il testo inglese
	 * sorgente (stessa convenzione di _t()); i due file JS usano un helper
	 * t(key) che legge da window.caUI.Organico.i18n con fallback sulla
	 * chiave stessa quando il dizionario manca (uso standalone/di test).
	 *
	 * Memorizzato staticamente per richiesta, come buildPaletteJson(): le
	 * traduzioni non cambiano per record, solo per richiesta/locale.
	 *
	 * @return string JSON
	 */
	private function buildI18nJson() : string {
		static $json = null;
		if ($json !== null) {
			return $json;
		}

		$strings = array(
			'Loading MOP vocabulary…',
			'No IFLA MOP term matches the search.',
			'{n} term(s) found',
			' (showing the first {limit} — refine your search)',
			'Search among {n} IFLA MOP terms…',
			'Search instrument in the IFLA MOP vocabulary',
			'alternative {group} · option {option}',
			'Remove',
			'Number of items',
			'Number of performers differs from number of items',
			'Number of performers',
			'Solo',
			'Ad libitum',
			'Overdub',
			'Digital processing',
			'Suffix',
			'Section / part / voice',
			'e.g. I, II, S, A, T, B',
			'Detach from ensemble group',
			'Remove from alternative',
			'-- none --',
			'Other (free text)…',
			'e.g. in B flat',
			'-- select an ensemble --',
			'Instrumental ensembles',
			'Choirs / group voices',
			'Technical groupings (non-IFLA)',
			'Percussion',
			'Continuo',
			'Group into ensemble',
			'{n} instruments selected. The ensemble name is chosen from the IFLA MOP vocabulary, for compatibility (for non-IFLA technical groupings, e.g. "Continuo", use "Technical groupings" or "Other"). The "group number" is optional: use it when the same ensemble has multiple sub-groups (e.g. "Percussion" 1 and 2, one performer each) - the label numbers itself automatically.',
			'Ensemble name (IFLA MOP)',
			'Custom label',
			'e.g. Percussion, Continuo, ...',
			'Group number (optional)',
			'Cancel',
			'Group',
			'Create alternative',
			'Assign the same "Option" number to instruments that should be shown together as a single bundle (e.g. flute+piccolo = option 1); use a different number for the alternative (e.g. trumpet+cornet = option 2).',
			'At least two different options are needed to create an alternative.',
			'Import from text (SBN MARC)',
			'Paste here the already catalogued value of the "Analytical instrumentation (SBN MARC)" field (e.g. "pf-solo,fl,2ob,2fag,2cor,2vl,vla,vlc,cb"). The text is analyzed but not modified; after the preview you can correct each item before saving.',
			'e.g.',
			'Analyze',
			'Import items',
			'How to import',
			'Add to the {n} existing items',
			'Replace the {n} existing items',
			'Clear all',
			'Clear instrumentation',
			'This removes all {n} items in the instrumentation. This action cannot be undone.',
			'No items recognized in the pasted text.',
			'{n} items found',
			', {m} to review (highlighted below).',
			'Copied ✓',
			'Copy JSON',
			'No instrumentation to display.',
			'Preview not available (unexpected error).',
			'No instrumentation',
			'item',
			'items',
			'Instrumentation',
			'{n} instruments or sections',
			'Work instrumentation',
			'or: ',
			'digital',
			"conductor's podium",
			'{label}: open the Wikidata page',
			'{label}: open the term in the IFLA vocabulary',
			'{label}: open the linked term',
			'section/part: {value}',
			'{n} items',
			'{n} performers',
			'solo',
			'ad libitum',
			'overdub',
			'digital processing',
			'(generic family icon)',
			'Wikidata: {uri}',
			'MOP: {uri}',
			'View fullscreen',
			'Exit fullscreen',
		);

		$dict = array();
		foreach ($strings as $s) {
			$dict[$s] = _t($s);
		}
		return $json = json_encode($dict, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
	}
	# ------------------------------------------------------------------
	/**
	 * Palette (griglia rapida) per l'editor: uno strumento per ogni voce di
	 * OrganicoIconDictionary::INSTRUMENTS, raggruppato per famiglia, con la
	 * URI MOP reale quando la label canonica ha un match esatto nel
	 * vocabolario (assets/organico/mop-vocabulary.json).
	 *
	 * Memorizzata staticamente per richiesta: e' un calcolo puro (nessun dato
	 * per-record), rifarlo per ogni riga bundle/ogni chiamata a htmlFormElement()
	 * nella stessa request rileggerebbe inutilmente 200KB di JSON da disco.
	 *
	 * @return string JSON
	 */
	private function buildPaletteJson() : string {
		static $json = null;
		if ($json !== null) {
			return $json;
		}

		$vocabularyPath = __CA_BASE_DIR__.'/assets/organico/mop-vocabulary.json';
		$mopForKey = array();
		if (is_file($vocabularyPath)) {
			$vocabulary = json_decode(file_get_contents($vocabularyPath), true) ?? array();
			foreach ($vocabulary as $term) {
				$norm = OrganicoIconDictionary::normalizeLabel($term['label']);
				$key = OrganicoIconDictionary::ALIASES[$norm] ?? null;
				if ($key !== null && !isset($mopForKey[$key])) {
					$mopForKey[$key] = array(
						'uri' => $term['uri'] ?? null,
						'code' => $term['code'] ?? null,
						'wikidataUri' => $term['wikidataUri'] ?? null,
					);
				}
			}
		}

		$byFamily = array();
		foreach (OrganicoIconDictionary::paletteData() as $entry) {
			$entry['mopUri'] = $mopForKey[$entry['key']]['uri'] ?? null;
			$entry['mopCode'] = $mopForKey[$entry['key']]['code'] ?? null;
			$entry['mopWikidataUri'] = $mopForKey[$entry['key']]['wikidataUri'] ?? null;
			$byFamily[$entry['family']][] = $entry;
		}

		$ordered = array();
		foreach (OrganicoIconDictionary::FAMILY_ORDER as $family) {
			if (!empty($byFamily[$family])) {
				$ordered[] = array(
					'family' => $family,
					'familyLabel' => OrganicoIconDictionary::FAMILY_LABEL[$family] ?? $family,
					'instruments' => $byFamily[$family],
				);
			}
		}

		$json = json_encode($ordered, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
		return $json;
	}
	# ------------------------------------------------------------------
	/**
	 * Base URL per gli asset a livello di repo (es. https://host/assets),
	 * stessa risoluzione usata da AssetLoadManager per i pacchetti non a tema.
	 *
	 * @return string
	 */
	private function getAssetsBaseUrl() : string {
		global $g_request;
		$vs_root = $g_request ? $g_request->getBaseUrlPath() : '';
		return $vs_root.'/assets';
	}
	# ------------------------------------------------------------------
	public function getAvailableSettings($pa_element_info=null) {
		global $_ca_attribute_settings;
		return $_ca_attribute_settings['OrganicoAttributeValue'];
	}
	# ------------------------------------------------------------------
	public function sortField() {
		return null;
	}
	# ------------------------------------------------------------------
	public function queryFields() : ?array {
		return ['value_longtext1'];
	}
	# ------------------------------------------------------------------
	public function getType() {
		return __CA_ATTRIBUTE_VALUE_ORGANICO__;
	}
	# ------------------------------------------------------------------
}
