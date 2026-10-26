# Prospecção + mini-CRM — Plano 2 de 3: importação da Receita Federal

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A script (`python -m app.lead_import`) that fills the `leads` table from the Receita Federal's open CNPJ data, run daily by a systemd timer on the VM and doing real work once a month (or when the scope changes).

**Architecture:** `backend/app/lead_import.py` is split in three layers so the test never touches the internet: **fetch** (WebDAV listing + download, stdlib `urllib`), **parse** (zip → `csv` rows → lead dicts), **apply** (one DB transaction). `run()` takes the fetch functions as parameters; the test passes fakes that serve small zips built on the fly.

**Tech Stack:** Python stdlib only (`urllib.request`, `zipfile`, `csv`, `xml.etree`), SQLAlchemy. systemd timer on the Oracle Linux VM.

**Spec:** `docs/superpowers/specs/2026-10-16-prospeccao-crm-design.md` (section "Importação")

**Depends on:** Plano 1 (`2026-10-16-prospeccao-1-backend.md`) — tables `leads`, `seller_cities`, `contacts`, `app_settings.lead_cnaes/last_lead_import_*`, and `leads.normalize_cnpj`, `leads.customer_cnpjs`.

## Global Constraints

- No new dependencies (stdlib only for HTTP, zip, CSV, XML).
- Source (verified 2026-10-16): WebDAV base `https://arquivos.receitafederal.gov.br/public.php/webdav`, Basic auth user = share token `YggdBLfdninEJX9`, empty password. Both in `config.py` (`receita_webdav_url`, `receita_share_token`), overridable from `.env`.
- Files: `Estabelecimentos0..9.zip`, `Empresas0..9.zip`, `Municipios.zip`. Each zip holds ONE oddly named file: read the first entry.
- CSV: `;` separator, latin-1, every field double-quoted, no header; fields may contain `;` → always `csv.reader`, never `split`.
- Estabelecimentos has 30 columns; indexes: 0 básico, 1 ordem, 2 DV, 4 fantasia, 5 situação (`"02"` = ativa), 10 início `YYYYMMDD`, 11 CNAE principal (7 digits), 13 tipo logradouro, 14 logradouro, 15 número, 16 complemento, 17 bairro, 18 CEP, 19 UF, 20 município (Receita code, zero-padded string), 21 DDD 1, 22 telefone 1, 27 e-mail. Empresas: 7 columns, 0 básico, 1 razão social. Municipios: 2 columns, code; name (uppercase, no accents).
- Any error (network, bad zip, wrong column count) → nothing written; exit code 1.
- CNPJ = `leads.normalize_cnpj(básico + ordem + DV)` (may contain letters).

## Review Focus

- A row whose address has `;` inside quotes must parse into the right columns (the column-count check would otherwise abort the whole import).
- A lead with contacts must survive an import that no longer lists it; one without contacts must go.
- The second run in the same month with the same scope must not download anything (the daily timer would otherwise pull ~7 GB a day).
- A month with a partial failure (e.g. `Estabelecimentos7.zip` 404) must leave the previous month's leads untouched and `last_lead_import_month` unchanged.
- A Receita town spelled like a customer's city ("JARAGUA DO SUL" vs "Jaraguá do Sul") must show the customer's spelling.

---

### Task 1: Parsing (rows, towns, establishment → lead, city display name)

**Files:**
- Create: `backend/app/lead_import.py`
- Create: `backend/test_lead_import.py`

**Interfaces:**
- Produces:
  - `read_rows(zip_path: str, columns: int) -> Iterator[list[str]]` — raises `ValueError` on a row with a different column count
  - `parse_towns(zip_path) -> dict[str, str]` (code → raw name)
  - `pick(row: list[str], cnaes: set[str], states: set[str], towns: dict[str, str]) -> dict | None` with keys `cnpj, basico, name, phone, email, address, raw_city, state, opened_at`
  - `display_city(raw: str, state: str, spellings: dict[tuple[str, str], str]) -> str`
- Test helpers (in `test_lead_import.py`, reused by Task 2): `make_zip(path, rows)`, `estab(**kw) -> list[str]`.

- [ ] **Step 1: Write the failing test** — create `backend/test_lead_import.py`:

