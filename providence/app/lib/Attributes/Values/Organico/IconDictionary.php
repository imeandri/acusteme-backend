<?php

declare(strict_types=1);

/**
 * Vendorizzata da organico-viewer/src/IconDictionary.php (nessuna modifica
 * di logica) — senza namespace, rinominata OrganicoIconDictionary per
 * evitare collisioni nel namespace globale di CollectiveAccess, che non usa
 * i namespace PHP per queste classi. Rigenerare da li' se il dizionario
 * cambia (e rigenerare anche assets/organico/organico-data.js con
 * organico-viewer/build/build-normalizer-js.php).
 *
 * Mappa mezzo di esecuzione -> icona/famiglia/riga di palco.
 *
 * Il matching primario avviene sulla label (IT/EN, normalizzata: minuscolo,
 * senza accenti, singolare) perche' e' il campo sempre presente nei dati
 * CollectiveAccess. mopCodeToKey() e' un aggancio secondario opzionale per
 * quando e' nota la URI del vocabolario IFLA MOP.
 *
 * Per aggiungere uno strumento: 1) disegnare assets/icons/source/<key>.svg
 * (e rigenerare lo sprite con build/build-icons.php), 2) aggiungere una riga
 * a self::INSTRUMENTS, 3) aggiungere gli alias di label a self::ALIASES.
 */
class OrganicoIconDictionary
{
    public const FAMILY_ORDER = [
        'voce', 'archi', 'pizzicati', 'legni', 'ottoni',
        'tastiere', 'percussioni', 'elettronica', 'altro',
    ];

    /** Icona usata quando lo strumento non ha un glifo dedicato. */
    public const FAMILY_FALLBACK_ICON = [
        'voce' => 'voce',
        'archi' => 'violino',
        'pizzicati' => 'chitarra',
        'legni' => 'flauto',
        'ottoni' => 'tromba',
        'tastiere' => 'pianoforte',
        'percussioni' => 'rullante',
        'elettronica' => 'elettronica',
        'altro' => 'sconosciuto',
    ];

    /** Riga di palco (1 = fronte/vicino al direttore ... 5 = fondo) per la modalita' orchestra. */
    public const FAMILY_ROW = [
        'archi' => 1,
        'pizzicati' => 2,
        'legni' => 2,
        'ottoni' => 3,
        'tastiere' => 4,
        'percussioni' => 4,
        'elettronica' => 4,
        'voce' => 5,
        'altro' => 4,
    ];

    /**
     * chiave canonica strumento => [icon, family]
     * "icon" e' il nome file in assets/icons/source (senza estensione) / id simbolo sprite.
     */
    public const INSTRUMENTS = [
        // archi
        'violino' => ['icon' => 'violino', 'family' => 'archi'],
        'viola' => ['icon' => 'viola', 'family' => 'archi'],
        'violoncello' => ['icon' => 'violoncello', 'family' => 'archi'],
        'contrabbasso' => ['icon' => 'contrabbasso', 'family' => 'archi'],
        'arpa' => ['icon' => 'arpa', 'family' => 'archi'],

        // pizzicati
        'chitarra' => ['icon' => 'chitarra', 'family' => 'pizzicati'],
        'chitarra-elettrica' => ['icon' => 'chitarra-elettrica', 'family' => 'pizzicati'],
        'mandolino' => ['icon' => 'mandolino', 'family' => 'pizzicati'],
        'banjo' => ['icon' => 'banjo', 'family' => 'pizzicati'],

        // legni
        'flauto' => ['icon' => 'flauto', 'family' => 'legni'],
        'ottavino' => ['icon' => 'ottavino', 'family' => 'legni'],
        'oboe' => ['icon' => 'oboe', 'family' => 'legni'],
        'corno-inglese' => ['icon' => 'corno-inglese', 'family' => 'legni'],
        'clarinetto' => ['icon' => 'clarinetto', 'family' => 'legni'],
        'clarinetto-basso' => ['icon' => 'clarinetto-basso', 'family' => 'legni'],
        'fagotto' => ['icon' => 'fagotto', 'family' => 'legni'],
        'sassofono' => ['icon' => 'sassofono', 'family' => 'legni'],
        'fisarmonica' => ['icon' => 'fisarmonica', 'family' => 'legni'],

        // ottoni
        'corno' => ['icon' => 'corno', 'family' => 'ottoni'],
        'tromba' => ['icon' => 'tromba', 'family' => 'ottoni'],
        'trombone' => ['icon' => 'trombone', 'family' => 'ottoni'],
        'tuba' => ['icon' => 'tuba', 'family' => 'ottoni'],

        // percussioni
        'timpani' => ['icon' => 'timpani', 'family' => 'percussioni'],
        'rullante' => ['icon' => 'rullante', 'family' => 'percussioni'],
        'grancassa' => ['icon' => 'grancassa', 'family' => 'percussioni'],
        'piatti' => ['icon' => 'piatti', 'family' => 'percussioni'],
        'triangolo' => ['icon' => 'triangolo', 'family' => 'percussioni'],
        'tamburello' => ['icon' => 'tamburello', 'family' => 'percussioni'],
        'xilofono' => ['icon' => 'xilofono', 'family' => 'percussioni'],
        'vibrafono' => ['icon' => 'vibrafono', 'family' => 'percussioni'],
        'glockenspiel' => ['icon' => 'glockenspiel', 'family' => 'percussioni'],
        'tam-tam' => ['icon' => 'tam-tam', 'family' => 'percussioni'],

        // tastiere
        'pianoforte' => ['icon' => 'pianoforte', 'family' => 'tastiere'],
        'organo' => ['icon' => 'organo', 'family' => 'tastiere'],
        'clavicembalo' => ['icon' => 'clavicembalo', 'family' => 'tastiere'],
        'celesta' => ['icon' => 'celesta', 'family' => 'tastiere'],
        'tastiera-synth' => ['icon' => 'tastiera-synth', 'family' => 'tastiere'],

        // voce
        'voce' => ['icon' => 'voce', 'family' => 'voce'],
        'coro' => ['icon' => 'coro', 'family' => 'voce'],

        // elettronica / altro
        'elettronica' => ['icon' => 'elettronica', 'family' => 'elettronica'],
        'sconosciuto' => ['icon' => 'sconosciuto', 'family' => 'altro'],
    ];

