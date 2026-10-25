"""CNPJ lookup self-check (no network: the services are faked). Run from backend/:  python test_cnpj_lookup.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile
import urllib.error

os.environ.update(DATABASE_URL=f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'test.db')}",
                  ADMIN_EMAIL="admin@test.com", ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

from app import cnpj_lookup as cl  # noqa: E402
from app.main import app  # noqa: E402

BRASILAPI = {"razao_social": "MALHARIA EXEMPLO LTDA", "nome_fantasia": "MALHAS DO SUL", "logradouro": "RUA DAS FLORES",
             "numero": "120", "complemento": "SALA 2", "bairro": "CENTRO", "municipio": "RIO DO SUL", "uf": "sc",
             "cep": "89160000", "ddd_telefone_1": "4735210000", "email": None, "descricao_situacao_cadastral": "ATIVA"}
CNPJA = {"company": {"name": "MALHARIA EXEMPLO LTDA"}, "alias": "Malhas do Sul", "status": {"text": "Ativa"},
         "address": {"street": "Rua das Flores", "number": "120", "details": None, "district": "Centro",
                     "city": "Rio do Sul", "state": "SC", "zip": "89160000"},
         "phones": [{"area": "47", "number": "35210000"}], "emails": [{"address": "Contato@Exemplo.com.br"}]}

expected = {"name": "MALHARIA EXEMPLO LTDA", "trade_name": "Malhas do Sul",
            "address": "Rua das Flores, 120 - Sala 2 - Centro - CEP 89160-000", "city": "Rio do Sul", "state": "SC",
            "phone": "(47) 3521-0000", "email": "", "status": "ATIVA"}
assert cl.from_brasilapi(BRASILAPI) == expected, cl.from_brasilapi(BRASILAPI)
assert cl.from_cnpja(CNPJA) == {**expected, "address": "Rua das Flores, 120 - Centro - CEP 89160-000",
                                "email": "contato@exemplo.com.br"}, cl.from_cnpja(CNPJA)


assert cl._title("ROD DEPUTADO ANTONIO HEIL SC 486") == "Rod Deputado Antonio Heil SC 486"
assert cl._title("CENTRO II") == "Centro II" and cl._title("DE ONDE") == "De Onde"


def fake(responses):
    def get(url):
        r = responses["brasilapi" if "brasilapi" in url else "cnpja"]
        if isinstance(r, Exception):
            raise r
        return r
    cl._get = get


fake({"brasilapi": BRASILAPI, "cnpja": CNPJA})
assert cl.lookup("12345678000190")["city"] == "Rio do Sul"
fake({"brasilapi": urllib.error.URLError("timeout"), "cnpja": CNPJA})  # BrasilAPI down: CNPJá answers
assert cl.lookup("12345678000190")["email"] == "contato@exemplo.com.br"
fake({"brasilapi": cl.NotFound(), "cnpja": cl.NotFound()})
try:
    cl.lookup("12345678000190")
    raise AssertionError("expected NotFound")
except cl.NotFound:
    pass
fake({"brasilapi": urllib.error.URLError("down"), "cnpja": urllib.error.URLError("down")})
try:
    cl.lookup("12345678000190")
    raise AssertionError("expected RuntimeError")
except RuntimeError:
    pass

# the API route: never more than a quiet 4xx/503 the form can show, and only for logged-in users
with TestClient(app) as c:
    assert c.get("/api/customers/cnpj/12345678000190").status_code == 401
    token = c.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin-pass-123"}).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    fake({"brasilapi": BRASILAPI, "cnpja": CNPJA})
    r = c.get("/api/customers/cnpj/12345678000190", headers=h)  # the form sends digits only
    assert r.status_code == 200 and r.json()["phone"] == "(47) 3521-0000", r.text
    assert c.get("/api/customers/cnpj/123", headers=h).status_code == 400
    fake({"brasilapi": cl.NotFound(), "cnpja": cl.NotFound()})
    assert c.get("/api/customers/cnpj/12345678000190", headers=h).status_code == 404
    fake({"brasilapi": urllib.error.URLError("down"), "cnpja": urllib.error.URLError("down")})
    assert c.get("/api/customers/cnpj/12345678000190", headers=h).status_code == 503
print("cnpj lookup OK")
