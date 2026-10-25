"""Company data from a CNPJ (Receita Federal's public registry) to pre-fill the customer form.
BrasilAPI first (free, no published limit); the CNPJá public API (5 queries/min per IP) if it fails.
Neither returns the inscrição estadual — that one is still typed by the user."""
import json
import re
import urllib.error
import urllib.request

from .br_format import format_phone

BRASILAPI_URL = "https://brasilapi.com.br/api/cnpj/v1/{}"
CNPJA_URL = "https://open.cnpja.com/office/{}"
USER_AGENT = "DiMarcyPedidos/1.0"  # urllib's default UA is blocked by some CDNs as a bot


class NotFound(Exception):
    pass


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            raise NotFound() from e
        raise


_SMALL = {"Da", "De", "Do", "Das", "Dos", "E"}
_UPPER = re.compile(r"^(?:[IVX]+|AC|AL|AM|AP|BA|BR|CE|DF|ES|GO|MA|MG|MS|MT|PA|PB|PE|PI|PR|RJ|RN|RO|RR|RS|SC|SP|TO)$")


def _title(s: str | None) -> str:
    """'RIO DO SUL' -> 'Rio do Sul', keeping 'CENTRO II' and 'SC 486' (BrasilAPI sends names in capitals)."""
    words = (s or "").strip().upper().split()
    return " ".join(w if _UPPER.match(w) else w.lower() if i and w.title() in _SMALL else w.title()
                    for i, w in enumerate(words))


def _address(street, number, complement, district, zip_code) -> str:
    cep = re.sub(r"\D", "", zip_code or "")
    parts = [", ".join(p for p in (_title(street), (number or "").strip()) if p),
             _title(complement), _title(district), f"CEP {cep[:5]}-{cep[5:]}" if len(cep) == 8 else ""]
    return " - ".join(p for p in parts if p)


def from_brasilapi(d: dict) -> dict:
    return {
        "name": (d.get("razao_social") or "").strip(),
        "trade_name": _title(d.get("nome_fantasia")),
        "address": _address(d.get("logradouro"), d.get("numero"), d.get("complemento"), d.get("bairro"), d.get("cep")),
        "city": _title(d.get("municipio")),
        "state": (d.get("uf") or "").upper(),
        "phone": format_phone(d.get("ddd_telefone_1")) or "",
        "email": (d.get("email") or "").strip().lower(),
        "status": (d.get("descricao_situacao_cadastral") or "").upper(),
    }


def from_cnpja(d: dict) -> dict:
    a = d.get("address") or {}
    phone = next(iter(d.get("phones") or []), {})
    email = next(iter(d.get("emails") or []), {})
    return {
        "name": ((d.get("company") or {}).get("name") or "").strip(),
        "trade_name": (d.get("alias") or "").strip(),
        "address": _address(a.get("street"), a.get("number"), a.get("details"), a.get("district"), a.get("zip")),
        "city": (a.get("city") or "").strip(),
        "state": (a.get("state") or "").upper(),
        "phone": format_phone(f"{phone.get('area', '')}{phone.get('number', '')}") or "",
        "email": (email.get("address") or "").strip().lower(),
        "status": ((d.get("status") or {}).get("text") or "").upper(),
    }


def lookup(cnpj: str) -> dict:
    """Normalized company data; NotFound if no service knows the CNPJ, other errors if both are down."""
    errors = []
    for url, convert in ((BRASILAPI_URL, from_brasilapi), (CNPJA_URL, from_cnpja)):
        try:
            return convert(_get(url.format(cnpj)))
        except NotFound:
            errors.append(None)
        except Exception as e:  # timeout, rate limit, service down: try the next one
            print(f"[cnpj] {url.format(cnpj)} failed: {e}")
            errors.append(e)
    if all(e is None for e in errors):
        raise NotFound()
    raise RuntimeError("CNPJ services unavailable")