    /** chiave canonica => etichetta italiana leggibile, per la palette dell'editor. */
    public const DISPLAY_LABEL = [
        'violino' => 'Violino', 'viola' => 'Viola', 'violoncello' => 'Violoncello',
        'contrabbasso' => 'Contrabbasso', 'arpa' => 'Arpa',
        'chitarra' => 'Chitarra', 'chitarra-elettrica' => 'Chitarra elettrica',
        'mandolino' => 'Mandolino', 'banjo' => 'Banjo',
        'flauto' => 'Flauto', 'ottavino' => 'Ottavino', 'oboe' => 'Oboe',
        'corno-inglese' => 'Corno inglese', 'clarinetto' => 'Clarinetto',
        'clarinetto-basso' => 'Clarinetto basso', 'fagotto' => 'Fagotto',
        'sassofono' => 'Sassofono', 'fisarmonica' => 'Fisarmonica',
        'corno' => 'Corno', 'tromba' => 'Tromba', 'trombone' => 'Trombone', 'tuba' => 'Tuba',
        'timpani' => 'Timpani', 'rullante' => 'Rullante', 'grancassa' => 'Grancassa',
        'piatti' => 'Piatti', 'triangolo' => 'Triangolo', 'tamburello' => 'Tamburello',
        'xilofono' => 'Xilofono', 'vibrafono' => 'Vibrafono', 'glockenspiel' => 'Glockenspiel',
        'tam-tam' => 'Tam-tam',
        'pianoforte' => 'Pianoforte', 'organo' => 'Organo', 'clavicembalo' => 'Clavicembalo',
        'celesta' => 'Celesta', 'tastiera-synth' => 'Tastiera/synth',
        'voce' => 'Voce', 'coro' => 'Coro',
        'elettronica' => 'Elettronica', 'sconosciuto' => 'Altro (generico)',
    ];

    /** Etichetta leggibile per famiglia, per i titoli dei gruppi nella palette. */
    public const FAMILY_LABEL = [
        'archi' => 'Archi', 'pizzicati' => 'Pizzicati', 'legni' => 'Legni', 'ottoni' => 'Ottoni',
        'percussioni' => 'Percussioni', 'tastiere' => 'Tastiere', 'voce' => 'Voce',
        'elettronica' => 'Elettronica', 'altro' => 'Altro',
    ];

    /**
     * Dati per la palette icone dell'editor: una voce per ogni strumento in
     * self::INSTRUMENTS, raggruppabile per famiglia lato client.
     *
     * @return array<int,array{key:string, icon:string, family:string, label:string}>
     */
    public static function paletteData(): array
    {
        $palette = [];
        foreach (self::INSTRUMENTS as $key => $def) {
            $palette[] = [
                'key' => $key,
                'icon' => $def['icon'],
                'family' => $def['family'],
                'label' => self::DISPLAY_LABEL[$key] ?? ucfirst($key),
            ];
        }
        return $palette;
    }