```python
"""Receita importer self-check, no internet: small zips built here. Run from backend/:  python test_lead_import.py
Uses a throwaway SQLite file, never dimarcy.db."""
import csv
import io
import os
import tempfile
import zipfile
from datetime import date

tmp = tempfile.mkdtemp()
db_file = os.path.join(tmp, "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from app import lead_import as li  # noqa: E402


def make_zip(path, rows, inner="K3241.K03200Y3.D61010.ESTABELE"):
    buf = io.StringIO()
    csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n").writerows(rows)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(inner, buf.getvalue().encode("latin-1"))
    return path


def estab(basico="10000000", ordem="0001", dv="01", fantasia="LOJA A", situacao="02", inicio="20250101",
          cnae="4781400", uf="SC", town="8175", ddd="47", phone="33330000", email="Loja@Mail.com",
          street="QUADRA 11;LOTE 04", number="10", bairro="CENTRO", cep="89251000"):
    row = [""] * 30
    row[0], row[1], row[2], row[4], row[5] = basico, ordem, dv, fantasia, situacao
    row[10], row[11], row[13], row[14], row[15] = inicio, cnae, "RUA", street, number
    row[17], row[18], row[19], row[20], row[21], row[22], row[27] = bairro, cep, uf, town, ddd, phone, email
    return row


def check_parsing():
    towns_zip = make_zip(os.path.join(tmp, "Municipios.zip"), [["8175", "JARAGUA DO SUL"], ["0001", "GUAJARA-MIRIM"]])
    towns = li.parse_towns(towns_zip)
    assert towns == {"8175": "JARAGUA DO SUL", "0001": "GUAJARA-MIRIM"}

    z = make_zip(os.path.join(tmp, "e.zip"), [estab()])
    rows = list(li.read_rows(z, 30))
    assert rows[0][14] == "QUADRA 11;LOTE 04"  # ';' inside quotes stays in its column
    bad = make_zip(os.path.join(tmp, "bad.zip"), [["1", "2"]])
    try:
        list(li.read_rows(bad, 30))
        raise AssertionError("wrong column count must raise")
    except ValueError:
        pass

    cn, st = {"4781400"}, {"SC"}
    lead = li.pick(estab(), cn, st, towns)
    assert lead == {"cnpj": "10000000000101", "basico": "10000000", "name": "LOJA A", "phone": "47 33330000",
                    "email": "loja@mail.com", "address": "RUA QUADRA 11;LOTE 04, 10, CENTRO, 89251000",
                    "raw_city": "JARAGUA DO SUL", "state": "SC", "opened_at": date(2025, 1, 1)}, lead
    assert li.pick(estab(situacao="08"), cn, st, towns) is None
    assert li.pick(estab(cnae="4642701"), cn, st, towns) is None
    assert li.pick(estab(uf="PR"), cn, st, towns) is None
    assert li.pick(estab(town="7777"), cn, st, towns) is None  # unknown town: can't place it in a region
    blank = li.pick(estab(basico="12ABC345", fantasia=" ", phone="", email="", inicio=""), cn, st, towns)
    assert blank["cnpj"] == "12ABC345000101" and blank["name"] == "" and blank["phone"] is None
    assert blank["email"] is None and blank["opened_at"] is None

    spellings = {("jaragua do sul", "SC"): "Jaraguá do Sul"}
    assert li.display_city("JARAGUA DO SUL", "SC", spellings) == "Jaraguá do Sul"
    assert li.display_city("SAO BENTO DO SUL", "SC", spellings) == "Sao Bento do Sul"
    assert li.display_city("GUAJARA-MIRIM", "RO", spellings) == "Guajara-Mirim"
    assert li.display_city("SAO FELIPE D'OESTE", "RO", spellings) == "Sao Felipe D'oeste"


if __name__ == "__main__":
    check_parsing()
    print("test_lead_import OK")
```

- [ ] **Step 2: Run to verify it fails**

Run (from `backend/`): `python test_lead_import.py`
Expected: `ImportError: cannot import name 'lead_import'`

- [ ] **Step 3: Implement the parsing layer** — create `backend/app/lead_import.py`:

