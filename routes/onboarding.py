"""Onboarding flow blueprint (v5 Step 2).

Implements the D-58 "connect step" — the post-signup screen that lists
supported fitness providers, shows the v5 §A.1 Connected Service consent
disclosure, and offers Connect / Skip-for-now / Continue actions. Step 1
(account-creation acknowledgment) fires at `auth.register`; Step 3 (§A
entry with provider prefill) lands in PR6 (Option D2) — for now Continue
and Skip both drop the athlete on `/profile?tab=athlete` (the existing
v1 athlete-identity surface, closest equivalent to §A entry).

Reuses PR4's `CONNECTION_PROVIDERS` registry and `load_connections`
helper from `routes/profile.py` so the provider roster, status badges,
and connect-URL plumbing stay single-source. The only divergence from
the Connections-tab rendering is the `return_to` path (the OAuth
callback bounces the athlete back to `/onboarding/connect` instead of
`/profile?tab=connections`).
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import get_db
from routes.auth import current_user_id
from routes.profile import CONNECTION_PROVIDERS, load_connections


bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')


# Where to drop the athlete after Continue / Skip. Step 3 (§A entry with
# provider-prefilled values) doesn't exist as a v5 surface yet — D2
# builds the prefill comparison page. Until then the v1 athlete tab on
# /profile is the closest equivalent (collects DoB, sex, height, body
# weight, primary sport — the §A fields). When D2 ships this target
# changes to whatever the prefill comparison page's URL is.
_POST_STEP2_TARGET = '/profile?tab=athlete'


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
    return redirect(_POST_STEP2_TARGET)


@bp.route('/continue', methods=['POST'])
def continue_():
    """Proceed to Step 3 (§A entry). Distinguished from /skip by
    intent — the athlete has chosen to advance after considering
    connections (whether they connected zero, one, or many). Currently
    same redirect target; kept as a separate endpoint so future
    instrumentation can tell the two apart.
    """
    return redirect(_POST_STEP2_TARGET)
