"""Cadastra as 149 cidades de SC com DDD 49 (docs/superpowers/cidades_DDD_49_Santa_Catarina.pdf) na região do Édipo.

Mesmas regras e uso do importar_regioes_pr.py (precisa dele na mesma pasta):
    python3 importar_regioes_sc.py              # simula
    python3 importar_regioes_sc.py --apply      # grava (com cópia de segurança antes)
"""
import sys

import importar_regioes_pr as base

base.STATE = "SC"
# were Ivanio's in production; moved to Édipo (confirmed 2026-10-29)
base.MOVE = {"Santa Cecília", "São Cristóvão do Sul"}
base.REGIONS = {
    "edipo": [
        "Abdon Batista", "Abelardo Luz", "Água Doce", "Águas de Chapecó", "Águas Frias", "Alto Bela Vista",
        "Anchieta", "Anita Garibaldi", "Arabutã", "Arroio Trinta", "Arvoredo", "Bandeirante", "Barra Bonita",
        "Belmonte", "Bocaina do Sul", "Bom Jardim da Serra", "Bom Jesus", "Bom Jesus do Oeste", "Bom Retiro",
        "Brunópolis", "Caçador", "Caibi", "Calmon", "Campo Belo do Sul", "Campo Erê", "Campos Novos",
        "Capão Alto", "Capinzal", "Catanduvas", "Caxambu do Sul", "Celso Ramos", "Cerro Negro", "Chapecó",
        "Concórdia", "Cordilheira Alta", "Coronel Freitas", "Coronel Martins", "Correia Pinto", "Cunha Porã",
        "Cunhataí", "Curitibanos", "Descanso", "Dionísio Cerqueira", "Entre Rios", "Erval Velho",
        "Faxinal dos Guedes", "Flor do Sertão", "Formosa do Sul", "Fraiburgo", "Frei Rogério", "Galvão",
        "Guaraciaba", "Guarujá do Sul", "Guatambú", "Herval d'Oeste", "Ibiam", "Ibicaré", "Iomerê", "Ipira",
        "Iporã do Oeste", "Ipuaçu", "Ipumirim", "Iraceminha", "Irani", "Irati", "Itá", "Itapiranga", "Jaborá",
        "Jardinópolis", "Joaçaba", "Jupiá", "Lacerdópolis", "Lages", "Lajeado Grande", "Lebon Régis",
        "Lindóia do Sul", "Luzerna", "Macieira", "Maravilha", "Marema", "Matos Costa", "Modelo", "Mondaí",
        "Monte Carlo", "Nova Erechim", "Nova Itaberaba", "Novo Horizonte", "Otacílio Costa", "Ouro",
        "Ouro Verde", "Paial", "Painel", "Palma Sola", "Palmeira", "Palmitos", "Paraíso", "Passos Maia",
        "Peritiba", "Pinhalzinho", "Pinheiro Preto", "Piratuba", "Planalto Alegre", "Ponte Alta",
        "Ponte Alta do Norte", "Ponte Serrada", "Presidente Castello Branco", "Princesa", "Quilombo",
        "Rio das Antas", "Rio Rufino", "Riqueza", "Romelândia", "Saltinho", "Salto Veloso", "Santa Cecília",
        "Santa Helena", "Santa Terezinha do Progresso", "Santiago do Sul", "São Bernardino", "São Carlos",
        "São Cristóvão do Sul", "São Domingos", "São João do Oeste", "São Joaquim", "São José do Cedro",
        "São José do Cerrito", "São Lourenço do Oeste", "São Miguel da Boa Vista", "São Miguel do Oeste",
        "Saudades", "Seara", "Serra Alta", "Sul Brasil", "Tangará", "Tigrinhos", "Timbó Grande", "Treze Tílias",
        "Tunápolis", "União do Oeste", "Urubici", "Urupema", "Vargeão", "Vargem", "Vargem Bonita", "Videira",
        "Xanxerê", "Xavantina", "Xaxim", "Zortéa",
    ],
}

if __name__ == "__main__":
    base.main(sys.argv[1:])
