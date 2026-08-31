<?php

require_once(__CA_MODELS_DIR__ . "/ca_objects.php");

class prepopulatePHPPlugin extends BaseApplicationPlugin {
    public function __construct() {
        parent::__construct();
    }

    public function checkStatus() {
        return [
            'description' => "Plugin Titolo Uniforme + no punto finale",
            'errors'      => [],
            'warnings'    => [],
            'available'   => true
        ];
    }

    public function hookSaveItem(&$pa_params) {
        try {
            global $g_ui_locale_id;

            $item     = $pa_params['instance'];
            $vs_table = get_class($item);
            $type     = $item->getWithTemplate("^{$vs_table}.type_id");
            $id       = $item->get("{$vs_table}.object_id");

            if ($vs_table !== 'ca_objects'
                || !in_array($type, ['Work','Works','Opera','Opere'], true)
            ) {
				return $pa_params;
            }

            // Percorso relativo alla cartella del plugin: portabile fra
            // l'istanza di produzione e installazioni CA locali di test.
            $logFile = __DIR__ . '/prepopulate_debug.log';
            $vt      = new ca_objects($id);
            $vt->setMode(ACCESS_WRITE);

            // 1) Fetch raw + worktype
            $rec = [
                'ordTit'       => $vt->getWithTemplate("^ca_objects.ord_tit_CN.ord_tit_ME"),
                'numOpera'     => $vt->getWithTemplate("^ca_objects.numbers_CN.numero_dopera"),
                'numOrdine'    => $vt->getWithTemplate("^ca_objects.numbers_CN.numero_ordine"),
                'numCatalogo'  => $vt->getWithTemplate("^ca_objects.numbers_CN.numeri_catalogo_tematico"),
                'orgSintetico' => $vt->getWithTemplate("^ca_objects.instrumentation_CN.organico_sintetico"),
                'orgAnalitico' => $vt->getWithTemplate("^ca_objects.instrumentation_CN.organico_analitico"),
                'tonalRaw'     => $vt->getWithTemplate("^ca_objects.tonality_ME"),
                'nonSig'       => $vt->getWithTemplate("^ca_objects.ord_tit_CN.nonsignificanttitle_ME"),
                'qual1'        => $vt->getWithTemplate("^ca_objects.ord_tit_CN.qualifier1_ME"),
                'qual2'        => $vt->getWithTemplate("^ca_objects.ord_tit_CN.qualifier2_ME"),
                'worktype'     => $vt->getWithTemplate("^ca_objects.worktype_ME")
            ];
            file_put_contents(
                $logFile,
                date('Y-m-d H:i:s')." | DEBUG_FIELDS -> ".
                json_encode($rec, JSON_UNESCAPED_UNICODE)."\n",
                FILE_APPEND
            );

            // 2) Build title (senza punto finale)
            $title = $this->buildTitoloUniforme($vt, $rec);
            file_put_contents(
                $logFile,
                date('Y-m-d H:i:s')." | DEBUG_TITLE -> $title\n",
                FILE_APPEND
            );

            // 3a) remove old preferred, commit
            $vt->removeAllLabels(__CA_LABEL_TYPE_PREFERRED__);
            $vt->update();

            // 3b) add new preferred label, commit
            $vt->addLabel(
                ['name' => $title],
                $g_ui_locale_id,
                __CA_LABEL_TYPE_PREFERRED__,
                true
            );
            $vt->update(['force'=>true,'hooks'=>false]);

            // 4) confirm
            file_put_contents(
                $logFile,
                date('Y-m-d H:i:s')." | DEBUG_LABEL_SAVED -> ".
                json_encode($vt->getLabels(__CA_LABEL_TYPE_PREFERRED__), JSON_UNESCAPED_UNICODE)."\n",
                FILE_APPEND
            );

        } catch (\Throwable $e) {
            error_log("prepopulatePHPPlugin error: ".$e->getMessage());
        }
		return $pa_params;
    }

    // CollectiveAccess may return either the localized label or the list value.
    protected function isChecked($raw) {
        return in_array(
            mb_strtolower(trim((string) $raw), 'UTF-8'),
            ['yes', 'sì', 'si', '1', 'true'],
            true
        );
    }

