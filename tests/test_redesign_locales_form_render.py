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
                 'notes': ''},
        equipment_categories=_EQUIP, active={'db'},
        notes='', is_manual=False, is_mapbox_anchored=False,
        is_deletable=False, display_address='',
        privacy_locked=False, privacy_opt_out=False, privacy_effective=False,
        terrain_choices=_TERRAIN, active_terrain_ids={'trail'},
        # WS-H Slice 5 / #884 slice 6b — the relocated (b) gear↔locale capture,
        # generalized from craft-only to the full unified registry (all kinds).
        gear_registry=[
            {'group_kind': 'bike', 'label': 'Bikes',
             'rows': [{'gear_id': 'mountain_bike', 'label': 'Mountain bike'}]},
            {'group_kind': 'paddle', 'label': 'Paddle craft',
             'rows': [{'gear_id': 'kayak', 'label': 'Kayak'}]},
            {'group_kind': 'ski', 'label': 'Skis & rollerskis',
             'rows': [{'gear_id': 'classic_xc_ski', 'label': 'Classic XC skis'}]},
        ],
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
    assert 'name="city"' not in html      # #941 — free-text city field retired
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
                 'category': None, 'notes': ''},
        active={'db'}, shared_tags={'bb'}, adds={'db'}, removes=set(),
        shared={'last_confirmed_at': '2026-05-01', 'contribution_count': 3},
        is_mapbox_anchored=True,
    ))
    assert 'app-shell' in html
    assert '+ override' in html        # 'db' is an add on top of shared
    assert 'shared' in html            # 'bb' inherited
    assert 'Inherited from the shared profile' in html
    # #971 Slice 3 — inherit mode offers the explicit "report as wrong" flag.
    assert 'name="report_correction"' in html
    # shared modes are not legacy → no city field.
    assert 'name="city"' not in html
    assert 'style="' not in html


def test_form_deletable_shows_delete():
    html = _render('locales/form.html', **_form_ctx(is_deletable=True))
    assert '/locales/home/delete' in html
    assert 'data-confirm=' in html     # delete still confirms
    assert 'style="' not in html


def test_form_offers_photo_upload_when_profile_backed():
    """#971 Slice 2 — once a backing shared profile exists, the editor offers a
    multipart photo upload and renders approved/own-pending photos."""
    html = _render('locales/form.html', **_form_ctx(
        photo_profile_id=77,
        photos=[
            {'id': 1, 'url': 'https://blob/a.jpg', 'is_own': False, 'pending': False},
            {'id': 2, 'url': 'https://blob/b.jpg', 'is_own': True, 'pending': True},
        ],
    ))
    assert 'enctype="multipart/form-data"' in html
    assert 'name="photo"' in html
    assert '/locales/home/photos' in html         # upload route
    assert 'https://blob/a.jpg' in html
    assert 'Pending review' in html               # the own pending photo
    assert '/locales/home/photos/2/delete' in html  # own photo deletable
    assert '/locales/home/photos/1/delete' not in html  # peer's not deletable
    assert 'style="' not in html


def test_form_hides_photos_without_backing_profile():
    """No backing profile yet → no photo affordance (save equipment first)."""
    html = _render('locales/form.html', **_form_ctx())
    assert 'name="photo"' not in html


def test_form_renders_gear_kept_here():
    """#953 — the (b) standing gear↔locale capture (WS-H #581 Slice 5) is now
    folded into the single equipment editor form: one Save covers equipment +
    gear, no separate `save_locale_crafts` round-trip that bounced out. The
    gear checkboxes render inside the main form, not a second one. #884 slice 6b
    generalizes the picker from craft-only to the full unified registry, so
    ski/snow/climbing/alpine gear renders alongside bikes + paddle craft."""
    html = _render('locales/form.html', **_form_ctx())
    assert 'Gear you keep here' in html
    assert 'name="craft_slug"' in html
    assert 'Mountain bike' in html and 'Kayak' in html
    # #884 slice 6b — non-craft kinds now render (the observable picker change).
    assert 'Skis &amp; rollerskis' in html and 'Classic XC skis' in html
    assert 'id="kept_classic_xc_ski"' in html
    assert 'id="kept_kayak"' in html               # crafts_here drives checked state
    # The gear surface no longer posts to its own route — it shares the
    # unified location save (#953).
    assert '/locales/home/crafts' not in html
    # Exactly one form carries the toggles + save (plus the separate delete
    # form when deletable); there is no second gear-only save button.
    assert 'Save gear kept here' not in html
    # Hidden when no registry (e.g. pre-Slice-5 callers) — guarded render.
    bare = _render('locales/form.html', **_form_ctx(gear_registry=None))
    assert 'Gear you keep here' not in bare
    assert 'style="' not in html and 'onclick=' not in html


