"""Cadastra as cidades do PR (lista impressa, docs/superpowers/WhatsApp Image 2026-10-28 ...) nas regiões
dos vendedores: as marcadas de laranja e com X vão para o Ivânio, Cruz Machado para a Márcia,
o resto (mais Mallet a Paranaguá, da página que faltava) para o Vinícius.

Só acrescenta: as cidades que o vendedor já tem continuam na região dele.
Se uma cidade já for da região de outro vendedor, para sem gravar nada (mesma regra da tela de usuários),
exceto as de MOVE, que passam para o vendedor da lista.

Roda direto no servidor, sem deploy e sem dependências (só Python 3).
Sem --apply só simula. Com --apply, faz antes uma cópia do banco (<banco>.bak-AAAAMMDD-HHMMSS).
Pode rodar mais de uma vez: não duplica nada.

Uso (na pasta do backend, onde fica o dimarcy.db):
    python3 import_regions_pr.py              # simula
    python3 import_regions_pr.py --apply      # grava
    python3 import_regions_pr.py --db /caminho/dimarcy.db --apply
"""
import os
import sqlite3
import sys
import time
import unicodedata

STATE = "PR"
REGIONS = {
    "vinicius": [
        "Adrianópolis", "Agudos do Sul", "Almirante Tamandaré", "Antonina", "Araucária", "Balsa Nova",
        "Bituruna", "Bocaiúva do Sul", "Campina Grande do Sul", "Campo Largo",
        "Campo Magro", "Carambeí", "Castro", "Cerro Azul", "Colombo", "Contenda", "Curitiba",
        "Doutor Ulysses", "Fazenda Rio Grande", "General Carneiro", "Guaraqueçaba", "Guaratuba", "Irati",
        "Itaperuçu", "Lapa", "Mallet", "Mandirituba", "Matinhos", "Morretes", "Palmeira", "Paranaguá",
        "Paulo Frontin", "Pinhais", "Piraquara", "Ponta Grossa", "Pontal do Paraná",
        "Porto Amazonas", "Porto Vitória", "Quatro Barras", "Quitandinha", "Rebouças",
        "Rio Branco do Sul", "São José dos Pinhais", "Tijucas do Sul", "Tunas do Paraná",
    ],
    "ivanio": [
        "Antônio Olinto", "Campo do Tenente", "Paula Freitas", "Piên", "Rio Azul", "São João do Triunfo",
        "São Mateus do Sul", "União da Vitória",
    ],
    "marcia": ["Cruz Machado"],
}
# already in another seller's region in production; the list wins (confirmed 2026-10-28)
MOVE = {"Agudos do Sul", "Mallet"}


def fold(text):
    """Lowercase without accents, so "Ivânio" == "ivanio"."""
    return "".join(c for c in unicodedata.normalize("NFD", text or "").casefold() if unicodedata.category(c) != "Mn")


def city_key(city):
    """Same as app.sales._city_key, so the app finds these rows."""
    plain = unicodedata.normalize("NFD", city).encode("ascii", "ignore").decode()
    return " ".join(plain.lower().split())


def run(con, apply):
    cur = con.cursor()
    users = cur.execute("SELECT id, name FROM users").fetchall()
    owners = {(key, state): uid for uid, key, state in cur.execute("SELECT user_id, city_key, state FROM seller_cities")}
    names = dict(users)

    plan, conflicts = [], []  # validate everything before writing anything
    for seller, cities in REGIONS.items():
        found = [(uid, name) for uid, name in users if seller in fold(name).split()]
        if len(found) != 1:
            raise SystemExit("Esperava 1 usuário chamado %r, achei %d: %r. Nada foi gravado." % (seller, len(found), found))
        uid = found[0][0]
        for city in cities:
            owner = owners.get((city_key(city), STATE))
            if owner is not None and owner != uid:
                if city not in MOVE:
                    conflicts.append("  %s: já é de %s, a lista manda para %s" % (city, names[owner], names[uid]))
                    continue
                plan.append((uid, city, names[owner]))
            else:
                plan.append((uid, city, owner is None))
    if conflicts:
        raise SystemExit("Cidades em conflito:\n%s\nNada foi gravado." % "\n".join(conflicts))

    stats = {}
    for uid, city, new in plan:
        row = stats.setdefault(names[uid], {"novas": 0, "já tinha": 0})
        if isinstance(new, str):  # moved from another seller
            cur.execute("UPDATE seller_cities SET user_id = ?, city = ? WHERE city_key = ? AND state = ?",
                        (uid, city, city_key(city), STATE))
            row["veio de %s" % new] = row.get("veio de %s" % new, []) + [city]
        elif new:
            cur.execute("INSERT INTO seller_cities (user_id, city, state, city_key) VALUES (?, ?, ?, ?)",
                        (uid, city, STATE, city_key(city)))
            row["novas"] += 1
        else:
            row["já tinha"] += 1

    if apply:
        con.commit()
    else:
        con.rollback()
    return stats


def main(argv):
    db_path = argv[argv.index("--db") + 1] if "--db" in argv else "dimarcy.db"
    apply = "--apply" in argv
    if not os.path.isfile(db_path):
        raise SystemExit("Banco não encontrado: %s (use --db /caminho/do/dimarcy.db)" % os.path.abspath(db_path))

    if apply:  # safety copy, using SQLite's own online backup
        backup = "%s.bak-%s" % (db_path, time.strftime("%Y%m%d-%H%M%S"))
        with sqlite3.connect(db_path) as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
        print("Cópia de segurança: %s" % backup)

    con = sqlite3.connect(db_path)
    try:
        stats = run(con, apply)
    finally:
        con.close()
    print("Banco: %s" % os.path.abspath(db_path))
    for k, v in stats.items():
        print("  %s: %s" % (k, v))
    print("Gravado." if apply else "Simulação: nada foi gravado. Rode de novo com --apply para gravar.")


if __name__ == "__main__":
    main(sys.argv[1:])