```python
"""Imports leads from the Receita Federal's open CNPJ data. Run from backend/:  python -m app.lead_import

A systemd timer runs it daily; it only does real work when the Receita published a new month or
the scope (states in seller_cities + Configurações' CNAE list) changed. Any error writes nothing.
Spec: docs/superpowers/specs/2026-10-16-prospeccao-crm-design.md (Importação)"""
import csv
import io
import zipfile
from datetime import date
from typing import Iterator

from .leads import normalize_cnpj
from .sales import _city_key

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
```

- [ ] **Step 4: Run the test**

Run: `python test_lead_import.py`
Expected: `test_lead_import OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/lead_import.py backend/test_lead_import.py
git commit -m "Lead import: parse Receita establishments, towns and city names"
```

---

### Task 2: Apply to the database and the `run()` orchestration

**Files:**
- Modify: `backend/app/lead_import.py`
- Modify: `backend/test_lead_import.py`

**Interfaces:**
- Consumes: `Lead`, `Contact`, `Customer`, `SellerCity`, `AppSettings`, `leads.customer_cnpjs`, `settings_store.get_app_settings`, `clock.today_br`.
- Produces:
  - `current_scope(db) -> tuple[set[str], set[str], str]` → `(states, cnaes, scope_text)`; `scope_text` like `"PR,SC|4781400"`
  - `apply(db, found: dict[str, dict], month: str, scope: str, today: date) -> int` (number of new leads; commits)
  - `run(db, latest_month: Callable[[], str], download: Callable[[str, str, str], None], parts: int = 10) -> str` → `"no-scope"`, `"up-to-date"` or `"imported {month}: {n} new"`. `download(month, file_name, dest_path)`.

- [ ] **Step 1: Write the failing test** — in `backend/test_lead_import.py`, add after `check_parsing`:

```python
def check_run():
    from datetime import timedelta

    from fastapi.testclient import TestClient

    from app import clock
    from app.database import SessionLocal
    from app.main import app
    from app.models import AppSettings, Contact, Customer, Lead, SellerCity, User

    today = date(2026, 10, 16)
    clock.today_br = lambda: today
    with TestClient(app):  # runs the startup: tables + settings row
        pass
    db = SessionLocal()
    ana = User(name="Ana", email="a@t.com", password_hash="x", role="seller")
    db.add(ana)
    db.flush()
    db.add(SellerCity(user_id=ana.id, city="Jaraguá do Sul", state="SC", city_key="jaragua do sul"))
    db.add(Customer(name="Já cliente", document="11.111.111/0001-11", city="Jaraguá do Sul", state="SC"))
    for cnpj, status in (("30000000000101", "discarded"), ("40000000000101", "new"), ("50000000000101", "new")):
        db.add(Lead(cnpj=cnpj, name=cnpj, city="Jaraguá do Sul", state="SC", city_key="jaragua do sul",
                    status=status, seen_at=today - timedelta(days=40)))
    db.flush()
    with_contact = db.query(Lead).filter_by(cnpj="50000000000101").one()
    db.add(Contact(user_id=ana.id, lead_id=with_contact.id, channel="call"))
    db.commit()

    files = {
        "Municipios.zip": [["8175", "JARAGUA DO SUL"], ["8047", "BLUMENAU"]],
        "Estabelecimentos0.zip": [
            estab(),                                             # Loja A
            estab(basico="20000000", fantasia=""),               # name from Empresas
            estab(basico="11111111", ordem="0001", dv="11"),     # already a customer
            estab(basico="30000000", fantasia="VOLTOU"),         # discarded before: stays discarded
            estab(basico="60000000", town="8047", situacao="08"),  # closed
        ],
        "Estabelecimentos3.zip": [estab(basico="12ABC345", fantasia="ALFA", town="8047")],  # Blumenau
        "Empresas2.zip": [["20000000", "LOJA B COMERCIO LTDA", "2062", "49", "1000,00", "01", ""]],
    }
    calls = []

    def download(month, name, dest):
        calls.append(name)
        if name == broken[0]:
            raise OSError("connection reset")
        make_zip(dest, files.get(name, []))

    def lead(cnpj):
        db.expire_all()
        return db.query(Lead).filter_by(cnpj=cnpj).one_or_none()

    # a failure mid-way writes nothing
    broken = ["Estabelecimentos5.zip"]
    try:
        li.run(db, lambda: "2026-10", download)
        raise AssertionError("download error must propagate")
    except OSError:
        pass
    assert lead("10000000000101") is None and lead("40000000000101") is not None
    assert db.query(AppSettings).first().last_lead_import_month is None

    broken = [""]
    assert li.run(db, lambda: "2026-10", download) == "imported 2026-10: 3 new"
    a = lead("10000000000101")
    assert (a.name, a.city, a.city_key, a.state, a.status) == ("LOJA A", "Jaraguá do Sul", "jaragua do sul", "SC", "new")
    assert lead("20000000000101").name == "LOJA B COMERCIO LTDA"
    assert lead("12ABC345000101").city == "Blumenau"
    assert lead("11111111000111") is None  # already a customer
    assert lead("30000000000101").status == "discarded" and lead("30000000000101").seen_at == today
    assert lead("40000000000101") is None  # gone from the Receita, no contacts
    assert lead("50000000000101") is not None  # gone, but has contacts: kept
    s = db.query(AppSettings).first()
    assert (s.last_lead_import_month, s.last_lead_import_scope) == ("2026-10", "SC|4781400")

    calls.clear()
    assert li.run(db, lambda: "2026-10", download) == "up-to-date"
    assert calls == []  # nothing downloaded

    s.lead_cnaes = "4781400,4642701"
    db.commit()
    assert li.run(db, lambda: "2026-10", download).startswith("imported 2026-10")  # scope changed
    assert db.query(AppSettings).first().last_lead_import_scope == "SC|4642701,4781400"

    db.query(SellerCity).delete()
    db.commit()
    assert li.run(db, lambda: "2026-11", download) == "no-scope"
    db.close()
```

