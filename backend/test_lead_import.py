"""Receita importer self-check, no internet: small zips built here. Run from backend/:  python test_lead_import.py
Uses a throwaway SQLite file, never dimarcy.db."""
import csv
import io
import os
import tempfile
import zipfile
from datetime import date, datetime

tmp = tempfile.mkdtemp()
db_file = os.path.join(tmp, "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from app import lead_import as li  # noqa: E402

PGFN_HEADER = ["CPF_CNPJ", "TIPO_PESSOA", "TIPO_DEVEDOR", "NOME_DEVEDOR", "UF_DEVEDOR", "UNIDADE_RESPONSAVEL",
               "ENTIDADE_RESPONSAVEL", "UNIDADE_INSCRICAO", "NUMERO_INSCRICAO", "TIPO_SITUACAO_INSCRICAO",
               "SITUACAO_INSCRICAO", "RECEITA_PRINCIPAL", "DATA_INSCRICAO", "INDICADOR_AJUIZADO", "VALOR_CONSOLIDADO"]
pgfn_files: dict[str, list] = {}  # PGFN file name -> rows; no internet in tests
li.latest_quarter = lambda: "2026_trimestre_03"
li.download_pgfn = lambda quarter, name, dest: make_zip(dest, [PGFN_HEADER] + pgfn_files.get(name, []))


def debt(cnpj, situation="Em cobrança", uf="SC"):
    return [cnpj, "Pessoa jurídica", "Principal", "X", uf, "", "PGFN", "", "1", situation, "", "", "", "NAO", "1000.00"]


def make_zip(path, rows, inner="K3241.K03200Y3.D61010.ESTABELE"):
    buf = io.StringIO()
    csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n").writerows(rows)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(inner, buf.getvalue().encode("latin-1"))
    return path


def estab(basico="10000000", ordem="0001", dv="01", fantasia="LOJA A", situacao="02", inicio="20250101",
          cnae="4781400", uf="SC", town="8175", ddd="47", phone="33330000", email="Loja@Mail.com",
          street="QUADRA 11;LOTE 04", number="10", bairro="CENTRO", cep="89251000", matriz="1"):
    row = [""] * 30
    row[0], row[1], row[2], row[3], row[4], row[5] = basico, ordem, dv, matriz, fantasia, situacao
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
    off = {"sizes": set(), "exclude_mei": False, "head_office_only": False, "require_contact": False, "min_age_months": 0,
           "area_codes": set()}
    on = {"sizes": {"01", "03"}, "exclude_mei": True, "head_office_only": True, "require_contact": True, "min_age_months": 6,
          "area_codes": set()}
    now = date(2026, 10, 16)
    lead = li.pick(estab(), cn, st, towns, on, now)
    assert lead == {"cnpj": "10000000000101", "basico": "10000000", "name": "LOJA A", "phone": None,
                    "email": "loja@mail.com", "address": "RUA QUADRA 11;LOTE 04, 10, CENTRO, 89251000",
                    "raw_city": "JARAGUA DO SUL", "state": "SC", "opened_at": date(2025, 1, 1)}, lead
    assert li.pick(estab(situacao="08"), cn, st, towns, off, now) is None
    assert li.pick(estab(cnae="4642701"), cn, st, towns, off, now) is None
    assert li.pick(estab(uf="PR"), cn, st, towns, off, now) is None
    assert li.pick(estab(town="7777"), cn, st, towns, off, now) is None  # unknown town: can't place it in a region
    blank = li.pick(estab(basico="12ABC345", fantasia=" ", phone="", email="", inicio=""), cn, st, towns, off, now)
    assert blank["cnpj"] == "12ABC345000101" and blank["name"] == "" and blank["phone"] is None
    assert blank["email"] is None and blank["opened_at"] is None
    assert li.pick(estab(basico="12ABC345", phone="", email="", inicio=""), cn, st, towns, on, now) is None
    assert li.pick(estab(matriz="2"), cn, st, towns, on, now) is None
    assert li.pick(estab(inicio="20260701"), cn, st, towns, on, now) is None
    assert li.pick(estab(inicio="20260701"), cn, st, towns, {**on, "min_age_months": 3}, now)
    assert li.pick(estab(phone="", email=""), cn, st, towns, {**on, "require_contact": False}, now)
    assert li.pick(estab(phone=""), cn, st, towns, on, now) is None  # an e-mail alone isn't enough: sellers use WhatsApp
    assert li.pick(estab(ddd="047"), cn, st, towns, {**on, "area_codes": {"47", "49"}}, now)
    assert li.pick(estab(ddd="48"), cn, st, towns, {**on, "area_codes": {"47", "49"}}, now) is None

    spellings = {("jaragua do sul", "SC"): "Jaraguá do Sul"}
    assert li.display_city("JARAGUA DO SUL", "SC", spellings) == "Jaraguá do Sul"
    assert li.display_city("SAO BENTO DO SUL", "SC", spellings) == "Sao Bento do Sul"
    assert li.display_city("GUAJARA-MIRIM", "RO", spellings) == "Guajara-Mirim"
    assert li.display_city("SAO FELIPE D'OESTE", "RO", spellings) == "Sao Felipe D'oeste"

    assert (li.capital("10000,00"), li.capital("1.500,50"), li.capital(""), li.capital("x")) == (10000, 1500.5, 0, 0)
    z = make_zip(os.path.join(tmp, "pgfn.zip"), [PGFN_HEADER, debt("10.000.000/0001-01"), debt("20.000.000/0001-01", "Benefício Fiscal"),
                                                 debt("30.000.000/0001-01", uf="SP"), debt("40.000.000/0001-01"), ["short"]])
    assert li.debtors(z, {"10000000", "20000000", "30000000"}, {"SC"}) == {"10000000"}
    short_header = [c for c in PGFN_HEADER if c not in ("ENTIDADE_RESPONSAVEL", "UNIDADE_INSCRICAO")]  # Não Previdenciário
    z = make_zip(os.path.join(tmp, "pgfn2.zip"), [short_header, ["10.000.000/0001-01", "", "", "", "SC", "", "1", "Em cobrança"]])
    assert li.debtors(z, {"10000000"}, {"SC"}) == {"10000000"}


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
        "Empresas2.zip": [["20000000", "LOJA B COMERCIO LTDA", "2062", "49", "1000,00", "01", ""],
                          ["10000000", "LOJA A LTDA", "2062", "49", "1000,00", "01", ""],
                          ["30000000", "VOLTOU LTDA", "2062", "49", "1000,00", "03", ""],
                          ["12ABC345", "ALFA LTDA", "2062", "49", "1000,00", "01", ""]],
        "Simples.zip": [["10000000", "S", "", "", "N", "", ""], ["20000000", "N", "", "", "N", "", ""]],
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
    assert (a.name, a.city, a.city_key, a.state, a.status) == ("LOJA A", "Jaraguá do Sul", "jaragua do sul", "SC", "pending")
    assert a.size == "me"
    assert lead("20000000000101").name == "LOJA B COMERCIO LTDA"
    assert lead("12ABC345000101").city == "Blumenau"
    assert lead("11111111000111") is None  # already a customer
    assert lead("30000000000101").status == "discarded" and lead("30000000000101").seen_at == today
    assert lead("40000000000101") is None  # gone from the Receita, no contacts
    assert lead("50000000000101") is not None  # gone, but has contacts: kept
    s = db.query(AppSettings).first()
    assert (s.last_lead_import_month, s.last_lead_import_scope) == ("2026-10", "PR,RS,SC|4781400|01,03|mei1|ho1|ct1|age6")

    calls.clear()
    assert li.run(db, lambda: "2026-10", download) == "up-to-date"
    assert calls == []  # nothing downloaded

    s.lead_cnaes = "4781400,4642701"
    db.commit()
    assert li.run(db, lambda: "2026-10", download).startswith("imported 2026-10")  # scope changed
    assert db.query(AppSettings).first().last_lead_import_scope == "PR,RS,SC|4642701,4781400|01,03|mei1|ho1|ct1|age6"
    s.lead_area_codes = "47"  # every test lead is "47": same leads, but a new scope
    db.commit()
    assert li.run(db, lambda: "2026-10", download).startswith("imported 2026-10")
    assert db.query(AppSettings).first().last_lead_import_scope.endswith("|age6|ddd47")

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
    only = {"Municipios.zip": towns, "Estabelecimentos0.zip": [estab(basico="70000000", fantasia="NARROW", cnae="4642701")],
            "Empresas0.zip": [["70000000", "N", "", "", "", "03", ""]]}
    s = db.query(AppSettings).first()
    s.lead_cnaes = "4642701"
    db.commit()
    assert li.run(db, lambda: "2026-10", lambda month, name, dest: make_zip(dest, only.get(name, []))).startswith("imported 2026-10")
    assert lead("70000000000101") is not None and lead("10000000000101") is None

    # --force runs even when month and scope are unchanged
    s = db.query(AppSettings).first()
    s.lead_cnaes = "4781400"
    db.commit()
    li.run(db, lambda: "2026-10", download)
    assert li.run(db, lambda: "2026-10", download) == "up-to-date"
    assert li.run(db, lambda: "2026-10", download, force=True).startswith("imported 2026-10")

    s = db.query(AppSettings).first()
    s.lead_states = ""
    db.commit()
    assert li.run(db, lambda: "2026-11", download) == "no-scope"
    s.lead_states = "PR,RS,SC"
    db.commit()
    db.close()


def check_filters():
    from app import clock
    from app.database import SessionLocal
    from app.models import AppSettings, Lead, SellerCity, User

    clock.today_br = lambda: date(2026, 10, 16)
    db = SessionLocal()
    db.query(SellerCity).delete()
    db.query(Lead).delete()
    bia = User(name="Bia", email="b@t.com", password_hash="x", role="seller")
    db.add(bia)
    db.flush()
    db.add(SellerCity(user_id=bia.id, city="Jaraguá do Sul", state="SC", city_key="jaragua do sul"))
    s = db.query(AppSettings).first()
    s.lead_cnaes, s.last_lead_import_month, s.last_lead_import_scope = "4781400", None, None
    db.commit()
    assert (s.lead_sizes, s.lead_exclude_mei, s.lead_head_office_only, s.lead_require_contact, s.lead_min_age_months) \
        == ("01,03", True, True, True, 6)

    def b(n):
        return f"{n}0000000"[:8]
    files = {
        "Municipios.zip": [["8175", "JARAGUA DO SUL"]],
        "Estabelecimentos0.zip": [
            estab(basico=b(1), fantasia="ME"), estab(basico=b(2), fantasia="EPP"),
            estab(basico=b(3), fantasia="FILIAL", ordem="0002", matriz="2"),
            estab(basico=b(4), fantasia="SEM CONTATO", phone="", email=""),
            estab(basico=b(5), fantasia="NOVA", inicio="20260701"),
            estab(basico=b(6), fantasia="GRANDE"), estab(basico=b(7), fantasia="NAOINF"),
            estab(basico=b(8), fantasia="MEI"), estab(basico=b(9), fantasia="DEVEDORA"),
        ],
        "Empresas0.zip": [[b(1), "x", "", "", "", "01", ""], [b(2), "x", "", "", "", "03", ""],
                          [b(3), "x", "", "", "", "01", ""], [b(4), "x", "", "", "", "01", ""],
                          [b(5), "x", "", "", "", "01", ""], [b(6), "x", "", "", "", "05", ""],
                          [b(7), "x", "", "", "", "00", ""], [b(8), "x", "", "", "", "01", ""],
                          [b(9), "x", "", "", "5000,00", "01", ""]],
        "Simples.zip": [[b(8), "S", "", "", "S", "", ""], [b(1), "S", "", "", "N", "", ""]],
    }

    def download(month, name, dest):
        make_zip(dest, files.get(name, []))

    def leads():
        db.expire_all()
        return {l.name: l for l in db.query(Lead)}

    pgfn_files["Dados_abertos_FGTS.zip"] = [debt(f"{b(9)[:2]}.{b(9)[2:5]}.{b(9)[5:]}/0001-01"),
                                            debt(f"{b(1)}000101", "Benefício Fiscal")]  # in installments: no flag
    assert li.run(db, lambda: "2026-10", download) == "imported 2026-10: 3 new"
    got = leads()
    assert set(got) == {"ME", "EPP", "DEVEDORA"}, set(got)  # debt and capital rank leads, never remove them
    assert (got["ME"].size, got["EPP"].size) == ("me", "epp")
    assert (got["DEVEDORA"].in_debt, float(got["DEVEDORA"].capital)) == (True, 5000)
    assert got["ME"].in_debt is False and got["ME"].capital == 0
    assert all(l.status == "pending" for l in got.values())

    s = db.query(AppSettings).first()
    s.lead_exclude_mei = False
    db.commit()
    assert li.run(db, lambda: "2026-10", download).startswith("imported 2026-10")  # scope changed
    got = leads()
    assert set(got) == {"ME", "EPP", "MEI", "DEVEDORA"} and got["MEI"].size == "mei" and got["MEI"].status == "pending"

    # a refreshed lead whose porte changed gets its size updated
    files["Empresas0.zip"][0][5] = "03"
    assert li.run(db, lambda: "2026-10", download, force=True).startswith("imported 2026-10")
    assert leads()["ME"].size == "epp"

    # PGFN down: the import still runs, debt marked as not checked
    real_pgfn = li.download_pgfn
    li.download_pgfn = lambda quarter, name, dest: (_ for _ in ()).throw(OSError("pgfn down"))
    try:
        assert li.run(db, lambda: "2026-10", download, force=True).startswith("imported 2026-10")
    finally:
        li.download_pgfn = real_pgfn
    assert leads()["DEVEDORA"].in_debt is None
    assert li.run(db, lambda: "2026-10", download, force=True).startswith("imported 2026-10")

    # run status: started_at cleared, error kept after a failure and cleared by the next success
    def failing(month, name, dest):
        raise OSError("boom")
    try:
        li.run_and_record(db, lambda: "2026-11", failing)
        raise AssertionError("must raise")
    except OSError:
        pass
    db.expire_all()
    s = db.query(AppSettings).first()
    assert s.lead_import_started_at is None and "boom" in s.lead_import_error
    assert li.run_and_record(db, lambda: "2026-11", download).startswith("imported 2026-11")
    db.expire_all()
    s = db.query(AppSettings).first()
    assert s.lead_import_started_at is None and s.lead_import_error is None
    # a non-forced (scheduled) run leaves a fresh UI run's lock alone; --force goes ahead
    stamp = li.utcnow()
    s.lead_import_started_at = stamp
    db.commit()
    assert li.run_and_record(db, lambda: "2026-12", download) == "already-running"
    db.expire_all()
    assert db.query(AppSettings).first().lead_import_started_at == stamp
    assert li.run_and_record(db, lambda: "2026-12", download, force=True).startswith("imported 2026-12")

    # a lock held by a dead process does not block a scheduled run; startup clears it with a message
    real_alive = li.pid_alive
    db.expire_all()
    s = db.query(AppSettings).first()
    s.lead_import_started_at, s.lead_import_pid = li.utcnow(), 99999999
    db.commit()
    li.pid_alive = lambda pid: False
    try:
        assert not li.import_running(s)
        li.clear_interrupted(db)
        db.expire_all()
        s = db.query(AppSettings).first()
        assert s.lead_import_started_at is None and s.lead_import_pid is None and "reiniciou" in s.lead_import_error
        s.lead_import_started_at, s.lead_import_pid = li.utcnow(), 99999999
        db.commit()
        li.pid_alive = lambda pid: True
        assert li.import_running(s)
        li.clear_interrupted(db)
        assert db.query(AppSettings).first().lead_import_started_at is not None
    finally:
        li.pid_alive = real_alive
    s = db.query(AppSettings).first()
    s.lead_import_started_at, s.lead_import_pid = None, None
    db.commit()

    # main(["--force"]) runs a forced import and returns 0; a failure returns 1
    real_months, real_dl = li.latest_month, li.download
    li.latest_month, li.download = (lambda: "2027-01"), download
    try:
        assert li.main(["--force"]) == 0
        li.download = failing
        assert li.main(["--force"]) == 1
    finally:
        li.latest_month, li.download = real_months, real_dl
    db.expire_all()
    assert db.query(AppSettings).first().last_lead_import_month == "2027-01"
    db.close()


if __name__ == "__main__":
    check_months()
    check_parsing()
    check_run()
    check_filters()
    print("test_lead_import OK")
