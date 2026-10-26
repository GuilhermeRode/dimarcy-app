"""Imports leads from the Receita Federal's open CNPJ data. Run from backend/:  python -m app.lead_import

A systemd timer runs it daily; it only does real work when the Receita published a new month or
the scope (Configurações' states, CNAE list and filters) changed. Any error writes nothing.
Each lead also gets its capital social and whether it has federal debt being collected (PGFN dívida ativa,
quarterly) — ranking signals, not filters.
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
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import clock
from .config import settings
from .database import SessionLocal
from .leads import customer_cnpjs, normalize_cnpj, refresh_scores
from .models import Contact, Customer, Lead
from .sales import _city_key
from .settings_store import get_app_settings

ESTAB_COLUMNS, COMPANY_COLUMNS, TOWN_COLUMNS, SIMPLES_COLUMNS = 30, 7, 2, 7
ACTIVE = "02"
SIZES = {"01": "me", "03": "epp", "05": "large"}  # Empresas porte -> leads.size
CONNECTORS = {"da", "das", "de", "do", "dos", "e"}


PGFN_URL = "https://dadosabertos.pgfn.gov.br"
PGFN_FILES = ("Dados_abertos_Nao_Previdenciario.zip", "Dados_abertos_Previdenciario.zip", "Dados_abertos_FGTS.zip")
IMPORT_STALE = timedelta(hours=4)  # a run older than this is considered dead


def utcnow() -> datetime:
    """Naive UTC, how import timestamps are stored (the UI appends "Z")."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def pid_alive(pid: int) -> bool:
    if os.name == "nt":  # os.kill would terminate the process there; can't tell, assume alive
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


def import_running(s) -> bool:
    return bool(s.lead_import_started_at and utcnow() - s.lead_import_started_at < IMPORT_STALE
                and (s.lead_import_pid is None or pid_alive(s.lead_import_pid)))


def clear_interrupted(db: Session) -> None:
    """Startup: an import whose process died with the server must not hold the lock for hours."""
    s = get_app_settings(db)
    if s.lead_import_started_at and s.lead_import_pid is not None and not pid_alive(s.lead_import_pid):
        s.lead_import_started_at, s.lead_import_pid = None, None
        s.lead_import_error = "Importação interrompida (o servidor reiniciou). Clique em Atualizar agora."
        db.commit()


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
    if filters["require_contact"] and not row[22].strip():  # a phone: sellers prospect by WhatsApp
        return None
    if filters["area_codes"] and row[21].strip().lstrip("0") not in filters["area_codes"]:
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


