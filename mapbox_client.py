"""Mapbox Search Box API client (D-59 §3, post-PR10 step-5 fix).

PR10's first verification surfaced a real problem: the legacy Mapbox
Geocoding v5 endpoint (`mapbox.places`) is not a POI / business-name
search. A query like "Planet Fitness Minneapolis" is silently reduced to
just "Minneapolis" and geocoded to addresses, returning zero Planet
Fitness POIs. D-59 §12 foresaw "Mapbox's chain coverage is going to
disappoint" but the actual behaviour was worse — no chain hits at all,
not just sparse coverage.

This module now uses Mapbox's Search Box API forward endpoint
(`/search/searchbox/v1/forward`), which is designed for POI / brand
queries and returns rich `poi_category` metadata. The diagnostic curl
on 2026-05-15 confirmed it returns the expected Planet Fitness POIs for
the same query that returned zero from Geocoding v5.

Public surface unchanged from the PR10 ship — `search_places(query)` and
`search_nearby(query, lng, lat, radius_km)` return the same normalised
feature dict shape (`mapbox_id`, `text`, `place_name`, `lng`, `lat`,
`category`, `raw_payload`) so `routes/locales.py` + the templates need
zero code changes. Internals differ:

  - Endpoint base path is `/search/searchbox/v1/forward` (not
    `/geocoding/v5/mapbox.places/{q}.json`).
  - Query is a `q` parameter, not embedded in the URL path.
  - Response shape is GeoJSON-FeatureCollection with each feature's
    coords in `geometry.coordinates` (was `feature.center`) and the
    business name in `properties.name` / `properties.name_preferred`
    (was `feature.text`). `_normalize_feature` translates.
  - `poi_category` is a list (was a comma-string under
    `properties.category`); we join with `, ` so the route's substring
    match (`'gym' in mb_category`) still works.
  - No `session_token` plumbing — the `/forward` endpoint is one-shot,
    unlike the `/suggest` + `/retrieve` pair.

Token via `MAPBOX_PUBLIC_TOKEN` env var (unchanged); 1-retry on 5xx with
1s backoff (unchanged); 4xx + persistent 5xx + network errors raise
`MapboxAPIError`; 0-results raises `MapboxNoResults`; missing env var
raises `MapboxTokenMissing` before any HTTP call (unchanged).

`mapbox_id` format changes between the two APIs (Geocoding v5 used
`poi.123456789`; Search Box API uses opaque base64-ish strings). The
column is TEXT and treated opaquely everywhere it's read, so no schema
or code impact — existing test rows with old-format IDs stay valid as
stored data; new writes use new-format IDs.
"""

import json
import math
import os
import time

import requests


MAPBOX_TOKEN_ENV = 'MAPBOX_PUBLIC_TOKEN'
MAPBOX_BASE_URL = 'https://api.mapbox.com/search/searchbox/v1/forward'
MAPBOX_RETRIEVE_URL = 'https://api.mapbox.com/search/searchbox/v1/retrieve'
DEFAULT_RADIUS_KM = 42.2  # D-59 §3 row 3 — marathon-distance threshold
REQUEST_TIMEOUT_S = 5


class MapboxError(Exception):
    """Base class for Mapbox client failures.

    Routes catch MapboxError broadly and render an inline "Place lookup
    unavailable" message; specific subclasses let templates show a more
    specific message (no token vs. API down vs. zero results).
    """


class MapboxTokenMissing(MapboxError):
    """MAPBOX_PUBLIC_TOKEN env var is unset (D-59 §3.4 row 1)."""


class MapboxAPIError(MapboxError):
    """4xx/5xx from Mapbox after retry (D-59 §3.4 rows 2/3)."""


class MapboxNoResults(MapboxError):
    """Mapbox returned 0 features (D-59 §3.4 row 5)."""


