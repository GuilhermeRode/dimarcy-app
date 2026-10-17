"""Prospecting rules shared by the leads/contacts routers, the dashboard and the importer.

A lead's seller is never stored: it's the active seller whose region (seller_cities) has the
lead's city, so moving a city between sellers moves its leads with no migration.
Spec: docs/superpowers/specs/2026-10-16-prospeccao-crm-design.md"""
import re


def normalize_cnpj(value: str | None) -> str:
    """Letters and digits only, uppercase — CNPJs may be alphanumeric since July 2026."""
    return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()
