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