def _get_token() -> str:
    token = os.environ.get(MAPBOX_TOKEN_ENV)
    if not token:
        raise MapboxTokenMissing(f'{MAPBOX_TOKEN_ENV} env var is unset')
    return token


def _bbox(lng: float, lat: float, radius_km: float) -> str:
    """Return Mapbox-style bbox `min_lng,min_lat,max_lng,max_lat` string for
    a square approximating the radius around the anchor.

    Mapbox's bbox parameter is a rectangle, not a circle. We approximate:
    1° latitude ≈ 111 km globally; 1° longitude ≈ 111 km × cos(lat). The
    square overshoots the circular radius at the corners but undershoots
    nothing — chain instances inside the radius are guaranteed inside the
    bbox.
    """
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return f'{lng - lng_delta},{lat - lat_delta},{lng + lng_delta},{lat + lat_delta}'


def _request(query: str, params: dict) -> dict:
    """Single Mapbox Search Box API forward call with 1-retry on 5xx
    (D-59 §3.4 rows 3/4). Returns parsed JSON; raises MapboxAPIError on
    persistent failure or 4xx.
    """
    full_params = dict(params)
    full_params['q'] = query
    full_params['access_token'] = _get_token()
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            r = requests.get(MAPBOX_BASE_URL, params=full_params, timeout=REQUEST_TIMEOUT_S)
        except requests.RequestException as e:
            last_exc = e
            if attempt == 0:
                time.sleep(1)
                continue
            raise MapboxAPIError(f'network error: {e}') from e
        if 500 <= r.status_code < 600:
            last_exc = MapboxAPIError(f'mapbox {r.status_code}: {r.text[:200]}')
            if attempt == 0:
                time.sleep(1)
                continue
            raise last_exc
        if r.status_code != 200:
            raise MapboxAPIError(f'mapbox {r.status_code}: {r.text[:200]}')
        return r.json()
    raise MapboxAPIError(f'unreachable: {last_exc}')


def _normalize_feature(feature: dict) -> dict:
    """Project the Search Box API forward `features[i]` shape down to the
    fields the app consumes. `raw_payload` carries the full feature for
    audit storage in locale_profiles.place_payload.

    Search Box API differences from legacy Geocoding v5:
      - coords live in `geometry.coordinates`, not `feature.center`
      - business name lives in `properties.name` (or `name_preferred`
        for branded POIs), not `feature.text`
      - full address lives in `properties.full_address`, not
        `feature.place_name`
      - `properties.poi_category` is a list of category strings;
        join with `, ` so the route's substring match still works.
    """
    props = feature.get('properties') or {}
    coords = (feature.get('geometry') or {}).get('coordinates') or [None, None]
    poi_category = props.get('poi_category') or []
    if isinstance(poi_category, list):
        category_str = ', '.join(str(c) for c in poi_category)
    else:
        category_str = str(poi_category)
    return {
        # Prefer name_preferred (brand-canonical, e.g. "Planet Fitness")
        # over name (which may include disambiguation suffixes like #234).
        'mapbox_id': props.get('mapbox_id', ''),
        'text': props.get('name_preferred') or props.get('name', ''),
        'place_name': props.get('full_address') or props.get('place_formatted', ''),
        'lng': coords[0] if len(coords) > 0 else None,
        'lat': coords[1] if len(coords) > 1 else None,
        'category': category_str,
        'raw_payload': json.dumps(feature),
    }


def search_places(query: str, limit: int = 5) -> list[dict]:
    """Forward POI/address search for /locales/new search box.

    Uses the Search Box API `/forward` endpoint, which is designed for
    POI / business-name queries (unlike legacy Geocoding v5 which dropped
    POI tokens from multi-word queries). `types=poi,address,place` lets
    Mapbox return the best match across POIs, street addresses, and named
    places.

    Returns up to `limit` normalised features; raises MapboxNoResults
    when Mapbox returns an empty features array (route renders inline
    "no matches" guidance per D-59 §3.4 row 5).
    """
    if not (query or '').strip():
        raise MapboxNoResults('empty query')
    payload = _request(query, {
        'limit': str(limit),
        'types': 'poi,address,place',
    })
    features = payload.get('features') or []
    if not features:
        raise MapboxNoResults(f'no matches for {query!r}')
    return [_normalize_feature(f) for f in features]


