"""Gym chain registry (D-59 §4).

Static seed for chain detection. Loaded at import time; no DB table.

Detection algorithm (D-59 §4.2): lowercase the Mapbox `text` field; walk
GYM_CHAINS in declaration order; first entry whose any `name_patterns`
substring is in the lowercased text wins. Patterns are case-insensitive
`in`-comparisons and intentionally lax (`'planet fit'` matches both
"Planet Fitness" and "Planet Fitness Express").

`category` values are the D-60 §3 taxonomy. Only `commercial_chain_gym`
and `climbing_gym_chain` are valid here (the other taxonomy values are
not chain-derived).

When the registry needs an entry not listed, add it in declaration order
intentionally — more specific patterns first to avoid the lax-matching
problem (e.g., `'lifetime athletic'` before `'life time'` if both were
patterns for the same chain). Patches land alongside ops PRs; no
versioning ceremony for additions.
"""

GYM_CHAINS: tuple[dict, ...] = (
    # ── Commercial chain gyms (US-focused; international by exception) ──
    {
        'chain_id': 'planet_fitness',
        'canonical_name': 'Planet Fitness',
        'name_patterns': ('planet fitness', 'planet fit', 'pf #'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'la_fitness',
        'canonical_name': 'LA Fitness',
        'name_patterns': ('la fitness', 'la-fitness'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': '24_hour_fitness',
        'canonical_name': '24 Hour Fitness',
        'name_patterns': ('24 hour fitness', '24-hour fitness', '24hr fitness'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'anytime_fitness',
        'canonical_name': 'Anytime Fitness',
        'name_patterns': ('anytime fitness',),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'golds_gym',
        'canonical_name': "Gold's Gym",
        'name_patterns': ("gold's gym", 'golds gym'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'crunch_fitness',
        'canonical_name': 'Crunch Fitness',
        'name_patterns': ('crunch fitness', 'crunch gym'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'equinox',
        'canonical_name': 'Equinox',
        'name_patterns': ('equinox fitness', 'equinox gym', 'equinox sports club'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'life_time',
        'canonical_name': 'Life Time',
        'name_patterns': ('lifetime fitness', 'life time fitness',
                          'lifetime athletic', 'life time athletic'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'ymca',
        'canonical_name': 'YMCA',
        'name_patterns': ('ymca',),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'orangetheory',
        'canonical_name': 'Orangetheory Fitness',
        'name_patterns': ('orangetheory', 'orange theory'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'f45',
        'canonical_name': 'F45 Training',
        'name_patterns': ('f45 training', 'f45 gym'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'snap_fitness',
        'canonical_name': 'Snap Fitness',
        'name_patterns': ('snap fitness',),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'ufc_gym',
        'canonical_name': 'UFC Gym',
        'name_patterns': ('ufc gym',),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'retro_fitness',
        'canonical_name': 'Retro Fitness',
        'name_patterns': ('retro fitness',),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'blink_fitness',
        'canonical_name': 'Blink Fitness',
        'name_patterns': ('blink fitness',),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'chuze_fitness',
        'canonical_name': 'Chuze Fitness',
        'name_patterns': ('chuze fitness', 'chuze gym'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'eos_fitness',
        'canonical_name': 'EoS Fitness',
        'name_patterns': ('eos fitness', 'eōs fitness'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'vasa_fitness',
        'canonical_name': 'VASA Fitness',
        'name_patterns': ('vasa fitness',),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'esporta_fitness',
        'canonical_name': 'Esporta Fitness',
        'name_patterns': ('esporta fitness', 'esporta gym'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'pure_gym',
        'canonical_name': 'PureGym',
        'name_patterns': ('puregym', 'pure gym'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'basic_fit',
        'canonical_name': 'Basic-Fit',
        'name_patterns': ('basic-fit', 'basic fit'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'soulcycle',
        'canonical_name': 'SoulCycle',
        'name_patterns': ('soulcycle', 'soul cycle'),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'barrys',
        'canonical_name': "Barry's",
        'name_patterns': ("barry's bootcamp", 'barrys bootcamp', "barry's gym"),
        'category': 'commercial_chain_gym',
    },
    {
        'chain_id': 'cyclebar',
        'canonical_name': 'CycleBar',
        'name_patterns': ('cyclebar', 'cycle bar studio'),
        'category': 'commercial_chain_gym',
    },
    # ── Climbing-gym chains (D-60 §3 `climbing_gym_chain`) ──
    {
        'chain_id': 'movement',
        'canonical_name': 'Movement',
        'name_patterns': ('movement climbing', 'movement gym', 'movement bouldering'),
        'category': 'climbing_gym_chain',
    },
    {
        'chain_id': 'sender_one',
        'canonical_name': 'Sender One',
        'name_patterns': ('sender one', 'sender 1'),
        'category': 'climbing_gym_chain',
    },
    {
        'chain_id': 'touchstone',
        'canonical_name': 'Touchstone Climbing',
        'name_patterns': ('touchstone climbing', 'touchstone bouldering'),
        'category': 'climbing_gym_chain',
    },
    {
        'chain_id': 'brooklyn_boulders',
        'canonical_name': 'Brooklyn Boulders',
        'name_patterns': ('brooklyn boulders',),
        'category': 'climbing_gym_chain',
    },
    {
        'chain_id': 'bouldering_project',
        'canonical_name': 'Bouldering Project',
        'name_patterns': ('bouldering project',),
        'category': 'climbing_gym_chain',
    },
    {
        'chain_id': 'earth_treks',
        'canonical_name': 'Earth Treks',
        'name_patterns': ('earth treks',),
        'category': 'climbing_gym_chain',
    },
    {
        'chain_id': 'metrorock',
        'canonical_name': 'MetroRock',
        'name_patterns': ('metrorock', 'metro rock climbing'),
        'category': 'climbing_gym_chain',
    },
    {
        'chain_id': 'vertical_world',
        'canonical_name': 'Vertical World',
        'name_patterns': ('vertical world',),
        'category': 'climbing_gym_chain',
    },
)


def detect_chain(mapbox_text: str) -> dict | None:
    """Return the first matching GYM_CHAINS entry for a Mapbox `text` value,
    or None when no entry matches.

    D-59 §4.2 step 2. Match is case-insensitive substring containment.
    Callers should fall through to Mapbox `properties.category` inspection
    (§4.2 step 3) for the no-match path.
    """
    if not mapbox_text:
        return None
    lowered = mapbox_text.lower()
    for chain in GYM_CHAINS:
        for pattern in chain['name_patterns']:
            if pattern in lowered:
                return chain
    return None