    protected function buildTitoloUniforme(ca_objects $vt, array $rec) {
        // 1) Forma
        $ft = ltrim($rec['ordTit'], "* ");
        if (strpos($ft, ';') !== false) {
            list($ft) = explode(';', $ft);
        }
        $forma = trim($ft);

        // Titolo Uniforme/Capitolo_2: un titolo significativo identifica
        // l'opera da solo; solo i titoli generici/non significativi vanno
        // integrati con organico, numerazione, catalogo tematico e tonalità.
        $nonSignificant = $this->isChecked($rec['nonSig']);

        $solo = $ensemble = $tonal = $num = '';
        if ($nonSignificant) {
            $dict = $this->loadDictionaries();

            // 2-3) Solisti + mezzo di esecuzione generale (organico analitico)
            $org = $this->parseOrganicoAnalitico($rec['orgAnalitico'], $dict['imap'], $dict['emap']);
            $solo = $org['solo'];

            // Ensemble (organico sintetico: parole collettive tipo "orch", "coro", "banda")
            $ensembleTokens = $this->parseEnsembleTokens($rec['orgSintetico'], $dict['emap']);
            $ensemble = implode(', ', array_unique(array_merge($org['mezzo'], $ensembleTokens)));

            // 4) Tonalità (minuscola; cap.2 la omette solo per i titoli significativi)
            $tonal = $this->resolveTonalita($rec['tonalRaw'], $dict['tmap']);

            // 5) Numero
            $num = !empty($rec['numOpera'])
                 ? $rec['numOpera']
                 : (!empty($rec['numOrdine']) ? 'n. '.$rec['numOrdine'] : '');
        }

        // 6) Base elements
        $elts = array_filter(
            [$forma, $solo, $ensemble, $num, $nonSignificant ? $rec['numCatalogo'] : '', $tonal],
            function($v){ return trim($v) !== ''; }
        );
        $title = implode(', ', $elts);

        // 7) qualifier1 (tipologia dell'opera): il flag "Non usare qualificatore 1"
        // sopprime il qualificatore quando attivo (vedi isChecked()).
        if (!$this->isChecked($rec['qual1'])
            && trim($rec['worktype']) !== ''
            && mb_strtolower($rec['worktype'], 'UTF-8') !== 'not set'
        ) {
            $escaped = htmlspecialchars(lcfirst($rec['worktype']), ENT_QUOTES, 'UTF-8');
            $title .= ' &lt;'.$escaped.'&gt;';
        }

        // 8) qualifier2 (autori): il flag "Non usare qualificatore 2" sopprime
        // il qualificatore quando attivo (vedi isChecked()).
        if (!$this->isChecked($rec['qual2'])) {
            $tmpl = "<unit relativeTo='ca_entities'>"
                  . "^ca_entities.preferred_labels, ^ca_entities.single_birth_date_ME-"
                  . "<ifdef code='ca_entities.single_date_death_ME'>^ca_entities.single_date_death_ME</ifdef>"
                  . "<ifnotdef code='ca_entities.single_date_death_ME'>...</ifnotdef>"
                  . "</unit>";
            $rawAuth = trim($vt->getWithTemplate($tmpl));
            $rawAuth = preg_replace('/\b\d{1,2}\s+\p{L}+\s+(\d{4})/u', '$1', $rawAuth);
            $authors = preg_split('/;\s*/', $rawAuth);
            $fmt = [];
            foreach ($authors as $a) {
                list($full, $dt) = array_pad(array_map('trim', explode(',', $a, 2)), 2, '');
                $hasY = preg_match('/\d{4}/', $dt);
                $parts = preg_split('/\s+/', $full);
                $sur   = array_pop($parts);
                $giv   = implode(' ', $parts);
                $lbl   = $sur . ($giv ? ', ' . $giv : '');
                if ($hasY) {
                    $lbl .= ', ' . $dt;
                }
                $fmt[] = $lbl;
            }
            // Filtra le voci vuote: senza autori collegati $rawAuth è '' e
            // produrrebbe una coppia di parentesi vuote (visto in produzione
            // sull'oggetto 1772: titolo salvato letteralmente come "()").
            $fmt = array_values(array_filter($fmt, function ($v) { return trim($v) !== ''; }));
            if ($fmt) {
                $title .= ' (' . implode('; ', $fmt) . ')';
            }
        }

        // 9) normalize spaces + trim
        $title = preg_replace('/\s+/', ' ', trim($title));

        // **Niente più “.” alla fine**
        return $title;
    }