def _request_retrieve(mapbox_id: str, params: dict) -> dict:
    """GET /search/searchbox/v1/retrieve/{mapbox_id} with 1-retry on 5xx.

    Same retry + error semantics as `_request` for the forward endpoint,
    but the id sits in the URL path, not in a `q` parameter.
    """
    full_params = dict(params)
    full_params['access_token'] = _get_token()
    url = f'{MAPBOX_RETRIEVE_URL}/{mapbox_id}'
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            r = requests.get(url, params=full_params, timeout=REQUEST_TIMEOUT_S)
        except requests.RequestException as e:
            last_exc = e
            if attempt == 0:
                time.sleep(1)
                continue
            raise MapboxAPIError(f'network error: {e}') from e
        if 500 <= r.status_code < 600:
            last_exc = MapboxAPIError(f'mapbox {r.status_code}: {r.text[:200]}')
            if attempt == 0:
                time.sleep(1)
                continue
            raise last_exc
        if r.status_code != 200:
            raise MapboxAPIError(f'mapbox {r.status_code}: {r.text[:200]}')
        return r.json()
    raise MapboxAPIError(f'unreachable: {last_exc}')


def retrieve(mapbox_id: str, session_token: str | None = None) -> dict:
    """Look up a single feature by its stored `mapbox_id` (PR18 item B).

    Used by the §7 refresh path so locales the athlete has renamed
    ("Horn's House" instead of "123 Main St") still refresh — name search
    would return no matches. The id is opaque and stable across name
    changes, so retrieve is the right tool.

    `session_token` is optional. Search Box `/retrieve` accepts it to
    bill against a prior `/suggest` session. Refresh isn't tied to a
    prior suggest call, so callers pass a fresh UUID per invocation;
    Mapbox treats it as a one-shot session and bills accordingly.

    Returns the same normalised feature shape as `search_places` /
    `search_nearby`. Raises `MapboxNoResults` when Mapbox returns an
    empty features array (id no longer exists on Mapbox's side — the
    place was deleted or merged upstream).
    """
    if not (mapbox_id or '').strip():
        raise MapboxNoResults('empty mapbox_id')
    params: dict = {}
    if session_token:
        params['session_token'] = session_token
    payload = _request_retrieve(mapbox_id, params)
    features = payload.get('features') or []
    if not features:
        raise MapboxNoResults(f'no feature for {mapbox_id!r}')
    return _normalize_feature(features[0])


def search_nearby(query: str, lng: float, lat: float,
                  radius_km: float = DEFAULT_RADIUS_KM,
                  limit: int = 10) -> list[dict]:
    """Proximity search for nearby chain instances (D-59 §5).

    Caller passes the chain's canonical name as `query` and the anchor's
    coords as the proximity origin. `bbox` cuts results to a square
    approximating the radius. Result filtering (only instances of the
    same chain; exclude the anchor) is the route's responsibility — this
    function just surfaces what Mapbox returns inside the bbox.

    Raises MapboxNoResults when Mapbox returns zero features in the bbox
    (rare — most chains have multiple metro-area instances).
    """
    if not (query or '').strip():
        raise MapboxNoResults('empty query')
    payload = _request(query, {
        'proximity': f'{lng},{lat}',
        'bbox': _bbox(lng, lat, radius_km),
        'types': 'poi',
        'limit': str(limit),
    })
    features = payload.get('features') or []
    if not features:
        raise MapboxNoResults(f'no nearby matches for {query!r}')
    return [_normalize_feature(f) for f in features]
