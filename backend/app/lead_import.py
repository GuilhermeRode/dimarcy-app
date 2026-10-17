"""Imports leads from the Receita Federal's open CNPJ data. Run from backend/:  python -m app.lead_import

A systemd timer runs it daily; it only does real work when the Receita published a new month or
the scope (states in seller_cities + Configurações' CNAE list) changed. Any error writes nothing.
Spec: docs/superpowers/specs/2026-10-16-prospeccao-crm-design.md (Importação)"""
import base64
import csv
import io
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime
from typing import Callable, Iterator

from sqlalchemy.orm import Session

from . import clock
from .config import settings
from .database import SessionLocal
from .leads import customer_cnpjs, normalize_cnpj
from .models import Contact, Customer, Lead, SellerCity
from .sales import _city_key
from .settings_store import get_app_settings

ESTAB_COLUMNS, COMPANY_COLUMNS, TOWN_COLUMNS = 30, 7, 2
ACTIVE = "02"
CONNECTORS = {"da", "das", "de", "do", "dos", "e"}


def read_rows(zip_path: str, columns: int) -> Iterator[list[str]]:
    """Rows of the single CSV inside a Receita zip (';', latin-1, quoted, no header)."""
    with zipfile.ZipFile(zip_path) as z, z.open(z.namelist()[0]) as raw:
        for row in csv.reader(io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";"):
            if len(row) != columns:
                raise ValueError(f"{zip_path}: expected {columns} columns, got {len(row)}")
            yield row


def parse_towns(zip_path: str) -> dict[str, str]:
    return {code: name for code, name in read_rows(zip_path, TOWN_COLUMNS)}


def _date(yyyymmdd: str) -> date | None:
    s = yyyymmdd.strip()
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8])) if len(s) == 8 else None
    except ValueError:
        return None


def pick(row: list[str], cnaes: set[str], states: set[str], towns: dict[str, str]) -> dict | None:
    """The lead fields of an establishment row, or None when it's out of scope."""
    if row[5] != ACTIVE or row[11] not in cnaes or row[19] not in states or row[20] not in towns:
        return None
    street = " ".join(p for p in (row[13].strip(), row[14].strip()) if p)
    address = ", ".join(p for p in (street, row[15].strip(), row[16].strip(), row[17].strip(), row[18].strip()) if p)
    return {
        "cnpj": normalize_cnpj(row[0] + row[1] + row[2]),
        "basico": row[0],
        "name": row[4].strip(),
        "phone": f"{row[21].strip()} {row[22].strip()}".strip() if row[22].strip() else None,
        "email": row[27].strip().lower() or None,
        "address": address[:250] or None,
        "raw_city": towns[row[20]],
        "state": row[19],
        "opened_at": _date(row[10]),
    }


def display_city(raw: str, state: str, spellings: dict[tuple[str, str], str]) -> str:
    """The customers' spelling when one exists ("Jaraguá do Sul"); else Title Case with lowercase
    connectors — the Receita writes towns in uppercase without accents."""
    known = spellings.get((_city_key(raw), state))
    if known:
        return known
    return " ".join(w if w in CONNECTORS else "-".join(p.capitalize() for p in w.split("-"))
                    for w in raw.lower().split())


def current_scope(db: Session) -> tuple[set[str], set[str], str]:
    """States that have at least one seller city, the CNAE list, and both as text for comparison."""
    states = {s for (s,) in db.query(SellerCity.state).distinct()}
    cnaes = {c for c in get_app_settings(db).lead_cnaes.split(",") if c}
    return states, cnaes, f"{','.join(sorted(states))}|{','.join(sorted(cnaes))}"