    // Dizionario SBN strumenti/ensemble/tonalità (vedi dictionaries.php). Il
    // 'pmap' del file NON viene usato: è generato automaticamente e contiene
    // plurali errati/con parentesi quadre residue ("[a otto manii]"); i plurali
    // si calcolano invece con pluralizeIt().
    protected function loadDictionaries() {
        static $dict = null;
        if ($dict === null) {
            $path = __DIR__ . '/dictionaries.php';
            $dict = is_file($path) ? require $path : [];
            $dict += ['imap' => [], 'emap' => [], 'tmap' => []];
        }
        return $dict;
    }

    // Split su virgola al livello superiore, ignorando le virgole dentro
    // parentesi (es. "orch(vl,vla,vlc)" resta un solo token).
    protected function splitTopLevel($s) {
        $parts = [];
        $depth = 0;
        $buf = '';
        foreach (str_split((string) $s) as $ch) {
            if ($ch === '(') { $depth++; }
            if ($ch === ')') { $depth = max(0, $depth - 1); }
            if ($ch === ',' && $depth === 0) {
                $parts[] = $buf;
                $buf = '';
                continue;
            }
            $buf .= $ch;
        }
        $parts[] = $buf;
        return array_values(array_filter(array_map('trim', $parts), function ($p) { return $p !== ''; }));
    }

    // Le indicazioni "oppure" descrivono organici alternativi: per generare
    // un'unica stringa di titolo uniforme si assume la prima alternativa.
    protected function firstAlternative($s) {
        $s = preg_split('/\boppure\b/i', (string) $s)[0];
        return trim($s, " ,");
    }

    // Toglie un indice di leggio/desk finale (cifre arabe o numerale romano
    // I/II/III/IV), es. "vl1" / "vlI" -> "vl", "vlc-solo3" -> "vlc-solo".
    protected function stripDeskIndex($code) {
        return rtrim(preg_replace('/-?(?:[1-9][0-9]*|I{1,3}|IV)$/', '', $code), '-');
    }

    // Pluralizzazione italiana a regola (o->i, a->e, e->i); i prestiti stranieri
    // invariabili noti restano cosi' come sono. Non e' un elenco esaustivo:
    // per un mezzo non riconosciuto qui si preferisce non alterare la parola
    // piuttosto che rischiare un plurale sbagliato.
    protected function pluralizeIt($label) {
        static $invariant = ['banjo', 'ukulele', 'kazoo', 'gamelan', 'tape', 'sax', 'tabla', 'sitar', 'oud', 'didgeridoo', 'synth', 'sampler', 'laptop'];
        $lc = mb_strtolower($label, 'UTF-8');
        foreach ($invariant as $w) {
            if ($lc === $w || mb_substr($lc, -mb_strlen($w) - 1, null, 'UTF-8') === ' ' . $w) {
                return $label;
            }
        }
        $last = mb_strtolower(mb_substr($label, -1, 1, 'UTF-8'), 'UTF-8');
        $stem = mb_substr($label, 0, -1, 'UTF-8');
        switch ($last) {
            case 'o': return $stem . 'i';
            case 'a': return $stem . 'e';
            case 'e': return $stem . 'i';
            default:  return $label;
        }
    }

    // Risolve un codice organico (gia' privato dell'indice di leggio) nella
    // relativa etichetta italiana, scomponendo eventuali composti
    // "base-modificatore" (es. "cl-b" = clarinetto + basso -> "clarinetto basso").
    protected function resolveMezzoCode($code, array $imap, array $emap = []) {
        $lc = strtolower(trim((string) $code, " \t-"));
        if ($lc === '') { return null; }
        if (isset($imap[$lc])) { return $imap[$lc]; }
        if (isset($emap[$lc])) { return $emap[$lc]; }
        if (preg_match('/^([a-z]+)-([a-z]+)$/', $lc, $m) && isset($imap[$m[1]]) && isset($imap['-' . $m[2]])) {
            return trim($imap[$m[1]] . ' ' . $imap['-' . $m[2]]);
        }
        return null;
    }