def capital(value: str) -> float:
    """Empresas' capital social, "1000,00" -> 1000.0 (0 when blank or unreadable)."""
    try:
        return float(value.strip().replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def debtors(zip_path: str, wanted: set[str], states: set[str]) -> set[str]:
    """CNPJ bases among `wanted` with a PGFN debt being collected ("Em cobrança"); debts paid in
    installments ("Benefício Fiscal") or guaranteed don't count. The zips hold several ';' CSVs with a header."""
    found = set()
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            with z.open(name) as raw:
                rows = csv.reader(io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";")
                header = next(rows, [])  # the situation column moves between files (7 or 9)
                if "TIPO_SITUACAO_INSCRICAO" not in header:
                    continue
                situation = header.index("TIPO_SITUACAO_INSCRICAO")
                for row in rows:
                    if len(row) > situation and row[4] in states and row[situation] == "Em cobrança":
                        base = normalize_cnpj(row[0])[:8]
                        if base in wanted:
                            found.add(base)
    return found


def current_scope(db: Session) -> tuple[set[str], set[str], dict, str]:
    """The states, the CNAE list, the quality filters, and all of it as text for comparison."""
    cfg = get_app_settings(db)
    states = {s for s in cfg.lead_states.split(",") if s}
    cnaes = {c for c in cfg.lead_cnaes.split(",") if c}
    filters = {"sizes": {c for c in cfg.lead_sizes.split(",") if c}, "exclude_mei": bool(cfg.lead_exclude_mei),
               "head_office_only": bool(cfg.lead_head_office_only), "require_contact": bool(cfg.lead_require_contact),
               "min_age_months": int(cfg.lead_min_age_months),
               "area_codes": {c for c in cfg.lead_area_codes.split(",") if c}}
    text = (f"{','.join(sorted(states))}|{','.join(sorted(cnaes))}|{','.join(sorted(filters['sizes']))}"
            f"|mei{int(filters['exclude_mei'])}|ho{int(filters['head_office_only'])}"
            f"|ct{int(filters['require_contact'])}|age{filters['min_age_months']}"
            + (f"|ddd{','.join(sorted(filters['area_codes']))}" if filters["area_codes"] else ""))
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
                  "size": d["size"], "capital": d["capital"], "in_debt": d["in_debt"], "seen_at": today}
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
    s.last_lead_import_month, s.last_lead_import_scope, s.last_lead_import_at = month, scope, utcnow()
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

    today = clock.today_br()
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
                lead = pick(row, cnaes, states, towns, filters, today)
                if lead:
                    found[lead["cnpj"]] = lead
            print(f"[lead_import] Estabelecimentos{i}.zip: {len(found)} leads so far", flush=True)
            os.remove(path)  # ~350 MB each (the first one ~2.3 GB): one on disk at a time
        wanted = {d["basico"] for d in found.values()}
        unnamed = {d["basico"] for d in found.values() if not d["name"]}
        names: dict[str, str] = {}
        portes: dict[str, str] = {}
        capitals: dict[str, float] = {}
        for i in range(parts):
            path = fetch(f"Empresas{i}.zip")
            for row in read_rows(path, COMPANY_COLUMNS):
                if row[0] in wanted:
                    portes[row[0]] = row[5]
                    capitals[row[0]] = capital(row[4])
                    if row[0] in unnamed:
                        names[row[0]] = row[1].strip()
            print(f"[lead_import] Empresas{i}.zip: {len(portes)} sizes so far", flush=True)
            os.remove(path)
        path = fetch("Simples.zip")
        mei = {row[0] for row in read_rows(path, SIMPLES_COLUMNS) if row[4] == "S" and row[0] in wanted}
        print(f"[lead_import] Simples.zip: {len(mei)} MEI", flush=True)
        os.remove(path)
        in_debt: set[str] | None = set()
        try:
            quarter = latest_quarter()
            for name in PGFN_FILES:
                path = os.path.join(tmp, name)
                download_pgfn(quarter, name, path)
                in_debt |= debtors(path, wanted, states)
                os.remove(path)
            print(f"[lead_import] PGFN {quarter}: {len(in_debt)} with dívida ativa", flush=True)
        except Exception as e:  # only a ranking signal: import anyway, as "not checked"
            in_debt = None
            print(f"[lead_import] PGFN unavailable, debt not checked: {e!r}", file=sys.stderr, flush=True)
        for cnpj, d in list(found.items()):
            if not d["name"]:
                d["name"] = names.get(d["basico"], "")
            porte = portes.get(d["basico"], "00")
            d["size"] = "mei" if d["basico"] in mei else SIZES.get(porte, "")
            d["capital"] = capitals.get(d["basico"])
            d["in_debt"] = None if in_debt is None else d["basico"] in in_debt
            if (filters["exclude_mei"] and d["size"] == "mei") or (d["size"] != "mei" and porte not in filters["sizes"]):
                del found[cnpj]
    existing_new = db.query(Lead).filter(Lead.status.in_(("pending", "new")), Lead.state.in_(states)).count()
    # Bad/partial download: don't wipe leads. The "less than half" check is skipped when the scope changed
    # (narrowed CNAEs / removed state legitimately shrink the result); an empty result is always refused.
    shrunk = len(found) < existing_new // 2 and s.last_lead_import_scope == scope
    if not found or shrunk:
        raise RuntimeError(f"Import looks wrong: {len(found)} leads found vs {existing_new} current new leads; nothing written")
    try:
        added = apply(db, found, month, scope, today)
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


def download(month: str, name: str, dest: str, attempts: int = 3, sleep: Callable[[float], None] = time.sleep,
             request: Callable[[str], urllib.request.Request] | None = None) -> None:
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen((request or _request)(f"{month}/{name}"), timeout=120) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f, 1024 * 1024)
            return
        except Exception as e:
            if attempt == attempts:
                raise RuntimeError(f"{month}/{name}: {e!r}") from e
            sleep(30)


def latest_quarter() -> str:
    """Newest PGFN folder, e.g. "2026_trimestre_03"."""
    with urllib.request.urlopen(PGFN_URL + "/", timeout=60) as r:
        quarters = re.findall(r'href="(\d{4}_trimestre_\d{2})/?"', r.read().decode("latin-1"))
    if not quarters:
        raise RuntimeError("No YYYY_trimestre_NN folder in the PGFN open data")
    return max(quarters)


def download_pgfn(quarter: str, name: str, dest: str) -> None:
    download(quarter, name, dest, request=lambda path: urllib.request.Request(f"{PGFN_URL}/{path}"))


def run_and_record(db: Session, latest_month, download, force: bool = False) -> str:
    """run() plus the status the Prospecção screen shows: started_at while running, last error."""
    s = get_app_settings(db)
    if not force and import_running(s):
        return "already-running"  # a UI run holds the lock; don't touch its status
    s.lead_import_started_at, s.lead_import_pid, s.lead_import_error = utcnow(), os.getpid(), None
    db.commit()
    try:
        return run(db, latest_month, download, force=force)
    except Exception as e:
        db.rollback()
        get_app_settings(db).lead_import_error = repr(e)[:300]
        raise
    finally:
        s = get_app_settings(db)
        s.lead_import_started_at, s.lead_import_pid = None, None
        db.commit()


def main(argv: list[str] | None = None) -> int:
    force = "--force" in (sys.argv[1:] if argv is None else argv)
    with SessionLocal() as db:
        try:
            print(f"[lead_import] {run_and_record(db, latest_month, download, force)}", flush=True)
            # every daily run, imported or not: the score depends on today and on the active customers per city
            print(f"[lead_import] scores refreshed: {refresh_scores(db, clock.today_br())} leads", flush=True)
            return 0
        except Exception as e:  # logged by systemd; tomorrow's run tries again
            print(f"[lead_import] failed, nothing written: {e!r}", file=sys.stderr, flush=True)
            return 1


if __name__ == "__main__":
    sys.exit(main())