and change the `__main__` block to:

```python
if __name__ == "__main__":
    check_parsing()
    check_run()
    print("test_lead_import OK")
```

- [ ] **Step 2: Run to verify it fails**

Run: `python test_lead_import.py`
Expected: `AttributeError: module 'app.lead_import' has no attribute 'run'`

- [ ] **Step 3: Implement apply + run** — in `backend/app/lead_import.py`, extend the imports:

```python
import csv
import io
import os
import tempfile
import zipfile
from datetime import date, datetime
from typing import Callable, Iterator

from sqlalchemy.orm import Session

from . import clock
from .leads import customer_cnpjs, normalize_cnpj
from .models import Contact, Customer, Lead, SellerCity
from .sales import _city_key
from .settings_store import get_app_settings
```

and append:

```python
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
    try:
        added = apply(db, found, month, scope, clock.today_br())
    except Exception:
        db.rollback()
        raise
    return f"imported {month}: {added} new"
```

- [ ] **Step 4: Run the test**

Run: `python test_lead_import.py`
Expected: `test_lead_import OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/lead_import.py backend/test_lead_import.py
git commit -m "Lead import: apply in one transaction, skip when month and scope are unchanged"
```

---

### Task 3: WebDAV fetch, command line entry point and the systemd timer

**Files:**
- Modify: `backend/app/config.py` (two settings)
- Modify: `backend/app/lead_import.py` (`latest_month`, `download`, `main`)
- Create: `backend/deploy/dimarcy-leads.service`, `backend/deploy/dimarcy-leads.timer`
- Modify: `README.md` (short "Importação de leads" section)
- Test: `backend/test_lead_import.py` (parsing of a PROPFIND response)

**Interfaces:**
- Produces: `parse_months(xml_text: str) -> list[str]`, `latest_month() -> str`, `download(month, name, dest) -> None`, `main() -> int`; module runnable with `python -m app.lead_import`.

- [ ] **Step 1: Write the failing test** — in `backend/test_lead_import.py`, add:

```python
def check_months():
    xml = """<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">
      <d:response><d:href>/public.php/webdav/</d:href></d:response>
      <d:response><d:href>/public.php/webdav/2026-09/</d:href></d:response>
      <d:response><d:href>/public.php/webdav/2026-10/</d:href></d:response>
      <d:response><d:href>/public.php/webdav/cnpj.tar.gz</d:href></d:response>
    </d:multistatus>"""
    assert li.parse_months(xml) == ["2026-09", "2026-10"]
```