    // Organico analitico -> frase solisti + lista mezzi generali con numerale
    // arabo quando presenti piu' esecutori dello stesso strumento (cap.2:
    // "Quartetti, 2 clarinetti, 2 violoncelli"). I sotto-gruppi annidati fra
    // parentesi (alternanze/cluster complessi) sono fuori scope e vengono
    // ignorati piuttosto che interpretati a casaccio.
    protected function parseOrganicoAnalitico($raw, array $imap, array $emap) {
        $tokens = $this->splitTopLevel($this->firstAlternative($raw));
        $hasSlashAlternation = strpos((string) $raw, '/') !== false;

        $soloCounts = []; $soloOrder = [];
        $genCounts  = []; $genOrder  = [];

        foreach ($tokens as $tok) {
            // Gruppo annidato, es. "orch(vl,vla,vlc)": si tiene solo il prefisso
            // ("orch") e si scarta il dettaglio fra parentesi, fuori scope qui.
            if (($parenPos = strpos($tok, '(')) !== false) {
                $tok = substr($tok, 0, $parenPos);
            }
            $tok = trim(explode('/', $tok)[0]);
            if ($tok === '') { continue; }

            $isSolo = stripos($tok, 'solo') !== false;
            $count = 1;
            if (preg_match('/^(\d+)\s*(.+)$/', $tok, $m)) {
                $count = (int) $m[1];
                $tok = $m[2];
            }
            $base = $this->stripDeskIndex(trim(str_ireplace(['-solo', 'solo'], '', $tok), " \t-"));
            if ($base === '') { continue; }

            if ($isSolo) {
                $soloCounts[$base] = ($soloCounts[$base] ?? 0) + $count;
                if (!in_array($base, $soloOrder, true)) { $soloOrder[] = $base; }
            } else {
                $genCounts[$base] = ($genCounts[$base] ?? 0) + $count;
                if (!in_array($base, $genOrder, true)) { $genOrder[] = $base; }
            }
        }

        // Frase solisti: stessa formulazione della versione precedente.
        $solNames = [];
        foreach ($soloOrder as $base) {
            $label = $this->resolveMezzoCode($base, $imap, $emap) ?? $base;
            for ($i = 0; $i < $soloCounts[$base]; $i++) { $solNames[] = $label; }
        }
        $n = count($solNames);
        $u = array_values(array_unique($solNames));
        $solo = '';
        if ($n === 1) {
            $solo = $u[0] . ' solo';
        } elseif ($n > 1 && count($u) === 1) {
            $solo = "$n " . $this->pluralizeIt($u[0]) . ' soli';
        } elseif (count($u) === 2) {
            $solo = $u[0] . ($hasSlashAlternation ? ' o ' : ' e ') . $u[1] . ' soli';
        } elseif ($n > 2) {
            $last = array_pop($u);
            $solo = implode(', ', $u) . ' e ' . $last . ' soli';
        }

        // Mezzo di esecuzione generale, con numerale arabo se >1 esecutore.
        $mezzo = [];
        foreach ($genOrder as $base) {
            $label = $this->resolveMezzoCode($base, $imap, $emap) ?? $base;
            $count = $genCounts[$base];
            $mezzo[] = $count > 1 ? ($count . ' ' . $this->pluralizeIt($label)) : $label;
        }

        return ['solo' => $solo, 'mezzo' => $mezzo];
    }

    // Organico sintetico -> nomi di ensemble/formazioni collettive (orchestra,
    // coro, banda...): parole collettive, non si contano.
    protected function parseEnsembleTokens($raw, array $emap) {
        $out = [];
        foreach ($this->splitTopLevel($this->firstAlternative($raw)) as $tok) {
            if (($parenPos = strpos($tok, '(')) !== false) {
                $tok = substr($tok, 0, $parenPos);
            }
            $tok = trim(explode('/', $tok)[0]);
            $lc = strtolower($tok);
            if (isset($emap[$lc]) && !in_array($emap[$lc], $out, true)) {
                $out[] = $emap[$lc];
            }
        }
        return $out;
    }

    // Estrae il codice tonalità dall'ultimo frammento "#codice" (URI IFLA,
    // es. ".../key#cxm") e lo risolve nel dizionario tonalità (minuscolo, cap.2).
    // Il vecchio pattern catturava solo una lettera + un eventuale "#" e non
    // riconosceva codici composti come "cxm" (do diesis minore): con più
    // occorrenze nel campo (valori multipli separati da ';') si usa l'ultima.
    protected function resolveTonalita($raw, array $tmap) {
        $tmapLc = array_change_key_case($tmap, CASE_LOWER);
        if (preg_match_all('/#([A-Za-z0-9]+)/', (string) $raw, $mm) && !empty($mm[1])) {
            $code = strtolower(end($mm[1]));
            return $tmapLc[$code] ?? $code;
        }
        if (preg_match('/\(([^)]+)\)/', (string) $raw, $m2)) {
            return mb_strtolower(trim($m2[1]), 'UTF-8');
        }
        return '';
    }

    static public function getRoleActionList() {
        return [];
    }
}