    /**
     * label normalizzata (minuscolo, senza accenti) => chiave canonica in self::INSTRUMENTS
     * Include sinonimi italiano/inglese e forme plurali piu' comuni.
     */
    public const ALIASES = [
        // archi
        'violino' => 'violino', 'violin' => 'violino', 'violini' => 'violino',
        'viola' => 'viola', 'viole' => 'viola',
        'violoncello' => 'violoncello', 'cello' => 'violoncello', 'violoncelli' => 'violoncello', 'cellos' => 'violoncello',
        'contrabbasso' => 'contrabbasso', 'double bass' => 'contrabbasso', 'contrabbassi' => 'contrabbasso', 'basso' => 'contrabbasso',
        'arpa' => 'arpa', 'harp' => 'arpa',

        // pizzicati
        'chitarra' => 'chitarra', 'guitar' => 'chitarra', 'chitarra classica' => 'chitarra', 'chitarra acustica' => 'chitarra',
        'chitarra elettrica' => 'chitarra-elettrica', 'electric guitar' => 'chitarra-elettrica',
        'chitarra basso' => 'chitarra-elettrica', 'basso elettrico' => 'chitarra-elettrica', 'bass guitar' => 'chitarra-elettrica',
        'mandolino' => 'mandolino', 'mandolin' => 'mandolino',
        'banjo' => 'banjo',

        // legni
        'flauto' => 'flauto', 'flute' => 'flauto', 'flauto traverso' => 'flauto',
        'ottavino' => 'ottavino', 'piccolo' => 'ottavino',
        'oboe' => 'oboe',
        'corno inglese' => 'corno-inglese', 'english horn' => 'corno-inglese', 'cor anglais' => 'corno-inglese',
        'clarinetto' => 'clarinetto', 'clarinet' => 'clarinetto', 'clarinet in b flat' => 'clarinetto',
        'clarinetto basso' => 'clarinetto-basso', 'bass clarinet' => 'clarinetto-basso',
        'fagotto' => 'fagotto', 'bassoon' => 'fagotto', 'controfagotto' => 'fagotto', 'contrabassoon' => 'fagotto',
        'sassofono' => 'sassofono', 'saxophone' => 'sassofono', 'sax' => 'sassofono',
        'fisarmonica' => 'fisarmonica', 'accordion' => 'fisarmonica',

        // ottoni
        'corno' => 'corno', 'french horn' => 'corno', 'corni' => 'corno', 'horn' => 'corno',
        'tromba' => 'tromba', 'trumpet' => 'tromba', 'trombe' => 'tromba', 'cornetta' => 'tromba', 'cornet' => 'tromba',
        'trombone' => 'trombone', 'tromboni' => 'trombone',
        'tuba' => 'tuba', 'basso tuba' => 'tuba',

        // percussioni
        'timpani' => 'timpani', 'timpano' => 'timpani', 'timpani drums' => 'timpani',
        'rullante' => 'rullante', 'snare drum' => 'rullante', 'tamburo' => 'rullante', 'tamburo militare' => 'rullante',
        'batteria' => 'rullante', 'drum kit' => 'rullante', 'drums' => 'rullante',
        'grancassa' => 'grancassa', 'bass drum' => 'grancassa',
        'piatti' => 'piatti', 'cymbals' => 'piatti', 'piatto' => 'piatti',
        'triangolo' => 'triangolo', 'triangle' => 'triangolo',
        'tamburello' => 'tamburello', 'tambourine' => 'tamburello', 'tamburello basco' => 'tamburello',
        'xilofono' => 'xilofono', 'xylophone' => 'xilofono',
        'vibrafono' => 'vibrafono', 'vibraphone' => 'vibrafono',
        'glockenspiel' => 'glockenspiel', 'campanelli' => 'glockenspiel',
        'tam-tam' => 'tam-tam', 'tam tam' => 'tam-tam', 'gong' => 'tam-tam',
        'marimba' => 'vibrafono',
        'maracas' => 'sconosciuto',
        'castagnette' => 'sconosciuto', 'castanets' => 'sconosciuto',

        // tastiere
        'pianoforte' => 'pianoforte', 'piano' => 'pianoforte', 'gran coda' => 'pianoforte',
        'organo' => 'organo', 'organ' => 'organo', 'organo a canne' => 'organo', 'organo elettrico' => 'organo',
        'clavicembalo' => 'clavicembalo', 'harpsichord' => 'clavicembalo', 'cembalo' => 'clavicembalo',
        'celesta' => 'celesta', 'celesta keyboard' => 'celesta',
        'tastiera' => 'tastiera-synth', 'synth' => 'tastiera-synth', 'synthesizer' => 'tastiera-synth', 'keyboard' => 'tastiera-synth',

        // voce
        'voce' => 'voce', 'voice' => 'voce', 'canto' => 'voce', 'coro' => 'coro', 'choir' => 'coro', 'chorus' => 'coro',
        'soprano' => 'voce', 'mezzosoprano' => 'voce', 'contralto' => 'voce', 'alto' => 'voce',
        'tenore' => 'voce', 'tenor' => 'voce', 'baritono' => 'voce', 'baritone' => 'voce',
        'basso vocale' => 'voce', 'bass voice' => 'voce', 'voce recitante' => 'voce', 'narratore' => 'voce',
        'basso voce' => 'voce',

        // elettronica
        'elettronica' => 'elettronica', 'electronics' => 'elettronica', 'nastro magnetico' => 'elettronica',
        'tape' => 'elettronica', 'live electronics' => 'elettronica', 'computer' => 'elettronica',
    ];

