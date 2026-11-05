"""Procura na base aberta da Receita o CNPJ de lojas que só temos pelo nome (rankings do Google Maps/Instagram).
Só lê: não grava nada no banco. Sem os filtros da importação (CNAE, MEI, matriz, telefone, idade), para mostrar
por que a loja não virou lead.

Entrada: JSON com [{"city", "state", "name", "phone", "ig"}, ...]. Saída: JSON com os candidatos de cada loja.
Compara nas cidades das lojas: nome fantasia ou razão social (sem "loja", "moda", "boutique"...),
telefone da Receita (8 últimos dígitos) e o @ do Instagram contra o e-mail/nome.

Uso (na pasta do backend, com o Python do app; baixa ~5 GB da Receita, um arquivo por vez, ~30-60 min):
    nice .venv/bin/python scripts/find_store_cnpjs.py lojas.json resultado.json
"""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.lead_import import (COMPANY_COLUMNS, ESTAB_COLUMNS, SIMPLES_COLUMNS, download, latest_month,  # noqa: E402
                             parse_towns, read_rows)
from app.leads import customer_cnpjs, receita_phone  # noqa: E402
from app.models import Lead  # noqa: E402
from app.sales import _city_key  # noqa: E402

CLOTHING = "4781400"
STOP = set("loja lojas moda modas boutique store feminina feminino femininas mulher fashion concept closet de da do das "
           "dos e the by vestuario acessorios multimarcas multimarca filial oficial roupas confeccoes comercio ltda me "
           "eireli epp mix and".split())


def norm(text):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", _city_key(text or "")).split())


def digits(text):
    return re.sub(r"\D", "", text or "")


class Store:
    def __init__(self, i, s):
        self.i, self.s = i, s
        toks = norm(s["name"]).split()
        city = set(norm(s["city"]).split())
        core = [t for t in toks if t not in STOP]
        core = [t for t in core if t not in city] or core
        self.core, self.comp, self.full = set(core), "".join(core), "".join(toks)
        self.phone = digits(s.get("phone"))
        self.ig = re.sub(r"[^a-z0-9]", "", (s.get("ig") or "").lower())

    def name_hit(self, name):
        n = norm(name)
        if not n:
            return False
        compact = n.replace(" ", "")
        if len(self.comp) >= 5:
            return self.core <= set(n.split()) or self.comp in compact
        return len(self.full) >= 5 and self.full in compact

    def why(self, name, phones, email):
        why = []
        if len(self.phone) >= 10 and any(p and p[-8:] == self.phone[-8:] for p in phones):
            why.append("tel")
        if self.name_hit(name):
            why.append("nome")
        local = re.sub(r"[^a-z0-9]", "", (email or "").split("@")[0])
        if len(self.ig) >= 6 and (self.ig in norm(name).replace(" ", "")
                                  or (len(local) >= 6 and (self.ig in local or local in self.ig))):
            why.append("ig")
        return why


def main(src, dst):
    stores = [Store(i, s) for i, s in enumerate(json.load(open(src, encoding="utf-8")))]
    by_town = {}
    for st in stores:
        by_town.setdefault((_city_key(st.s["city"]), st.s["state"]), []).append(st)
    month = latest_month()
    hits = {}     # cnpj -> candidate
    clothing = {}  # basico -> [(row fields, town's stores)]: active clothing shops, matched on the razão social later
    with tempfile.TemporaryDirectory() as tmp:
        def fetch(name):
            path = os.path.join(tmp, name)
            download(month, name, path)
            return path

        towns = {code: _city_key(n) for code, n in parse_towns(fetch("Municipios.zip")).items()}
        for part in range(10):
            path = fetch(f"Estabelecimentos{part}.zip")
            for r in read_rows(path, ESTAB_COLUMNS):
                local = by_town.get((towns.get(r[20], ""), r[19]))
                if not local:
                    continue
                phones = [digits(receita_phone(r[21], r[22])), digits(receita_phone(r[23], r[24]))]
                cand = {"cnpj": r[0] + r[1] + r[2], "basico": r[0], "fantasia": r[4].strip(), "ativa": r[5] == "02",
                        "matriz": r[3] == "1", "cnae": r[11], "roupas": CLOTHING in (r[11], *r[12].split(",")),
                        "aberta": r[10], "telefone": receita_phone(r[21], r[22]), "email": r[27].strip().lower(),
                        "endereco": " ".join(p for p in (r[13], r[14], r[15], r[17]) if p.strip())}
                for st in local:
                    why = st.why(cand["fantasia"], phones, cand["email"])
                    if why:
                        hits.setdefault(cand["cnpj"], {**cand, "lojas": {}})["lojas"][st.i] = why
                if cand["roupas"] and cand["ativa"]:
                    clothing.setdefault(r[0], []).append((cand, local))
            os.remove(path)
            print(f"Estabelecimentos{part}: {len(hits)} candidatos, {len(clothing)} lojas de roupa", flush=True)
        wanted = {c["basico"] for c in hits.values()} | set(clothing)
        companies = {}
        for part in range(10):
            path = fetch(f"Empresas{part}.zip")
            for r in read_rows(path, COMPANY_COLUMNS):
                if r[0] in wanted:
                    companies[r[0]] = {"razao": r[1].strip(), "porte": r[5]}
            os.remove(path)
            print(f"Empresas{part}: {len(companies)}", flush=True)
        path = fetch("Simples.zip")
        mei = {r[0] for r in read_rows(path, SIMPLES_COLUMNS) if r[4] == "S" and r[0] in wanted}
        os.remove(path)

    for basico, rows in clothing.items():  # "SANDRA DOS SANTOS JANSSEN" is the store "Sandra Janssen"
        razao = companies.get(basico, {}).get("razao", "")
        for cand, local in rows:
            for st in local:
                why = st.why(razao, [], cand["email"])
                if why and st.i not in hits.get(cand["cnpj"], {}).get("lojas", {}):
                    hits.setdefault(cand["cnpj"], {**cand, "lojas": {}})["lojas"][st.i] = why
    with SessionLocal() as db:
        leads = {c: s for c, s in db.query(Lead.cnpj, Lead.status)}
        customers = customer_cnpjs(db)
    out = [[] for _ in stores]
    for cnpj, c in hits.items():
        comp = companies.get(c["basico"], {})
        c.update(razao=comp.get("razao", ""), porte={"01": "ME", "03": "EPP", "05": "Demais"}.get(comp.get("porte"), "?"),
                 mei=c["basico"] in mei, lead=leads.get(cnpj), cliente=cnpj in customers)
        for i, why in c.pop("lojas").items():
            out[int(i)].append({**c, "por": "+".join(why)})
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"Pronto: {sum(1 for o in out if o)} de {len(stores)} lojas com candidato. Resultado em {dst}", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
