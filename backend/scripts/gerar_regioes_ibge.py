"""Regenerates the Regiões screen's data from the IBGE. Only needed if the IBGE changes or another state is added:
frontend/src/assets/br-regions.json (UF -> mesorregião -> microrregião -> cities, sorted) and
br-cities.json (UF -> cities, the whole country, for the search).

Uso (na pasta do backend):  python scripts/gerar_regioes_ibge.py
"""
import gzip
import json
import os
import urllib.request

STATES = ("SC", "PR", "RS")
URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{}/municipios"
ALL_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"
ASSETS = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "assets")


def fetch(url):
    raw = urllib.request.urlopen(url, timeout=120).read()
    return json.loads(gzip.decompress(raw) if raw.startswith(b"\x1f\x8b") else raw)  # the IBGE gzips regardless of Accept-Encoding


def write(name, data):
    with open(os.path.join(ASSETS, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


regions = {}
for uf in STATES:
    regions[uf] = {}
    for town in fetch(URL.format(uf)):
        micro = town["microrregiao"]
        regions[uf].setdefault(micro["mesorregiao"]["nome"], {}).setdefault(micro["nome"], []).append(town["nome"])
    regions[uf] = {meso: {m: sorted(c) for m, c in sorted(micros.items())} for meso, micros in sorted(regions[uf].items())}

write("br-regions.json", regions)

country = {}
for town in fetch(ALL_URL):
    country.setdefault(town["UF-sigla"], []).append(town["municipio-nome"])
write("br-cities.json", {uf: sorted(c) for uf, c in sorted(country.items())})
print(sum(len(c) for c in country.values()), "cidades")