    /**
     * label generica di sezione/famiglia (non uno strumento specifico) => famiglia.
     * Usata quando il catalogatore indica un gruppo non dettagliato, es. "percussioni:
     * 2 esecutori" senza specificare quali strumenti (convenzione ammessa: il dettaglio
     * per-esecutore, quando c'e', arriva via gruppo_ensemble/numero_gruppo sui singoli
     * mezzi di esecuzione). Restituisce l'icona di fallback della famiglia con
     * matched=false, invece di cadere sul fallback assoluto "altro".
     */
    public const GENERIC_FAMILY_LABELS = [
        'percussioni' => 'percussioni', 'percussione' => 'percussioni', 'percussion' => 'percussioni',
        'percussioni aggiuntive' => 'percussioni', 'batteria di percussioni' => 'percussioni',
        'archi' => 'archi', 'strings' => 'archi',
        'legni' => 'legni', 'woodwinds' => 'legni', 'fiati' => 'legni',
        'ottoni' => 'ottoni', 'brass' => 'ottoni',
        'tastiere' => 'tastiere', 'keyboards' => 'tastiere',
        'voci' => 'voce', 'voices' => 'voce',
    ];

    /**
     * Normalizza una label per il lookup: minuscolo, trim, accenti rimossi,
     * spazi multipli collassati.
     */
    public static function normalizeLabel(string $label): string
    {
        $label = mb_strtolower(trim($label), 'UTF-8');
        $transliterated = @iconv('UTF-8', 'ASCII//TRANSLIT', $label);
        if ($transliterated !== false) {
            $label = $transliterated;
        }
        $label = preg_replace('/[^a-z0-9\s\-]/', '', $label) ?? $label;
        $label = preg_replace('/\s+/', ' ', $label) ?? $label;
        return trim($label);
    }

    /**
     * Risolve una label libera (es. "Flauto", "clarinetti", "Trumpet in Bb")
     * in ['icon' => ..., 'family' => ..., 'matched' => bool].
     * "matched" e' false quando si e' usato il fallback di famiglia/assoluto.
     */
    public static function resolve(string $label, ?string $mopUri = null): array
    {
        $norm = self::normalizeLabel($label);

        if (isset(self::ALIASES[$norm])) {
            $key = self::ALIASES[$norm];
            return self::INSTRUMENTS[$key] + ['matched' => true];
        }

        // fallback: prova a matchare la prima parola significativa (es. "corno in fa" -> "corno")
        $firstWord = strtok($norm, ' -');
        if ($firstWord !== false && isset(self::ALIASES[$firstWord])) {
            $key = self::ALIASES[$firstWord];
            return self::INSTRUMENTS[$key] + ['matched' => true];
        }

        // ultimo tentativo: cerca l'alias come sottostringa della label (o viceversa)
        foreach (self::ALIASES as $aliasLabel => $key) {
            if ($norm !== '' && (str_contains($norm, $aliasLabel) || str_contains($aliasLabel, $norm))) {
                return self::INSTRUMENTS[$key] + ['matched' => true];
            }
        }

        // label generica di famiglia (es. "percussioni" senza strumento specifico):
        // meglio l'icona generica della famiglia giusta che il fallback assoluto.
        if (isset(self::GENERIC_FAMILY_LABELS[$norm])) {
            $family = self::GENERIC_FAMILY_LABELS[$norm];
            return [
                'icon' => self::FAMILY_FALLBACK_ICON[$family],
                'family' => $family,
                'matched' => false,
            ];
        }

        return [
            'icon' => self::FAMILY_FALLBACK_ICON['altro'],
            'family' => 'altro',
            'matched' => false,
        ];
    }

    public static function familyRow(string $family): int
    {
        return self::FAMILY_ROW[$family] ?? 4;
    }

    public static function familyOrderIndex(string $family): int
    {
        $index = array_search($family, self::FAMILY_ORDER, true);
        return $index === false ? count(self::FAMILY_ORDER) : $index;
    }
}
