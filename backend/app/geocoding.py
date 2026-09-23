"""Best-effort city geocoding via Nominatim (OpenStreetMap) — free, no API key.

Called only when a customer's city/state is set or changed (not on every
read), so it stays well within Nominatim's usage policy (max ~1 req/s,
identifying User-Agent). Never raises — a failed lookup just leaves
lat/lng unset and the customer save still succeeds.
"""
import json
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "DiMarcyPedidos/1.0 (internal order-management tool)"


def geocode_city(city: str, state: str | None) -> tuple[float, float] | None:
    if not city:
        return None
    params = {
        "city": city,
        "state": state or "",
        "country": "Brazil",
        "format": "json",
        "limit": "1",
    }
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            results = json.loads(r.read().decode())
        if not results:
            return None
        return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"[geocoding] Failed to geocode '{city}/{state}': {e}")
        return None
