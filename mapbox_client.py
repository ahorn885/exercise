"""Mapbox Geocoding API client (D-59 §3).

Forward geocoding only — D-59 §3.1 is explicit that v1 doesn't use reverse
geocoding (athletes always start from a search string). Two surfaces:

  - search_places(query)        — autocomplete for /locales/new search box
  - search_nearby(query, lng, lat) — proximity discovery for the 42.2 km
                                     nearby-chain-instance picker (D-59 §5)

Both wrap the same Mapbox endpoint (`/geocoding/v5/mapbox.places/{q}.json`)
with different query params. Returns a list of normalized feature dicts
(see _normalize_feature) — caller never touches raw Mapbox JSON except via
`raw_payload` for audit storage on locale_profiles.place_payload.

Token via MAPBOX_PUBLIC_TOKEN env var (D-59 §3.2; PR9 handoff §5.1 names
this var). Public-scope (`pk.*`) tokens are fine for server-side geocoding
calls. When the env var is unset, every call raises MapboxTokenMissing —
routes catch this and degrade to manual-entry-only UX (D-59 §3.4 row 1).

Failure handling per D-59 §3.4: 5xx + network errors retry once with 1s
backoff; 4xx and 0-results raise typed exceptions for the caller to render
inline. No automatic fallback to manual entry — the route layer owns that
UX decision.
"""

import json
import os
import time
import urllib.parse

import requests


MAPBOX_TOKEN_ENV = 'MAPBOX_PUBLIC_TOKEN'
MAPBOX_BASE_URL = 'https://api.mapbox.com/geocoding/v5/mapbox.places'
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

    Mapbox's bbox parameter is a rectangle, not a circle (D-59 §3.1 note).
    We approximate: 1° latitude ≈ 111 km globally; 1° longitude ≈
    111 km × cos(lat). The square overshoots the circular radius at the
    corners but undershoots nothing — chain instances inside the radius
    are guaranteed inside the bbox.
    """
    import math
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return f'{lng - lng_delta},{lat - lat_delta},{lng + lng_delta},{lat + lat_delta}'


def _request(query: str, params: dict) -> dict:
    """Single Mapbox forward-geocoding call with 1-retry on 5xx (D-59 §3.4
    rows 3/4). Returns parsed JSON; raises MapboxAPIError on persistent
    failure or 4xx.
    """
    encoded = urllib.parse.quote(query, safe='')
    url = f'{MAPBOX_BASE_URL}/{encoded}.json'
    full_params = dict(params)
    full_params['access_token'] = _get_token()
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
    # Unreachable — both branches above either return or raise.
    raise MapboxAPIError(f'unreachable: {last_exc}')


def _normalize_feature(feature: dict) -> dict:
    """Project the Mapbox `features[i]` shape down to the fields the app
    consumes. `raw_payload` carries the full feature for audit storage in
    locale_profiles.place_payload.
    """
    center = feature.get('center') or [None, None]
    return {
        'mapbox_id': feature.get('id', ''),
        'text': feature.get('text', ''),  # primary name — fed to detect_chain
        'place_name': feature.get('place_name', ''),  # full breadcrumb display
        'lng': center[0] if len(center) > 0 else None,
        'lat': center[1] if len(center) > 1 else None,
        'category': (feature.get('properties') or {}).get('category', ''),
        'raw_payload': json.dumps(feature),
    }


def search_places(query: str, limit: int = 5) -> list[dict]:
    """Forward geocoding for /locales/new search box (D-59 §3.1 row 1).

    Returns up to `limit` normalized features; raises MapboxNoResults when
    Mapbox returns an empty features array (route renders inline "no
    matches" guidance per D-59 §3.4 row 5).
    """
    if not (query or '').strip():
        raise MapboxNoResults('empty query')
    payload = _request(query, {
        'autocomplete': 'true',
        'types': 'poi,address',
        'limit': str(limit),
    })
    features = payload.get('features') or []
    if not features:
        raise MapboxNoResults(f'no matches for {query!r}')
    return [_normalize_feature(f) for f in features]


def search_nearby(query: str, lng: float, lat: float,
                  radius_km: float = DEFAULT_RADIUS_KM,
                  limit: int = 10) -> list[dict]:
    """Proximity search for nearby chain instances (D-59 §5).

    Caller computes the bbox via `_bbox()` and passes the chain's canonical
    name as `query`. Result filtering (only instances of the same chain;
    exclude the anchor) is the route's responsibility — this function just
    surfaces what Mapbox returns inside the bbox.

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
