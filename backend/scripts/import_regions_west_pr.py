"""Cadastra as 84 cidades do PR com DDD 45 e 46 (docs/superpowers/cidades_ddd_45_46.xlsx) na região do Luiz Fernando.

Mesmas regras e uso do import_regions_pr.py (precisa dele na mesma pasta):
    python3 import_regions_west_pr.py              # simula
    python3 import_regions_west_pr.py --apply      # grava (com cópia de segurança antes)
"""
import sys

import import_regions_pr as base

base.STATE = "PR"
base.MOVE = set()
base.REGIONS = {
    "luiz": [
        "Anahy", "Boa Vista da Aparecida", "Braganey", "Cafelândia", "Campo Bonito", "Capitão Leônidas Marques",
        "Cascavel", "Catanduvas", "Céu Azul", "Corbélia", "Diamante do Sul", "Diamante d'Oeste",
        "Entre Rios do Oeste", "Foz do Iguaçu", "Guaraniaçu", "Ibema", "Iguatu", "Itaipulândia", "Lindoeste",
        "Marechal Cândido Rondon", "Matelândia", "Medianeira", "Mercedes", "Missal", "Nova Aurora",
        "Nova Santa Rosa", "Ouro Verde do Oeste", "Pato Bragado", "Quatro Pontes", "Ramilândia", "Santa Helena",
        "Santa Lúcia", "Santa Tereza do Oeste", "Santa Terezinha de Itaipu", "São José das Palmeiras",
        "São Miguel do Iguaçu", "Serranópolis do Iguaçu", "Toledo", "Três Barras do Paraná", "Vera Cruz do Oeste",
        "Ampére", "Barracão", "Bela Vista da Caroba", "Boa Esperança do Iguaçu", "Bom Jesus do Sul",
        "Bom Sucesso do Sul", "Capanema", "Chopinzinho", "Clevelândia", "Coronel Domingos Soares", "Coronel Vivida",
        "Cruzeiro do Iguaçu", "Dois Vizinhos", "Enéas Marques", "Espigão Alto do Iguaçu", "Flor da Serra do Sul",
        "Francisco Beltrão", "Honório Serpa", "Itapejara d'Oeste", "Manfrinópolis", "Mangueirinha", "Mariópolis",
        "Marmeleiro", "Nova Esperança do Sudoeste", "Nova Prata do Iguaçu", "Palmas", "Pato Branco",
        "Pérola d'Oeste", "Pinhal de São Bento", "Planalto", "Pranchita", "Quedas do Iguaçu", "Realeza",
        "Renascença", "Salgado Filho", "Salto do Lontra", "Santa Izabel do Oeste", "Santo Antônio do Sudoeste",
        "São João", "São Jorge d'Oeste", "Saudade do Iguaçu", "Sulina", "Verê", "Vitorino",
    ],
}

if __name__ == "__main__":
    base.main(sys.argv[1:])