# ─── locales/new.html ───────────────────────────────────────────────────

def _new_ctx(**kw):
    base = dict(query='', acked=True, results=[], error=None,
                disclosure_version='v1', upgrade_slug='', upgrade_locale=None)
    base.update(kw)
    return base


def test_new_disclosure_gate_renders():
    html = _render('locales/new.html', **_new_ctx(acked=False, query='gym'))
    assert 'Place lookup uses Mapbox' in html
    assert '/locales/new/acknowledge' in html
    assert 'Acknowledge' in html
    # #941 — the manual-entry escape hatch is retired; every location is
    # Mapbox-anchored, so the gate no longer offers a manual fallback.
    assert 'manual' not in html.lower()
    assert 'style="' not in html


def test_new_search_results_render():
    results = [{'text': 'Planet Fitness', 'place_name': '123 Main St',
                'mapbox_id': 'poi.1'}]
    html = _render('locales/new.html', **_new_ctx(query='planet', results=results))
    assert 'name="q"' in html                 # search field
    assert 'Planet Fitness' in html
    assert 'name="mapbox_id"' in html          # per-result save form
    assert 'Save this' in html
    # No manual-entry path anywhere in the add-location flow (#941).
    assert '/locales/new/manual' not in html
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
    registry = [
        {'group_kind': 'bike', 'label': 'Bikes',
         'rows': [{'gear_id': 'mountain_bike', 'label': 'Mountain bike'}]},
        {'group_kind': 'paddle', 'label': 'Paddle craft',
         'rows': [{'gear_id': 'packraft', 'label': 'Packraft'}]},
        {'group_kind': 'climb', 'label': 'Climbing',
         'rows': [{'gear_id': 'climbing_gear', 'label': 'Climbing gear'}]},
    ]
    html = _render('profile/event_windows.html',
                   windows=[],
                   locales=['home', 'belfast-hotel'],
                   override_types=('indoor_only', 'locale_unavailable', 'away'),
                   gear_registry=registry)
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
    # Slice 4 (WS-H #581): brought-gear (c) on the away window, fed from the
    # unified gear registry. #884 slice 6c-1 — the form field is now
    # `brought_gear` (legacy-craft naming retired); 6b generalized the catalog to
    # all kinds.
    assert 'name="brought_gear"' in html
    assert 'Packraft' in html and 'Mountain bike' in html
    assert 'Climbing gear' in html and 'value="climbing_gear"' in html
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
                   gear_registry=[],
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
                   gear_registry=[{'group_kind': 'paddle', 'label': 'Paddle craft',
                                   'rows': [{'gear_id': 'packraft', 'label': 'Packraft'}]}],
                   draft={
                       'start_date': '2026-07-03',
                       'end_date': '2026-07-05',
                       'override_type': 'away',
                       'unavailable_locale': '',
                       'away_locale': 'belfast-hotel',
                       'brought_gear': ['packraft'],
                       'notes': 'work travel',
                   })
    assert 'value="2026-07-03"' in html and 'value="2026-07-05"' in html
    assert 'value="work travel"' in html
    # The away constraint + destination come back selected.
    assert '<option value="away" selected>' in html
    assert '<option value="belfast-hotel" selected>belfast-hotel</option>' in html
    # The brought-gear checkbox comes back checked.
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
        brought_gear=kw.get('brought_gear', ()),
        volume_pct=kw.get('volume_pct'),
        volume_by_date=kw.get('volume_by_date', {}),
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
                           away_locale='belfast-hotel', brought_gear=('packraft',)),
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
    (preserving the multi-valued brought-gear list) and popped exactly once on
    the next render, so a stale draft can't leak onto a later unrelated visit —
    same single-consume contract as the locale flow's return_to stash."""
    from werkzeug.datastructures import MultiDict
    from routes.profile import _stash_event_window_draft, _pop_event_window_draft
    form = MultiDict([
        ('start_date', '2026-07-03'), ('end_date', '2026-07-05'),
        ('override_type', 'away'), ('away_locale', 'belfast-hotel'),
        ('brought_gear', 'packraft'), ('brought_gear', 'kayak'),
        ('notes', '  work travel  '),
    ])
    with _appmod.app.test_request_context('/'):
        _stash_event_window_draft(form)
        draft = _pop_event_window_draft()
        assert draft['start_date'] == '2026-07-03'
        assert draft['override_type'] == 'away'
        assert draft['away_locale'] == 'belfast-hotel'
        assert draft['brought_gear'] == ['packraft', 'kayak']
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
    # #889 — a single-day window renders one date + a "(1 day)" tag, never a
    # "start → end" range that reads as multi-day.
    assert '2026-07-03 <span class="dim">(1 day)</span>' in html
    assert '2026-07-03 → 2026-07-03' not in html
    # The multi-day no_training window still renders the arrow range.
    assert '2026-07-10 → 2026-07-11' in html


