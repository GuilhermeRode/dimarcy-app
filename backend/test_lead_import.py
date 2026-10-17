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
    few = make_zip(os.path.join(tmp, "few.zip"), [["1", "2"], estab(), ["3"]])
    assert list(li.read_rows(few, 30)) == [estab()]  # a few malformed rows are skipped (warning on stderr)
    bad = make_zip(os.path.join(tmp, "bad.zip"), [["1", "2"]] * 1001)
    try:
        list(li.read_rows(bad, 30))
        raise AssertionError("more than 1000 malformed rows must raise")
    except ValueError:
        pass

    attempts, naps = [], []
    class Boom(Exception):
        pass
    orig = li.urllib.request.urlopen
    def failing(*a, **k):
        attempts.append(1)
        raise Boom("down")
    li.urllib.request.urlopen = failing
    try:
        li.download("2026-10", "x.zip", os.path.join(tmp, "x.zip"), sleep=naps.append)
        raise AssertionError("download must give up")
    except RuntimeError as e:
        assert "2026-10/x.zip" in str(e) and isinstance(e.__cause__, Boom)
    finally:
        li.urllib.request.urlopen = orig
    assert len(attempts) == 3 and naps == [30, 30]

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


def check_months():
    xml = """<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">
      <d:response><d:href>/public.php/webdav/</d:href></d:response>
      <d:response><d:href>/public.php/webdav/2026-09/</d:href></d:response>
      <d:response><d:href>/public.php/webdav/2026-10/</d:href></d:response>
      <d:response><d:href>/public.php/webdav/cnpj.tar.gz</d:href></d:response>
    </d:multistatus>"""
    assert li.parse_months(xml) == ["2026-09", "2026-10"]


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

    # a run that finds nothing is refused: leads and the stamped month stay as they were
    n_leads = db.query(Lead).count()
    towns = files["Municipios.zip"]
    try:
        li.run(db, lambda: "2026-11", lambda month, name, dest: make_zip(dest, towns if name == "Municipios.zip" else []))
        raise AssertionError("an empty import must raise")
    except RuntimeError:
        pass
    db.expire_all()
    assert db.query(Lead).count() == n_leads
    assert db.query(AppSettings).first().last_lead_import_month == "2026-10"

    # narrowing the scope may shrink the result below half of the current leads: that is not a bad download
    only = {"Municipios.zip": towns, "Estabelecimentos0.zip": [estab(basico="70000000", fantasia="NARROW", cnae="4642701")]}
    s = db.query(AppSettings).first()
    s.lead_cnaes = "4642701"
    db.commit()
    assert li.run(db, lambda: "2026-10", lambda month, name, dest: make_zip(dest, only.get(name, []))).startswith("imported 2026-10")
    assert lead("70000000000101") is not None and lead("10000000000101") is None

    db.query(SellerCity).delete()
    db.commit()
    assert li.run(db, lambda: "2026-11", download) == "no-scope"
    db.close()


if __name__ == "__main__":
    check_months()
    check_parsing()
    check_run()
    print("test_lead_import OK")
