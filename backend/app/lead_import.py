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
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timedelta
from typing import Callable, Iterator

from sqlalchemy import select
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
SIZES = {"01": "me", "03": "epp", "05": "large"}  # Empresas porte -> leads.size
CONNECTORS = {"da", "das", "de", "do", "dos", "e"}


def read_rows(zip_path: str, columns: int) -> Iterator[list[str]]:
    """Rows of the single CSV inside a Receita zip (';', latin-1, quoted, no header)."""
    with zipfile.ZipFile(zip_path) as z, z.open(z.namelist()[0]) as raw:
        skipped, first_bad = 0, 0
        reader = csv.reader(io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";")
        for row in reader:
            if len(row) != columns:
                skipped += 1
                first_bad = first_bad or reader.line_num
                continue
            yield row
    if skipped > 1000:
        raise ValueError(f"{zip_path}: {skipped} rows with the wrong column count (expected {columns})")
    if skipped:
        print(f"[lead_import] {os.path.basename(zip_path)}: skipped {skipped} malformed rows, first at line {first_bad}",
              file=sys.stderr, flush=True)


def parse_towns(zip_path: str) -> dict[str, str]:
    return {code: name for code, name in read_rows(zip_path, TOWN_COLUMNS)}


def _date(yyyymmdd: str) -> date | None:
    s = yyyymmdd.strip()
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8])) if len(s) == 8 else None
    except ValueError:
        return None


def pick(row: list[str], cnaes: set[str], states: set[str], towns: dict[str, str], filters: dict,
         today: date) -> dict | None:
    """The lead fields of an establishment row, or None when it's out of scope or fails a quality filter."""
    if row[5] != ACTIVE or row[11] not in cnaes or row[19] not in states or row[20] not in towns:
        return None
    if filters["head_office_only"] and row[3] != "1":
        return None
    opened_at = _date(row[10])
    age = filters["min_age_months"]
    if age and (opened_at is None or opened_at > today - timedelta(days=30 * age)):
        return None
    if filters["require_contact"] and not (row[22].strip() or row[27].strip()):
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
        "opened_at": opened_at,
    }


def display_city(raw: str, state: str, spellings: dict[tuple[str, str], str]) -> str:
    """The customers' spelling when one exists ("Jaraguá do Sul"); else Title Case with lowercase
    connectors — the Receita writes towns in uppercase without accents."""
    known = spellings.get((_city_key(raw), state))
    if known:
        return known
    return " ".join(w if w in CONNECTORS else "-".join(p.capitalize() for p in w.split("-"))
                    for w in raw.lower().split())


def current_scope(db: Session) -> tuple[set[str], set[str], dict, str]:
    """States that have a seller city, the CNAE list, the quality filters, and all of it as text for comparison."""
    states = {s for (s,) in db.query(SellerCity.state).distinct()}
    cfg = get_app_settings(db)
    cnaes = {c for c in cfg.lead_cnaes.split(",") if c}
    filters = {"sizes": {c for c in cfg.lead_sizes.split(",") if c}, "exclude_mei": bool(cfg.lead_exclude_mei),
               "head_office_only": bool(cfg.lead_head_office_only), "require_contact": bool(cfg.lead_require_contact),
               "min_age_months": int(cfg.lead_min_age_months)}
    text = (f"{','.join(sorted(states))}|{','.join(sorted(cnaes))}|{','.join(sorted(filters['sizes']))}"
            f"|mei{int(filters['exclude_mei'])}|ho{int(filters['head_office_only'])}"
            f"|ct{int(filters['require_contact'])}|age{filters['min_age_months']}")
    return states, cnaes, filters, text


def apply(db: Session, found: dict[str, dict], month: str, scope: str, today: date) -> int:
    """Writes one import in a single transaction: insert new CNPJs, refresh known ones (status kept),
    drop 'pending'/'new' leads that left the Receita unless they have contacts. Returns how many are new."""
    known = customer_cnpjs(db)
    spellings = {(_city_key(c), (s or "").strip().upper()): " ".join(c.split())
                 for c, s in db.query(Customer.city, Customer.state).filter(Customer.city.isnot(None)) if c.strip()}
    existing = {lead.cnpj: lead for lead in db.query(Lead)}
    added = 0
    for cnpj, d in found.items():
        if cnpj in known:
            continue
        city = display_city(d["raw_city"], d["state"], spellings)
        fields = {"name": (d["name"] or cnpj)[:160], "phone": d["phone"], "email": (d["email"] or "")[:160] or None, "address": d["address"],
                  "city": city, "state": d["state"], "city_key": _city_key(city), "opened_at": d["opened_at"],
                  "size": d["size"], "seen_at": today}
        lead = existing.get(cnpj)
        if lead:
            for k, v in fields.items():
                setattr(lead, k, v)
        else:
            db.add(Lead(cnpj=cnpj, status="pending", **fields))
            added += 1
    with_contacts = {lid for (lid,) in db.query(Contact.lead_id).filter(Contact.lead_id.isnot(None)).distinct()}
    gone = [lead.id for cnpj, lead in existing.items()
            if lead.status in ("pending", "new") and cnpj not in found and lead.id not in with_contacts]
    for i in range(0, len(gone), 500):  # stay under SQLite's bound-parameter limit
        batch = gone[i:i + 500]  # re-checked in SQL: a contact may have been added since the read above
        db.query(Lead).filter(Lead.id.in_(batch), Lead.status.in_(("pending", "new")),
                              ~Lead.id.in_(select(Contact.lead_id).where(Contact.lead_id.isnot(None)))
                              ).delete(synchronize_session=False)
    s = get_app_settings(db)
    s.last_lead_import_month, s.last_lead_import_scope, s.last_lead_import_at = month, scope, datetime.now()
    db.commit()
    return added


