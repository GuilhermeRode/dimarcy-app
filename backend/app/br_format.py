"""Brazilian customer data: CPF/CNPJ and phone formatting, and pulling the state registration (IE)
out of free-text notes. Same masks as maskDocument/maskPhone in frontend/src/format.js."""
import re


def _digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


def format_document(v: str | None) -> str | None:
    """000.000.000-00 (CPF) or 00.000.000/0000-00 (CNPJ); anything else is kept as typed."""
    d = _digits(v)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return v.strip() if v else v


def format_phone(v: str | None) -> str | None:
    """(00) 0000-0000 or (00) 00000-0000, dropping a leading country code 55 or trunk 0. An old 8-digit
    mobile (starting with 6-9) gets the 9th digit every Brazilian mobile has had since 2016."""
    d = _digits(v).lstrip("0")  # trunk 0 ("047 3333-4444", "0xx47 ...") or "0055 ..."; no DDD starts with 0
    if len(d) > 11 and d.startswith("55"):
        d = d[2:]
    if len(d) == 10 and d[2] in "6789":
        d = d[:2] + "9" + d[2:]
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    return v.strip() if v else v


# Inscrição estadual mask per state (Sintegra layouts), each 0 is a digit; some states have two
# lengths. Keep in sync with IE_MASKS in frontend/src/format.js.
IE_MASKS = {
    "AC": ["00.000.000/000-00"], "AL": ["000000000"], "AM": ["00.000.000-0"], "AP": ["000000000"],
    "BA": ["000000-00", "0000000-00"], "CE": ["00000000-0"], "DF": ["00000000000-00"], "ES": ["000.000.00-0"],
    "GO": ["00.000.000-0"], "MA": ["000000000"], "MG": ["000.000.000/0000"], "MS": ["00.000.000-0"],
    "MT": ["0000000000-0"], "PA": ["00-000000-0"], "PB": ["00000000-0"], "PE": ["0000000-00", "00.0.000.0000000-0"],
    "PI": ["000000000"], "PR": ["00000000-00"], "RJ": ["00.000.00-0"], "RN": ["00.000.000-0", "00.0.000.000-0"],
    "RO": ["0000000000000-0"], "RR": ["00000000-0"], "RS": ["000/0000000"], "SC": ["000.000.000"],
    "SE": ["00000000-0"], "SP": ["000.000.000.000"], "TO": ["000000000", "00000000000"],
}


def format_state_registration(v: str | None, uf: str | None) -> str | None:
    """IE in its state's mask when the digit count matches one; ISENTO and anything else kept as typed."""
    if not v or v.strip().upper().startswith("ISENT"):
        return v.strip().upper() if v else v
    d = _digits(v)
    for mask in IE_MASKS.get((uf or "").upper(), []):
        if mask.count("0") == len(d):
            it = iter(d)
            return "".join(next(it) if ch == "0" else ch for ch in mask)
    return v.strip()


# "IE: 254.123.456", "I.E. 123456789", "Inscrição Estadual nº 123/456", "Insc. Est. isento"
_IE = re.compile(
    r"\b(?:inscri[cç][aã]o\s+estadual|insc(?:r)?\.?\s*est(?:adual)?\.?|I\.?\s?E\b\.?)"
    r"\s*(?:n[º°o]?\.?\s*)?[:=\-–]?\s*"
    r"(isent[oa]|\d[\d.\-/ ]*\d|\d)",
    re.IGNORECASE,
)


def extract_state_registration(notes: str | None) -> tuple[str | None, str | None]:
    """(IE found in the notes or None, notes without it — None when nothing else is left)."""
    m = _IE.search(notes or "")
    if not m:
        return None, notes
    value = m.group(1).strip()
    value = "ISENTO" if value.lower().startswith("isent") else value
    rest = (notes[:m.start()] + notes[m.end():])
    # tidy the hole left behind: separators at the edges and empty lines
    rest = "\n".join(line.strip(" \t-–;,|") for line in rest.splitlines())
    rest = re.sub(r"\n{2,}", "\n", rest).strip(" \n-–;,|")
    return value, rest or None