def test_event_windows_form_makes_single_day_ergonomic(monkeypatch):
    """#889 — the end date is optional (blank = single day) and the form spells
    out that a volume % blankets every covered day, so one reduced day inside a
    longer trip is captured as its own one-day window."""
    html = _render('profile/event_windows.html',
                   windows=[], locales=['home'],
                   override_types=('indoor_only', 'locale_unavailable', 'away',
                                   'reduced_volume', 'no_training'),
                   craft_catalog={}, return_to=None, return_to_label=None,
                   draft=None)
    # The end-date input is no longer `required` (blank means a single day).
    end_field = html[html.index('name="end_date"'):]
    end_input_end = end_field.index('>')
    assert 'required' not in end_field[:end_input_end]
    assert 'leave blank for a single day' in html
    # The reduced-volume control names its per-day scope so the athlete knows to
    # split a single reduced day out of a longer trip.
    assert 'Applies to' in html and 'every' in html
    assert 'one-day window' in html
    assert 'style="' not in html and 'onclick=' not in html  # strict CSP


def test_event_windows_list_links_to_per_day_editor_for_multiday_reduced():
    """#889 — a MULTI-day reduced_volume window offers a 'Per-day levels' link to
    the per-date editor; a single-day one doesn't (nothing to spread)."""
    html = _render('profile/event_windows.html',
                   windows=[
                       _ew('2026-07-03', '2026-07-07', 'reduced_volume',
                           id=1, volume_pct=0.5),
                       _ew('2026-07-10', '2026-07-10', 'reduced_volume',
                           id=2, volume_pct=0.5),
                   ],
                   locales=['home'],
                   override_types=('reduced_volume', 'no_training'),
                   craft_catalog={}, return_to=None, return_to_label=None,
                   draft=None)
    assert 'Per-day levels' in html
    assert '/event-windows/1/volume-days' in html
    assert '/event-windows/2/volume-days' not in html  # single day → no link


def test_event_window_volume_days_editor_renders_per_day_selects():
    """#889 — the per-day editor renders one percent select per covered date,
    pre-selected from the schedule, offering 100% as a normal (unreduced) day."""
    win = _ew('2026-07-03', '2026-07-05', 'reduced_volume', id=3, volume_pct=0.5)
    days = [
        {'iso': '2026-07-03', 'pct': 25},
        {'iso': '2026-07-04', 'pct': 100},
        {'iso': '2026-07-05', 'pct': 50},
    ]
    html = _render('profile/event_window_volume_days.html',
                   window=win, days=days, default_pct=50,
                   choices=(25, 50, 75, 100), return_to=None)
    assert 'app-shell' in html
    assert 'name="vol_2026-07-03"' in html
    assert 'name="vol_2026-07-04"' in html
    assert 'name="vol_2026-07-05"' in html
    # Saved levels round-trip; 100% is labelled the normal day.
    assert '<option value="25" selected>25%</option>' in html
    assert '<option value="100" selected>100% — normal</option>' in html
    assert 'action="/profile/event-windows/3/volume-days"' in html
    assert 'style="' not in html and 'onclick=' not in html  # strict CSP