and call `check_months()` first in the `__main__` block.

- [ ] **Step 2: Run to verify it fails**

Run: `python test_lead_import.py`
Expected: `AttributeError: module 'app.lead_import' has no attribute 'parse_months'`

- [ ] **Step 3: Add the settings** — in `backend/app/config.py`, inside `Settings`, after `notify_email`:

```python

    # Receita Federal open CNPJ data (lead import). A public Nextcloud share read over WebDAV;
    # the Receita has moved it before, so both are overridable from .env.
    receita_webdav_url: str = "https://arquivos.receitafederal.gov.br/public.php/webdav"
    receita_share_token: str = "YggdBLfdninEJX9"
```

- [ ] **Step 4: Implement fetch + main** — in `backend/app/lead_import.py`, add to the imports:

```python
import base64
import re
import shutil
import sys
import urllib.request
import xml.etree.ElementTree as ET

from .config import settings
from .database import SessionLocal
```

and append:

```python
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
```

- [ ] **Step 5: Run the test**

Run: `python test_lead_import.py`
Expected: `test_lead_import OK`

- [ ] **Step 6: Check the real share once (cheap: only the listing)**

Run: `python -c "from app.lead_import import latest_month; print(latest_month())"`
Expected: the newest month, e.g. `2026-10`. If it fails with 401/404, the share moved: find the new token on the Receita's "Dados Abertos CNPJ" page and set `RECEITA_SHARE_TOKEN` / `RECEITA_WEBDAV_URL` in `.env`.

- [ ] **Step 7: systemd units** — create `backend/deploy/dimarcy-leads.service`:

```ini
[Unit]
Description=Di Marcy - importação de leads da Receita Federal
After=network-online.target

[Service]
Type=oneshot
User=opc
WorkingDirectory=/opt/dimarcy/backend
ExecStart=/opt/dimarcy/backend/.venv/bin/python -m app.lead_import
Nice=10
```

and `backend/deploy/dimarcy-leads.timer`:

```ini
[Unit]
Description=Roda a importação de leads todo dia de madrugada

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 8: README** — append to `README.md`:

```markdown
## Importação de leads (Prospecção)

`python -m app.lead_import` (em `backend/`) baixa os dados abertos de CNPJ da Receita e atualiza a tabela
`leads`. Só trabalha de verdade quando sai um mês novo ou quando mudam as UFs das regiões / os CNAEs em
Configurações; nos outros dias sai na hora. Leva 20–40 min e baixa ~7 GB (um arquivo por vez).

Na VM (o backend precisa ter subido uma vez depois da atualização, para criar as tabelas):

    sudo cp /opt/dimarcy/backend/deploy/dimarcy-leads.* /etc/systemd/system/
    sudo systemctl daemon-reload && sudo systemctl enable --now dimarcy-leads.timer
    sudo systemctl start dimarcy-leads.service   # primeira importação, sem esperar a madrugada
    journalctl -u dimarcy-leads -n 20            # resultado

Se a Receita mudar o endereço, ajuste `RECEITA_WEBDAV_URL` / `RECEITA_SHARE_TOKEN` no `.env`.
```

- [ ] **Step 9: Manual verification (local, one real import)** — with at least one seller city in SC saved through the app (Plano 1 API or Plano 3 screen), run from `backend/`:

Run: `python -m app.lead_import`
Expected (after 20–40 min): `[lead_import] imported 2026-10: N new` with N around 50–60 thousand for SC. Then:
`python -c "from app.database import SessionLocal; from app.models import Lead; db=SessionLocal(); print([ (l.name, l.city, l.phone) for l in db.query(Lead).filter(Lead.city_key=='jaragua do sul').limit(5)])"`
Expected: five Jaraguá do Sul stores with plausible names and phones. Report the numbers to the user.

- [ ] **Step 10: Commit**

```bash
git add backend/app/config.py backend/app/lead_import.py backend/test_lead_import.py backend/deploy README.md
git commit -m "Lead import: Receita WebDAV client, CLI entry point and daily systemd timer"
```
