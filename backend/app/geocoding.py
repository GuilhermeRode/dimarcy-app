"""Best-effort city geocoding via Nominatim (OpenStreetMap) — free, no API key.

A `cities` table caches (name, state) -> (lat, lng), so the same city is never
looked up twice. On a cache miss, the actual network call runs in a
BackgroundTask (see routers/customers.py) so it never blocks the customer
save — the tradeoff is that lat/lng for a brand-new city show up a moment
later (next reload), not in that request's response. Never raises — a
failed lookup just leaves lat/lng unset and the customer save still succeeds.
"""
import json
import urllib.parse
import urllib.request

from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import City, Customer

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


def lookup_cached_city(db: Session, city: str, state: str | None) -> tuple[float, float] | None:
    name = city.strip()
    uf = (state or "").strip().upper()
    row = db.query(City).filter(func.lower(City.name) == name.lower(), City.state == uf).first()
    return (row.lat, row.lng) if row else None


def geocode_and_cache_background(customer_id: int, city: str, state: str | None) -> None:
    """Runs after the response is sent — its own DB session, since the
    request's session is already closed by then."""
    coords = geocode_city(city, state)
    if not coords:
        return
    with SessionLocal() as db:
        customer = db.get(Customer, customer_id)
        if customer and customer.city == city and customer.state == state:
            customer.lat, customer.lng = coords
        db.add(City(name=city.strip(), state=(state or "").strip().upper(), lat=coords[0], lng=coords[1]))
        db.commit()
