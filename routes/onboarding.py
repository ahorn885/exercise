"""Onboarding flow blueprint (v5 Steps 2 + 3a).

Step 2 — D-58 "connect step" — the post-signup screen that lists
supported fitness providers, shows the v5 §A.1 Connected Service consent
disclosure, and offers Connect / Skip-for-now / Continue actions.

Step 3a — D-58 prefill comparison page (PR7 / D2a) — the read-side of
the v5 §A.2 provider-prefill UX. Renders per-field cards comparing the
athlete's currently-stored value against each connected provider's
extractor output. PR7 ships read-only with stub action buttons; D2b
wires write-side opt-in (`[Use provider]`) + the `manual_override` flip.

Step 1 (account-creation acknowledgment) fires at `auth.register`.
Step 3 proper (§A profile-form entry) is the existing v1 surface at
`/profile?tab=athlete`. After PR7, Continue from `/onboarding/connect`
lands on `/onboarding/prefill` instead of jumping straight to the
profile form.

Reuses PR4's `CONNECTION_PROVIDERS` registry and `load_connections`
helper from `routes/profile.py` so the provider roster, status badges,
and connect-URL plumbing stay single-source. The only divergence from
the Connections-tab rendering is the `return_to` path (the OAuth
callback bounces the athlete back to `/onboarding/connect` instead of
`/profile?tab=connections`).
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash

import database
from database import get_db
from athlete import get_athlete_profile
from routes.auth import current_user_id
from routes.profile import CONNECTION_PROVIDERS, load_connections
from routes.profile_fields import KNOWN_PROFILE_FIELDS, provider_label


bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')


# Where to drop the athlete after Continue / Skip on Step 2. PR7 flips
# Continue to the new prefill comparison page; Skip still jumps straight
# to the profile form since an athlete who skipped connecting providers
# has nothing to compare against. The post-prefill target stays
# `/profile?tab=athlete` (the v1 §A entry surface).
_POST_STEP2_CONTINUE_TARGET = '/onboarding/prefill'
_POST_STEP2_SKIP_TARGET = '/profile?tab=athlete'
_POST_STEP3_TARGET = '/profile?tab=athlete'

# Back-compat alias for the connect template (passes the value through
# to the Skip/Continue button copy via Jinja). Pre-PR7 callers expected
# a single target; the template now reads it as the Continue label hint
# only, since Skip has its own redirect target.
_POST_STEP2_TARGET = _POST_STEP2_CONTINUE_TARGET


@bp.route('/connect', methods=['GET'])
def connect():
    """Render the Step 2 connect screen.

    Lists every provider in `CONNECTION_PROVIDERS` with current status,
    the v5 §A.1 Connected Service consent disclosure (collapsible), and
    Connect buttons that bounce through the provider's `oauth_start`
    with `return_to=/onboarding/connect` so the post-OAuth callback
    lands the athlete back here with `?<slug>_connected=1` (success) or
    `?<slug>_oauth_error=…` / `?<slug>_register_error=1` (failure).
    """
    db = get_db()
    uid = current_user_id()

    return_to = url_for('onboarding.connect')
    connections = load_connections(db, uid, return_to=return_to)

    # Post-OAuth-callback flag surfacing. Same pattern as profile.edit
    # (PR4) — the first hit wins; multi-provider races on the same
    # render are rare-enough-to-ignore. The label drives the success /
    # error alert copy; the slug drives nothing (kept for parity in
    # case the template wants to highlight the specific card later).
    just_connected_label = None
    oauth_error_label = None
    for slug, label, _endpoint in CONNECTION_PROVIDERS:
        if just_connected_label is None and request.args.get(f'{slug}_connected') == '1':
            just_connected_label = label
        if oauth_error_label is None and (
            request.args.get(f'{slug}_oauth_error')
            or request.args.get(f'{slug}_register_error')
        ):
            oauth_error_label = label

    connected_count = sum(1 for c in connections if c['is_connected'])

    return render_template(
        'onboarding/connect.html',
        connections=connections,
        connected_count=connected_count,
        just_connected_label=just_connected_label,
        oauth_error_label=oauth_error_label,
        post_step2_target=_POST_STEP2_TARGET,
    )


@bp.route('/skip', methods=['POST'])
def skip():
    """Skip Step 2 with no providers connected.

    No DB write — the v5 §A.2.4 14-day connect-provider nudge (Option E
    in the PR4 §5.1 menu, not yet implemented) keys off `provider_auth`
    rowcount + account age, not off a skip event. If a future PR wants
    to differentiate "skipped explicitly" from "never visited the page"
    it can add an `account_nudges` row with `nudge_type='step2_skipped'`
    here. For PR5 the skip is a pure redirect.
    """
    flash(
        "You can connect providers any time from Profile → Connections.",
        'info',
    )
    return redirect(_POST_STEP2_SKIP_TARGET)


@bp.route('/continue', methods=['POST'])
def continue_():
    """Proceed to Step 3a (prefill review). PR7 flips this target from
    the bare profile form to `/onboarding/prefill` so athletes who
    connected at least one provider see the comparison page first.
    Athletes who connected zero providers also land here — the prefill
    page renders an honest empty state and offers a one-click pass
    through to the profile form.
    """
    return redirect(_POST_STEP2_CONTINUE_TARGET)


@bp.route('/prefill', methods=['GET'])
def prefill():
    """Render the v5 §A.2 per-field prefill comparison page (Step 3a).

    For each `KNOWN_PROFILE_FIELDS` entry, resolves three things:

      - Currently stored value from `athlete_profile`.
      - Existing provenance row (if any) from
        `athlete_profile_field_provenance` — surfaces the per-field
        `source` tag in the UI.
      - Per-connected-provider candidate values from
        `routes.profile_extractors` (gated by `provider_auth.status =
        active`; disconnected providers don't surface candidates).

    PR7 ships read-only — the per-card `[Use provider]` / `[Keep current]`
    buttons render as disabled placeholders with explanatory copy.
    D2b wires the write path + the `'self_report'` → `'manual_override'`
    flip when an athlete edits a previously-prefilled value.

    PG-only provenance read mirrors `routes/profile.py:_record_self_report_provenance` —
    SQLite dev returns no rows since the table is in `_PG_MIGRATIONS` only.
    """
    db = get_db()
    uid = current_user_id()

    profile = get_athlete_profile(db, uid) or {}

    connections = load_connections(db, uid)
    connected_slugs = {c['slug'] for c in connections if c['is_connected']}

    provenance_by_field = {}
    if database._is_postgres():
        rows = db.execute(
            'SELECT field_name, source, last_updated_at '
            'FROM athlete_profile_field_provenance WHERE user_id = ?',
            (uid,),
        ).fetchall()
        provenance_by_field = {r['field_name']: dict(r) for r in rows}

    fields = []
    for field_def in KNOWN_PROFILE_FIELDS:
        name = field_def['name']
        current_value = profile.get(name)

        candidates = []
        for slug, extractor in field_def['extractors'].items():
            if slug not in connected_slugs:
                continue
            value, synced_at, note = extractor(db, uid)
            if value is None:
                continue
            candidates.append({
                'provider_slug': slug,
                'provider_label': provider_label(slug),
                'value': value,
                'synced_at': synced_at,
                'note': note,
            })

        # Most-recent-wins ordering per v5 §A.2.2 step 3. None values
        # sort to the end so present-but-undated candidates still
        # render below dated ones. Stable sort preserves declaration
        # order when synced_at ties (rare in practice).
        candidates.sort(
            key=lambda c: c['synced_at'] or '',
            reverse=True,
        )

        fields.append({
            'name': name,
            'label': field_def['label'],
            'unit': field_def['unit'],
            'current_value': current_value,
            'provenance': provenance_by_field.get(name),
            'candidates': candidates,
        })

    fields_with_candidates = sum(1 for f in fields if f['candidates'])

    return render_template(
        'onboarding/prefill.html',
        fields=fields,
        fields_with_candidates=fields_with_candidates,
        connected_count=sum(1 for c in connections if c['is_connected']),
        post_step3_target=_POST_STEP3_TARGET,
    )
