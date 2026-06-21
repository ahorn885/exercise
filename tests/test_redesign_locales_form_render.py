"""Render smoke tests for the redesign Locations forms (Phase 6 secondary
forms): the equipment editor (`locales/form.html`, all three modes) and the
add-location flow (`locales/new.html`, all three states).

The `edit_profile` / `new_locale` routes run intricate query paths (shared
profiles, overrides, terrain, Mapbox), so rather than mock all of that we
render the templates directly through the booted app's Jinja env inside a
request context — this still exercises the full new shell (base.html, sidebar,
topbar, context processors) and catches template/CSP regressions.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import flask  # noqa: E402
import app as _appmod  # noqa: E402


def _render(template, **ctx):
    with _appmod.app.test_request_context('/'):
        flask.g.current_user_row = {'id': 1, 'username': 'owner',
                                    'display_name': 'Owner'}
        return flask.render_template(template, **ctx)


# ─── locales/form.html ──────────────────────────────────────────────────

_EQUIP = [('Free weights', [('db', 'Dumbbells'), ('bb', 'Barbell')])]
_TERRAIN = [{'id': 'trail', 'label': 'Trail', 'description': 'Dirt singletrack.'},
            {'id': 'road', 'label': 'Road'}]


def _form_ctx(**kw):
    base = dict(
        mode='legacy', locale='home',
        profile={'locale_name': None, 'chain_name': None, 'category': None,
                 'notes': '', 'city': ''},
        equipment_categories=_EQUIP, active={'db'},
        notes='', city='', is_manual=False, is_mapbox_anchored=False,
        is_deletable=False, display_address='',
        privacy_locked=False, privacy_opt_out=False, privacy_effective=False,
        terrain_choices=_TERRAIN, active_terrain_ids={'trail'},
        # WS-H Slice 5 — the relocated (b) craft↔locale capture.
        craft_catalog={'cycling': [{'slug': 'mountain_bike', 'label': 'Mountain bike'}],
                       'paddling': [{'slug': 'kayak', 'label': 'Kayak'}]},
        crafts_here=['kayak'],
    )
    base.update(kw)
    return base


def test_form_legacy_renders():
    html = _render('locales/form.html', **_form_ctx())
    assert 'app-shell' in html
    assert 'Location equipment' in html
    # Field names preserved for the POST handler.
    assert 'name="equipment"' in html
    assert 'name="locale_terrain_ids"' in html
    assert 'name="city"' in html          # legacy-only field present
    assert 'name="notes"' in html
    assert 'Dumbbells' in html and 'Trail' in html
    # Terrain `notes` render as a hover tooltip on the label (issue #444).
    assert 'title="Dirt singletrack."' in html
    # No shared-profile override chips in legacy mode.
    assert '+ override' not in html
    assert 'style="' not in html and 'onclick=' not in html


def test_form_shared_inherit_shows_override_chips():
    html = _render('locales/form.html', **_form_ctx(
        mode='shared_inherit',
        profile={'locale_name': 'Planet Fitness', 'chain_name': 'Planet Fitness',
                 'category': None, 'notes': '', 'city': ''},
        active={'db'}, shared_tags={'bb'}, adds={'db'}, removes=set(),
        shared={'last_confirmed_at': '2026-05-01', 'contribution_count': 3},
        is_mapbox_anchored=True,
    ))
    assert 'app-shell' in html
    assert '+ override' in html        # 'db' is an add on top of shared
    assert 'shared' in html            # 'bb' inherited
    assert 'Inherited from the shared profile' in html
    # shared modes are not legacy → no city field.
    assert 'name="city"' not in html
    assert 'style="' not in html


def test_form_deletable_shows_delete():
    html = _render('locales/form.html', **_form_ctx(is_deletable=True))
    assert '/locales/home/delete' in html
    assert 'data-confirm=' in html     # delete still confirms
    assert 'style="' not in html


def test_form_renders_craft_kept_here():
    """WS-H #581 Slice 5 — the (b) standing craft↔locale capture, relocated off the
    event-windows page onto the per-locale edit page (craft kept at a place is a
    property of the place), posting to the locale-scoped `save_locale_crafts`."""
    html = _render('locales/form.html', **_form_ctx())
    assert 'Craft you keep here' in html
    assert 'name="craft_slug"' in html
    assert '/locales/home/crafts' in html          # locale-scoped save route
    assert 'Mountain bike' in html and 'Kayak' in html
    assert 'id="kept_kayak"' in html               # crafts_here drives checked state
    # Hidden when no catalog (e.g. pre-Slice-5 callers) — guarded render.
    bare = _render('locales/form.html', **_form_ctx(craft_catalog=None))
    assert 'Craft you keep here' not in bare
    assert 'style="' not in html and 'onclick=' not in html


# ─── locales/new.html ───────────────────────────────────────────────────

def _new_ctx(**kw):
    base = dict(manual=False, query='', acked=True, results=[], error=None,
                manual_categories=[('home', 'Home gym')],
                residential_categories=['home_gym', 'other_residence'],
                disclosure_version='v1', upgrade_slug='', upgrade_locale=None)
    base.update(kw)
    return base


def test_new_manual_renders():
    html = _render('locales/new.html', **_new_ctx(manual=True))
    assert 'app-shell' in html
    assert 'name="locale_name"' in html
    assert 'name="address"' in html
    assert 'name="category"' in html
    assert '/locales/new/manual' in html
    assert 'style="' not in html


def test_new_disclosure_gate_renders():
    html = _render('locales/new.html', **_new_ctx(acked=False, query='gym'))
    assert 'Place lookup uses Mapbox' in html
    assert '/locales/new/acknowledge' in html
    assert 'Acknowledge' in html
    assert 'style="' not in html


def test_new_search_results_render():
    results = [{'text': 'Planet Fitness', 'place_name': '123 Main St',
                'mapbox_id': 'poi.1'}]
    html = _render('locales/new.html', **_new_ctx(query='planet', results=results))
    assert 'name="q"' in html                 # search field
    assert 'Planet Fitness' in html
    assert 'name="mapbox_id"' in html          # per-result save form
    assert 'Save this' in html
    assert 'style="' not in html and 'onclick=' not in html


# ─── locales/nearby.html + refresh_confirm.html ─────────────────────────

def test_nearby_renders_candidates():
    candidates = [{'mapbox_id': 'poi.1', 'text': 'Planet Fitness Uptown',
                   'place_name': '99 Lake St'}]
    html = _render('locales/nearby.html', canonical='Planet Fitness',
                   anchor={'locale_name': 'PF Downtown', 'locale': 'pf-dt'},
                   candidates=candidates)
    assert 'app-shell' in html
    assert 'name="mapbox_id"' in html
    assert 'Planet Fitness Uptown' in html
    assert 'Add selected' in html
    assert 'style="' not in html and 'onclick=' not in html


def test_refresh_confirm_renders_diff():
    html = _render('locales/refresh_confirm.html', locale='pf-dt',
                   profile={'locale_name': 'PF Downtown'},
                   refreshed={'text': 'Planet Fitness — Downtown', 'raw_payload': '{}'},
                   old_text='Planet Fitness', old_chain_name='Planet Fitness',
                   new_chain_id='pf', new_chain_name='Planet Fitness',
                   new_category='gym', name_changed=True, chain_changed=False)
    assert 'app-shell' in html
    # All hidden POST fields preserved for the confirm roundtrip.
    for name in ('confirm', 'refresh_text', 'refresh_chain_id',
                 'refresh_chain_name', 'refresh_category', 'refresh_payload'):
        assert 'name="%s"' % name in html
    assert 'Yes, update' in html
    assert 'Planet Fitness — Downtown' in html
    assert 'style="' not in html


# ─── profile/event_windows.html ─────────────────────────────────────────
# Slice 2b (WS-H #581): the away-destination capture links into the existing
# /locales/new Mapbox flow with a return_to back to the event-windows page,
# rather than embedding a duplicate search UI. This render asserts the
# pick-existing dropdown (2a) and the inline-create link (2b) both render.


def test_event_windows_capture_renders_away_create_link():
    catalog = {
        'cycling': [{'slug': 'mountain_bike', 'label': 'Mountain bike'}],
        'paddling': [{'slug': 'packraft', 'label': 'Packraft'}],
    }
    html = _render('profile/event_windows.html',
                   windows=[],
                   locales=['home', 'belfast-hotel'],
                   override_types=('indoor_only', 'locale_unavailable', 'away'),
                   craft_catalog=catalog)
    assert 'app-shell' in html
    # 2a — pick-existing destination dropdown.
    assert 'name="away_locale"' in html
    assert 'belfast-hotel' in html
    # 2b + #608 item 2 — inline-create is now a formaction submit button that
    # POSTs the in-progress form to the stash route (which hands off to
    # /locales/new server-side, preserving form state), not a plain href.
    assert '/profile/event-windows/new-locale' in html
    assert 'formaction=' in html and 'formnovalidate' in html
    assert 'event-windows' in html
    assert 'Add a new location' in html
    # The new-location submit appears before the visible "Add window" submit, so
    # a first visually-hidden duplicate must claim the Enter-key default — else
    # pressing Enter would bounce to /locales/new. Lock that ordering within the
    # add-window form (anchored on its action so the shell can't interfere).
    form_start = html.index('action="/profile/event-windows/add"')
    hidden_default = html.index('visually-hidden', form_start)
    new_loc_submit = html.index('formaction=', form_start)
    assert hidden_default < new_loc_submit
    # No draft on a fresh visit → date/notes fields render an empty value.
    assert 'value=""' in html
    # Slice 4 (WS-H #581): brought-craft (c) on the away window, fed from the
    # closed craft catalog.
    assert 'name="brought_craft"' in html
    assert 'Packraft' in html and 'Mountain bike' in html
    # Slice 5: the standing craft↔locale (b) capture moved to the per-locale edit
    # page — this page now only links there, no in-page craft_slug form.
    assert 'name="craft_slug"' not in html
    assert 'own page</a>' in html and '/locales' in html
    # Strict-CSP: no inline style/handlers.
    assert 'style="' not in html and 'onclick=' not in html
    # Slice 5b: no plan-gen round-trip when reached standalone (no return_to) —
    # the back-link banner stays hidden.
    assert 'Back to plan generation' not in html


def test_event_windows_renders_plan_gen_round_trip_when_return_to_set():
    """Slice 5b (WS-H #581): reached from the plan-gen review panel, the page
    shows a 'back to plan generation' link and threads return_to through the
    add/delete forms so the round-trip survives an edit."""
    html = _render('profile/event_windows.html',
                   windows=[],
                   locales=['home'],
                   override_types=('indoor_only', 'locale_unavailable', 'away'),
                   craft_catalog={'cycling': [], 'paddling': []},
                   return_to='/plans/v2/new')
    assert 'Back to plan generation' in html
    assert 'href="/plans/v2/new"' in html
    # The add form preserves return_to so an append bounces back to create.
    assert 'name="return_to"' in html and 'value="/plans/v2/new"' in html
    # The inline new-location create link nests return_to so creating a
    # destination still lands back in the round-trip.
    assert '/plans/v2/new' in html
    assert 'style="' not in html and 'onclick=' not in html


def test_event_windows_form_repopulates_from_draft():
    """#608 item 2 (WS-H): after an inline new-location round-trip, the stashed
    in-progress window form is replayed into the add form — dates, the away
    constraint + destination, brought-craft, and notes all come back selected,
    so the athlete doesn't re-enter what the strict-CSP reload would have wiped."""
    html = _render('profile/event_windows.html',
                   windows=[],
                   locales=['home', 'belfast-hotel'],
                   override_types=('indoor_only', 'locale_unavailable', 'away'),
                   craft_catalog={'paddling': [{'slug': 'packraft', 'label': 'Packraft'}]},
                   draft={
                       'start_date': '2026-07-03',
                       'end_date': '2026-07-05',
                       'override_type': 'away',
                       'unavailable_locale': '',
                       'away_locale': 'belfast-hotel',
                       'brought_craft': ['packraft'],
                       'notes': 'work travel',
                   })
    assert 'value="2026-07-03"' in html and 'value="2026-07-05"' in html
    assert 'value="work travel"' in html
    # The away constraint + destination come back selected.
    assert '<option value="away" selected>' in html
    assert '<option value="belfast-hotel" selected>belfast-hotel</option>' in html
    # The brought-craft checkbox comes back checked.
    assert 'value="packraft" checked>' in html
    assert 'style="' not in html and 'onclick=' not in html


# ─── plan_create/new_form.html — Slice 5b event-windows review panel ──────


def _ew(start, end, override_type, **kw):
    import types as _types
    from datetime import date as _date
    return _types.SimpleNamespace(
        id=kw.get('id', 1),
        start_date=_date.fromisoformat(start),
        end_date=_date.fromisoformat(end),
        override_type=override_type,
        unavailable_locale=kw.get('unavailable_locale'),
        away_locale=kw.get('away_locale'),
        brought_craft=kw.get('brought_craft', ()),
        volume_pct=kw.get('volume_pct'),
        notes=kw.get('notes', ''),
    )


def test_plan_create_form_lists_event_windows_for_review():
    """The create form surfaces upcoming windows for review at plan generation
    (F1) and links to the dedicated editor with a return_to back here."""
    html = _render('plan_create/new_form.html',
                   race_event=None,
                   today_iso='2026-06-14',
                   event_windows=[
                       _ew('2026-07-03', '2026-07-05', 'away',
                           away_locale='belfast-hotel', brought_craft=('packraft',)),
                       _ew('2026-08-12', '2026-08-12', 'indoor_only'),
                   ])
    assert 'app-shell' in html
    assert 'Event windows' in html
    assert 'belfast-hotel' in html and 'packraft' in html
    assert 'Indoor only' in html
    # Round-trip into the dedicated editor, returning to the create form.
    assert '/profile/event-windows?return_to=' in html
    assert 'Add / edit event windows' in html
    assert 'style="' not in html and 'onclick=' not in html


def test_plan_create_form_empty_event_windows_prompts_declaration():
    """With no upcoming windows the panel still renders the edit link + a
    prompt to declare any travel/indoor windows."""
    html = _render('plan_create/new_form.html',
                   race_event=None,
                   today_iso='2026-06-14',
                   event_windows=[])
    assert 'No upcoming event windows' in html
    assert '/profile/event-windows?return_to=' in html


# ─── Slice 5b open-redirect guard on the round-trip return_to ─────────────


def test_event_windows_return_to_rejects_non_local_paths():
    """The plan-gen round-trip return_to must be a local same-site path — an
    absolute/protocol-relative URL is dropped so it can't become an open
    redirect (mirrors routes/locales._stash_return_to)."""
    from routes.profile import _safe_local_path
    assert _safe_local_path('/plans/v2/new') == '/plans/v2/new'
    assert _safe_local_path('//evil.example.com') is None
    assert _safe_local_path('https://evil.example.com') is None
    assert _safe_local_path('') is None
    assert _safe_local_path(None) is None


def test_event_windows_back_link_label_reflects_origin():
    """#608 item 3 (WS-H): the editor's back-link label is derived from the
    round-trip origin so it reads 'setup' when reached from onboarding and
    'plan generation' from the create form — consistent across add/delete."""
    from routes.profile import _event_windows_return_label
    assert _event_windows_return_label('/onboarding/locales') == 'setup'
    assert _event_windows_return_label('/plans/v2/new') == 'plan generation'
    assert _event_windows_return_label(None) == 'plan generation'
    html = _render('profile/event_windows.html', windows=[], locales=['home'],
                   override_types=('indoor_only', 'locale_unavailable', 'away'),
                   craft_catalog={}, return_to='/onboarding/locales',
                   return_to_label='setup')
    assert 'Back to setup' in html and 'href="/onboarding/locales"' in html


def test_event_window_draft_stash_is_consumed_once():
    """#608 item 2: the in-progress add-window form is stashed in the session
    (preserving the multi-valued brought-craft list) and popped exactly once on
    the next render, so a stale draft can't leak onto a later unrelated visit —
    same single-consume contract as the locale flow's return_to stash."""
    from werkzeug.datastructures import MultiDict
    from routes.profile import _stash_event_window_draft, _pop_event_window_draft
    form = MultiDict([
        ('start_date', '2026-07-03'), ('end_date', '2026-07-05'),
        ('override_type', 'away'), ('away_locale', 'belfast-hotel'),
        ('brought_craft', 'packraft'), ('brought_craft', 'kayak'),
        ('notes', '  work travel  '),
    ])
    with _appmod.app.test_request_context('/'):
        _stash_event_window_draft(form)
        draft = _pop_event_window_draft()
        assert draft['start_date'] == '2026-07-03'
        assert draft['override_type'] == 'away'
        assert draft['away_locale'] == 'belfast-hotel'
        assert draft['brought_craft'] == ['packraft', 'kayak']
        assert draft['notes'] == 'work travel'      # stripped
        # Consumed once — a second pop in the same session returns nothing.
        assert _pop_event_window_draft() is None


# ─── Slice 6b (#593) — volume / in-transit window capture ────────────────────


def test_event_windows_form_offers_volume_types_and_percent():
    """The add-window form offers the two volume constraint types + the
    reduced-volume percent control (Slice 6b)."""
    html = _render('profile/event_windows.html',
                   windows=[], locales=['home'],
                   override_types=('indoor_only', 'locale_unavailable', 'away',
                                   'reduced_volume', 'no_training'),
                   craft_catalog={}, return_to=None, return_to_label=None,
                   draft=None)
    assert 'value="reduced_volume"' in html
    assert 'value="no_training"' in html
    assert 'name="volume_pct"' in html
    assert '50% — half day' in html
    assert 'style="' not in html and 'onclick=' not in html  # strict CSP


def test_event_windows_list_renders_volume_labels():
    """Saved volume windows render readable labels (with the percent for
    reduced_volume) in the list table."""
    html = _render('profile/event_windows.html',
                   windows=[
                       _ew('2026-07-03', '2026-07-03', 'reduced_volume',
                           volume_pct=0.5),
                       _ew('2026-07-10', '2026-07-11', 'no_training'),
                   ],
                   locales=['home'],
                   override_types=('indoor_only', 'locale_unavailable', 'away',
                                   'reduced_volume', 'no_training'),
                   craft_catalog={}, return_to=None, return_to_label=None,
                   draft=None)
    assert 'Reduced volume' in html and '50%' in html
    assert 'No training' in html