def run(db: Session, latest_month: Callable[[], str], download: Callable[[str, str, str], None],
        parts: int = 10, force: bool = False) -> str:
    states, cnaes, filters, scope = current_scope(db)
    if not states or not cnaes:
        return "no-scope"
    month = latest_month()
    s = get_app_settings(db)
    if not force and (s.last_lead_import_month, s.last_lead_import_scope) == (month, scope):
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
                lead = pick(row, cnaes, states, towns, filters, clock.today_br())
                if lead:
                    found[lead["cnpj"]] = lead
            print(f"[lead_import] Estabelecimentos{i}.zip: {len(found)} leads so far", flush=True)
            os.remove(path)  # ~350 MB each (the first one ~2.3 GB): one on disk at a time
        wanted = {d["basico"] for d in found.values()}
        unnamed = {d["basico"] for d in found.values() if not d["name"]}
        names: dict[str, str] = {}
        portes: dict[str, str] = {}
        for i in range(parts):
            path = fetch(f"Empresas{i}.zip")
            for row in read_rows(path, COMPANY_COLUMNS):
                if row[0] in wanted:
                    portes[row[0]] = row[5]
                    if row[0] in unnamed:
                        names[row[0]] = row[1].strip()
            print(f"[lead_import] Empresas{i}.zip: {len(portes)} sizes so far", flush=True)
            os.remove(path)
        path = fetch("Simples.zip")
        mei = {row[0] for row in read_rows(path, COMPANY_COLUMNS) if row[4] == "S" and row[0] in wanted}
        print(f"[lead_import] Simples.zip: {len(mei)} MEI", flush=True)
        os.remove(path)
        for cnpj, d in list(found.items()):
            if not d["name"]:
                d["name"] = names.get(d["basico"], "")
            porte = portes.get(d["basico"], "00")
            d["size"] = "mei" if d["basico"] in mei else SIZES.get(porte, "")
            if (filters["exclude_mei"] and d["size"] == "mei") or (d["size"] != "mei" and porte not in filters["sizes"]):
                del found[cnpj]
    existing_new = db.query(Lead).filter(Lead.status.in_(("pending", "new")), Lead.state.in_(states)).count()
    # Bad/partial download: don't wipe leads. The "less than half" check is skipped when the scope changed
    # (narrowed CNAEs / removed state legitimately shrink the result); an empty result is always refused.
    shrunk = len(found) < existing_new // 2 and s.last_lead_import_scope == scope
    if not found or shrunk:
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


def download(month: str, name: str, dest: str, attempts: int = 3, sleep: Callable[[float], None] = time.sleep) -> None:
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(_request(f"{month}/{name}"), timeout=120) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f, 1024 * 1024)
            return
        except Exception as e:
            if attempt == attempts:
                raise RuntimeError(f"{month}/{name}: {e!r}") from e
            sleep(30)


def run_and_record(db: Session, latest_month, download, force: bool = False) -> str:
    """run() plus the status the Prospecção screen shows: started_at while running, last error."""
    s = get_app_settings(db)
    s.lead_import_started_at, s.lead_import_error = datetime.now(), None
    db.commit()
    try:
        return run(db, latest_month, download, force=force)
    except Exception as e:
        db.rollback()
        get_app_settings(db).lead_import_error = repr(e)[:300]
        raise
    finally:
        get_app_settings(db).lead_import_started_at = None
        db.commit()


def main(argv: list[str] | None = None) -> int:
    force = "--force" in (sys.argv[1:] if argv is None else argv)
    with SessionLocal() as db:
        try:
            print(f"[lead_import] {run_and_record(db, latest_month, download, force)}", flush=True)
            return 0
        except Exception as e:  # logged by systemd; tomorrow's run tries again
            print(f"[lead_import] failed, nothing written: {e!r}", file=sys.stderr, flush=True)
            return 1


if __name__ == "__main__":
    sys.exit(main())