def apply(db: Session, found: dict[str, dict], month: str, scope: str, today: date) -> int:
    """Writes one import in a single transaction: insert new CNPJs, refresh known ones (status kept),
    drop 'new' leads that left the Receita unless they have contacts. Returns how many are new."""
    known = customer_cnpjs(db)
    spellings = {(_city_key(c), (s or "").strip().upper()): " ".join(c.split())
                 for c, s in db.query(Customer.city, Customer.state).filter(Customer.city.isnot(None)) if c.strip()}
    existing = {lead.cnpj: lead for lead in db.query(Lead)}
    added = 0
    for cnpj, d in found.items():
        if cnpj in known:
            continue
        city = display_city(d["raw_city"], d["state"], spellings)
        fields = {"name": (d["name"] or cnpj)[:160], "phone": d["phone"], "email": d["email"], "address": d["address"],
                  "city": city, "state": d["state"], "city_key": _city_key(city), "opened_at": d["opened_at"],
                  "seen_at": today}
        lead = existing.get(cnpj)
        if lead:
            for k, v in fields.items():
                setattr(lead, k, v)
        else:
            db.add(Lead(cnpj=cnpj, status="new", **fields))
            added += 1
    with_contacts = {lid for (lid,) in db.query(Contact.lead_id).filter(Contact.lead_id.isnot(None)).distinct()}
    gone = [lead.id for cnpj, lead in existing.items()
            if lead.status == "new" and cnpj not in found and lead.id not in with_contacts]
    for i in range(0, len(gone), 500):  # stay under SQLite's bound-parameter limit
        db.query(Lead).filter(Lead.id.in_(gone[i:i + 500])).delete(synchronize_session=False)
    s = get_app_settings(db)
    s.last_lead_import_month, s.last_lead_import_scope, s.last_lead_import_at = month, scope, datetime.now()
    db.commit()
    return added


def run(db: Session, latest_month: Callable[[], str], download: Callable[[str, str, str], None],
        parts: int = 10) -> str:
    states, cnaes, scope = current_scope(db)
    if not states or not cnaes:
        return "no-scope"
    month = latest_month()
    s = get_app_settings(db)
    if (s.last_lead_import_month, s.last_lead_import_scope) == (month, scope):
        return "up-to-date"

    found: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        def fetch(name: str) -> str:
            path = os.path.join(tmp, name)
            download(month, name, path)
            return path

        towns_zip = fetch("Municipios.zip")
        towns = parse_towns(towns_zip)
        for i in range(parts):
            path = fetch(f"Estabelecimentos{i}.zip")
            for row in read_rows(path, ESTAB_COLUMNS):
                lead = pick(row, cnaes, states, towns)
                if lead:
                    found[lead["cnpj"]] = lead
            os.remove(path)  # ~350 MB each (the first one ~2.3 GB): one on disk at a time
        unnamed = {d["basico"] for d in found.values() if not d["name"]}
        if unnamed:
            names: dict[str, str] = {}
            for i in range(parts):
                path = fetch(f"Empresas{i}.zip")
                for row in read_rows(path, COMPANY_COLUMNS):
                    if row[0] in unnamed:
                        names[row[0]] = row[1].strip()
                os.remove(path)
            for d in found.values():
                if not d["name"]:
                    d["name"] = names.get(d["basico"], "")
    existing_new = db.query(Lead).filter(Lead.status == "new", Lead.state.in_(states)).count()
    if not found or len(found) < existing_new // 2:  # bad/partial download: don't wipe leads
        raise RuntimeError(f"Import looks wrong: {len(found)} leads found vs {existing_new} current new leads; nothing written")
    try:
        added = apply(db, found, month, scope, clock.today_br())
    except Exception:
        db.rollback()
        raise
    return f"imported {month}: {added} new"


def _request(path: str, method: str = "GET", headers: dict | None = None) -> urllib.request.Request:
    token = base64.b64encode(f"{settings.receita_share_token}:".encode()).decode()
    return urllib.request.Request(f"{settings.receita_webdav_url.rstrip('/')}/{path}", method=method,
                                  headers={"Authorization": f"Basic {token}", **(headers or {})})


def parse_months(xml_text: str) -> list[str]:
    hrefs = (e.text or "" for e in ET.fromstring(xml_text).iter("{DAV:}href"))
    return sorted(m.group(1) for m in (re.search(r"/(\d{4}-\d{2})/?$", h) for h in hrefs) if m)


def latest_month() -> str:
    with urllib.request.urlopen(_request("", "PROPFIND", {"Depth": "1"}), timeout=60) as r:
        months = parse_months(r.read().decode())
    if not months:
        raise RuntimeError("No YYYY-MM folder in the Receita share")
    return months[-1]


def download(month: str, name: str, dest: str) -> None:
    with urllib.request.urlopen(_request(f"{month}/{name}"), timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f, 1024 * 1024)


def main() -> int:
    with SessionLocal() as db:
        try:
            print(f"[lead_import] {run(db, latest_month, download)}")
            return 0
        except Exception as e:  # logged by systemd; tomorrow's run tries again
            print(f"[lead_import] failed, nothing written: {e!r}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(main())
