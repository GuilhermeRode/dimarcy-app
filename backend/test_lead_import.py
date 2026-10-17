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
